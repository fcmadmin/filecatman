import logging
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget, QMainWindow, QSizePolicy, QToolButton, QMenu
from filecatman.core.functions import loadUI


class HelpBrowser(QMainWindow):
    dialogName = 'Help Browser'
    currentModel = None
    page = None

    def __init__(self, app, docsDir, page=None):
        super(HelpBrowser, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.config = app.config
        self.icons = app.iconsList.icons
        self.docsDir = docsDir
        if page:
            self.page = page
        else:
            self.page = "index.html"

        self.logger.info(self.dialogName+" Dialog Opened")
        self.ui = loadUI("gui/ui/helpbrowser.ui")
        self.setCentralWidget(self.ui.centralwidget)
        self.setStatusBar(self.ui.statusbar)
        self.addToolBar(self.ui.toolBar)

        self.setWindowSizeAndCentre()
        self.setWindowTitle(self.dialogName)
        self.setWindowIcon(self.icons['Filecatman'])

        self.constructRestOfUi()
        self.setDefaults()
        self.connectSignals()
        self.setIcons()

    def setWindowSizeAndCentre(self):
        from PySide6.QtGui import QGuiApplication
        self.setMinimumSize(700, 500)
        qr = self.frameGeometry()
        cp = QGuiApplication.screenAt(QCursor().pos()).availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def constructRestOfUi(self):
        self.ui.toolbuttonZoom = QToolButton()
        self.ui.toolbuttonZoom.setToolTip("Zoom Actions")
        self.ui.menuZoomActions = QMenu()
        self.ui.menuZoomActions.addActions((self.ui.actionZoomIn, self.ui.actionZoomOut))
        self.ui.toolbuttonZoom.setMenu(self.ui.menuZoomActions)
        self.ui.toolbuttonZoom.setPopupMode(QToolButton.InstantPopup)
        self.ui.toolBar.insertWidget(self.ui.actionClose, self.ui.toolbuttonZoom)

        self.ui.emptyWidget = QWidget()
        self.ui.emptyWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.ui.toolBar.insertWidget(self.ui.actionClose, self.ui.emptyWidget)

    def setIcons(self):
        self.ui.actionClose.setIcon(self.icons['Exit'])
        self.ui.actionForward.setIcon(self.icons['Forward'])
        self.ui.actionBack.setIcon(self.icons['Backward'])
        self.ui.actionContents.setIcon(self.icons['Contents'])
        self.ui.toolbuttonZoom.setIcon(self.icons['Search'])
        self.ui.actionZoomIn.setIcon(self.icons['Search'])
        self.ui.actionZoomOut.setIcon(self.icons['Search'])

    def connectSignals(self):
        self.ui.actionBack.triggered.connect(self.previousPage)
        self.ui.actionForward.triggered.connect(self.nextPage)
        self.ui.textBrowser.backwardAvailable.connect(self.ui.actionBack.setEnabled)
        self.ui.textBrowser.forwardAvailable.connect(self.ui.actionForward.setEnabled)
        self.ui.actionClose.triggered.connect(self.close)
        self.ui.actionContents.triggered.connect(self.contentsPage)
        self.ui.actionZoomIn.triggered.connect(self.zoomIn)
        self.ui.actionZoomOut.triggered.connect(self.zoomOut)

    def setDefaults(self):
        self.ui.textBrowser.setSearchPaths(self.docsDir)
        self.ui.textBrowser.setSource(self.page)

        self.ui.actionBack.setEnabled(False)
        self.ui.actionForward.setEnabled(False)

    def setPage(self, page=None):
        if page:
            self.page = page
            self.ui.textBrowser.setSource(page)

    def nextPage(self):
        self.ui.textBrowser.forward()

    def previousPage(self):
        self.ui.textBrowser.backward()

    def contentsPage(self):
        self.ui.textBrowser.setSource('index.html')

    def zoomIn(self):
        self.ui.textBrowser.zoomIn()

    def zoomOut(self):
        self.ui.textBrowser.zoomOut()

    def closeEvent(self, event):
        super().closeEvent(event)