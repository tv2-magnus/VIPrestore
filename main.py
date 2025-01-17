import sys
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QLineEdit,
    QVBoxLayout, QWidget, QMenuBar, QStatusBar,
    QGroupBox, QLabel, QSplitter, QFrame, QPushButton, QFormLayout, QHBoxLayout
)
from PySide6.QtGui import QAction, QIcon


class MyTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data[0]) if self._data else 0

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self._data[index.row()][index.column()]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("High-Performance Table with Sidebar")
        self.resize(800, 600)

        # Menu Bar
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("background-color:rgb(201, 201, 201); color: black;")
        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Status Bar
        self.setStatusBar(QStatusBar())

        # Main Layout
        main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Top Bar with Toggle Button
        top_bar = QHBoxLayout()
        self.toggle_button = QPushButton()
        self.toggle_button.setFixedSize(30, 30)
        self.toggle_button.setIcon(QIcon.fromTheme("view-sidebar"))  # Example icon
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        top_bar.addWidget(self.toggle_button, alignment=Qt.AlignLeft)

        # Add top bar to main layout
        main_layout.addLayout(top_bar)

        # Splitter for Sidebar and Table
        self.splitter = QSplitter(Qt.Horizontal)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFrameShape(QFrame.StyledPanel)
        sidebar_layout = QVBoxLayout(self.sidebar)

        # Filter Area
        filter_group = QGroupBox("Filters")
        filter_layout = QFormLayout(filter_group)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Use 'src:' or 'dst:' here...")
        self.search_box.textChanged.connect(self.on_search_text_changed)
        filter_layout.addRow(QLabel("Search:"), self.search_box)

        sidebar_layout.addWidget(filter_group)
        sidebar_layout.addStretch()  # Push content to the top
        self.splitter.addWidget(self.sidebar)

        # Main Content Area
        main_content = QWidget()
        main_content.setLayout(QVBoxLayout())
        self.splitter.addWidget(main_content)

        # Table in Main Content
        table_frame = QFrame()
        table_frame.setFrameShape(QFrame.Box)
        table_frame.setFrameShadow(QFrame.Raised)
        table_layout = QVBoxLayout(table_frame)
        self.table_view = QTableView()
        data = [
            ["Row0-Col0", "Row0-Col1"],
            ["Row1-Col0", "Row1-Col1"],
            ["Row2-Col0", "Row2-Col1"]
        ]
        self.model = MyTableModel(data)
        self.table_view.setModel(self.model)
        table_layout.addWidget(self.table_view)

        main_content.layout().addWidget(table_frame)

        # Add Splitter to Main Layout
        main_layout.addWidget(self.splitter)

    def toggle_sidebar(self):
        if self.sidebar.isVisible():
            self.sidebar.hide()
            self.splitter.setSizes([0, 1])
            self.toggle_button.setIcon(QIcon.fromTheme("go-next"))  # Icon for "hidden"
        else:
            self.sidebar.show()
            self.splitter.setSizes([1, 3])
            self.toggle_button.setIcon(QIcon.fromTheme("view-sidebar"))  # Icon for "shown"

    def on_search_text_changed(self, text):
        # Placeholder for future filtering logic
        pass


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
