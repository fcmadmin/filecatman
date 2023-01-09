import csv
from PySide6.QtCore import Qt, Signal
from filecatman.core.functions import warningMsgBox, æscape
from filecatman.gui.newitemtype import NewItemTypeDialog


class EditItemTypeDialog(NewItemTypeDialog):
    appName = 'Edit Item Type'
    editedItemType = Signal(int, str, str, str, str, str, Qt.CheckState, list)
    currentNoun = None

    def __init__(self, parent, dataList):
        super(EditItemTypeDialog, self).__init__(parent)

        self.treeRowIndex = dataList[0]
        self.ui.checkVisible.setCheckState(dataList[1])
        self.ui.buttonIcon.setIcon(self.icons[dataList[2]])
        self.iconName = dataList[2]
        self.ui.lineNoun.setText(dataList[3])
        self.currentNoun = dataList[3]
        self.ui.linePlural.setText(dataList[4])
        self.ui.lineTable.setText(dataList[5])
        self.ui.lineFolder.setText(dataList[6])
        if not dataList[7] == "":
            reader = csv.reader([dataList[7]], skipinitialspace=True)
            for extensions in reader:
                for ext in extensions:
                    if not self.ui.extensionList.findItems(ext, Qt.MatchExactly):
                        self.ui.extensionList.addItem(ext)

    def resetItemTypeIcon(self):
        self.setButtonIcon("Items")
        self.config['itemTypes'][self.currentNoun].setIconName("Items")

    def processData(self):
        nounName = æscape(self.ui.lineNoun.text())
        pluralName = æscape(self.ui.linePlural.text())
        tableName = æscape(self.ui.lineTable.text())
        folderName = æscape(self.ui.lineFolder.text())
        iconName = self.iconName

        typeVisible = self.ui.checkVisible.checkState()

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
            self.logger.debug("Icon Name: "+iconName)

            self.editedItemType.emit(
                self.treeRowIndex, nounName, pluralName, tableName, folderName, iconName, typeVisible, extensions)

            self.close()
