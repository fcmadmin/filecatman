# Filecatman is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Filecatman is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Filecatman. If not, see http://www.gnu.org/licenses/.

import sys
import os, platform
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtCore import Qt
from filecatman.core.database import ÆDatabase
from filecatman.core.functions import warningMsgBox, getÆDirPath
from filecatman.gui import MainWindow, StartupWizard, HelpBrowser
import filecatman.config as config
from filecatman.icons import getDefaultIconsList
from filecatman.log import logger


class Filecatman(QApplication):
    main, wizard, config, database, helpBrowser = None, None, None, None, None
    iconsList, systemName, logger, portableMode = None, None, None, None

    def __init__(self, args):
        super().__init__(args)
        self.setAttribute(Qt.AA_DontShowIconsInMenus, False)  # Fix for missing context menu icons in XFCE
        self.defaultStyle = self.style().objectName()
        self.defaultPalette = self.palette()

    def exec_(self, databasePath=None):
        self.logger = logger
        self.getSystemSpecifics()
        self.logger.info("This is Filecatman "+self.applicationVersion()+" running on "+self.systemName)
        if self.portableMode:
            self.logger.info(
                "Running in portable mode. Configuration files are saved in the application's directory.")
        self.config = config.Config()
        self.iconsList = getDefaultIconsList()
        self.changeStyle()
        self.changePalette()
        self.setIconTheme()

        if databasePath:
            self.config['db'] = dict()
            self.config.settings.remove('db')
            self.config['db']['db'] = os.path.abspath(databasePath)
            self.config['db']['type'] = "sqlite"
            self.config['autoloadDatabase'] = False
            self.confirmConnection()
        elif self.config['autoloadDatabase'] is True:
            self.confirmConnection()
        else:
            self.openWizard()
        super().exec_()

    def getSystemSpecifics(self):
        if sys.platform.startswith('linux'):
            self.systemName = "Linux"
        elif sys.platform.startswith('win'):
            self.systemName = "Windows"
        elif sys.platform.startswith('darwin'):
            self.systemName = "Mac"
        else:
            self.systemName = sys.platform

    def confirmConnection(self):
        try:
            db = ÆDatabase(self.config['db'])
            db.open()
            db.close()
            logger.debug('Database Connection Successful.')
            self.database = db
            self.openMainWindow()

        except BaseException as e:
            warningMsgBox(None, str(e), "Database Connection Failed")
            logger.error('Database connection failed.')
            logger.error("Error: {}".format(e))
            self.config['autoloadDatabase'] = False
            self.config['db'].clear()
            self.config.settings.remove('db')
            self.config.writeConfig()
            self.openWizard()

    def openMainWindow(self):
        # try:
        if not self.main:
            self.main = MainWindow(self)
        self.main.initializeWindow()
        # except BaseException as e:
        #     warningMsgBox(None, str(e), "(openMainWindow) An Error Occurred")

    def openWizard(self, pageIden=None):
        # try:
        if not self.wizard:
            self.wizard = StartupWizard(self)
        if pageIden:
            self.wizard.restart()
            welcomePage = self.wizard.page(0)
            welcomePage.nextPageIden = self.wizard.pageID[pageIden]
            self.wizard.next()
        self.wizard.initializeWizard()
        # except BaseException as e:
        #     warningMsgBox(None, str(e), "(OpenWizard) An Error Occurred")

    def openHelpBrowser(self, page=None):
        try:
            if platform.system() in ("Windows", "Darwin"):
                docPaths = (os.path.join(getÆDirPath(),'docs','en'),)
            else:
                if self.portableMode:
                    docPaths = ('docs/en/',)
                else:
                    docPaths = (
                        "/usr/share/doc/filecatman/en/",
                        "/usr/local/share/doc/filecatman/en/",
                        os.path.join(getÆDirPath(), 'docs', 'en')
                    )
            self.logger.debug("Help Contents Paths: "+str(docPaths))

            if not self.helpBrowser:
                self.helpBrowser = HelpBrowser(self, docPaths, page)
            else:
                self.helpBrowser.setPage(page)
            if not self.helpBrowser.isVisible():
                self.helpBrowser.show()

        except BaseException as e:
            warningMsgBox(None, str(e), "An Error Occurred")

    def changeStyle(self):
        if self.config['style'] == "System Default":
            self.setStyle(QStyleFactory.create(self.defaultStyle))
        else:
            self.setStyle(QStyleFactory.create(self.config['style']))

    def changePalette(self):
        if self.config['standardPalette']:
            self.setPalette(self.style().standardPalette())
        else:
            self.setPalette(self.defaultPalette)

    def setIconTheme(self):
        if not self.config.get('iconTheme'):
            self.config['iconTheme'] = 'System Default'
        self.iconsList.setSystemIconTheme(self.config['customSystemTheme'])
        self.iconsList.setIconTheme(self.config['iconTheme'])

        if self.main:
            self.main.setIconTheme()

    def setIcons(self):
        if self.main:
            self.main.setIcons()
        if self.wizard:
            self.wizard.setIcons()
        if self.helpBrowser:
            self.helpBrowser.setIcons()

    def setPortableMode(self, mode):
        self.portableMode = mode
