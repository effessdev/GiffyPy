# GiffyPy

A simple video editor made **specifically for editing screen recordings**. Export videos to animated WebP, GIF, MP4, WebM, MOV, or MKV.

<img width="1292" height="741" alt="image" src="https://github.com/user-attachments/assets/d7a5bb0a-408a-45dc-8851-5003f3da7c6c" />

## Features

- **Non-Destructive Multi-Clip Timeline:**
  - Split video segments anywhere (`S` key).
  - Drag and drop clips to reorder them on the fly.
  - Drag clip edges to trim start and end points with live preview.
- **Interactive Visual Cropping:**
  - Resize and move an overlay crop rectangle with rule-of-thirds visual guides.
- **Flexible Export Options:**
  - Export to **WebP**, **GIF**, **MP4**, **WebM**, **MOV**, or **MKV**.
  - Adjust framerate (0.5 to 60 FPS), scaling/resolution %, and quality settings (automatic palette generation with dither controls for GIFs).
  - Four ways to save, each with its own button:
    - **Overwrite Existing File:** replaces the file next to the source video, with a confirmation prompt first.
    - **Save a Numbered Copy:** saves next to the source video as `name (edited N)` without replacing anything.
    - **Save To…:** opens a file dialog so you can pick the location and file name.
    - **Copy to Clipboard:** exports and copies the result to the clipboard (GIF and WebP only).
- **Fast Timeline Navigation & Controls:**
  - Scroll, zoom (`Ctrl + Wheel`), and pan (`Middle-click drag`) through complex timelines.
  - Frame-by-frame navigation using arrow keys.
- **Seamless Preview:**
  - Automatic background proxy generation for codecs not natively supported by Qt.

## Interface Layout

1. **Video Preview Panel:** Shows real-time playback and interactive crop region controls.
2. **Interactive Timeline:** Displays all clips sequentially. Scrub top ruler, trim clip handles, or reorder segments easily.
3. **Export Panel:** Fine-tune format, FPS, resolution scale, and output quality, then choose how to save with one of the four export buttons (Overwrite, Numbered Copy, Save To…, Copy to Clipboard).

## Prerequisites

FFmpeg should be installed and available in your `PATH`.

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Space` | Play / Pause |
| `S` | Split clip at current playhead position |
| `Delete` | Delete selected clip segment |
| `Ctrl + Z` | Undo last edit action |
| `Ctrl + O` | Open video file dialog |
| `Left Arrow` | Step 1 frame backward |
| `Right Arrow` | Step 1 frame forward |
| `Ctrl + =` / `Ctrl + +` | Zoom in timeline |
| `Ctrl + -` | Zoom out timeline |
| `Ctrl + 0` | Fit timeline to view |
| `Middle-Click Drag` | Pan timeline horizontally |
| `Ctrl + Scroll` | Zoom timeline centered at mouse cursor |

## Packaging to Standalone Executable (Windows)

To build a standalone executable on Windows using PyInstaller:

```cmd
package.bat
```

This compiles the app using `main.py` and includes `icon.ico`.
