from urllib.parse import unquote
import os
import logging
from PySide6.QtCore import Signal, QDate, QDir, QElapsedTimer, QThread, QIODevice, QFile, QDateTime, QXmlStreamWriter
from PySide6.QtWidgets import QWizard, QWizardPage, QFileDialog, QPushButton, QLabel, QVBoxLayout
from PySide6.QtSql import QSqlQuery
from filecatman.core.functions import loadUI, warningMsgBox
from filecatman.core import const


class ExportWizard(QWizard):
    pageID = dict(
        ConfirmExport=0,
        Progress=1,
        Finish=3,
        ExportCancelled=4
    )
    dataExported = Signal()
    itemCount, categoryCount, relationCount = 0, 0, 0
    elapsedTime = 0
    exportSuccess = None
    lastError = None
    threadRunning = False

    def __init__(self, parent):
        super(ExportWizard, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.app = self.mainWindow.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.pixmaps = self.mainWindow.pixmaps
        self.db = self.mainWindow.db

        self.setWindowTitle("Export Data to XML File")
        self.setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['XMLExport'])
        self.setModal(True)
        self.setOption(QWizard.IndependentPages, False)
        self.setOption(self.WizardOption.NoBackButtonOnLastPage, True)
        self.setOption(self.WizardOption.HaveHelpButton, True)

        self.setPage(self.pageID['ConfirmExport'], ConfirmExportPage(self))
        self.setPage(self.pageID['Progress'], ProgressPage(self))
        self.setPage(self.pageID['Finish'], FinishPage(self))
        self.setPage(self.pageID['ExportCancelled'], ExportCancelledPage(self))

        self.button(self.WizardButton.HelpButton).clicked.connect(self.openHelpBrowser)

    def accept(self):
        self.close()

    def openHelpBrowser(self):
        if not self.threadRunning:
            self.close()
            self.app.openHelpBrowser("exportxml.html")

    def reject(self):
        if not self.threadRunning:
            super().reject()


class ConfirmExportPage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.setTitle("Export XML File")
        self.setSubTitle("Do you want to export an XML file?")
        self.setCommitPage(True)
        self.ui = loadUI("gui/ui/exportwizardconfirmexport.ui")
        self.setLayout(self.ui.layout())
        self.setMandatoryFields()

        self.ui.buttonBrowse.clicked.connect(self.saveFileDialog)

        self.db.open()
        self.wizard.itemCount = self.db.selectCount("items")
        self.wizard.categoryCount = self.db.selectCount("terms")
        self.wizard.relationCount = self.db.selectCount("term_relationships")
        self.db.close()

        self.ui.labelItemsValue.setText(str(self.wizard.itemCount))
        self.ui.labelCategoriesValue.setText(str(self.wizard.categoryCount))
        self.ui.labelRelationsValue.setText(str(self.wizard.relationCount))

    def setMandatoryFields(self):
        self.registerField('xmlFile*', self.ui.lineFile)

    def saveFileDialog(self):
        saveFileDialog = QFileDialog(self)
        saveFileDialog.setFileMode(saveFileDialog.FileMode.AnyFile)
        saveFileDialog.setNameFilter("Filecatman XML (*.xml)")
        saveFileDialog.setDefaultSuffix('xml')
        saveFileDialog.setDirectory(QDir().homePath())
        saveFileDialog.selectFile(os.path.basename(self.db.config['db'])+"."+QDate.currentDate().toString("yyyy-MM-dd")+".xml")
        saveFileDialog.setWindowTitle("Save XML File")
        saveFileDialog.setViewMode(saveFileDialog.ViewMode.List)
        saveFileDialog.setAcceptMode(saveFileDialog.AcceptMode.AcceptSave)
        if saveFileDialog.exec_():
            fileObj = saveFileDialog.selectedFiles()
            filename = fileObj[0]
            try:
                filename = filename.split(os.getcwd()+'/')[1]
            except IndexError:
                pass
            self.logger.debug(filename)
            self.ui.lineFile.setText(filename)


class ProgressPage(QWizardPage):
    exportXMLThread = None
    categoryExportCount, itemExportCount, relationExportCount = 0, 0, 0
    elapsedTime = None
    exportCancelled = None
    timer = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.setTitle("Export Progress")
        self.setSubTitle("Current progress of export operation.")
        self.ui = loadUI("gui/ui/exportwizardprogress.ui")
        self.setLayout(self.ui.layout())

    def initializePage(self):
        self.exportCancelled = None
        stopButton = QPushButton("Cancel Export")
        self.wizard.setButton(self.wizard.WizardButton.CustomButton1, stopButton)
        self.wizard.customButtonClicked.connect(self.terminateExport)
        self.wizard.setOption(self.wizard.WizardOption.NoCancelButton, True)
        self.wizard.setOption(self.wizard.WizardOption.HaveCustomButton1, True)

        maximumCount = self.wizard.itemCount+self.wizard.categoryCount+self.wizard.relationCount
        self.ui.progressBar.setRange(0, maximumCount)

        try:
            self.exportXMLThread = ExportXMLThread(self)
            self.exportXMLThread.timerStartedSig.connect(self.timerStart)
            self.exportXMLThread.finished.connect(self.goToFinish)
            self.exportXMLThread.itemExportedSig.connect(self.updateItemProgress)
            self.exportXMLThread.categoryExportedSig.connect(self.updateCategoryProgress)
            self.exportXMLThread.relationExportedSig.connect(self.updateRelationProgress)
            self.exportXMLThread.start()
        except BaseException as e:
            warningMsgBox(self.wizard, e, title="Error Exporting Data")

    def timerStart(self):
        self.timer = QElapsedTimer()
        self.timer.start()

    def timerCheck(self):
        time = '{0:.3f}'.format(round(self.timer.elapsed()/1000, 3))
        self.ui.labelElapsedValue.setText(time+" Seconds")

    def terminateExport(self):
        self.exportCancelled = True
        self.exportXMLThread.exit()
        self.exportXMLThread.wait()
        self.wizard.next()
        os.remove(self.wizard.field('xmlFile'))

    def updateItemProgress(self, count, rowName):
        self.ui.labelItemsValue.setText(str(count)+" / "+str(self.wizard.itemCount))
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        self.ui.labelCurrentlyValue.setText(rowName)
        self.timerCheck()

    def updateCategoryProgress(self, count, rowName):
        self.ui.labelCategoriesValue.setText(str(count)+" / "+str(self.wizard.categoryCount))
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        self.ui.labelCurrentlyValue.setText(rowName)
        self.timerCheck()

    def updateRelationProgress(self, count):
        self.ui.labelRelationsValue.setText(str(count)+" / "+str(self.wizard.relationCount))
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)

    def goToFinish(self):
        self.wizard.itemsExported = self.exportXMLThread.itemExportCount
        self.wizard.categoriesExported = self.exportXMLThread.categoryExportCount
        self.wizard.relationsExported = self.exportXMLThread.relationExportCount
        self.wizard.elapsedTime = round(self.timer.elapsed()/1000, 3)
        self.logger.debug("Elapsed time: "+str(self.wizard.elapsedTime)+" Seconds")
        self.wizard.next()

    def isComplete(self):
        return False

    def nextId(self):
        if self.exportCancelled is True:
            return self.wizard.pageID['ExportCancelled']
        else:
            return self.wizard.pageID['Finish']


class FinishPage(QWizardPage):
    exportStatus = 0

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db
        self.labelTime = QLabel()
        self.labelTime.setWordWrap(True)
        self.labelItems = QLabel()
        self.labelItems.setWordWrap(True)
        self.labelCats = QLabel()
        self.labelCats.setWordWrap(True)
        self.labelRelations = QLabel()
        self.labelRelations.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.labelTime)
        self.layout().addWidget(self.labelItems)
        self.layout().addWidget(self.labelCats)
        self.layout().addWidget(self.labelRelations)

    def initializePage(self):
        self.setFinalPage(True)
        self.wizard.setOption(self.wizard.WizardOption.HaveCustomButton1, False)
        if self.wizard.exportSuccess is True:
            self.logger.info('XML Export Successful.')
            self.exportStatus = 1
            self.setTitle("XML Exported")
            self.setSubTitle("Successfully exported data to XML file.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.labelTime.setText("<b>Time taken to export:</b> {} Seconds".format(self.wizard.elapsedTime))
            self.labelItems.setText("<b>Items exported:</b> {} / {}"
                .format(self.wizard.itemsExported, self.wizard.itemCount))
            self.labelCats.setText("<b>Categories exported:</b> {} / {}"
                .format(self.wizard.categoriesExported, self.wizard.categoryCount))
            self.labelRelations.setText("<b>Relations exported:</b> {} / {}"
                .format(self.wizard.relationsExported, self.wizard.relationCount))
            self.wizard.dataExported.emit()
        else:
            self.logger.error('XML Export Failed.')
            self.exportStatus = 0
            self.setTitle("Export Failed")
            self.setSubTitle("Failed to export XML file.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.labelTime.setText("<b>Error:</b> {}".format(self.wizard.lastError))
            self.labelItems.setText(None)
            self.labelCats.setText(None)
            self.labelRelations.setText(None)

    def isComplete(self):
        return True

    def nextId(self):
        return -1


class ExportCancelledPage(QWizardPage):
    exportStatus = 0

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
        self.logger.info('XML Export Cancelled.')
        self.exportStatus = 1
        self.setTitle("XML Export Cancelled")
        self.setSubTitle("The export operation was cancelled.")
        self.label.setText("Nothing was exported. The export operation was cancelled.")

    def nextId(self):
        return -1


class ExportXMLThread(QThread):
    categoryExportCount, itemExportCount, relationExportCount = 0, 0, 0
    elapsedTime = None

    itemExportedSig = Signal(int, str)
    categoryExportedSig = Signal(int, str)
    relationExportedSig = Signal(int)
    timerStartedSig = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent.wizard
        self.progressPage = parent
        self.db = parent.db

    def run(self):
        self.wizard.threadRunning = True
        self.timerStartedSig.emit()
        self.categoryExportCount, self.itemExportCount, self.relationExportCount = 0, 0, 0

        file = QFile(self.wizard.field('xmlFile'))
        if not file.open(QIODevice.WriteOnly):
            self.logger.error("Failed to write to '{}'".format(self.wizard.field('xmlFile')))
            self.logger.error("Error: '{}'".format(file.errorString()))
            self.wizard.exportSuccess = False
            self.wizard.lastError = file.errorString()
            return False

        self.db.open()

        stream = QXmlStreamWriter(file)
        stream.setAutoFormatting(True)
        stream.setAutoFormattingIndent(4)
        stream.writeStartDocument()
        stream.writeComment(" {0} {1} ".format(const.APPNAME, const.VERSION))
        stream.writeComment(" Extensible Markup Language file. ")
        creationDate = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm")
        stream.writeComment(" Created: '{}' ".format(creationDate))

        stream.writeStartElement("channel")

        for itemType in self.wizard.config['itemTypes']:
            stream.writeStartElement("itemType")
            stream.writeStartElement("nounName")
            stream.writeCDATA(itemType.nounName)
            stream.writeEndElement()
            stream.writeStartElement("pluralName")
            stream.writeCDATA(itemType.pluralName)
            stream.writeEndElement()
            stream.writeStartElement("tableName")
            stream.writeCDATA(itemType.tableName)
            stream.writeEndElement()
            stream.writeStartElement("dirName")
            stream.writeCDATA(itemType.dirName)
            stream.writeEndElement()
            for extension in itemType.extensions:
                stream.writeTextElement("extension", extension)
            stream.writeEndElement()

        for taxonomy in self.wizard.config['taxonomies']:
            stream.writeStartElement("taxonomy")
            stream.writeStartElement("nounName")
            stream.writeCDATA(taxonomy.nounName)
            stream.writeEndElement()
            stream.writeStartElement("pluralName")
            stream.writeCDATA(taxonomy.pluralName)
            stream.writeEndElement()
            stream.writeStartElement("tableName")
            stream.writeCDATA(taxonomy.tableName)
            stream.writeEndElement()
            stream.writeStartElement("dirName")
            stream.writeCDATA(taxonomy.dirName)
            stream.writeEndElement()
            stream.writeTextElement("hasChildren", str(taxonomy.hasChildren))
            stream.writeTextElement("isTags", str(taxonomy.isTags))
            stream.writeEndElement()

        sqlCats = "SELECT t.term_id, t.term_name, " \
                  "t.term_slug, t.term_taxonomy, t.term_description, t.term_parent " \
                  "FROM terms AS t"
        queryCats = QSqlQuery(self.db.con)
        queryCats.setForwardOnly(True)
        if not queryCats.exec_(sqlCats):
            self.logger.error(queryCats.lastError().text())
        while queryCats.next() and not self.progressPage.exportCancelled:
            idenIndex = queryCats.record().indexOf("term_id")
            nameIndex = queryCats.record().indexOf("term_name")
            slugIndex = queryCats.record().indexOf("term_slug")
            taxonomyIndex = queryCats.record().indexOf("term_taxonomy")
            descriptionIndex = queryCats.record().indexOf("term_description")
            parentIndex = queryCats.record().indexOf("term_parent")

            categoryParentSlug = ''
            if not queryCats.value(parentIndex) in (0, None, '', '0'):
                queryParentSlug = QSqlQuery(
                    "SELECT t.term_slug FROM terms AS t "
                    "WHERE term_id = '{}'".format(queryCats.value(parentIndex)),
                    self.db.con
                )
                if queryParentSlug.first():
                    categoryParentSlug = queryParentSlug.value(0)

            stream.writeStartElement("category")

            stream.writeTextElement("category_id", str(queryCats.value(idenIndex)))
            stream.writeTextElement("category_slug", queryCats.value(slugIndex))
            stream.writeStartElement("category_name")
            stream.writeCDATA(queryCats.value(nameIndex))
            stream.writeEndElement()
            stream.writeStartElement("category_description")
            stream.writeCDATA(unquote(queryCats.value(descriptionIndex)))
            stream.writeEndElement()
            stream.writeTextElement("category_tax", queryCats.value(taxonomyIndex))
            stream.writeTextElement("category_parent", categoryParentSlug)

            stream.writeEndElement()

            self.categoryExportCount += 1
            self.categoryExportedSig.emit(self.categoryExportCount, queryCats.value(nameIndex))

        sqlItems = "SELECT * FROM items;"

        queryItems = QSqlQuery(self.db.con)
        queryItems.setForwardOnly(True)
        queryItems.exec_(sqlItems)

        while queryItems.next() and not self.progressPage.exportCancelled:
            idenIndex = queryItems.record().indexOf("item_id")
            nameIndex = queryItems.record().indexOf("item_name")
            typeIndex = queryItems.record().indexOf("type_id")
            sourceIndex = queryItems.record().indexOf("item_source")
            timeIndex = queryItems.record().indexOf("item_time")
            descriptionIndex = queryItems.record().indexOf("item_description")

            if isinstance(queryItems.value(timeIndex), str):
                itemTime = queryItems.value(timeIndex)
            elif isinstance(queryItems.value(timeIndex), QDateTime) and queryItems.value(timeIndex).isValid():
                itemTime = queryItems.value(timeIndex).toString('yyyy-MM-dd hh:mm:ss')
            else:
                itemTime = "0000-00-00 00:00:00"

            stream.writeStartElement("item")

            stream.writeTextElement("title", queryItems.value(nameIndex))
            stream.writeTextElement("item_id", str(queryItems.value(idenIndex)))
            stream.writeTextElement("type_id", queryItems.value(typeIndex))
            stream.writeTextElement("item_source", unquote(queryItems.value(sourceIndex)))
            stream.writeTextElement("item_time", itemTime)
            stream.writeTextElement("item_description", unquote(queryItems.value(descriptionIndex)))

            self.itemExportCount += 1
            self.itemExportedSig.emit(self.itemExportCount, queryItems.value(nameIndex))

            sqlRelations = "SELECT t.term_taxonomy, t.term_slug, t.term_name " \
                           "FROM term_relationships AS tr " \
                           "INNER JOIN terms AS t ON (t.term_id = tr.term_id) " \
                           "WHERE (tr.item_id = '{}') ORDER BY t.term_name ASC;"\
                           .format(str(queryItems.value(idenIndex)))

            queryRelations = QSqlQuery(self.db.con)
            queryRelations.setForwardOnly(True)
            queryRelations.exec_(sqlRelations)
            while queryRelations.next() and not self.progressPage.exportCancelled:
                taxIndex = queryRelations.record().indexOf("term_taxonomy")
                slugIndex = queryRelations.record().indexOf("term_slug")
                nameIndex = queryRelations.record().indexOf("term_name")
                stream.writeStartElement("relation")
                stream.writeAttribute('taxonomy', queryRelations.value(taxIndex))
                stream.writeAttribute('slug', queryRelations.value(slugIndex))
                stream.writeCDATA(queryRelations.value(nameIndex))
                stream.writeEndElement()
                self.relationExportCount += 1
                self.relationExportedSig.emit(self.relationExportCount)

            stream.writeEndElement()

        stream.writeEndElement()
        stream.writeEndDocument()
        file.close()
        self.db.close()

        self.wizard.exportSuccess = True
        self.wizard.threadRunning = False