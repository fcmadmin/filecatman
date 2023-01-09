import logging
import os, platform
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QCursor, QAction
from PySide6.QtWidgets import QDialog, QMenu
from filecatman.core.objects import ÆDataFolderModel, ÆButtonLineEdit
from filecatman.core.functions import loadUI, getDataFilePath, warningMsgBox


class SelectFileDialog(QDialog):
    treeModels = {}
    dialogName = 'Select Existing File'
    currentModel = None
    selectedItemNameSignal = Signal(str)

    def __init__(self, parent):
        super(SelectFileDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.main = parent
        self.app = parent.app
        self.config = parent.config
        self.icons = parent.icons
        self.treeIcons = parent.treeIcons
        self.db = parent.db
        self.dataDir = self.config['options']['defaultDataDir']

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/selectfiledialog.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(600, 450)
        self.setWindowTitle(self.dialogName)
        self.constructRestOfUI()

        self.setDefaults()
        self.createTypeListModel()
        self.ui.itemsTree.sortByColumn(1, Qt.AscendingOrder)

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Open).clicked.connect(self.processData)
        self.ui.itemsTree.doubleClicked.connect(self.processData, Qt.UniqueConnection)
        self.ui.buttonRefresh.clicked.connect(self.updateTreeModels)
        self.ui.actionRefresh.triggered.connect(self.updateTreeModels)
        self.ui.lineSearch.textEdited.connect(self.searchItemsTree)
        self.ui.lineSearch.buttonClicked.connect(self.ui.lineSearch.clear)
        self.ui.labelDataDirVal.linkActivated.connect(self.openDataDir)
        self.ui.itemsTree.customContextMenuRequested.connect(self.itemsTreeContextMenu)
        self.ui.actionSelectFile.triggered.connect(self.processData)
        self.ui.actionPreviewFile.triggered.connect(self.openFileInDefaultApplication)

        self.ui.actionPreviewFile.setIcon(self.icons['Play'])
        self.ui.actionRefresh.setIcon(self.icons['Refresh'])
        self.ui.buttonRefresh.setIcon(self.icons["Refresh"])

    def constructRestOfUI(self):
        self.ui.lineSearch = ÆButtonLineEdit(self.icons)
        self.ui.lineSearch.setPlaceholderText('Search Files')
        self.ui.controlsGrid.addWidget(self.ui.lineSearch, 1, 1)

        self.ui.menuTable = QMenu()
        self.ui.menuTable.addActions((self.ui.actionSelectFile, self.ui.actionPreviewFile))
        seperator = QAction(self)
        seperator.setSeparator(True)
        self.ui.menuTable.addAction(seperator)
        self.ui.menuTable.addAction(self.ui.actionRefresh)

    def setDefaults(self):
        for itemType in self.config['itemTypes']:
            if not itemType.isWeblinks:
                self.treeModels[itemType.nounName] = ÆDataFolderModel(self, itemType.nounName)
        self.ui.labelDataDirVal.setText('<a href="{0}">{0}</a>'.format(self.dataDir))

    def exec_(self, itemType):
        self.goToItemType(itemType)
        super().exec_()

    def goToItemType(self, itemType=None):
        model = self.ui.typeList.model()
        if itemType not in ('', None):
            selectedItems = model.findItems(itemType, Qt.MatchExactly, 1)
            if selectedItems:
                itemTypeItem = selectedItems[0]
                index = model.indexFromItem(itemTypeItem)
                self.ui.typeList.setCurrentIndex(model.index(index.row(), 0))
        else:
            index = model.index(0, 0)
            self.ui.typeList.setCurrentIndex(index)

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

    def returnItemName(self):
        indexes = self.ui.itemsTree.selectedIndexes()
        if indexes:
            itemName = self.currentModel.items[indexes[0].row()][1]
            itemExt = self.currentModel.items[indexes[0].row()][5]
            itemNameExt = itemName+'.'+itemExt
            if itemNameExt is not None:
                return itemNameExt
        return None

    def onTypeListSelectionChanged(self):
        indexes = self.ui.typeList.selectedIndexes()
        if indexes:
            itemNounIndex = indexes[0].sibling(indexes[0].row(), 1)
            selectedItemNoun = indexes[0].model().itemFromIndex(itemNounIndex)
            if selectedItemNoun.data(0) is not None:
                self.logger.debug(selectedItemNoun.data(0))
                self.displayFolder(selectedItemNoun.data(0))

        self.ui.actionSelectFile.setEnabled(False)
        self.ui.actionPreviewFile.setEnabled(False)

    def onItemsTreeSelectionChanged(self, selection=None):
        data = self.returnItemName()
        self.logger.debug(data)
        self.ui.lineFileName.setText(data)

        if selection is None:
            self.ui.actionSelectFile.setEnabled(False)
            self.ui.actionPreviewFile.setEnabled(False)
        else:
            self.ui.actionSelectFile.setEnabled(True)
            self.ui.actionPreviewFile.setEnabled(True)

    def updateTreeModels(self):
        for itemType, model in self.treeModels.items():
            self.updateTreeModel(itemType, model)
        self.ui.itemsTree.sortByColumn(1, Qt.AscendingOrder)

    def updateTreeModel(self, itemType, model):
        model.clear()
        model.setItemType(itemType)

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

    def processData(self):
        itemName = self.ui.lineFileName.text()
        if itemName:
            self.selectedItemNameSignal.emit(itemName)
            self.close()

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
                subprocess.call(('open', getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName)))
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

    def itemsTreeContextMenu(self):
        self.ui.menuTable.exec_(QCursor().pos())

    def close(self):
        super().close()

    def deleteLater(self):
        for model in self.treeModels.values():
            model.deleteLater()
        super().deleteLater()