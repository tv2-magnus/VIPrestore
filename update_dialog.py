# update_dialog.py

from PyQt6 import QtWidgets, QtCore
import webbrowser

class UpdateDialog(QtWidgets.QDialog):
    def __init__(self, current_version, new_version, commits_html, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.resize(550, 450)

        layout = QtWidgets.QVBoxLayout(self)

        # Top label summarizing versions
        summary_label = QtWidgets.QLabel(
            f"<h2 style='color:#0078D7;'>A new version is available!</h2>"
            f"<p><b>Current:</b> {current_version} &nbsp;&nbsp;→&nbsp;&nbsp;"
            f"<b>Latest:</b> {new_version}</p>"
        )
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # Show commits (if any)
        if commits_html.strip() and not commits_html.startswith("(Could not"):
            commits_label = QtWidgets.QLabel()
            commits_label.setText(commits_html)  # already built as HTML
            commits_label.setOpenExternalLinks(False)
            commits_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
            commits_label.linkActivated.connect(lambda url: webbrowser.open(url))
            layout.addWidget(commits_label)
        else:
            # Either no commits found or an error
            layout.addWidget(QtWidgets.QLabel(f"<b>Note:</b> {commits_html}"))

        # Buttons at bottom
        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(button_layout)

        btn_ok = QtWidgets.QPushButton("Download & Install")
        btn_cancel = QtWidgets.QPushButton("Cancel")

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_ok)
        button_layout.addWidget(btn_cancel)

        self.setLayout(layout)
