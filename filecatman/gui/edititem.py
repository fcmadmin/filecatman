from urllib.parse import unquote
from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt, QDate, QTime
from filecatman.core.namespace import Æ
from filecatman.core.functions import warningMsgBox, æscape
from filecatman.gui.newitem import NewItemDialog


class EditItemDialog(NewItemDialog):
    appName = "Edit Item"
    itemData = None
    updateItem = None

    def __init__(self, parent, itemID):
        self.itemID = itemID
        self.db = parent.db
        super(EditItemDialog, self).__init__(parent)
        self.ui.setWindowTitle(self.appName)
        self.displayData()
        self.createListModels()

    def displayData(self):
        self.db.open()
        self.itemData = self.db.selectItem(self.itemID)
        self.db.close()

        itemName = self.itemData.record().indexOf("item_name")
        itemSource = self.itemData.record().indexOf("item_source")
        itemTypeId = self.itemData.record().indexOf("type_id")
        itemDescription = self.itemData.record().indexOf("item_description")
        itemTime = self.itemData.record().indexOf("item_time")

        typeIndex = self.ui.comboType.findData(self.itemData.value(itemTypeId))
        self.ui.comboType.setCurrentIndex(typeIndex)
        self.ui.lineName.setText(self.itemData.value(itemName))
        self.ui.lineSource.setText(unquote(self.itemData.value(itemSource)))
        self.ui.textDescription.setPlainText(unquote(self.itemData.value(itemDescription)))

        if isinstance(self.itemData.value(itemTime), str):
            date, time = str(self.itemData.value(itemTime)).split(" ")
            if date == '0000-00-00':
                self.ui.checkNoDate.setCheckState(Qt.Checked)
            else:
                dateObj = QDate.fromString(date, "yyyy-MM-dd")
                timeObj = QTime.fromString(time, "hh:mm:ss")
                self.ui.dateEdit.setDate(dateObj)
                self.ui.timeEdit.setTime(timeObj)
        else:
            dateTime = self.itemData.value(itemTime)
            timeObj = dateTime.time()
            dateObj = dateTime.date()
            if dateObj.isNull():
                self.ui.checkNoDate.setCheckState(Qt.Checked)
            else:
                self.ui.dateEdit.setDate(dateObj)
                self.ui.timeEdit.setTime(timeObj)

    def createListModels(self):
        for taxonomy, model in self.listModels.items():
            self.db.open()
            relatedTags = self.db.selectRelatedTags(self.itemID, taxonomy)
            while relatedTags.next():
                model.appendRow(QStandardItem(relatedTags.value(0)))
            self.db.close()

    def createTreeModels(self):
        for taxonomy, model in self.treeModels.items():
            self.db.open()
            categories = self.db.selectCategoriesAsTree({"taxonomy": taxonomy})
            i = 0
            lastIndex = None
            while i <= len(categories)-1:
                item = QStandardItem(categories[i]['name'])
                itemID = QStandardItem(str(categories[i]['id']))
                item.setCheckable(True)
                relationExists = self.db.checkRelation(self.itemID, categories[i]['id'])
                if relationExists:
                    item.setCheckState(Qt.Checked)
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
            self.db.close()

    def processData(self):
        data = dict()
        data['id'] = self.itemID
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
            self.db.transaction()
            self.updateItem = self.db.updateItem(data)
            self.deleteRelationsBeforeInsertion()
            self.processRelations(self.itemID)
            self.db.commit()
            self.db.close()
            self.itemInserted.emit()
            self.close()

    def deleteRelationsBeforeInsertion(self):
        deleteRelations = self.db.deleteRelations(self.itemID)
        if deleteRelations:
            self.logger.debug("Relations deleted before insertion.")

    def renameFile(self):
        oldName = self.ui.lineName.text()
        super().renameFile()
        newName = self.ui.lineName.text()

        if newName:
            if not oldName == newName:
                data = dict()
                data['id'] = self.itemID
                data['name'] = newName
                data['type'] = self.ui.comboType.itemData(self.ui.comboType.currentIndex())

                self.db.open()
                self.updateItem = self.db.updateItem(data)
                self.db.close()