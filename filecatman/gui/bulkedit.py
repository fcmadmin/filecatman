import logging
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDialog, QMenu, QTreeView, QWidgetAction, QAbstractItemView
from filecatman.core.functions import loadUI
from filecatman.core.objects import ÆTaxonomy


class BulkEditDialog(QDialog):
    relationsModel, itemsModel = QStandardItemModel(), QStandardItemModel()
    dialogName = 'Bulk Edit Items'
    itemsUpdated = Signal()

    def __init__(self, parent, itemIdens):
        super(BulkEditDialog, self).__init__(parent)
        self.itemIdens = itemIdens
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.app = self.mainWindow.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/bulkedit.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(600)
        self.setWindowTitle(self.dialogName)

        self.setIcons()
        self.connectSignals()
        self.setDefaults()

    def setIcons(self):
        self.ui.tabWidget.setTabIcon(0, self.icons['Items'])
        self.ui.tabWidget.setTabIcon(1, self.icons['Relations'])
        self.ui.buttonAddRelation.setIcon(self.icons['Add'])
        self.ui.buttonRemoveRelation.setIcon(self.icons['Remove'])
        self.ui.buttonClearRelations.setIcon(self.icons['CheckNone'])
        self.ui.buttonRemoveItem.setIcon(self.icons['Remove'])

    def connectSignals(self):
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.buttonAddRelation.clicked.connect(self.openAddRelationDialog)
        self.ui.buttonRemoveRelation.clicked.connect(self.removeRelationFromTree)
        self.ui.buttonClearRelations.clicked.connect(self.clearRelationsFromTree)
        self.ui.buttonRemoveItem.clicked.connect(self.removeItemFromTree)

    def setDefaults(self):
        self.clearItemsFromTree()
        self.clearRelationsFromTree()
        self.ui.relationsTree.setModel(self.relationsModel)
        self.relationsModel.setHorizontalHeaderLabels(('', 'Taxonomy', 'Category'))
        self.ui.relationsTree.setColumnWidth(0, 100)
        self.ui.relationsTree.setColumnWidth(1, 200)
        self.ui.itemsTree.setModel(self.itemsModel)
        self.itemsModel.setHorizontalHeaderLabels(('Item Name',))
        for itemTuple in self.itemIdens:
            typeObj = self.config['itemTypes'][itemTuple[2]]
            itemName = QStandardItem(itemTuple[1])
            itemName.setData(itemTuple[0], Qt.UserRole)
            itemName.setIcon(self.icons[typeObj.iconName])
            self.itemsModel.appendRow((itemName,))
        self.updateItemsCount()

    def updateItemsCount(self):
        rowCount = self.itemsModel.rowCount()
        if rowCount is 1:
            self.ui.labelItemsCount.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.labelItemsCount.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.labelItemsCount.textFormat()

    def onRelationsTreeSelectionChanged(self):
        indexes = self.ui.relationsTree.selectedIndexes()
        if indexes:
            opName = self.relationsModel.data(indexes[0])
            opData = self.relationsModel.data(indexes[0], role=Qt.UserRole)
            taxNoun = self.relationsModel.data(indexes[1])
            taxTable = self.relationsModel.data(indexes[1], role=Qt.UserRole)
            catName = self.relationsModel.data(indexes[2])
            catIden = self.relationsModel.data(indexes[2], role=Qt.UserRole)

            self.logger.debug("{} {} {}".format(opName, taxNoun, catName))
            self.logger.debug("({} {} {})".format(opData, taxTable, catIden))

    def openAddRelationDialog(self):
        addRelationDialog = InsertOrDeleteRelationDialog(self)
        addRelationDialog.relationAdded.connect(self.addRelationToTree)
        addRelationDialog.exec_()
        addRelationDialog.deleteLater()

    def addRelationToTree(self, taxOpName, taxOp, tax, catName, cat):
        OpItem = QStandardItem(taxOpName)
        OpItem.setData(taxOp, Qt.UserRole)
        taxItem = QStandardItem(tax.nounName)
        taxItem.setData(tax.tableName, Qt.UserRole)
        taxItem.setIcon(self.icons[tax.iconName])
        catItem = QStandardItem(catName)
        catItem.setData(cat, Qt.UserRole)
        self.relationsModel.appendRow((OpItem, taxItem, catItem))

        try:
            selectionModel = self.ui.relationsTree.selectionModel()
            selectionModel.selectionChanged.connect(self.onRelationsTreeSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

    def removeRelationFromTree(self):
        index = self.ui.relationsTree.selectedIndexes()
        if index:
            category = index[2].data(0)
            self.logger.debug("`{}` was popped.".format(category))
            self.relationsModel.takeRow(index[0].row())

    def removeItemFromTree(self):
        index = self.ui.itemsTree.selectedIndexes()
        if index:
            category = index[0].data(0)
            self.logger.debug("`{}` was popped.".format(category))
            self.itemsModel.takeRow(index[0].row())
        self.updateItemsCount()

    def clearRelationsFromTree(self):
        self.relationsModel.removeRows(0, self.relationsModel.rowCount())

    def clearItemsFromTree(self):
        self.itemsModel.removeRows(0, self.itemsModel.rowCount())

    def processData(self):
        self.db.open()
        self.db.transaction()

        itemIdens = list()
        i = 0
        while self.itemsModel.item(i, 0):
            itemIden = self.itemsModel.data(self.itemsModel.index(i, 0), role=Qt.UserRole)
            itemIdens.append(itemIden)
            i += 1

        i = 0
        while self.relationsModel.item(i, 0):
            relationOp = self.relationsModel.data(self.relationsModel.index(i, 0), role=Qt.UserRole)
            taxonomy = self.relationsModel.data(self.relationsModel.index(i, 1), role=Qt.UserRole)
            categoryIden = self.relationsModel.data(self.relationsModel.index(i, 2), role=Qt.UserRole)
            self.logger.debug("({} {} {})".format(relationOp, taxonomy, categoryIden))

            if relationOp == "Insert":
                for itemIden in itemIdens:
                    self.db.newRelation({'item': itemIden, 'term': categoryIden})
            elif relationOp == "Delete":
                for itemIden in itemIdens:
                    relationExists = self.db.checkRelation(itemIden, categoryIden)
                    if relationExists:
                        self.db.deleteRelation(itemIden, categoryIden)
            i += 1

        self.db.commit()
        self.db.close()
        self.itemsUpdated.emit()
        self.close()


class InsertOrDeleteRelationDialog(QDialog):
    relationAdded = Signal(str, str, ÆTaxonomy, str, str)
    dialogName = "Insert or Delete Relation"
    selectedCategoryText = None

    def __init__(self, parent):
        super().__init__(parent.mainWindow)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent.mainWindow
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/addrelation.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(450)
        self.setWindowTitle(self.dialogName)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).setText("&Add")
        self.constructRestOfUi()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.comboTaxonomy.currentIndexChanged.connect(self.onComboTaxonomyIndexChanged)
        self.ui.categoryTree.clicked.connect(self.returnSelectedCategory)

        self.setDefaults()

    def constructRestOfUi(self):
        self.ui.buttonCategory.setMenu(QMenu(self.ui.buttonCategory))
        self.ui.categoryTree = QTreeView(self)
        self.ui.categoryTree.setHeaderHidden(True)
        self.ui.categoryTree.setEditTriggers(QAbstractItemView.NoEditTriggers)

        action = QWidgetAction(self.ui.buttonCategory)
        action.setDefaultWidget(self.ui.categoryTree)
        self.ui.buttonCategory.menu().addAction(action)

    def setDefaults(self):
        for taxonomy in self.config['taxonomies']:
            self.ui.comboTaxonomy.addItem(self.icons[taxonomy.iconName], taxonomy.nounName, taxonomy)
        self.ui.comboTaxonomy.setCurrentIndex(0)

        self.ui.comboTaxonomyOp.addItem("Insert", "Insert")
        self.ui.comboTaxonomyOp.addItem("Delete", "Delete")

    def onComboTaxonomyIndexChanged(self, index):
        itemTax = self.ui.comboTaxonomy.itemData(index)
        if itemTax:
            itemTax = itemTax.tableName
        itemName = self.ui.comboTaxonomy.itemText(index)
        self.logger.debug("Taxonomy Selected. Name: "+str(itemName)+" Tax: "+str(itemTax))
        self.displayCategories(itemTax)

    def displayCategories(self, taxonomy):
        if taxonomy in self.config['taxonomies'].tableNames():
            self.ui.buttonCategory.setEnabled(True)
            self.ui.labelCategory.setEnabled(True)
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            self.db.close()
            model = QStandardItemModel()
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                item = QStandardItem(categories[i]['name'])
                item.setData(categories[i]['id'], Qt.UserRole)
                lvlDifference = categories[i]['level'] - categories[i-1]['level']
                if categories[i]['level'] == 0:
                    model.appendRow((item,))
                elif lvlDifference > 0:
                    lastItem = model.itemFromIndex(lastIndex)
                    lastItem.appendRow((item,))
                elif lvlDifference == 0:
                    parentOfLastItem = model.itemFromIndex(lastIndex.parent())
                    parentOfLastItem.appendRow((item,))
                elif lvlDifference < 0:
                    currentIndex = lastIndex.parent()
                    ii = 0
                    while ii > lvlDifference:
                        currentIndex = currentIndex.parent()
                        ii -= 1
                    parentOfItem = model.itemFromIndex(currentIndex)
                    parentOfItem.appendRow((item,))
                lastIndex = model.indexFromItem(item)
                i += 1
            self.ui.categoryTree.setModel(model)

            catName = model.data(model.index(0, 0, QModelIndex()), role=Qt.DisplayRole)
            catIden = model.data(model.index(0, 0, QModelIndex()), role=Qt.UserRole)
            if catIden and catName:
                self.logger.debug(str(catIden)+': '+catName)
                self.ui.buttonCategory.setText(catName.replace("&", "&&"))
                self.selectedCategoryText = catName
                self.ui.buttonCategory.catIden = catIden
            else:
                self.ui.buttonCategory.setText(None)
                self.selectedCategoryText = None
                self.ui.buttonCategory.catIden = None
        else:
            self.ui.buttonCategory.setEnabled(False)
            self.ui.labelCategory.setEnabled(False)

    def returnSelectedCategory(self):
        indexes = self.ui.categoryTree.selectedIndexes()
        if indexes:
            catName = self.ui.categoryTree.model().data(indexes[0], role=Qt.DisplayRole)
            catIden = self.ui.categoryTree.model().data(indexes[0], role=Qt.UserRole)
            self.logger.debug(str(catIden)+': '+catName)
            self.ui.buttonCategory.setText(catName.replace("&", "&&"))
            self.ui.buttonCategory.catIden = catIden
            self.selectedCategoryText = catName
            self.ui.buttonCategory.menu().hide()

    def processData(self):
        itemTaxonomy = self.ui.comboTaxonomy.itemData(self.ui.comboTaxonomy.currentIndex())
        itemCategoryName = self.selectedCategoryText
        itemCategory = str(self.ui.buttonCategory.catIden)
        itemTaxonomyOpName = self.ui.comboTaxonomyOp.itemText(self.ui.comboTaxonomyOp.currentIndex())
        itemTaxonomyOp = self.ui.comboTaxonomyOp.itemData(self.ui.comboTaxonomyOp.currentIndex())

        if self.ui.buttonCategory.catIden:
            self.relationAdded.emit(
                itemTaxonomyOpName, itemTaxonomyOp, itemTaxonomy, itemCategoryName, itemCategory)

        self.close()