import logging
from urllib.parse import quote
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QMenu, QTreeView, QWidgetAction, QAbstractItemView
from PySide6.QtGui import QStandardItem, QStandardItemModel
from filecatman.core.functions import loadUI, æscape
from filecatman.core.objects import ÆTaxonomy


class AdvancedSearchDialog(QDialog):
    relationsModel = QStandardItemModel()
    dialogName = 'Advanced Search'
    sqlSignal = Signal(str)
    tableColumns = (('Name', 'item_name', æscape),
                    ('Source', 'item_source', quote),
                    ('Description', 'item_description', quote))
    
    def __init__(self, parent):
        super(AdvancedSearchDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.app = self.mainWindow.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = parent.db

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/advancedsearch.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(600)
        self.setWindowTitle(self.dialogName)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).setText("&Search")

        self.constructRestOfUi()
        self.setIcons()
        self.connectSignals()
        self.setDefaults()
        self.ui.lineKeywords.setFocus()

    def constructRestOfUi(self):
        self.ui.buttonCategory.setMenu(QMenu(self.ui.buttonCategory))
        self.ui.buttonCategory.catIden = None
        self.ui.categoryTree = QTreeView(self)
        self.ui.categoryTree.setHeaderHidden(True)
        self.ui.categoryTree.setEditTriggers(QAbstractItemView.NoEditTriggers)

        action = QWidgetAction(self.ui.buttonCategory)
        action.setDefaultWidget(self.ui.categoryTree)
        self.ui.buttonCategory.menu().addAction(action)

    def setIcons(self):
        self.ui.tabWidget.setTabIcon(0, self.icons['Search'])
        self.ui.tabWidget.setTabIcon(1, self.icons['Relations'])
        self.ui.buttonAddRelation.setIcon(self.icons['Add'])
        self.ui.buttonRemoveRelation.setIcon(self.icons['Remove'])
        self.ui.buttonClearRelations.setIcon(self.icons['CheckNone'])

    def connectSignals(self):
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Help).clicked.connect(self.openHelpBrowser)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processQuery)
        self.ui.comboTaxonomy.currentIndexChanged.connect(self.onComboTaxonomyIndexChanged)
        self.ui.comboType.currentIndexChanged.connect(self.onComboTypeIndexChanged)
        self.ui.comboField.currentIndexChanged.connect(self.onComboFieldIndexChanged)
        self.ui.comboDateType.currentIndexChanged.connect(self.onComboDateTypeIndexChanged)
        self.ui.buttonAddRelation.clicked.connect(self.openAddRelationDialog)
        self.ui.buttonRemoveRelation.clicked.connect(self.removeRelationFromTree)
        self.ui.buttonClearRelations.clicked.connect(self.clearRelationsFromTree)
        self.ui.categoryTree.clicked.connect(self.returnSelectedCategory)

    def openHelpBrowser(self):
        self.close()
        self.app.openHelpBrowser("advancedsearch.html")

    def setDefaults(self):
        self.clearRelationsFromTree()
        self.ui.relationsTree.setModel(self.relationsModel)
        self.relationsModel.setHorizontalHeaderLabels(('', 'Taxonomy', 'Category'))
        self.ui.relationsTree.setColumnWidth(0, 100)
        self.ui.relationsTree.setColumnWidth(1, 200)

        self.ui.comboTaxonomy.addItem('Any', None)
        for taxonomy in self.config['taxonomies']:
            self.ui.comboTaxonomy.addItem(self.icons[taxonomy.iconName], taxonomy.nounName, taxonomy.tableName)
        self.ui.comboTaxonomy.setCurrentIndex(0)

        self.ui.comboType.addItem('Any', None)
        for itemType in self.config['itemTypes']:
            self.ui.comboType.addItem(self.icons[itemType.iconName], itemType.nounName, itemType.tableName)

        self.ui.comboField.addItem('Any', None)
        for nounName, tableName, wordFunction in self.tableColumns:
            self.ui.comboField.addItem(nounName, tableName)

        self.ui.comboKeywordsOp.addItem("With", "")
        self.ui.comboKeywordsOp.addItem("Without", "NOT ")
        self.ui.comboTypeOp.addItem("With", "=")
        self.ui.comboTypeOp.addItem("Without", "<>")
        self.ui.comboTaxonomyOp.addItem("With", "IN")
        self.ui.comboTaxonomyOp.addItem("Without", "NOT IN")

        self.ui.comboDateOp.addItem("With", "true")
        self.ui.comboDateOp.addItem("Without", "false")
        self.ui.comboDateOp.addItem("Greater than", "greater")
        self.ui.comboDateOp.addItem("Less than", "less")
        self.ui.comboDateType.addItems(("Any date", "Date", "Date range", "Null date"))
        self.ui.comboKeywordsType.addItems(("Keywords", "Phrase"))

    def displayCategories(self, taxonomy):
        if taxonomy in self.config['taxonomies'].tableNames():
            model = QStandardItemModel()
            item = QStandardItem('Any')
            item.setData(None, Qt.UserRole)
            model.appendRow((item,))

            self.ui.buttonCategory.setEnabled(True)
            self.ui.labelCategory.setEnabled(True)
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            self.db.close()
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                item = QStandardItem(categories[i]['name'])
                item.setData(str(categories[i]['id']), Qt.UserRole)
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

            self.ui.buttonCategory.setText('Any')
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
            self.ui.buttonCategory.menu().hide()

    def onComboTypeIndexChanged(self, index):
        itemID = self.ui.comboType.itemData(index)
        itemName = self.ui.comboType.itemText(index)
        self.logger.debug("Item Type Changed. Name: "+str(itemName)+" ID: "+str(itemID))

    def onComboTaxonomyIndexChanged(self, index):
        itemTax = self.ui.comboTaxonomy.itemData(index)
        itemName = self.ui.comboTaxonomy.itemText(index)
        self.logger.debug("Taxonomy Selected. Name: "+str(itemName)+" Tax: "+str(itemTax))
        self.displayCategories(itemTax)

    def onComboCategoryIndexChanged(self, index):
        itemID = self.ui.comboCategory.itemData(index)
        itemName = self.ui.comboCategory.itemText(index)
        self.logger.debug("Category Selected. Name: "+str(itemName)+" ID: "+str(itemID))

    def onComboFieldIndexChanged(self, index):
        itemID = self.ui.comboField.itemData(index)
        itemName = self.ui.comboField.itemText(index)
        self.logger.debug("Column Field Changed. Name: "+str(itemName)+" ID: "+str(itemID))

    def onComboDateTypeIndexChanged(self, index):
        dateType = self.ui.comboDateType.itemText(index)
        self.logger.debug("Date Type Changed. Type: "+str(dateType))
        if dateType == "Any date":
            self.ui.labelDateRangeTo.setEnabled(False)
            self.ui.dateFrom.setEnabled(False)
            self.ui.dateTo.setEnabled(False)
        elif dateType == "Date range":
            self.ui.labelDateRangeTo.setEnabled(True)
            self.ui.dateFrom.setEnabled(True)
            self.ui.dateTo.setEnabled(True)
        elif dateType == "Date":
            self.ui.labelDateRangeTo.setEnabled(False)
            self.ui.dateFrom.setEnabled(True)
            self.ui.dateTo.setEnabled(False)
        elif dateType == "Null date":
            self.ui.labelDateRangeTo.setEnabled(False)
            self.ui.dateFrom.setEnabled(False)
            self.ui.dateTo.setEnabled(False)

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
        addRelationDialog = AddRelationToQueryDialog(self)
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

    def clearRelationsFromTree(self):
        self.relationsModel.removeRows(0, self.relationsModel.rowCount())

    def processQuery(self):
        SQLWhere = []
        SQLName = ''
        keywordsWhere = ''
        wordFunction = None

        itemKeywords = self.ui.lineKeywords.text()
        itemType = self.ui.comboType.itemData(self.ui.comboType.currentIndex())
        itemTaxonomy = self.ui.comboTaxonomy.itemData(self.ui.comboTaxonomy.currentIndex())
        itemCategory = self.ui.buttonCategory.catIden
        itemField = self.ui.comboField.itemData(self.ui.comboField.currentIndex())
        itemDateFrom = self.ui.dateFrom.date().toString("yyyy-MM-dd")+" 00:00:00"
        itemDateTo = self.ui.dateTo.date().toString("yyyy-MM-dd")+" 00:00:00"

        itemKeywordsType = self.ui.comboKeywordsType.itemText(self.ui.comboKeywordsType.currentIndex())
        itemDateType = self.ui.comboDateType.itemText(self.ui.comboDateType.currentIndex())
        itemKeywordsOp = self.ui.comboKeywordsOp.itemData(self.ui.comboKeywordsOp.currentIndex())
        itemTypeOp = self.ui.comboTypeOp.itemData(self.ui.comboTypeOp.currentIndex())
        itemTaxonomyOp = self.ui.comboTaxonomyOp.itemData(self.ui.comboTaxonomyOp.currentIndex())
        itemDateOp = self.ui.comboDateOp.itemData(self.ui.comboDateOp.currentIndex())

        if not itemKeywords.strip() == '':
            if itemField:
                for index, col in enumerate([tup[1] for tup in self.tableColumns]):
                    if col == itemField:
                        wordFunction = self.tableColumns[index][2]
                        break
                if itemKeywordsType == "Keywords":
                    i = 0
                    for word in itemKeywords.split():
                        i += 1
                        if i is 1:
                            SQLName += "({0} LIKE '%{1}%'".format(itemField, wordFunction(word))
                        else:
                            SQLName += " AND {0} LIKE '%{1}%'".format(itemField, wordFunction(word))

                elif itemKeywordsType == "Phrase":
                    SQLName += "({0} LIKE '%{1}%'".format(itemField, wordFunction(itemKeywords))
                SQLName += ") \n"
                SQLWhere.append("{}".format(itemKeywordsOp)+SQLName)
            else:
                fieldsWhere = list()
                for nounName, col, wordFunction in self.tableColumns:
                    if itemKeywordsType == "Keywords":
                        i = 0
                        for word in itemKeywords.split():
                            i += 1
                            if i is 1:
                                keywordsWhere = "({0} LIKE '%{1}%'".format(col, wordFunction(word))
                            else:
                                keywordsWhere += " AND {0} LIKE '%{1}%'".format(col, wordFunction(word))
                    elif itemKeywordsType == "Phrase":
                        keywordsWhere = "({0} LIKE '%{1}%'".format(col, wordFunction(itemKeywords))
                    keywordsWhere += ") \n"
                    fieldsWhere.append(keywordsWhere)
                SQLName = "("+" OR ".join(fieldsWhere)+")"
                SQLWhere.append("{}".format(itemKeywordsOp)+SQLName)

        if itemType:
            SQLWhere.append("( i.type_id {0} '{1}' )".format(itemTypeOp, itemType))

        if not itemDateType == "Any date":
            if itemDateType == "Date":
                dateOp = dict(true="=", false="<>", greater=">", less="<")[itemDateOp]
                SQLWhere.append("( item_time {0} '{1}' )".format(dateOp, itemDateFrom))
            elif itemDateType == "Date range":
                dateOp = dict(true="BETWEEN", false="NOT BETWEEN", greater=">", less="<")[itemDateOp]
                SQLWhere.append("( item_time {0} '{1}' AND '{2}' )".format(dateOp, itemDateFrom, itemDateTo))
            elif itemDateType == "Null date":
                dateOp = dict(true="=", false="<>", greater=">", less="<")[itemDateOp]
                SQLWhere.append("( item_time {0} '0000-00-00 00:00:00' )".format(dateOp))

        if itemTaxonomy:
            SQLTaxonomy = "SELECT tr.item_id \n" \
                          "FROM term_relationships AS tr \n" \
                          "INNER JOIN terms AS t ON (t.term_id = tr.term_id) \n" \
                          "WHERE ( t.term_taxonomy = '{}' )".format(itemTaxonomy)
            if itemCategory:
                SQLTaxonomy += " AND ( tr.term_id = '{0}' )".format(itemCategory)
            SQLWhere.append("( i.item_id {0} (\n{1}\n) )".format(itemTaxonomyOp, SQLTaxonomy))

        i = 0
        while self.relationsModel.item(i, 0):
            taxonomyOp = self.relationsModel.data(self.relationsModel.index(i, 0), role=Qt.UserRole)
            taxonomy = self.relationsModel.data(self.relationsModel.index(i, 1), role=Qt.UserRole)
            categoryIden = self.relationsModel.data(self.relationsModel.index(i, 2), role=Qt.UserRole)
            self.logger.debug("({} {} {})".format(taxonomyOp, taxonomy, categoryIden))

            SQLTaxonomy = "SELECT tr.item_id \n" \
                          "FROM term_relationships AS tr \n" \
                          "INNER JOIN terms AS t ON (t.term_id = tr.term_id) \n" \
                          "WHERE ( t.term_taxonomy = '{}' )".format(taxonomy)
            if not categoryIden in (None, ''):
                SQLTaxonomy += " AND ( tr.term_id = '{0}' )".format(categoryIden)
            SQLWhere.append("( i.item_id {0} (\n{1}\n) )".format(taxonomyOp, SQLTaxonomy))

            i += 1

        if len(SQLWhere) > 0:
            whereJoined = "\nWHERE "+" AND \n".join(SQLWhere)
        else:
            whereJoined = ''
        SQL = "SELECT DISTINCT i.item_id AS 'ID', item_name AS 'Name', \n" \
              "type_id AS 'Type', item_time AS 'Time', item_source AS 'Source' \n" \
              "FROM items AS i {} \n" \
              "ORDER BY i.item_id ASC".format(whereJoined)
        self.sqlSignal.emit(SQL)
        self.close()


class AddRelationToQueryDialog(QDialog):
    relationAdded = Signal(str, str, ÆTaxonomy, str, str)
    dialogName = "Add Relation to Query"
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
        self.ui.comboTaxonomy.addItem('Any', None)
        for taxonomy in self.config['taxonomies']:
            self.ui.comboTaxonomy.addItem(self.icons[taxonomy.iconName], taxonomy.nounName, taxonomy)
        self.ui.comboTaxonomy.setCurrentIndex(0)

        self.ui.comboTaxonomyOp.addItem("With", "IN")
        self.ui.comboTaxonomyOp.addItem("Without", "NOT IN")

    def onComboTaxonomyIndexChanged(self, index):
        itemTax = self.ui.comboTaxonomy.itemData(index)
        if itemTax:
            itemTax = itemTax.tableName
        itemName = self.ui.comboTaxonomy.itemText(index)
        self.logger.debug("Taxonomy Selected. Name: "+str(itemName)+" Tax: "+str(itemTax))
        self.displayCategories(itemTax)

    def displayCategories(self, taxonomy):
        if taxonomy in self.config['taxonomies'].tableNames():
            model = QStandardItemModel()
            item = QStandardItem('Any')
            item.setData(None, Qt.UserRole)
            model.appendRow((item,))

            self.ui.buttonCategory.setEnabled(True)
            self.ui.labelCategory.setEnabled(True)
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            self.db.close()
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                item = QStandardItem(categories[i]['name'])
                item.setData(str(categories[i]['id']), Qt.UserRole)
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

            self.ui.buttonCategory.setText('Any')
            self.selectedCategoryText = 'Any'
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
            self.selectedCategoryText = catName
            self.ui.buttonCategory.catIden = catIden
            self.ui.buttonCategory.menu().hide()

    def processData(self):
        itemTaxonomy = self.ui.comboTaxonomy.itemData(self.ui.comboTaxonomy.currentIndex())
        itemCategoryName = self.selectedCategoryText
        itemCategory = self.ui.buttonCategory.catIden
        itemTaxonomyOpName = self.ui.comboTaxonomyOp.itemText(self.ui.comboTaxonomyOp.currentIndex())
        itemTaxonomyOp = self.ui.comboTaxonomyOp.itemData(self.ui.comboTaxonomyOp.currentIndex())

        if itemCategoryName:
            self.relationAdded.emit(
                itemTaxonomyOpName, itemTaxonomyOp, itemTaxonomy, itemCategoryName, itemCategory)

        self.close()