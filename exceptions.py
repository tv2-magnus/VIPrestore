"""
exceptions.py - Exception handling infrastructure for VIPrestore
"""

import sys
import traceback
import logging
from typing import Optional, Callable
from PyQt6 import QtWidgets, QtCore
import strings

logger = logging.getLogger(__name__)

class ExceptionHandler:
    """
    Centralized exception handling for the application.
    Provides consistent error reporting and recovery strategies.
    """
    
    def __init__(self):
        """Initialize the exception handler."""
        self.app = None
        self.main_window = None
        
    def set_application(self, app, main_window=None):
        """
        Set the application and main window references.
        
        Args:
            app: QApplication instance
            main_window: Optional MainWindow instance
        """
        self.app = app
        self.main_window = main_window
    
    def install_global_handler(self):
        """Install as global exception handler for unhandled exceptions."""
        sys.excepthook = self.global_exception_handler
    
    def global_exception_handler(self, exc_type, exc_value, exc_traceback):
        """
        Global handler for unhandled exceptions.
        Logs the error and shows a dialog to the user.
        
        Args:
            exc_type: Exception type
            exc_value: Exception value
            exc_traceback: Exception traceback
        """
        # Log the full exception
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Format error message for user
        error_msg = f"{exc_type.__name__}: {exc_value}"
        
        # Show dialog on the main thread
        if self.app and self.app.thread() == QtCore.QThread.currentThread():
            # We're on the main thread, show dialog directly
            self.show_exception_dialog(error_msg)
        else:
            # We're on a background thread, schedule dialog on main thread
            QtCore.QMetaObject.invokeMethod(
                self, 
                "show_exception_dialog",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, error_msg)
            )
    
    @QtCore.pyqtSlot(str)
    def show_exception_dialog(self, error_msg):
        """
        Show exception dialog to the user.
        
        Args:
            error_msg: Error message to display
        """
        parent = self.main_window if self.main_window else None
        QtWidgets.QMessageBox.critical(
            parent,
            strings.DIALOG_TITLE_ERROR,
            f"An unexpected error occurred:\n\n{error_msg}\n\n"
            f"This error has been logged. Please restart the application."
        )
    
    def handle_api_error(self, error, context="operation", parent=None):
        """
        Handle API-related errors with appropriate user feedback.
        
        Args:
            error: The exception that occurred
            context: Context description for error message
            parent: Parent widget for dialog
            
        Returns:
            bool: True if handled, False if re-raised
        """
        from vipclient import VideoIPathClientError
        from service_manager import ServiceManagerError
        
        # Default to main window if no parent specified
        if parent is None and self.main_window:
            parent = self.main_window
        
        # Log the error
        logger.error(f"API error during {context}: {error}", exc_info=True)
        
        # Handle different error types
        if isinstance(error, VideoIPathClientError):
            QtWidgets.QMessageBox.critical(
                parent,
                strings.DIALOG_TITLE_ERROR,
                f"Connection error: {error}"
            )
            return True
            
        elif isinstance(error, ServiceManagerError):
            QtWidgets.QMessageBox.critical(
                parent,
                strings.DIALOG_TITLE_ERROR,
                f"Service operation failed: {error}"
            )
            return True
            
        elif isinstance(error, requests.exceptions.RequestException):
            QtWidgets.QMessageBox.critical(
                parent,
                strings.DIALOG_TITLE_ERROR,
                f"Network request failed: {error}"
            )
            return True
            
        else:
            # Unhandled exception type, log and re-raise
            logger.error(
                f"Unhandled exception in {context}", 
                exc_info=True
            )
            return False
    
    def confirm_destructive_action(
        self, 
        message: str, 
        title: str = strings.DIALOG_TITLE_CONFIRM,
        parent=None
    ) -> bool:
        """
        Show confirmation dialog for destructive actions.
        
        Args:
            message: Confirmation message to display
            title: Dialog title
            parent: Parent widget for dialog
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        if parent is None and self.main_window:
            parent = self.main_window
            
        reply = QtWidgets.QMessageBox.question(
            parent,
            title,
            message,
            QtWidgets.QMessageBox.StandardButton.Yes | 
            QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No  # Default is No (safer)
        )
        return reply == QtWidgets.QMessageBox.StandardButton.Yes


# Create a singleton instance
exception_handler = ExceptionHandler()