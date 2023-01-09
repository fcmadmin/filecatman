import os, platform
import webbrowser
import csv
import shutil
import logging
from urllib.parse import unquote, quote
from threading import Thread

from PySide6.QtCore import Qt, QElapsedTimer, QDateTime, QSettings
from PySide6.QtWidgets import QMainWindow, QMenu, QToolButton, QMessageBox, QPushButton, QComboBox
from PySide6.QtGui import QAction, QStandardItemModel, QStandardItem, QCursor, QIcon
from PySide6.QtSql import QSqlQuery, QSqlDatabase

from filecatman.core import const
from filecatman.core.namespace import Æ
from filecatman.core.objects import ÆItemType, ÆItemTypeList, ÆTaxonomy, ÆTaxonomyList, \
    ÆMessageBox, ÆMainTableModel, ÆCategoryTreeModel, ÆRelationsTableModel, ÆButtonLineEdit, ÆMainTreeView, \
    ÆMainListView
from filecatman.core.functions import getDataFilePath, warningMsgBox, deleteFile, æscape, loadUI, uploadFile, downloadFile, convToBool
from filecatman.core.database import ÆDatabase
from filecatman.gui import NewItemDialog, EditItemDialog, NewCategoryDialog, EditCategoryDialog, PreferencesDialog, \
    InfoDialog, AboutDialog, ImportWizard, ExportWizard, CreateLinksWizard, ItemChecker, \
    FileManager, AdvancedSearchDialog, RelationsRecounter, BulkEditDialog, LinkChecker, OpenWithDialog
import requests


class MainWindow(QMainWindow):
    config, defColumns, searchPhrase, db, timer = None, None, None, None, None
    missingFiles, brokenLinks = list(), list()
    menuModel, bulkCatsModel, bulkItemsModel = QStandardItemModel(), QStandardItemModel(), QStandardItemModel()
    tableArgs, icons, pixmaps, treeIcons = dict(), dict(), dict(), dict()
    tableModel, treeModel, relationsModel, = ÆMainTableModel(), ÆCategoryTreeModel(), None
    currentView = None
    advancedSearchSQL = None
    isInitialized = False
    tableViewMode = "list"
    defaultExtensions = dict(
        webpage=('html', 'htm', 'xhtml', 'xht'),
        document=('pdf', 'doc', 'docx', 'txt', 'odt', 'mobi', 'epub', 'rtf', 'abw'),
        image=('jpeg', 'jpg', 'png', 'apng', 'gif', 'bmp', 'svg', 'ico', 'webp'),
        audio=('mp3', 'flac', 'wav', 'wma', 'mid', 'ogg', 'm4a'),
        video=('flv', 'mp4', 'avi', 'm4v', 'mkv', 'mov', 'mpeg', 'mpg', 'wmv', '3gp', 'webm')
    )
    defaultItemTypes = (
        ('Webpages', 'Webpage', 'webpage', defaultExtensions['webpage']),
        ('Documents', 'Document', 'document', defaultExtensions['document']),
        ('Images', 'Image', 'image', defaultExtensions['image']),
        ('Weblinks', 'Weblink', 'weblink'),
        ('Audio', 'Audio', 'audio', defaultExtensions['audio']),
        ('Video', 'Video', 'video', defaultExtensions['video'])
    )
    defaultTaxonomies = (
        ('Authors', 'Author', 'author', False),
        ('Subjects', 'Subject', 'subject', True),
        ('Tags', 'Tag', 'tag', False, True)
    )

    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.icons = self.app.iconsList.icons
        self.pixmaps = self.app.iconsList.pixmaps
        self.treeIcons = self.app.iconsList.treeIcons
        self.clipboard = self.app.clipboard()
        if self.app.portableMode:
            self.iconsDir = "icons/"
        else:
            self.iconsDir = os.path.join(os.path.dirname(QSettings().fileName()),"icons")
        self.appName = app.applicationName()
        self.ui = loadUI(os.path.join('gui','ui','main.ui'))
        self.setCentralWidget(self.ui.centralwidget)
        self.setMenuBar(self.ui.menubar)
        self.setStatusBar(self.ui.statusbar)
        self.addToolBar(self.ui.toolBar)
        self.addToolBar(self.ui.toolBarBulkActions)
        self.addToolBar(self.ui.toolBarSearch)
        self.setWindowIcon(self.icons['Filecatman'])
        self.setWindowSizeAndCentre()
        self.constructRestOfUI()
        self.connectSignals()

    def initializeWindow(self, config=None):
        self.setConfig(config)
        self.setVariables()
        self.setCustomIcons()
        self.setWindowTitle(os.path.basename(self.config['db']['db'])+' - '+self.appName)
        self.setIconTheme()
        self.displayMenu()
        self.setIcons()
        self.setTreeModels()
        self.displayItems()
        self.onTreeViewSelectionChanged()
        self.setUserSettings()
        self.isInitialized = True
        self.show()

    def createDefaultItemTypes(self):
        itemTypes = ÆItemTypeList()
        for typeTuple in self.defaultItemTypes:
            itemType = ÆItemType()
            itemType.setPluralName(typeTuple[0])
            itemType.setNounName(typeTuple[1])
            itemType.setTableName(typeTuple[2])
            if len(typeTuple) is 4:
                itemType.setExtensions(typeTuple[3])
                if itemType.hasExtension("html") and itemType.hasExtension("htm"):
                    itemType.isWebpages = True
            else:
                itemType.isWeblinks = True
            itemType.setIconName(typeTuple[1])
            itemTypes.append(itemType)
        return itemTypes

    def createDefaultTaxonomies(self):
        taxonomies = ÆTaxonomyList()
        for taxTuple in self.defaultTaxonomies:
            taxonomy = ÆTaxonomy()
            taxonomy.setPluralName(taxTuple[0])
            taxonomy.setNounName(taxTuple[1])
            taxonomy.setTableName(taxTuple[2])
            taxonomy.setHasChildren(taxTuple[3])
            if len(taxTuple) is 5:
                taxonomy.setIsTags(taxTuple[4])
            taxonomy.setIconName(taxTuple[1])
            taxonomies.append(taxonomy)
        return taxonomies

    def setUserSettings(self):
        self.ui.toolBar.setVisible(self.config['mainWindow']['toggleMainToolbar'])
        self.ui.toolBarSearch.setVisible(self.config['mainWindow']['toggleSearchToolbar'])
        self.ui.toolBarBulkActions.setVisible(self.config['mainWindow']['toggleBulkActionsToolbar'])
        self.ui.scrollAreaMenu.setVisible(self.config['mainWindow']['toggleSidebar'])
        self.ui.statusbar.setVisible(self.config['mainWindow']['toggleStatusbar'])
        self.ui.tabWidget.setVisible(self.config['mainWindow']['toggleSelectionDetails'])

        self.ui.toggleMainToolbar.setChecked(self.config['mainWindow']['toggleMainToolbar'])
        self.ui.toggleSearchToolbar.setChecked(self.config['mainWindow']['toggleSearchToolbar'])
        self.ui.toggleBulkActionsToolbar.setChecked(self.config['mainWindow']['toggleBulkActionsToolbar'])
        self.ui.toggleSidebar.setChecked(self.config['mainWindow']['toggleSidebar'])
        self.ui.toggleStatusbar.setChecked(self.config['mainWindow']['toggleStatusbar'])
        self.ui.toggleSelectionDetails.setChecked(self.config['mainWindow']['toggleSelectionDetails'])

    def setVariables(self):
        self.tableArgs['tableType'] = None

        if self.config['db']['type'] == 'sqlite':
            self.ui.actionVacuumDatabase.setEnabled(True)
            self.ui.actionVacuumDatabase.setVisible(True)
        else:
            self.ui.actionVacuumDatabase.setEnabled(False)
            self.ui.actionVacuumDatabase.setVisible(False)

    def setCustomIcons(self):
        if os.path.exists(self.iconsDir):
            for iconName in os.listdir(self.iconsDir):
                iconPath = os.path.join(self.iconsDir,iconName)
                if os.path.isfile(iconPath):
                    iconBaseName = os.path.basename(iconName)
                    fileExtension = os.path.splitext(iconBaseName)[1][1:].lower().strip()
                    if fileExtension in self.defaultExtensions['image']:
                        icon = QIcon(iconPath)
                        if not icon.isNull():
                            self.icons[iconBaseName] = icon

    def setTreeModels(self):
        self.tableModel.setParent(self)
        self.treeModel.setParent(self)
        self.relationsModel = ÆRelationsTableModel(self)

    def initializeDatabase(self):
        if self.app.database is None:
            self.db = ÆDatabase(self.config['db'])
            self.db.appConfig = self.app.config
        elif QSqlDatabase.contains(self.app.database.con.connectionName()):
            self.db = self.app.database
            self.db.appConfig = self.app.config
            self.logger.debug("Using current database.")
        else:
            self.logger.error("Database Problem.")

    def setWindowSizeAndCentre(self):
        from PySide6.QtGui import QGuiApplication
        self.setMinimumSize(800, 600)
        qr = self.frameGeometry()
        cp = QGuiApplication.screenAt(QCursor().pos()).availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def constructRestOfUI(self):
        self.setAcceptDrops(True)
        self.ui.toolbuttonNew = QToolButton()
        self.ui.toolbuttonNew.setToolTip("New Actions")
        self.ui.toolbuttonNew.setMenu(self.ui.menuNew)
        self.ui.toolbuttonNew.setPopupMode(QToolButton.InstantPopup)
        self.ui.toolBar.insertWidget(self.ui.actionRefresh, self.ui.toolbuttonNew)

        self.ui.toolbuttonCopy = QToolButton()
        self.ui.toolbuttonCopy.setToolTip("Copy Actions")
        self.ui.menuCopyActions = QMenu()
        self.ui.menuCopyActions.addActions((self.ui.actionCopyFilePath, self.ui.actionCopypasta))
        self.ui.toolbuttonCopy.setMenu(self.ui.menuCopyActions)
        self.ui.toolbuttonCopy.setPopupMode(QToolButton.InstantPopup)
        self.ui.toolBar.insertWidget(self.ui.actionEdit, self.ui.toolbuttonCopy)

        self.ui.lineSearch = ÆButtonLineEdit(self.icons, clearEnabled=False)
        self.ui.lineSearch.setToolTip("Search Items")
        self.ui.lineSearch.setStatusTip("Select items in database with matching keywords")
        self.ui.lineSearch.setMaximumWidth(200)
        self.ui.lineSearch.setPlaceholderText('Search Items')
        self.ui.toolBarSearch.addWidget(self.ui.lineSearch)

        self.ui.comboBulkActions = QComboBox()
        self.ui.comboBulkActions.setToolTip("Select Bulk Action")
        self.ui.comboBulkActions.setStatusTip("Select bulk action to apply to checked rows")
        self.ui.comboBulkActions.setMaximumWidth(120)
        self.ui.comboBulkActions.addItem('Bulk Actions', 0)
        self.ui.comboBulkActions.addItem('Copypasta', 1)
        self.ui.comboBulkActions.addItem('Edit Items', 2)
        self.ui.comboBulkActions.addItem('Delete', 3)
        self.ui.comboBulkActions.addItem('Delete Relations', 4)
        self.ui.comboBulkActions.addItem('Delete with Files', 5)
        self.ui.toolBarBulkActions.insertWidget(self.ui.actionApplyBulkAction, self.ui.comboBulkActions)

        self.ui.menuListMenu = QMenu()
        self.ui.menuListMenu.addActions((self.ui.actionEditItemTypes, self.ui.actionEditTaxonomies))
        seperator = QAction(self)
        seperator.setSeparator(True)
        self.ui.menuListMenu.addAction(seperator)
        self.ui.menuListMenu.addAction(self.ui.actionRefreshMenu)

        self.ui.menuRelationsMenu = QMenu()
        self.ui.menuRelationsMenu.addActions((self.ui.actionViewRelation, self.ui.actionDeleteRelation))

        currentSizes = self.ui.splitter_2.sizes()
        currentSizes[1] = 170
        self.ui.splitter_2.setSizes(currentSizes)

        self.ui.treeView = ÆMainTreeView()
        self.ui.tableViewWidget.insertWidget(0, self.ui.treeView)

        self.ui.listView = ÆMainListView()
        self.ui.tableViewWidget.insertWidget(1, self.ui.listView)

        self.ui.tableSearchWidget.hide()
        self.ui.tableViewWidget.setCurrentIndex(0)
        self.currentView = self.ui.treeView

    def setTableViewMode(self, mode=None, refresh=True):
        if mode == "icons":
            self.ui.tableViewWidget.setCurrentIndex(1)
            self.ui.actionViewAsList.setChecked(False)
            self.ui.actionViewAsIcons.setChecked(True)
            self.tableViewMode = "icons"
            self.currentView = self.ui.listView
        else:
            self.ui.tableViewWidget.setCurrentIndex(0)
            self.ui.actionViewAsIcons.setChecked(False)
            self.ui.actionViewAsList.setChecked(True)
            self.tableViewMode = "list"
            self.currentView = self.ui.treeView
        if refresh:
            self.refreshTable()

    def setTableViewModeCategories(self, refresh=True):
        self.ui.tableViewWidget.setCurrentIndex(0)
        self.ui.actionViewAsIcons.setEnabled(False)
        self.ui.actionViewAsList.setEnabled(False)
        self.tableViewMode = "list"
        self.currentView = self.ui.treeView
        if refresh:
            self.refreshTable()

    def setTableViewModeItems(self, refresh=True):
        self.ui.actionViewAsIcons.setEnabled(True)
        self.ui.actionViewAsList.setEnabled(True)
        if self.ui.actionViewAsIcons.isChecked() and (self.tableViewMode == "list"):
            self.ui.tableViewWidget.setCurrentIndex(1)
            self.tableViewMode = "icons"
        else:
            self.tableViewMode = "list"
        if refresh:
            self.refreshTable()

    def getTableViewMode(self):
        if self.ui.actionViewAsIcons.isChecked():
            return "icons"
        else:
            return "list"

    def setCurrentView(self):
        if self.ui.actionViewAsIcons.isChecked():
            self.currentView = self.ui.listView
        else:
            self.currentView = self.ui.treeView

    def connectSignals(self):
        self.app.aboutToQuit.connect(self.exitApp)
        self.ui.actionExit.triggered.connect(self.close)
        self.ui.actionAbout.triggered.connect(self.openAboutDialog)
        self.ui.toggleMainToolbar.triggered.connect(self.toggleMainToolbar)
        self.ui.toggleSearchToolbar.triggered.connect(self.toggleSearchToolbar)
        self.ui.toggleBulkActionsToolbar.triggered.connect(self.toggleBulkActionsToolbar)
        self.ui.toggleSidebar.triggered.connect(self.toggleSidebar)
        self.ui.toggleStatusbar.triggered.connect(self.toggleStatusbar)
        self.ui.toggleSelectionDetails.triggered.connect(self.toggleSelectionDetails)
        self.ui.treeView.customContextMenuRequested.connect(self.treeViewContextMenu)
        self.ui.treeView.doubleClicked.connect(self.launchItem)
        self.ui.listView.customContextMenuRequested.connect(self.treeViewContextMenu)
        self.ui.listView.doubleClicked.connect(self.launchItem)
        self.ui.relationsTree.doubleClicked.connect(self.launchRelation)
        self.ui.toolBar.customContextMenuRequested.connect(self.toolbarContextMenu)
        self.ui.toolBarSearch.customContextMenuRequested.connect(self.toolbarContextMenu)
        self.ui.toolBarBulkActions.customContextMenuRequested.connect(self.toolbarContextMenu)
        self.ui.treeMenu.customContextMenuRequested.connect(self.menuListContextMenu)
        self.ui.actionAboutQt.triggered.connect(self.app.aboutQt)
        self.ui.actionViewItem.triggered.connect(self.launchItem)
        self.ui.buttonViewRelation.clicked.connect(self.launchRelation)
        self.ui.actionViewRelation.triggered.connect(self.launchRelation)
        self.ui.actionNewItem.triggered.connect(self.openNewItemDialog)
        self.ui.actionNewCategory.triggered.connect(self.openNewCategoryDialog)
        self.ui.actionRefresh.triggered.connect(self.refreshTable)
        self.ui.actionRefreshMenu.triggered.connect(self.refreshMenu)
        self.ui.actionDelete.triggered.connect(self.deleteSelection)
        self.ui.actionPreferences.triggered.connect(self.openPreferences)
        self.ui.actionDeleteAllData.triggered.connect(self.deleteAllData)
        self.ui.actionDropDatabase.triggered.connect(self.dropDatabase)
        self.ui.actionFullScreen.triggered.connect(self.toggleFullScreen)
        self.ui.actionDatabaseInfo.triggered.connect(self.viewDatabaseInfo)
        self.ui.actionEdit.triggered.connect(self.openEditDialog)
        self.ui.actionCloseDatabase.triggered.connect(self.closeDatabase)
        self.ui.actionNewSQLiteDatabase.triggered.connect(self.newSQLiteDatabase)
        self.ui.actionNewMySQLDatabase.triggered.connect(self.newMySQLDatabase)
        self.ui.actionOpenSQLiteDatabase.triggered.connect(self.openSQLiteDatabase)
        self.ui.actionOpenMySQLDatabase.triggered.connect(self.openMySQLDatabase)
        self.ui.buttonDeleteRelation.clicked.connect(self.deleteRelation)
        self.ui.actionDeleteRelation.triggered.connect(self.deleteRelation)
        self.ui.buttonDeleteAllRelations.clicked.connect(self.deleteAllRelations)
        self.ui.actionApplyBulkAction.triggered.connect(self.applyBulkAction)
        self.ui.actionBulkCopypasta.triggered.connect(lambda: self.applyBulkAction(1))
        self.ui.actionBulkEdit.triggered.connect(lambda: self.applyBulkAction(2))
        self.ui.actionBulkDelete.triggered.connect(lambda: self.applyBulkAction(3))
        self.ui.actionBulkDeleteRelations.triggered.connect(lambda: self.applyBulkAction(4))
        self.ui.actionBulkDeleteWithFiles.triggered.connect(lambda: self.applyBulkAction(5))
        self.ui.lineSearch.buttonClicked.connect(self.setSearchResults)
        self.ui.lineSearch.returnPressed.connect(self.setSearchResults)
        self.ui.actionImportXML.triggered.connect(self.openImportWizard)
        self.ui.actionExportXML.triggered.connect(self.openExportWizard)
        self.ui.actionItemChecker.triggered.connect(self.openItemChecker)
        self.ui.actionLinkChecker.triggered.connect(self.openLinkChecker)
        self.ui.actionOpenFolder.triggered.connect(self.launchDataFolder)
        self.ui.actionCreateSymbolicLinks.triggered.connect(self.openCreateLinksWizard)
        self.ui.actionFileManager.triggered.connect(self.openFileManager)
        self.ui.actionEditItemTypes.triggered.connect(lambda: self.openPreferences("Item Types"))
        self.ui.actionEditTaxonomies.triggered.connect(lambda: self.openPreferences("Taxonomies"))
        self.ui.actionCopypasta.triggered.connect(self.copypastaSelected)
        self.ui.actionAdvancedSearch.triggered.connect(self.openAdvancedSearch)
        self.ui.actionCopyFilePath.triggered.connect(self.copyFilePath)
        self.ui.actionSelectAll.triggered.connect(self.mainTreeSelectAll)
        self.ui.actionCheckSelected.triggered.connect(self.checkSelection)
        self.ui.actionUncheckSelected.triggered.connect(self.uncheckSelection)
        self.ui.actionCheckInvertSelected.triggered.connect(self.checkInvertSelection)
        self.ui.actionCheckAll.triggered.connect(self.checkAll)
        self.ui.actionUncheckAll.triggered.connect(self.checkNone)
        self.ui.actionCheckInvertAll.triggered.connect(self.checkInverse)
        self.ui.actionFind.triggered.connect(self.toggleTableSearch)
        self.ui.toolHideSearch.clicked.connect(self.toggleTableSearch)
        self.ui.lineFind.textEdited.connect(self.mainTreeSearch)
        self.ui.toolSelectAll.clicked.connect(self.mainTreeSelectAllSearchResults)
        self.ui.toolPreviousResult.clicked.connect(self.mainTreeSelectPreviousResult)
        self.ui.toolNextResult.clicked.connect(self.mainTreeSelectNextResult)
        self.ui.actionHelpContents.triggered.connect(self.openHelpBrowser)
        self.ui.relationsTree.customContextMenuRequested.connect(self.relationsTreeContextMenu)
        self.ui.actionVacuumDatabase.triggered.connect(self.vacuumDatabase)
        self.ui.actionRecountRelations.triggered.connect(self.openRelationsRecounter)
        self.ui.actionShowLogFile.triggered.connect(self.openLogFile)
        self.ui.actionOpenConfigFolder.triggered.connect(self.openConfigFolder)
        self.ui.menuOpenWith.triggered.connect(self.openItemInCustomApplication)
        self.ui.actionViewAsList.triggered.connect(self.setTableViewMode)
        self.ui.actionViewAsIcons.triggered.connect(lambda: self.setTableViewMode("icons"))

    def writeDatabaseOptions(self):
        if self.db:
            self.writeItemTypesAndTaxonomies()
            self.db.open()
            self.db.transaction()
            for option, value in self.config['options'].items():
                self.db.insertOption(option, quote(str(value)))
            self.db.commit()
            self.db.close()
            if self.db.error is None:
                self.logger.debug('Database options written.')

    def setConfig(self, config=None):
        self.config = self.app.config
        if config:
            for key, value in config.items():
                self.config[key] = value
                self.logger.debug("Inherited Configuration: "+key+": "+str(self.config[key]))

        self.initializeDatabase()
        self.readDatabaseOptions()
        self.readItemTypesAndTaxonomies()

    def readDatabaseOptions(self):
        self.db.open()
        options = self.db.selectOptions()
        if options:
            if not self.config.get('options'):
                self.config['options'] = dict()
                self.config['options']['relativeDataDir'] = False
                if self.app.portableMode:
                    self.config['options']['defaultDataDir'] = "./fallback project data/"
                else:
                    self.config['options']['defaultDataDir'] = \
                        os.path.dirname(QSettings().fileName())+"/fallback project data/"
                if not os.path.exists(self.config['options']['defaultDataDir']):
                    os.mkdir(self.config['options']['defaultDataDir'])
                self.config['options']['catLvls'] = const.MAXCATLVLS
            while options.next():
                self.config['options'][options.value(0)] = unquote(options.value(1))
            try:
                self.config['options']['catLvls'] = int(self.config['options']['catLvls'])
                self.config['options']['relativeDataDir'] = convToBool(self.config['options']['relativeDataDir'], False)
            except KeyError:
                pass

            if not os.path.isabs(self.config['options']['defaultDataDir']) and self.db.config['type'] == "sqlite":
                databaseDir = os.path.dirname(self.db.config['db'])
                dataFolder = os.path.basename(os.path.normpath(self.config['options']['defaultDataDir']))
                relativeDataPath = os.path.join(databaseDir, dataFolder)
                self.config['options']['defaultDataDir'] = relativeDataPath
                self.logger.debug("New Relative Data Dir:" + relativeDataPath)
            self.config['options']['defaultDataDir'] = os.path.join(self.config['options']['defaultDataDir'],"")
        self.db.close()

    def writeItemTypesAndTaxonomies(self):
        self.db.open()
        self.db.transaction()
        self.db.deleteItemTypes()
        self.db.deleteTaxonomies()
        for itemType in self.config['itemTypes']:
            data = dict()
            data['noun_name'] = itemType.nounName
            data['plural_name'] = itemType.pluralName
            data['dir_name'] = itemType.dirName
            data['table_name'] = itemType.tableName
            data['icon_name'] = quote(itemType.iconName)
            data['enabled'] = int(itemType.enabled)
            data['extensions'] = ', '.join(itemType.extensions)
            self.db.insertItemType(data)
        for taxonomy in self.config['taxonomies']:
            data = dict()
            data['noun_name'] = taxonomy.nounName
            data['plural_name'] = taxonomy.pluralName
            data['dir_name'] = taxonomy.dirName
            data['table_name'] = taxonomy.tableName
            data['icon_name'] = quote(taxonomy.iconName)
            data['enabled'] = int(taxonomy.enabled)
            data['has_children'] = int(taxonomy.hasChildren)
            data['is_tags'] = int(taxonomy.isTags)
            self.db.insertTaxonomy(data)
        self.db.commit()
        if self.db.error is None:
            self.logger.debug('Item types and taxonomies written to database.')
        self.db.close()

    def readItemTypesAndTaxonomies(self):
        self.db.open()

        if self.config.get('itemTypes'):
            self.config['itemTypes'].clear()
        else:
            self.config['itemTypes'] = ÆItemTypeList()
        itemTypesQuery = self.db.selectItemTypes()
        while itemTypesQuery.next():
            itemType = ÆItemType()
            itemType.setNounName(itemTypesQuery.value(1))
            itemType.setPluralName(itemTypesQuery.value(2))
            itemType.setDirName(itemTypesQuery.value(3))
            itemType.setTableName(itemTypesQuery.value(4))
            itemType.setIconName(unquote(itemTypesQuery.value(5)))
            itemType.setEnabled(int(itemTypesQuery.value(6)))
            reader = csv.reader([itemTypesQuery.value(7)], skipinitialspace=True)
            for extensions in reader:
                if extensions:
                    itemType.setExtensions(extensions)
                    if itemType.hasExtension("html") and itemType.hasExtension("htm"):
                        itemType.isWebpages = True
                else:
                    itemType.isWeblinks = True
            self.config['itemTypes'].append(itemType)
        if not self.config.get('itemTypes') or len(self.config['itemTypes']) is 0:
            self.config['itemTypes'] = self.createDefaultItemTypes()

        if self.config.get('taxonomies'):
                self.config['taxonomies'].clear()
        else:
            self.config['taxonomies'] = ÆTaxonomyList()
        taxonomiesQuery = self.db.selectTaxonomies()
        while taxonomiesQuery.next():
            taxonomy = ÆTaxonomy()
            taxonomy.setNounName(taxonomiesQuery.value(1))
            taxonomy.setPluralName(taxonomiesQuery.value(2))
            taxonomy.setDirName(taxonomiesQuery.value(3))
            taxonomy.setTableName(taxonomiesQuery.value(4))
            taxonomy.setIconName(unquote(taxonomiesQuery.value(5)))
            taxonomy.setEnabled(int(taxonomiesQuery.value(6)))
            taxonomy.setHasChildren(int(taxonomiesQuery.value(7)))
            taxonomy.setIsTags(int(taxonomiesQuery.value(8)))
            self.config['taxonomies'].append(taxonomy)
        if not self.config.get('taxonomies') or len(self.config['taxonomies']) is 0:
            self.config['taxonomies'] = self.createDefaultTaxonomies()

        self.db.close()

    def setIcons(self):
        self.ui.menuNewDatabase.setIcon(self.icons['DatabaseNew'])
        self.ui.actionNewSQLiteDatabase.setIcon(self.icons['DatabaseNew'])
        self.ui.actionNewMySQLDatabase.setIcon(self.icons['DatabaseNew'])
        self.ui.menuOpenDatabase.setIcon(self.icons['DatabaseOpen'])
        self.ui.actionOpenSQLiteDatabase.setIcon(self.icons['DatabaseOpen'])
        self.ui.actionOpenMySQLDatabase.setIcon(self.icons['DatabaseOpen'])
        self.ui.actionExit.setIcon(self.icons['Exit'])
        self.ui.actionAbout.setIcon(self.icons['About'])
        self.ui.actionNewItem.setIcon(self.icons['Add2'])
        self.ui.actionNewCategory.setIcon(self.icons['Add2'])
        self.ui.actionEdit.setIcon(self.icons['Edit'])
        self.ui.actionDelete.setIcon(self.icons['Remove'])
        self.ui.actionRefresh.setIcon(self.icons['Refresh'])
        self.ui.actionRefreshMenu.setIcon(self.icons['Refresh'])
        self.ui.actionViewItem.setIcon(self.icons['Play'])
        self.ui.menuOpenWith.setIcon(self.icons['Play'])
        self.ui.actionCloseDatabase.setIcon(self.icons['DatabaseClose'])
        self.ui.actionPreferences.setIcon(self.icons['Preferences'])
        self.ui.actionDeleteAllData.setIcon(self.icons['DatabaseDrop'])
        self.ui.actionDropDatabase.setIcon(self.icons['DatabaseDrop'])
        self.ui.actionDatabaseInfo.setIcon(self.icons['DatabaseInfo'])
        self.ui.tabWidget.setTabIcon(0, self.icons['Details'])
        self.ui.tabWidget.setTabIcon(1, self.icons['Relations'])
        self.ui.tabWidget.setTabIcon(2, self.icons['Options'])
        self.ui.menuNew.setIcon(self.icons['Add'])
        self.ui.toolbuttonNew.setIcon(self.icons['Add'])
        self.ui.toolbuttonCopy.setIcon(self.icons['Copy'])
        self.ui.actionFullScreen.setIcon(self.icons['Fullscreen'])
        self.ui.buttonDeleteAllRelations.setIcon(self.icons['Remove'])
        self.ui.buttonDeleteRelation.setIcon(self.icons['Remove'])
        self.ui.actionDeleteRelation.setIcon(self.icons['Remove'])
        self.ui.actionApplyBulkAction.setIcon(self.icons['Execute'])
        self.ui.actionBulkDelete.setIcon(self.icons['Remove'])
        self.ui.actionBulkDeleteRelations.setIcon(self.icons['Remove'])
        self.ui.actionBulkDeleteWithFiles.setIcon(self.icons['Remove'])
        self.ui.actionBulkCopypasta.setIcon(self.icons['Copy'])
        self.ui.actionBulkEdit.setIcon(self.icons['Edit'])
        self.ui.menuBulkActions.setIcon(self.icons['Execute'])
        self.ui.comboBulkActions.setItemIcon(1, self.icons['Copy'])
        self.ui.comboBulkActions.setItemIcon(2, self.icons['Edit'])
        self.ui.comboBulkActions.setItemIcon(3, self.icons['Remove'])
        self.ui.comboBulkActions.setItemIcon(4, self.icons['Remove'])
        self.ui.comboBulkActions.setItemIcon(5, self.icons['Remove'])
        self.ui.actionAdvancedSearch.setIcon(self.icons['Search'])
        self.ui.buttonViewRelation.setIcon(self.icons['Play'])
        self.ui.actionViewRelation.setIcon(self.icons['Play'])
        self.ui.menuImport.setIcon(self.icons['Import'])
        self.ui.menuExport.setIcon(self.icons['Export'])
        self.ui.actionImportXML.setIcon(self.icons['XMLImport'])
        self.ui.actionExportXML.setIcon(self.icons['XMLExport'])
        self.ui.actionItemChecker.setIcon(self.icons['FileChecker'])
        self.ui.actionLinkChecker.setIcon(self.icons['FileChecker'])
        self.ui.actionOpenFolder.setIcon(self.icons['Folder'])
        self.ui.actionCreateSymbolicLinks.setIcon(self.icons['SymbolicLink'])
        self.ui.actionEditItemTypes.setIcon(self.icons['Items'])
        self.ui.actionEditTaxonomies.setIcon(self.icons['Categories'])
        self.ui.actionFileManager.setIcon(self.icons['FileManager'])
        self.ui.lineSearch.button.setIcon(self.icons['Search'])
        self.ui.actionCopypasta.setIcon(self.icons['Copy'])
        self.ui.actionCopyFilePath.setIcon(self.icons['Copy'])
        self.ui.actionSelectAll.setIcon(self.icons['SelectAll'])
        self.ui.actionCheckSelected.setIcon(self.icons['CheckAll'])
        self.ui.actionUncheckSelected.setIcon(self.icons['CheckNone'])
        self.ui.actionCheckInvertSelected.setIcon(self.icons['CheckInverse'])
        self.ui.actionCheckAll.setIcon(self.icons['CheckAll'])
        self.ui.actionUncheckAll.setIcon(self.icons['CheckNone'])
        self.ui.actionCheckInvertAll.setIcon(self.icons['CheckInverse'])
        self.ui.actionFind.setIcon(self.icons['Find'])
        self.ui.toolHideSearch.setIcon(self.icons['Remove'])
        self.ui.toolNextResult.setIcon(self.icons['Down'])
        self.ui.toolPreviousResult.setIcon(self.icons['Up'])
        self.ui.toolSelectAll.setIcon(self.icons['SelectAll'])
        self.ui.actionAboutQt.setIcon(self.icons['Qt'])
        self.ui.actionHelpContents.setIcon(self.icons['HelpContents'])
        self.ui.actionRecountRelations.setIcon(self.icons['Relations'])

    def setIconTheme(self):
        treeIconNames =\
            self.config['itemTypes'].nounNames() + \
            self.config['taxonomies'].nounNames() + \
            list(('Success', 'Warning'))
        self.app.iconsList.setTreeIconNames(treeIconNames)
        self.app.iconsList.setTreeIcons()

        self.config['itemTypes'].validateIcons(self.app.iconsList.icons, 'Items')
        self.config['taxonomies'].validateIcons(self.app.iconsList.icons, 'Categories')
        self.logger.debug("Icon Theme Set.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.deleteKeyPressed()
        else:
            super().keyPressEvent(event)

    def deleteKeyPressed(self):
        if self.ui.relationsTree.selectedIndexes():
            self.deleteRelation()
        elif self.currentView.selectedIndexes():
            self.deleteSelection()

    def displayMenu(self):
        self.ui.treeMenu.setModel(None)
        self.menuModel.clear()

        items = QStandardItem(self.icons['Items'], "Items")
        for itemType in self.config['itemTypes']:
            if itemType.enabled is True:
                items.appendRow(QStandardItem(self.icons[itemType.iconName], itemType.pluralName))
        categories = QStandardItem(self.icons['Categories'], "Categories")
        for taxonomy in self.config['taxonomies']:
            if taxonomy.enabled is True:
                categories.appendRow(QStandardItem(self.icons[taxonomy.iconName], taxonomy.pluralName))

        self.menuModel.appendRow(items)
        self.menuModel.appendRow(categories)
        if self.advancedSearchSQL or self.searchPhrase:
            searchResultsItem = QStandardItem(self.icons['Search'], "Search Results")
            self.menuModel.appendRow(searchResultsItem)
        if len(self.missingFiles) > 0:
            missingFilesItem = QStandardItem(self.icons['Warning'], "Missing Files")
            self.menuModel.appendRow(missingFilesItem)
        if len(self.brokenLinks) > 0:
            brokenLinksItem = QStandardItem(self.icons['Warning'], "Broken Links")
            self.menuModel.appendRow(brokenLinksItem)
        self.ui.treeMenu.setModel(self.menuModel)
        self.ui.treeMenu.expandAll()

        index = self.ui.treeMenu.model().index(0, 0)
        self.ui.treeMenu.setCurrentIndex(index)

        try:
            selectionModel = self.ui.treeMenu.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeMenuSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

    def displayItems(self, data=None):
        if self.timer is None:
            self.timer = QElapsedTimer()
            self.timer.start()
        else:
            self.timer.restart()

        noExtraQuery = None
        sqlWhere, sqlCat = str(), str()

        self.tableArgs['query'] = data

        itemTypes = self.config['itemTypes'].tableNames(Æ.OnlyDisabled)
        if self.tableArgs['query']:
            if self.tableArgs['query'].get('type_id'):
                sqlWhere = "WHERE type_id = '{}'".format(self.tableArgs['query']['type_id'])
            else:
                sqlWhere = "WHERE type_id NOT IN ('{}') ".format("', '".join(itemTypes))
            if self.tableArgs['query'].get('cat'):
                sqlCat = "INNER JOIN term_relationships as tr on (tr.item_id = i.item_id) " \
                         "AND (tr.term_id = '{}')".format(self.tableArgs['query']['cat'])
                if not self.tableArgs['query'].get('catName'):
                    SQL = 'SELECT t.term_name FROM terms AS t ' \
                          'WHERE t.term_id = "{}"'.format(self.tableArgs['query']['cat'])
                    query = QSqlQuery(SQL, self.db.con)
                    if query.first():
                        self.tableArgs['query']['catName'] = query.value(0)
        else:
            noExtraQuery = 1
            self.tableArgs['query'] = None
            sqlWhere = "WHERE type_id NOT IN ('{}') ".format("', '".join(itemTypes))
        SQL = "SELECT i.item_id AS 'ID', item_name AS 'Name', \n" \
              "type_id AS 'Type', item_time AS 'Time', item_source AS 'Source' \n" \
              "FROM items AS i {}{} \n" \
              "ORDER BY i.item_id ASC".format(str(sqlCat), str(sqlWhere))
        self.logger.debug('\n'+SQL)

        self.tableModel.viewMode = self.getTableViewMode()
        self.setTableViewModeItems(refresh=False)

        self.defColumns = ("Iden", "Name", "Type", "Time", "Source")
        self.tableModel.clear()
        self.treeModel.clear()
        self.tableModel.setTableType(Æ.TableItems)
        self.tableModel.setColNames(self.defColumns)
        self.tableModel.setQuery(SQL, self.db)
        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.tableModel)
        if not self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            self.currentView.setColumnWidth(0, 100)
            self.currentView.setColumnWidth(1, 450)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 170)
            self.currentView.setRootIsDecorated(False)
            self.currentView.setItemsExpandable(False)

        self.tableArgs['tableType'] = Æ.TableItems
        self.setCurrentView()

        if noExtraQuery is 1:
            self.ui.tableTitle.setText("<b>All Items</b>")
        else:
            titleText = "Items"
            if sqlCat is not '':
                titleText += " on ‘{}’".format(self.tableArgs['query']['catName'])
            if self.tableArgs['query'].get('type_id'):
                titleText += " of type ‘{}’".format(
                    self.config['itemTypes'].nounFromTable(self.tableArgs['query']['type_id']))
            self.ui.tableTitle.setText("<b>"+titleText+"</b>")
        self.ui.tableTitle.textFormat()
        rowCount = self.currentView.model().rowCount()
        if rowCount is 1:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.tableStatus.textFormat()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

        self.logger.debug("Elapsed Time: "+str(round(self.timer.elapsed()/1000, 3))+" Seconds")
        self.onTreeModelUpdated()

    def displayCategories(self, data=None):
        self.setTableViewModeCategories(refresh=False)
        if self.timer is None:
            self.timer = QElapsedTimer()
            self.timer.start()
        else:
            self.timer.restart()

        noExtraQuery = None
        self.tableArgs['query'] = data

        taxonomies = self.config['taxonomies'].tableNames(Æ.OnlyDisabled)
        if self.tableArgs['query']:
            if self.tableArgs['query'].get('term_tax'):
                sqlextra = "root.term_taxonomy = '{}'".format(self.tableArgs['query']['term_tax'])
                self.tableArgs['query']['term_tax'] = self.tableArgs['query']['term_tax']
            else:
                sqlextra = "root.term_taxonomy NOT IN ('{}')".format("', '".join(taxonomies))
        else:
            sqlextra = "root.term_taxonomy NOT IN ('{}')".format("', '".join(taxonomies))
            noExtraQuery = 1
            self.tableArgs['query'] = None

        self.defColumns = ("Name", "Iden", "Taxonomy", "Count", "Slug")

        self.tableModel.clear()
        self.treeModel.clear()
        self.treeModel.setTableType(Æ.TableCategories)
        self.treeModel.setColNames(self.defColumns)
        self.treeModel.setupModelData(sqlextra, self.db)

        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.treeModel)

        if not self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            # self.currentView.setColumnWidth(0, 450)
            self.currentView.setColumnWidth(1, 100)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 100)
            self.currentView.setColumnWidth(4, 200)
            self.currentView.setRootIsDecorated(True)
            self.currentView.setItemsExpandable(True)
        self.tableArgs['tableType'] = Æ.TableCategories
        self.currentView.resizeColumnToContents(0)

        if noExtraQuery is 1:
            self.ui.tableTitle.setText("<b>All Categories</b>")
        else:
            if self.tableArgs['query'].get('term_tax'):
                self.ui.tableTitle.setText("<b>Categories with taxonomy ‘{}’</b>"
                .format(self.config['taxonomies'].nounFromTable(self.tableArgs['query']['term_tax'])))

        self.ui.tableTitle.textFormat()
        count = self.treeModel.rowCount()
        if count == 1:
            self.ui.tableStatus.setText("<b>"+str(count)+" Category</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(count)+" Categories</b>")
        self.ui.tableStatus.textFormat()
        self.db.close()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
            pass

        self.logger.debug("Elapsed Time: "+str(round(self.timer.elapsed()/1000, 3))+" Seconds")
        self.onTreeModelUpdated()

    def displayRelations(self, selectedID, sqlextra=""):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            SQL = "SELECT t.term_name AS 'Name', t.term_taxonomy AS 'Taxonomy', \n" \
                  "t.term_id AS 'termID' \n" \
                  "FROM term_relationships AS tr \n" \
                  "INNER JOIN terms AS t ON t.term_id = tr.term_id \n" \
                  "WHERE (tr.item_id = {}) {}""".format(selectedID, sqlextra)
            self.logger.debug('\n'+SQL)

            defColumns = ("Name", "Taxonomy", "Term ID")

            self.ui.relationsTree.setModel(None)
            self.relationsModel.clear()
            self.relationsModel.setTableType("Categories")
            self.relationsModel.setColNames(defColumns)
            self.relationsModel.setQuery(SQL, self.db)

            self.ui.relationsTree.setModel(self.relationsModel)
            self.ui.relationsTree.resizeColumnToContents(0)
            self.ui.relationsTree.header().hideSection(2)

            relationsCount = self.relationsModel.rowCount()
            self.ui.labelRelationsCount.setText(str(relationsCount)+" Relations")
            if relationsCount > 0:
                self.ui.buttonDeleteAllRelations.setEnabled(True)
            else:
                self.ui.buttonDeleteAllRelations.setEnabled(False)
            self.ui.buttonDeleteRelation.setEnabled(False)
            self.ui.buttonViewRelation.setEnabled(False)

            try:
                selectionModel = self.ui.relationsTree.selectionModel()
                selectionModel.selectionChanged.connect(self.onRelationsTreeSelectionChanged, Qt.UniqueConnection)
            except RuntimeError:
                pass

        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            SQL = """SELECT i.item_name AS "Name", i.type_id AS "Type",
                i.item_id AS "itemID", i.item_source AS 'Source', i.item_time AS 'Time'
                FROM term_relationships AS tr
                INNER JOIN items AS i ON i.item_id = tr.item_id
                WHERE (tr.term_id = {}) {}""".format(selectedID, sqlextra)

            defColumns = ("Name", "Type", "Item Iden", "Source")

            self.ui.relationsTree.setModel(None)
            self.relationsModel.clear()
            self.relationsModel.setTableType("Items")
            self.relationsModel.setColNames(defColumns)
            self.relationsModel.setQuery(SQL, self.db)

            self.ui.relationsTree.setModel(self.relationsModel)
            self.ui.relationsTree.setColumnWidth(0, 500)
            self.ui.relationsTree.header().hideSection(2)
            self.ui.relationsTree.header().hideSection(3)

            relationsCount = self.relationsModel.rowCount()
            self.ui.labelRelationsCount.setText(str(relationsCount)+" Relations")
            if relationsCount > 0:
                self.ui.buttonDeleteAllRelations.setEnabled(True)
            else:
                self.ui.buttonDeleteAllRelations.setEnabled(False)
            self.ui.buttonDeleteRelation.setEnabled(False)
            self.ui.buttonViewRelation.setEnabled(False)

            try:
                selectionModel = self.ui.relationsTree.selectionModel()
                selectionModel.selectionChanged.connect(self.onRelationsTreeSelectionChanged, Qt.UniqueConnection)
            except RuntimeError:
                pass

    def displayNothing(self):
        self.ui.treeMenu.clearSelection()
        self.currentView.setModel(None)
        self.ui.tableTitle.setText(None)
        self.ui.tableStatus.setText(None)
        self.logger.debug("You Selected Nothing")
        self.onTreeViewSelectionChanged()
        self.tableArgs['tableType'] = False

    def displayTabsItems(self):
        self.db.open()
        self.ui.detailsGrid.setColumnStretch(1, 1)

        selectedItem = self.returnSelectedItem(0)
        self.displayRelations(selectedItem)

        gridRow = 0
        for c, colname in enumerate(self.defColumns):
            selectedItem = self.returnSelectedItem(c)
            if selectedItem not in ('', None):
                if colname in ('Source',):
                    selectedItem = '<a href="{0}">{0}</a>'.format(selectedItem)
                    self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setOpenExternalLinks(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setText("<b>"+colname+": </b>")
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().textFormat()
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setText(selectedItem)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().textFormat()
                gridRow += 1

        selectedItem = self.returnSelectedItem(0)
        query = QSqlQuery(
            """SELECT item_description
            FROM items AS i WHERE (i.item_id = {})""".format(selectedItem), self.db.con)
        if query.first():
            description = query.value(0)
            if description not in ('', None):
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setText("<b>Description: </b>")
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setText(unquote(description))
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().textFormat()
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().textFormat()
                gridRow += 1
            else:
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(False)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(False)

        if not self.returnSelectedItem(2) in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
            folderPath = str(self.config['options']['defaultDataDir']) \
                + self.config['itemTypes'].dirFromNoun(self.returnSelectedItem(2)) + "/"
            self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(True)
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(True)
            self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setText("<b>Folder Path: </b>")
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setText('<a href="{0}">{0}</a>'.format(folderPath))
            self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().textFormat()
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().textFormat()
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setOpenExternalLinks(False)
            try:
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().linkActivated.connect(
                    self.launchDataFolder, Qt.UniqueConnection)
            except RuntimeError:
                pass
            gridRow += 1
        else:
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setOpenExternalLinks(True)

        while gridRow+1 <= self.ui.detailsGrid.rowCount():
            self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(False)
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(False)
            gridRow += 1

        self.db.close()

    def displayTabsCategories(self):
        self.db.open()
        self.ui.detailsGrid.setColumnStretch(1, 1)

        selectedItem = self.returnSelectedItem(1)
        self.displayRelations(selectedItem)

        gridRow = 0
        for c, colname in enumerate(self.defColumns):
            selectedItem = self.returnSelectedItem(c)
            if selectedItem not in ('', None):
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setText("<b>"+colname+": </b>")
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().textFormat()
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setText(selectedItem)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().textFormat()
                gridRow += 1

        selectedItem = self.returnSelectedItem(1)
        query = QSqlQuery(
            """SELECT term_description
            FROM terms AS t WHERE (t.term_id = {})""".format(selectedItem),
            self.db.con)
        if query.first():
            description = query.value(0)
            if description not in ('', None):
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(True)
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setText("<b>Description: </b>")
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setText(unquote(description))
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().textFormat()
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().textFormat()
                gridRow += 1
            else:
                self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(False)
                self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(False)

        while gridRow+1 <= self.ui.detailsGrid.rowCount():
            self.ui.detailsGrid.itemAtPosition(gridRow, 0).widget().setVisible(False)
            self.ui.detailsGrid.itemAtPosition(gridRow, 1).widget().setVisible(False)
            gridRow += 1

        self.db.close()

    def displaySearchResults(self):
        searchWords = self.searchPhrase.split()
        i = 0

        SQL = "SELECT item_id AS 'ID', item_name AS 'Name', " \
              "type_id AS 'Type', item_time AS 'Time', item_source AS 'Source' FROM items "
        SQLWhere = "WHERE (items.item_id is not NULL)"
        for word in searchWords:
            word = æscape(word)
            i += 1
            if i is 1:
                SQLWhere += " AND (item_name LIKE '%{}%' ".format(word)
            else:
                SQLWhere += "AND item_name LIKE '%{}%' ".format(word)
        SQLWhere += ") "
        SQL += SQLWhere+" ORDER BY item_id ASC"

        self.tableModel.viewMode = self.getTableViewMode()
        self.setTableViewModeItems(refresh=False)

        self.defColumns = ("Iden", "Name", "Type", "Time", "Source")
        self.tableModel.clear()
        self.treeModel.clear()
        self.tableModel.setTableType(Æ.TableSearch)
        self.tableModel.setColNames(self.defColumns)
        self.tableModel.setQuery(SQL, self.db)
        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.tableModel)
        if not self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            self.currentView.setColumnWidth(0, 100)
            self.currentView.setColumnWidth(1, 450)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 170)
            self.currentView.setRootIsDecorated(False)
            self.currentView.setItemsExpandable(False)
        self.tableArgs['tableType'] = Æ.TableSearch

        self.setCurrentView()

        self.ui.tableTitle.setText("<b>Search Results for ‘{}’</b>".format(self.searchPhrase))
        self.ui.tableTitle.textFormat()
        rowCount = self.currentView.model().rowCount()
        if rowCount is 1:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.tableStatus.textFormat()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
                pass

        self.logger.info("Search Results Displayed for '{}'".format(self.searchPhrase))
        self.onTreeModelUpdated()

    def displayAdvancedSearch(self):
        self.tableModel.viewMode = self.getTableViewMode()
        self.setTableViewModeItems(refresh=False)

        self.defColumns = ("Iden", "Name", "Type", "Time", "Source")
        self.logger.debug('\n'+self.advancedSearchSQL)

        ##self.tableModel.viewMode = self.tableViewMode
        self.tableModel.clear()
        self.treeModel.clear()
        self.tableModel.setTableType(Æ.TableSearch)
        self.tableModel.setColNames(self.defColumns)
        self.tableModel.setQuery(self.advancedSearchSQL, self.db)
        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.tableModel)
        if not self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            self.currentView.setColumnWidth(0, 100)
            self.currentView.setColumnWidth(1, 450)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 170)
            self.currentView.setRootIsDecorated(False)
            self.currentView.setItemsExpandable(False)
        self.tableArgs['tableType'] = Æ.TableSearch
        self.setCurrentView()

        self.ui.tableTitle.setText("<b>Advanced Search Results</b>")
        self.ui.tableTitle.textFormat()
        rowCount = self.currentView.model().rowCount()
        if rowCount is 1:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.tableStatus.textFormat()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
                pass

        self.logger.info("Advanced Search Results Displayed")
        self.onTreeModelUpdated()

    def displayMissingFiles(self):
        if len(self.missingFiles) < 1:
            self.displayNothing()
            return

        SQL = "SELECT i.item_id AS 'ID', item_name AS 'Name', \n" \
              "type_id AS 'Type', item_time AS 'Time', item_source AS 'Source' \n" \
              "FROM items AS i WHERE item_id IN ({}) \n" \
              "ORDER BY i.item_id ASC".format(", ".join(self.missingFiles))
        self.logger.debug('\n'+SQL)

        self.tableModel.viewMode = self.getTableViewMode()
        self.setTableViewModeItems(refresh=False)

        self.defColumns = ("Iden", "Name", "Type", "Time", "Source")
        ##self.tableModel.viewMode = self.tableViewMode
        self.tableModel.clear()
        self.treeModel.clear()
        self.tableModel.setTableType(Æ.TableSearch)
        self.tableModel.setColNames(self.defColumns)
        self.tableModel.setQuery(SQL, self.db)
        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.tableModel)
        if not self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            self.currentView.setColumnWidth(0, 100)
            self.currentView.setColumnWidth(1, 450)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 170)
            self.currentView.setRootIsDecorated(False)
            self.currentView.setItemsExpandable(False)
        self.tableArgs['tableType'] = Æ.TableMissing
        self.setCurrentView()

        self.ui.tableTitle.setText("<b>Items with Missing Files</b>")
        self.ui.tableTitle.textFormat()

        rowCount = self.currentView.model().rowCount()
        if rowCount is 1:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.tableStatus.textFormat()
        self.db.close()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
                pass
        self.onTreeModelUpdated()

    def displayBrokenLinks(self):
        if len(self.brokenLinks) < 1:
            self.displayNothing()
            return

        SQL = "SELECT i.item_id AS 'ID', item_name AS 'Name', \n" \
              "type_id AS 'Type', item_time AS 'Time', item_source AS 'Source' \n" \
              "FROM items AS i WHERE item_id IN ({}) \n" \
              "ORDER BY i.item_id ASC".format(", ".join(self.brokenLinks))
        self.logger.debug('\n'+SQL)

        self.tableModel.viewMode = self.getTableViewMode()
        self.setTableViewModeItems(refresh=False)

        self.defColumns = ("Iden", "Name", "Type", "Time", "Source")
        self.tableModel.clear()
        self.treeModel.clear()
        self.tableModel.setTableType(Æ.TableSearch)
        self.tableModel.setColNames(self.defColumns)
        self.tableModel.setQuery(SQL, self.db)
        self.ui.lineFind.clear()
        self.currentView.clearSearchResults()
        self.currentView.clearSelection()
        self.currentView.setModel(self.tableModel)
        if not self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.currentView.reset()
            self.currentView.sortByColumn(3, Qt.AscendingOrder)
            self.currentView.setColumnWidth(0, 100)
            self.currentView.setColumnWidth(1, 450)
            self.currentView.setColumnWidth(2, 110)
            self.currentView.setColumnWidth(3, 170)
            self.currentView.setRootIsDecorated(False)
            self.currentView.setItemsExpandable(False)
        self.tableArgs['tableType'] = Æ.TableBrokenLinks
        self.setCurrentView()

        self.ui.tableTitle.setText("<b>Items with Broken Links</b>")
        self.ui.tableTitle.textFormat()

        rowCount = self.currentView.model().rowCount()
        if rowCount is 1:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Item</b>")
        else:
            self.ui.tableStatus.setText("<b>"+str(rowCount)+" Items</b>")
        self.ui.tableStatus.textFormat()
        self.db.close()

        try:
            selectionModel = self.currentView.selectionModel()
            selectionModel.selectionChanged.connect(self.onTreeViewSelectionChanged, Qt.UniqueConnection)
        except RuntimeError:
                pass
        self.onTreeModelUpdated()

    def returnSelectedItem(self, col=0):
        indexes = self.currentView.selectedIndexes()
        if indexes:
            index = indexes[0]
            row = index.row()
            parent = index.parent()
            if (self.ui.actionViewAsIcons.isChecked() and self.ui.actionViewAsIcons.isEnabled()) and col is 0:
                data = self.mainTreeModel().rows[row][col+1]
            else:
                data = self.mainTreeModel().data(self.mainTreeModel().index(row, col, parent), role=Qt.DisplayRole)
            if isinstance(data, QDateTime):
                return data.toString('yyyy-MM-dd hh:mm:ss')
            elif not isinstance(data, str):
                return str(data)
            elif data == "0000-00-00 00:00:00":
                return None
            else:
                return data

    def mainTreeSelectedRows(self):
        indexes = self.currentView.selectedIndexes()
        if indexes:
            rows = set([i.row() for i in indexes])
        else:
            rows = set()
        return rows

    def mainTreeSelectedIndexes(self):
        indexes = self.currentView.selectedIndexes()
        newIndexes = list()
        if indexes:
            for i in indexes:
                if i.column() is 1:
                    newIndexes.append(i)
        return newIndexes

    def onTreeMenuSelectionChanged(self):
        indexes = self.ui.treeMenu.selectedIndexes()
        if indexes:
            selectedItem = indexes[0].model().itemFromIndex(indexes[0])
            if selectedItem.data(0) is not None:
                if selectedItem.data(0) == "Items":
                    self.displayItems()
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected Items")
                elif self.config['itemTypes'][selectedItem.data(0)]:
                    tableName = self.config['itemTypes'][selectedItem.data(0)].tableName
                    self.displayItems(dict(type_id=tableName))
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected "+selectedItem.data(0))
                elif selectedItem.data(0) == "Categories":
                    self.displayCategories()
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected Categories")
                elif self.config['taxonomies'][selectedItem.data(0)]:
                    tableName = self.config['taxonomies'][selectedItem.data(0)].tableName
                    self.displayCategories(dict(term_tax=tableName))
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected "+selectedItem.data(0))
                elif selectedItem.data(0) == "Search Results":
                    if self.advancedSearchSQL:
                        self.displayAdvancedSearch()
                    else:
                        self.displaySearchResults()
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected Search Results")
                elif selectedItem.data(0) == "Missing Files":
                    self.displayMissingFiles()
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected Missing Files")
                elif selectedItem.data(0) == "Broken Links":
                    self.displayBrokenLinks()
                    self.currentView.scrollToTop()
                    self.logger.debug("You Selected Broken Links")

                self.ui.comboBulkActions.setCurrentIndex(0)
                self.onTreeViewSelectionChanged()
                self.onRelationsTreeSelectionChanged()

    def onTreeViewSelectionChanged(self, newSelection=None):
        if not self.currentView.selectedIndexes():
            self.logger.debug("No selection made.")
            for tab in range(self.ui.tabWidget.count()):
                self.ui.tabWidget.setTabEnabled(tab, False)
            self.ui.actionViewItem.setEnabled(False)
            self.ui.menuOpenWith.setEnabled(False)
            self.ui.actionEdit.setEnabled(False)
            self.ui.actionDelete.setEnabled(False)
            self.ui.actionCopypasta.setEnabled(False)
            self.ui.actionCopyFilePath.setEnabled(False)
            self.ui.toolbuttonCopy.setEnabled(False)
            self.ui.actionCheckSelected.setEnabled(False)
            self.ui.actionUncheckSelected.setEnabled(False)
            self.ui.actionCheckInvertSelected.setEnabled(False)
        elif newSelection:
            if self.tableArgs['tableType'] in (Æ.TableItems, Æ.TableSearch, Æ.TableBrokenLinks):
                selectedItem = self.returnSelectedItem(1)
                if selectedItem is not None:
                    for tab in range(self.ui.tabWidget.count()):
                        self.ui.tabWidget.setTabEnabled(tab, True)
                    self.ui.actionViewItem.setEnabled(True)
                    self.ui.menuOpenWith.setEnabled(True)
                    self.ui.actionEdit.setEnabled(True)
                    self.ui.actionDelete.setEnabled(True)
                    self.ui.actionCopypasta.setEnabled(True)
                    self.ui.actionDelete.setEnabled(True)
                    self.ui.actionCopyFilePath.setEnabled(True)
                    self.ui.toolbuttonCopy.setEnabled(True)
                    self.ui.actionCheckSelected.setEnabled(True)
                    self.ui.actionUncheckSelected.setEnabled(True)
                    self.ui.actionCheckInvertSelected.setEnabled(True)
                    self.displayTabsItems()
                    self.createOpenWithMenu(selectedItem)
                    self.logger.debug("Selected Item: "+selectedItem)
            elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                selectedItem = self.returnSelectedItem(1)
                if selectedItem is not None:
                    for tab in range(self.ui.tabWidget.count()):
                        self.ui.tabWidget.setTabEnabled(tab, True)
                    self.ui.actionViewItem.setEnabled(True)
                    self.ui.menuOpenWith.setEnabled(False)
                    self.ui.actionEdit.setEnabled(True)
                    self.ui.actionDelete.setEnabled(True)
                    self.ui.actionCopypasta.setEnabled(True)
                    self.ui.actionCopyFilePath.setEnabled(False)
                    self.ui.toolbuttonCopy.setEnabled(True)
                    self.ui.actionCheckSelected.setEnabled(True)
                    self.ui.actionUncheckSelected.setEnabled(True)
                    self.ui.actionCheckInvertSelected.setEnabled(True)
                    self.displayTabsCategories()
                    self.logger.debug("Selected Category: "+selectedItem)
            elif self.tableArgs['tableType'] == Æ.TableMissing:
                selectedItem = self.returnSelectedItem(1)
                if selectedItem is not None:
                    for tab in range(self.ui.tabWidget.count()):
                        self.ui.tabWidget.setTabEnabled(tab, True)
                    self.ui.actionViewItem.setEnabled(False)
                    self.ui.menuOpenWith.setEnabled(False)
                    self.ui.actionEdit.setEnabled(True)
                    self.ui.actionDelete.setEnabled(True)
                    self.ui.actionCopypasta.setEnabled(True)
                    self.ui.actionCopyFilePath.setEnabled(True)
                    self.ui.toolbuttonCopy.setEnabled(True)
                    self.ui.actionCheckSelected.setEnabled(False)
                    self.ui.actionUncheckSelected.setEnabled(True)
                    self.ui.actionCheckInvertSelected.setEnabled(True)
                    self.displayTabsItems()

    def onTreeModelUpdated(self):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            self.ui.actionBulkDeleteWithFiles.setEnabled(True)
            self.ui.comboBulkActions.setItemData(5, 1 | 32, Qt.UserRole-1)
            self.ui.actionViewAsList.setEnabled(True)
            self.ui.actionViewAsIcons.setEnabled(True)

        else:
            self.ui.actionBulkDeleteWithFiles.setEnabled(False)
            self.ui.comboBulkActions.setItemData(5, False, Qt.UserRole-1)
            self.ui.actionViewAsList.setEnabled(False)
            self.ui.actionViewAsIcons.setEnabled(False)

            # TODO

    def onRelationsTreeSelectionChanged(self, newSelection=None):
        try:
            if newSelection is not None and self.relationsModel.tableType == "Categories":
                index = newSelection.indexes()[0]
                indexOfID = self.relationsModel.index(index.row(), 2)
                selectionID = self.relationsModel.data(indexOfID)
                selectedItem = self.returnSelectedItem(1)
                if selectionID is not None:
                    self.logger.debug("Selected Relation: Item ID = "+str(selectedItem) +
                                      " Term ID = "+str(selectionID))
                self.ui.buttonDeleteRelation.setEnabled(True)
                self.ui.buttonDeleteAllRelations.setEnabled(True)
                self.ui.buttonViewRelation.setEnabled(True)
            elif newSelection is not None and self.relationsModel.tableType == "Items":
                index = newSelection.indexes()[0]
                indexOfID = self.relationsModel.index(index.row(), 2)
                selectionID = self.relationsModel.data(indexOfID)
                selectedItem = self.returnSelectedItem(0)
                if selectionID is not None:
                    self.logger.debug("Selected Relation: Item ID = "+str(selectionID) +
                                      " Term ID = "+str(selectedItem))
                self.ui.buttonDeleteRelation.setEnabled(True)
                self.ui.buttonDeleteAllRelations.setEnabled(True)
                self.ui.buttonViewRelation.setEnabled(True)
            else:
                self.ui.buttonDeleteRelation.setEnabled(False)
                self.ui.buttonViewRelation.setEnabled(False)
        except IndexError:
            pass

    def launchRelation(self):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            indexName = self.ui.relationsTree.selectedIndexes()[0]
            indexIden = indexName.sibling(indexName.row(), 2)
            itemIden = self.relationsModel.data(indexIden)
            itemName = self.relationsModel.data(indexName)
            self.logger.debug("({}) {} Selected.".format(itemIden, itemName))

            self.displayItems({"cat": itemIden, 'catName': itemName})
            self.currentView.scrollToTop()
            self.ui.treeMenu.clearSelection()
            self.onTreeViewSelectionChanged()

            self.logger.debug("Category Launched")
        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            indexName = self.ui.relationsTree.selectedIndexes()[0]
            indexType = indexName.sibling(indexName.row(), 1)
            indexIden = indexName.sibling(indexName.row(), 2)
            indexSource = indexName.sibling(indexName.row(), 3)
            itemName = self.relationsModel.data(indexName)
            itemType = self.relationsModel.data(indexType)
            itemIden = self.relationsModel.data(indexIden)
            itemSource = self.relationsModel.data(indexSource)
            self.openItemInDefaultApplication(itemName, itemType, itemSource)
            self.logger.debug("({}/{}) {} Selected.".format(itemIden, itemType, itemName))
            self.onTreeViewSelectionChanged()
            self.logger.debug("Item Launched")

    def launchItem(self):
        rows = self.mainTreeSelectedRows()
        if rows:
            if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                row = self.currentView.selectedIndexes()[0].row()
                itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
                itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
                itemSource = self.mainTreeModel().data(self.mainTreeModel().index(row, 4))
                self.openItemInDefaultApplication(itemName, itemType, itemSource)
            elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:

                termIden = self.returnSelectedItem(1)
                termName = self.returnSelectedItem(0)
                self.logger.debug("Term ID: "+termIden+" Tax Name: "+termName)
                self.displayItems({"cat": termIden, 'catName': termName})

                self.currentView.scrollToTop()
                self.ui.treeMenu.clearSelection()
            self.currentView.clearSelection()
            self.onTreeViewSelectionChanged()
            self.onRelationsTreeSelectionChanged()

    def launchDataFolder(self):
        try:
            folderPath = self.config['options']['defaultDataDir']
            if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                if self.currentView.selectedIndexes():
                    itemType = self.returnSelectedItem(2)
                    if itemType in self.config['itemTypes'].nounNames(Æ.NoWeblinks):
                        folderPath = os.path.join(folderPath, self.config['itemTypes'].dirFromNoun(itemType))
            elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                folderPath = self.config['options']['defaultDataDir']
            if platform.system() == "Windows":
                os.startfile(folderPath)
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.call(('open', folderPath))
            else:
                os.system('xdg-open "{}"'.format(folderPath))
        except BaseException as e:
            warningMsgBox(self, e, title="Error Opening Folder")

    def openItemInCustomApplication(self, action):
        if action.text() == "Default Application":
            self.launchItem()
        elif action.text() == "Other Application...":
            self.openOpenWithDialog()
        else:
            import subprocess
            self.logger.debug("Action: "+action.text())
            dataDir = self.config['options']['defaultDataDir']
            row = self.currentView.selectedIndexes()[0].row()
            itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
            itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
            if itemType in self.config['itemTypes'].nounNames(Æ.NoWeblinks):
                fileExtension = os.path.splitext(itemName)[1][1:].lower().strip()
                command = '"'+self.config["openWith"][fileExtension][action.text()]+'"'+' "{}" '.format(
                        getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName))
                self.logger.debug(command)
                if platform.system() in ("Windows",):
                    t = Thread(target=lambda: subprocess.call(command))
                    t.start()
                elif platform.system() == "Darwin":
                    t = Thread(target=lambda: subprocess.call(("open", "-a", self.config["openWith"][fileExtension][action.text()],
                                     getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName) )) )
                    t.start()
                else:
                    t = Thread(target=lambda: os.system(command))
                    t.start()
            else:
                itemSource = self.mainTreeModel().data(self.mainTreeModel().index(row, 4))
                command = '"'+self.config["openWith"]["weblink"][action.text()]+'"'+' "{}" '.format(itemSource)
                self.logger.debug(command)
                if platform.system() in ("Windows",):
                    t = Thread(target=lambda: subprocess.call(command))
                    t.start()
                elif platform.system() == "Darwin":
                    t = Thread(target=lambda: subprocess.call(("open", "-a", self.config["openWith"]["weblink"][action.text()],
                                      itemSource )) )
                    t.start()
                else:
                    t = Thread(target=lambda: os.system(command))
                    t.start()

    def openItemInDefaultApplication(self, itemName, itemType, itemSource):
        try:
            self.logger.debug("Item Type: "+itemType)
            dataDir = self.config['options']['defaultDataDir']
            if itemType in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
                self.logger.debug("Item Source: "+itemSource)
                webbrowser.open(itemSource)

            elif itemType in self.config['itemTypes'].nounNames(Æ.NoWeblinks):
                self.logger.debug(itemType+" Name: "+itemName)
                if platform.system() == "Windows":
                    os.startfile(getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName))
                elif platform.system() == "Darwin":
                    import subprocess
                    subprocess.call(('open', getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName)))
                else:
                    exitCode = os.system('xdg-open "{}"'.format(
                        getDataFilePath(dataDir, self.config['itemTypes'].dirFromNoun(itemType), itemName)))
                    if exitCode is not 0:
                        warningMsgBox(self, "Unable to launch file. Probably missing from directory.",
                                      title="Error Opening File")
        except BaseException as e:
            warningMsgBox(self, e, title="Error Opening File")

    def copyFilePath(self):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                itemPaths = list()
                for row in rows:
                    itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
                    if itemType in self.config['itemTypes'].nounNames(Æ.NoWeblinks):
                        itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
                        itemPath = os.path.join(str(self.config['options']['defaultDataDir']),
                                                 self.config['itemTypes'].dirFromNoun(itemType),itemName)
                    else:
                        itemPath = self.mainTreeModel().data(self.mainTreeModel().index(row, 4))
                    itemPaths.append(itemPath)
                itemPathsJoined = "\n".join(itemPaths)
                self.logger.debug(itemPathsJoined)
                self.clipboard.setText(itemPathsJoined)
                self.logger.debug("File path copied to clipboard.")

    def copypastaSelected(self):
        self.db.open()
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                if self.tableViewMode == "icons":
                    itemIdens = [str(self.mainTreeModel().rows[row][1]) for row in rows]
                else:
                    itemIdens = [str(self.mainTreeModel().data(self.mainTreeModel().index(row, 0))) for row in rows]
                copypastaText = str()
                query = self.db.selectCopypasta(itemIdens)
                try:
                    while query.next():
                        copypastaText += self.createCopypasta(query)
                    self.logger.debug(copypastaText)
                    self.clipboard.setText(copypastaText)
                    self.logger.debug("Data copied to clipboard.")
                except IndexError:
                    warningMsgBox(self, "Unable to copy to clipboard. Formatting is invalid.",
                                  "Invalid Formatting")
        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            indexes = self.mainTreeSelectedIndexes()
            if indexes:
                itemIdens = [str(self.mainTreeModel().data(i, 0)) for i in indexes]
                copypastaText = str()
                query = self.db.selectCopypastaFromCategories(itemIdens)
                try:
                    while query.next():
                        copypastaText += self.createCopypasta(query)
                    self.logger.debug(copypastaText)
                    self.clipboard.setText(copypastaText)
                    self.logger.debug("Data copied to clipboard.")
                except IndexError:
                    warningMsgBox(self, "Unable to copy to clipboard. Formatting is invalid.",
                                  "Invalid Formatting")
        self.db.close()

    def createCopypasta(self, query):
        if self.config['copypasta']['enabledName']:
            if self.config['copypasta']['keepFileExtension']:
                itemName = self.config['copypasta']['formatName'].format(query.value(0))+'\n'
            else:
                fileExtension = os.path.splitext(query.value(0))[1][1:].lower().strip()
                if self.config['itemTypes'][query.value(3)].hasExtension(fileExtension):
                    itemName = self.config['copypasta']['formatName'].format(
                        os.path.splitext(query.value(0))[0])+'\n'
                else:
                    itemName = self.config['copypasta']['formatName'].format(query.value(0))+'\n'
        else:
            itemName = ''
        if self.config['copypasta']['enabledSource']:
            itemSource = unquote(query.value(1))
            if not itemSource == "":
                itemSource = self.config['copypasta']['formatSource'].format(itemSource)+'\n'
        else:
            itemSource = ''
        if self.config['copypasta']['enabledDescription']:
            itemDescription = unquote(query.value(2))
            if not itemDescription == "":
                if not self.config['copypasta']['formatEachLineOfDesc']:
                    itemDescription = self.config['copypasta']['formatDescription']\
                        .format(itemDescription)+'\n'
                else:
                    descriptionLines = itemDescription.split('\n')
                    for index, line in enumerate(descriptionLines):
                        if not line == "":
                            descriptionLines[index] = self.config['copypasta']['formatDescription'].format(line)
                    itemDescription = "\n".join(descriptionLines)+'\n'
        else:
            itemDescription = ''
        copypastaText = self.config['copypasta']['outerFormatting']\
            .format(itemName+itemSource+itemDescription)+"\n"
        return copypastaText

    def mainTreeSelectAll(self):
        self.currentView.selectAll()

    def checkSelection(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                self.mainTreeModel().checkSelection(rows)
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            indexes = self.mainTreeSelectedIndexes()
            if indexes:
                self.mainTreeModel().checkSelection(indexes)

    def uncheckSelection(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                self.mainTreeModel().uncheckSelection(rows)
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            indexes = self.mainTreeSelectedIndexes()
            if indexes:
                self.mainTreeModel().uncheckSelection(indexes)

    def checkInvertSelection(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                self.mainTreeModel().checkInvertSelection(rows)
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            indexes = self.mainTreeSelectedIndexes()
            if indexes:
                self.mainTreeModel().checkInvertSelection(indexes)

    def checkAll(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            self.mainTreeModel().checkAll()
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            self.mainTreeModel().checkAll()

    def checkNone(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            self.mainTreeModel().checkNone()
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            self.mainTreeModel().checkNone()

    def checkInverse(self):
        if self.mainTreeModel().tableType in Æ.ItemTableTypes:
            self.mainTreeModel().checkInverse()
        if self.mainTreeModel().tableType in Æ.CategoryTableTypes:
            self.mainTreeModel().checkInverse()

    def deleteSelection(self):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                msgBox = ÆMessageBox(self)
                if len(rows) is 1:
                    itemName = self.returnSelectedItem(1)
                    message = "Are you sure you want to delete <i>{}</i>?".format(itemName)
                    msgBox.setText("<b>Confirm deletion of selected item?</b>")
                else:
                    message = "Are you sure you want to delete the {} selected items?".format(str(len(rows)))
                    msgBox.setText("<b>Confirm deletion of selected items?</b>")
                msgBox.setIcon(ÆMessageBox.Icon.Information)
                msgBox.setWindowTitle("Confirm Deletion")
                msgBox.setInformativeText(message)
                msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                msgBox.setCheckable(True)
                msgBox.checkboxes[0].setText("Delete file in data folder.")
                msgBox.checkboxes[0].setChecked(True)
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.logger.info("Deletion Executed.")
                    self.db.open()
                    self.db.transaction()
                    for row in rows:
                        if self.tableViewMode == "icons":
                            itemID = self.mainTreeModel().rows[row][1]
                        else:
                            itemID = self.mainTreeModel().data(self.mainTreeModel().index(row, 0))
                        self.db.deleteItem(str(itemID))
                        if msgBox.checkboxes[0].isChecked():
                            itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
                            itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
                            dataDir = self.config['options']['defaultDataDir']
                            typeDir = self.config['itemTypes'].dirFromNoun(itemType)
                            filePath = getDataFilePath(dataDir, typeDir, itemName)
                            if os.path.exists(filePath):
                                if itemType in self.config['itemTypes'].nounNames(Æ.IsWebpages):
                                    folderName = os.path.splitext(itemName)[0]+"_files"
                                    folderPath = getDataFilePath(dataDir, typeDir, folderName)
                                    deleteFile(self, filePath, folderPath)
                                else:
                                    deleteFile(self, filePath)
                                self.logger.info("File deleted from data folder.")
                        self.logger.debug("Item Deleted")
                    self.db.commit()
                    self.db.close()
                    self.refreshTable()
                elif ret == msgBox.StandardButton.Cancel:
                    self.logger.info("Deletion Cancelled.")
                msgBox.deleteLater()
        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            indexes = self.mainTreeSelectedIndexes()
            if indexes:
                msgBox = QMessageBox(self)
                if len(indexes) is 1:
                    catName = self.returnSelectedItem(0)
                    message = "Are you sure you want to delete <i>{}</i>?".format(catName)
                    msgBox.setText("<b>Confirm deletion of selected category?</b>")
                else:
                    message = "Are you sure you want to delete the {} selected categories?".format(str(len(indexes)))
                    msgBox.setText("<b>Confirm deletion of selected categories?</b>")
                msgBox.setIcon(QMessageBox.Icon.Information)
                msgBox.setWindowTitle("Confirm Deletion")
                msgBox.setInformativeText(message)
                msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.logger.info("Deletion Executed.")
                    self.db.open()
                    self.db.transaction()
                    for index in indexes:
                        catIden = self.mainTreeModel().data(index, 0)
                        self.db.deleteCategory(str(catIden))
                    self.db.commit()
                    self.db.close()
                    self.refreshTable()
                elif ret == msgBox.StandardButton.Cancel:
                    self.logger.info("Deletion Cancelled.")
                msgBox.deleteLater()

    def deleteRelation(self):
        message = "Are you sure you want to delete the selected relation?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Information)
        msgBox.setWindowTitle("Confirm Deletion")
        msgBox.setText("<b>Confirm deletion of selected relation?</b>")
        msgBox.setInformativeText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.logger.info("Deletion Executed.")
            self.db.open()
            index = self.ui.relationsTree.selectedIndexes()[0]
            indexOfIden = index.sibling(index.row(), 2)
            relationsIden = self.relationsModel.data(indexOfIden)
            if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                mainIden = self.returnSelectedItem(0)
                self.db.deleteRelation(itemid=mainIden, termid=relationsIden)
            elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                mainIden = self.returnSelectedItem(1)
                self.db.deleteRelation(itemid=relationsIden, termid=mainIden)
            self.refreshTable()
            self.onRelationsTreeSelectionChanged()
            self.db.close()
        elif ret == msgBox.StandardButton.Cancel:
            self.logger.info("Deletion Cancelled.")
        msgBox.deleteLater()

    def deleteAllRelations(self):
        message = "Are you sure you want to delete all relations for the selection?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Information)
        msgBox.setWindowTitle("Confirm Deletion")
        msgBox.setText("<b>Confirm deletion of all selection’s relations?</b>")
        msgBox.setInformativeText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.logger.info("Deletion Executed.")
            self.db.open()
            self.db.transaction()
            if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                mainIden = self.returnSelectedItem(0)
                self.db.deleteRelations(mainIden, col='item_id')
            elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                mainIden = self.returnSelectedItem(1)
                self.db.deleteRelations(mainIden, col='term_id')
            self.db.commit()
            self.db.close()
            self.refreshTable()
            self.onRelationsTreeSelectionChanged()

        elif ret == msgBox.StandardButton.Cancel:
            self.logger.info("Deletion Cancelled.")
        msgBox.deleteLater()

    def deleteAllData(self):
        message = "Are you sure you want to delete all item and category data in the database?"
        msgBox = ÆMessageBox(self)
        msgBox.setIcon(ÆMessageBox.Icon.Warning)
        msgBox.setWindowTitle("Delete all Data in Database?")
        msgBox.setText('<span style="font-weight:600;"><span style="color:red;">'
                       'WARNING:</span> This process cannot be undone.</span>')
        msgBox.setInformativeText(message)
        btnWipeItOut = QPushButton('WIPE IT OUT!!!')
        msgBox.addButton(btnWipeItOut, msgBox.ButtonRole.YesRole)
        msgBox.addButton(msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        msgBox.setCheckable(True)
        msgBox.checkboxes[0].setText("Delete all files in data folder.")
        ret = msgBox.exec_()
        if msgBox.clickedButton() == btnWipeItOut:
            self.logger.info("Deletion Executed.")
            try:
                self.db.open()
                self.db.deleteAllData()
                self.db.close()
                if msgBox.checkboxes[0].isChecked():
                    dataDir = self.config['options']['defaultDataDir']
                    if os.path.exists(dataDir):
                        shutil.rmtree(dataDir)
                        self.logger.info("All files deleted from data folder.")
                QMessageBox().information(None, 'Data Successfully Deleted',
                                          'The database data was deleted.', QMessageBox.StandardButton.Ok)
            except BaseException as e:
                warningMsgBox(self, e, title="Error Deleting File")
            self.refreshTable()
        elif ret == msgBox.StandardButton.Cancel:
            self.logger.info("Deletion Cancelled.")
        msgBox.deleteLater()

    def dropDatabase(self):
        message = "Are you sure you want to delete the database?"
        msgBox = ÆMessageBox(self)
        msgBox.setIcon(ÆMessageBox.Icon.Warning)
        msgBox.setWindowTitle("Delete the Database?")
        msgBox.setText('<span style="font-weight:600;"><span style="color:red;">'
                       'WARNING:</span> This process cannot be undone.</span>')
        msgBox.setInformativeText(message)
        btnWipeItOut = QPushButton('WIPE IT OUT!!!')
        msgBox.addButton(btnWipeItOut, msgBox.ButtonRole.YesRole)
        msgBox.addButton(msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        msgBox.setCheckable(True)
        msgBox.checkboxes[0].setText("Delete all files in data folder.")
        ret = msgBox.exec_()
        if msgBox.clickedButton() == btnWipeItOut:
            self.logger.info("Deletion Executed.")
            try:
                self.db.open()
                self.db.dropDatabase()
                self.db.removeConnection()
                if msgBox.checkboxes[0].isChecked():
                    dataDir = self.config['options']['defaultDataDir']
                    if os.path.exists(dataDir):
                        shutil.rmtree(dataDir)
                        self.logger.info("All files deleted from data folder.")
                QMessageBox().information(None, 'Database Successfully Deleted',
                                          'The database was deleted.', QMessageBox.StandardButton.Ok)
                self.config['autoloadDatabase'] = False
                self.config['db'].clear()
                self.config.settings.remove('db')
                self.db = None
                self.close()
                self.config.writeConfig()
                self.app.openWizard()
            except BaseException as e:
                warningMsgBox(self, e, title="Error Deleting File")
        elif ret == msgBox.StandardButton.Cancel:
            self.logger.info("Deletion Cancelled.")
        msgBox.deleteLater()

    def vacuumDatabase(self):
        if self.config['db']['type'] == 'sqlite':
            try:
                message = "Are you sure you want to vacuum the current database?"
                msgBox = QMessageBox(self)
                msgBox.setIcon(QMessageBox.Icon.Question)
                msgBox.setWindowTitle("Vacuum the Current Database?")
                msgBox.setText(message)
                msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                ret = msgBox.exec_()
                if ret == msgBox.StandardButton.Ok:
                    self.db.open()
                    self.db.vacuumDatabase()
                    self.db.close()
                    QMessageBox().information(
                        None, 'Database Successfully Vacuumed', 'The database was vacuumed.', QMessageBox.StandardButton.Ok)
            except BaseException as e:
                warningMsgBox(self, e, title="Error Vacuuming Database")

    def toggleMainToolbar(self):
        if self.ui.toggleMainToolbar.isChecked() is True:
            self.ui.toolBar.show()
            self.config['mainWindow']['toggleMainToolbar'] = True
            self.logger.debug("Main Toolbar shown.")
        else:
            self.ui.toolBar.hide()
            self.config['mainWindow']['toggleMainToolbar'] = False
            self.logger.debug("Main Toolbar hidden.")

    def toggleSearchToolbar(self):
        if self.ui.toggleSearchToolbar.isChecked() is True:
            self.ui.toolBarSearch.show()
            self.config['mainWindow']['toggleSearchToolbar'] = True
            self.logger.debug("Search Toolbar shown.")
        else:
            self.ui.toolBarSearch.hide()
            self.config['mainWindow']['toggleSearchToolbar'] = False
            self.logger.debug("Search Toolbar hidden.")

    def toggleBulkActionsToolbar(self):
        if self.ui.toggleBulkActionsToolbar.isChecked() is True:
            self.ui.toolBarBulkActions.show()
            self.config['mainWindow']['toggleBulkActionsToolbar'] = True
            self.logger.debug("Bulk Actions Toolbar shown.")
        else:
            self.ui.toolBarBulkActions.hide()
            self.config['mainWindow']['toggleBulkActionsToolbar'] = False
            self.logger.debug("Bulk Actions Toolbar hidden.")

    def toggleSidebar(self):
        if self.ui.toggleSidebar.isChecked() is True:
            self.ui.scrollAreaMenu.show()
            self.config['mainWindow']['toggleSidebar'] = True
            self.logger.debug("Sidebar shown.")
        else:
            self.ui.scrollAreaMenu.hide()
            self.config['mainWindow']['toggleSidebar'] = False
            self.logger.debug("Sidebar hidden.")

    def toggleStatusbar(self):
        if self.ui.toggleStatusbar.isChecked() is True:
            self.ui.statusbar.show()
            self.config['mainWindow']['toggleStatusbar'] = True
            self.logger.debug("Statusbar shown.")
        else:
            self.ui.statusbar.hide()
            self.config['mainWindow']['toggleStatusbar'] = False
            self.logger.debug("Statusbar hidden.")

    def toggleSelectionDetails(self):
        if self.ui.toggleSelectionDetails.isChecked() is True:
            self.ui.tabWidget.show()
            self.config['mainWindow']['toggleSelectionDetails'] = True
            self.logger.debug("Details shown.")
        else:
            self.ui.tabWidget.hide()
            self.config['mainWindow']['toggleSelectionDetails'] = False
            self.logger.debug("Details hidden.")

    def toggleFullScreen(self):
        if self.isFullScreen() is True:
            self.showMaximized()
        else:
            self.showFullScreen()

    def viewDatabaseInfo(self):
        infoDialog = InfoDialog(self)
        infoDialog.exec_()
        infoDialog.deleteLater()

    def applyBulkAction(self, actionCode=None):
        comboBox = self.ui.comboBulkActions
        if not actionCode:
            actionCode = comboBox.itemData(comboBox.currentIndex())
            actionName = comboBox.currentText()
            self.logger.debug("Bulk Action '{}' selected. Iden: '{}'".format(actionName, actionCode))
        if actionCode > 0:
            i = 0
            rowIdens = []
            model = self.mainTreeModel()
            if self.mainTreeModel().tableType in Æ.ItemTableTypes:
                while model.hasIndex(i, 0):
                    if model.data(model.index(i, 0), Qt.CheckStateRole) == Qt.Checked:
                        name = model.data(model.index(i, 1))
                        iden = model.rows[i][1]
                        rowType = model.data(model.index(i, 2))
                        rowIdens.append((iden, name, rowType))
                    i += 1
            elif self.mainTreeModel().tableType in Æ.CategoryTableTypes:
                rowIdens = self.treeModel.rootItem.returnCheckedData()
            if len(rowIdens) >= 1:
                self.db.open()
                if actionCode == 1:
                    if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                        query = self.db.selectCopypasta([str(iden[0]) for iden in rowIdens])
                        copypastaText = str()
                        try:
                            while query.next():
                                copypastaText += self.createCopypasta(query)
                            self.logger.debug(copypastaText)
                            self.clipboard.setText(copypastaText)
                            self.logger.info("Data copied to clipboard.")
                        except IndexError:
                            warningMsgBox(self, "Unable to copy to clipboard. Formatting is invalid.",
                                          "Invalid Formatting")
                    elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                        query = self.db.selectCopypastaFromCategories([str(iden[0]) for iden in rowIdens])
                        copypastaText = str()
                        try:
                            while query.next():
                                copypastaText += self.createCopypasta(query)
                            self.logger.debug(copypastaText)
                            self.clipboard.setText(copypastaText)
                            self.logger.info("Data copied to clipboard.")
                        except IndexError:
                            warningMsgBox(self, "Unable to copy to clipboard. Formatting is invalid.",
                                          "Invalid Formatting")
                elif actionCode == 2:
                    if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                        bulkEditDialog = BulkEditDialog(self, rowIdens)
                        bulkEditDialog.itemsUpdated.connect(self.refreshTable)
                        bulkEditDialog.exec_()
                        bulkEditDialog.deleteLater()
                    elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                        query = self.db.selectCopypastaFromCategories([str(iden[0]) for iden in rowIdens])
                        itemDetails = list()
                        while query.next():
                            iden = query.value(4)
                            name = query.value(0)
                            rowType = query.value(3)
                            itemDetails.append((iden, name, rowType))
                        bulkEditDialog = BulkEditDialog(self, itemDetails)
                        bulkEditDialog.itemsUpdated.connect(self.refreshTable)
                        bulkEditDialog.exec_()
                        bulkEditDialog.deleteLater()

                elif actionCode == 3:
                    if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                        self.db.transaction()
                        for itemIden in rowIdens:
                            self.db.deleteItem(itemIden[0])
                        self.db.commit()
                    elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                        self.db.transaction()
                        for catIden in rowIdens:
                            self.db.deleteCategory(catIden[0])
                        self.db.commit()
                    self.logger.info(str(len(rowIdens))+" rows deleted from database.")
                elif actionCode == 4:
                    if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                        self.db.transaction()
                        for itemIden in rowIdens:
                            self.db.deleteRelations(itemIden[0], col='item_id')
                        self.db.commit()
                        self.logger.info("Relations deleted from {} items in database.".format(str(len(rowIdens))))
                    elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
                        self.db.transaction()
                        for catIden in rowIdens:
                            self.db.deleteRelations(catIden[0], col='term_id')
                        self.db.commit()
                        self.logger.info("Relations deleted from {} categories in database.".format(str(len(rowIdens))))
                elif actionCode == 5:
                    if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                        self.db.transaction()
                        dataDir = self.config['options']['defaultDataDir']
                        for itemIden in rowIdens:
                            self.db.deleteItem(itemIden[0])
                            itemName = itemIden[1]
                            itemType = itemIden[2]
                            typeDir = self.config['itemTypes'].dirFromNoun(itemType)
                            filePath = getDataFilePath(dataDir, typeDir, itemName)
                            if os.path.exists(filePath):
                                if itemType in self.config['itemTypes'].nounNames(Æ.IsWebpages):
                                    folderName = os.path.splitext(itemName)[0]+"_files"
                                    folderPath = getDataFilePath(dataDir, typeDir, folderName)
                                    deleteFile(self, filePath, folderPath)
                                else:
                                    deleteFile(self, filePath)
                                self.logger.info("File deleted from data folder.")
                        self.db.commit()
                    self.logger.info(str(len(rowIdens))+" files deleted from database and data directory.")
                self.db.close()
                self.refreshTable()
            self.ui.comboBulkActions.setCurrentIndex(0)

    def setSearchResults(self):
        if not self.ui.lineSearch.text() in ('', None):
            self.advancedSearchSQL = None
            self.searchPhrase = self.ui.lineSearch.text()
            indexes = self.ui.treeMenu.selectedIndexes()
            if indexes:
                data = self.ui.treeMenu.model().itemFromIndex(indexes[0]).data(0)
            else:
                data = False
            if data == "Search Results":
                self.displaySearchResults()
            else:
                try:
                    searchResultsItem = self.ui.treeMenu.model().findItems("Search Results", Qt.MatchExactly, 0)[0]
                    searchResultsItem.setEnabled(True)
                except IndexError:
                    searchResultsItem = QStandardItem(self.icons['Search'], "Search Results")
                    self.menuModel.appendRow(searchResultsItem)
                index = self.ui.treeMenu.model().indexFromItem(searchResultsItem)
                self.ui.treeMenu.setCurrentIndex(index)
            self.logger.debug(data)
        else:
            try:
                searchResultsItem = self.ui.treeMenu.model().findItems("Search Results", Qt.MatchExactly, 0)[0]
                index = self.ui.treeMenu.model().indexFromItem(searchResultsItem)
                self.ui.treeMenu.model().takeRow(index.row())
            except IndexError:
                pass
            self.refreshMenu()

    def setAdvancedSearchResults(self, sql):
        if sql:
            self.searchPhrase = None
            self.advancedSearchSQL = sql
            indexes = self.ui.treeMenu.selectedIndexes()
            if indexes:
                data = self.ui.treeMenu.model().itemFromIndex(indexes[0]).data(0)
            else:
                data = False
            if data == "Search Results":
                self.displayAdvancedSearch()
            else:
                try:
                    searchResultsItem = self.ui.treeMenu.model().findItems("Search Results", Qt.MatchExactly, 0)[0]
                    searchResultsItem.setEnabled(True)
                except IndexError:
                    searchResultsItem = QStandardItem(self.icons['Search'], "Search Results")
                    self.menuModel.appendRow(searchResultsItem)
                index = self.ui.treeMenu.model().indexFromItem(searchResultsItem)
                self.ui.treeMenu.setCurrentIndex(index)
            self.logger.debug(data)
        else:
            try:
                searchResultsItem = self.ui.treeMenu.model().findItems("Search Results", Qt.MatchExactly, 0)[0]
                index = self.ui.treeMenu.model().indexFromItem(searchResultsItem)
                self.ui.treeMenu.model().takeRow(index.row())
            except IndexError:
                pass
            self.refreshMenu()

    def refreshTable(self):
        if self.tableArgs['tableType'] == Æ.TableItems:
            self.displayItems(self.tableArgs['query'])
        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            self.displayCategories(self.tableArgs['query'])
        elif self.tableArgs['tableType'] == Æ.TableSearch:
            if self.advancedSearchSQL:
                self.displayAdvancedSearch()
            else:
                self.displaySearchResults()
        elif self.tableArgs['tableType'] == Æ.TableMissing:
            self.openItemChecker()
        elif self.tableArgs['tableType'] == Æ.TableBrokenLinks:
            self.openLinkChecker()
        self.onTreeViewSelectionChanged()

    def refreshMenu(self):
        self.checkTypesAndTaxonomies()
        self.displayMenu()
        self.onTreeMenuSelectionChanged()

    def setMissingFiles(self, missingItems):
        indexes = self.ui.treeMenu.selectedIndexes()
        if indexes:
            data = self.ui.treeMenu.model().itemFromIndex(indexes[0]).data(0)
        else:
            data = False
        if len(missingItems) >= 1:
            self.missingFiles = missingItems
            if data == "Missing Files":
                self.displayMissingFiles()
            else:
                try:
                    missingFilesItem = self.ui.treeMenu.model().findItems("Missing Files", Qt.MatchExactly, 0)[0]
                    missingFilesItem.setEnabled(True)
                except IndexError:
                    missingFilesItem = QStandardItem(self.icons['Warning'], "Missing Files")
                    self.menuModel.appendRow(missingFilesItem)
                index = self.ui.treeMenu.model().indexFromItem(missingFilesItem)
                self.ui.treeMenu.setCurrentIndex(index)
        else:
            try:
                self.missingFiles.clear()
            except AttributeError:
                del self.missingFiles[:]
            try:
                missingFilesItem = self.ui.treeMenu.model().findItems("Missing Files", Qt.MatchExactly, 0)[0]
                index = self.ui.treeMenu.model().indexFromItem(missingFilesItem)
                self.ui.treeMenu.model().takeRow(index.row())
            except IndexError:
                pass
            self.displayMenu()
            self.onTreeMenuSelectionChanged()

    def setBrokenLinks(self, brokenLinks):
        indexes = self.ui.treeMenu.selectedIndexes()
        if indexes:
            data = self.ui.treeMenu.model().itemFromIndex(indexes[0]).data(0)
        else:
            data = False
        if len(brokenLinks) >= 1:
            self.brokenLinks = brokenLinks
            if data == "Broken Links":
                self.displayBrokenLinks()
            else:
                try:
                    brokenLinksItem = self.ui.treeMenu.model().findItems("Broken Links", Qt.MatchExactly, 0)[0]
                except IndexError:
                    brokenLinksItem = QStandardItem(self.icons['Warning'], "Broken Links")
                    self.menuModel.appendRow(brokenLinksItem)
                index = self.ui.treeMenu.model().indexFromItem(brokenLinksItem)
                self.ui.treeMenu.setCurrentIndex(index)
        else:
            try:
                self.brokenLinks.clear()
            except AttributeError:
                del self.brokenLinks[:]
            try:
                brokenLinksItem = self.ui.treeMenu.model().findItems("Broken Links", Qt.MatchExactly, 0)[0]
                index = self.ui.treeMenu.model().indexFromItem(brokenLinksItem)
                self.ui.treeMenu.model().takeRow(index.row())
            except IndexError:
                pass
            self.displayMenu()
            self.onTreeMenuSelectionChanged()

    def checkTypesAndTaxonomies(self):
        try:
            self.db.open()
            queryTypes = self.db.selectDistinctItemTypes()
            while queryTypes.next():
                tableName = queryTypes.value(0)
                self.logger.debug("Checking "+tableName)
                if not self.config['itemTypes'][tableName]:
                    itemType = ÆItemType()
                    itemType.setPluralName(tableName.title()+"s")
                    itemType.setNounName(tableName.title())
                    itemType.setTableName(tableName)
                    self.config['itemTypes'].append(itemType)
            queryTaxonomies = self.db.selectDistinctTaxonomies()
            while queryTaxonomies.next():
                tableName = queryTaxonomies.value(0)
                self.logger.debug("Checking "+tableName)
                if not self.config['taxonomies'][tableName]:
                    taxonomy = ÆTaxonomy()
                    taxonomy.setPluralName(tableName.title()+"s")
                    taxonomy.setNounName(tableName.title())
                    taxonomy.setTableName(tableName)
                    self.config['taxonomies'].append(taxonomy)
            self.db.close()
        except BaseException as e:
            warningMsgBox(self, e, title="Error Checking Item Types & Taxonomies")

    def treeViewContextMenu(self):
        self.ui.menuTable.exec_(QCursor().pos())

    def createOpenWithMenu(self, name):
        row = self.currentView.selectedIndexes()[0].row()
        itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))

        self.ui.menuOpenWith.clear()
        self.ui.actionDefaultApplication = QAction(self.icons['Play'], "Default Application", self)
        self.ui.menuOpenWith.addAction(self.ui.actionDefaultApplication)

        if itemType not in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
            fileExtension = os.path.splitext(name)[1][1:].lower().strip()
            if fileExtension in self.config["openWith"]:
                commandsList = self.config["openWith"][fileExtension]
                for appName in commandsList.keys():
                    menuAction = QAction(self.icons['MimeApp'], appName, self)
                    self.ui.menuOpenWith.addAction(menuAction)
        elif "weblink" in self.config["openWith"]:
            commandsList = self.config["openWith"]["weblink"]
            for appName in commandsList.keys():
                menuAction = QAction(self.icons['MimeApp'], appName, self)
                self.ui.menuOpenWith.addAction(menuAction)

        Seperator = QAction("", self)
        Seperator.setSeparator(True)
        self.ui.menuOpenWith.addAction(Seperator)
        self.ui.actionOtherApplication = QAction("Other Application...", self)
        self.ui.menuOpenWith.addAction(self.ui.actionOtherApplication)

    def menuListContextMenu(self):
        self.ui.menuListMenu.exec_(QCursor().pos())

    def toolbarContextMenu(self):
        self.ui.menuView.exec_(QCursor().pos())

    def relationsTreeContextMenu(self):
        self.ui.menuRelationsMenu.exec_(QCursor().pos())

    def toggleTableSearch(self):
        self.ui.lineFind.clear()
        if self.ui.tableSearchWidget.isHidden():
            self.ui.tableSearchWidget.show()
            self.ui.lineFind.setFocus()
        else:
            self.ui.tableSearchWidget.hide()

    def mainTreeSearch(self, searchString):
        self.currentView.search(searchString)

    def mainTreeSelectAllSearchResults(self):
        if not self.ui.lineFind.text() == '':
            self.currentView.clearSelection()
            self.currentView.selectAllSearchResults()

    def mainTreeSelectPreviousResult(self):
        if not self.ui.lineFind.text() == '':
            self.currentView.selectPreviousSearchResult()

    def mainTreeSelectNextResult(self):
        if not self.ui.lineFind.text() == '':
            self.currentView.selectNextSearchResult()

    def mainTreeModel(self):
        if not self.currentView.model():
            return self.tableModel
        else:
            return self.currentView.model()

    def openAboutDialog(self):
        aboutDialog = AboutDialog(self)
        aboutDialog.exec_()
        aboutDialog.deleteLater()

    def openImportWizard(self):
        importWizard = ImportWizard(self)
        importWizard.dataImported.connect(self.refreshMenu)
        importWizard.finished.connect(importWizard.deleteLater)
        importWizard.show()

    def openExportWizard(self):
        exportWizard = ExportWizard(self)
        exportWizard.finished.connect(exportWizard.deleteLater)
        exportWizard.show()

    def openCreateLinksWizard(self):
        linksWizard = CreateLinksWizard(self)
        linksWizard.finished.connect(linksWizard.deleteLater)
        linksWizard.show()

    def openItemChecker(self):
        itemChecker = ItemChecker(self)
        itemChecker.missingFilesSignal.connect(self.setMissingFiles)
        itemChecker.completed.connect(itemChecker.deleteLater)
        itemChecker.run()

    def openLinkChecker(self):
        linkChecker = LinkChecker(self)
        linkChecker.brokenLinksSignal.connect(self.setBrokenLinks)
        linkChecker.completed.connect(linkChecker.deleteLater)
        linkChecker.run()

    def openRelationsRecounter(self):
        relationsRecounter = RelationsRecounter(self)
        relationsRecounter.completed.connect(relationsRecounter.deleteLater)
        relationsRecounter.run()

    def openFileManager(self):
        fileManager = FileManager(self)
        fileManager.exec_()
        fileManager.deleteLater()
        self.refreshTable()

    def openNewItemDialog(self):
        newItemDialog = NewItemDialog(self)
        newItemDialog.itemInserted.connect(self.refreshTable)
        newItemDialog.exec_()
        newItemDialog.deleteLater()

    def openNewCategoryDialog(self):
        newCategoryDialog = NewCategoryDialog(self)
        newCategoryDialog.categoryInserted.connect(self.refreshTable)
        newCategoryDialog.exec_()
        newCategoryDialog.deleteLater()

    def openEditDialog(self):
        if self.tableArgs['tableType'] in Æ.ItemTableTypes:
            rows = self.mainTreeSelectedRows()
            if rows:
                if len(rows) is 1:
                    itemIden = self.returnSelectedItem(0)
                    editItemDialog = EditItemDialog(self, itemIden)
                    editItemDialog.itemInserted.connect(self.refreshTable)
                    editItemDialog.exec_()
                    editItemDialog.deleteLater()
                else:
                    rowIdens = list()

                    for row in rows:
                        if self.tableViewMode == "icons":
                            itemIden = self.mainTreeModel().rows[row][1]
                        else:
                            itemIden = self.mainTreeModel().data(self.mainTreeModel().index(row, 0))
                        itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
                        itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
                        rowIdens.append((itemIden, itemName, itemType))
                    bulkEditDialog = BulkEditDialog(self, rowIdens)
                    bulkEditDialog.itemsUpdated.connect(self.refreshTable)
                    bulkEditDialog.exec_()
                    bulkEditDialog.deleteLater()
        elif self.tableArgs['tableType'] in Æ.CategoryTableTypes:
            catID = self.returnSelectedItem(1)
            editCategoryDialog = EditCategoryDialog(self, catID)
            editCategoryDialog.categoryInserted.connect(self.refreshTable)
            editCategoryDialog.exec_()
            editCategoryDialog.deleteLater()

    def openPreferences(self, tabPageName=None):
        preferencesDialog = PreferencesDialog(self)
        if tabPageName == "Item Types":
            preferencesDialog.goToItemTypes()
        elif tabPageName == "Taxonomies":
            preferencesDialog.goToTaxonomies()
        preferencesDialog.exec_()
        preferencesDialog.deleteLater()

    def openAdvancedSearch(self):
        searchDialog = AdvancedSearchDialog(self)
        searchDialog.sqlSignal.connect(self.setAdvancedSearchResults)
        searchDialog.exec_()
        searchDialog.deleteLater()

    def openOpenWithDialog(self):
        rows = self.mainTreeSelectedRows()
        if rows:
            if self.tableArgs['tableType'] in Æ.ItemTableTypes:
                row = self.currentView.selectedIndexes()[0].row()
                itemName = self.mainTreeModel().data(self.mainTreeModel().index(row, 1))
                itemType = self.mainTreeModel().data(self.mainTreeModel().index(row, 2))
                if itemType in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
                    openWithDialog = OpenWithDialog(self, "weblink")
                    openWithDialog.exec_()
                    openWithDialog.deleteLater()
                    self.createOpenWithMenu(self.returnSelectedItem(1))
                elif itemType in self.config['itemTypes'].nounNames(Æ.NoWeblinks):
                    fileExtension = os.path.splitext(itemName)[1][1:].lower().strip()
                    openWithDialog = OpenWithDialog(self, fileExtension)
                    openWithDialog.exec_()
                    openWithDialog.deleteLater()
                    self.createOpenWithMenu(self.returnSelectedItem(1))

    def openHelpBrowser(self):
        self.app.openHelpBrowser()

    def openLogFile(self):
        if self.app.portableMode:
            logPath = "Filecatman.log"
        elif platform.system() == "Windows":
            logPath = os.path.join(os.path.dirname(QSettings().fileName()), "Filecatman.log")
        elif platform.system() == "Darwin":
            logPath = os.path.join(os.path.dirname(QSettings().fileName()), "com.filecatman.Filecatman.log")
        else: logPath = os.path.join(os.path.dirname(QSettings().fileName()), "Filecatman.log")
        if platform.system() == "Windows":
            os.startfile(logPath)
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.call(('open', logPath))
        else:
            os.system('xdg-open "{}"'.format(logPath))

    def openConfigFolder(self):
        if self.app.portableMode:
            configDir = "./"
        else:
            configDir = os.path.dirname(QSettings().fileName())
        if platform.system() == "Windows":
            os.startfile(configDir)
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.call(('open', configDir))
        else:
            os.system('xdg-open "{}"'.format(configDir))

    def closeDatabase(self):
        message = "Are you sure you want to close the current database?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setWindowTitle("Close the Current Database?")
        msgBox.setText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.writeDatabaseOptions()
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.close()
            if self.db.con.isOpen():
                self.db.close()
            self.config.writeConfig()
            self.app.openWizard()
        elif ret == msgBox.StandardButton.Cancel:
            pass
        msgBox.deleteLater()

    def openSQLiteDatabase(self):
        message = "Are you sure you want to close the current database?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setWindowTitle("Close the Current Database?")
        msgBox.setText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.writeDatabaseOptions()
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.close()
            if self.db.con.isOpen():
                self.db.close()
            self.config.writeConfig()
            self.app.openWizard(pageIden='OpenSQLite')
        elif ret == msgBox.StandardButton.Cancel:
            pass
        msgBox.deleteLater()

    def openMySQLDatabase(self):
        message = "Are you sure you want to close the current database?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setWindowTitle("Close the Current Database?")
        msgBox.setText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.writeDatabaseOptions()
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.close()
            if self.db.con.isOpen():
                self.db.close()
            self.config.writeConfig()
            self.app.openWizard(pageIden='OpenMySQL')
        elif ret == msgBox.StandardButton.Cancel:
            pass
        msgBox.deleteLater()

    def newSQLiteDatabase(self):
        message = "Are you sure you want to close the current database?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setWindowTitle("Close the Current Database?")
        msgBox.setText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.writeDatabaseOptions()
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.close()
            if self.db.con.isOpen():
                self.db.close()
            self.config.writeConfig()
            self.app.openWizard(pageIden='NewSQLite')
        elif ret == msgBox.StandardButton.Cancel:
            pass
        msgBox.deleteLater()

    def newMySQLDatabase(self):
        message = "Are you sure you want to close the current database?"
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setWindowTitle("Close the Current Database?")
        msgBox.setText(message)
        msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
        msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
        ret = msgBox.exec_()
        if ret == msgBox.StandardButton.Ok:
            self.writeDatabaseOptions()
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.close()
            if self.db.con.isOpen():
                self.db.close()
            self.config.writeConfig()
            self.app.openWizard(pageIden='NewMySQL')
        elif ret == msgBox.StandardButton.Cancel:
            pass
        msgBox.deleteLater()

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat('text/plain'):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        self.logger.debug("Text Dropped:\n"+e.mimeData().text())
        mimeData = e.mimeData().text()
        mimeDataPaths = mimeData.split("\n")
        for path in mimeDataPaths:
            dataPath = unquote(path.replace("file://", "")).strip()
            if os.path.exists(dataPath):
                if os.path.isfile(dataPath):
                    self.uploadDroppedFile(dataPath)
            else:
                self.uploadDroppedURL(path.strip())
        self.refreshMenu()

    def uploadDroppedFile(self, file):
        dataDir = self.config['options']['defaultDataDir']
        fileSource = file
        if fileSource:
            baseFilename = os.path.basename(fileSource)
            fileName = os.path.splitext(baseFilename)[0]
            fileExtension = os.path.splitext(fileSource)[1][1:].lower().strip()
            baseFilename = fileName+'.'+str(fileExtension)
            self.logger.debug(baseFilename)
            fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
            tableType = self.config['itemTypes'].tableFromNoun(fileType)
            if fileType:
                dirType = self.config['itemTypes'].dirFromNoun(fileType)
                fileDestination = getDataFilePath(dataDir, dirType, baseFilename)
                if not os.path.exists(getDataFilePath(dataDir, dirType, æscape(baseFilename))):
                    if uploadFile(self, fileSource, fileDestination, fileType):
                        self.db.open()
                        self.db.newItem(data=dict(name=baseFilename, type=tableType))
                        self.db.close()
                        return True
                    else:
                        warningMsgBox(self, "Error Uploading File")
                else:
                    self.logger.warning("File Already Exists: `{}`".format(baseFilename))
                    message = "Do you want you want to overwrite the existing file?"
                    msgBox = QMessageBox(self)
                    msgBox.setIcon(QMessageBox.Icon.Question)
                    msgBox.setWindowTitle("Overwrite Existing File?")
                    msgBox.setText(message)
                    msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                    msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                    ret = msgBox.exec_()
                    if ret == msgBox.StandardButton.Ok:
                        if uploadFile(self, fileSource, fileDestination, fileType):
                            return True
                        else:
                            warningMsgBox(self, "Error Uploading File")
                    elif ret == msgBox.StandardButton.Cancel:
                        self.logger.error("Upload Aborted.")
                    msgBox.deleteLater()
            else:
                warningMsgBox(self, "File type is not recognised. Upload aborted.", "Unknown File Type")

    def uploadDroppedURL(self, url):
        dataDir = self.config['options']['defaultDataDir']
        fileSource = url.replace("https://", "http://")
        if fileSource:
            baseFilename = os.path.basename(url.split('/')[-1])
            fileName = os.path.splitext(baseFilename)[0]
            fileExtension = os.path.splitext(baseFilename)[1][1:].lower().strip()
            baseFilename = fileName+'.'+str(fileExtension)
            self.logger.debug(baseFilename)
            fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
            tableType = self.config['itemTypes'].tableFromNoun(fileType)
            if fileType:
                dirType = self.config['itemTypes'].dirFromNoun(fileType)
                fileDestination = getDataFilePath(dataDir, dirType, baseFilename)
                if not os.path.exists(getDataFilePath(dataDir, dirType, æscape(baseFilename))):
                    if downloadFile(self, fileSource, fileDestination, fileType):
                        self.db.open()
                        self.db.newItem(data=dict(name=baseFilename, type=tableType, source=url))
                        self.db.close()
                        return True
                    else:
                        warningMsgBox(self, "Error Downloading File")
                else:
                    self.logger.warning("File Already Exists: `{}`".format(baseFilename))
                    message = "Do you want you want to overwrite the existing file?"
                    msgBox = QMessageBox(self)
                    msgBox.setIcon(QMessageBox.Icon.Question)
                    msgBox.setWindowTitle("Overwrite Existing File?")
                    msgBox.setText(message)
                    msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
                    msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
                    ret = msgBox.exec_()
                    if ret == msgBox.StandardButton.Ok:
                        if downloadFile(self, fileSource, fileDestination, fileType):
                            return True
                        else:
                            warningMsgBox(self, "Error Downloading File")
                    elif ret == msgBox.StandardButton.Cancel:
                        self.logger.error("Download Aborted.")
                    msgBox.deleteLater()
            else:
                warningMsgBox(self, "File type is not recognised. Upload aborted.", "Unknown File Type")

    def exitApp(self):
        if self.isInitialized:
            self.writeDatabaseOptions()
            self.config.writeConfig()
        self.app.exit()