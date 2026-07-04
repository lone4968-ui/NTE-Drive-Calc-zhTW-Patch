# -*- coding: utf-8 -*-
"""
NTE Drive Calc 繁體化補丁
=========================
把「异环驱动计算器」(简中版) 的設定檔與程式碼就地簡轉繁，
讓它可以正確辨識繁體中文版《異環》的詞條。

用法：
    python nte_traditionalizer.py                → 互動式，會問你程式資料夾在哪
    python nte_traditionalizer.py "C:\\路徑\\程式資料夾"   → 直接指定

原理：
    OpenCC (s2twp) 簡→繁 + 遊戲專有名詞校正對照表
    轉換前會自動備份到 _backup_簡體原版/，隨時可還原。

作者：你自己 (原程式來自 https://github.com/hxwd94666/NTE-Drive-Calc，本工具不含其任何程式碼)
"""

import sys
import io
import shutil
from pathlib import Path
from datetime import datetime

# 讓 Windows 主控台能印出中文
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

try:
    from opencc import OpenCC
except ImportError:
    print("❌ 缺少 OpenCC，請先執行：pip install opencc-python-reimplemented")
    sys.exit(1)

CC = OpenCC("s2twp")  # 簡體 → 繁體(台灣正體，含用語轉換)

# ── 專有名詞校正：OpenCC 轉錯或想強制指定的，寫在這 ──────────
# 格式： "OpenCC轉出來的錯誤" : "你要的正確繁體"
# 目前 s2twp 對此遊戲詞條表現良好，先留空，實測發現錯字再往這加。
GLOSSARY = {
    # 範例（若發現角色名/套裝名轉錯，照這格式加）：
    # "某錯字": "正確字",
}

# 只處理這些副檔名的檔案
JSON_GLOB = "*.json"
PY_SUFFIX = ".py"

# 要掃描的子資料夾（相對程式根目錄）
TARGET_DIRS = ["config", "src"]
TARGET_ROOT_FILES = ["main.py"]

# 不要碰的資料夾（測試、備份、快取）
SKIP_DIRS = {"tests", "_backup_簡體原版", "__pycache__", ".git", "assets"}


def convert_text(text: str) -> str:
    out = CC.convert(text)
    for wrong, right in GLOSSARY.items():
        out = out.replace(wrong, right)
    return out


def iter_target_files(root: Path):
    """列出所有要轉換的 .json 與 .py 檔"""
    # 根目錄指定檔
    for name in TARGET_ROOT_FILES:
        p = root / name
        if p.is_file():
            yield p
    # 子資料夾遞迴
    for d in TARGET_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.suffix == PY_SUFFIX or p.suffix == ".json":
                yield p


def make_backup(root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / "_backup_簡體原版" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for d in TARGET_DIRS:
        src = root / d
        if src.is_dir():
            shutil.copytree(src, backup_dir / d,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in TARGET_ROOT_FILES:
        p = root / name
        if p.is_file():
            shutil.copy2(p, backup_dir / name)
    return backup_dir


def main():
    print("=" * 56)
    print("  NTE Drive Calc 繁體化補丁")
    print("=" * 56)

    # 取得目標資料夾
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).expanduser().resolve()
    else:
        raw = input("\n請把「异环驱动计算器」的程式資料夾拖進來(或貼路徑)後按 Enter：\n> ").strip().strip('"')
        root = Path(raw).expanduser().resolve()

    if not root.is_dir():
        print(f"\n❌ 找不到資料夾：{root}")
        sys.exit(1)

    # 驗證看起來像不像那個程式
    if not (root / "config").is_dir() or not (root / "src").is_dir():
        print(f"\n⚠️ 這資料夾裡沒有 config/ 和 src/，可能不是程式根目錄。")
        print(f"   目前指到：{root}")
        if input("   仍要繼續嗎？(y/N) ").strip().lower() != "y":
            sys.exit(0)

    files = list(iter_target_files(root))
    print(f"\n找到 {len(files)} 個要轉換的檔案 (.json + .py)")

    # 備份
    print("\n[1/2] 備份簡體原版...")
    backup = make_backup(root)
    print(f"      ✅ 已備份到：{backup}")

    # 轉換
    print("\n[2/2] 開始簡轉繁...")
    changed = 0
    for p in files:
        try:
            original = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"      ⏭ 跳過(非utf-8)：{p.relative_to(root)}")
            continue
        converted = convert_text(original)
        if converted != original:
            p.write_text(converted, encoding="utf-8")
            changed += 1
            print(f"      ✓ {p.relative_to(root)}")

    print("\n" + "=" * 56)
    print(f"  完成！共轉換 {changed} 個檔案。")
    print("=" * 56)
    print(f"\n若要還原簡體版，把下列資料夾內容複製回去即可：")
    print(f"  {backup}")
    print(f"\n⚠️ 提醒：作者程式更新後，需要重新執行本補丁。")


if __name__ == "__main__":
    main()
