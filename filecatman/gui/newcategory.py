import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QDialog, QMenu, QTreeView, QWidgetAction, QAbstractItemView
from filecatman.core.objects import Æ
from filecatman.core.functions import loadUI, æscape, warningMsgBox


class NewCategoryDialog(QDialog):
    newCategory = None
    appName = "New Category"
    categoryInserted = Signal()

    def __init__(self, parent):
        super(NewCategoryDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.app = parent.app
        self.config = parent.config
        self.icons = parent.icons
        self.db = parent.db
        self.logger.info(self.appName+" Dialog Opened")
        self.ui = loadUI("gui/ui/newcategory.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(600, 300)
        self.setWindowTitle(self.appName)

        self.ui.tabWidget.setTabIcon(0, self.icons['DetailsEdit'])
        self.constructRestOfUi()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Help).clicked.connect(self.openHelpBrowser)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.comboTaxonomy.currentIndexChanged.connect(self.onComboTaxonomyIndexChanged)
        self.ui.categoryTree.clicked.connect(self.returnSelectedCategory)

        self.setDefaults()
        self.displayParents(self.config['taxonomies'].tableNames()[0])
        self.ui.lineName.setFocus()
        
    def constructRestOfUi(self):
        self.ui.buttonParent.setMenu(QMenu(self.ui.buttonParent))
        self.ui.buttonParent.catIden = None
        self.ui.categoryTree = QTreeView(self)
        self.ui.categoryTree.setHeaderHidden(True)
        self.ui.categoryTree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.categoryTree.setMinimumWidth(400)
        action = QWidgetAction(self.ui.buttonParent)
        action.setDefaultWidget(self.ui.categoryTree)
        self.ui.buttonParent.menu().addAction(action)

    def openHelpBrowser(self):
        self.close()
        self.app.openHelpBrowser("newcategory.html")

    def setDefaults(self):
        for taxonomy in self.config['taxonomies']:
            self.ui.comboTaxonomy.addItem(self.icons[taxonomy.iconName], taxonomy.nounName, taxonomy.tableName)
        self.ui.comboTaxonomy.setCurrentIndex(0)

    def displayParents(self, taxonomy):
        if taxonomy not in self.config['taxonomies'].tableNames(Æ.NoChildren):
            model = QStandardItemModel()
            item = QStandardItem('— No Parent —')
            item.setData(None, Qt.UserRole)
            model.appendRow((item,))

            self.ui.buttonParent.setEnabled(True)
            self.ui.labelParent.setEnabled(True)
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            self.db.close()
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                if categories[i]['level'] == self.config['options']['catLvls']:
                    categories.pop(i)
                    continue
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
        else:
            self.ui.buttonParent.setEnabled(False)
            self.ui.labelParent.setEnabled(False)
        self.ui.buttonParent.setText('— No Parent —')
        self.ui.buttonParent.catIden = None

    def onComboTaxonomyIndexChanged(self, index):
        itemTax = self.ui.comboTaxonomy.itemData(index)
        itemName = self.ui.comboTaxonomy.itemText(index)
        self.logger.debug("Taxonomy Selected. Name: "+str(itemName)+" Tax: "+str(itemTax))
        self.displayParents(itemTax)
        
    def returnSelectedCategory(self):
        indexes = self.ui.categoryTree.selectedIndexes()
        if indexes:
            catName = self.ui.categoryTree.model().data(indexes[0], role=Qt.DisplayRole)
            catIden = self.ui.categoryTree.model().data(indexes[0], role=Qt.UserRole)
            self.logger.debug(str(catIden)+': '+catName)
            self.ui.buttonParent.setText(catName.replace("&", "&&"))
            self.ui.buttonParent.catIden = catIden
            self.ui.buttonParent.menu().hide()

    def processData(self):
        if self.ui.lineName.text() == "":
            warningMsgBox(self.parent, "Name field is missing.", "Name Missing")
            self.ui.labelName.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Name: </span></p>')
            self.ui.labelName.textFormat()
            self.ui.lineName.setFocus()
        else:
            data = dict()
            data['name'] = æscape(self.ui.lineName.text())
            data['slug'] = self.ui.lineSlug.text()
            data['taxonomy'] = self.ui.comboTaxonomy.itemData(self.ui.comboTaxonomy.currentIndex())
            data['parent'] = self.ui.buttonParent.catIden
            data['description'] = self.ui.textDescription.toPlainText()

            self.db.open()
            self.db.transaction(debug=True)
            self.newCategory = self.db.newCategory(data)
            self.db.commit()
            self.db.close()
            self.categoryInserted.emit()
            self.close()