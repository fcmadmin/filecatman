import os
import csv
import shutil
import logging
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QDialog, QListWidgetItem, QWidget, QFileDialog, QMessageBox, QStyleFactory, QDialogButtonBox
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeyEvent
from filecatman.core.objects import ÆItemType, ÆTaxonomy, ÆMessageBox
from filecatman.core.functions import getDataFilePath, warningMsgBox, loadUI
from filecatman.gui import NewItemTypeDialog, EditItemTypeDialog, NewTaxonomyDialog, EditTaxonomyDialog, \
    SaveFormattingDialog


class PreferencesDialog(QDialog):
    appName = "Preferences"
    sections = dict()
    restartRequired = False
    def __init__(self, parent):
        super(PreferencesDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = parent.app
        self.config = parent.config
        self.parent = parent
        self.icons = parent.icons
        self.logger.info("Preferences Dialog Opened")
        self.ui = loadUI("gui/ui/preferences.ui")
        self.setLayout(self.ui.layout())
        self.setWindowTitle(self.appName)
        self.setMinimumWidth(800)

        self.setDefaults()
        self.setIcons()
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Help).clicked.connect(self.openHelpBrowser)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.processData)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Apply).clicked.connect(self.applyData)
        self.ui.listSections.currentRowChanged.connect(self.onListSectionsRowChanged)

    def openHelpBrowser(self):
        self.close()
        self.app.openHelpBrowser("preferences.html")

    def onListSectionsRowChanged(self, row):
        selectedItem = self.ui.listSections.item(row)
        self.logger.debug("Selected Section: "+selectedItem.text())
        self.ui.stackedPages.setCurrentIndex(row)

    def setDefaults(self):
        self.sections['General'] = GeneralTabs(self)
        self.ui.stackedPages.addWidget(self.sections['General'])
        self.ui.listItemPreferences = QListWidgetItem("General")
        self.ui.listSections.addItem(self.ui.listItemPreferences)

        self.sections['Database'] = DatabaseTabs(self)
        self.ui.stackedPages.addWidget(self.sections['Database'])
        self.ui.listItemDatabase = QListWidgetItem("Database")
        self.ui.listSections.addItem(self.ui.listItemDatabase)

        self.sections['Copypasta'] = CopypastaTabs(self)
        self.ui.stackedPages.addWidget(self.sections['Copypasta'])
        self.ui.listItemCopypasta = QListWidgetItem("Copypasta")
        self.ui.listSections.addItem(self.ui.listItemCopypasta)

        self.ui.listSections.setCurrentRow(0)

    def setIcons(self):
        self.ui.listItemPreferences.setIcon(self.icons['Preferences'])
        self.ui.listItemDatabase.setIcon(self.icons['DatabaseInfo'])
        self.ui.listItemCopypasta.setIcon(self.icons['Copy'])

    def applyData(self):
        self.processData(1)

    def processData(self, apply=None):
        for section in self.sections:
            self.sections[section].processData()

        self.app.setIconTheme()
        self.parent.refreshMenu()
        self.app.setIcons()

        if self.restartRequired:
            msgBox = QMessageBox(self.parent)
            msgBox.setIcon(msgBox.Icon.Information)
            msgBox.setWindowTitle("Restart Required")
            msgBox.setText("A restart is required to apply all preferences.")
            msgBox.exec_()
            msgBox.deleteLater()
            self.restartRequired = False

        if not apply:
            self.close()
        else:
            self.refreshTabs()

    def goToItemTypes(self):
        itemList = self.ui.listSections.findItems("Database", Qt.MatchExactly)
        self.ui.listSections.setCurrentItem(itemList[0])
        self.sections['Database'].ui.databaseTabs.setCurrentIndex(1)

    def goToTaxonomies(self):
        itemList = self.ui.listSections.findItems("Database", Qt.MatchExactly)
        self.ui.listSections.setCurrentItem(itemList[0])
        self.sections['Database'].ui.databaseTabs.setCurrentIndex(2)

    def refreshTabs(self):
        self.setIcons()
        for section in self.sections:
            try:
                self.sections[section].refreshTabs()
            except AttributeError:
                pass


class GeneralTabs(QWidget):
    originalPalette = None

    def __init__(self, parent):
        super(GeneralTabs, self).__init__(parent)
        self.logger = parent.logger
        self.mainWindow = parent.parent
        self.app = parent.app
        self.config = self.mainWindow.config
        self.preferences = parent

        self.ui = loadUI("gui/ui/preferencesgeneral.ui")
        self.setLayout(self.ui.layout())

        self.setDefaults()

    def setDefaults(self):
        self.originalPalette = self.app.palette()
        for theme in self.app.iconsList.iconThemes.keys():
            self.ui.comboIconTheme.addItem(theme)
            if self.config['iconTheme'] == theme:
                count = self.ui.comboIconTheme.count()
                self.ui.comboIconTheme.setCurrentIndex(count-1)

        self.ui.comboStyle.addItem('System Default')
        for style in QStyleFactory.keys():
            self.ui.comboStyle.addItem(style)
            if self.config['style'] == style:
                count = self.ui.comboStyle.count()
                self.ui.comboStyle.setCurrentIndex(count-1)

        self.ui.checkStandardPalette.setChecked(self.config['standardPalette'])
        if not self.config['customSystemTheme'] == "":
            self.ui.lineThemeCustom.setText(self.config['customSystemTheme'])
        else:
            self.ui.lineThemeCustom.setText("")

    def processData(self):
        self.config['iconTheme'] = self.ui.comboIconTheme.currentText()
        self.logger.debug("Selected Icon Theme: "+self.config['iconTheme'])

        self.config['customSystemTheme'] = self.ui.lineThemeCustom.text()

        if not self.config['style'] == self.ui.comboStyle.currentText():
            self.config['style'] = self.ui.comboStyle.currentText()
            self.preferences.restartRequired = True

        if not self.config['standardPalette'] == self.ui.checkStandardPalette.isChecked():
            self.config['standardPalette'] = self.ui.checkStandardPalette.isChecked()
            self.preferences.restartRequired = True


class DatabaseTabs(QWidget):
    itemTypesModel, taxonomiesModel = QStandardItemModel(), QStandardItemModel()
    itemTypeDeletionQueue, taxonomyDeletionQueue = list(), list()
    fileTypeUpdateQueue = dict()
    itemTypeUpdateQueue, taxonomyUpdateQueue = dict(), dict()
    delItemTypeMsgAcknowledged, delTaxonomyMsgAcknowledged = False, False
    deleteItemTypeData = False

    def __init__(self, parent):
        super(DatabaseTabs, self).__init__(parent)
        self.logger = parent.logger
        self.mainWindow = parent.parent
        self.config = self.mainWindow.config
        self.dataDir = self.config['options']['defaultDataDir']
        if self.config['options'].get('relativeDataDir'): self.relativeDir = self.config['options']['relativeDataDir']
        else: self.relativeDir = False
        self.icons = self.mainWindow.icons
        self.db = self.mainWindow.db
        self.treeIcons = self.mainWindow.treeIcons

        self.ui = loadUI("gui/ui/preferencesdatabase.ui")
        self.setLayout(self.ui.layout())

        self.setDefaults()
        self.setIcons()

        self.ui.buttonDataDir.clicked.connect(self.openFileDialog)
        self.ui.buttonAddItemType.clicked.connect(self.openNewItemTypeDialog)
        self.ui.buttonDeleteItemType.clicked.connect(self.removeItemTypeFromTree)
        self.ui.buttonEditItemType.clicked.connect(self.openEditItemTypeDialog)
        self.ui.buttonMoveUp.clicked.connect(self.moveRowUpTree)
        self.ui.buttonMoveDown.clicked.connect(self.moveRowDownTree)
        self.ui.itemTypesTree.doubleClicked.connect(self.openEditItemTypeDialog)
        self.ui.buttonResetItemTypes.clicked.connect(self.resetItemTypes)
        self.ui.buttonAddTaxonomy.clicked.connect(self.openNewTaxonomyDialog)
        self.ui.buttonDeleteTaxonomy.clicked.connect(self.removeTaxonomyFromTree)
        self.ui.buttonEditTaxonomy.clicked.connect(self.openEditTaxonomyDialog)
        self.ui.buttonMoveUpTaxonomy.clicked.connect(self.moveTaxonomyRowUpTree)
        self.ui.buttonMoveDownTaxonomy.clicked.connect(self.moveTaxonomyRowDownTree)
        self.ui.taxonomiesTree.doubleClicked.connect(self.openEditTaxonomyDialog)
        self.ui.buttonResetTaxonomies.clicked.connect(self.resetTaxonomies)
        self.ui.buttonDefaultTaxonomies.clicked.connect(self.addDefaultTaxonomies)
        self.ui.buttonDefaultItemTypes.clicked.connect(self.addDefaultItemTypes)

    def setIcons(self):
        self.ui.buttonAddItemType.setIcon(self.icons['Add'])
        self.ui.buttonDeleteItemType.setIcon(self.icons['Remove'])
        self.ui.buttonEditItemType.setIcon(self.icons['Edit'])
        self.ui.buttonMoveUp.setIcon(self.icons['Up'])
        self.ui.buttonMoveDown.setIcon(self.icons['Down'])
        self.ui.buttonAddTaxonomy.setIcon(self.icons['Add'])
        self.ui.buttonDeleteTaxonomy.setIcon(self.icons['Remove'])
        self.ui.buttonEditTaxonomy.setIcon(self.icons['Edit'])
        self.ui.buttonMoveUpTaxonomy.setIcon(self.icons['Up'])
        self.ui.buttonMoveDownTaxonomy.setIcon(self.icons['Down'])

    def refreshTabs(self):
        self.setIcons()
        self.displayItemTypes()
        self.displayTaxonomies()

    def setDefaults(self):
        self.ui.checkOpenLast.setChecked(self.config['autoloadDatabase'])
        self.ui.lineDataDir.setText(self.config['options']['defaultDataDir'])
        if self.db.config['type'] == "sqlite":
            if self.config['options'].get('relativeDataDir'):
                self.ui.checkRelativeDir.setChecked(self.config['options']['relativeDataDir'])
            else: self.ui.checkRelativeDir.setChecked(False)
            self.ui.checkRelativeDir.setEnabled(True)
        else:
            self.ui.checkRelativeDir.setChecked(False)
            self.ui.checkRelativeDir.setEnabled(False)
        self.ui.spinCatLvls.setValue(self.config['options']['catLvls'])

        self.displayItemTypes()
        self.displayTaxonomies()

    def openFileDialog(self):
        openDialog = QFileDialog(self)
        openDialog.setFileMode(openDialog.FileMode.Directory)
        openDialog.setDirectory(self.config['options']['defaultDataDir'])
        openDialog.setWindowTitle("Select Data Directory")
        openDialog.setViewMode(openDialog.ViewMode.List)
        openDialog.setOption(openDialog.Option.ShowDirsOnly, True)
        if openDialog.exec_():
            fileObj = openDialog.selectedFiles()
            filename = fileObj[0] + "/"
            self.logger.debug(filename)
            self.ui.lineDataDir.setText(filename)

    def displayItemTypes(self):
        columnNames = ("Visible", "Icon", "Noun Name", "Plural Name", "Table Name", "Folder Name", "Extensions")
        self.itemTypesModel.clear()
        for itemType in self.config['itemTypes']:
            enabledItem = QStandardItem()
            enabledItem.setCheckable(True)
            if itemType.enabled is True:
                enabledItem.setCheckState(Qt.Checked)
            else:
                enabledItem.setCheckState(Qt.Unchecked)
            pluralItem = QStandardItem(itemType.pluralName)
            dirItem = QStandardItem(itemType.dirName)
            iconItem = QStandardItem(self.icons[itemType.iconName], itemType.iconName)
            nounItem = QStandardItem(itemType.nounName)
            tableItem = QStandardItem(itemType.tableName)
            extensionsItem = QStandardItem(", ".join(itemType.extensions))
            self.itemTypesModel.appendRow((
                enabledItem, iconItem, nounItem, pluralItem, tableItem, dirItem, extensionsItem))
        self.ui.itemTypesTree.setModel(self.itemTypesModel)

        self.itemTypesModel.setHorizontalHeaderLabels(columnNames)
        self.ui.itemTypesTree.setColumnWidth(0, 60)
        self.ui.itemTypesTree.setColumnWidth(1, 50)

        index = self.itemTypesModel.index(0, 0)
        self.ui.itemTypesTree.setCurrentIndex(index)

    def displayTaxonomies(self):
        columnNames = ("Visible", "Icon", "Noun Name", "Plural Name",
                       "Table Name", "Folder Name", "Has Children", "Tags Mode")
        self.taxonomiesModel.clear()
        for taxonomy in self.config['taxonomies']:
            enabledItem = QStandardItem()
            enabledItem.setCheckable(True)
            if taxonomy.enabled:
                enabledItem.setCheckState(Qt.Checked)
            else:
                enabledItem.setCheckState(Qt.Unchecked)
            pluralItem = QStandardItem(taxonomy.pluralName)
            dirItem = QStandardItem(taxonomy.dirName)
            iconItem = QStandardItem(self.icons[taxonomy.iconName], taxonomy.iconName)
            nounItem = QStandardItem(taxonomy.nounName)
            tableItem = QStandardItem(taxonomy.tableName)
            hasChildrenItem = QStandardItem()
            hasChildrenItem.setCheckable(True)
            if taxonomy.hasChildren:
                hasChildrenItem.setCheckState(Qt.Checked)
            else:
                hasChildrenItem.setCheckState(Qt.Unchecked)
            isTagsItem = QStandardItem()
            isTagsItem.setCheckable(True)
            if taxonomy.isTags:
                isTagsItem.setCheckState(Qt.Checked)
            else:
                isTagsItem.setCheckState(Qt.Unchecked)
            self.taxonomiesModel.appendRow((
                enabledItem, iconItem, nounItem, pluralItem, tableItem, dirItem, hasChildrenItem, isTagsItem))
        self.ui.taxonomiesTree.setModel(self.taxonomiesModel)

        self.taxonomiesModel.setHorizontalHeaderLabels(columnNames)
        self.ui.taxonomiesTree.setColumnWidth(0, 60)
        self.ui.taxonomiesTree.setColumnWidth(1, 50)

        index = self.taxonomiesModel.index(0, 0)
        self.ui.taxonomiesTree.setCurrentIndex(index)

    def openNewItemTypeDialog(self):
        newItemTypeDialog = NewItemTypeDialog(self.mainWindow)
        newItemTypeDialog.newItemType.connect(self.addItemTypeToTree)
        newItemTypeDialog.exec()
        newItemTypeDialog.deleteLater()

    def openNewTaxonomyDialog(self):
        newTaxonomyDialog = NewTaxonomyDialog(self.mainWindow)
        newTaxonomyDialog.newTaxonomy.connect(self.addTaxonomyToTree)
        newTaxonomyDialog.exec()
        newTaxonomyDialog.deleteLater()

    def addItemTypeToTree(self, nounName, pluralName, tableName, dirName, iconName, typeVisible, extensions):
        enabledItem = QStandardItem()
        enabledItem.setCheckable(True)
        if typeVisible is True:
            enabledItem.setCheckState(Qt.Checked)
        else:
            enabledItem.setCheckState(Qt.Unchecked)
        pluralItem = QStandardItem(pluralName)
        dirItem = QStandardItem(dirName)
        iconItem = QStandardItem(self.icons[iconName], iconName)
        nounItem = QStandardItem(nounName)
        tableItem = QStandardItem(tableName)
        extensionsItem = QStandardItem(", ".join(extensions))
        self.itemTypesModel.appendRow((
            enabledItem, iconItem, nounItem, pluralItem, tableItem, dirItem, extensionsItem))

    def addTaxonomyToTree(self, nounName, pluralName, tableName, dirName, iconName, typeVisible, hasChildren, isTags):
        enabledItem = QStandardItem()
        enabledItem.setCheckable(True)
        enabledItem.setCheckState(typeVisible)
        pluralItem = QStandardItem(pluralName)
        dirItem = QStandardItem(dirName)
        iconItem = QStandardItem(self.icons[iconName], iconName)
        nounItem = QStandardItem(nounName)
        tableItem = QStandardItem(tableName)
        hasChildrenItem = QStandardItem()
        hasChildrenItem.setCheckable(True)
        hasChildrenItem.setCheckState(hasChildren)
        isTagsItem = QStandardItem()
        isTagsItem.setCheckable(True)
        isTagsItem.setCheckState(isTags)
        self.taxonomiesModel.appendRow((
            enabledItem, iconItem, nounItem, pluralItem, tableItem, dirItem, hasChildrenItem, isTagsItem))

    def openEditItemTypeDialog(self):
        dataList = list()
        indexes = self.ui.itemTypesTree.selectedIndexes()
        if indexes:
            dataList.append(indexes[0].row())

            checkItem = self.itemTypesModel.itemFromIndex(indexes[0])
            dataList.append(checkItem.checkState())
            indexes.pop(0)

            for index in indexes:
                data = self.itemTypesModel.itemFromIndex(index).data(0)
                dataList.append(data)
            self.logger.debug(dataList)

            editItemTypeDialog = EditItemTypeDialog(self.mainWindow, dataList)
            editItemTypeDialog.editedItemType.connect(self.editItemTypeInTree)
            editItemTypeDialog.exec()
            editItemTypeDialog.deleteLater()

    def openEditTaxonomyDialog(self):
        dataList = list()
        indexes = self.ui.taxonomiesTree.selectedIndexes()
        if indexes:
            dataList.append(indexes[0].row())

            checkItem = self.taxonomiesModel.itemFromIndex(indexes[0])
            dataList.append(checkItem.checkState())
            indexes.pop(0)

            for index in indexes[:-2]:
                data = self.taxonomiesModel.itemFromIndex(index).data(0)
                dataList.append(data)

            checkHasChildrenItem = self.taxonomiesModel.itemFromIndex(indexes[-2])
            dataList.append(checkHasChildrenItem.checkState())

            checkIsTagsItem = self.taxonomiesModel.itemFromIndex(indexes[-1])
            dataList.append(checkIsTagsItem.checkState())
            self.logger.debug(dataList)

            editTaxonomyDialog = EditTaxonomyDialog(self.mainWindow, dataList)
            editTaxonomyDialog.editedTaxonomy.connect(self.editTaxonomyInTree)
            editTaxonomyDialog.exec()
            editTaxonomyDialog.deleteLater()

    def editItemTypeInTree(self, row, nounName, pluralName, tableName, dirName, iconName, typeVisible, extensions):
        indexVisible = self.itemTypesModel.index(row, 0)
        self.itemTypesModel.setData(indexVisible, typeVisible, Qt.CheckStateRole)
        indexIcon = self.itemTypesModel.index(row, 1)
        self.itemTypesModel.itemFromIndex(indexIcon).setIcon(self.icons[iconName])
        self.itemTypesModel.setData(indexIcon, iconName, Qt.EditRole)
        indexNoun = self.itemTypesModel.index(row, 2)
        self.itemTypesModel.setData(indexNoun, nounName, Qt.EditRole)
        indexPlural = self.itemTypesModel.index(row, 3)
        self.itemTypesModel.setData(indexPlural, pluralName, Qt.EditRole)

        indexTable = self.itemTypesModel.index(row, 4)
        oldTableName = self.itemTypesModel.data(indexTable)
        for key, value in self.itemTypeUpdateQueue.items():
            if value == oldTableName:
                oldTableName = key
                self.itemTypeUpdateQueue.pop(key)
                break
        self.itemTypeUpdateQueue[oldTableName] = tableName
        self.itemTypesModel.setData(indexTable, tableName, Qt.EditRole)

        indexDir = self.itemTypesModel.index(row, 5)
        oldDirName = self.itemTypesModel.data(indexDir)
        for key, value in self.fileTypeUpdateQueue.items():
            if value == oldDirName:
                oldDirName = key
                self.fileTypeUpdateQueue.pop(key)
                break
        self.fileTypeUpdateQueue[oldDirName] = dirName
        self.itemTypesModel.setData(indexDir, dirName, Qt.EditRole)

        indexExtensions = self.itemTypesModel.index(row, 6)
        self.itemTypesModel.setData(indexExtensions, ", ".join(extensions), Qt.EditRole)

    def editTaxonomyInTree(self, row, nounName, pluralName, tableName, dirName, iconName, typeVisible,
                           hasChildren, isTags):
        qtBugFix = {Qt.CheckState.Checked: 2, Qt.CheckState.Unchecked: 0}
        print(qtBugFix[typeVisible])
        print(qtBugFix[hasChildren])
        print(qtBugFix[isTags])
        indexVisible = self.taxonomiesModel.index(row, 0)
        self.taxonomiesModel.setData(indexVisible, qtBugFix[typeVisible], Qt.CheckStateRole)
        indexIcon = self.taxonomiesModel.index(row, 1)
        self.taxonomiesModel.itemFromIndex(indexIcon).setIcon(self.icons[iconName])
        self.taxonomiesModel.setData(indexIcon, iconName, Qt.EditRole)
        indexNoun = self.taxonomiesModel.index(row, 2)
        self.taxonomiesModel.setData(indexNoun, nounName, Qt.EditRole)
        indexPlural = self.taxonomiesModel.index(row, 3)
        self.taxonomiesModel.setData(indexPlural, pluralName, Qt.EditRole)

        indexTable = self.taxonomiesModel.index(row, 4)
        oldTableName = self.taxonomiesModel.data(indexTable)
        for key, value in self.taxonomyUpdateQueue.items():
            if value == oldTableName:
                oldTableName = key
                self.taxonomyUpdateQueue.pop(key)
                break
        self.taxonomyUpdateQueue[oldTableName] = tableName
        self.taxonomiesModel.setData(indexTable, tableName, Qt.EditRole)

        indexDir = self.taxonomiesModel.index(row, 5)
        self.taxonomiesModel.setData(indexDir, dirName, Qt.EditRole)
        indexHasChildren = self.taxonomiesModel.index(row, 6)
        self.taxonomiesModel.setData(indexHasChildren, qtBugFix[hasChildren], Qt.CheckStateRole)
        indexIsTags = self.taxonomiesModel.index(row, 7)
        self.taxonomiesModel.setData(indexIsTags, qtBugFix[isTags], Qt.CheckStateRole)

    def removeItemTypeFromTree(self):
        index = self.ui.itemTypesTree.selectedIndexes()
        if index:
            typeIden = index[4].data(0)

            message = '<span style="font-weight:600;"><span style="color:red;">WARNING:</span> ' \
                      'This will delete all items with this type. Continue?'
            msgBox = ÆMessageBox(self)
            msgBox.setIcon(msgBox.Icon.Warning)
            msgBox.setWindowTitle("Delete Item Type?")
            msgBox.setText(message)
            msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
            msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
            msgBox.setCheckable(True)
            msgBox.checkboxes[0].setText("Delete files in data folder.")
            if not self.delItemTypeMsgAcknowledged:
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.delItemTypeMsgAcknowledged = True
            if self.delItemTypeMsgAcknowledged:
                if msgBox.checkboxes[0].isChecked():
                    self.deleteItemTypeData = True
                self.itemTypeDeletionQueue.append(typeIden)
                self.itemTypesModel.takeRow(index[0].row())

    def removeTaxonomyFromTree(self):
        index = self.ui.taxonomiesTree.selectedIndexes()
        if index:
            termTaxonomy = index[4].data(0)

            message = '<span style="font-weight:600;"><span style="color:red;">WARNING:</span> ' \
                      'This will delete all categories with this taxonomy. Continue?'
            msgBox = QMessageBox(self)
            msgBox.setIcon(QMessageBox.Icon.Warning)
            msgBox.setWindowTitle("Delete Taxonomy?")
            msgBox.setText(message)
            msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
            msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
            if not self.delTaxonomyMsgAcknowledged:
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.delTaxonomyMsgAcknowledged = True
            if self.delTaxonomyMsgAcknowledged:
                self.taxonomyDeletionQueue.append(termTaxonomy)
                self.taxonomiesModel.takeRow(index[0].row())

    def moveRowUpTree(self):
        indexes = self.ui.itemTypesTree.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            if row > 0:
                itemList = self.itemTypesModel.takeRow(row)
                self.itemTypesModel.insertRow(row-1, itemList)
                index = self.itemTypesModel.index(row-1, 0)
                self.ui.itemTypesTree.setCurrentIndex(index)

    def moveTaxonomyRowUpTree(self):
        indexes = self.ui.taxonomiesTree.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            if row > 0:
                itemList = self.taxonomiesModel.takeRow(row)
                self.taxonomiesModel.insertRow(row-1, itemList)
                index = self.taxonomiesModel.index(row-1, 0)
                self.ui.taxonomiesTree.setCurrentIndex(index)

    def moveRowDownTree(self):
        indexes = self.ui.itemTypesTree.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            if row < self.itemTypesModel.rowCount()-1:
                itemList = self.itemTypesModel.takeRow(row)
                self.itemTypesModel.insertRow(row+1, itemList)
                index = self.itemTypesModel.index(row+1, 0)
                self.ui.itemTypesTree.setCurrentIndex(index)

    def moveTaxonomyRowDownTree(self):
        indexes = self.ui.taxonomiesTree.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            if row < self.taxonomiesModel.rowCount()-1:
                itemList = self.taxonomiesModel.takeRow(row)
                self.taxonomiesModel.insertRow(row+1, itemList)
                index = self.taxonomiesModel.index(row+1, 0)
                self.ui.taxonomiesTree.setCurrentIndex(index)

    def resetItemTypes(self):
        self.itemTypesModel.clear()
        try:
            self.itemTypeDeletionQueue.clear()
        except AttributeError:
            del self.itemTypeDeletionQueue[:]
        self.fileTypeUpdateQueue.clear()
        self.itemTypeUpdateQueue.clear()
        self.displayItemTypes()

    def addDefaultTaxonomies(self):
        defaultTaxonomies = self.mainWindow.defaultTaxonomies
        for defTax in defaultTaxonomies:
            i = 0
            alreadyExists = False
            while self.taxonomiesModel.hasIndex(i, 0):
                currentNoun = self.taxonomiesModel.data(self.taxonomiesModel.index(i, 2))
                if currentNoun == defTax[1]:
                    alreadyExists = True
                    break
                currentPlural = self.taxonomiesModel.data(self.taxonomiesModel.index(i, 3))
                if currentPlural == defTax[0]:
                    alreadyExists = True
                    break
                i += 1
            if defTax[3] is True:
                hasChildren = Qt.Checked
            else:
                hasChildren = Qt.Unchecked
            if len(defTax) is 5:
                isTags = Qt.Checked
            else:
                isTags = Qt.Unchecked
            if alreadyExists is False:
                self.addTaxonomyToTree(
                    nounName=defTax[1], pluralName=defTax[0], tableName=defTax[2], dirName=defTax[0],
                    iconName=defTax[1], typeVisible=Qt.Checked, hasChildren=hasChildren, isTags=isTags
                )

    def addDefaultItemTypes(self):
        defaultItemTypes = self.mainWindow.defaultItemTypes
        for defType in defaultItemTypes:
            i = 0
            alreadyExists = False
            while self.itemTypesModel.hasIndex(i, 0):
                currentNoun = self.itemTypesModel.data(self.itemTypesModel.index(i, 2))
                if currentNoun == defType[1]:
                    alreadyExists = True
                    break
                currentPlural = self.itemTypesModel.data(self.itemTypesModel.index(i, 3))
                if currentPlural == defType[0]:
                    alreadyExists = True
                    break
                i += 1
            if len(defType) is 4:
                extensions = defType[3]
            else:
                extensions = ()
            if alreadyExists is False:
                self.addItemTypeToTree(
                    nounName=defType[1], pluralName=defType[0], tableName=defType[2], dirName=defType[0],
                    iconName=defType[1], typeVisible=True, extensions=extensions
                )

    def resetTaxonomies(self):
        self.taxonomiesModel.clear()
        try:
            self.taxonomyDeletionQueue.clear()
        except AttributeError:
            del self.taxonomyDeletionQueue[:]
        self.taxonomyUpdateQueue.clear()
        self.displayTaxonomies()

    def processData(self):
        self.config['autoloadDatabase'] = self.ui.checkOpenLast.isChecked()
        if self.db.config['type'] == "sqlite":
            self.config['options']['relativeDataDir'] = self.ui.checkRelativeDir.isChecked()
        else:
            self.config['options']['relativeDataDir'] = False
        self.config['options']['defaultDataDir'] = self.ui.lineDataDir.text()

        self.config['options']['catLvls'] = self.ui.spinCatLvls.value()

        for typeIden in self.itemTypeDeletionQueue:
            self.db.open()
            self.db.transaction()
            itemsQuery = self.db.selectItems(dict(type_id=typeIden, col='i.item_id'))
            while itemsQuery.next():
                self.db.deleteItem(itemsQuery.value(0))
            self.db.commit()
            self.db.close()
            if self.deleteItemTypeData is True:
                folderName = self.config['itemTypes'].dirFromTable(typeIden)
                if folderName:
                    try:
                        folderPath = getDataFilePath(self.dataDir, folderName)
                        if os.path.exists(folderPath):
                            shutil.rmtree(folderPath)
                            self.logger.info("`{}` data folder deleted.".format(folderName))
                    except BaseException as e:
                        warningMsgBox(self.mainWindow, e, title="Error Deleting Folder")
                        return False
        try:
            self.itemTypeDeletionQueue.clear()
        except AttributeError:
            del self.itemTypeDeletionQueue[:]

        for taxonomy in self.taxonomyDeletionQueue:
            try:
                self.db.open()
                self.db.transaction()
                catQuery = self.db.selectCategories(dict(term_taxonomy=taxonomy, col='t.term_id'))
                while catQuery.next():
                    self.db.deleteCategory(catQuery.value(0))
                self.db.commit()
                self.db.close()
            except BaseException as e:
                warningMsgBox(self.mainWindow, e, title="Error Renaming Folder")
                return False
        try:
            self.taxonomyDeletionQueue.clear()
        except AttributeError:
            del self.taxonomyDeletionQueue[:]

        for oldName, newName in self.itemTypeUpdateQueue.items():
            try:
                self.logger.debug("Changing {} to {}".format(oldName, newName))
                self.db.open()
                self.db.transaction()
                self.db.updateItemType(oldName, newName)
                self.db.commit()
                self.db.close()
            except BaseException as e:
                warningMsgBox(self.mainWindow, e, title="Error Renaming Folder")
                return False
        self.itemTypeUpdateQueue.clear()

        for oldName, newName in self.fileTypeUpdateQueue.items():
            self.logger.debug("Changing Folder {} to {}".format(oldName, newName))
            oldFolderPath = getDataFilePath(self.dataDir, oldName)
            newFolderPath = getDataFilePath(self.dataDir, newName)
            self.logger.debug("OLD FOLDER PATH: "+oldFolderPath)
            self.logger.debug("NEW FOLDER PATH: "+newFolderPath)
            try:
                if os.path.exists(oldFolderPath):
                    os.rename(oldFolderPath, newFolderPath)
            except BaseException as e:
                warningMsgBox(self.mainWindow, e, title="Error Renaming Folder")
                return False
        self.fileTypeUpdateQueue.clear()

        for oldName, newName in self.taxonomyUpdateQueue.items():
            try:
                self.logger.debug("Changing {} to {}".format(oldName, newName))
                self.db.open()
                self.db.transaction()
                self.db.updateTaxonomy(oldName, newName)
                self.db.commit()
                self.db.close()
            except BaseException as e:
                warningMsgBox(self.mainWindow, e, title="Error Renaming Folder")
                return False
        self.taxonomyUpdateQueue.clear()
        qtBugFix = {Qt.CheckState.Checked: 2, Qt.CheckState.Unchecked: 0}
        self.config['itemTypes'].clear()
        i = 0
        model = self.itemTypesModel
        while model.hasIndex(i, 0):
            itemType = ÆItemType()
            itemType.setEnabled(bool(qtBugFix[model.itemFromIndex(model.index(i, 0)).checkState()]))
            itemType.setIconName(model.itemFromIndex(model.index(i, 1)).data(0))
            itemType.setNounName(model.itemFromIndex(model.index(i, 2)).data(0))
            itemType.setPluralName(model.itemFromIndex(model.index(i, 3)).data(0))
            itemType.setTableName(model.itemFromIndex(model.index(i, 4)).data(0))
            itemType.setDirName(model.itemFromIndex(model.index(i, 5)).data(0))
            reader = csv.reader([model.itemFromIndex(model.index(i, 6)).data(0)], skipinitialspace=True)
            for extensions in reader:
                if extensions:
                    itemType.setExtensions(extensions)
                    if itemType.hasExtension("html") and itemType.hasExtension("htm"):
                        itemType.isWebpages = True
                else:
                    itemType.isWeblinks = True
            self.config['itemTypes'].append(itemType)
            i += 1

        self.config['taxonomies'].clear()
        i = 0
        model = self.taxonomiesModel
        while model.hasIndex(i, 0):
            taxonomy = ÆTaxonomy()
            taxonomy.setEnabled(bool(qtBugFix[model.itemFromIndex(model.index(i, 0)).checkState()]))
            taxonomy.setIconName(model.itemFromIndex(model.index(i, 1)).data(0))
            taxonomy.setNounName(model.itemFromIndex(model.index(i, 2)).data(0))
            taxonomy.setPluralName(model.itemFromIndex(model.index(i, 3)).data(0))
            taxonomy.setTableName(model.itemFromIndex(model.index(i, 4)).data(0))
            taxonomy.setDirName(model.itemFromIndex(model.index(i, 5)).data(0))
            taxonomy.setHasChildren(bool(qtBugFix[model.itemFromIndex(model.index(i, 6)).checkState()]))
            taxonomy.setIsTags(bool(qtBugFix[model.itemFromIndex(model.index(i, 7)).checkState()]))
            self.config['taxonomies'].append(taxonomy)
            i += 1


class CopypastaTabs(QWidget):
    formattingModel = QStandardItemModel()

    def __init__(self, parent):
        super(CopypastaTabs, self).__init__(parent)
        self.logger = parent.logger
        self.mainWindow = parent.parent
        self.app = parent.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons

        self.ui = loadUI("gui/ui/preferencescopypasta.ui")
        self.setLayout(self.ui.layout())

        self.ui.buttonEditFormatting.clicked.connect(self.editSelectedRow)
        self.ui.buttonResetFormatting.clicked.connect(self.resetFormattingTree)
        self.ui.buttonClearFormatting.clicked.connect(self.clearSelectedRow)
        self.ui.buttonSaveTemplate.clicked.connect(self.saveTemplate)
        self.ui.buttonDeleteTemplate.clicked.connect(self.deleteTemplate)
        self.ui.comboTemplates.currentIndexChanged.connect(self.onComboTemplatesIndexChanged)

        self.setIcons()
        self.setDefaults()

    def setIcons(self):
        self.ui.buttonClearFormatting.setIcon(self.icons['Clear'])
        self.ui.buttonEditFormatting.setIcon(self.icons['Edit'])

    def refreshTabs(self):
        self.setIcons()
        self.displayFormattingTree()

    def setDefaults(self):
        try:
            self.ui.checkCopyName.setChecked(self.config['copypasta']['enabledName'])
            self.ui.checkCopySource.setChecked(self.config['copypasta']['enabledSource'])
            self.ui.checkCopyDescription.setChecked(self.config['copypasta']['enabledDescription'])
            self.ui.checkKeepFileExtension.setChecked(self.config['copypasta']['keepFileExtension'])
            self.ui.checkFormatDescByLine.setChecked(self.config['copypasta']['formatEachLineOfDesc'])
        except (TypeError, KeyError):
            self.config.createDefaultCopypasta()
            self.logger.warning("Configuration file contained invalid Copypasta settings.")
            self.setDefaults()
            return

        self.displayFormattingTemplates()
        self.displayFormattingTree()

    def displayFormattingTree(self):
        self.formattingModel.clear()
        columnNames = ('Field', 'Formatting')
        columnData = (
            (QStandardItem('Name'), QStandardItem(self.config['copypasta']['formatName'])),
            (QStandardItem('Source'), QStandardItem(self.config['copypasta']['formatSource'])),
            (QStandardItem('Description'), QStandardItem(self.config['copypasta']['formatDescription'])),
            (QStandardItem('Outer Formatting'), QStandardItem(self.config['copypasta']['outerFormatting']))
        )
        for data in columnData:
            data[0].setEditable(False)
            self.formattingModel.appendRow((data[0], data[1]))

        self.ui.formattingTree.setModel(self.formattingModel)
        self.formattingModel.setHorizontalHeaderLabels(columnNames)
        self.ui.formattingTree.setColumnWidth(0, 200)

        index = self.formattingModel.index(0, 0)
        self.ui.formattingTree.setCurrentIndex(index)

    def editSelectedRow(self):
        indexes = self.ui.formattingTree.selectedIndexes()
        if indexes:
            currentRow = indexes[0].row()
            index = self.formattingModel.index(currentRow, 1)
            self.ui.formattingTree.setCurrentIndex(index)
            self.ui.formattingTree.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F2, Qt.NoModifier))

    def resetFormattingTree(self):
        self.ui.comboTemplates.setCurrentIndex(0)
        self.displayFormattingTree()

    def clearSelectedRow(self):
        indexes = self.ui.formattingTree.selectedIndexes()
        if indexes:
            currentRow = indexes[0].row()
            index = self.formattingModel.index(currentRow, 1)
            self.formattingModel.setData(index, "{0}")

    def displayFormattingTemplates(self):
        self.ui.comboTemplates.addItem("Current Template")
        for name in self.config['copypastaTemplates'].keys():
            self.ui.comboTemplates.addItem(name)

    def saveTemplate(self):
        formattingDialog = SaveFormattingDialog(self.mainWindow)
        formattingDialog.exec_()
        name = formattingDialog.templateName
        if not name == '':
            formatName = self.formattingModel.data(self.formattingModel.index(0, 1))
            formatSource = self.formattingModel.data(self.formattingModel.index(1, 1))
            formatDescription = self.formattingModel.data(self.formattingModel.index(2, 1))
            formatOuter = self.formattingModel.data(self.formattingModel.index(3, 1))
            if self.config['copypastaTemplates'].get(name):
                message = "Are you sure you want to overwrite existing template?"
                msgBox = QMessageBox(self)
                msgBox.setIcon(QMessageBox.Icon.Question)
                msgBox.setWindowTitle("Overwrite Existing Template?")
                msgBox.setText(message)
                msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.config['copypastaTemplates'].pop(name)
                    self.config['copypastaTemplates'][name] = (formatName, formatSource, formatDescription, formatOuter)
                msgBox.deleteLater()
            else:
                self.config['copypastaTemplates'][name] = (formatName, formatSource, formatDescription, formatOuter)
                self.ui.comboTemplates.addItem(name)
        formattingDialog.deleteLater()

    def deleteTemplate(self):
        row = self.ui.comboTemplates.currentIndex()
        if row > 0:
            self.config['copypastaTemplates'].pop(self.ui.comboTemplates.currentText())
            self.ui.comboTemplates.removeItem(row)

    def onComboTemplatesIndexChanged(self):
        row = self.ui.comboTemplates.currentIndex()
        if row > 0:
            name = self.ui.comboTemplates.currentText()
            template = self.config['copypastaTemplates'][name]
            self.formattingModel.setData(self.formattingModel.index(0, 1), template[0])
            self.formattingModel.setData(self.formattingModel.index(1, 1), template[1])
            self.formattingModel.setData(self.formattingModel.index(2, 1), template[2])
            self.formattingModel.setData(self.formattingModel.index(3, 1), template[3])
        else:
            self.formattingModel.setData(self.formattingModel.index(0, 1),
                                         self.config['copypasta']['formatName'])
            self.formattingModel.setData(self.formattingModel.index(1, 1),
                                         self.config['copypasta']['formatSource'])
            self.formattingModel.setData(self.formattingModel.index(2, 1),
                                         self.config['copypasta']['formatDescription'])
            self.formattingModel.setData(self.formattingModel.index(3, 1),
                                         self.config['copypasta']['outerFormatting'])

    def processData(self):
        self.config['copypasta']['enabledName'] = self.ui.checkCopyName.isChecked()
        self.config['copypasta']['enabledSource'] = self.ui.checkCopySource.isChecked()
        self.config['copypasta']['enabledDescription'] = self.ui.checkCopyDescription.isChecked()
        self.config['copypasta']['keepFileExtension'] = self.ui.checkKeepFileExtension.isChecked()
        self.config['copypasta']['formatEachLineOfDesc'] = self.ui.checkFormatDescByLine.isChecked()

        self.config['copypasta']['formatName'] = self.formattingModel.data(self.formattingModel.index(0, 1))
        self.config['copypasta']['formatSource'] = self.formattingModel.data(self.formattingModel.index(1, 1))
        self.config['copypasta']['formatDescription'] = self.formattingModel.data(self.formattingModel.index(2, 1))
        self.config['copypasta']['outerFormatting'] = self.formattingModel.data(self.formattingModel.index(3, 1))