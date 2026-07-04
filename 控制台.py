# -*- coding: utf-8 -*-
"""
NTE 繁化版 控制台
================
一個圖形介面，一眼看清楚：
  - 環境是否正常（Python / 主程式 / 套件 / 手把驅動 / 已轉繁）
  - 主程式(作者) 與 繁化補丁 是否為最新版
  - 一鍵操作：啟動、更新主程式、更新補丁、修復、看說明
用 Tkinter（Python 內建），不需先裝任何套件即可執行。
"""
import os
import sys
import json
import glob
import shutil
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import ttk
from pathlib import Path

HERE = Path(__file__).parent.resolve()

AUTHOR_REPO = "hxwd94666/NTE-Drive-Calc"
PATCH_REPO = "lone4968-ui/NTE-Drive-Calc-zhTW-Patch"  # 本補丁的 GitHub 庫（需 Public 才能自動更新）

# 補丁更新時要覆蓋的檔案 / 資料夾（相對 repo 根）；不動使用者資料
PATCH_FILES = ["README.md", "使用說明.txt", "一鍵安裝.bat",
               "異環計算器繁中控制台.bat", "控制台.py", "_patch"]

# 需要的執行套件（顯示用的是 import 名稱）
ESSENTIALS = [
    "PySide6", "rapidocr_onnxruntime", "onnxruntime", "cv2", "numpy",
    "scipy", "PIL", "pydantic", "loguru", "pyautogui", "keyboard",
    "mss", "pypinyin", "vgamepad", "opencc",
]

# ── 顏色 ──
BG, CARD, TEXT, MUTED = "#1e1e2e", "#2a2a3a", "#e6e6e6", "#9aa0aa"
OK, BAD, WARN, ACCENT = "#4ade80", "#f87171", "#fbbf24", "#58a6ff"


# ── 環境探測 ────────────────────────────────────────────────
def find_program_root():
    for sub in sorted(HERE.glob("NTE-Drive-Calc*")):
        if (sub / "main.py").exists():
            return sub
    if (HERE / "main.py").exists():
        return HERE
    return None


def find_python():
    cands = []
    la = os.environ.get("LOCALAPPDATA", "")
    if la:
        cands += glob.glob(la + r"\Programs\Python\Python*\python.exe")
        cands += glob.glob(la + r"\Python\python.exe")
        cands += glob.glob(la + r"\Python\*\python.exe")
    pf = os.environ.get("ProgramFiles", "")
    if pf:
        cands += glob.glob(pf + r"\Python*\python.exe")
    pfx = os.environ.get("ProgramFiles(x86)", "")
    if pfx:
        cands += glob.glob(pfx + r"\Python*\python.exe")
    for name in ("python", "py"):
        p = shutil.which(name)
        if p:
            cands.append(p)
    # 去重、排除商店假 python
    real, seen = [], set()
    for c in cands:
        cl = c.lower()
        if cl in seen or "windowsapps" in cl or not os.path.exists(c):
            continue
        seen.add(cl)
        real.append(c)
    # 優先選「已裝好 PySide6」的那個
    for c in real:
        try:
            if subprocess.run([c, "-c", "import PySide6"],
                             capture_output=True, timeout=20).returncode == 0:
                return c
        except Exception:
            pass
    return real[0] if real else (shutil.which("py") or shutil.which("python"))


def pythonw_of(py):
    """把 python.exe 換成 pythonw.exe（無主控台版），找不到就用原本的"""
    if not py:
        return py
    cand = os.path.join(os.path.dirname(py), "pythonw.exe")
    return cand if os.path.exists(cand) else py


def gh_latest(repo):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/main",
        headers={"User-Agent": "NTE", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        d = json.loads(r.read().decode("utf-8"))
    date = (((d.get("commit") or {}).get("author") or {}).get("date", ""))[:10]
    return (d.get("sha") or "")[:12], date


def missing_packages(py):
    """回傳缺少的套件清單（用目標 python 檢查）"""
    code = ("import importlib.util as u,json;"
            "print(json.dumps([m for m in %r if u.find_spec(m) is None]))" % ESSENTIALS)
    try:
        out = subprocess.run([py, "-c", code], capture_output=True, text=True,
                             timeout=30).stdout.strip()
        return json.loads(out) if out else ESSENTIALS
    except Exception:
        return None  # 檢查失敗


def driver_ok(py):
    try:
        r = subprocess.run([py, "-c", "import vgamepad; vgamepad.VX360Gamepad()"],
                           capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def is_traditional(root):
    try:
        d = json.loads((root / "config" / "stats.json").read_text(encoding="utf-8"))
        ks = "".join(d.get("gold_base_values", {}).keys())
        return any(c in ks for c in "擊禦環傾")
    except Exception:
        return False


PREF_FILE = HERE / "控制台設定.json"


def load_pref():
    try:
        return json.loads(PREF_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_pref(d):
    try:
        PREF_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ── UI ──────────────────────────────────────────────────────
class Console:
    def __init__(self, root):
        self.root = root
        root.title("異環計算器繁中控制台")
        root.configure(bg=BG)
        root.geometry("640x620")
        root.minsize(560, 560)

        self.py = None
        self.prog = None
        self.proc = None          # 主程式子程序（控制台當房東）
        self.rows = {}
        self._cond = {}
        self._pref = load_pref()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 標題
        tk.Label(root, text="異環計算器繁中控制台", bg=BG, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 17, "bold")).pack(pady=(16, 2))
        tk.Label(root, text="异环驱动计算器 · 繁體中文補丁", bg=BG, fg=MUTED,
                 font=("Microsoft JhengHei UI", 9)).pack()

        # 狀態卡
        self.status_card = self._card("　環境檢查")
        for key, label in [
            ("python", "Python"),
            ("program", "主程式已下載"),
            ("packages", "套件齊全"),
            ("driver", "虛擬手把驅動"),
            ("trad", "已轉繁體"),
        ]:
            self.rows[key] = self._status_row(self.status_card, label)

        # 版本卡
        self.ver_card = self._card("　版本狀態")
        self.rows["ver_author"] = self._status_row(self.ver_card, "主程式（作者）")
        self.rows["ver_patch"] = self._status_row(self.ver_card, "繁化補丁")

        # 按鈕
        bf = tk.Frame(root, bg=BG)
        bf.pack(fill="x", padx=20, pady=(6, 4))
        self.btn_launch = self._btn(bf, "🚀 啟動程式", self.act_launch, ACCENT)
        self.btn_launch.pack(fill="x", pady=3)
        grid = tk.Frame(bf, bg=BG)
        grid.pack(fill="x")
        _btns = [
            ("🔄 重新檢查", self.refresh),
            ("⬇ 更新主程式", self.act_update_main),
            ("🔧 修復", self.act_repair),
            ("📖 使用說明", self.act_readme),
        ]
        for _i, (_t, _c) in enumerate(_btns):
            _r, _col = divmod(_i, 2)
            self._btn(grid, _t, _c, CARD).grid(row=_r, column=_col, sticky="ew", padx=3, pady=3)
        grid.columnconfigure(0, weight=1, uniform="btn")
        grid.columnconfigure(1, weight=1, uniform="btn")

        # 自動啟動開關
        self.auto_var = tk.BooleanVar(value=bool(self._pref.get("auto_launch", False)))
        cb = tk.Checkbutton(
            root, variable=self.auto_var,
            text="  檢查全過且為最新版時，開啟控制台後自動啟動程式",
            command=self._on_toggle, bg=BG, fg=TEXT, selectcolor=CARD,
            activebackground=BG, activeforeground=TEXT, bd=0,
            font=("Microsoft JhengHei UI", 9), anchor="w")
        cb.pack(fill="x", padx=20, pady=(2, 0))

        # 狀態列
        self.status = tk.StringVar(value="檢查中…")
        tk.Label(root, textvariable=self.status, bg=BG, fg=MUTED, anchor="w",
                 font=("Microsoft JhengHei UI", 9)).pack(fill="x", padx=20, pady=(4, 12))

        self.refresh()

    # -- 元件 --
    def _card(self, title):
        tk.Label(self.root, text=title, bg=BG, fg=TEXT, anchor="w",
                 font=("Microsoft JhengHei UI", 11, "bold")).pack(fill="x", padx=20, pady=(12, 2))
        c = tk.Frame(self.root, bg=CARD)
        c.pack(fill="x", padx=20)
        return c

    def _status_row(self, parent, label):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=12, pady=5)
        dot = tk.Label(row, text="●", bg=CARD, fg=MUTED, font=("Segoe UI", 11))
        dot.pack(side="left")
        tk.Label(row, text=label, bg=CARD, fg=TEXT, width=16, anchor="w",
                 font=("Microsoft JhengHei UI", 10)).pack(side="left", padx=(6, 0))
        val = tk.Label(row, text="檢查中…", bg=CARD, fg=MUTED, anchor="w",
                       font=("Microsoft JhengHei UI", 10))
        val.pack(side="left", fill="x", expand=True)
        return {"dot": dot, "val": val}

    def _btn(self, parent, text, cmd, bg):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=TEXT,
                         activebackground=bg, activeforeground=TEXT, bd=0,
                         font=("Microsoft JhengHei UI", 10, "bold"),
                         relief="flat", cursor="hand2", pady=9)

    def _set(self, key, color, text):
        r = self.rows[key]
        self.root.after(0, lambda: (r["dot"].config(fg=color), r["val"].config(text=text, fg=color)))

    # -- 檢查 --
    def refresh(self):
        self.status.set("檢查中…")
        for r in self.rows.values():
            r["dot"].config(fg=MUTED); r["val"].config(text="檢查中…", fg=MUTED)
        threading.Thread(target=self._do_checks, daemon=True).start()

    def _do_checks(self):
        c = self._cond = {}
        # Python
        self.py = find_python()
        if self.py:
            self._set("python", OK, os.path.basename(os.path.dirname(self.py)) + "  ✓")
        else:
            self._set("python", BAD, "找不到 → 請先跑「一鍵安裝.bat」或裝 Python")

        # 主程式
        self.prog = find_program_root()
        c["program"] = bool(self.prog)
        self._set("program", OK, "已下載 ✓") if self.prog else \
            self._set("program", BAD, "尚未安裝 → 點「更新主程式」")

        # 套件
        if self.py:
            miss = missing_packages(self.py)
            c["packages"] = (miss is not None and not miss)
            if miss is None:
                self._set("packages", WARN, "無法檢查")
            elif not miss:
                self._set("packages", OK, "全部齊全 ✓")
            else:
                self._set("packages", BAD, f"缺 {len(miss)} 個：{', '.join(miss[:4])}…")
        else:
            c["packages"] = False
            self._set("packages", MUTED, "需先有 Python")

        # 驅動
        if self.py:
            dok = driver_ok(self.py)
            c["driver"] = dok
            self._set("driver", OK if dok else WARN,
                      "正常 ✓" if dok else "未安裝（自動掃描才需要）")
        else:
            c["driver"] = False
            self._set("driver", MUTED, "需先有 Python")

        # 已轉繁
        if self.prog:
            trad = is_traditional(self.prog)
            c["trad"] = trad
            self._set("trad", OK if trad else BAD,
                      "是 ✓" if trad else "否 → 點「更新主程式」重轉")
        else:
            c["trad"] = False
            self._set("trad", MUTED, "需先安裝主程式")

        # 版本：作者
        c["author"] = self._check_version(
            "ver_author", AUTHOR_REPO,
            (self.prog / "_installed_commit.txt") if self.prog else None)
        # 版本：補丁
        if PATCH_REPO:
            c["patch"] = self._check_version("ver_patch", PATCH_REPO,
                                             HERE / "_patch_commit.txt", auto_baseline=True)
        else:
            c["patch"] = "ok"  # 未設定補丁庫時不擋自動啟動
            self._set("ver_patch", MUTED, "未設定補丁 GitHub 庫")

        self.root.after(0, lambda: self.status.set("檢查完成。"))
        self.root.after(0, self._after_checks)

    def _check_version(self, key, repo, marker, auto_baseline=False):
        """回傳 'latest' / 'outdated' / 'unknown' / 'offline'"""
        try:
            sha, date = gh_latest(repo)
        except Exception:
            self._set(key, WARN, "離線／無法連（私人庫需設 Public）")
            return "offline"
        cur = ""
        if marker and marker.exists():
            cur = marker.read_text(encoding="utf-8").strip()
        if not cur:
            if auto_baseline and marker:
                try:
                    marker.write_text(sha, encoding="utf-8")
                    self._set(key, OK, f"已是最新 ✓（{date}）")
                    return "latest"
                except Exception:
                    pass
            self._set(key, WARN, f"最新 {date}（本地版本未知）")
            return "unknown"
        elif cur == sha:
            self._set(key, OK, f"已是最新 ✓（{date}）")
            return "latest"
        else:
            self._set(key, WARN, f"有新版！（{date}）→ 點更新")
            return "outdated"

    def _after_checks(self):
        # 先處理補丁更新（若有），沒有再考慮自動啟動主程式
        if self._cond.get("patch") == "outdated" and self._prompt_patch_update():
            return
        self._maybe_autolaunch()

    def _prompt_patch_update(self):
        import ctypes
        r = ctypes.windll.user32.MessageBoxW(
            0, "繁化補丁有新版本！要現在更新嗎？\n（會下載最新補丁並覆蓋，不動你的掃描資料）",
            "補丁更新", 0x4 | 0x20 | 0x1000)
        if r == 6:  # IDYES
            threading.Thread(target=self._update_patch, daemon=True).start()
            return True
        return False

    def _update_patch(self):
        import urllib.request, zipfile, tempfile, shutil
        self.root.after(0, lambda: self.status.set("下載補丁更新中…"))
        try:
            url = f"https://github.com/{PATCH_REPO}/archive/refs/heads/main.zip"
            tmp = Path(tempfile.gettempdir()) / "nte_patch_update.zip"
            urllib.request.urlretrieve(url, str(tmp))
            exdir = Path(tempfile.gettempdir()) / "nte_patch_extract"
            if exdir.exists():
                shutil.rmtree(exdir, ignore_errors=True)
            with zipfile.ZipFile(str(tmp)) as z:
                z.extractall(str(exdir))
            roots = [p for p in exdir.iterdir() if p.is_dir()]
            if not roots:
                raise RuntimeError("解壓結果異常")
            src = roots[0]
            for name in PATCH_FILES:
                s = src / name
                d = HERE / name
                if not s.exists():
                    continue
                if s.is_dir():
                    if d.exists():
                        shutil.rmtree(d, ignore_errors=True)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            # GitHub 下載的 .bat 可能是 LF，Windows 批次檔需 CRLF，強制修正
            for bat in list(HERE.glob("*.bat")) + list((HERE / "_patch").glob("*.bat")):
                try:
                    raw = bat.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                    bat.write_bytes(raw)
                except Exception:
                    pass
            # 更新本地版本基準
            try:
                sha, _ = gh_latest(PATCH_REPO)
                (HERE / "_patch_commit.txt").write_text(sha, encoding="utf-8")
            except Exception:
                pass
            self.root.after(0, self._patch_updated_done)
        except Exception as e:
            self.root.after(0, lambda: self.status.set(f"補丁更新失敗：{e}"))

    def _patch_updated_done(self):
        self.status.set("補丁已更新，正在自動重新啟動控制台…")
        # 若主程式正在跑，先關掉（避免殘留）
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        # 用同一個 python（pythonw，繼承目前管理員權限）重開控制台，再關掉自己
        try:
            subprocess.Popen([sys.executable, str(HERE / "控制台.py")], cwd=str(HERE))
        except Exception as e:
            self.status.set(f"已更新，但自動重啟失敗，請手動重開：{e}")
            return
        self.root.after(1000, self.root.destroy)

    # -- 動作 --
    def _run_and_refresh(self, args, cwd=None):
        """在新主控台視窗跑，跑完自動重新檢查狀態"""
        try:
            proc = subprocess.Popen(args, cwd=cwd,
                                    creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            self.status.set(f"啟動失敗：{e}")
            return

        def _wait():
            try:
                proc.wait()
            except Exception:
                pass
            self.root.after(0, self.refresh)
        threading.Thread(target=_wait, daemon=True).start()

    def act_launch(self):
        if self.proc and self.proc.poll() is None:
            self.status.set("程式已在運行中。")
            return
        if not self.prog:
            self.status.set("主程式尚未安裝，請先點「更新主程式」。")
            return
        pyw = pythonw_of(self.py) if self.py else None
        if not pyw:
            self.status.set("找不到 Python，無法啟動。")
            return
        env = dict(os.environ)
        env["NTE_SKIP_UPDATE_CHECK"] = "1"   # 版本檢查由控制台負責，程式端不重複問
        try:
            self.proc = subprocess.Popen([pyw, str(self.prog / "_launcher.py")],
                                         cwd=str(self.prog), env=env)
        except Exception as e:
            self.status.set(f"啟動失敗：{e}")
            return
        self._set_running(True)
        self._poll_proc()

    def act_stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
        self._set_running(False)
        self.status.set("已停止程式。")

    def _set_running(self, running):
        if running:
            self.btn_launch.config(text="■ 停止程式（關閉控制台也會一起關）",
                                   command=self.act_stop, bg="#7a3b3b")
            self.status.set("▶ 程式運行中（控制台=運行中；關閉即結束）")
        else:
            self.btn_launch.config(text="🚀 啟動程式", command=self.act_launch, bg=ACCENT)

    def _poll_proc(self):
        if self.proc and self.proc.poll() is None:
            self.root.after(1000, self._poll_proc)
        else:
            self.proc = None
            self._set_running(False)
            self.status.set("程式已結束。")

    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.root.destroy()

    def act_update_main(self):
        self.status.set("更新/安裝中…（看新視窗；完成後會自動重新檢查）")
        self._run_and_refresh([str(HERE / "一鍵安裝.bat")], cwd=str(HERE))

    def act_repair(self):
        if not self.py:
            self.status.set("找不到 Python，無法修復。")
            return
        pkgs = ("opencc-python-reimplemented pyside6 rapidocr-onnxruntime onnxruntime "
                "opencv-python numpy scipy pillow pydantic loguru pyautogui keyboard "
                "mss pypinyin vgamepad")
        import tempfile
        bat = Path(tempfile.gettempdir()) / "nte_repair.bat"
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo Installing packages, please wait a few minutes...\r\n"
            f'"{self.py}" -m pip install {pkgs}\r\n'
            "echo.\r\n"
            "echo [Done] This window closes automatically...\r\n"
            "ping -n 3 127.0.0.1 >nul\r\n"
            "exit\r\n"
        )
        try:
            bat.write_text(content, encoding="utf-8")
        except Exception as e:
            self.status.set(f"修復失敗：{e}")
            return
        self.status.set("修復中…（看新視窗；完成後會自動重新檢查）")
        self._run_and_refresh([str(bat)])

    def act_readme(self):
        for name in ("使用說明.txt", "README.md"):
            p = HERE / name
            if p.exists():
                try:
                    self._show_text(name, p.read_text(encoding="utf-8"))
                except Exception as e:
                    self.status.set(f"開啟說明失敗：{e}")
                return
        self.status.set("找不到說明檔。")

    def _show_text(self, title, text):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.geometry("660x600")
        txt = tk.Text(win, bg=CARD, fg=TEXT, wrap="word", bd=0,
                      font=("Microsoft JhengHei UI", 10), padx=14, pady=12,
                      insertbackground=TEXT)
        sb = tk.Scrollbar(win, command=txt.yview)
        txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", text)
        txt.config(state="disabled")

    # -- 自動啟動 --
    def _on_toggle(self):
        self._pref["auto_launch"] = bool(self.auto_var.get())
        save_pref(self._pref)

    def _maybe_autolaunch(self):
        if not self.auto_var.get():
            return
        c = self._cond
        ok = (c.get("program") and c.get("packages") and c.get("driver")
              and c.get("trad") and c.get("author") == "latest"
              and c.get("patch") in ("latest", "ok"))
        if ok:
            self.status.set("全部正常，啟動程式中…")
            self.act_launch()
        else:
            self.status.set("有項目未通過或有新版，未自動啟動。")


def main():
    root = tk.Tk()
    try:
        Console(root)
    except Exception as e:
        import traceback
        traceback.print_exc()
        tk.Label(root, text=f"啟動失敗：{e}").pack()
    root.mainloop()


if __name__ == "__main__":
    main()
