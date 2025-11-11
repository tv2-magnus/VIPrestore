import json
from pathlib import Path
from PyQt6 import QtWidgets, uic
from utils import resource_path

class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("login_dialog.ui"), self)
        self.loginButton.clicked.connect(self.accept)
        self.loadRemoteSystems()

    def get_user_config_dir(self) -> Path:
        """Returns the user-writable configuration directory."""
        import os
        import sys
        if sys.platform.startswith("win"):
            config_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "VIPrestore"
        elif sys.platform == "darwin":
            config_dir = Path.home() / "Library" / "Application Support" / "VIPrestore"
        else:
            config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "VIPrestore"
        return config_dir

    def loadRemoteSystems(self):
        # First try to load from user config directory
        user_config_file = self.get_user_config_dir() / "remotesystems.json"
        
        try:
            if user_config_file.exists():
                with open(user_config_file, "r", encoding="utf-8") as f:
                    systems = json.load(f)
            else:
                # Fallback to bundled file if user config doesn't exist
                with open(resource_path("remotesystems.json"), "r") as f:
                    systems = json.load(f)
        except Exception:
            systems = []
        self.comboBoxRemoteSystems.clear()
        self.remoteSystems = {}
        for system in systems:
            name = system.get("name", "")
            url = system.get("url", "")
            if name:
                self.comboBoxRemoteSystems.addItem(name)
                self.remoteSystems[name] = url

    def getCredentials(self):
        selected = self.comboBoxRemoteSystems.currentText()
        server_url = self.remoteSystems.get(selected, "")
        return (
            server_url,
            self.usernameLineEdit.text().strip(),
            self.passwordLineEdit.text().strip()
        )
