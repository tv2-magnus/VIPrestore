"""
downloads.py - Centralized download management for VIPrestore
"""

import os
import tempfile
import logging
import requests
from PyQt6 import QtCore
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DownloadWorker(QtCore.QObject):
    """Worker object that handles file downloads in a separate thread."""
    
    # Signals
    cancelled = QtCore.pyqtSignal()
    progressChanged = QtCore.pyqtSignal(int)  # Percent complete
    statusTextChanged = QtCore.pyqtSignal(str)  # Status text
    finished = QtCore.pyqtSignal(str)  # File path on success
    errorOccurred = QtCore.pyqtSignal(str)  # Error message
    
    def __init__(self, download_url: str, filename: str, headers: Dict[str, str] = None, parent=None):
        """
        Initialize the download worker.
        
        Args:
            download_url: URL to download from
            filename: Name for the downloaded file
            headers: Optional headers for the request
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.download_url = download_url
        self.filename = filename
        self.headers = headers or {}
        self._cancelled = False
        self._temp_dir = None
        self._file_path = None
        
    def get_file_path(self) -> str:
        """
        Get the full path where the file will be downloaded.
        Creates the temp directory if needed.
        
        Returns:
            str: Full path to the download target
        """
        if self._file_path is None:
            self._temp_dir = tempfile.gettempdir()
            self._file_path = os.path.join(self._temp_dir, self.filename)
        return self._file_path
    
    @staticmethod
    def human_readable_size(size_in_bytes: int) -> str:
        """
        Convert bytes to a human-readable string.
        
        Args:
            size_in_bytes: Size in bytes
            
        Returns:
            str: Human readable size (e.g., "4.2 MB")
        """
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_in_bytes)
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024
            idx += 1
        return f"{size:.2f} {units[idx]}"
    
    @QtCore.pyqtSlot()
    def start_download(self):
        """Perform the actual download in chunks and emit progress signals."""
        try:
            file_path = self.get_file_path()
            logger.debug(f"Starting download to: {file_path}")
            
            response = requests.get(
                self.download_url, 
                stream=True, 
                headers=self.headers, 
                timeout=30
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            
            # Emit initial progress
            if total_size > 0:
                self.statusTextChanged.emit(
                    f"Downloading... {self.human_readable_size(0)} of "
                    f"{self.human_readable_size(total_size)}"
                )
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self._cancelled:
                        logger.debug("Download cancelled")
                        f.close()
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        self.cancelled.emit()
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            percent = int((downloaded_size / total_size) * 100)
                            self.progressChanged.emit(percent)
                            
                            # Update status every 5% for large files
                            if percent % 5 == 0 or percent >= 100:
                                self.statusTextChanged.emit(
                                    f"Downloading... {self.human_readable_size(downloaded_size)} of "
                                    f"{self.human_readable_size(total_size)}"
                                )
            
            logger.debug(f"Download completed: {file_path}")
            self.progressChanged.emit(100)
            self.finished.emit(file_path)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Download request error: {e}")
            error_msg = f"Download failed: {str(e)}"
            self.errorOccurred.emit(error_msg)
            
        except Exception as e:
            logger.error(f"Unexpected download error: {e}", exc_info=True)
            error_msg = f"Unexpected error: {str(e)}"
            self.errorOccurred.emit(error_msg)
    
    def cancel_download(self):
        """Cancel the current download operation."""
        logger.debug("Cancelling download...")
        self._cancelled = True