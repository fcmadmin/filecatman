import os
import logging
from PySide6.QtCore import Signal, QSize, QDir
from PySide6.QtGui import QStandardItemModel, QIcon
from PySide6.QtWidgets import QDialog, QListWidgetItem, QFileDialog, QMessageBox
from filecatman.core.functions import loadUI, uploadFile, deleteFile, warningMsgBox


class PickIconDialog(QDialog):
    iconsListModel = QStandardItemModel()
    dialogName = 'Pick Icon'
    iconNameSignal = Signal(str)
    iconDeleted = Signal()

    def __init__(self, parent):
        super(PickIconDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.mainWindow = parent.mainWindow
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/pickicon.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(610, 550)
        self.setWindowTitle(self.dialogName)

        self.setDefaults()
        self.iconsDir = self.mainWindow.iconsDir
        self.logger.debug("Icons Directory: "+self.iconsDir)

        self.ui.buttonAdd.setIcon(self.icons['Add'])
        self.ui.buttonRemove.setIcon(self.icons['Remove'])

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.iconsList.doubleClicked.connect(self.processData)
        self.ui.buttonAdd.clicked.connect(self.addIcon)
        self.ui.buttonRemove.clicked.connect(self.removeIcon)

    def setDefaults(self):
        for iconName, icon in sorted(self.icons.items()):
            if not icon.isNull():
                listItem = QListWidgetItem(icon, iconName)
                listItem.setSizeHint(QSize(75, 75))
                self.ui.iconsList.addItem(listItem)

    def insertIconIntoTree(self, iconName):
        listItem = QListWidgetItem(self.icons[iconName], iconName)
        listItem.setSizeHint(QSize(75, 75))
        self.ui.iconsList.addItem(listItem)
        self.ui.iconsList.setCurrentItem(listItem)

    def processData(self):
        itemName = self.ui.iconsList.currentItem().data(0)
        self.iconNameSignal.emit(itemName)
        self.close()

    def addIcon(self):
        selectIconDialog = QFileDialog(self.mainWindow)
        selectIconDialog.setFileMode(selectIconDialog.FileMode.ExistingFile)
        selectIconDialog.setDirectory(QDir().homePath())
        selectIconDialog.setWindowTitle("Select Icon")
        selectIconDialog.setViewMode(selectIconDialog.ViewMode.List)
        if selectIconDialog.exec_():
            fileObj = selectIconDialog.selectedFiles()
            iconSource = fileObj[0]
            fileExtension = os.path.splitext(iconSource)[1][1:].lower().strip()
            if fileExtension in self.mainWindow.defaultExtensions['image']:
                self.logger.debug(iconSource)
                baseIconName = os.path.basename(iconSource)
                fileDestination = os.path.join(self.iconsDir,baseIconName)
                try:
                    if not os.path.exists(fileDestination):
                        if uploadFile(self.parent, iconSource, fileDestination):
                            self.icons[baseIconName] = QIcon(fileDestination)
                            self.insertIconIntoTree(baseIconName)
                        else:
                            self.logger.error("Error Uploading Icon")
                    else:
                        self.logger.warning("Icon Already Exists: `{}`".format(baseIconName))
                        message = "Do you want you want to overwrite the existing icon?"
                        msgBox = QMessageBox(self)
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setWindowTitle("Overwrite Existing Icon?")
                        msgBox.setText(message)
                        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                        ret = msgBox.exec_()
                        if ret == msgBox.StandardButton.Ok:
                            if uploadFile(self.parent, iconSource, fileDestination):
                                self.icons[baseIconName] = QIcon(fileDestination)
                                self.insertIconIntoTree(baseIconName)
                            else:
                                self.logger.error("Error Uploading Icon")
                        elif ret == msgBox.StandardButton.Cancel:
                            self.logger.info("Upload Aborted.")
                        msgBox.deleteLater()
                except BaseException as e:
                    warningMsgBox(self, e, title="Error Uploading Icon")
            else:
                warningMsgBox(self.parent, "Icon type is not recognised. Upload aborted.", "Unknown Icon Type")
        selectIconDialog.deleteLater()

    def removeIcon(self):
        try:
            if not self.ui.iconsList.currentItem():
                return False
            iconName = self.ui.iconsList.currentItem().data(0)
            itemPath = os.path.join(self.iconsDir,iconName)
            if isinstance(self.icons[iconName], QIcon):
                if os.path.exists(itemPath):
                    if deleteFile(self.mainWindow, itemPath):
                        self.ui.iconsList.takeItem(self.ui.iconsList.currentRow())
                        self.icons.pop(iconName, None)
                        self.iconDeleted.emit()
                        return True
                    else:
                        return False
            self.logger.warning("`{}` is not a custom icon or doesn't exist.".format(iconName))
            return False
        except BaseException as e:
            warningMsgBox(self, e, title="Error Deleting Icon")