import csv
import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QDialog
from filecatman.core.functions import loadUI, warningMsgBox, æscape
from filecatman.gui.pickicon import PickIconDialog


class NewItemTypeDialog(QDialog):
    iconName = None
    appName = 'New Item Type'
    newItemType = Signal(str, str, str, str, str, bool, list)
    
    def __init__(self, parent):
        super(NewItemTypeDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db

        self.logger.info(self.appName+" Dialog Opened")
        self.ui = loadUI("gui/ui/newitemtype.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(400, 300)
        self.setWindowTitle(self.appName)

        self.setDefaults()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.buttonAddExtension.clicked.connect(self.addExtensions)
        self.ui.buttonRemoveExtension.clicked.connect(self.removeSelectedExtension)
        self.ui.buttonIcon.clicked.connect(self.openPickIconDialog)

        self.ui.tabWidget.setTabIcon(0, self.icons['DetailsEdit'])
        self.ui.tabWidget.setTabIcon(1, self.icons['Options'])
        self.ui.buttonAddExtension.setIcon(self.icons['Add'])
        self.ui.buttonRemoveExtension.setIcon(self.icons['Remove'])

    def setDefaults(self):
        self.ui.buttonIcon.setIcon(self.icons['Items'])
        self.iconName = "Items"

    def removeSelectedExtension(self):
        index = self.ui.extensionList.selectedIndexes()[0]
        itemRemoved = self.ui.extensionList.takeItem(index.row())
        self.logger.debug(itemRemoved.data(0)+" was popped.")

    def addExtensions(self):
        lineEditText = self.ui.lineExtension.text()

        reader = csv.reader([lineEditText], skipinitialspace=True)
        for extensions in reader:
            for ext in extensions:
                ext = æscape(ext)
                if not self.ui.extensionList.findItems(ext, Qt.MatchExactly):
                    self.ui.extensionList.addItem(ext)
                self.logger.debug(ext)

        self.ui.lineExtension.clear()

    def openPickIconDialog(self):
        pickIconDialog = PickIconDialog(self)
        pickIconDialog.iconNameSignal.connect(self.setButtonIcon)
        pickIconDialog.iconDeleted.connect(self.resetItemTypeIcon)
        pickIconDialog.exec_()
        pickIconDialog.deleteLater()

    def setButtonIcon(self, iconName):
        self.ui.buttonIcon.setIcon(self.icons[iconName])
        self.iconName = iconName

    def resetItemTypeIcon(self):
        self.setButtonIcon("Items")

    def processData(self):
        nounName = æscape(self.ui.lineNoun.text())
        pluralName = æscape(self.ui.linePlural.text())
        tableName = æscape(self.ui.lineTable.text())
        folderName = æscape(self.ui.lineFolder.text())

        if self.ui.checkVisible.isChecked() is True:
            typeVisible = True
        else:
            typeVisible = False

        i = 0
        extensions = list()
        while self.ui.extensionList.item(i):
            item = self.ui.extensionList.item(i)
            i += 1
            extensions.append(item.text())

        if (nounName or pluralName or tableName) == "":
            warningMsgBox(self.parent, "One or more fields are missing.", "Field Missing")
            self.ui.labelNoun.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Noun Name: </span></p>')
            self.ui.labelPlural.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Plural Name: </span></p>')
            self.ui.labelTable.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Table Name: </span></p>')
            self.ui.labelNoun.textFormat()
            self.ui.labelPlural.textFormat()
            self.ui.labelTable.textFormat()
            self.ui.tabWidget.setCurrentIndex(0)
        else:
            self.logger.debug("Noun: "+nounName+" Plural: "+pluralName+" Table: "+tableName+" Folder: "+folderName)
            self.logger.debug("Visible: "+str(typeVisible))
            self.logger.debug("Extensions to be inserted:")
            self.logger.debug(extensions)
            self.logger.debug("Icon Name: "+self.iconName)

            self.newItemType.emit(
                nounName, pluralName, tableName, folderName, self.iconName, typeVisible, extensions)

            self.close()