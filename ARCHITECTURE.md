# Architecture

GiffyPy is a screen recorder and video editor built on PySide6 for the UI and
an out-of-process `ffmpeg`/`ffprobe` for all media work. The app never re-encodes
while you edit; edits stay as lightweight metadata until export.

## Program flow

The app moves through four stages, all driven from the main window:

1. **Open** — a file path (dialog, drag-and-drop, or a fresh screen recording)
   is probed with `ffprobe` off the GUI thread to get size, duration, and frame
   rate.
2. **Preview** — a low-resolution JPEG sequence is generated in the background
   so scrubbing the timeline shows a frame instantly, while the real video plays
   through Qt's media player.
3. **Edit** — trims, splits, reordering, per-clip speed, and cropping mutate an
   in-memory clip list. Nothing touches the source file.
4. **Export** — the clip list plus crop/scale/fps/quality choices are turned
   into an `ffmpeg` filtergraph and run as a separate process that writes the
   final animated image or video.

## Layering

Code is split by whether it depends on Qt widgets or the app's live state:

- `giffypy/ui/` holds widgets and painting — timeline, crop overlay and preview
  view, toolbar, export panel, theme. These know how to look and react to input.
- `giffypy/core/` holds media probing, preview generation, editing logic, export
  command building, screen recording, and session reset. Pure helpers here (the
  ffmpeg argument builder, path numbering, `ffprobe` parsing) carry no UI import.
- `giffypy/window.py` is the single orchestrator: it owns the window state and
  wires UI widgets to the core controllers. No other module reaches across this
  boundary.
- `giffypy/core/constants.py` is the shared leaf — binary paths, tuning
  constants, format lists — that everything may depend on and that depends on
  nothing.

The dependency graph stays acyclic:
`main.py` → `window.py` → `{core/*, ui/*}` → `core/constants.py`.

## Non-destructive editing model

The entire edit is a list of segments, each a `(start, end, speed)` triple in
source-time. The timeline widget owns and displays this list; editing operations
in the editor controller only reshape it. Undo works by snapshotting the list
(`deepcopy`) before each change. Coordinate translation between edit-time
(where the playhead sits on the timeline) and source-time (the frame to show or
trim) happens wherever a segment is rendered or seeked. Export reads the same
list to build its filtergraph, so what you scrub is exactly what ships.

## Live preview strategy

Two layers sit in the preview scene: the real video item (used during playback)
and a proxy pixmap drawn on top while scrubbing. The proxy manager decodes a
downscaled JPEG sequence at preview frame rate in a temp directory, so dragging
the playhead is a single file read rather than a video seek. When the media
player delivers a freshly decoded frame, the proxy layer steps aside.

## Process & threading model

The GUI runs on a single Qt thread. Everything heavy is pushed off it: media
probing and recording finalization use short-lived worker threads that report
back through Qt signals, while preview generation and export run as `QProcess`
instances that write their output to a temporary file first and swap it into
place on success. Shutdown paths stop any active recording and clean up temp
artifacts so no orphaned `ffmpeg` or leftover files remain.

## Look here for

- Startup, resource paths: `main.py`
- Window wiring, state, load lifecycle, close/cleanup: `giffypy/window.py`
- `ffprobe`/`ffmpeg` discovery and tuning constants: `giffypy/core/constants.py`
- Media probing: `giffypy/core/media.py`
- Async file loading: `giffypy/core/loader.py`
- Proxy sequence and scrub preview: `giffypy/core/preview.py`
- Playback, split, delete, undo, speed, crop toggle: `giffypy/core/editor.py`
- ffmpeg argument building and numbered export paths (pure): `giffypy/core/export.py`
- Export run, progress, output swap: `giffypy/core/exporter.py`
- Desktop capture start/stop/discard: `giffypy/core/screen_recorder.py`
- Session reset back to the placeholder: `giffypy/core/session.py`
- Timeline widget (segments, gestures, zoom): `giffypy/ui/timeline.py`
- Crop overlay and pannable/zoomable preview view: `giffypy/ui/crop.py`
- Toolbar construction and state: `giffypy/ui/toolbar.py`
- Export panel widgets: `giffypy/ui/export_panel.py`
- Global stylesheet/palette: `giffypy/ui/theme.py`
