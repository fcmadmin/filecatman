import os, platform
import logging
from PySide6.QtCore import Qt, QEvent, QDir
from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QDialogButtonBox, QFileDialog, QMessageBox
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeyEvent, QCursor
from filecatman.core.functions import loadUI, warningMsgBox, uploadFile, getDataFilePath, æscape
from filecatman.core.objects import ÆDataFolderModel, ÆButtonLineEdit, ÆMessageBox


class FileManager(QDialog):
    treeModels = {}
    dialogName = 'File Manager'
    currentModel = None

    def __init__(self, parent):
        super(FileManager, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.main = parent
        self.app = parent.app
        self.config = self.app.config
        self.icons = self.app.iconsList.icons
        self.treeIcons = self.app.iconsList.treeIcons
        self.db = self.app.database
        self.dataDir = self.config['options']['defaultDataDir']

        self.logger.info(self.dialogName+" Dialog Opened")
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.ui = loadUI("gui/ui/filemanager.ui")
        self.layout().addWidget(self.ui)

        self.setMinimumSize(700, 550)
        self.setWindowTitle(self.dialogName)
        self.constructRestOfUi()

        self.setDefaults()
        self.createTypeListModel()
        self.ui.itemsTree.sortByColumn(1, Qt.AscendingOrder)

        self.connectSignals()
        self.setIcons()

    def connectSignals(self):
        self.ui.buttonBox.button(QDialogButtonBox.Close).clicked.connect(self.close)
        self.ui.actionRefresh.triggered.connect(self.updateTreeModels)
        self.ui.actionOpenFile.triggered.connect(self.openFileInDefaultApplication)
        self.ui.actionDeleteFile.triggered.connect(self.deleteFile)
        self.ui.actionApplyBulkAction.triggered.connect(self.applyBulkAction)
        self.ui.actionRenameFile.triggered.connect(self.renameFile)
        self.ui.actionUploadFile.triggered.connect(self.uploadFileDialog)
        self.ui.itemsTree.doubleClicked.connect(self.openFileInDefaultApplication)
        self.ui.itemsTree.customContextMenuRequested.connect(self.itemsTreeContextMenu, Qt.UniqueConnection)
        self.ui.actionCheckAll.triggered.connect(self.checkAll)
        self.ui.actionCheckNone.triggered.connect(self.checkNone)
        self.ui.actionCheckInverse.triggered.connect(self.checkInverse)
        self.ui.actionBulkDelete.triggered.connect(lambda: self.applyBulkAction(1))
        self.ui.actionBulkDeleteWithItems.triggered.connect(lambda: self.applyBulkAction(2))
        self.ui.actionAutoCreateItems.triggered.connect(lambda: self.applyBulkAction(3))
        self.ui.lineSearch.textEdited.connect(self.searchItemsTree)
        self.ui.lineSearch.buttonClicked.connect(self.ui.lineSearch.clear)
        self.ui.actionClose.triggered.connect(self.close)
        self.ui.actionHelpContents.triggered.connect(self.openHelpBrowser)
        self.ui.labelDataDirVal.linkActivated.connect(self.openDataDir)

    def setIcons(self):
        self.ui.actionUploadFile.setIcon(self.icons['Add'])
        self.ui.actionRefresh.setIcon(self.icons['Refresh'])
        self.ui.actionOpenFile.setIcon(self.icons['Play'])
        self.ui.actionDeleteFile.setIcon(self.icons['Remove'])
        self.ui.actionRenameFile.setIcon(self.icons['Edit'])
        self.ui.actionApplyBulkAction.setIcon(self.icons['Execute'])
        self.ui.comboBulkActions.setItemIcon(1, self.icons['Remove'])
        self.ui.comboBulkActions.setItemIcon(2, self.icons['Remove'])
        self.ui.comboBulkActions.setItemIcon(3, self.icons['Items'])
        self.ui.actionCheckAll.setIcon(self.icons['CheckAll'])
        self.ui.actionCheckNone.setIcon(self.icons['CheckNone'])
        self.ui.actionCheckInverse.setIcon(self.icons['CheckInverse'])
        self.ui.menuBulkActions.setIcon(self.icons['Execute'])
        self.ui.actionBulkDelete.setIcon(self.icons['Remove'])
        self.ui.actionBulkDeleteWithItems.setIcon(self.icons['Remove'])
        self.ui.actionAutoCreateItems.setIcon(self.icons['Items'])
        self.ui.actionClose.setIcon(self.icons['Exit'])
        self.ui.actionHelpContents.setIcon(self.icons['HelpContents'])

    def constructRestOfUi(self):
        self.ui.comboBulkActions = QComboBox()
        self.ui.comboBulkActions.setMaximumWidth(120)
        self.ui.comboBulkActions.addItem('Bulk Actions', 0)
        self.ui.comboBulkActions.addItem('Delete Files', 1)
        self.ui.comboBulkActions.addItem('Delete with Items', 2)
        self.ui.comboBulkActions.addItem('Auto Create Items', 3)
        self.ui.toolBar.insertWidget(self.ui.actionApplyBulkAction, self.ui.comboBulkActions)

        self.ui.lineSearch = ÆButtonLineEdit(icons=self.icons)
        self.ui.lineSearch.setMaximumWidth(200)
        self.ui.lineSearch.setPlaceholderText('Search Files')
        self.ui.toolBar.addWidget(self.ui.lineSearch)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.deleteKeyPressed()
        else:
            super().keyPressEvent(event)

    def openHelpBrowser(self):
        self.close()
        self.app.openHelpBrowser('filemanager.html')

    def setDefaults(self):
        for itemType in self.config['itemTypes']:
            if not itemType.isWeblinks:
                self.treeModels[itemType.nounName] = ÆDataFolderModel(self, itemType.nounName, advancedMode=True)

        self.ui.labelDataDirVal.setText('<a href="{0}">{0}</a>'.format(self.dataDir))

    def createTypeListModel(self):
        typeListModel = QStandardItemModel()
        for itemType in self.config['itemTypes']:
            if not itemType.isWeblinks:
                item = QStandardItem(itemType.pluralName)
                item.setIcon(self.icons[itemType.iconName])
                typeID = QStandardItem(itemType.nounName)
                typeListModel.appendRow((item, typeID))

        self.ui.typeList.setModel(typeListModel)

        selectionModel = self.ui.typeList.selectionModel()
        selectionModel.selectionChanged.connect(self.onTypeListSelectionChanged, Qt.UniqueConnection)

        index = self.ui.typeList.model().index(0, 0)
        self.ui.typeList.setCurrentIndex(index)

    def updateTreeModels(self):
        for itemType, model in self.treeModels.items():
            model.clear()
            model.setItemType(itemType)
        self.ui.itemsTree.sortByColumn(1, Qt.AscendingOrder)

    def returnItemName(self):
        indexes = self.ui.itemsTree.selectedIndexes()
        if indexes:
            itemName = self.currentModel.items[indexes[0].row()][1]
            itemExt = self.currentModel.items[indexes[0].row()][5]
            itemNameExt = itemName+'.'+itemExt
            if itemNameExt is not None:
                return itemNameExt
        return None

    def onTypeListSelectionChanged(self, selection):
        indexes = selection.indexes()
        if indexes:
            itemNounIndex = indexes[0].sibling(indexes[0].row(), 1)
            selectedItemNoun = indexes[0].model().itemFromIndex(itemNounIndex)
            selectedItemPlural = indexes[0].model().itemFromIndex(indexes[0])
            if selectedItemNoun.data(0) is not None:
                self.logger.debug(selectedItemNoun.data(0))
                self.displayFolder(selectedItemNoun.data(0))
                self.ui.labelTitle.setText("<b>"+selectedItemPlural.data(0)+"</b>")
                rowCount = self.currentModel.rowCount()
                if rowCount is 1:
                    self.ui.labelStatus.setText("<b>"+str(rowCount)+" File</b>")
                else:
                    self.ui.labelStatus.setText("<b>"+str(rowCount)+" Files</b>")
        self.ui.actionOpenFile.setEnabled(False)
        self.ui.actionDeleteFile.setEnabled(False)
        self.ui.actionRenameFile.setEnabled(False)
        self.ui.lineFileName.clear()

    def onItemsTreeSelectionChanged(self, selection=None):
        data = self.returnItemName()
        self.ui.lineFileName.setText(data)

        if selection is None:
            self.ui.actionOpenFile.setEnabled(False)
            self.ui.actionDeleteFile.setEnabled(False)
            self.ui.actionRenameFile.setEnabled(False)
            self.ui.lineFileName.clear()
        else:
            self.logger.debug(data)
            self.ui.actionOpenFile.setEnabled(True)
            self.ui.actionDeleteFile.setEnabled(True)
            self.ui.actionRenameFile.setEnabled(True)

    def displayFolder(self, itemType):
        self.currentModel = self.treeModels[itemType]
        self.ui.itemsTree.setModel(self.currentModel)
        self.ui.itemsTree.resizeColumnToContents(0)
        if self.ui.itemsTree.columnWidth(0) > 400:
            self.ui.itemsTree.setColumnWidth(0, 400)
        self.ui.itemsTree.setColumnWidth(1, 200)

        try:
            selectionModel = self.ui.itemsTree.selectionModel()
            selectionModel.selectionChanged.connect(self.onItemsTreeSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

    def deleteFile(self):
        indexes = self.ui.itemsTree.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            itemName = self.returnItemName()
            message = "Are you sure you want to delete <i>{}</i>?".format(itemName)
            msgBox = ÆMessageBox(self)
            msgBox.setIcon(msgBox.Icon.Information)
            msgBox.setWindowTitle("Confirm Deletion")
            msgBox.setText("<b>Confirm deletion of selected file?</b>")
            msgBox.setInformativeText(message)
            msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
            msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
            if self.currentModel.items[row][3] == 'Yes':
                msgBox.setCheckable(True)
                msgBox.checkboxes[0].setText("Delete corresponding database item.")
                msgBox.checkboxes[0].setChecked(True)
            ret = msgBox.exec_()
            if ret == msgBox.StandardButton.Ok:
                self.logger.info("Deletion Executed.")
                if self.currentModel.items[row][3] == 'Yes' and msgBox.checkboxes[0].isChecked():
                    self.currentModel.deleteFile(row, withItem=True)
                else:
                    self.currentModel.deleteFile(row)
            elif ret == msgBox.StandardButton.Cancel:
                self.logger.info("Deletion Cancelled.")
            msgBox.deleteLater()

    def renameFile(self):
        currentRow = self.ui.itemsTree.selectedIndexes()[0].row()
        index = self.currentModel.index(currentRow, 0)
        self.ui.itemsTree.setCurrentIndex(index)
        self.ui.itemsTree.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F2, Qt.NoModifier))

    def applyBulkAction(self, actionCode=None):
        comboBox = self.ui.comboBulkActions
        if not actionCode:
            actionCode = comboBox.itemData(comboBox.currentIndex())
            actionName = comboBox.currentText()
            self.logger.debug("Bulk Action '{}' selected. Iden: '{}'".format(actionName, actionCode))
        if actionCode >  0:
            rowIdens = []
            model = self.currentModel
            for row, item in enumerate(model.items):
                if item[0] is True:
                    rowIdens.append(row)
            if actionCode == 1:
                model.deleteFiles(rowIdens)
                self.logger.info(str(len(rowIdens))+" files deleted from data directory.")
            if actionCode == 2:
                model.deleteFiles(rowIdens, withItem=True)
                self.logger.info(str(len(rowIdens))+" files deleted from data directory and database.")
            if actionCode == 3:
                model.autoCreateItems(rowIdens)
        self.ui.itemsTree.clearSelection()
        self.ui.actionOpenFile.setEnabled(False)
        self.ui.actionDeleteFile.setEnabled(False)
        self.ui.actionRenameFile.setEnabled(False)
        self.ui.lineFileName.clear()
        comboBox.setCurrentIndex(0)

    def itemsTreeContextMenu(self):
        self.ui.menuTable.exec_(QCursor().pos())

    def checkAll(self):
        self.logger.debug("All rows checked.")
        self.currentModel.checkAll()

    def checkNone(self):
        self.logger.debug("All rows unchecked.")
        self.currentModel.checkNone()

    def checkInverse(self):
        self.logger.debug("Checked Selection Inverted.")
        self.currentModel.checkInverse()

    def uploadFileDialog(self):
        fileDialog = QFileDialog(self.main)
        fileObj = fileDialog.getOpenFileName(None, "Upload a New file", dir=QDir().homePath())
        fileDialog.deleteLater()
        fileSource = fileObj[0]
        if fileSource:
            baseFilename = os.path.basename(fileSource)
            fileName = os.path.splitext(baseFilename)[0]
            fileExtension = os.path.splitext(fileSource)[1][1:].lower().strip()
            baseFilename = fileName+'.'+str(fileExtension)
            self.logger.debug(baseFilename)
            fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
            if fileType:
                model = self.ui.typeList.model()
                pluralItem = model.findItems(fileType, Qt.MatchExactly, 1)[0]
                pluralIndex = model.indexFromItem(pluralItem)
                self.ui.typeList.setCurrentIndex(model.index(pluralIndex.row(), 0))

                dirType = self.config['itemTypes'].dirFromNoun(fileType)
                fileDestination = getDataFilePath(self.dataDir, dirType, baseFilename)
                if not os.path.exists(getDataFilePath(self.dataDir, dirType, æscape(baseFilename))):
                    if uploadFile(self.main, fileSource, fileDestination, fileType):
                        self.updateTreeModels()
                        self.displayFolder(fileType)
                    else:
                        warningMsgBox(self.main, "Error Uploading File")
                else:
                    self.logger.warning("File Already Exists: `{}`".format(baseFilename))
                    message = "Do you want you want to overwrite the existing file?"
                    msgBox = QMessageBox(self)
                    msgBox.setIcon(QMessageBox.Question)
                    msgBox.setWindowTitle("Overwrite Existing File?")
                    msgBox.setText(message)
                    msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                    msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                    ret = msgBox.exec_()
                    if ret == msgBox.StandardButton.Ok:
                        if uploadFile(self.main, fileSource, fileDestination, fileType):
                            self.updateTreeModels()
                            self.displayFolder(fileType)
                        else:
                            warningMsgBox(self.main, "Error Uploading File")
                    elif ret == msgBox.StandardButton.Cancel:
                        self.logger.error("Upload Aborted.")
                    msgBox.deleteLater()
            else:
                warningMsgBox(self.main, "File type is not recognised. Upload aborted.", "Unknown File Type")

    def searchItemsTree(self, keyword):
        if not keyword == '':
            self.ui.itemsTree.keyboardSearch(keyword)

    def openFileInDefaultApplication(self):
        itemName = self.returnItemName()
        itemType = self.currentModel.currentItemType
        try:
            self.logger.debug("Item Type: "+itemType)
            dataDir = self.config['options']['defaultDataDir']

            self.logger.debug(itemType+" Name: "+itemName)
            if platform.system() == "Windows":
                os.startfile(getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName))
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.call(
                    ('open', getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName)))
            else:
                os.system('xdg-open "{}"'.format(
                    getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName)))
        except BaseException as e:
            warningMsgBox(self, e, title="Error Opening File")

    def openDataDir(self):
        if platform.system() == "Windows":
            os.startfile(self.dataDir)
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.call(('open', self.dataDir))
        else:
            os.system('xdg-open "{}"'.format(self.dataDir))