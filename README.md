# Minimalist Drawing

<div align="center">

<img src="packaging/minimalist-drawing.svg" width="128" height="128" alt="Minimalist Drawing Logo" />

### High-performance, distraction-free infinite drawing and scratchpad application for Linux and Windows

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)](#installation)
[![Windows](https://img.shields.io/badge/Windows-exe%20%7C%20zip-0078d4.svg?logo=windows)](#windows-10--11)
[![Arch Linux](https://img.shields.io/badge/Arch_Linux-pkg.tar.zst-1793d1.svg?logo=arch-linux)](#arch-linux-manjaro-cachyos)
[![Debian / Ubuntu](https://img.shields.io/badge/Debian_%2F_Ubuntu-.deb-a81d33.svg?logo=debian)](#debian--ubuntu--mint--pop_os)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg?logo=python)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg?logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)

[Download Executables](#quick-start--download) • [Features](#key-features) • [Shortcuts](#keyboard-shortcuts) • [Installation](#installation) • [Build Guide](#building-packages)

</div>

---

## Overview

**Minimalist Drawing** is a fast, elegant, distraction-free infinite canvas scratchpad built with PyQt6. Designed for problem solving, competitive programming, math scratch work, system design brainstorming, and daily note-taking across Linux and Windows.

Featuring smooth quadratic Bezier curve interpolation, instant one-click screen clearing with full undo/redo safety, real-time geometric shape recognition, and spatial QuadTree viewport acceleration.

---

## Key Features

- **Instant Clear Screen**: One-click screen clear button located directly on the floating palette and left toolbar, fully undoable at any time with <kbd>Ctrl</kbd> + <kbd>Z</kbd>.
- **Quad-Bezier Smoothing**: Anti-aliased freehand pen and highlighter strokes with real-time Bezier interpolation and pressure sensitivity.
- **Spatial QuadTree Acceleration**: Efficient 2D spatial indexing for instant rendering, smooth viewport culling, and responsive hit testing even with thousands of strokes.
- **Geometric Shape Auto-Correction**: Automatically detects and snaps rough hand-drawn strokes into clean geometric primitives:
  - **Lines**: Straight segments snapped by chord deviation.
  - **Circles and Ellipses**: Snapped based on radial variance.
  - **Rectangles**: Snapped to clean axis-aligned bounding boxes.
  - **Triangles**: Polygon simplified through Ramer-Douglas-Peucker classification.
- **Adaptive Themes**: Instant Light (`#FFFFFF`) and Dark (`#121212`) mode switching with intelligent semantic ink inversion (default ink stays readable across themes, explicit colors remain locked).
- **Lasso Selection and Transformation**: Select strokes and images, drag to reposition, resize with bounding handles, duplicate, copy, and paste (<kbd>Ctrl</kbd>+<kbd>C</kbd>, <kbd>Ctrl</kbd>+<kbd>V</kbd>).
- **On-Canvas Typing**: Double-click anywhere to place a frameless text input directly onto the canvas.
- **Lossless Export**: Export the canvas to PNG (<kbd>Ctrl</kbd> + <kbd>S</kbd>) or drag & drop / open reference images (<kbd>Ctrl</kbd> + <kbd>O</kbd>).
- **Infinite Pan and Zoom**: Pan smoothly using <kbd>Space</kbd> + drag or middle mouse button, zoom anchored at the cursor position with the mouse wheel.
- **Cross-Platform**: First-class support for both Linux (standalone binary, Arch package, Debian package) and Windows (standalone `.exe` and portable zip).

---

## Quick Start / Download

Download pre-compiled binaries and packages directly from the [Releases](https://github.com/luffy3006/minimalist-drawing/releases) page:

| Platform / Package | Target System | Download Link |
| :--- | :--- | :--- |
| **Windows Executable** | Windows 10 / 11 (x64) | [`minimalist-drawing.exe`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing.exe) |
| **Windows Portable ZIP** | Windows 10 / 11 (x64) | [`minimalist-drawing-windows-x64.zip`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing-windows-x64.zip) |
| **Linux Standalone Binary** | Any Linux (x86_64) | [`minimalist-drawing`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing) |
| **Arch Linux Package** | Arch Linux / CachyOS / Manjaro | [`minimalist-drawing-1.0.0-1-any.pkg.tar.zst`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing-1.0.0-1-any.pkg.tar.zst) |
| **Debian / Ubuntu Package** | Debian / Ubuntu / Linux Mint | [`minimalist-drawing_1.0.0_all.deb`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing_1.0.0_all.deb) |

---

## Installation

### Windows (10 / 11)

#### Option A: Standalone Executable
1. Download [`minimalist-drawing.exe`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing.exe).
2. Double-click to run. No installation or external dependencies required.

#### Option B: Portable ZIP
1. Download [`minimalist-drawing-windows-x64.zip`](https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing-windows-x64.zip).
2. Extract the archive and launch `minimalist-drawing.exe`.

#### Option C: Run with Python on Windows
```bat
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing
packaging\run_windows.bat
```

---

### Linux (Universal Standalone Binary)

No dependencies, package managers, or Python installation needed:

```bash
# Download binary
curl -LO https://github.com/luffy3006/minimalist-drawing/releases/latest/download/minimalist-drawing

# Make executable
chmod +x minimalist-drawing

# Run
./minimalist-drawing
```

Optional: Install system-wide:
```bash
sudo mv minimalist-drawing /usr/local/bin/
```

---

### Arch Linux / Manjaro / CachyOS

#### Option A: Using the pre-built `.pkg.tar.zst` package
```bash
sudo pacman -U minimalist-drawing-1.0.0-1-any.pkg.tar.zst
```

#### Option B: Using the PKGBUILD
```bash
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing/packaging
makepkg -si
```

---

### Debian / Ubuntu / Mint / Pop!_OS

Install the `.deb` package using `apt` (recommended, resolves dependencies automatically):

```bash
sudo apt install ./minimalist-drawing_1.0.0_all.deb
```

Or using `dpkg`:
```bash
sudo dpkg -i minimalist-drawing_1.0.0_all.deb
sudo apt-get install -f
```

---

### Install via pip / Python

```bash
git clone https://github.com/luffy3006/minimalist-drawing.git
cd minimalist-drawing
pip install .

# Launch application
minimalist-drawing
```

---

### Run from Source

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

### Linux Packages
The repository includes a unified build script that outputs the standalone binary, the Arch Linux package, and the Debian package:

```bash
python3 build_packages.py
```

Outputs in `dist/`:
- `dist/minimalist-drawing` (Standalone binary executable)
- `dist/minimalist-drawing-1.0.0-1-any.pkg.tar.zst` (Arch Linux package)
- `dist/minimalist-drawing_1.0.0_all.deb` (Debian package)

### Windows Executable
To build the Windows `.exe` locally on Windows:

```powershell
pip install -r requirements.txt pyinstaller pillow
pyinstaller --onefile --windowed --name minimalist-drawing --icon packaging/minimalist-drawing.ico --add-data "packaging/minimalist-drawing.ico;packaging" --add-data "packaging/minimalist-drawing.png;packaging" --add-data "autocorrect.py;." main.py
```

### Running Tests

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover tests
```

---

## Project Structure

```
minimalist-drawing/
├── .github/workflows/          # CI/CD automated build and release workflows (Linux & Windows)
│   └── release.yml
├── packaging/                  # Linux & Windows system packaging assets
│   ├── minimalist-drawing.desktop
│   ├── minimalist-drawing.svg
│   ├── minimalist-drawing.png
│   ├── minimalist-drawing.ico
│   ├── run_windows.bat
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
├── build_packages.py           # Automated multi-format Linux package builder
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
