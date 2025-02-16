import os
import sys

def resource_path(relative_path):
    """Return the absolute path to a resource, works in dev and PyInstaller."""
    try:
        # PyInstaller stores temp path in _MEIPASS.
        base_path = sys._MEIPASS
    except AttributeError:
        # In dev, use the directory of this file.
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)
