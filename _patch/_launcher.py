# -*- coding: utf-8 -*-
"""
繁化版啟動器（免管理員）
繞過原程式的管理員自動重啟（那段在原始碼執行環境會閃退），
直接開起圖形介面。
探索介面、貼圖鑑定不需管理員；只有「自動掃描遊戲」需要，
若要用自動掃描，請改用『啟動繁化版_管理員.bat』。
"""
import sys
import os
import ctypes
from pathlib import Path

# ── 修正多螢幕 DPI 無限延伸 ──────────────────────────────
# 兩螢幕縮放不同(如 125% vs 100%)時，拖曳跨螢幕會觸發 DPI 事件迴圈，
# 視窗無限變大。強制「系統單一 DPI」即可切斷迴圈。
# 必須在建立任何 Qt 視窗之前執行。
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
try:
    # -2 = DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-2))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ── 自動尋找程式主體（含 src/ui/app.py 的資料夾）─────────
# 不管本檔是放在程式根目錄、還是放在補丁包根目錄（程式在
# NTE-Drive-Calc-main 子資料夾），都能找到並啟動。
HERE = Path(__file__).parent.resolve()


def _find_program_root(start: Path):
    if (start / "src" / "ui" / "app.py").exists():
        return start
    # 優先找 NTE-Drive-Calc* 子資料夾
    for sub in sorted(start.glob("NTE-Drive-Calc*")):
        if (sub / "src" / "ui" / "app.py").exists():
            return sub
    # 退而求其次：掃描所有子資料夾
    for sub in start.iterdir():
        if sub.is_dir() and (sub / "src" / "ui" / "app.py").exists():
            return sub
    return None


ROOT = _find_program_root(HERE)
if ROOT is None:
    print("=" * 50)
    print("[X] 找不到程式主體（缺少 src 資料夾）。")
    print("    請先執行『一鍵安裝.bat』下載並安裝程式，")
    print("    或確認 NTE-Drive-Calc-main 資料夾與本檔在一起。")
    print("=" * 50)
    input("按 Enter 關閉...")
    sys.exit(1)

os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))

# ── 自我修復：缺套件就用「正在執行的這個 python」自動補裝 ──
# 注意：不照 requirements.txt 全裝，因為它硬鎖 rapidocr-openvino>=1.4.0，
# 新版 Python(如 3.13)沒有對應版本會導致整包失敗。改裝「精選必要清單」
# (不鎖版本)，OCR 用 rapidocr-onnxruntime 即可，openvino/directml 為選用。
# (pip 安裝名稱, python import 名稱) — 兩者常不同
_ESSENTIALS = [
    ("pyside6", "PySide6"),
    ("rapidocr-onnxruntime", "rapidocr_onnxruntime"),
    ("onnxruntime", "onnxruntime"),
    ("opencv-python", "cv2"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("pillow", "PIL"),
    ("pydantic", "pydantic"),
    ("loguru", "loguru"),
    ("pyautogui", "pyautogui"),
    ("keyboard", "keyboard"),
    ("mss", "mss"),
    ("pypinyin", "pypinyin"),
    ("vgamepad", "vgamepad"),
    ("opencc-python-reimplemented", "opencc"),
]


def _ensure_deps():
    import importlib
    import importlib.util

    def _installed(mod):
        try:
            return importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            return False

    # 逐一檢查，缺哪個裝哪個（不能只看 PySide6，否則後加的
    # vgamepad 在「PySide6 已存在」時永遠不會被補裝）
    missing = [pip for pip, mod in _ESSENTIALS if not _installed(mod)]
    if not missing:
        return

    import subprocess
    print("=" * 50)
    print("偵測到缺少套件，正在自動安裝（第一次需要幾分鐘）...")
    print("缺少：", ", ".join(missing))
    print("使用的 Python：", sys.executable)
    print("=" * 50)
    rc = subprocess.call([sys.executable, "-m", "pip", "install"] + missing)
    if rc != 0:
        for pkg in missing:
            subprocess.call([sys.executable, "-m", "pip", "install", pkg])
    importlib.invalidate_caches()

    still = [pip for pip, mod in _ESSENTIALS if not _installed(mod)]
    if still:
        print("❌ 以下套件安裝後仍無法載入，請截圖回報：", ", ".join(still))
        input("按 Enter 關閉...")
        sys.exit(1)
    print("✅ 相依套件安裝完成。")

_ensure_deps()

import src.ui.app as app

# 繞過管理員檢查／自動重啟
app._ensure_admin = lambda: None
app._is_admin = lambda: True


# ── OCR 輸出正規化 ──────────────────────────────────────────
# RapidOCR 模型偏簡體、且常把「擊」誤讀成「擎」等，導致辨識出的
# 詞條對不上繁體 config（一張圖要湊滿 4 條有效副屬性才算成功，
# 差一條就整張進 failed）。這裡在比對前修正 OCR 文字：
#   1) 修常見誤字（OpenCC 不會處理的，如 擎→擊）
#   2) 簡轉繁（属→屬、强→強、倾→傾…）
# 讓 OCR 文字對得上繁體詞條。
def _patch_ocr_normalization():
    # OCR 引擎一定要在，否則無法掛鉤
    try:
        import src.scanner.ocr_engine as _oe
    except Exception as e:
        print("（OCR 正規化未啟用，找不到 OCR 引擎：", e, "）")
        return

    # 簡轉繁（s2twp）需要 opencc；沒裝也沒關係，誤字修正照樣套用。
    # 實測這遊戲的 RapidOCR 幾乎都讀成繁體，真正救回失敗圖的是下面的誤字修正表，
    # 簡轉繁只是保險，所以 opencc 缺席時不該讓整個正規化跟著失效。
    try:
        from opencc import OpenCC
        _cc = OpenCC("s2twp")  # 與 config 轉換用同一模式，確保結果一致
    except Exception as e:
        _cc = None
        print("（注意：opencc 未安裝，簡轉繁停用，但誤字修正仍生效；建議按『修復』補裝 opencc）：", e)

    # 純誤字修正（非簡繁，OpenCC 不會修）。RapidOCR 對筆畫多的字（擊、禦）
    # 偶爾會誤讀或整個漏掉，導致詞條對不上、湊不滿 4 條而整張失敗。
    # 以下為實測收集到的常見錯法，直接補回正確片段（皆非任何正確詞條的子字串，不會誤傷）：
    _FIX = {
        "擎": "擊",            # 「擊」最常被讀成「擎」：攻擎力 / 暴擎傷害 / 暴擎率
        "攻力": "攻擊力",       # 漏掉「擊」
        "防力": "防禦力",       # 漏掉「禦」
        "暴傷害": "暴擊傷害",   # 漏掉「擊」
        "暴率": "暴擊率",       # 漏掉「擊」
    }

    def _norm(t):
        t = str(t)
        for k, v in _FIX.items():
            t = t.replace(k, v)
        return _cc.convert(t) if _cc is not None else t

    _orig_text = _oe.OCREngine.extract_text
    def _patched_text(self, img):
        return [_norm(t) for t in _orig_text(self, img)]
    _oe.OCREngine.extract_text = _patched_text

    _orig_lines = _oe.OCREngine.extract_lines
    def _patched_lines(self, img):
        out = _orig_lines(self, img)
        for d in out:
            if isinstance(d, dict) and "text" in d:
                d["text"] = _norm(d["text"])
        return out
    _oe.OCREngine.extract_lines = _patched_lines


_patch_ocr_normalization()


# ── 開機時檢查作者是否有新版（比對 GitHub main 最新 commit）──
# 安裝時 一鍵安裝.bat 會把當下的 commit 記到 _installed_commit.txt，
# 這裡比對線上最新 commit，不同就提示。離線/失敗都靜默跳過。
def _check_update():
    if os.environ.get("NTE_SKIP_UPDATE_CHECK"):
        return  # 由控制台負責版本檢查，避免重複詢問
    try:
        import urllib.request
        import json
        marker = ROOT / "_installed_commit.txt"
        current = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
        req = urllib.request.Request(
            "https://api.github.com/repos/hxwd94666/NTE-Drive-Calc/commits/main",
            headers={"User-Agent": "NTE-Trad-Patch",
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        sha = (data.get("sha") or "")[:12]
        date = ((data.get("commit") or {}).get("author") or {}).get("date", "")[:10]
        if current and sha and sha != current:
            import ctypes
            msg = (f"作者發布了新版本！(更新日期 {date})\n\n"
                   "要現在更新嗎？\n\n"
                   "• 按「是」：自動關閉程式並執行更新\n"
                   "           (你的掃描資料會保留)\n"
                   "• 按「否」：這次先不更新，直接開程式")
            # MB_YESNO(0x4) | MB_ICONQUESTION(0x20) | MB_SYSTEMMODAL(0x1000)
            res = ctypes.windll.user32.MessageBoxW(
                0, msg, "NTE 繁化版 — 發現作者新版本", 0x4 | 0x20 | 0x1000)
            if res == 6:  # IDYES
                installer = ROOT.parent / "一鍵安裝.bat"
                if installer.exists():
                    import subprocess
                    subprocess.Popen(["cmd", "/c", "start", "", str(installer)],
                                     cwd=str(ROOT.parent))
                    sys.exit(0)  # 退出本程式，讓更新器能取代資料夾
                else:
                    ctypes.windll.user32.MessageBoxW(
                        0, "找不到「一鍵安裝.bat」，請手動執行更新。", "提示", 0x30)
        elif not current:
            # 首次沒有標記檔，順手寫入目前最新，之後才能比對
            try:
                marker.write_text(sha, encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass  # 離線或 API 失敗 → 不影響啟動


_check_update()

app.run_gui()
