import os
import logging
from PySide6.QtCore import Qt, QDir, QThread, Signal
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QWizard, QWizardPage, QMenu, QLineEdit, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGridLayout, QGroupBox, QTextEdit, QFrame
from filecatman.core import const
from filecatman.core.database import ÆDatabase
from filecatman.core.functions import loadUI


class StartupWizard(QWizard):
    pageID = dict(
        Welcome=0,
        OpenMySQL=1,
        ConnectToMySQL=2,
        OpenSQLite=3,
        ConnectToSQLite=4,
        NewSQLite=5,
        CreateSQLite=6,
        NewMySQL=7,
        CreateMySQL=8,
        DatabaseOptions=9,
        ConnectionStatus=10
    )
    skipConfig = True
    db = None
    connectionStatus = 0

    def __init__(self, app):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.icons = self.app.iconsList.icons
        self.pixmaps = self.app.iconsList.pixmaps
        self.config = self.app.config
        self.appName = app.applicationName()
        self.setWindowTitle(self.appName)
        self.setWindowIcon(self.icons['Filecatman'])
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setOption(QWizard.WizardOption.HaveHelpButton, True)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        self.setButtonText(self.WizardButton.CancelButton, "Exit")
        self.setWindowSizeAndCentre()

        self.setPage(self.pageID['Welcome'], WelcomePage(self))
        self.setPage(self.pageID['OpenMySQL'], OpenMySQLPage(self))
        self.setPage(self.pageID['ConnectToMySQL'], ConnectToMySQL(self))
        self.setPage(self.pageID['OpenSQLite'], OpenSQLitePage(self))
        self.setPage(self.pageID['ConnectToSQLite'], ConnectToSQLite(self))
        self.setPage(self.pageID['NewSQLite'], NewSQLitePage(self))
        self.setPage(self.pageID['CreateSQLite'], CreateSQLiteDatabase(self))
        self.setPage(self.pageID['NewMySQL'], NewMySQLPage(self))
        self.setPage(self.pageID['CreateMySQL'], CreateMySQLDatabase(self))
        self.setPage(self.pageID['DatabaseOptions'], DatabaseOptionsPage(self))
        self.setPage(self.pageID['ConnectionStatus'], ConnectionStatusPage(self))

        self.button(self.WizardButton.HelpButton).clicked.connect(self.openHelpBrowser)

    def setWindowSizeAndCentre(self):
        from PySide6.QtGui import QGuiApplication
        qr = self.frameGeometry()
        cp = QGuiApplication.screenAt(QCursor().pos()).availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def setIcons(self):
        self.page(0).ui.buttonNew.setIcon(self.icons['DatabaseNew'])
        self.page(0).ui.buttonOpen.setIcon(self.icons['DatabaseOpen'])
        self.page(0).ui.actionNewSQLite.setIcon(self.icons['DatabaseNew'])
        self.page(0).ui.actionNewMySQL.setIcon(self.icons['DatabaseNew'])
        self.page(0).ui.actionOpenSQLite.setIcon(self.icons['DatabaseOpen'])
        self.page(0).ui.actionOpenMySQL.setIcon(self.icons['DatabaseOpen'])
        self.page(1).setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['Open'])
        self.page(3).setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['Open'])
        self.page(5).setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['New'])
        self.page(7).setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['New'])

    def initializeWizard(self):
        self.db = None
        self.show()

    def accept(self):
        self.config['db'] = self.config['db']
        if self.db is not None:
            if self.db.con.isOpen():
                self.db.close()
            self.app.database = self.db

        if self.field('autoloadDatabase1') | self.field('autoloadDatabase2') | self.field('autoloadDatabase3'):
            self.config['autoloadDatabase'] = True
        if self.field('DatabaseOptionDataDir'):
            self.config['options'] = dict()
            self.config['options']['defaultDataDir'] = self.field('DatabaseOptionDataDir')
            self.config['options']['catLvls'] = self.field('DatabaseOptionCatLvls')

        self.close()
        self.app.openMainWindow()

    def openHelpBrowser(self):
        self.app.openHelpBrowser("startupwizard.html")


class WelcomePage(QWizardPage):
    nextPageIden = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.setTitle('<span style=" font-size:14pt;">'+self.wizard.appName+'</span>')
        self.setSubTitle("A file categorization management program.")
        self.ui = loadUI("gui/ui/wizardmenu.ui")
        self.setLayout(self.ui.layout())

        self.ui.buttonNew.setIcon(self.wizard.icons['DatabaseNew'])
        self.ui.buttonOpen.setIcon(self.wizard.icons['DatabaseOpen'])

        self.constructRestOfUI()
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Filecatman48'])

    def constructRestOfUI(self):
        self.ui.menuNewDatabase = QMenu()
        self.ui.actionNewSQLite = QAction(self.wizard.icons['DatabaseNew'], "New &SQLite Database", self)
        self.ui.actionNewMySQL = QAction(self.wizard.icons['DatabaseNew'], "New &MySQL Database", self)
        self.ui.menuNewDatabase.addActions((self.ui.actionNewSQLite, self.ui.actionNewMySQL))
        self.ui.buttonNew.setMenu(self.ui.menuNewDatabase)

        self.ui.menuOpenDatabase = QMenu()
        self.ui.actionOpenSQLite = QAction(self.wizard.icons['DatabaseOpen'], "Open &SQLite Database", self)
        self.ui.actionOpenMySQL = QAction(self.wizard.icons['DatabaseOpen'], "Open &MySQL Database", self)
        self.ui.menuOpenDatabase.addActions((self.ui.actionOpenSQLite, self.ui.actionOpenMySQL))
        self.ui.buttonOpen.setMenu(self.ui.menuOpenDatabase)

        self.ui.actionNewSQLite.triggered.connect(lambda: self.onButtonPressGoToNext(self.wizard.pageID['NewSQLite']))
        self.ui.actionNewMySQL.triggered.connect(lambda: self.onButtonPressGoToNext(self.wizard.pageID['NewMySQL']))
        self.ui.actionOpenSQLite.triggered.connect(lambda: self.onButtonPressGoToNext(self.wizard.pageID['OpenSQLite']))
        self.ui.actionOpenMySQL.triggered.connect(lambda: self.onButtonPressGoToNext(self.wizard.pageID['OpenMySQL']))

    def onButtonPressGoToNext(self, nextPage):
        self.nextPageIden = nextPage
        self.wizard.next()

    def nextId(self):
        if self.nextPageIden is not None:
            return self.nextPageIden
        else:
            return 0

    def isComplete(self):
        return False


class OpenMySQLPage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardopenmysql.ui")
        self.setLayout(self.ui.layout())
        self.setTabOrder(self.ui.lineHost, self.ui.spinPort)
        self.setTabOrder(self.ui.spinPort, self.ui.lineUser)
        self.setTabOrder(self.ui.lineUser, self.ui.linePass)
        self.setTabOrder(self.ui.linePass, self.ui.lineDatabase)
        self.setTabOrder(self.ui.lineDatabase, self.ui.checkOpenLast)
        self.setTitle("Open Existing MySQL Database")
        self.setSubTitle("Connect to a MySQL server and open a database.")
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Open'])

        self.setFields()

    def initializePage(self):
        self.setDefaults()
        self.ui.lineHost.selectAll()

    def setDefaults(self):
        self.ui.linePass.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.ui.lineHost.setText("localhost")

    def setFields(self):
        self.registerField('DatabaseHost*', self.ui.lineHost)
        self.registerField('DatabaseUser*', self.ui.lineUser)
        self.registerField('DatabasePassword', self.ui.linePass)
        self.registerField('DatabaseName*', self.ui.lineDatabase)
        self.registerField('DatabasePort', self.ui.spinPort)
        self.registerField('autoloadDatabase1', self.ui.checkOpenLast)

    def nextId(self):
        return self.wizard.pageID['ConnectToMySQL']


class ConnectToMySQL(QWizardPage):
    config = None
    testDBThread = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardprogress.ui")
        self.setLayout(self.ui.layout())

        self.setTitle("Connecting To MySQL Database")
        self.setSubTitle("Currently attempting to connect to MySQL database.")
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Filecatman48'])

    def cleanupPage(self):
        try:
            self.testDBThread.disconnect(self.testDBThread)
            self.testDBThread.connectionFinished.disconnect()
            self.testDBThread.db = None
            self.testDBThread.quit()
            self.testDBThread = None
            super().cleanupPage()
        except RuntimeError:
            pass

    def initializePage(self):
        self.config = {
            'host': str(self.wizard.field('DatabaseHost')),
            'port': self.wizard.field('DatabasePort'),
            'user': str(self.wizard.field('DatabaseUser')),
            'passwd': str(self.wizard.field('DatabasePassword')),
            'db': str(self.wizard.field('DatabaseName')),
            'type': 'mysql'
        }
        self.testDBThread = TestDBThread(self, self.config)
        self.testDBThread.connectionFinished.connect(self.goToStatusPage, Qt.UniqueConnection)
        self.testDBThread.start()

    def goToStatusPage(self):
        if self.testDBThread:
            if self.testDBThread.connectionStatus is 1:
                self.wizard.connectionStatus = 1
                self.wizard.db = self.testDBThread.db
                self.wizard.config['db'] = self.config
                self.wizard.config['db']['type'] = "mysql"
            elif self.testDBThread.connectionStatus is 0:
                self.config.clear()
                self.wizard.connectionStatus = 0
                self.wizard.connectionError = self.testDBThread.connectionError
            self.testDBThread.deleteLater()
            self.wizard.next()

    def isComplete(self):
        return False

    def nextId(self):
        return self.wizard.pageID['ConnectionStatus']


class ConnectionStatusPage(QWizardPage):
    connectionStatus = 0
    db = None
    databaseInfoCreated = None
    groupSQL = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)

    def cleanupPage(self):
        self.wizard.setOption(self.wizard.HaveCustomButton1, False)
        self.wizard.setOption(self.wizard.NoBackButtonOnLastPage, False)

    def backToForm(self):
        self.wizard.back()
        self.wizard.back()
        if self.wizard.currentId() is self.wizard.pageID['Welcome']:
            self.wizard.next()

    def initializePage(self):
        self.wizard.setOption(self.wizard.NoBackButtonOnLastPage, True)
        backButton = QPushButton("< &Back")
        self.wizard.setButton(self.wizard.CustomButton1, backButton)
        self.wizard.customButtonClicked.connect(self.backToForm)
        self.wizard.setOption(self.wizard.HaveCustomButton1, True)

        self.db = self.wizard.db
        if self.wizard.connectionStatus is 1:
            self.connectionStatus = 1
            self.logger.info('Database Connection Successful.')
            self.setTitle("Connection Established")
            self.setSubTitle("Successfully connected to the MySQL database.")
            self.label.hide()
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.db.open()
            databaseInfo(self, self.db)
            self.db.close()
        elif self.wizard.connectionStatus is 0:
            self.connectionStatus = 0
            self.logger.error("Error: {}".format(self.wizard.connectionError))
            self.label.show()
            self.label.setText("<b>Error:</b> {}".format(self.wizard.connectionError))
            self.logger.error('Database Connection failed.')
            self.setTitle("Connection to MySQL Failed")
            self.setSubTitle("Failed at connecting to the MySQL database.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.layout().takeAt(1)
            if self.groupSQL:
                self.groupSQL.setTitle(None)
                self.groupSQL.hide()

    def isComplete(self):
        if self.connectionStatus is 1:
            return True
        else:
            return False

    def nextId(self):
        return -1


class OpenSQLitePage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardopensqlite.ui")
        self.setLayout(self.ui.layout())

        self.setTitle("Open Existing SQLite Database")
        self.setSubTitle("Choose a SQLite database file to open.")
        self.setFields()

        self.setTabOrder(self.ui.buttonBrowse, self.ui.checkOpenLast)
        self.ui.buttonBrowse.setFocus()

        self.ui.buttonBrowse.clicked.connect(self.openFileDialog)
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Open'])

    def setFields(self):
        self.registerField('DatabaseFile*', self.ui.lineFile)
        self.registerField('autoloadDatabase2', self.ui.checkOpenLast)

    def openFileDialog(self):
        fileObj = QFileDialog().getOpenFileName(None, "Open SQLite Database", dir=QDir().homePath())
        filename = fileObj[0]
        self.logger.debug(filename)
        self.ui.lineFile.setText(filename)

    def nextId(self):
        return self.wizard.pageID['ConnectToSQLite']


class ConnectToSQLite(QWizardPage):
    connectionStatus = 0
    databaseInfoCreated = None
    groupSQL = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)

    def initializePage(self):
        config = {
            'db': str(self.wizard.field('DatabaseFile')),
            'type': 'sqlite'
        }
        try:
            db = ÆDatabase(config)
            db.open()
            self.logger.info('Database Connection Successful.')
            self.connectionStatus = 1
            self.setTitle("Connection Established")
            self.setSubTitle("Successfully connected to the SQLite database.")
            self.label.hide()
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.wizard.config['db'] = config
            self.wizard.db = db
            databaseInfo(self, db)
            db.close()
        except BaseException as e:
            self.label.show()
            self.label.setText("<b>Error:</b> {}".format(e))
            self.logger.error('Database Connection failed.')
            self.connectionStatus = 0
            self.setTitle("Connection to SQLite Failed")
            self.setSubTitle("Failed at connecting to the SQLite database.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.layout().takeAt(1)
            if self.groupSQL:
                self.groupSQL.setTitle(None)
                self.groupSQL.hide()

    def isComplete(self):
        if self.connectionStatus is 1:
            return True
        else:
            return False

    def nextId(self):
        return -1


class NewSQLitePage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardnewsqlite.ui")
        self.setLayout(self.ui.layout())

        self.setTitle("Create an SQLite Database")
        self.setSubTitle("Create a new database in an SQLite file.")
        self.setMandatoryFields()

        self.ui.buttonBrowse.clicked.connect(self.saveFileDialog)
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['New'])

    def setMandatoryFields(self):
        self.registerField('NewSQLiteFile*', self.ui.lineFile)

    def saveFileDialog(self):
        saveFileDialog = QFileDialog()
        saveFileDialog.setFileMode(saveFileDialog.FileMode.AnyFile)
        saveFileDialog.setNameFilter("Filecatman Database (*.db)")
        saveFileDialog.setDefaultSuffix('db')
        saveFileDialog.setDirectory(QDir().homePath())
        saveFileDialog.setWindowTitle("New SQLite Database")
        saveFileDialog.setViewMode(saveFileDialog.ViewMode.List)
        saveFileDialog.setAcceptMode(saveFileDialog.AcceptMode.AcceptSave)
        if saveFileDialog.exec_():
            fileObj = saveFileDialog.selectedFiles()
            filename = fileObj[0]
            self.logger.debug(filename)
            self.ui.lineFile.setText(filename)

    def nextId(self):
        return self.wizard.pageID['CreateSQLite']


class CreateSQLiteDatabase(QWizardPage):
    connectionStatus = 0
    databaseInfoCreated = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)

    def initializePage(self):
        config = {
            'db': str(self.wizard.field('NewSQLiteFile')),
            'type': 'sqlite',
            'create': True
        }
        try:
            db = ÆDatabase(config)
            db.open()
            self.logger.info('Database Creation Successful.')
            self.connectionStatus = 1
            self.setTitle("Database Created")
            self.setSubTitle("Successfully created an SQLite database.")
            self.label.setText("The project database was successfully created. Click next to set the database options.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.wizard.config['db'] = config
            self.wizard.db = db
            db.close()
        except BaseException as e:
            self.label.setText("<b>Error:</b> {}".format(e))
            self.logger.error('Database Creation failed.')
            self.connectionStatus = 0
            self.setTitle("Failed at Creating SQLite Database")
            self.setSubTitle("Failed at creating an SQLite database.")
            self.setPixmap(self.wizard.WizardPixmap.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.layout().takeAt(1)

    def isComplete(self):
        if self.connectionStatus is 1:
            return True
        else:
            return False

    def nextId(self):
        return self.wizard.pageID['DatabaseOptions']


class NewMySQLPage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardnewmysql.ui")
        self.setLayout(self.ui.layout())
        self.ui.labelHost.setMinimumWidth(120)
        self.ui.labelDatabase.setMinimumWidth(120)
        self.setTabOrder(self.ui.lineHost, self.ui.spinPort)
        self.setTabOrder(self.ui.spinPort, self.ui.lineUser)
        self.setTabOrder(self.ui.lineUser, self.ui.linePass)
        self.setTabOrder(self.ui.linePass, self.ui.lineDatabase)
        self.setTitle("New MySQL Database")
        self.setSubTitle("Create a new database on a MySQL server.")
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['New'])

        self.setFields()

    def initializePage(self):
        self.setDefaults()
        self.ui.lineHost.selectAll()

    def setDefaults(self):
        self.ui.linePass.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.ui.lineHost.setText("localhost")

    def setFields(self):
        self.registerField('NewMySQLDatabaseHost*', self.ui.lineHost)
        self.registerField('NewMySQLDatabasePort', self.ui.spinPort)
        self.registerField('NewMySQLDatabaseUser*', self.ui.lineUser)
        self.registerField('NewMySQLDatabasePassword', self.ui.linePass)
        self.registerField('NewMySQLDatabaseName*', self.ui.lineDatabase)

    def nextId(self):
        return self.wizard.pageID['CreateMySQL']


class CreateMySQLDatabase(QWizardPage):
    config = None
    testDBThread = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/wizardprogress.ui")
        self.setLayout(self.ui.layout())
        self.setTitle("Connecting To MySQL Database")
        self.setSubTitle("Currently attempting to connect to MySQL database.")
        self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Filecatman48'])

    def cleanupPage(self):
        try:
            self.testDBThread.disconnect(self.testDBThread)
            self.testDBThread.connectionFinished.disconnect()
            self.testDBThread.db = None
            self.testDBThread.quit()
            self.testDBThread = None
            super().cleanupPage()
        except RuntimeError:
            pass

    def initializePage(self):
        self.config = {
            'host': str(self.wizard.field('NewMySQLDatabaseHost')),
            'port': self.wizard.field('NewMySQLDatabasePort'),
            'user': str(self.wizard.field('NewMySQLDatabaseUser')),
            'passwd': str(self.wizard.field('NewMySQLDatabasePassword')),
            'db': str(self.wizard.field('NewMySQLDatabaseName')),
            'type': 'mysql',
            'create': True
        }
        self.testDBThread = TestDBThread(self, self.config)
        self.testDBThread.connectionFinished.connect(self.goToNextPage, Qt.UniqueConnection)
        self.testDBThread.start()

    def goToNextPage(self):
        if self.testDBThread:
            if self.testDBThread.connectionStatus is 1:
                self.wizard.connectionStatus = 1
                self.wizard.db = self.testDBThread.db
                self.wizard.config['db'] = self.config
                self.wizard.config['db']['type'] = "mysql"
            elif self.testDBThread.connectionStatus is 0:
                self.config.clear()
                self.wizard.connectionStatus = 0
                self.wizard.connectionError = self.testDBThread.connectionError
            self.testDBThread.deleteLater()
            self.wizard.next()

    def isComplete(self):
        return False

    def nextId(self):
        if self.wizard.connectionStatus is 1:
            return self.wizard.pageID['DatabaseOptions']
        else:
            return self.wizard.pageID['ConnectionStatus']


class DatabaseOptionsPage(QWizardPage):

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.ui = loadUI("gui/ui/preferencesdatabase.ui")
        self.setLayout(self.ui.databaseTab.layout())
        self.setTitle("Set Database Options")
        self.setSubTitle("Set the preferences for this database.")

        self.ui.buttonDataDir.clicked.connect(self.openFileDialog)
        self.setDefaults()
        self.setMandatoryFields()

    def setDefaults(self):
        self.ui.spinCatLvls.setValue(const.MAXCATLVLS)

    def setMandatoryFields(self):
        self.registerField('autoloadDatabase3', self.ui.checkOpenLast)
        self.registerField('DatabaseOptionDataDir*', self.ui.lineDataDir)
        self.registerField('DatabaseOptionCatLvls', self.ui.spinCatLvls)

    def openFileDialog(self):
        openDialog = QFileDialog(self)
        openDialog.setFileMode(openDialog.FileMode.Directory)
        openDialog.setDirectory(QDir().homePath())
        openDialog.setWindowTitle("Select Data Directory")
        openDialog.setViewMode(openDialog.ViewMode.List)
        openDialog.setOption(openDialog.Option.ShowDirsOnly, True)
        if openDialog.exec_():
            fileObj = openDialog.selectedFiles()
            filename = fileObj[0] + "/"
            self.logger.debug(filename)
            self.ui.lineDataDir.setText(filename)

    def nextId(self):
        return -1


def databaseInfo(parent, db):
    if not parent.databaseInfoCreated:
        parent.labelName = QLabel()
        parent.labelDataDir = QLabel()
        parent.labelItemCount = QLabel()
        parent.labelCatCount = QLabel()
        parent.labelRelationCount = QLabel()
        parent.dataName = QLabel()
        parent.dataDataDir = QTextEdit()
        parent.dataDataDir.setReadOnly(True)
        parent.dataDataDir.setFrameStyle(QFrame.NoFrame)
        parent.dataDataDir.setStyleSheet("background: rgba(0,0,0,0%)")
        parent.dataDataDir.setContextMenuPolicy(Qt.PreventContextMenu)
        parent.dataItemCount = QLabel()
        parent.dataCatCount = QLabel()
        parent.dataRelationCount = QLabel()
        parent.labelTables = QLabel()
        parent.labelTables.setWordWrap(True)

        parent.gridlayout = QGridLayout()
        parent.gridlayout.addWidget(parent.labelName, 0, 0)
        parent.gridlayout.addWidget(parent.dataName, 0, 1)
        parent.gridlayout.addWidget(parent.labelDataDir, 1, 0)
        parent.gridlayout.addWidget(parent.dataDataDir, 1, 1)
        parent.gridlayout.addWidget(parent.labelItemCount, 2, 0)
        parent.gridlayout.addWidget(parent.dataItemCount, 2, 1)
        parent.gridlayout.addWidget(parent.labelCatCount, 3, 0)
        parent.gridlayout.addWidget(parent.dataCatCount, 3, 1)
        parent.gridlayout.addWidget(parent.labelRelationCount, 4, 0)
        parent.gridlayout.addWidget(parent.dataRelationCount, 4, 1)
        parent.gridlayout.addWidget(parent.labelTables, 5, 0, 1, 2)
        parent.groupSQL = QGroupBox()
        parent.groupSQL.setLayout(parent.gridlayout)
        parent.databaseInfoCreated = 1

    parent.layout().takeAt(1)
    parent.layout().addWidget(parent.groupSQL)

    parent.groupSQL.setTitle("Database Information")
    parent.labelName.setText("<b>Name:</b> ")
    parent.labelDataDir.setText("<b>Data Folder:</b> ")
    parent.labelItemCount.setText("<b>Item Count:</b> ")
    parent.labelCatCount.setText("<b>Category Count:</b> ")
    parent.labelRelationCount.setText("<b>Relation Count:</b> ")
    parent.dataName.setText(os.path.basename(db.config['db']))
    parent.dataDataDir.setText(str(db.selectOption('defaultDataDir')))
    parent.dataItemCount.setText(str(db.selectCount('items')))
    parent.dataCatCount.setText(str(db.selectCount('terms')))
    parent.dataRelationCount.setText(str(db.selectCount('term_relationships')))

    tables = ", ".join(db.tables())
    parent.labelTables.setText("<b>Tables:</b> "+tables)
    parent.groupSQL.show()


class TestDBThread(QThread):
    connectionFinished = Signal()
    connectionStatus = 0
    connectionError = None
    db = None

    def __init__(self, parent, config):
        super().__init__(parent)
        self.wizard = parent.wizard
        self.logger = parent.logger
        self.config = config

    def run(self):
        try:
            self.logger.debug("Connecting to database.")
            self.db = ÆDatabase(self.config)

            self.connectionStatus = 1
            if self.db and not self.wizard.isHidden():
                self.connectionFinished.emit()

        except BaseException as e:
            self.connectionError = e
            self.connectionStatus = 0
            if not self.wizard.isHidden():
                self.connectionFinished.emit()