import logging
from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import QProgressDialog, QMessageBox
from PySide6.QtSql import QSqlQuery


class RelationsRecounter(QObject):
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
        self.logger.info("Relations Recounter Initialized.")
        self.processingThread = ProcessingThread(self)
        self.processingThread.categoryCount.connect(self.initializeProgressDialog)
        self.processingThread.categoryChecked.connect(self.updateProgress)
        self.processingThread.finished.connect(self.recountFinished)

        self.processingThread.start()

    def initializeProgressDialog(self, itemCount):
        self.progressDialog = QProgressDialog("Recounting relations for all items.", "Cancel", 0, itemCount)

        self.progressDialog.setWindowTitle("Recounting Relations")
        self.progressDialog.setParent(self.main, Qt.WindowModal)

        appRect = self.main.geometry()
        appX = appRect.width()
        appY = appRect.height()
        x = self.progressDialog.width()
        y = self.progressDialog.height()
        self.progressDialog.move(appX/2-x/2+appRect.left(), appY/2-y/2+appRect.top())

        self.progressDialog.canceled.connect(self.recountCancelled)
        self.progressDialog.show()

    def updateProgress(self):
        self.progressDialog.setValue(self.progressDialog.value()+1)

    def recountCancelled(self):
        self.processingThread.quit()
        self.processCancelled = True
        self.recountFinished()

    def recountFinished(self):
        self.progressDialog.hide()
        self.progressDialog.deleteLater()
        if self.processCancelled:
            self.logger.info("Recount Cancelled.")
            self.completed.emit()
        else:
            self.errorCount = self.processingThread.errorCount
            self.processingThread.deleteLater()
            self.logger.info("Recount Finished. Errors: "+str(self.errorCount))
            if self.errorCount >= 1:
                QMessageBox.warning(
                    self.main, 'Some Counts Were Wrong',
                    '{} categories had a wrong relations count.'.format(str(self.errorCount)), QMessageBox.Ok
                )
            else:
                QMessageBox.information(
                    self.main, 'No Counts Invalid',
                    'All relation counts are correct.', QMessageBox.Ok
                )
            self.completed.emit()


class ProcessingThread(QThread):

    categoryCount = Signal(int)
    categoryChecked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = parent.logger
        self.db = parent.db
        self.config = parent.config
        self.parent = parent
        self.main = parent.main
        self.errorCount = 0

    def run(self):
        self.logger.info("Started relations recounting.")
        self.db.open()
        self.db.transaction()
        query = QSqlQuery(self.db.con)
        query.setForwardOnly(True)
        sqlCount = "SELECT COUNT(term_id) FROM terms"
        self.logger.debug('\n'+sqlCount)
        query.exec_(sqlCount)
        if query.first():
            self.categoryCount.emit(query.value(0))
            self.logger.debug("Total Categories: "+str(query.value(0)))

        queryCategories = self.db.selectCategories(
            args=dict(col="t.term_id, t.term_name, t.term_count"))
        while queryCategories.next() and not self.parent.processCancelled:
            categoryIden = queryCategories.value(0)
            categoryName = queryCategories.value(1)
            categoryCount = queryCategories.value(2)

            newCount = self.db.selectCountRelations(col="term_id", iden=categoryIden)

            if not newCount == categoryCount:
                self.logger.error(
                    "Category '({}) {}' had a count of '{}' items, when it should be '{}'."
                    .format(categoryIden, categoryName, categoryCount, newCount))
                self.errorCount += 1
                sqlUpdate = "UPDATE terms SET term_count={} WHERE term_id = {}"\
                    .format(newCount, categoryIden)
                self.logger.debug('\n'+sqlUpdate)
                QSqlQuery(sqlUpdate, self.db.con)

            self.categoryChecked.emit()
        self.db.commit()
        self.db.close()