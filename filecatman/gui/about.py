import webbrowser
import logging
from PySide6.QtWidgets import QDialog
from filecatman.core.functions import loadUI
from filecatman.core import const


class AboutDialog(QDialog):
    dialogName = 'About'
    licenceDialog = None

    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(self.dialogName+" Dialog Opened")
        self.mainWindow = parent
        self.app = parent.app
        self.config = parent.config
        self.icons = parent.icons
        self.pixmaps = parent.pixmaps
        self.ui = loadUI("gui/ui/about.ui")

        self.setWindowTitle(self.dialogName)
        self.setLayout(self.ui.layout())
        self.setFixedSize(350, 375)

        self.ui.image.setPixmap(self.pixmaps['Filecatman'])
        self.ui.comment.setText(
            '<html><head/><body><p align="center">{0}</p></body></html>'.format(const.DESCRIPTION))
        self.ui.labelCopyright.setText(
            '<html><head/><body><p align="center">{0}</p></body></html>'.format(const.COPYRIGHT))
        self.ui.homepage.setText(
            '<html><head/><body><p align="center"><a href="'+const.WEBSITE+'">'
            '<span style=" text-decoration: underline; color:#0000ff;">Website</span></a></p></body></html>'
        )
        self.ui.title.setText(
            '<html><head/><body><p align="center">'
            '<span style=" font-size:14pt;">{} </span>'
            '<span style=" font-size:14pt; font-weight:400;">{}</span>'
            '</p></body></html>'.format(const.APPNAME, const.VERSION)
        )

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Close).clicked.connect(self.close)
        self.ui.buttonLicence.clicked.connect(self.openLicence)

    def openLicence(self):
        self.licenceDialog = LicenceDialog(self)
        self.licenceDialog.exec_()
        self.licenceDialog.deleteLater()


class LicenceDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent.mainWindow)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.aboutDialog = parent
        self.mainWindow = parent.mainWindow
        self.app = self.mainWindow.app
        self.setWindowTitle("Licence")

        self.logger.info("Licence Dialog Opened")
        self.ui = loadUI("gui/ui/licence.ui")
        self.setLayout(self.ui.layout())
        self.setMinimumSize(400, 300)

        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Close).clicked.connect(self.close)
        self.ui.textLicence.anchorClicked.connect(self.openLink)

    def openLink(self, url):
        url = url.toString()
        if url == "licence":
            self.close()
            self.aboutDialog.close()
            self.app.openHelpBrowser("gpl.html")
        else:
            webbrowser.open(url)