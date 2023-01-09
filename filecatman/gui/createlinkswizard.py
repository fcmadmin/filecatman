import os
import logging
from urllib.parse import unquote
from PySide6.QtCore import QElapsedTimer, QThread, Signal, QDate, QDateTime, QFile, QIODevice, QTextStream
from PySide6.QtSql import QSqlQuery
from PySide6.QtWidgets import QWizardPage, QWizard, QFileDialog, QPushButton, QLabel, QVBoxLayout
from filecatman.core.namespace import Æ
from filecatman.core.functions import loadUI


class CreateLinksWizard(QWizard):
    pageID = dict(
        ConfirmCreation=0,
        Progress=1,
        Finish=3,
        CreationCancelled=4
    )
    linksCreatedSig = Signal()
    maxLinksCount, itemsTimeCount, relationCount = 0, 0, 0
    elapsedTime = 0
    creationSuccess = None
    lastError = None
    threadRunning = False

    def __init__(self, parent):
        super(CreateLinksWizard, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setModal(True)
        self.mainWindow = parent
        self.app = self.mainWindow.app
        self.config = parent.config
        self.icons = parent.icons
        self.pixmaps = parent.pixmaps
        self.db = parent.db

        self.setWindowTitle("Create Symbolic Links")
        self.setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['SymbolicLink'])
        self.setOption(self.WizardOption.IndependentPages, False)
        self.setOption(self.WizardOption.NoBackButtonOnLastPage, True)
        self.setOption(self.WizardOption.HaveHelpButton, True)

        self.setPage(self.pageID['ConfirmCreation'], ConfirmCreationPage(self))
        self.setPage(self.pageID['Progress'], ProgressPage(self))
        self.setPage(self.pageID['Finish'], FinishPage(self))
        self.setPage(self.pageID['CreationCancelled'], CreationCancelledPage(self))

        self.button(self.WizardButton.HelpButton).clicked.connect(self.openHelpBrowser)

    def openHelpBrowser(self):
        if not self.threadRunning:
            self.close()
            self.app.openHelpBrowser("createlinks.html")

    def accept(self):
        self.close()

    def reject(self):
        if not self.threadRunning:
            super().reject()


class ConfirmCreationPage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.config = parent.config
        self.setTitle("Create Symbolic Links to Files")
        self.setSubTitle("Do you want to create symbolic links to the files?")
        self.setCommitPage(True)
        self.ui = loadUI("gui/ui/createlinkswizardconfirm.ui")
        self.setLayout(self.ui.layout())
        self.setFields()

        self.ui.buttonBrowse.clicked.connect(self.selectDirectoryDialog)

    def initializePage(self):
        self.setDefaults()

    def setDefaults(self):
        self.db.open()
        queryTimeCount = QSqlQuery("SELECT COUNT(*) FROM items WHERE (item_time <> '0000-00-00 00:00:00')", self.db.con)
        if queryTimeCount.first():
            self.wizard.itemsTimeCount = queryTimeCount.value(0)

        noLinkTypes = self.config['itemTypes'].tableNames(Æ.NoWeblinks)
        linkTypeCountSQL = "SELECT COUNT(*) FROM items"
        linkTypeCountSQL += " WHERE type_id NOT IN ('{}') ".format("', '".join(noLinkTypes))
        queryLinksCount = QSqlQuery(linkTypeCountSQL, self.db.con)
        if queryLinksCount.first():
            self.wizard.linkTypeCount = queryLinksCount.value(0)

        self.wizard.relationCount = self.db.selectCount("term_relationships")
        self.db.close()
        self.wizard.maxLinksCount = self.wizard.relationCount+self.wizard.itemsTimeCount+self.wizard.linkTypeCount
        self.ui.labelLinksValue.setText(str(self.wizard.maxLinksCount))

        dataDir = self.config['options']['defaultDataDir']
        if os.path.isdir(os.getcwd() + "/" + dataDir[:-1]):
            dataDir = os.getcwd() + "/" + dataDir[:-1]
        else:
            dataDir = dataDir[:-1]
        parentDir = os.path.dirname(dataDir)
        self.ui.lineFile.setText(parentDir)

    def setFields(self):
        self.registerField('linksDir*', self.ui.lineFile)
        self.registerField('overwriteLinks', self.ui.checkOverwrite)

    def selectDirectoryDialog(self):
        selectDirectoryDialog = QFileDialog(self)
        selectDirectoryDialog.setFileMode(selectDirectoryDialog.FileMode.Directory)
        dataDir = self.config['options']['defaultDataDir']
        if os.path.isdir(os.getcwd() + "/" + dataDir[:-1]):
            dataDir = os.getcwd() + "/" + dataDir[:-1]
        else:
            dataDir = dataDir[:-1]
        self.logger.debug("Data dir: "+dataDir)
        parentDir = os.path.dirname(dataDir)
        self.logger.debug("Parent dir: "+parentDir)
        selectDirectoryDialog.setDirectory(parentDir)
        selectDirectoryDialog.setWindowTitle("Select Data Directory")
        selectDirectoryDialog.setViewMode(selectDirectoryDialog.ViewMode.List)
        selectDirectoryDialog.setOption(selectDirectoryDialog.Option.ShowDirsOnly, True)
        if selectDirectoryDialog.exec_():
            fileObj = selectDirectoryDialog.selectedFiles()
            dirName = fileObj[0]
            self.logger.debug(dirName)
            self.ui.lineFile.setText(dirName)


class ProgressPage(QWizardPage):
    createLinksThread = None
    linksCreatedCount, linksOverwrittenCount, linksExistingCount = 0, 0, 0
    elapsedTime = None
    creationCancelled = None
    timer = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.setTitle("Link Creation Progress")
        self.setSubTitle("Current progress of link creation operation.")
        self.ui = loadUI("gui/ui/createlinkswizardprogress.ui")
        self.setLayout(self.ui.layout())

    def initializePage(self):
        self.creationCancelled = None
        stopButton = QPushButton("Cancel Creation")
        self.wizard.setButton(QWizard.WizardButton.CustomButton1, stopButton)
        self.wizard.customButtonClicked.connect(self.terminateCreation)
        self.wizard.setOption(QWizard.WizardOption.NoCancelButton, True)
        self.wizard.setOption(QWizard.WizardOption.HaveCustomButton1, True)

        maximumCount = self.wizard.maxLinksCount
        self.ui.progressBar.setRange(0, maximumCount)

        try:
            self.createLinksThread = CreateLinksThread(self)
            self.createLinksThread.timerStartedSig.connect(self.timerStart)
            self.createLinksThread.finished.connect(self.goToFinish)
            self.createLinksThread.linkCreatedSig.connect(self.updateLinksCreatedProgress)
            self.createLinksThread.linkOverwrittenSig.connect(self.updateLinksOverwrittenProgress)
            self.createLinksThread.linkExistingSig.connect(self.updateLinksExistingProgress)
            self.createLinksThread.errorSig.connect(self.updateErrors)
            self.createLinksThread.start()
        except BaseException as e:
            self.logger.error("Error: {}".format(str(e)))
            self.wizard.lastError = str(e)
            return False

    def timerStart(self):
        self.timer = QElapsedTimer()
        self.timer.start()

    def timerCheck(self):
        time = '{0:.3f}'.format(round(self.timer.elapsed()/1000, 3))
        self.ui.labelElapsedValue.setText(time+" Seconds")

    def terminateCreation(self):
        self.creationCancelled = True
        self.createLinksThread.exit()
        self.createLinksThread.wait()
        self.wizard.next()

    def updateLinksCreatedProgress(self, count, rowName):
        self.ui.labelCreatedValue.setText(str(count)+" / "+str(self.wizard.maxLinksCount))
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        self.ui.labelCurrentlyValue.setText(rowName)
        self.timerCheck()

    def updateLinksOverwrittenProgress(self, overwrittenCount, existingcount, createdCount, rowName):
        self.ui.labelOverwrittenValue.setText(str(overwrittenCount))
        self.ui.labelExistingValue.setText(str(existingcount))
        self.ui.labelCreatedValue.setText(str(createdCount)+" / "+str(self.wizard.maxLinksCount))
        self.ui.labelCurrentlyValue.setText(rowName)
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        self.timerCheck()

    def updateLinksExistingProgress(self, count):
        self.ui.labelExistingValue.setText(str(count))
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        self.timerCheck()

    def updateErrors(self, count):
        self.ui.labelErrorsValue.setText(str(count))

    def goToFinish(self):
        self.wizard.linksCreated = self.createLinksThread.linksCreatedCount
        self.wizard.linksOverwritten = self.createLinksThread.linksOverwrittenCount
        self.wizard.linksAlreadyExisting = self.createLinksThread.linksAlreadyExistingCount
        self.wizard.elapsedTime = round(self.timer.elapsed()/1000, 3)
        self.wizard.creationErrors = self.createLinksThread.errorCount
        self.logger.debug("Elapsed time: "+str(self.wizard.elapsedTime)+" Seconds")
        self.wizard.next()

    def isComplete(self):
        return False

    def nextId(self):
        if self.creationCancelled is True:
            return self.wizard.pageID['CreationCancelled']
        else:
            return self.wizard.pageID['Finish']


class FinishPage(QWizardPage):
    creationStatus = 0

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.labelTime = QLabel()
        self.labelTime.setWordWrap(True)
        self.labelLinksCreated = QLabel()
        self.labelLinksCreated.setWordWrap(True)
        self.labelLinksOverwritten = QLabel()
        self.labelLinksOverwritten.setWordWrap(True)
        self.labelLinksExisting = QLabel()
        self.labelLinksExisting.setWordWrap(True)
        self.labelErrors = QLabel()
        self.labelErrors.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.labelTime)
        self.layout().addWidget(self.labelLinksCreated)
        self.layout().addWidget(self.labelLinksOverwritten)
        self.layout().addWidget(self.labelLinksExisting)
        self.layout().addWidget(self.labelErrors)

    def initializePage(self):
        self.setFinalPage(True)
        self.wizard.setOption(self.wizard.WizardOption.HaveCustomButton1, False)
        if self.wizard.creationSuccess is True:
            self.logger.info('Symbolic Links Creation Successful.')
            self.creationStatus = 1
            self.setTitle("Links Created")
            self.setSubTitle("Successfully created symbolic links.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.labelTime.setText("<b>Time taken to create:</b> {} Seconds".format(self.wizard.elapsedTime))
            self.labelLinksCreated.setText("<b>Links created:</b> {} / {}"
                .format(self.wizard.linksCreated, self.wizard.maxLinksCount))
            self.labelLinksOverwritten.setText("<b>Links overwritten:</b> {}".format(self.wizard.linksOverwritten))
            self.labelLinksExisting.setText("<b>Links already existing:</b> {}"
                .format(self.wizard.linksAlreadyExisting))
            self.labelErrors.setText("<b>Errors:</b> {}".format(self.wizard.creationErrors))
            self.wizard.linksCreatedSig.emit()
        else:
            self.logger.error('Link Creation Failed.')
            self.creationStatus = 0
            self.setTitle("Link Creation Failed")
            self.setSubTitle("Failed to create symbolic links.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.labelTime.setText("<b>Error:</b> {}".format(self.wizard.lastError))
            self.labelLinksCreated.setText(None)
            self.labelLinksOverwritten.setText(None)
            self.labelLinksExisting.setText(None)
            self.labelErrors.setText(None)

    def isComplete(self):
        return True

    def nextId(self):
        return -1


class CreationCancelledPage(QWizardPage):
    creationStatus = 0

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)

    def initializePage(self):
        self.setFinalPage(True)
        self.wizard.setOption(self.wizard.WizardOption.HaveCustomButton1, False)
        self.logger.info('Link Creation Cancelled.')
        self.creationStatus = 1
        self.setTitle("Link Creation Cancelled")
        self.setSubTitle("The link creation operation was cancelled.")
        self.label.setText("Symbolic links creation aborted.")

    def nextId(self):
        return -1


class CreateLinksThread(QThread):
    linksCreatedCount, linksOverwrittenCount, linksAlreadyExistingCount, errorCount = 0, 0, 0, 0
    elapsedTime = None

    linkCreatedSig = Signal(int, str)
    linkOverwrittenSig = Signal(int, int, int, str)
    linkExistingSig = Signal(int)
    errorSig = Signal(int)
    timerStartedSig = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent.wizard
        self.progressPage = parent
        self.db = parent.db
        self.config = parent.wizard.config

        self.dataDir = self.wizard.config['options']['defaultDataDir']
        if os.path.isdir(os.getcwd() + "/" + self.dataDir[:-1]):
            self.dataDir = os.getcwd() + "/" + self.dataDir
        self.workingDir = self.wizard.field("linksDir")
        self.overwriteLinks = self.wizard.field("overwriteLinks")
        self.logger.debug("Overwrite Links: "+str(self.overwriteLinks))

        self.fileCreated = QFile(self.workingDir+"/LinksCreated.log")
        self.fileCreated.open(QIODevice.WriteOnly | QFile.Truncate)
        self.streamCreated = QTextStream(self.fileCreated)
        self.fileOverwritten = QFile(self.workingDir+"/LinksOverwritten.log")
        self.fileOverwritten.open(QIODevice.WriteOnly | QFile.Truncate)
        self.streamOverwritten = QTextStream(self.fileOverwritten)
        self.fileExisting = QFile(self.workingDir+"/LinksAlreadyExist.log")
        self.fileExisting.open(QIODevice.WriteOnly | QFile.Truncate)
        self.streamExisting = QTextStream(self.fileExisting)
        self.fileErrors = QFile(self.workingDir+"/LinkErrors.log")
        self.fileErrors.open(QIODevice.WriteOnly | QFile.Truncate)
        self.streamErrors = QTextStream(self.fileErrors)

    def run(self):
        self.wizard.threadRunning = True

        self.timerStartedSig.emit()
        self.linksCreatedCount, self.linksOverwrittenCount, self.linksAlreadyExistingCount = 0, 0, 0
        self.db.open()

        sqlItems = "SELECT i.item_id, i.item_name, i.type_id, i.item_source, " \
                   "i.item_time FROM items AS i"
        queryItems = QSqlQuery(self.db.con)
        queryItems.setForwardOnly(True)
        queryRelations = QSqlQuery(self.db.con)
        queryRelations.setForwardOnly(True)

        queryItems.exec_(sqlItems)

        while queryItems.next() and not self.progressPage.creationCancelled:
            itemIden = queryItems.value(0)
            itemName = queryItems.value(1)
            itemType = queryItems.value(2)
            itemSource = unquote(queryItems.value(3))
            itemTime = queryItems.value(4)
            typeDir = self.config['itemTypes'].dirFromTable(itemType)

            if itemType in self.config['itemTypes'].tableNames(Æ.NoWeblinks):
                filePath = os.path.join(self.dataDir,typeDir,itemName)
                if not os.path.exists(filePath):
                    errorMessage = "File Error: File '{}' not found.".format(itemName)
                    self.logger.error(errorMessage)
                    self.streamErrors << errorMessage << '\n'
                    self.errorCount += 1
                    self.errorSig.emit(self.errorCount)
                    continue
            else:
                linkPath = os.path.join(self.workingDir, 'Media', typeDir, itemName+"."+self.desktopFileExt())
                if not self.createDesktopFile(linkPath, itemName, itemSource):
                    self.wizard.creationSuccess = False
                    return False

            if isinstance(itemTime, str):
                date = itemTime.split(" ")[0]
                dateTime = QDate().fromString(date, 'yyyy-MM-dd')
                if dateTime.isValid():
                    timeYear = dateTime.toString('yyyy')
                    timeMonth = dateTime.toString('MMMM')
                    if itemType in self.config['itemTypes'].tableNames(Æ.IsWeblinks):
                        timeLink = os.path.join(self.workingDir, "Time", timeYear, timeMonth, typeDir, itemName+'.'+self.desktopFileExt())
                        if not self.createDesktopFile(timeLink, itemName, itemSource):
                            self.wizard.creationSuccess = False
                            return False
                    elif itemType in self.config['itemTypes'].tableNames(Æ.NoWeblinks):
                        timeLink = self.workingDir+'/Time/'+timeYear+'/'+timeMonth+'/'+typeDir+'/'+itemName
                        if not self.createLink(filePath, timeLink, itemName):
                            self.wizard.creationSuccess = False
                            return False
            elif isinstance(itemTime, QDateTime) and itemTime.isValid():
                timeYear = itemTime.toString('yyyy')
                timeMonth = itemTime.toString('MMMM')
                if itemType in self.config['itemTypes'].tableNames(Æ.IsWeblinks):
                    timeLink = os.path.join(self.workingDir, "Time", timeYear, timeMonth, typeDir, itemName+"."+self.desktopFileExt())
                    if not self.createDesktopFile(timeLink, itemName, itemSource):
                        self.wizard.creationSuccess = False
                        return False
                elif itemType in self.config['itemTypes'].tableNames(Æ.NoWeblinks):
                    timeLink = self.workingDir+'/Time/'+timeYear+'/'+timeMonth+'/'+typeDir+'/'+itemName
                    if not self.createLink(filePath, timeLink, itemName):
                        self.wizard.creationSuccess = False
                        return False

            sqlRelations = "SELECT t.term_name, t.term_parent, t.term_taxonomy " \
                           "FROM term_relationships AS tr " \
                           "INNER JOIN terms AS t ON (t.term_id = tr.term_id) " \
                           "WHERE (tr.item_id = '{}')".format(itemIden)
            queryRelations.exec_(sqlRelations)

            while queryRelations.next() and not self.progressPage.creationCancelled:
                termName = queryRelations.value(0)
                termParent = queryRelations.value(1)
                termTaxonomy = queryRelations.value(2)
                
                taxonomyDir = self.config['taxonomies'].dirFromTable(termTaxonomy)

                if itemType in self.config['itemTypes'].tableNames(Æ.IsWeblinks):
                    typeDir = typeDir
                    if termParent in ("", None, 0):
                        linkPath = os.path.join(self.workingDir, taxonomyDir, termName, typeDir, itemName+"."+self.desktopFileExt())
                    else:
                        termParentRoot, termParentsJoined = self.returnTermParents(termParent, termTaxonomy)
                        linkPath = os.path.join(self.workingDir, taxonomyDir, termParentRoot, typeDir, termParentsJoined+termName,itemName+'.'+self.desktopFileExt())

                    if not self.createDesktopFile(linkPath, itemName, itemSource):
                        self.wizard.creationSuccess = False
                        return False

                elif itemType in self.config['itemTypes'].tableNames(Æ.NoWeblinks):
                    if termParent in ("", None, 0):
                        linkPath = self.workingDir+'/'+taxonomyDir+'/'+termName+'/'+typeDir+'/'+itemName
                    else:
                        termParentRoot, termParentsJoined = self.returnTermParents(termParent, termTaxonomy)
                        linkPath = self.workingDir+'/'+taxonomyDir+'/'+termParentRoot+'/'+typeDir+'/'\
                            + termParentsJoined+termName+'/'+itemName

                    if not self.createLink(filePath, linkPath, itemName):
                        self.wizard.creationSuccess = False
                        return False

        self.db.close()
        self.wizard.creationSuccess = True
        self.garbageCollection()

        self.wizard.threadRunning = False

    def returnTermParents(self, termParent, termTaxonomy):
        termParentNames = self.recursiveParentSearch(termParent, termTaxonomy)
        if len(termParentNames) > 1:
            termParentsJoined = '/'.join(termParentNames[1:])+'/'
        else:
            termParentsJoined = ''
        termParentRoot = termParentNames[0]
        return termParentRoot, termParentsJoined

    def recursiveParentSearch(self, termParent, termTaxonomy):
        sqlParent = "SELECT t.term_name, t.term_parent FROM terms AS t " \
                    "WHERE (t.term_id = '{}') AND (t.term_taxonomy = '{}')"\
                    .format(termParent, termTaxonomy)
        queryParent = QSqlQuery(self.db.con)
        queryParent.setForwardOnly(True)
        queryParent.exec_(sqlParent)

        if queryParent.first():
            parentName = queryParent.value(0)
            parentParent = queryParent.value(1)

            if parentParent in ("", None, 0, termParent):
                return [parentName]
            else:
                termParentNames = self.recursiveParentSearch(parentParent, termTaxonomy)
                termParentNames.append(parentName)
                return termParentNames
        else:
            errorMesssage = "Parent Searching Error: Term not found."
            self.logger.error(errorMesssage)
            self.streamErrors << errorMesssage << '\n'
            self.errorCount += 1
            self.errorSig.emit(self.errorCount)

    def desktopFileExt(self):
        import platform
        if platform.system() in ("Windows", "Darwin"): return "url"
        return "desktop"

    def _createMacDesktopFile(self, linkPath, itemName, itemSource):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir): os.makedirs(linkDir)
            if os.path.exists(linkPath):
                if self.overwriteLinks:
                    with open(linkPath, 'w') as fp:
                        fp.write('[InternetShortcut]\n')
                        fp.write('URL=%s\n' % itemSource)
                        fp.write('IconIndex=0')
                    os.chmod(linkPath, 0o755)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(itemSource, linkPath)
                    self.streamOverwritten << creationMessage << '\n'
                    self.linksCreatedCount += 1
                    self.linksAlreadyExistingCount += 1
                    self.linksOverwrittenCount += 1
                    self.linkOverwrittenSig.emit(self.linksOverwrittenCount, self.linksAlreadyExistingCount,
                                                 self.linksCreatedCount, itemName)
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(itemSource, linkPath)
                    self.streamExisting << creationMessage << '\n'
                    self.linksAlreadyExistingCount += 1
                    self.linkExistingSig.emit(self.linksAlreadyExistingCount)
                    return True
            else:
                with open(linkPath, 'x') as fp:
                    fp.write('[InternetShortcut]\n')
                    fp.write('URL=%s\n' % itemSource)
                    fp.write('IconIndex=0')
                os.chmod(linkPath, 0o755)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(itemSource, linkPath)
                self.streamCreated << creationMessage << '\n'
                self.linksCreatedCount += 1
                self.linkCreatedSig.emit(self.linksCreatedCount, itemName)
            return True
        except BaseException as e:
            self.logger.error("Error: {}".format(str(e)))
            self.wizard.lastError = str(e)
            self.streamErrors << str(e) << '\n'
            self.errorCount += 1
            return False

    def _createWinDesktopFile(self, linkPath, itemName, itemSource):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir): os.makedirs(linkDir)
            if os.path.exists(linkPath):
                if self.overwriteLinks:
                    with open(linkPath, 'w') as fp:
                        fp.write('[InternetShortcut]\n')
                        fp.write('URL=%s' % itemSource)
                    os.chmod(linkPath, 0o755)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(itemSource, linkPath)
                    self.streamOverwritten << creationMessage << '\n'
                    self.linksCreatedCount += 1
                    self.linksAlreadyExistingCount += 1
                    self.linksOverwrittenCount += 1
                    self.linkOverwrittenSig.emit(self.linksOverwrittenCount, self.linksAlreadyExistingCount,
                                                 self.linksCreatedCount, itemName)
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(itemSource, linkPath)
                    self.streamExisting << creationMessage << '\n'
                    self.linksAlreadyExistingCount += 1
                    self.linkExistingSig.emit(self.linksAlreadyExistingCount)
                    return True
            else:
                with open(linkPath, 'x') as fp:
                    fp.write('[InternetShortcut]\n')
                    fp.write('URL=%s' % itemSource)
                os.chmod(linkPath, 0o755)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(itemSource, linkPath)
                self.streamCreated << creationMessage << '\n'
                self.linksCreatedCount += 1
                self.linkCreatedSig.emit(self.linksCreatedCount, itemName)
            return True
        except BaseException as e:
            self.logger.error("Error: {}".format(str(e)))
            self.wizard.lastError = str(e)
            self.streamErrors << str(e) << '\n'
            self.errorCount += 1
            return False

    def _createLinuxDesktopFile(self, linkPath, itemName, itemSource):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir):
                os.makedirs(linkDir)
            file = QFile(linkPath)
            if os.path.exists(linkPath):
                if self.overwriteLinks is True:
                    if not file.open(QIODevice.WriteOnly | QFile.Truncate):
                        errorMessage = "Desktop File Error: Unable to write desktop file."
                        self.logger.error(errorMessage)
                        self.streamErrors << errorMessage << '\n'
                        self.errorCount += 1
                        self.errorSig.emit(self.errorCount)
                        return False
                    textStream = QTextStream(file)
                    textStream << "[Desktop Entry]" << '\n'
                    textStream << "Encoding=UTF-8" << '\n'
                    textStream << "Name="+itemName << '\n'
                    textStream << "Type=Link" << '\n'
                    textStream << "URL="+itemSource
                    file.close()
                    os.chmod(linkPath, 0o755)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(itemSource, linkPath)
                    self.streamOverwritten << creationMessage << '\n'
                    self.linksCreatedCount += 1
                    self.linksAlreadyExistingCount += 1
                    self.linksOverwrittenCount += 1
                    self.linkOverwrittenSig.emit(self.linksOverwrittenCount, self.linksAlreadyExistingCount,
                                                 self.linksCreatedCount, itemName)
                    return True
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(itemSource, linkPath)
                    self.streamExisting << creationMessage << '\n'
                    self.linksAlreadyExistingCount += 1
                    self.linkExistingSig.emit(self.linksAlreadyExistingCount)
                    return True
            else:
                if not file.open(QIODevice.WriteOnly):
                    errorMessage = "Desktop File Error: Unable to write desktop file."
                    self.logger.error(errorMessage)
                    self.streamErrors << errorMessage << '\n'
                    self.errorCount += 1
                    self.errorSig.emit(self.errorCount)
                    return False
                textStream = QTextStream(file)
                textStream << "[Desktop Entry]" << '\n'
                textStream << "Encoding=UTF-8" << '\n'
                textStream << "Name="+itemName << '\n'
                textStream << "Type=Link" << '\n'
                textStream << "URL="+itemSource
                file.close()
                os.chmod(linkPath, 0o755)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(itemSource, linkPath)
                self.streamCreated << creationMessage << '\n'
                self.linksCreatedCount += 1
                self.linkCreatedSig.emit(self.linksCreatedCount, itemName)
                return True
        except BaseException as e:
            self.logger.error("Error: {}".format(str(e)))
            self.wizard.lastError = str(e)
            self.streamErrors << str(e) << '\n'
            self.errorCount += 1
            return False

    def createDesktopFile(self, linkPath, itemName, itemSource):
        import platform
        if platform.system() == "Windows": return self._createWinDesktopFile(linkPath, itemName, itemSource)
        elif platform.system() == "Darwin": return self._createMacDesktopFile(linkPath, itemName, itemSource)
        return self._createLinuxDesktopFile(linkPath, itemName, itemSource)

    def createLink(self, filePath, linkPath, itemName):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir):
                os.makedirs(linkDir)
            if os.path.lexists(linkPath):
                if self.overwriteLinks is True:
                    os.unlink(linkPath)
                    os.symlink(filePath, linkPath)
                    # os.chmod(linkPath, 0o755)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(filePath, linkPath)
                    self.streamOverwritten << creationMessage << '\n'
                    self.linksCreatedCount += 1
                    self.linksAlreadyExistingCount += 1
                    self.linksOverwrittenCount += 1
                    self.linkOverwrittenSig.emit(self.linksOverwrittenCount, self.linksAlreadyExistingCount,
                                                 self.linksCreatedCount, itemName)
                    return True
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(filePath, linkPath)
                    self.streamExisting << creationMessage << '\n'
                    self.linksAlreadyExistingCount += 1
                    self.linkExistingSig.emit(self.linksAlreadyExistingCount)
                    return True
            else:
                os.symlink(filePath, linkPath)
                # os.chmod(linkPath, 0o755)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(filePath, linkPath)
                self.streamCreated << creationMessage << '\n'
                self.linksCreatedCount += 1
                self.linkCreatedSig.emit(self.linksCreatedCount, itemName)
                return True
        except BaseException as e:
            self.logger.error("Error: {}".format(str(e)))
            self.wizard.lastError = str(e)
            self.streamErrors << str(e) << '\n'
            self.errorCount += 1
            return False

    def garbageCollection(self):
        self.fileErrors.deleteLater()
        self.fileCreated.deleteLater()
        self.fileExisting.deleteLater()
        self.fileOverwritten.deleteLater()