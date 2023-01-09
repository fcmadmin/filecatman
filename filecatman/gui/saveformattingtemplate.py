import logging
from PySide6.QtWidgets import QDialog
from filecatman.core.functions import loadUI


class SaveFormattingDialog(QDialog):
    dialogName = 'Type New Template Name'
    templateName = str()

    def __init__(self, parent):
        super(SaveFormattingDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.config = parent.config
        self.icons = parent.icons

        self.setWindowTitle(self.dialogName)
        self.ui = loadUI("gui/ui/saveformattingtemplate.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(400)

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).clicked.connect(self.saveTemplate)

        self.logger.info(self.dialogName+" Dialog Opened")

    def saveTemplate(self):
        self.templateName = self.ui.lineName.text()
        self.close()