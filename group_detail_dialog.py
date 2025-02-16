import json
from PyQt6 import QtCore
from PyQt6 import QtWidgets

class GroupDetailDialog(QtWidgets.QDialog):
    def __init__(self, group_id: str, group_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Group Service: {group_id}")
        self.resize(700, 400)

        layout = QtWidgets.QVBoxLayout(self)
        self.detailsTable = QtWidgets.QTableWidget(self)
        self.detailsTable.setColumnCount(2)
        self.detailsTable.horizontalHeader().setVisible(False)
        self.detailsTable.verticalHeader().setVisible(False)
        self.detailsTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.detailsTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.detailsTable.setWordWrap(True)
        layout.addWidget(self.detailsTable)

        self._populateTable(group_id, group_data)

    def _populateTable(self, group_id: str, group_data: dict):
        self.detailsTable.setRowCount(0)

        def add_row(field: str, val: str):
            r = self.detailsTable.rowCount()
            self.detailsTable.insertRow(r)
            item_field = QtWidgets.QTableWidgetItem(field)
            item_field.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.detailsTable.setItem(r, 0, item_field)

            item_val = QtWidgets.QTableWidgetItem(val)
            item_val.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            item_val.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
            self.detailsTable.setItem(r, 1, item_val)

        add_row("Service Kind", "Group-Based Service")
        booking = group_data.get("booking", {})
        add_row("serviceId", booking.get("serviceId", group_id))
        add_row("lockedBy", booking.get("lockedBy", ""))
        add_row("from", booking.get("from", ""))
        add_row("to", booking.get("to", ""))
        descriptor = booking.get("descriptor", {})
        add_row("descriptor.label", descriptor.get("label", ""))
        add_row("descriptor.desc", descriptor.get("desc", ""))
        res_obj = group_data.get("res", {})
        json_str = json.dumps(res_obj, indent=2)
        add_row("res", json_str)