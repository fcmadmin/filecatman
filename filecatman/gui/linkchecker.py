import logging
import time
from urllib.parse import unquote
from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import QProgressDialog, QMessageBox, QDialog
from PySide6.QtSql import QSqlQuery
from PySide6.QtGui import QStandardItem, QStandardItemModel
import requests
from filecatman.core.functions import loadUI

class LinkChecker(QObject):
    brokenLinksSignal = Signal(list)
    completed = Signal()
    threadRunning = False

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.config = parent.config
        self.db = parent.db
        self.icons = parent.icons

        self.progressDialog = None
        self.processingThread = None
        self.processCancelled = None
        self.errorCount = 0
        self.brokenLinks = 0

    def run(self):
        self.logger.info("Link Checker Initialized.")
        selectTypesDialog = LinkCheckerDialog(self)
        selectTypesDialog.selectedTypesSignal.connect(self.runThread)
        selectTypesDialog.exec_()
        selectTypesDialog.deleteLater()

    def runThread(self, typesList):
        self.processingThread = ProcessingThread(self, typesList)
        self.processingThread.itemCount.connect(self.initializeProgressDialog)
        self.processingThread.itemChecked.connect(self.updateProgress)
        self.processingThread.finished.connect(self.linkCheckingFinished)
        self.processingThread.start()

    def initializeProgressDialog(self, itemCount):
        self.progressDialog = QProgressDialog(
            "Checking each item's source to confirm it is valid.", "Cancel", 0, itemCount)
        self.progressDialog.setWindowTitle("Checking Sources")
        self.progressDialog.setParent(self.mainWindow, Qt.WindowModal)

        appRect = self.mainWindow.geometry()
        appX = appRect.width()
        appY = appRect.height()
        x = self.progressDialog.width()
        y = self.progressDialog.height()
        self.progressDialog.move(appX/2-x/2+appRect.left(), appY/2-y/2+appRect.top())

        self.progressDialog.canceled.connect(self.linkCheckingCancelled)
        self.progressDialog.show()

    def updateProgress(self):
        self.progressDialog.setValue(self.progressDialog.value()+1)

    def linkCheckingCancelled(self):
        self.processCancelled = True

    def linkCheckingFinished(self):
        try:
            self.progressDialog.hide()
            self.progressDialog.deleteLater()
        except AttributeError:
            pass

        self.errorCount = self.processingThread.errorCount
        self.brokenLinks = self.processingThread.brokenLinks
        self.processingThread.deleteLater()
        self.logger.info("Link Check Finished. Errors: "+str(self.errorCount))
        if self.errorCount >= 1:
            self.brokenLinksSignal.emit(self.brokenLinks)
        elif not self.processCancelled:
            self.brokenLinksSignal.emit(list())
            QMessageBox.information(
                self.mainWindow, 'No Links Broken',
                'All item sources were reached without errors.', QMessageBox.Ok
            )
        if self.processCancelled:
            self.logger.info("Link Check Cancelled.")
        self.completed.emit()


class LinkCheckerDialog(QDialog):
    typesModel = QStandardItemModel()
    selectedTypesSignal = Signal(list)
    dialogName = "Link Checker"

    def __init__(self, parent):
        super(LinkCheckerDialog, self).__init__(parent.mainWindow)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent.mainWindow
        self.app = self.mainWindow.app
        self.config = self.mainWindow.config
        self.icons = self.mainWindow.icons
        self.db = parent.db

        self.ui = loadUI("gui/ui/linkchecker.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(400)
        self.setWindowTitle(self.dialogName)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).setText("&Start")

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Ok).clicked.connect(self.accept)
        self.ui.typesTree.doubleClicked.connect(self.checkSelectedItem)

        self.setDefaults()

    def setDefaults(self):
        self.typesModel.clear()
        for itemType in self.config['itemTypes']:
            if itemType.enabled is True:
                item = QStandardItem(self.icons[itemType.iconName], itemType.pluralName)
                item.setCheckable(True)
                item.setCheckState(Qt.Checked)
                item.setData(itemType.tableName, Qt.UserRole)
                self.typesModel.appendRow(item)
        self.ui.typesTree.setModel(self.typesModel)
        self.typesModel.setHorizontalHeaderLabels(("Item types to be checked",))

    def checkSelectedItem(self):
        try:
            index = self.ui.typesTree.selectedIndexes()[0]
            self.ui.typesTree.clearSelection()
            selectedItem = index.model().itemFromIndex(index)
            if selectedItem.checkState() is Qt.Unchecked:
                selectedItem.setCheckState(Qt.Checked)
            else:
                selectedItem.setCheckState(Qt.Unchecked)
        except IndexError:
            pass

    def accept(self):
        checkedTypesList = list()
        i = 0
        while self.typesModel.item(i):
            item = self.typesModel.item(i)
            if item.checkState() == Qt.Checked:
                self.logger.debug(item.data(0)+" is checked.")
                tableName = item.data(role=Qt.UserRole)
                checkedTypesList.append(tableName)
            i += 1

        self.selectedTypesSignal.emit(checkedTypesList)
        super().accept()


class ProcessingThread(QThread):
    itemCount = Signal(int)
    itemChecked = Signal()

    def __init__(self, parent, typesList):
        super().__init__(parent)
        self.typesList = typesList
        self.logger = parent.logger
        self.db = parent.db
        self.config = parent.config
        self.dataDir = self.config['options']['defaultDataDir']
        self.parent = parent
        self.main = parent.mainWindow
        self.errorCount = 0
        self.brokenLinks = list()

    def run(self):
        self.parent.threadRunning = True
        self.logger.info("Started link checking.")
        self.db.open()
        query = QSqlQuery(self.db.con)
        query.setForwardOnly(True)
        sqlCount = "SELECT COUNT(item_id) FROM items WHERE (item_source LIKE '%http%') " \
                   "AND (type_id IN ('{}'))".format("', '".join(self.typesList))
        self.logger.debug('\n'+sqlCount)
        query.exec_(sqlCount)
        if query.first():
            self.itemCount.emit(query.value(0))
            self.logger.debug("Total Links: "+str(query.value(0)))
        sqlItems = "SELECT item_id, item_name, item_source FROM items WHERE (item_source LIKE '%http%') " \
                   "AND (type_id IN ('{}'))".format("', '".join(self.typesList))
        self.logger.debug('\n'+sqlItems)
        query.exec_(sqlItems)
        while query.next() and not self.parent.processCancelled:
            itemIden = query.value(0)
            itemName = query.value(1)
            itemSource = unquote(query.value(2))

            if "youtube" in itemSource:
                youtubeIden = None
                try:
                    if "v=" in itemSource:
                        youtubeIden = itemSource.split("v=")[1][:11]
                    elif "/v/" in itemSource:
                        youtubeIden = itemSource.split("/v/")[1][:11]
                    elif "/embed/" in itemSource:
                        youtubeIden = itemSource.split("/embed/")[1][:11]
                    if youtubeIden:
                        itemSource = "http://gdata.youtube.com/feeds/api/videos/"+youtubeIden
                except IndexError:
                    pass
            try:
                r = requests.get(itemSource, timeout=20)
                self.logger.debug(itemName+": "+str(r.status_code))

                if r.status_code == 403:
                    time.sleep(5)
                    r = requests.get(itemSource, timeout=20)
                    self.logger.warning("(Recheck on 403) "+itemName+": "+str(r.status_code))
                if r.status_code != 200:
                    self.errorCount += 1
                    self.brokenLinks.append(str(itemIden))
            except BaseException as e:
                self.logger.error("Error checking '"+itemName+"': "+str(e))

            self.itemChecked.emit()
        self.db.close()
        self.parent.threadRunning = False