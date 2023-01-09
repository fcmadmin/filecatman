from urllib.parse import unquote
from filecatman.core.functions import æscape, warningMsgBox
from filecatman.gui.newcategory import NewCategoryDialog


class EditCategoryDialog(NewCategoryDialog):
    appName = "Edit Category"
    categoryData = None
    updateCategory = None

    def __init__(self, parent, taxID):
        super(EditCategoryDialog, self).__init__(parent)
        self.taxID = taxID
        self.ui.setWindowTitle(self.appName)
        self.db = parent.db
        self.displayData()

    def displayData(self):
        self.db.open()
        self.categoryData = self.db.selectCategory(self.taxID)
        self.db.close()

        termName = self.categoryData.record().indexOf("term_name")
        termSlug = self.categoryData.record().indexOf("term_slug")
        termTaxonomy = self.categoryData.record().indexOf("term_taxonomy")
        termParent = self.categoryData.record().indexOf("term_parent")
        termDescription = self.categoryData.record().indexOf("term_description")

        self.ui.lineName.setText(self.categoryData.value(termName))
        self.ui.lineSlug.setText(self.categoryData.value(termSlug))
        taxonomyIndex = self.ui.comboTaxonomy.findData(self.categoryData.value(termTaxonomy))
        self.ui.comboTaxonomy.setCurrentIndex(taxonomyIndex)
        self.ui.textDescription.setPlainText(unquote(self.categoryData.value(termDescription)))

        if self.categoryData.value(termParent) in ('', None, 0):
            self.ui.buttonParent.setText('— No Parent —')
            self.ui.buttonParent.catIden = None
        else:
            self.db.open()
            parentData = self.db.selectCategory(self.categoryData.value(termParent))
            self.db.close()
            termName = parentData.value(parentData.record().indexOf("term_name"))
            self.logger.debug(termName)
            self.ui.buttonParent.setText(termName.replace("&", "&&"))
            self.ui.buttonParent.catIden = self.categoryData.value(termParent)

    def processData(self):
        if self.ui.lineName.text() == "":
            warningMsgBox(self.parent, "Name field is missing.", "Name Missing")
            self.ui.labelName.setText(
                '<p><span style="font-weight:600;"><span style="color:red;">*</span> Name: </span></p>')
            self.ui.labelName.textFormat()
            self.ui.lineName.setFocus()
        else:
            data = dict()
            data['taxid'] = self.taxID
            termID = self.categoryData.record().indexOf("term_id")
            data['termid'] = self.categoryData.value(termID)
            data['name'] = æscape(self.ui.lineName.text())
            data['slug'] = self.ui.lineSlug.text()
            data['taxonomy'] = self.ui.comboTaxonomy.itemData(self.ui.comboTaxonomy.currentIndex())
            data['parent'] = self.ui.buttonParent.catIden
            data['description'] = self.ui.textDescription.toPlainText()

            if not self.taxID == data['parent']:
                self.db.open()
                self.db.transaction()
                self.updateCategory = self.db.updateCategory(data)
                self.db.commit()
                self.db.close()
                self.categoryInserted.emit()
                self.close()
            else:
                warningMsgBox(self.parent, "Category cannot be its own parent and child.", "Invalid Parent")