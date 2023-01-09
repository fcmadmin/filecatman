import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget, QGroupBox, QGridLayout, QDialogButtonBox, QTextEdit, \
    QFrame


class InfoDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.config = parent.config
        self.db = parent.db
        self.setWindowTitle("Database Info")
        self.setFixedSize(500, 400)

        self.displayInformation()

    def displayInformation(self):
        self.db.open()
        layout = QVBoxLayout()

        gridlayout = QGridLayout()
        gridlayout.addWidget(QLabel("<b>Name:</b> "), 0, 0)
        nameLabel = QLabel(os.path.basename(self.db.config['db']))
        gridlayout.addWidget(nameLabel, 0, 1)
        gridlayout.addWidget(QLabel("<b>Data Folder:</b>"), 1, 0)
        dataDirText = QTextEdit(self.config['options']['defaultDataDir'])
        dataDirText.setReadOnly(True)
        dataDirText.setFrameStyle(QFrame.NoFrame)
        dataDirText.setStyleSheet("background: rgba(0,0,0,0%)")
        dataDirText.setContextMenuPolicy(Qt.PreventContextMenu)
        gridlayout.addWidget(dataDirText, 1, 1)
        gridlayout.addWidget(QLabel("<b>Item Count:</b> "), 2, 0)
        gridlayout.addWidget(QLabel(str(self.db.selectCount('items'))), 2, 1)
        gridlayout.addWidget(QLabel("<b>Category Count:</b> "), 3, 0)
        gridlayout.addWidget(QLabel(str(self.db.selectCount('terms'))), 3, 1)
        gridlayout.addWidget(QLabel("<b>Relation Count:</b> "), 4, 0)
        gridlayout.addWidget(QLabel(str(self.db.selectCount('term_relationships'))), 4, 1)
        tables = ", ".join(self.db.tables())
        label = QLabel("<b>Tables:</b> "+tables)
        label.setWordWrap(True)
        gridlayout.addWidget(label, 5, 0, 1, 2)
        gridwidget = QWidget()
        gridwidget.setLayout(gridlayout)
        groupSQL = QGroupBox()
        groupSQL.setLayout(gridlayout)
        groupSQL.setTitle("Database Information")
        layout.addWidget(groupSQL)

        gridlayout = QGridLayout()
        label = QLabel("<b>Version</b>: ")
        label.textFormat()
        gridlayout.addWidget(label, 0, 0)
        gridlayout.addWidget(QLabel(self.db.versionInfo()), 0, 1)
        gridwidget = QWidget()
        gridwidget.setLayout(gridlayout)
        groupSQL = QGroupBox()
        groupSQL.setLayout(gridlayout)
        if self.db.config['type'] == 'mysql':
            groupSQL.setTitle("My SQL Information")
        if self.db.config['type'] == 'sqlite':
            groupSQL.setTitle("SQLite Information")
        layout.addWidget(groupSQL)

        layout.addStretch()
        bb = QDialogButtonBox()
        bb.addButton(bb.StandardButton.Close)
        layout.addWidget(bb)
        self.setLayout(layout)
        self.db.close()
        bb.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.close)