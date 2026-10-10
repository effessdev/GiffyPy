# GiffyPy

A simple and fast video editor made **specifically for editing screen recordings for your project README**. Export to animated WebP, GIF, MP4, WebM, MOV, or MKV. Opens in under a second. Instant timeline scrubbing (no loading screens, ever).

<img width="1287" alt="image" src="https://github.com/user-attachments/assets/1e386c9f-665a-4cfe-bec7-9bc16aed9114" />

---

## Goal of the editor

Make editing screen recordings of your project for your README extremely fast and effortless, so you can focus on the project instead marketing.

## Features

### ✂️ Interactive Visual Cropping

- Resize and move an overlay crop rectangle.
- Use the rule-of-thirds visual guides to help position the crop.

### 🎬 Non-Destructive Multi-Clip Timeline

Edit and arrange video segments without destructively modifying the original video.

- **Split clips:** Split video segments anywhere using the `S` key.
- **Reorder clips:** Drag and drop clips to reorder them on the fly.
- **Trim clips:** Drag clip edges to trim start and end points with live preview.

### 📤 Flexible Export Options

Export to **WebP, GIF, MP4, WebM, MOV, or MKV**.

Customize your exports with these settings:

- **Framerate:** Adjust from 0.5 to 60 FPS.
- **Scaling / Resolution:** Set the output resolution as a percentage.
- **Quality:** Adjust output quality settings.
- **GIF palette and dithering:** Use automatic palette generation with dither controls for GIFs.

#### Four Ways to Save

Each save option has its own button.

| Option | Description |
|---|---|
| **Overwrite Existing File** | Replaces the file next to the source video, with a confirmation prompt first. |
| **Save a Numbered Copy** | Saves next to the source video as `name (edited N)` without replacing anything. |
| **Save To…** | Opens a file dialog so you can pick the location and file name. |
| **Copy to Clipboard** | Exports and copies the result to the clipboard. Available for GIF and WebP only. |

### 🧭 Fast Timeline Navigation & Controls

Navigate and edit complex timelines with these controls:

- **Scroll:** Scroll through the timeline.
- **Zoom:** Use `Ctrl + Wheel` to zoom, or two finger zoom while using trackpad.
- **Pan:** Use `Middle-click drag` to pan through the timeline, or drag with two fingers on a trackpad.
- **Frame-by-frame navigation:** Use the arrow keys to move one frame at a time.

### ▶️ Seamless Preview & Undo

### ▶️ Seamless Preview & Undo

- **Automatic codec support:** Generates background proxies for video codecs that Qt cannot natively play.
- **Instant scrubbing:** Generates a low-resolution image sequence of the video at import time, allowing the preview to update quickly as you scrub the timeline without loading screens. Displays low-resolution images while scrubbing for a responsive experience, then switches to the full-resolution frame as soon as you release the mouse.

---

## Interface Layout

The interface is organized into three main panels:

### 1. Video Preview Panel (top left)

- Shows real-time playback.
- Provides interactive crop region controls.

### 2. Interactive Timeline (bottom left)

- Displays all clips sequentially.
- Scrub the top ruler.
- Trim clips using their handles.
- Reorder segments easily.

### 3. Export Panel (right side, from top to bottom)

Fine-tune your export settings before saving:

- **Format**
- **FPS**
- **Resolution scale**
- **Output quality**

Choose how to save using one of the four export buttons: **Overwrite, Numbered Copy, Save To…, or Copy to Clipboard**.

---

## Prerequisites

**FFmpeg** should be installed and available in your `PATH`.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
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

---

## Packaging to Standalone Executable (Windows)

To build a standalone executable on Windows using PyInstaller:

Run the following command:

```cmd
package.bat
```

This compiles the app using `main.py` and includes `icon.ico`.
