from PySide6.QtCore import Qt, Signal
from filecatman.core.functions import warningMsgBox, æscape
from filecatman.gui.newtaxonomy import NewTaxonomyDialog


class EditTaxonomyDialog(NewTaxonomyDialog):
    iconName = None
    appName = 'Edit Taxonomy'
    editedTaxonomy = Signal(int, str, str, str, str, str, Qt.CheckState, Qt.CheckState, Qt.CheckState)
    currentNoun = None
    
    def __init__(self, parent, dataList):
        super(EditTaxonomyDialog, self).__init__(parent)

        self.treeRowIndex = dataList[0]
        self.ui.checkVisible.setCheckState(dataList[1])
        self.ui.buttonIcon.setIcon(self.icons[dataList[2]])
        self.iconName = dataList[2]
        self.ui.lineNoun.setText(dataList[3])
        self.currentNoun = dataList[3]
        self.ui.linePlural.setText(dataList[4])
        self.ui.lineTable.setText(dataList[5])
        self.ui.lineFolder.setText(dataList[6])
        self.ui.checkHasChildren.setCheckState(dataList[7])
        self.ui.checkTagsMode.setCheckState(dataList[8])

    def resetTaxonomyIcon(self):
        self.setButtonIcon("Categories")
        self.config['taxonomies'][self.currentNoun].setIconName("Categories")

    def processData(self):
        nounName = æscape(self.ui.lineNoun.text())
        pluralName = æscape(self.ui.linePlural.text())
        tableName = æscape(self.ui.lineTable.text())
        folderName = æscape(self.ui.lineFolder.text())

        typeVisible = self.ui.checkVisible.checkState()
        hasChildren = self.ui.checkHasChildren.checkState()
        isTags = self.ui.checkTagsMode.checkState()

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
            self.logger.debug("Has Children: "+str(hasChildren))
            self.logger.debug("Icon Name: "+self.iconName)

            self.editedTaxonomy.emit(
                self.treeRowIndex, nounName, pluralName, tableName, folderName,
                self.iconName, typeVisible, hasChildren, isTags
            )

            self.close()