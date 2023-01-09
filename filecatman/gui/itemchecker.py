import logging
from PySide6.QtCore import Qt, QObject, Signal, QThread, QFile
from PySide6.QtWidgets import QProgressDialog, QMessageBox
from PySide6.QtSql import QSqlQuery
from filecatman.core.namespace import Æ
from filecatman.core.functions import getDataFilePath
from filecatman.core.objects import ÆItemType


class ItemChecker(QObject):
    missingFilesSignal = Signal(list)
    completed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.main = parent
        self.config = parent.config
        self.db = parent.db
        self.icons = parent.icons

        self.progressDialog = None
        self.processingThread = None
        self.processCancelled = None
        self.errorCount = 0
        self.missingFiles = 0

    def run(self):
        self.logger.info("Item Checker Initialized.")
        self.processingThread = ProcessingThread(self)
        self.processingThread.itemCount.connect(self.initializeProgressDialog)
        self.processingThread.itemChecked.connect(self.updateProgress)
        self.processingThread.finished.connect(self.itemCheckingFinished)

        self.processingThread.start()

    def initializeProgressDialog(self, itemCount):
        self.progressDialog = QProgressDialog("Checking each item to confirm it exists.", "Cancel", 0, itemCount)

        self.progressDialog.setWindowTitle("Checking Items")
        self.progressDialog.setParent(self.main, Qt.WindowModal)

        appRect = self.main.geometry()
        appX = appRect.width()
        appY = appRect.height()
        x = self.progressDialog.width()
        y = self.progressDialog.height()
        self.progressDialog.move(appX/2-x/2+appRect.left(), appY/2-y/2+appRect.top())

        self.progressDialog.canceled.connect(self.itemCheckingCancelled)
        self.progressDialog.show()

    def updateProgress(self):
        self.progressDialog.setValue(self.progressDialog.value()+1)

    def itemCheckingCancelled(self):
        self.processingThread.quit()
        self.processCancelled = True
        self.itemCheckingFinished()

    def itemCheckingFinished(self):
        self.progressDialog.hide()
        self.progressDialog.deleteLater()
        if self.processCancelled:
            self.logger.info("Item Check Cancelled.")
            self.completed.emit()
        else:
            self.errorCount = self.processingThread.errorCount
            self.missingFiles = self.processingThread.missingFiles
            self.processingThread.deleteLater()
            self.logger.info("Item Check Finished. Errors: "+str(self.errorCount))
            if self.errorCount >= 1:
                self.missingFilesSignal.emit(self.missingFiles)
            else:
                self.missingFilesSignal.emit(list())
                QMessageBox.information(
                    self.main, 'No Files Missing',
                    'All items exist in their directories.', QMessageBox.Ok
                )
            self.completed.emit()


class ProcessingThread(QThread):

    itemCount = Signal(int)
    itemChecked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.db = parent.db
        self.config = parent.config
        self.dataDir = self.config['options']['defaultDataDir']
        self.parent = parent
        self.main = parent.main
        self.errorCount = 0
        self.missingFiles = list()

    def run(self):
        self.logger.info("Started item checking.")
        self.db.open()
        query = QSqlQuery(self.db.con)
        query.setForwardOnly(True)
        weblinkTypes = self.config['itemTypes'].tableNames(Æ.IsWeblinks)
        sqlCount = "SELECT COUNT(item_id) FROM items WHERE type_id NOT IN ('{}')"\
            .format("', '".join(weblinkTypes))
        self.logger.debug('\n'+sqlCount)
        query.exec_(sqlCount)
        if query.first():
            self.itemCount.emit(query.value(0))
            self.logger.debug("Total Files: "+str(query.value(0)))
        sqlItems = "SELECT item_id, item_name, type_id FROM items WHERE type_id NOT IN ('{}')"\
            .format("', '".join(weblinkTypes))
        self.logger.debug('\n'+sqlItems)
        query.exec_(sqlItems)
        while query.next() and not self.parent.processCancelled:
            itemIden = query.value(0)
            itemName = query.value(1)
            itemTypeValue = query.value(2)
            itemType = self.config['itemTypes'].dirFromTable(itemTypeValue)
            if not itemType:
                itemType = ÆItemType()
                itemType.setPluralName(itemTypeValue.title()+"s")
                itemType.setNounName(itemTypeValue.title())
                itemType.setTableName(itemTypeValue)
                self.config['itemTypes'].append(itemType)
                itemType = self.config['itemTypes'].dirFromTable(itemTypeValue)

            filePath = getDataFilePath(self.dataDir, itemType, itemName)
            if not QFile.exists(filePath):
                self.errorCount += 1
                self.missingFiles.append(str(itemIden))
            self.itemChecked.emit()
        self.db.close()