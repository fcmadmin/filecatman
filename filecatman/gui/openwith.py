import logging
import os
from PySide6.QtCore import Signal, Qt, QDir
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QDialog, QListWidgetItem, QMenu, QFileDialog
from filecatman.core.functions import loadUI, warningMsgBox


class OpenWithDialog(QDialog):
    appName = 'Open With'
    itemInserted = Signal()
    fileExt = ''

    def __init__(self, parent, fileExt):
        super(OpenWithDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.app = parent.app
        self.config = parent.config
        self.icons = parent.icons
        self.db = parent.db
        self.fileExt = fileExt

        self.logger.info(self.appName+" Dialog Opened")
        self.ui = loadUI("gui/ui/openwith.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(600, 300)
        self.setWindowTitle(self.appName)
        self.setDefaults()
        self.constructRestOfUi()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.buttonAddCommand.clicked.connect(self.addCommand)
        self.ui.buttonBrowse.clicked.connect(self.browseDialog)
        self.ui.commandsList.currentItemChanged.connect(self.onListItemChanged)
        self.ui.commandsList.customContextMenuRequested.connect(self.commandsListContextMenu)

    def constructRestOfUi(self):
        self.ui.menuList = QMenu()
        self.ui.actionRemoveCommand = QAction(self.icons["Remove"], "Remove Command", self)
        self.ui.menuList.addAction(self.ui.actionRemoveCommand)

        self.ui.actionRemoveCommand.triggered.connect(self.removeCommand)

    def setDefaults(self):
        if self.fileExt in self.config["openWith"]:
            for appName, appPath in self.config["openWith"][self.fileExt].items():
                listItem = QListWidgetItem(appName)
                listItem.setData(Qt.UserRole, appPath)
                self.ui.commandsList.addItem(listItem)

    def addCommand(self):
        if self.ui.lineCommand.text().strip() != "":
            appPath = self.ui.lineCommand.text().strip()
            # if os.name == "nt":
            appName = appPath
            #appName = appPath.split("/")[-1]
            listItem = QListWidgetItem(appName)
            listItem.setData(Qt.UserRole, appPath)
            self.ui.commandsList.addItem(listItem)
        self.ui.lineCommand.clear()

    def removeCommand(self):
        row = self.ui.commandsList.currentRow()
        self.ui.commandsList.takeItem(row)

    def onListItemChanged(self):
        currentItem = self.ui.commandsList.currentItem()
        if currentItem:
            commandName = currentItem.data(Qt.DisplayRole)
            commandPath = currentItem.data(Qt.UserRole)
            print("Command Name: "+commandName+" Command Path: "+commandPath)

    def processData(self):
        i = 0
        commandsDict = dict()
        while self.ui.commandsList.item(i):
            item = self.ui.commandsList.item(i)
            commandName = item.data(Qt.DisplayRole)
            commandPath = item.data(Qt.UserRole)
            i += 1
            commandsDict[commandName] = commandPath
        self.config["openWith"][self.fileExt] = commandsDict
        self.close()

    def commandsListContextMenu(self):
        self.ui.menuList.exec_(QCursor().pos())

    def browseDialog(self):
        browseDialog = QFileDialog(self.parent)
        fileObj = browseDialog.getOpenFileName(None, "Upload a New file", dir=QDir().homePath())
        browseDialog.deleteLater()
        filePath = fileObj[0]
        try:
            if filePath:
                self.ui.lineCommand.setText(filePath)
        except BaseException as e:
            warningMsgBox(self, e, title="Error Selecting File")

    def hideEvent(self, event):
        self.close()