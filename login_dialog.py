import json
from PyQt6 import QtWidgets, uic
from utils import resource_path

class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("login_dialog.ui"), self)
        self.loginButton.clicked.connect(self.accept)
        self.loadRemoteSystems()

    def loadRemoteSystems(self):
        try:
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
