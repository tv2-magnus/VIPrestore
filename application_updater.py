import logging
import os
import requests
import subprocess
import tempfile
from PyQt6 import QtWidgets, QtCore
from typing import Optional
from downloads import DownloadWorker
from update_dialog import UpdateDialog
from utils import resource_path, schedule_ui_task
from downloads import DownloadWorker  # Import the centralized DownloadWorker
import strings

logger = logging.getLogger(__name__)

class ApplicationUpdater:
    """Manages application updates from GitHub releases."""
    
    def __init__(self, parent_window, splash_screen=None):
        self.parent = parent_window
        self.splash = splash_screen
        self.repo_owner = "tv2-magnus"
        self.repo_name = "VIPrestore"
        self.current_version = self._get_current_version()
        self.worker = None
        self.thread = None
        self.download_thread = None
        self.download_worker = None
    
    def _get_current_version(self) -> str:
        """Get the current version from constants module."""
        from constants import get_version
        version = get_version()
        logger.debug(f"Current version: {version}")
        return version
    
    def parse_version(self, version_str: str) -> tuple:
        version_str = version_str.lstrip("v")
        parts = version_str.split("-")
        main = parts[0]
        build = parts[1] if len(parts) > 1 else None
        
        main_nums = [int(x) for x in main.split(".")]
        if build and build.isdigit():
            main_nums.append(int(build))
            
        return tuple(main_nums)

    def check_for_update(self) -> Optional[dict]:
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "viprestore-updater"
        }

        logger.debug(f"Checking for update at: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.debug("No releases found (empty JSON).")
                return None

            latest = data[0]
            latest_version = latest.get("tag_name", "").strip()

            if self.parse_version(latest_version) > self.parse_version(self.current_version):
                logger.debug(f"Update available: {latest_version} > {self.current_version}")
                return latest

            logger.debug("No update available.")
            return None
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None

    def fetch_compare_commits(self, base_tag: str, head_tag: str) -> str:
        compare_api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/compare/{base_tag}...{head_tag}"
        logger.debug(f"Fetching compare data from: {compare_api_url}")

        try:
            resp = requests.get(compare_api_url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch compare commits: {e}")
            return "(Could not fetch commit list.)"

        data = resp.json()
        commits = data.get("commits", [])
        if not commits:
            return "No commits found between these versions."

        # Build a bullet-list of commits
        lines = []
        for c in commits:
            sha = c.get("sha", "")
            short_sha = sha[:7] if len(sha) >= 7 else sha
            message = c.get("commit", {}).get("message", "")
            lines.append(f"- <b>{short_sha}</b> {message}")

        result = "<p><b>Commits in this release:</b></p>\n" + "<br>".join(lines)
        return result

    def sanitize_release_body(self, body: str) -> str:
        lines = body.splitlines()
        filtered = []
        for ln in lines:
            if "Full Changelog" in ln:
                continue  # skip that line
            filtered.append(ln)
        return "\n".join(filtered)

    def human_readable_size(self, size_in_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_in_bytes)
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024
            idx += 1
        return f"{size:.2f} {units[idx]}"

    def check_for_updates_async(self):
        """Check for updates asynchronously while handling splash screen properly."""
        # Add this debug line
        logger.debug("Starting update check process")
        
        # Ensure main window shows after minimum splash time
        if self.splash and hasattr(self.splash, 'min_splash_time'):
            logger.debug(f"Scheduling splash screen finish with time: {self.splash.min_splash_time}")
            schedule_ui_task(lambda: self.splash.finish(self.parent), self.splash.min_splash_time)
        else:
            logger.debug("No splash screen or min_splash_time not defined")
        
        # Run the check in a separate thread
        self.thread = QtCore.QThread()
        self.worker = UpdateCheckWorker(self)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.process)
        self.worker.finished.connect(self.on_update_check_complete)
        self.worker.error.connect(self.on_update_check_error)
        
        # Start the thread
        logger.debug("Starting update check thread")
        self.thread.start()
    
    def on_update_check_complete(self, update_info):
        # Clean up thread
        self.thread.quit()
        self.thread.wait()
        
        # Don't close splash directly - finish() was called in check_for_updates_async
        
        if not update_info:
            # No update available, just show the main window if not already visible
            if self.parent and not self.parent.isVisible():
                self.parent.show()
            return
        
        # Show update dialog
        self.show_update_dialog(update_info)
    
    def on_update_check_error(self, error_message):
        logger.error(f"Update check error: {error_message}")
        
        # Clean up thread
        self.thread.quit()
        self.thread.wait()
        
        # Don't close splash directly - finish() was called in check_for_updates_async
        
        # Show main window if not already visible
        if self.parent and not self.parent.isVisible():
            self.parent.show()
    
    def show_update_dialog(self, update_info):
        latest_version = update_info.get("tag_name", "").strip()
        
        # Get release body and clean it
        raw_body = update_info.get("body", "")
        release_body = self.sanitize_release_body(raw_body)
        
        # Build compare tags
        current_tag = self.current_version if self.current_version.startswith("v") else f"v{self.current_version}"
        head_tag = latest_version
        
        # Fetch commits from GitHub compare
        commits_html = self.fetch_compare_commits(current_tag, head_tag)
        
        # Show UpdateDialog
        dlg = UpdateDialog(
            current_version=self.current_version,
            new_version=latest_version,
            commits_html=commits_html
        )
        
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            logger.debug("User accepted. Downloading update...")
            self.download_update(update_info)
        else:
            logger.debug("User declined update.")
            self.parent.show()

    def download_update(self, update_info):
        """
        Download the latest release asset from GitHub with progress tracking.
        
        Args:
            update_info: GitHub release information dictionary
        """
        assets = update_info.get("assets", [])
        if not assets:
            QtWidgets.QMessageBox.critical(
                self.parent, 
                strings.DIALOG_TITLE_ERROR, 
                "No downloadable assets found in the latest release."
            )
            self.parent.show()
            return

        asset = assets[0]
        asset_api_url = asset.get("browser_download_url")
        filename = asset.get("name")

        logger.debug(f"Downloading from: {asset_api_url}")

        headers = {
            "User-Agent": "viprestore-updater"
        }

        # Create a progress dialog
        progress = QtWidgets.QProgressDialog("Initializing download...", "Cancel", 0, 100, self.parent)
        progress.setWindowTitle("Downloading Update")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        # Force the dialog to repaint
        QtWidgets.QApplication.processEvents()

        # Create worker and thread and store as instance variables to prevent garbage collection
        self.download_thread = QtCore.QThread()
        self.download_worker = DownloadWorker(asset_api_url, filename, headers)
        self.download_worker.moveToThread(self.download_thread)

        # Connect signals
        self.download_worker.progressChanged.connect(progress.setValue)
        self.download_worker.statusTextChanged.connect(progress.setLabelText)
        self.download_worker.errorOccurred.connect(
            lambda msg: self.handle_download_error(msg, progress, self.download_thread))
        self.download_worker.finished.connect(
            lambda path: self.handle_download_finished(path, progress, self.download_thread))
        self.download_worker.cancelled.connect(
            lambda: self.handle_download_cancelled(progress, self.download_thread))

        # Connect cancel button to handler
        progress.canceled.connect(lambda: self.handle_progress_cancelled(progress))

        # When the thread starts, call the worker's start_download()
        self.download_thread.started.connect(self.download_worker.start_download)

        # Start the thread
        logger.debug("Starting download thread")
        self.download_thread.start()

    def handle_progress_cancelled(self, progress):
        """Handle when the user clicks the cancel button on the progress dialog."""
        progress.setCancelButtonText("Cancelling...")
        progress.setLabelText("Cancelling download...")
        progress.setCancelButton(None)  # Disable the cancel button
        self.download_worker.cancel_download()

    def handle_download_cancelled(self, progress_dialog, thread):
        """Handle when the download has been successfully cancelled."""
        logger.debug("Download cancellation complete")
        progress_dialog.close()
        thread.quit()
        thread.wait()
        self.parent.show()

    def handle_download_error(self, error_message: str, progress_dialog: QtWidgets.QProgressDialog, thread: QtCore.QThread):
        QtWidgets.QMessageBox.critical(
            self.parent, 
            strings.DIALOG_TITLE_ERROR, 
            f"Download failed: {error_message}"
        )
        progress_dialog.close()
        thread.quit()
        thread.wait()
        self.parent.show()

    def handle_download_finished(self, file_path: str, progress_dialog: QtWidgets.QProgressDialog, thread: QtCore.QThread):
        progress_dialog.setValue(100)
        progress_dialog.close()
        thread.quit()
        thread.wait()

        reply = QtWidgets.QMessageBox.question(
            self.parent,
            "Update Downloaded",
            "Update has been downloaded. Install it now?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("Launching the downloaded update.")
            subprocess.Popen([file_path], shell=True)
            QtWidgets.QApplication.quit()
            import sys
            sys.exit(0)
        else:
            # If user chooses not to install now, show the main window
            self.parent.show()


class UpdateCheckWorker(QtCore.QObject):
    """Worker for checking updates in a background thread."""
    
    finished = QtCore.pyqtSignal(object)  # Signal emits update_info or None
    error = QtCore.pyqtSignal(str)  # Signal emits error message
    
    def __init__(self, updater):
        super().__init__()
        self.updater = updater
    
    @QtCore.pyqtSlot()
    def process(self):
        """Check for updates and emit result."""
        logger.debug("UpdateCheckWorker process started")
        try:
            update_info = self.updater.check_for_update()
            logger.debug(f"Update check completed: {update_info is not None}")
            self.finished.emit(update_info)
        except Exception as e:
            logger.error(f"Error in update check worker: {e}")
            self.error.emit(str(e))