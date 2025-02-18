import json
import os
from PyQt6 import QtWidgets, QtCore

class SystemsEditorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Systems Editor")
        self.resize(600, 400)
        self.systems_file = "remotesystems.json"
        self.systems = []
        self.setup_ui()
        self.load_systems()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # Layout with systems list and detail editor
        hlayout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(hlayout)

        # Left: Systems list and buttons
        left_layout = QtWidgets.QVBoxLayout()
        hlayout.addLayout(left_layout, 1)
        self.list_widget = QtWidgets.QListWidget()

        # Enable drag-and-drop reordering
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        left_layout.addWidget(self.list_widget)
        btn_layout = QtWidgets.QHBoxLayout()
        left_layout.addLayout(btn_layout)
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_remove = QtWidgets.QPushButton("Remove")
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)

        # Right: Detail form
        form_layout = QtWidgets.QFormLayout()
        hlayout.addLayout(form_layout, 2)
        self.edit_name = QtWidgets.QLineEdit()
        self.edit_url = QtWidgets.QLineEdit()
        form_layout.addRow("Name:", self.edit_name)
        form_layout.addRow("URL:", self.edit_url)

        # Bottom: Save and Cancel buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        main_layout.addWidget(self.button_box)

        # Connect signals
        self.list_widget.currentRowChanged.connect(self.on_selection_changed)
        self.list_widget.model().rowsMoved.connect(self.update_systems_order)  # Track reordering
        self.edit_name.textEdited.connect(self.on_name_edited)
        self.edit_url.textEdited.connect(self.on_url_edited)
        self.btn_add.clicked.connect(self.add_system)
        self.btn_remove.clicked.connect(self.remove_system)
        self.button_box.accepted.connect(self.save_and_accept)
        self.button_box.rejected.connect(self.reject)

    def load_systems(self):
        if os.path.exists(self.systems_file):
            try:
                with open(self.systems_file, "r") as f:
                    self.systems = json.load(f)
            except Exception:
                self.systems = []
        else:
            self.systems = []
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for sys_data in self.systems:
            name = sys_data.get("name", "") or "<unnamed>"
            self.list_widget.addItem(name)
        if self.systems:
            self.list_widget.setCurrentRow(0)
        else:
            self.clear_details()

    def clear_details(self):
        self.edit_name.clear()
        self.edit_url.clear()

    def on_selection_changed(self, row: int):
        if 0 <= row < len(self.systems):
            sys_data = self.systems[row]
            self.edit_name.blockSignals(True)
            self.edit_url.blockSignals(True)
            self.edit_name.setText(sys_data.get("name", ""))
            self.edit_url.setText(sys_data.get("url", ""))
            self.edit_name.blockSignals(False)
            self.edit_url.blockSignals(False)
        else:
            self.clear_details()

    def on_name_edited(self, text: str):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.systems):
            self.systems[row]["name"] = text
            self.list_widget.currentItem().setText(text or "<unnamed>")

    def on_url_edited(self, text: str):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.systems):
            self.systems[row]["url"] = text

    def add_system(self):
        new_system = {"name": "", "url": ""}
        self.systems.append(new_system)
        self.list_widget.addItem("<unnamed>")
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def remove_system(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Remove System", "Remove selected system?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            del self.systems[row]
            self.refresh_list()

    def update_systems_order(self):
        """Update self.systems list order when user drags and drops items."""
        new_order = []
        for index in range(self.list_widget.count()):
            item_text = self.list_widget.item(index).text()
            for system in self.systems:
                if system["name"] == item_text:
                    new_order.append(system)
                    break
        self.systems = new_order

    def save_and_accept(self):
        try:
            with open(self.systems_file, "w") as f:
                json.dump(self.systems, f, indent=4)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save systems: {e}")
            return
        self.accept()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    dlg = SystemsEditorDialog()
    dlg.exec()