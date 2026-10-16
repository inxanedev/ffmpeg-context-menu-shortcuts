import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
import winreg

REPO_URL = "https://github.com/inxanedev/ffmpeg-context-menu-shortcuts"

VIDEO_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".ts",
]

BASE = r"Software\Classes\SystemFileAssociations"

TWEAKS = {
    "compress": {
        "title": "inx: compress video",
        "desc": "Re-encode with libx264 (CRF 24) into <name>-compressed.mp4",
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


def _key_path(ext, tweak_id):
    return rf"{BASE}\{ext}\shell\inx_{tweak_id}"


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
        main = ttk.Frame(self, padding=16)
        main.grid(sticky="nsew")

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
    cmd = ["ffmpeg", "-y", "-i", path, *tweak["ffmpeg_args"], out]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        input("ffmpeg failed. Press Enter to close...")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--run":
        run_tweak(sys.argv[2], sys.argv[3])
    else:
        App().mainloop()
