"""
Update Checker and Dialog for Minimalist Drawing.
Provides:
  - Background asynchronous update checking (silent unless an update is found)
  - Manual update check triggered from UI button
  - Non-intrusive UpdateDialog with 'Update Now' and 'Remind Me Later' options
  - OS-aware asset detection for Linux and Windows
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QFont, QColor

APP_VERSION = "1.0.0"
GITHUB_REPO = "luffy3006/minimalist-drawing"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

REMIND_LATER_INTERVAL_SECONDS = 86400  # 24 hours


def parse_version(v_str: str) -> tuple[int, ...]:
    """Parse a semantic version string from tag or name (e.g. 'v1.2.3' -> (1, 2, 3))."""
    if not v_str:
        return (0, 0, 0)
    import re
    match = re.search(r'(\d+)(?:\.(\d+))?(?:\.(\d+))?', v_str)
    if match:
        major = int(match.group(1)) if match.group(1) else 0
        minor = int(match.group(2)) if match.group(2) else 0
        patch = int(match.group(3)) if match.group(3) else 0
        return (major, minor, patch)
    return (0, 0, 0)


@dataclass
class UpdateInfo:
    has_update: bool
    current_version: str
    latest_version: str
    release_name: str
    release_notes: str
    release_url: str
    download_url: str | None = None
    error: str | None = None


def select_best_asset(assets: list[dict], release_url: str) -> str:
    """Select the most relevant download asset based on the current operating system."""
    if not assets:
        return release_url

    is_windows = sys.platform == "win32"
    is_linux = sys.platform.startswith("linux")

    # Windows preference: .exe or .zip
    if is_windows:
        for a in assets:
            name = a.get("name", "").lower()
            if name.endswith(".exe"):
                return a.get("browser_download_url", release_url)
        for a in assets:
            name = a.get("name", "").lower()
            if "windows" in name and name.endswith(".zip"):
                return a.get("browser_download_url", release_url)

    # Linux preference: distro package or standalone binary
    if is_linux:
        # Check if Arch or Debian-based
        is_arch = os.path.exists("/etc/arch-release") or os.path.exists("/usr/bin/pacman")
        is_debian = os.path.exists("/etc/debian_version") or os.path.exists("/usr/bin/dpkg")

        if is_arch:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".pkg.tar.zst"):
                    return a.get("browser_download_url", release_url)

        if is_debian:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".deb"):
                    return a.get("browser_download_url", release_url)

        # Standalone binary
        for a in assets:
            name = a.get("name", "")
            if name == "minimalist-drawing":
                return a.get("browser_download_url", release_url)

    return release_url


def fetch_latest_release(current_ver: str = APP_VERSION, repo: str = GITHUB_REPO) -> UpdateInfo:
    """Synchronously queries the GitHub Releases API for the latest version."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"MinimalistDrawing/{current_ver}",
            "Accept": "application/vnd.github.v3+json",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag_name = data.get("tag_name", "").strip()
        release_name = data.get("name", tag_name) or tag_name
        release_notes = data.get("body", "") or "No release notes provided."
        release_url = data.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag_name}"
        assets = data.get("assets", [])
        download_url = select_best_asset(assets, release_url)

        current_tuple = parse_version(current_ver)
        latest_tuple = parse_version(tag_name)
        if latest_tuple == (0, 0, 0) and release_name:
            latest_tuple = parse_version(release_name)

        has_update = latest_tuple > current_tuple

        return UpdateInfo(
            has_update=has_update,
            current_version=current_ver,
            latest_version=tag_name,
            release_name=release_name,
            release_notes=release_notes,
            release_url=release_url,
            download_url=download_url,
        )
    except urllib.error.HTTPError as e:
        return UpdateInfo(
            has_update=False,
            current_version=current_ver,
            latest_version=current_ver,
            release_name="",
            release_notes="",
            release_url=GITHUB_RELEASES_URL,
            error=f"GitHub API HTTP {e.code}: {e.reason}",
        )
    except Exception as e:
        return UpdateInfo(
            has_update=False,
            current_version=current_ver,
            latest_version=current_ver,
            release_name="",
            release_notes="",
            release_url=GITHUB_RELEASES_URL,
            error=str(e),
        )


class UpdateWorker(QThread):
    """Background worker thread for checking updates without freezing the GUI."""
    finished_check = pyqtSignal(object)  # Emits UpdateInfo

    def __init__(self, current_ver: str = APP_VERSION, repo: str = GITHUB_REPO, is_manual: bool = False):
        super().__init__()
        self.current_ver = current_ver
        self.repo = repo
        self.is_manual = is_manual

    def run(self):
        info = fetch_latest_release(self.current_ver, self.repo)
        self.finished_check.emit(info)


def should_notify_background(info: UpdateInfo) -> bool:
    """Determine whether to alert the user about an update during automatic background check."""
    if not info.has_update or info.error:
        return False

    settings = QSettings("MinimalistDrawing", "Updater")
    remind_later_time = settings.value("remind_later_time", 0.0, type=float)
    skipped_version = settings.value("skipped_version", "", type=str)

    if skipped_version == info.latest_version:
        return False

    now = time.time()
    if now - remind_later_time < REMIND_LATER_INTERVAL_SECONDS:
        return False

    return True


def record_remind_later():
    """Stores the timestamp when the user chooses 'Remind Me Later'."""
    settings = QSettings("MinimalistDrawing", "Updater")
    settings.setValue("remind_later_time", time.time())


def record_skip_version(version: str):
    """Stores a version that the user has explicitly chosen to skip."""
    settings = QSettings("MinimalistDrawing", "Updater")
    settings.setValue("skipped_version", version)


class UpdateDialog(QDialog):
    """Polished, minimalist dialog notifying user of an available software update."""
    def __init__(self, info: UpdateInfo, parent=None, is_manual: bool = False):
        super().__init__(parent)
        self.info = info
        self.is_manual = is_manual

        self.setWindowTitle("Software Update Available - Minimalist Drawing")
        self.setFixedSize(520, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #27272a;
            }
            QLabel {
                color: #e4e4e7;
            }
            QLabel#headerTitle {
                font-size: 17px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#badgeCurrent {
                background-color: #27272a;
                color: #a1a1aa;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#badgeNew {
                background-color: #1e3a5f;
                color: #60a5fa;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QTextBrowser {
                background-color: #121215;
                color: #d4d4d8;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 10px;
                font-size: 12.5px;
            }
            QPushButton {
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
                background-color: #27272a;
                color: #f4f4f5;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton#primaryBtn {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
                color: #ffffff;
            }
            QPushButton#primaryBtn:hover {
                background-color: #1d4ed8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        # Header section
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(4)

        title_lbl = QLabel("A new version of Minimalist Drawing is available!", self)
        title_lbl.setObjectName("headerTitle")
        header_text_layout.addWidget(title_lbl)

        sub_lbl = QLabel(f"Release: {info.release_name or info.latest_version}", self)
        sub_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        header_text_layout.addWidget(sub_lbl)

        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Version Pill Badges
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(8)

        lbl_curr = QLabel(f"Current: v{info.current_version.lstrip('v')}", self)
        lbl_curr.setObjectName("badgeCurrent")
        badges_layout.addWidget(lbl_curr)

        arrow_lbl = QLabel("→", self)
        arrow_lbl.setStyleSheet("color: #71717a; font-size: 14px; font-weight: bold;")
        badges_layout.addWidget(arrow_lbl)

        lbl_new = QLabel(f"New: {info.latest_version}", self)
        lbl_new.setObjectName("badgeNew")
        badges_layout.addWidget(lbl_new)

        badges_layout.addStretch()
        layout.addLayout(badges_layout)

        # Release Notes / Description
        notes_label = QLabel("Release Notes:", self)
        notes_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #a1a1aa;")
        layout.addWidget(notes_label)

        self.notes_browser = QTextBrowser(self)
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setMarkdown(info.release_notes or "No details provided.")
        layout.addWidget(self.notes_browser)

        # Button actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_remind_later = QPushButton("Remind Me Later", self)
        self.btn_remind_later.setToolTip("Postpone notifications for 24 hours")
        self.btn_remind_later.clicked.connect(self._on_remind_later)
        btn_layout.addWidget(self.btn_remind_later)

        btn_layout.addStretch()

        self.btn_update_now = QPushButton("Update Now", self)
        self.btn_update_now.setObjectName("primaryBtn")
        self.btn_update_now.setToolTip("Open the release download page")
        self.btn_update_now.clicked.connect(self._on_update_now)
        btn_layout.addWidget(self.btn_update_now)

        layout.addLayout(btn_layout)

    def _on_update_now(self):
        target_url = self.info.download_url or self.info.release_url
        QDesktopServices.openUrl(QUrl(target_url))
        self.accept()

    def _on_remind_later(self):
        record_remind_later()
        self.reject()
