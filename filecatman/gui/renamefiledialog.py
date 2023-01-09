import logging
from PySide6.QtWidgets import QDialog
from filecatman.core.functions import loadUI


class RenameFileDialog(QDialog):
    dialogName = 'Type New File Name'
    fileName = str()

    def __init__(self, parent, oldName):
        super(RenameFileDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mainWindow = parent
        self.config = parent.config
        self.icons = parent.icons
        self.fileName = oldName

        self.setWindowTitle(self.dialogName)
        self.ui = loadUI("gui/ui/saveformattingtemplate.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumWidth(400)
        self.ui.lineName.setText(self.fileName)
        self.ui.lineName.setFocus()

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Cancel).clicked.connect(self.close)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).clicked.connect(self.saveName)

        self.logger.info(self.dialogName+" Dialog Opened")

    def saveName(self):
        self.fileName = self.ui.lineName.text()
        self.close()