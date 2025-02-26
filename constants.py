import os
from utils import resource_path

# Get version from file
def get_version():
    try:
        with open(resource_path("version.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

# Application identifiers
APP_NAME = "VIPrestore"
APP_VERSION = get_version()
APP_ID = f"tv2.{APP_NAME.lower()}.client.{APP_VERSION}"
APP_VERSION_FILE = "version.txt"