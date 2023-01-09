import csv
import os
import logging
from urllib.parse import quote
from PySide6.QtCore import Signal, Qt, QDate, QTime, QDir, QFile, QIODevice
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QMenu, QTreeView, QAbstractItemView, QWidgetAction,QDialogButtonBox
from filecatman.core.namespace import Æ
from filecatman.core.functions import loadUI, warningMsgBox, uploadFile, getDataFilePath, æscape
from filecatman.core.objects import ÆCompleterLineEdit, ÆTagsCompleter
from filecatman.gui import SelectFileDialog, RenameFileDialog


class NewItemDialog(QDialog):
    newItem, newCategory, selectFileDialog = None, None, None
    treeModels, listModels = dict(), dict()
    completerTagsList = list()
    appName = 'New Item'
    itemInserted = Signal()
    
    def __init__(self, parent):
        super(NewItemDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.app = parent.app
        self.config = parent.config
        self.icons = parent.icons
        self.db = parent.db

        self.logger.info(self.appName+" Dialog Opened")
        self.ui = loadUI("gui/ui/newitem.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(600, 300)
        self.setWindowTitle(self.appName)
        self.constructRestOfUi()

        self.ui.tabWidget.setTabIcon(0, parent.icons['DetailsEdit'])
        self.ui.tabWidget.setTabIcon(1, parent.icons['RelationsEdit'])
        self.ui.buttonAddCat.setIcon(parent.icons['Add'])
        self.ui.buttonAddTag.setIcon(parent.icons['Add'])
        self.ui.buttonRemoveTag.setIcon(parent.icons['Remove'])
        # QDialogButtonBox.StandardButton.Ok
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Help).clicked.connect(self.openHelpBrowser)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.checkNoDate.stateChanged.connect(self.toggleDate)
        self.ui.buttonAddTag.clicked.connect(self.addTags)
        self.ui.buttonRemoveTag.clicked.connect(self.removeSelectedTag)
        self.ui.termsTree.doubleClicked.connect(self.checkSelectedItem)
        self.ui.comboType.currentIndexChanged.connect(self.onComboTypeIndexChanged)
        self.ui.buttonAddCat.clicked.connect(self.insertNewCategory)
        self.ui.buttonBrowse.clicked.connect(self.openFileDialog)
        self.ui.buttonUpload.clicked.connect(self.uploadFileDialog)
        self.ui.buttonRename.clicked.connect(self.renameFile)
        self.ui.categoryTree.clicked.connect(self.returnSelectedCategory)
        self.ui.lineAdd.textChangedSig.connect(self.ui.lineAddCompleter.update)
        self.ui.lineAddCompleter.activated.connect(self.ui.lineAdd.completeText)

        self.setDefaults()
        self.createTreeModels()
        firstTaxonomy = self.config['taxonomies'][0]
        if firstTaxonomy.isTags:
            self.displayTags(firstTaxonomy.tableName)
        else:
            self.displayRelations(firstTaxonomy.tableName)
            self.displayParents(firstTaxonomy.tableName)
        self.ui.comboType.setFocus()

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

        self.ui.lineAdd = ÆCompleterLineEdit()
        self.ui.lineAdd.setPlaceholderText("Seperate with commas.")
        self.ui.gridLayout.addWidget(self.ui.lineAdd, 1, 0, 1, 2)

        self.ui.lineAddCompleter = ÆTagsCompleter(self.ui.lineAdd, self.completerTagsList)
        self.ui.lineAddCompleter.setCaseSensitivity(Qt.CaseInsensitive)
        self.ui.lineAddCompleter.setWidget(self.ui.lineAdd)

    def openHelpBrowser(self):
        self.close()
        self.app.openHelpBrowser("featuresanddialogs.html#newitem")

    def setDefaults(self):
        for taxonomy in self.config['taxonomies'].tableNames(Æ.NoTags):
            self.treeModels[taxonomy] = QStandardItemModel()

        for taxonomy in self.config['taxonomies'].tableNames(Æ.IsTags):
            self.listModels[taxonomy] = QStandardItemModel()

        self.ui.dateEdit.setDisplayFormat("yyyy-MM-dd")
        self.ui.dateEdit.setDate(QDate().currentDate())
        self.ui.timeEdit.setTime(QTime().currentTime())

        for itemType in self.config['itemTypes']:
            self.ui.comboType.addItem(self.icons[itemType.iconName], itemType.nounName, itemType.tableName)

        menuSIM = QStandardItemModel()
        for taxonomy in self.config['taxonomies']:
            item = QStandardItem(taxonomy.pluralName)
            item.setIcon(self.icons[taxonomy.iconName])
            typeID = QStandardItem(taxonomy.tableName)
            menuSIM.appendRow((item, typeID))
        self.ui.taxList.setModel(menuSIM)
        index = self.ui.taxList.model().index(0, 0)
        self.ui.taxList.setCurrentIndex(index)

        selectionModel = self.ui.taxList.selectionModel()
        selectionModel.selectionChanged.connect(self.onTaxListSelectionChanged, Qt.UniqueConnection)

    def onTaxListSelectionChanged(self):
        index = self.ui.taxList.selectedIndexes()[0]
        selectedItem = index.model().itemFromIndex(index)
        if selectedItem.data(0) is not None:
            if selectedItem.data(0) in self.config['taxonomies'].pluralNames(Æ.NoTags):
                tableName = self.config['taxonomies'].tableFromPlural(selectedItem.data(0))
                self.displayRelations(tableName)
                self.displayParents(tableName)
                self.logger.debug("You Selected "+selectedItem.data(0))
            elif selectedItem.data(0) in self.config['taxonomies'].pluralNames(Æ.IsTags):
                tableName = self.config['taxonomies'].tableFromPlural(selectedItem.data(0))
                self.displayTags(tableName)
                self.logger.debug("You Selected "+selectedItem.data(0))

    def createTreeModels(self):
        for taxonomy, model in self.treeModels.items():
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            self.db.close()
            model.clear()
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                item = QStandardItem(categories[i]['name'])
                itemID = QStandardItem(str(categories[i]['id']))
                item.setCheckable(True)
                lvlDifference = categories[i]['level'] - categories[i-1]['level']
                if categories[i]['level'] == 0:
                    model.appendRow((item, itemID))
                elif lvlDifference > 0:
                    lastItem = model.itemFromIndex(lastIndex)
                    lastItem.appendRow((item, itemID))
                elif lvlDifference == 0:
                    parentOfLastItem = model.itemFromIndex(lastIndex.parent())
                    parentOfLastItem.appendRow((item, itemID))
                elif lvlDifference < 0:
                    currentIndex = lastIndex.parent()
                    ii = 0
                    while ii > lvlDifference:
                        currentIndex = currentIndex.parent()
                        ii -= 1
                    parentOfItem = model.itemFromIndex(currentIndex)
                    parentOfItem.appendRow((item, itemID))
                lastIndex = model.indexFromItem(item)
                i += 1

    def displayRelations(self, taxonomy):
        self.ui.stackedWidget.setCurrentIndex(0)

        self.ui.termsTree.setModel(self.treeModels[taxonomy])
        #self.ui.termsTree.expandAll()
        self.ui.termsTree.setHeaderHidden(True)
        self.ui.termsTree.header().hideSection(1)

        index = self.ui.termsTree.model().index(0, 0)
        self.ui.termsTree.setCurrentIndex(index)

        try:
            selectionModel = self.ui.termsTree.selectionModel()
            selectionModel.selectionChanged.connect(self.onTermsTreeSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

    def displayTags(self, taxonomy):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.ui.tagList.setModel(self.listModels[taxonomy])
        self.ui.lineAdd.clear()

        self.completerTagsList.clear()
        self.db.open()
        taxonomyList = self.db.selectCategories(dict(term_taxonomy=taxonomy, col="term_name"))
        while taxonomyList.next():
            nameIndex = taxonomyList.record().indexOf("term_name")
            nameValue = taxonomyList.value(nameIndex)
            self.completerTagsList.append(str(nameValue))
        self.db.close()

        self.ui.lineAddCompleter.all_tags = set(self.completerTagsList)

    def displayParents(self, taxonomy):
        if taxonomy not in self.config['taxonomies'].tableNames(Æ.NoChildren):
            model = QStandardItemModel()
            item = QStandardItem('— No Parent —')
            item.setData(None, Qt.UserRole)
            model.appendRow((item,))

            self.ui.buttonParent.setEnabled(True)
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
        self.ui.buttonParent.setText('— No Parent —')
        self.ui.buttonParent.catIden = None

    def returnSelectedCategory(self):
        indexes = self.ui.categoryTree.selectedIndexes()
        if indexes:
            catName = self.ui.categoryTree.model().data(indexes[0], role=Qt.DisplayRole)
            catIden = self.ui.categoryTree.model().data(indexes[0], role=Qt.UserRole)
            self.logger.debug(str(catIden)+': '+catName)
            self.ui.buttonParent.setText(catName.replace("&", "&&"))
            self.ui.buttonParent.catIden = catIden
            self.ui.buttonParent.menu().hide()

    def onComboTypeIndexChanged(self, index):
        itemID = self.ui.comboType.itemData(index)
        itemName = self.ui.comboType.itemText(index)
        self.logger.debug("Item Type Changed. Name: "+itemName+" ID: "+itemID)
        if itemName in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
            self.ui.labelName.setText('<html><head/><body><p>'
                                      '<span style=" font-weight:600;">Name:</span>'
                                      '</p></body></html>')
            self.ui.buttonUpload.setEnabled(False)
            self.ui.buttonBrowse.setEnabled(False)
            self.ui.buttonRename.setEnabled(False)
            self.ui.lineName.setReadOnly(False)
            self.ui.lineName.clear()
            self.ui.lineName.setEnabled(True)
            self.ui.lineName.setPlaceholderText("Type a name for the link.")
        else:
            self.ui.labelName.setText('<html><head/><body><p>'
                                      '<span style=" font-weight:600;">File:</span>'
                                      '</p></body></html>')
            self.ui.buttonUpload.setEnabled(True)
            self.ui.buttonBrowse.setEnabled(True)
            self.ui.buttonRename.setEnabled(True)
            self.ui.lineName.setReadOnly(True)
            self.ui.lineName.clear()
            self.ui.lineName.setEnabled(True)
            self.ui.lineName.setPlaceholderText("Browse for existing file or upload a new file.")
            self.ui.labelSource.setText(
                '<p><span style="font-weight:600;">Source: </span></p>')

    def insertNewCategory(self):
        if self.ui.lineAddCat.text() == "":
            warningMsgBox(self.parent, "One or more fields are missing.", "Field Missing")
            self.ui.lineAddCat.setFocus()
        else:
            newCategoryData = dict()
            newCategoryData['name'] = æscape(self.ui.lineAddCat.text())
            newCategoryData['parent'] = self.ui.buttonParent.catIden
            index = self.ui.taxList.selectedIndexes()[0]
            indexID = self.ui.taxList.model().index(index.row(), 1)
            newCategoryData['taxonomy'] = indexID.model().itemFromIndex(indexID).data(0)
            self.logger.debug(str(newCategoryData))

            self.db.open()
            itWasCreated = self.db.newCategory(newCategoryData)
            self.db.close()
            if itWasCreated:
                model = self.treeModels[newCategoryData['taxonomy']]
                itemName = QStandardItem(newCategoryData['name'])
                itemName.setCheckable(True)
                itemName.setCheckState(Qt.Checked)
                itemID = QStandardItem(str(self.db.lastInsertId))
                if newCategoryData['parent'] not in ('', None, 'NULL'):
                    i = 0
                    while model.item(i):
                        curItemName = model.item(i)
                        curItemID = model.item(i, 1)
                        if curItemID.data(0) == str(newCategoryData['parent']):
                            ii = 0
                            itemAlreadyExists = None
                            while curItemName.child(ii):
                                self.logger.debug("Searching item name: "+curItemName.child(ii).data(0) +
                                                  " Name: "+itemName.data(0))
                                if curItemName.child(ii).data(0) == itemName.data(0):
                                    itemAlreadyExists = curItemName.child(ii)
                                    self.logger.info("Item already exists")
                                    break
                                ii += 1
                            if not itemAlreadyExists:
                                curItemName.appendRow((itemName, itemID))
                            else:
                                itemAlreadyExists.setCheckState(Qt.Checked)
                            #self.ui.termsTree.expandAll()
                            break
                        else:
                            self.iterateTermsTreeForParent(model, curItemName, newCategoryData['parent'],
                                                           itemName, itemID)
                        i += 1
                else:
                    itemAlreadyExists = self.ui.termsTree.model().findItems(
                        newCategoryData['name'], Qt.MatchExactly, 0)
                    if not itemAlreadyExists:
                        model.insertRow(0, (itemName, itemID))
                    else:
                        self.logger.info("Item already exists")
                        itemAlreadyExists[0].setCheckState(Qt.Checked)
                self.displayParents(newCategoryData['taxonomy'])
                self.displayRelations(newCategoryData['taxonomy'])
                self.ui.lineAddCat.clear()

    def iterateTermsTreeForParent(self, model, item, parent, itemName, itemID):
        if item.hasChildren():
            i = 0
            while item.child(i):
                curItemName = item.child(i)
                curItemID = item.child(i, 1)
                if curItemID.data(0) == str(parent):
                    ii = 0
                    itemAlreadyExists = None
                    while curItemName.child(ii):
                        self.logger.debug("Searching item name: "+curItemName.child(ii).data(0)+" Name: " +
                                          itemName.data(0))
                        if curItemName.child(ii).data(0) == itemName.data(0):
                            itemAlreadyExists = curItemName.child(ii)
                            self.logger.info("Item already exists")
                            break
                        ii += 1
                    if not itemAlreadyExists:
                        curItemName.appendRow((itemName, itemID))
                    else:
                        itemAlreadyExists.setCheckState(Qt.Checked)
                    #self.ui.termsTree.expandAll()
                    break
                else:
                    self.iterateTermsTreeForParent(model, curItemName, parent, itemName, itemID)
                i += 1

    def removeSelectedTag(self):
        indexes = self.ui.tagList.selectedIndexes()
        if indexes:
            index = indexes[0]
            itemRemoved = self.ui.tagList.model().takeRow(index.row())
            self.logger.debug(itemRemoved[0].data(0)+" was popped.")

    def addTags(self):
        lineEditText = self.ui.lineAdd.text()

        reader = csv.reader([lineEditText], skipinitialspace=True)
        for tags in reader:
            for tag in tags:
                tag = æscape(tag)
                if not self.ui.tagList.model().findItems(tag, Qt.MatchExactly):
                    if not tag == "":
                        self.ui.tagList.model().appendRow(QStandardItem(tag))
                        self.logger.debug(tag)

        self.ui.lineAdd.clear()

    def onTermsTreeSelectionChanged(self, selection):
        try:
            index = selection.indexes()[0]
            idIndex = index.sibling(index.row(), 1)
            categoryID = index.model().itemFromIndex(idIndex).data(0)
            self.logger.debug('ID: '+categoryID)
            self.logger.debug("Row: "+str(index.row())+" Column: "+str(index.column()) +
                              " Parent: "+str(index.parent().row()))
            selectedItem = index.model().itemFromIndex(index)
            checkState = selectedItem.checkState()
            if checkState is Qt.Unchecked:
                self.logger.debug(selectedItem.data(0)+" is checked")
            elif checkState is Qt.Checked:
                self.logger.debug(selectedItem.data(0)+" is not checked")
        except IndexError:
            self.logger.debug("Terms tree closed.")

    def checkSelectedItem(self):
        index = self.ui.termsTree.selectedIndexes()[0]
        selectedItem = index.model().itemFromIndex(index)
        if selectedItem.checkState() is Qt.Unchecked:
            selectedItem.setCheckState(Qt.Checked)
        else:
            selectedItem.setCheckState(Qt.Unchecked)

    def toggleDate(self):
        if self.ui.checkNoDate.isChecked() is True:
            self.ui.dateEdit.setEnabled(False)
            self.ui.timeEdit.setEnabled(False)
        else:
            self.ui.dateEdit.setEnabled(True)
            self.ui.timeEdit.setEnabled(True)

    def processData(self):
        data = dict()
        data['name'] = æscape(self.ui.lineName.text())
        data['type'] = self.ui.comboType.itemData(self.ui.comboType.currentIndex())
        data['source'] = self.ui.lineSource.text()
        if self.ui.checkNoDate.isChecked() is False:
            data['date'] = self.ui.dateEdit.text()
            data['time'] = self.ui.timeEdit.text()
        data['description'] = self.ui.textDescription.toPlainText()

        if data['name'] == "":
            warningMsgBox(self.parent, "One or more fields are missing.", "Field Missing")
            if data['type'] in self.config['itemTypes'].tableNames(Æ.IsWeblinks):
                self.ui.labelName.setText(
                    '<p><span style="font-weight:600;"><span style="color:red;">*</span> Name: </span></p>')
            else:
                self.ui.labelName.setText(
                    '<p><span style="font-weight:600;"><span style="color:red;">*</span> File: </span></p>')
            self.ui.labelName.textFormat()
            self.ui.lineName.setFocus()
            self.ui.tabWidget.setCurrentIndex(0)
        elif data['type'] in self.config['itemTypes'].tableNames(Æ.IsWeblinks) and data['source'] == "":
            warningMsgBox(self.parent, "One or more fields are missing.", "Field Missing")
            self.ui.labelSource.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Source: </span></p>')
            self.ui.labelSource.textFormat()
            self.ui.lineSource.setFocus()
            self.ui.tabWidget.setCurrentIndex(0)
        elif "'" in data['name']:
            warningMsgBox(
                self.parent,
                "Name field contains an illegal character. Single dumb quotations ('') conflict with SQL querying. "
                "Use smart quotations (‘’) instead.", "Illegal Character")
            self.ui.lineName.setFocus()
            self.ui.tabWidget.setCurrentIndex(0)
        else:
            self.db.open()
            self.db.transaction(debug=True)
            self.db.newItem(data)
            if self.db.lastInsertId:
                self.processRelations(self.db.lastInsertId)
            else:
                warningMsgBox(self, "Unable to insert item. Already exists in database.", "Item Already Exists")
            self.db.commit()
            self.db.close()
            self.itemInserted.emit()
            self.close()

    def processRelations(self, itemID):
        for modelName, model in self.treeModels.items():
            i = 0
            while model.item(i):
                item = model.item(i)
                if item.checkState() == Qt.Checked:
                    itemIndex = item.index()
                    idIndex = itemIndex.sibling(itemIndex.row(), 1)
                    categoryID = model.itemFromIndex(idIndex).data(0)
                    self.logger.debug(item.data(0)+" is checked. ID: "+categoryID)
                    self.db.newRelation({'item': itemID, 'term': categoryID})
                self.itemIterator(model, itemID, item)
                i += 1

        for modelName, model in self.listModels.items():
            i = 0
            while model.item(i):
                item = model.item(i)
                self.db.newCategory({'name': item.text(), 'taxonomy': modelName}, {'replace': True})
                self.db.newRelation({'item': itemID, 'term': self.db.lastInsertId})
                i += 1

                self.logger.debug("Tag to be inserted: "+item.text())

    def itemIterator(self, model, itemID, item):
        if item.hasChildren():
            i = 0
            while item.child(i):
                childItem = item.child(i)
                if childItem.checkState() == Qt.Checked:
                    itemIndex = childItem.index()
                    idIndex = itemIndex.sibling(itemIndex.row(), 1)
                    categoryID = model.itemFromIndex(idIndex).data(0)
                    self.logger.debug(childItem.data(0)+" is checked. ID: "+categoryID)
                    self.db.newRelation({'item': itemID, 'term': categoryID})
                self.itemIterator(model, itemID, childItem)
                i += 1

    def openFileDialog(self):
        itemType = self.ui.comboType.currentText()
        if not self.selectFileDialog:
            self.selectFileDialog = SelectFileDialog(self.parent)
            self.selectFileDialog.selectedItemNameSignal.connect(self.processFileName)
        self.selectFileDialog.exec_(itemType)

    def processFileName(self, fileName):
        if fileName:
            baseFilename = os.path.basename(fileName)
            self.logger.debug(baseFilename)
            for illegal in ("'", '"', '`', '$'):
                if illegal in baseFilename:
                    warningMsgBox(
                        self.parent,
                        "File name contains an illegal character [{}]. Please rename in file manager.".format(illegal),
                        "Illegal Character")
                    break
            else:
                fileExtension = os.path.splitext(fileName)[1][1:].lower().strip()
                fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
                if fileType:
                    typeIndex = self.ui.comboType.findText(fileType)
                    self.ui.comboType.setCurrentIndex(typeIndex)

                self.ui.lineName.setText(baseFilename)

    def uploadFileDialog(self):
        dataDir = self.config['options']['defaultDataDir']
        fileDialog = QFileDialog(self.parent)
        fileObj = fileDialog.getOpenFileName(None, "Upload a New file", dir=QDir().homePath())
        fileDialog.deleteLater()
        fileSource = fileObj[0]
        try:
            if fileSource:
                baseFilename = os.path.basename(fileSource)
                fileName = os.path.splitext(baseFilename)[0]
                fileExtension = os.path.splitext(fileSource)[1][1:].lower().strip()
                baseFilename = fileName+'.'+str(fileExtension)
                self.logger.debug(baseFilename)
                fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
                if fileType:
                    typeIndex = self.ui.comboType.findText(fileType)
                    self.ui.comboType.setCurrentIndex(typeIndex)
                    dirType = self.config['itemTypes'].dirFromNoun(fileType)
                    fileDestination = getDataFilePath(dataDir, dirType, baseFilename)
                    if not os.path.exists(getDataFilePath(dataDir, dirType, æscape(baseFilename))):
                        if uploadFile(self.parent, fileSource, fileDestination, fileType):
                            self.ui.lineName.setText(æscape(baseFilename))
                        else:
                            self.logger.error("Error Uploading File".format(fileExtension))
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
                            if uploadFile(self.parent, fileSource, fileDestination, fileType):
                                self.ui.lineName.setText(æscape(baseFilename))
                            else:
                                self.logger.error("Error Uploading File.")
                        elif ret == msgBox.StandardButton.Cancel:
                            self.logger.info("Upload Aborted.")
                        msgBox.deleteLater()
                else:
                    warningMsgBox(self.parent, "File type is not recognised. Upload aborted.", "Unknown File Type")
        except BaseException as e:
            warningMsgBox(self, e, title="Error Uploading File")

    def renameFile(self):
        oldName = self.ui.lineName.text()
        itemType = self.ui.comboType.itemText(self.ui.comboType.currentIndex())
        if oldName:
            dataDir = self.config['options']['defaultDataDir']
            fileExtension = os.path.splitext(oldName)[1][1:].lower().strip()
            oldBaseName = os.path.splitext(oldName)[0]

            renameFileDialog = RenameFileDialog(self.parent, oldBaseName)
            renameFileDialog.exec_()
            newBaseName = æscape(renameFileDialog.fileName)
            if newBaseName:
                newName = newBaseName+'.'+fileExtension
                oldFilePath = getDataFilePath(
                    dataDir, self.config['itemTypes'].dirFromNoun(itemType), oldName)
                newFilePath = getDataFilePath(
                    dataDir, self.config['itemTypes'].dirFromNoun(itemType), newName)
                try:
                    if itemType in self.config['itemTypes'].nounNames(Æ.IsWebpages):
                        oldFolderName = oldBaseName+'_files'
                        newFolderName = newBaseName+'_files'
                        oldFolderPath = getDataFilePath(
                            dataDir, self.config['itemTypes'].dirFromNoun(itemType), oldFolderName)
                        newFolderPath = getDataFilePath(
                            dataDir, self.config['itemTypes'].dirFromNoun(itemType), newFolderName)
                        if os.path.exists(oldFolderPath):
                            os.rename(oldFolderPath, newFolderPath)
                            file = QFile(oldFilePath)
                            if file.open(QIODevice.ReadWrite):
                                fileData = file.readAll()
                                oldFolderNameQuoted = quote(oldFolderName)
                                newFolderNameQuoted = quote(newFolderName)
                                fileData.replace(oldFolderName, newFolderNameQuoted)
                                fileData.replace(oldFolderNameQuoted, newFolderNameQuoted)
                                file.resize(0)
                                file.seek(0)
                                file.write(fileData)
                                file.close()
                                file.deleteLater()

                    os.rename(oldFilePath, newFilePath)
                    self.ui.lineName.setText(newName)
                except BaseException as e:
                    warningMsgBox(self.parent, e, title="Error Renaming File")
                    return False

    def garbageCollection(self):
        self.ui.termsTree.setModel(None)
        for name, model in self.treeModels.items():
            model.clear()
        self.logger.debug("Garbage collected.")

    def closeEvent(self, event):
        super(NewItemDialog, self).closeEvent(event)
        self.garbageCollection()

    def hideEvent(self, event):
        self.close()

    def deleteLater(self):
        if self.selectFileDialog:
            self.selectFileDialog.deleteLater()
        super().deleteLater()