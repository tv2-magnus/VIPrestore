import os
import sys
import logging
from PyQt6 import QtCore

logger = logging.getLogger(__name__)

def resource_path(relative_path):
    """Return the absolute path to a resource, works in dev and PyInstaller."""
    try:
        # PyInstaller stores temp path in _MEIPASS.
        base_path = sys._MEIPASS
    except AttributeError:
        # In dev, use the directory of this file.
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class UITaskScheduler(QtCore.QObject):
    """
    Scheduler for UI tasks that handles deferred execution properly.
    Replaces the QTimer.singleShot(0,...) anti-pattern with a more maintainable approach.
    """
    
    def __init__(self, parent=None):
        """Initialize the task scheduler."""
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute_next)
        self._queue = []
        self._executing = False
    
    def schedule(self, callback, delay_ms=0):
        """
        Schedule a callback to be executed after the specified delay.
        
        Args:
            callback: Function to call
            delay_ms: Delay in milliseconds, 0 for next event loop iteration
        """
        self._queue.append(callback)
        
        # Start timer if not already running
        if not self._timer.isActive() and not self._executing:
            self._timer.start(delay_ms)
    
    def _execute_next(self):
        """Execute the next scheduled task."""
        if not self._queue:
            return
            
        self._executing = True
        try:
            callback = self._queue.pop(0)
            callback()
        except Exception as e:
            logger.error(f"Error in scheduled task: {e}", exc_info=True)
        finally:
            self._executing = False
            
            # Schedule next task if available
            if self._queue:
                self._timer.start(0)


# Create singleton instance
ui_scheduler = UITaskScheduler()


def schedule_ui_task(callback, delay_ms=0):
    """
    Schedule a task to run on the UI thread after specified delay.
    Replacement for QTimer.singleShot pattern.
    
    Args:
        callback: Function to call
        delay_ms: Delay in milliseconds, 0 for next event loop iteration
    """
    ui_scheduler.schedule(callback, delay_ms)