import os
import logging
import xml.etree.ElementTree as ElementTree
from PySide6.QtCore import Signal, QDir, QElapsedTimer, QThread
from PySide6.QtWidgets import QWizard, QWizardPage, QFileDialog, QPushButton, QLabel, QVBoxLayout
from PySide6.QtSql import QSqlQuery
from filecatman.core.objects import ÆItemType, ÆTaxonomy
from filecatman.core.functions import loadUI, warningMsgBox


class ImportWizard(QWizard):
    pageID = dict(
        SelectXMLFile=0,
        ImportData=1,
        ProgressPage=2,
        Finish=3,
        ImportCancelled=4
    )
    dataImported = Signal()
    itemCount, categoryCount, relationCount = 0, 0, 0
    elapsedTime = 0
    importSuccess = None
    threadRunning = False

    def __init__(self, parent):
        super(ImportWizard, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.app = self.mainWindow.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.pixmaps = self.mainWindow.pixmaps
        self.db = self.mainWindow.db

        self.setWindowTitle("Import Data from XML File")
        self.setPixmap(self.WizardPixmap.LogoPixmap, self.pixmaps['XMLImport'])
        self.setModal(True)
        self.setOption(self.WizardOption.NoBackButtonOnLastPage, True)
        self.setOption(self.WizardOption.HaveHelpButton, True)

        self.setPage(self.pageID['SelectXMLFile'], SelectXMLFilePage(self))
        self.setPage(self.pageID['ImportData'], ImportDataPage(self))
        self.setPage(self.pageID['ProgressPage'], ProgressPage(self))
        self.setPage(self.pageID['Finish'], FinishPage(self))
        self.setPage(self.pageID['ImportCancelled'], ImportCancelledPage(self))

        self.button(self.WizardButton.HelpButton).clicked.connect(self.openHelpBrowser)

    def accept(self):
        self.deleteLater()
        self.close()

    def openHelpBrowser(self):
        if not self.threadRunning:
            self.close()
            self.app.openHelpBrowser("importxml.html")

    def reject(self):
        if not self.threadRunning:
            super().reject()


class SelectXMLFilePage(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.setTitle("Import XML File")
        self.setSubTitle("Select a Filecatman compatible XML file.")
        self.ui = loadUI("gui/ui/importwizardselectfile.ui")
        self.setLayout(self.ui.layout())
        self.setMandatoryFields()

        self.ui.buttonBrowse.clicked.connect(self.openFileDialog)

    def setMandatoryFields(self):
        self.registerField('XMLFile*', self.ui.lineFile)

    def openFileDialog(self):
        fileObj = QFileDialog.getOpenFileName(None, "Open XML File", dir=QDir().homePath())
        filename = fileObj[0]
        try:
            filename = filename.split(os.getcwd()+'/')[1]
        except IndexError:
            pass
        self.logger.debug(filename)
        self.ui.lineFile.setText(filename)


class ImportDataPage(QWizardPage):
    importStatus = 0
    newItems, newCategories = list(), dict()
    file = None

    def __init__(self, parent):
        super().__init__(parent)
        self.wizard = parent

        self.setCommitPage(True)

        self.labelItems = QLabel()
        self.labelItems.setWordWrap(True)
        self.labelCats = QLabel()
        self.labelCats.setWordWrap(True)
        self.labelRelations = QLabel()
        self.labelRelations.setWordWrap(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.labelItems)
        self.layout().addWidget(self.labelCats)
        self.layout().addWidget(self.labelRelations)

    def initializePage(self):
        self.file = str(self.wizard.field('XMLFile'))
        try:
            self.iterparseXML(self.file)
            self.wizard.newItems = self.newItems
            self.wizard.newCategories = self.newCategories
            if self.wizard.newItems:
                self.importStatus = 1
                self.setTitle("Continue Importing Data?")
                self.setSubTitle("Insert the imported data into the database?")
                self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
                self.wizard.itemCount = len(self.wizard.newItems)
                self.wizard.categoryCount = len(self.wizard.newCategories)
                self.labelItems.setText("<b>Items to be imported:</b> {}".format(self.wizard.itemCount))
                self.labelCats.setText("<b>Categories to be imported:</b> {}".format(self.wizard.categoryCount))
                self.wizard.relationCount = 0
                for relations in [i['relations'] for i in self.wizard.newItems]:
                    self.wizard.relationCount += len(relations)
                self.labelRelations.setText("<b>Relations to be imported:</b> {}".format(self.wizard.relationCount))
        except BaseException as e:
            self.importStatus = 0
            self.setTitle("Failed To Import XML File")
            self.setSubTitle("An error occurred while parsing the file.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.labelItems.setText("<b>Error:</b> {}".format(str(e)))
            self.labelCats.setText(None)
            self.labelRelations.setText(None)

    def iterparseXML(self, file):
        self.newItems, self.newCategories = list(), dict()

        context = ElementTree.iterparse(file, events=('start', 'end'))
        context = iter(context)
        dummy, root = context.__next__()

        for event, elem in context:
            if event == 'end' and elem.tag == 'itemType':
                itemType = ÆItemType()
                itemType.setNounName(elem.find('nounName').text)
                itemType.setPluralName(elem.find('pluralName').text)
                itemType.setTableName(elem.find('tableName').text)
                itemType.setDirName(elem.find('dirName').text)
                for ext in elem.iter('extension'):
                    itemType.addExtension(ext.text)
                if len(itemType.extensions) is 0:
                    itemType.isWeblinks = True
                elif itemType.hasExtension("html") and itemType.hasExtension("htm"):
                    itemType.isWebpages = True
                if not self.wizard.config['itemTypes'][itemType.nounName]:
                    self.wizard.config['itemTypes'].append(itemType)
                elem.clear()
            elif event == 'end' and elem.tag == 'taxonomy':
                taxonomy = ÆTaxonomy()
                taxonomy.setNounName(elem.find('nounName').text)
                taxonomy.setPluralName(elem.find('pluralName').text)
                taxonomy.setTableName(elem.find('tableName').text)
                taxonomy.setDirName(elem.find('dirName').text)
                taxonomy.setIsTags(elem.find('isTags').text)
                taxonomy.setHasChildren(bool(elem.find('hasChildren').text))
                if not self.wizard.config['taxonomies'][taxonomy.nounName]:
                    self.wizard.config['taxonomies'].append(taxonomy)
                elem.clear()
            elif event == 'end' and elem.tag == 'item':
                self.newItems.append(dict(
                    name=elem.find('title').text,
                    id=elem.find('item_id').text,
                    type=elem.find('type_id').text,
                    source=elem.find('item_source').text,
                    time=elem.find('item_time').text,
                    description=elem.find('item_description').text,
                    relations=[c.attrib for c in elem.iter('relation')]
                ))
                elem.clear()
            elif event == 'end' and elem.tag == 'category':
                self.newCategories[elem.find('category_tax').text + elem.find('category_slug').text] = dict(
                    id=elem.find('category_id').text,
                    slug=elem.find('category_slug').text,
                    name=elem.find('category_name').text,
                    description=elem.find('category_description').text,
                    taxonomy=elem.find('category_tax').text,
                    parent=elem.find('category_parent').text
                )
                elem.clear()
            root.clear()

    def isComplete(self):
        if self.importStatus is 1:
            return True
        else:
            return False


class ProgressPage(QWizardPage):
    insertionStatus, categoryImportCount, \
        itemImportCount, relationImportCount = 0, 0, 0, 0
    elapsedTime = None
    queryXMLThread = None
    importCancelled = None
    timer = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.wizard = parent
        self.db = parent.db

        self.setTitle("Progress")
        self.setSubTitle("Current progress of the import operation.")
        self.ui = loadUI("gui/ui/importwizardprogress.ui")
        self.setLayout(self.ui.layout())

    def initializePage(self):
        self.resetProgress()

        stopButton = QPushButton("Cancel Import")
        self.wizard.setButton(self.wizard.WizardButton.CustomButton1, stopButton)
        self.wizard.customButtonClicked.connect(self.terminateImport)
        self.wizard.setOption(self.wizard.WizardOption.NoCancelButton, True)
        self.wizard.setOption(self.wizard.WizardOption.HaveCustomButton1, True)

        maximumCount = self.wizard.itemCount+self.wizard.categoryCount+self.wizard.relationCount
        self.ui.progressBar.setRange(0, maximumCount)
        try:
            self.queryXMLThread = QueryXMLThread(self)
            self.queryXMLThread.timerStartedSig.connect(self.timerStart)
            self.queryXMLThread.finished.connect(self.goToFinish)
            self.queryXMLThread.itemInsertedSig.connect(self.updateItemProgress)
            self.queryXMLThread.categoryInsertedSig.connect(self.updateCategoryProgress)
            self.queryXMLThread.relationInsertedSig.connect(self.updateRelationProgress)

            self.queryXMLThread.start()
        except BaseException as e:
            warningMsgBox(self, e, title="Error Importing Data")
            return False

    def resetProgress(self):
        self.insertionStatus, self.categoryImportCount, \
            self.itemImportCount, self.relationImportCount = 0, 0, 0, 0
        self.elapsedTime = None
        self.queryXMLThread = None
        self.importCancelled = None
        self.ui.labelElapsedValue.setText("0 Seconds")
        self.ui.labelItemsValue.setText("0 / "+str(self.wizard.itemCount))
        self.ui.labelCategoriesValue.setText("0 / "+str(self.wizard.categoryCount))
        self.ui.labelRelationsValue.setText("0 / "+str(self.wizard.relationCount))
        self.ui.progressBar.setValue(0)
        self.ui.labelCurrentlyValue.setText(None)

    def timerStart(self):
        if self.timer is None:
            self.timer = QElapsedTimer()
        self.timer.start()

    def timerCheck(self):
        time = '{0:.3f}'.format(round(self.timer.elapsed()/1000, 3))
        self.ui.labelElapsedValue.setText(time+" Seconds")

    def terminateImport(self):
        self.queryXMLThread.quit()
        self.db.rollback()
        self.importCancelled = True
        self.wizard.next()

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
        self.wizard.itemsImported = self.queryXMLThread.itemImportCount
        self.wizard.categoriesImported = self.queryXMLThread.categoryImportCount
        self.wizard.relationsImported = self.queryXMLThread.relationImportCount
        self.wizard.elapsedTime = round(self.timer.elapsed()/1000, 3)
        self.logger.debug("Elapsed time: "+str(self.wizard.elapsedTime)+" Seconds")
        self.wizard.next()
        self.queryXMLThread.deleteLater()

    def isComplete(self):
        return False

    def nextId(self):
        if self.importCancelled is True:
            return self.wizard.pageID['ImportCancelled']
        else:
            return self.wizard.pageID['Finish']


class FinishPage(QWizardPage):
    insertionStatus = 0

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
        if self.wizard.importSuccess is True:
            self.logger.info('XML Import Successful.')
            self.insertionStatus = 1
            self.setTitle("XML Imported")
            self.setSubTitle("Successfully imported data from XML file.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Success'])
            self.labelTime.setText("<b>Time taken to import:</b> {} Seconds".format(self.wizard.elapsedTime))
            self.labelItems.setText("<b>Items imported:</b> {} / {}"
                .format(self.wizard.itemsImported, self.wizard.itemCount))
            self.labelCats.setText("<b>Categories imported:</b> {} / {}"
                .format(self.wizard.categoriesImported, self.wizard.categoryCount))
            self.labelRelations.setText("<b>Relations imported:</b> {} / {}"
                .format(self.wizard.relationsImported, self.wizard.relationCount))
            self.wizard.dataImported.emit()
        else:
            self.logger.error('XML Import Failed.')
            self.logger.error("Error: {}".format(self.db.lastError()))
            self.insertionStatus = 0
            self.setTitle("Import Failed")
            self.setSubTitle("Failed to import XML file.")
            self.setPixmap(self.wizard.WizardPixmap.LogoPixmap, self.wizard.pixmaps['Failure'])
            self.labelTime.setText("<b>Error:</b> {}".format(self.db.lastError()))
            self.labelItems.setText(None)
            self.labelCats.setText(None)
            self.labelRelations.setText(None)

    def isComplete(self):
        return True

    def nextId(self):
        return -1


class ImportCancelledPage(QWizardPage):
    insertionStatus = 0

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
        self.logger.info('XML Import Cancelled.')
        self.insertionStatus = 1
        self.setTitle("XML Import Cancelled")
        self.setSubTitle("The import operation was cancelled.")
        self.label.setText("Nothing was imported. The import operation was cancelled.")

    def nextId(self):
        return -1


class QueryXMLThread(QThread):
    insertionStatus, categoryImportCount, \
        itemImportCount, relationImportCount = 0, 0, 0, 0
    elapsedTime = None

    itemInsertedSig = Signal(int, str)
    categoryInsertedSig = Signal(int, str)
    relationInsertedSig = Signal(int)
    timerStartedSig = Signal()
    catInsertIdens = dict()

    def __init__(self, parent=None):
        super(QueryXMLThread, self).__init__(parent)
        self.logger = parent.logger
        self.db = parent.db
        self.progressPage = parent
        self.wizard = parent.wizard

    def run(self):
        self.wizard.threadRunning = True
        self.timerStartedSig.emit()
        self.insertionStatus, self.categoryImportCount, \
            self.itemImportCount, self.relationImportCount = 0, 0, 0, 0
        existingTaxonomies = self.wizard.config['taxonomies'].tableNames()
        self.db.open()
        self.db.transaction()

        self.catInsertIdens = dict()
        for taxonomy in existingTaxonomies:
            self.catInsertIdens[taxonomy] = dict()

        for key, newCat in self.wizard.newCategories.items():
            if self.progressPage.importCancelled:
                break
            if newCat['parent'] in ("", None):
                dbResponse = self.db.newCategory(data=dict(
                    name=str(newCat['name']), slug=str(newCat['slug']), taxonomy=str(newCat['taxonomy'])),
                    args=dict(replace=True)
                )
                if dbResponse is True:
                    self.catInsertIdens[newCat['taxonomy']][newCat['slug']] = self.db.lastInsertId
                    self.categoryImportCount += 1
                    self.categoryInsertedSig.emit(self.categoryImportCount, newCat['name'])
            else:
                try:
                    currentParent = self.catInsertIdens[newCat['taxonomy']][newCat['parent']]
                except KeyError:
                    currentParent = self.parentIterator(newCat['taxonomy'], newCat['parent'])
                finally:
                    dbResponse = self.db.newCategory(data=dict(
                        name=str(newCat['name']), slug=str(newCat['slug']), taxonomy=str(newCat['taxonomy']),
                        parent=str(currentParent)), args=dict(replace=True)
                    )
                    if dbResponse is True:
                        self.catInsertIdens[newCat['taxonomy']][newCat['slug']] = self.db.lastInsertId
                        self.categoryImportCount += 1
                        self.categoryInsertedSig.emit(self.categoryImportCount, newCat['name'])

        for newItem in self.wizard.newItems:
            if self.progressPage.importCancelled:
                break
            newItemIden = None
            dbResponse = self.db.newItem(data=dict(
                name=newItem['name'], type=newItem['type'], source=newItem['source'],
                datetime=newItem['time'], description=newItem['description'])
            )
            if dbResponse:
                self.itemImportCount += 1
                self.itemInsertedSig.emit(self.itemImportCount, newItem['name'])
                if self.db.lastInsertId:
                    newItemIden = self.db.lastInsertId
                else:
                    newItemIdenQuery = QSqlQuery("SELECT item_id from items WHERE "
                                                 "(item_name = '{}') AND (type_id = '{}')"
                                                 .format(newItem['name'], newItem['type']), self.db.con)
                    if newItemIdenQuery.first():
                        newItemIden = newItemIdenQuery.value(0)

            if newItem['relations']:
                for relation in newItem['relations']:
                    termTaxonomyId = self.catInsertIdens[relation['taxonomy']][relation['slug']]
                    if self.db.newRelation(dict(item=newItemIden, term=termTaxonomyId)):
                        self.relationImportCount += 1
                        self.relationInsertedSig.emit(self.relationImportCount)

        self.db.commit()
        self.db.close()

        self.wizard.importSuccess = True
        self.wizard.threadRunning = False

    def parentIterator(self, parentTax, parentSlug):
        parentCat = self.wizard.newCategories[parentTax+parentSlug]

        if parentCat['parent'] in ("", None):
            dbResponse = self.db.newCategory(data=dict(
                name=str(parentCat['name']), slug=str(parentCat['slug']), taxonomy=str(parentCat['taxonomy']),
                args=dict(replace=True)
            ))
            if dbResponse is True:
                self.catInsertIdens[parentCat['taxonomy']][parentCat['slug']] = self.db.lastInsertId
                return self.db.lastInsertId
        else:
            try:
                parentParent = self.catInsertIdens[parentCat['taxonomy']][parentCat['parent']]
            except KeyError:
                parentParent = self.parentIterator(parentCat['taxonomy'], parentCat['parent'])
            dbResponse = self.db.newCategory(data=dict(
                name=str(parentCat['name']), slug=str(parentCat['slug']), taxonomy=str(parentCat['taxonomy']),
                parent=str(parentParent)), args=dict(replace=True)
            )
            if dbResponse is True:
                self.catInsertIdens[parentCat['taxonomy']][parentCat['slug']] = self.db.lastInsertId
                return self.db.lastInsertId