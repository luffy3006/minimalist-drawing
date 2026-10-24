# Minimalist Drawing

<div align="center">

<img src="packaging/minimalist-drawing.svg" width="128" height="128" alt="Minimalist Drawing Logo" />

### High-performance, distraction-free infinite drawing & whiteboard application for Linux

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux-orange.svg)](#installation)
[![Arch Linux](https://img.shields.io/badge/Arch_Linux-pkg.tar.zst-1793d1.svg?logo=arch-linux)](#arch-linux-manjaro-cachyos)
[![Debian / Ubuntu](https://img.shields.io/badge/Debian_%2F_Ubuntu-.deb-a81d33.svg?logo=debian)](#debian--ubuntu--mint--pop_os)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg?logo=python)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg?logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)

[Download Executables](#quick-start--download) • [Features](#key-features) • [Shortcuts](#keyboard-shortcuts) • [Installation](#installation) • [Build Guide](#building-packages)

</div>

---

## Overview

**Minimalist Drawing** is a fast, elegant, distraction-free infinite canvas scratchpad built with PyQt6. Designed for problem solving, competitive programming, math scratch work, system design brainstorming, and daily note-taking on Linux.

Featuring smooth quadratic Bezier curve interpolation, instant one-click screen clearing with full undo/redo safety, real-time geometric shape recognition, and spatial QuadTree viewport acceleration.

---

## Key Features

- 🧹 **Instant Clear Screen**: One-click screen clear button right in the floating palette and left toolbar, fully undoable at any time with <kbd>Ctrl</kbd> + <kbd>Z</kbd>.
- ✍️ **Quad-Bezier Smoothing**: Anti-aliased freehand pen and highlighter strokes with real-time Bezier interpolation and pressure sensitivity.
- ⚡ **Spatial QuadTree Acceleration**: Efficient 2D spatial indexing for instant rendering, smooth viewport culling, and lightning-fast hit testing even with thousands of strokes.
- 📐 **Geometric Shape Auto-Correction**: Automatically detects and snaps rough hand-drawn strokes into clean geometric primitives:
  - **Lines**: Straight segments snapped by chord deviation.
  - **Circles & Ellipses**: Snapped based on radial variance.
  - **Rectangles**: Snapped to clean axis-aligned boxes.
  - **Triangles**: Polygon simplified through Ramer-Douglas-Peucker classification.
- 🌗 **Adaptive Themes**: Instant Light (`#FFFFFF`) and Dark (`#121212`) mode switching with intelligent semantic ink inversion (default ink stays readable across themes, explicit colors remain locked).
- 🧲 **Lasso Selection & Transformation**: Select strokes and images, drag to reposition, resize with bounding handles, duplicate, copy, and paste (<kbd>Ctrl</kbd>+<kbd>C</kbd>, <kbd>Ctrl</kbd>+<kbd>V</kbd>).
- ⌨️ **On-Canvas Typing**: Double-click anywhere to place a frameless text input directly onto the canvas.
- 💾 **Lossless Export**: Export the canvas to PNG (<kbd>Ctrl</kbd> + <kbd>S</kbd>) or drag & drop / open reference images (<kbd>Ctrl</kbd> + <kbd>O</kbd>).
- 🖱️ **Infinite Pan & Zoom**: Pan smoothly using <kbd>Space</kbd> + drag or middle mouse button, zoom anchored at the cursor position with mouse wheel.

---

## Quick Start / Download

Download pre-compiled binaries and packages directly from the [Releases](https://github.com/luffy3006/minimalist-drawing/releases) page:

| Package Format | Target Distribution | Download Link |
| :--- | :--- | :--- |
| **Standalone Binary** | Any Linux (x86_64) | [`minimalist-drawing`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing) |
| **Arch Package** | Arch Linux / CachyOS / Manjaro | [`minimalist-drawing-1.0.0-1-any.pkg.tar.zst`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing-1.0.0-1-any.pkg.tar.zst) |
| **Debian Package** | Debian / Ubuntu / Linux Mint | [`minimalist-drawing_1.0.0_all.deb`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing_1.0.0_all.deb) |

---

## Installation

### 1. Standalone Executable (Universal Linux)

No dependencies, package managers, or Python installation needed:

```bash
# Download binary
curl -LO https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing

# Make executable
chmod +x minimalist-drawing

# Run
./minimalist-drawing
```

*(Optional) Install system-wide:*
```bash
sudo mv minimalist-drawing /usr/local/bin/
```

---

### 2. Arch Linux / Manjaro / CachyOS

#### Option A: Using the `.pkg.tar.zst` package
```bash
# Download and install
sudo pacman -U minimalist-drawing-1.0.0-1-any.pkg.tar.zst
```

#### Option B: Using the `PKGBUILD`
```bash
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing/packaging
makepkg -si
```

---

### 3. Debian / Ubuntu / Mint / Pop!_OS

Install the `.deb` package using `apt` (recommended, handles dependencies automatically):

```bash
# Install with apt
sudo apt install ./minimalist-drawing_1.0.0_all.deb
```

Or using `dpkg`:
```bash
sudo dpkg -i minimalist-drawing_1.0.0_all.deb
sudo apt-get install -f
```

---

### 4. Install via pip / Python

```bash
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing
pip install .

# Launch application
minimalist-drawing
```

---

### 5. Run from Source

```bash
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing
pip install -r requirements.txt
python3 main.py
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>C</kbd> | **Clear Canvas / Screen** (also available via toolbar button) |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> | **Undo** (restores cleared canvas or stroke) |
| <kbd>Ctrl</kbd> + <kbd>Y</kbd> / <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd> | **Redo** |
| <kbd>P</kbd> | Pen Tool |
| <kbd>H</kbd> | Highlighter Tool |
| <kbd>E</kbd> | Eraser Tool |
| <kbd>L</kbd> | Lasso Selection Tool |
| <kbd>[</kbd> / <kbd>]</kbd> | Decrease / Increase Stroke Width |
| <kbd>D</kbd> | Toggle Dark / Light Mode |
| <kbd>Ctrl</kbd> + <kbd>S</kbd> | Save Canvas as Lossless PNG |
| <kbd>Ctrl</kbd> + <kbd>O</kbd> | Open / Insert Image |
| <kbd>Ctrl</kbd> + <kbd>C</kbd> | Copy Selected Items |
| <kbd>Ctrl</kbd> + <kbd>V</kbd> | Paste Selected Items |
| <kbd>Delete</kbd> / <kbd>Backspace</kbd> | Delete Selected Items |
| <kbd>Space</kbd> + Click & Drag | Pan Canvas |
| Mouse Wheel | Zoom In / Out at Cursor Position |
| Double-Click | Open Frameless Text Input |
| <kbd>Enter</kbd> | Commit Text to Canvas |
| <kbd>Esc</kbd> | Cancel Text Input / Deselect |

---

## Building Packages

The repository includes a unified build script that outputs the standalone binary, the Arch Linux package, and the Debian package:

```bash
# Build all packages into dist/
python3 build_packages.py
```

Outputs in `dist/`:
- `dist/minimalist-drawing` (Standalone binary executable)
- `dist/minimalist-drawing-1.0.0-1-any.pkg.tar.zst` (Arch Linux package)
- `dist/minimalist-drawing_1.0.0_all.deb` (Debian package)

### Running Tests

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests
```

---

## Project Structure

```
minimalist-drawing/
├── .github/workflows/          # CI/CD automated build and release workflows
│   └── release.yml
├── packaging/                  # Linux system packaging assets
│   ├── minimalist-drawing.desktop
│   ├── minimalist-drawing.svg
│   ├── minimalist-drawing.png
│   ├── io.github.luffy3006.minimalist_drawing.metainfo.xml
│   └── PKGBUILD
├── src/minimalist_drawing/     # Core package source
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── autocorrect.py
│   └── assets/
├── tests/                      # Automated test suite
│   ├── __init__.py
│   └── test_drawing.py
├── build_packages.py           # Automated multi-format package builder
├── main.py                     # Root direct runner
├── autocorrect.py              # Root direct helper
├── pyproject.toml              # Modern Python packaging configuration
├── setup.py                    # Legacy build support
├── requirements.txt            # Python dependencies
├── LICENSE                     # MIT License
└── README.md                   # Documentation
```

---

## License

This project is licensed under the [MIT License](LICENSE).
