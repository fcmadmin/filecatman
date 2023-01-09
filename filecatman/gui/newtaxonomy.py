import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QDialog
from filecatman.core.functions import loadUI, warningMsgBox, æscape
from filecatman.gui.pickicon import PickIconDialog


class NewTaxonomyDialog(QDialog):
    iconName = None
    appName = 'New Taxonomy'
    newTaxonomy = Signal(str, str, str, str, str, Qt.CheckState, Qt.CheckState, Qt.CheckState)
    
    def __init__(self, parent):
        super(NewTaxonomyDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db

        self.logger.info(self.appName+" Dialog Opened")
        self.ui = loadUI("gui/ui/newtaxonomy.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(400, 300)
        self.setWindowTitle(self.appName)

        self.setDefaults()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.buttonIcon.clicked.connect(self.openPickIconDialog)

        self.ui.tabWidget.setTabIcon(0, self.icons['DetailsEdit'])

    def setDefaults(self):
        self.ui.buttonIcon.setIcon(self.icons['Categories'])
        self.iconName = "Categories"

    def openPickIconDialog(self):
        pickIconDialog = PickIconDialog(self)
        pickIconDialog.iconNameSignal.connect(self.setButtonIcon)
        pickIconDialog.iconDeleted.connect(self.resetTaxonomyIcon)
        pickIconDialog.exec_()
        pickIconDialog.deleteLater()

    def setButtonIcon(self, iconName):
        self.ui.buttonIcon.setIcon(self.icons[iconName])
        self.iconName = iconName

    def resetTaxonomyIcon(self):
        self.setButtonIcon("Categories")

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

            self.newTaxonomy.emit(
                nounName, pluralName, tableName, folderName, self.iconName, typeVisible, hasChildren, isTags)

            self.close()