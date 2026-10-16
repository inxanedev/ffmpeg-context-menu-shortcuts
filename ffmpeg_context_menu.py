import json
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
import winreg

REPO_URL = "https://github.com/inxanedev/ffmpeg-context-menu-shortcuts"

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
CRF_MIN, CRF_MAX, CRF_DEFAULT = 18, 32, 24

DEFAULT_SETTINGS = {"crf": CRF_DEFAULT}

VIDEO_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".ts",
]

BASE = r"Software\Classes\SystemFileAssociations"

TWEAKS = {
    "compress": {
        "title": "inx: compress video",
        "desc": "Re-encode with libx264 (adjustable CRF) into <name>-compressed.mp4",
        "suffix": "-compressed.mp4",
        "ffmpeg_args": [
            "-c:v", "libx264", "-crf", "24", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        ],
    },
    "audio": {
        "title": "inx: extract audio",
        "desc": "Extract audio into <name>-audioextracted.mp3",
        "suffix": "-audioextracted.mp3",
        "ffmpeg_args": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    },
}


def _key_path(ext, tweak_id):
    return rf"{BASE}\{ext}\shell\inx_{tweak_id}"


def load_settings():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)
    try:
        crf = int(data.get("crf", CRF_DEFAULT))
    except (TypeError, ValueError):
        crf = CRF_DEFAULT
    return {"crf": min(CRF_MAX, max(CRF_MIN, crf))}


def save_settings(settings):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


def _console_exe():
    exe = sys.executable or "python"
    if exe.lower().endswith("pythonw.exe"):
        candidate = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(candidate):
            return candidate
    return exe


def _launcher_command(tweak_id):
    exe = _console_exe()
    script = os.path.abspath(__file__)
    return f'"{exe}" "{script}" --run {tweak_id} "%1"'


def _pythonw_exe():
    exe = sys.executable or "pythonw"
    if exe.lower().endswith("python.exe"):
        candidate = exe[: -len("python.exe")] + "pythonw.exe"
        if os.path.exists(candidate):
            return candidate
    return exe


def _ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def create_desktop_shortcut():
    script = os.path.abspath(__file__)
    workdir = os.path.dirname(script)
    target = _pythonw_exe()
    name = "FFMPEG shortcut gui.lnk"
    ps = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$desktop = [Environment]::GetFolderPath('Desktop')",
            f"$lnk = Join-Path $desktop {_ps_quote(name)}",
            "$ws = New-Object -ComObject WScript.Shell",
            "$sc = $ws.CreateShortcut($lnk)",
            f"$sc.TargetPath = {_ps_quote(target)}",
            f"$sc.Arguments = {_ps_quote(chr(34) + script + chr(34))}",
            f"$sc.WorkingDirectory = {_ps_quote(workdir)}",
            f"$sc.IconLocation = {_ps_quote(target + ',0')}",
            f"$sc.Description = {_ps_quote('FFMPEG context menu tweaks GUI')}",
            "$sc.Save()",
            "Write-Output $lnk",
        ]
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OSError((result.stderr or "Failed to create shortcut").strip())
    return result.stdout.strip()


def _delete_tree(root, path):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as k:
            subkeys = []
            i = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except FileNotFoundError:
        return
    for sub in subkeys:
        _delete_tree(root, path + "\\" + sub)
    winreg.DeleteKey(root, path)


def is_enabled(tweak_id):
    for ext in VIDEO_EXTENSIONS:
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, _key_path(ext, tweak_id)).Close()
        except FileNotFoundError:
            return False
    return True


def set_enabled(tweak_id, enabled):
    for ext in VIDEO_EXTENSIONS:
        path = _key_path(ext, tweak_id)
        if enabled:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE
            ) as k:
                winreg.SetValueEx(k, None, 0, winreg.REG_SZ, TWEAKS[tweak_id]["title"])
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, path + r"\command", 0, winreg.KEY_WRITE
            ) as k:
                winreg.SetValueEx(k, None, 0, winreg.REG_SZ, _launcher_command(tweak_id))
        else:
            _delete_tree(winreg.HKEY_CURRENT_USER, path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FFmpeg Context Menu Tweaks")
        self.resizable(False, False)
        self._busy = False
        self.vars = {}
        self._build()
        self.refresh()

    def _build(self):
        self.settings = load_settings()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        tweaks_tab = ttk.Frame(notebook, padding=16)
        settings_tab = ttk.Frame(notebook, padding=16)
        info_tab = ttk.Frame(notebook, padding=16)
        notebook.add(tweaks_tab, text="Tweaks")
        notebook.add(settings_tab, text="Settings")
        notebook.add(info_tab, text="Info")
        self._build_tweaks(tweaks_tab)
        self._build_settings(settings_tab)
        self._build_info(info_tab)

    def _build_tweaks(self, main):
        ttk.Label(
            main,
            text="Video file right-click menu tweaks",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(
            main,
            text="Toggle an option to add or remove it from the context menu.\n"
            "No admin rights needed (HKCU). ffmpeg must be in your PATH.",
            foreground="#555",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        row = 2
        for tweak_id, tweak in TWEAKS.items():
            var = tk.BooleanVar()
            self.vars[tweak_id] = var
            cb = ttk.Checkbutton(
                main,
                text=tweak["title"],
                variable=var,
                command=lambda t=tweak_id: self.toggle(t),
            )
            cb.grid(row=row, column=0, columnspan=2, sticky="w")
            ttk.Label(
                main, text=tweak["desc"], foreground="#777"
            ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=(22, 0))
            row += 2

        self.status = ttk.Label(main, text="", foreground="#0a7d00")
        self.status.grid(row=row, column=0, sticky="w", pady=(12, 0))
        ttk.Button(main, text="Refresh", command=self.refresh).grid(
            row=row, column=1, sticky="e", pady=(12, 0)
        )

        link = tk.Label(
            main,
            text="made by inxanedev",
            fg="#0a66c2",
            cursor="hand2",
            font=("Segoe UI", 8, "underline"),
        )
        link.grid(row=row + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        link.bind(
            "<Button-1>",
            lambda _e: webbrowser.open(REPO_URL),
        )

    def _build_settings(self, parent):
        ttk.Label(
            parent,
            text="Compression settings",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(
            parent,
            text="Quality (CRF). Lower = better quality and larger files.\n"
            "Higher = smaller files with more quality loss.",
            foreground="#555",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        self.crf_var = tk.IntVar(value=self.settings["crf"])
        self.crf_label = ttk.Label(
            parent, text=f"CRF: {self.settings['crf']}", font=("Segoe UI", 9, "bold")
        )
        self.crf_label.grid(row=2, column=0, columnspan=2, sticky="w")

        tk.Scale(
            parent,
            from_=CRF_MIN,
            to=CRF_MAX,
            orient="horizontal",
            resolution=1,
            length=300,
            variable=self.crf_var,
            command=self._on_crf_change,
            showvalue=False,
        ).grid(row=3, column=0, columnspan=2, sticky="we", pady=(4, 2))

        ends = ttk.Frame(parent)
        ends.grid(row=4, column=0, columnspan=2, sticky="we")
        ttk.Label(ends, text=f"{CRF_MIN} (better quality)", foreground="#777").pack(
            side="left"
        )
        ttk.Label(ends, text=f"{CRF_MAX} (smaller)", foreground="#777").pack(side="right")

        ttk.Label(
            parent,
            text="Applied to the \"inx: compress video\" shortcut.",
            foreground="#777",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Separator(parent, orient="horizontal").grid(
            row=6, column=0, columnspan=2, sticky="we", pady=(16, 12)
        )

        ttk.Label(
            parent, text="Desktop shortcut", font=("Segoe UI", 9, "bold")
        ).grid(row=7, column=0, columnspan=2, sticky="w")

        ttk.Label(
            parent,
            text="Add a shortcut to open this tool from your desktop.",
            foreground="#777",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 8))

        ttk.Button(
            parent, text="Create Desktop Shortcut", command=self._create_shortcut
        ).grid(row=9, column=0, columnspan=2, sticky="w")

        self.shortcut_status = ttk.Label(parent, text="", foreground="#0a7d00")
        self.shortcut_status.grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _create_shortcut(self):
        try:
            path = create_desktop_shortcut()
            self.shortcut_status.config(
                text=f"Shortcut created: {os.path.basename(path)}", foreground="#0a7d00"
            )
        except Exception as exc:
            self.shortcut_status.config(
                text="Failed to create shortcut.", foreground="#b00020"
            )
            messagebox.showerror("Shortcut error", str(exc))

    def _on_crf_change(self, value):
        crf = int(float(value))
        self.crf_label.config(text=f"CRF: {crf}")
        if crf != self.settings["crf"]:
            self.settings["crf"] = crf
            save_settings(self.settings)

    def _build_info(self, parent):
        ttk.Label(
            parent,
            text="How to use this tool",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        lines = [
            "1. Tweaks tab: tick a tweak to add it to the right-click menu of video "
            "files. Untick it to remove it. This saves instantly.",
            "2. Right-click any video file and pick \"inx: compress video\" or "
            "\"inx: extract audio\".",
            "3. Output is saved next to the video, named <name>-compressed.mp4 or "
            "<name>-audioextracted.mp3.",
            "4. A console window opens while ffmpeg runs and closes when it's done.",
            "",
            "Settings tab:",
            "- Drag the CRF slider to change compression quality. It applies to the "
            "next right-click automatically - you do NOT need to refresh or re-tick "
            "the tweak.",
            "",
            "Good to know:",
            "- ffmpeg must be installed and on your PATH, or the shortcuts will fail.",
            "- No admin rights are needed; everything is stored under your user account.",
            "- Use the Refresh button only if the registry was changed outside this app.",
            "- If you move or rename this script, untick and re-tick the tweaks so the "
            "saved paths update.",
        ]

        ttk.Label(
            parent,
            text="\n".join(lines),
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def refresh(self):
        for tweak_id, var in self.vars.items():
            var.set(is_enabled(tweak_id))
        self.set_status("Registry state loaded.", "#555")

    def set_status(self, text, color="#0a7d00"):
        self.status.config(text=text, foreground=color)

    def toggle(self, tweak_id):
        if self._busy:
            return
        self._busy = True
        desired = self.vars[tweak_id].get()
        try:
            set_enabled(tweak_id, desired)
            self.vars[tweak_id].set(is_enabled(tweak_id))
            state = "enabled" if desired else "disabled"
            self.set_status(f'"{TWEAKS[tweak_id]["title"]}" {state}.')
        except OSError as exc:
            self.vars[tweak_id].set(is_enabled(tweak_id))
            self.set_status("Failed to update registry.", "#b00020")
            messagebox.showerror("Registry error", str(exc))
        finally:
            self._busy = False


def run_tweak(tweak_id, path):
    tweak = TWEAKS.get(tweak_id)
    if tweak is None:
        return
    base, _ = os.path.splitext(path)
    out = base + tweak["suffix"]
    args = list(tweak["ffmpeg_args"])
    if tweak_id == "compress":
        crf = load_settings()["crf"]
        args[args.index("-crf") + 1] = str(crf)
    cmd = ["ffmpeg", "-y", "-i", path, *args, out]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        input("ffmpeg failed. Press Enter to close...")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--run":
        run_tweak(sys.argv[2], sys.argv[3])
    else:
        App().mainloop()
