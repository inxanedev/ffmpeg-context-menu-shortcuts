# ffmpeg-context-menu-shortcuts

A small Windows GUI to toggle **right-click context-menu shortcuts for video files** that run [ffmpeg](https://ffmpeg.org/). No admin rights required.

Made by [inxanedev](https://github.com/inxanedev).

## What it does

The tool adds (or removes) two entries to the right-click menu of common video files
(`.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.3gp`, `.ts`):

| Menu entry | Action |
| --- | --- |
| **inx: compress video** | Re-encodes with `libx264` (CRF 24, preset `medium`) + AAC 128k into `<name>-compressed.mp4` in the same folder. |
| **inx: extract audio** | Extracts the audio track to MP3 (`libmp3lame`, VBR `-q:a 2`) into `<name>-audioextracted.mp3` in the same folder. |

Both output files are written next to the original video with the suffix `-compressed` or
`-audioextracted`.

## Requirements

- **Windows** (uses the Windows registry).
- **Python 3** with Tkinter (bundled with the standard python.org Windows installer).
- **ffmpeg must be in your `PATH`** so the context-menu commands can find it.

To check that ffmpeg is available, open a terminal and run:

```
ffmpeg -version
```

If that fails, install ffmpeg and add its `bin` folder to your `PATH` (or use
`winget install Gyan.FFmpeg`), then reopen your terminal.

## How it works

Run the script (or double-click it) to open the GUI:

```
python ffmpeg_context_menu.py
```

Each option is a checkbox showing its current state:

- **Toggling an option on** writes registry entries under
  `HKEY_CURRENT_USER\Software\Classes\SystemFileAssociations\<ext>\shell\inx_*`
  for every supported video extension. Because everything lives under `HKCU`, **no administrator
  rights are needed**, and the entries only affect the current user.
- **Toggling an option off** deletes those keys, which removes the menu entry.

The context-menu command launches the script again in a hidden mode
(`ffmpeg_context_menu.py --run <tweak> "<file>"`). That mode builds the output path from the
selected file and calls ffmpeg, so files with spaces or unusual names are handled correctly.
A console window shown during processing displays ffmpeg's progress.

> **Note:** if you move or rename `ffmpeg_context_menu.py` after enabling a tweak, the menu entry
> points to the old location. Just toggle the option off and on again to refresh it.

## Usage

1. Make sure ffmpeg is in your `PATH`.
2. Run `ffmpeg_context_menu.py`.
3. Tick the tweaks you want.
4. Right-click a video file and choose **inx: compress video** or **inx: extract audio**.
5. To undo, untick the tweaks (or use the **Refresh** button to re-read the current state).
