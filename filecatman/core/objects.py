import os
import time
import shutil
import logging
import copy
import operator
from urllib.parse import quote, unquote

from PySide6.QtCore import Signal, Qt, QAbstractTableModel, QFile, QIODevice, QDateTime, QSize, QAbstractItemModel, \
    QModelIndex, QItemSelection, QStringListModel, QSortFilterProxyModel, QItemSelectionModel
from PySide6.QtWidgets import QStyle, QToolButton, QLineEdit, QMessageBox, QVBoxLayout, \
    QSizePolicy, QAbstractItemView, QCheckBox, QTreeView, QListView, QCompleter
from PySide6.QtSql import QSqlQuery
from PySide6.QtGui import QIcon, QPixmap

from filecatman.core.printcolours import bcolours
from filecatman.core.namespace import Æ
from filecatman.core.functions import formatBytes, getDataFilePath, warningMsgBox, æscape


class ÆButtonLineEdit(QLineEdit):
    buttonClicked = Signal()
    clearEnabled = True

    def __init__(self, icons, parent=None, clearEnabled=True):
        super(ÆButtonLineEdit, self).__init__(parent)
        self.clearEnabled = clearEnabled
        self.icons = icons
        self.button = QToolButton(self)
        if self.icons.get('Search'):
            self.button.setIcon(self.icons['Search'])
        self.button.setStyleSheet('border: 0px; padding: 0px;')
        if self.clearEnabled:
            self.button.setCursor(Qt.ArrowCursor)
        else:
            self.button.setCursor(Qt.PointingHandCursor)
        self.button.setFocusPolicy(Qt.NoFocus)
        self.button.clicked.connect(self.buttonClicked.emit)
        self.button.setMaximumHeight(20)
        self.button.setToolTip("Search")

        self.editingFinished.connect(self.decideButton)
        self.textEdited.connect(self.decideButton)

        frameWidth = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        buttonSize = self.button.sizeHint()
        self.setStyleSheet('QLineEdit {padding-right: %dpx; }' % (buttonSize.width() + frameWidth + 1))
        self.setMinimumSize(max(self.minimumSizeHint().width(), buttonSize.width() + frameWidth*2 + 2),
                            max(self.minimumSizeHint().height(), buttonSize.height() + frameWidth*2 + 2))

    def resizeEvent(self, event):
        buttonSize = self.button.sizeHint()
        frameWidth = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.button.move(self.rect().right() - frameWidth - buttonSize.width(),
                         (self.rect().bottom() - 20 + 1)/2)
        super(ÆButtonLineEdit, self).resizeEvent(event)

    def decideButton(self):
        if self.text() == '':
            self.button.setIcon(self.icons['Search'])
            if self.clearEnabled:
                self.button.setCursor(Qt.ArrowCursor)
            else:
                self.button.setCursor(Qt.PointingHandCursor)
            self.button.setToolTip("Search")
        else:
            if self.clearEnabled:
                self.button.setIcon(self.icons['Clear'])
                self.button.setCursor(Qt.PointingHandCursor)
                self.button.setToolTip("Clear Textfield")

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        actionUndo = menu.actions()[0]
        actionUndo.setIcon(self.icons['Undo'])
        actionRedo = menu.actions()[1]
        actionRedo.setIcon(self.icons['Redo'])
        actionCut = menu.actions()[3]
        actionCut.setIcon(self.icons['Cut'])
        actionCopy = menu.actions()[4]
        actionCopy.setIcon(self.icons['Copy'])
        actionPaste = menu.actions()[5]
        actionPaste.setIcon(self.icons['Paste'])
        actionDelete = menu.actions()[6]
        actionDelete.setIcon(self.icons['Remove'])
        actionSelectAll = menu.actions()[8]
        actionSelectAll.setIcon(self.icons['SelectAll'])

        menu.exec_(event.globalPos())
        menu.deleteLater()


class ÆColoredFormatter(logging.Formatter):
    LEVELCOLOR = {
        'INFO': bcolours.BOLD,
        'DEBUG': bcolours.BLUE,
        'WARNING': bcolours.WARNING,
        'ERROR': bcolours.FAIL,
        'CRITICAL': bcolours.CRITICAL,
        'ENDC': bcolours.ENDC
    }

    def __init__(self, msg):
        logging.Formatter.__init__(self, msg)

    def format(self, record):
        record = copy.copy(record)
        levelname = record.levelname
        if levelname in self.LEVELCOLOR:
            record.levelname = "["+self.LEVELCOLOR[levelname]+levelname+self.LEVELCOLOR['ENDC']+"]"
            record.name = bcolours.HEADER+record.name+bcolours.ENDC
        return logging.Formatter.format(self, record)


class ÆIconList:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.__fallbackNames = dict()
        self.__pixmapNames = list()
        self.__treeIconNames = list()

        self.icons = dict()
        self.pixmaps = dict()
        self.treeIcons = dict()

        self.iconThemes = dict()
        self.iconTheme = None

    def icon(self, iconName):
        if iconName in self.icons.keys():
            return self.icons[iconName]
        return False

    def getPixmap(self, pixmapName):
        if pixmapName in self.__pixmapNames:
            return self.pixmaps[pixmapName]
        elif pixmapName in self.icons.keys():
            self.__pixmapNames.append(pixmapName)
            self.pixmaps[pixmapName] = QPixmap(self.icons[pixmapName].pixmap(48))
            return self.pixmaps[pixmapName]

    def getTreeIcon(self, iconName):
        if self.iconTheme.isSystemTheme:
            if iconName in self.__treeIconNames:
                return self.treeIcons[iconName]
            else:
                self.__treeIconNames.append(iconName)
                self.treeIcons[iconName] = QIcon(self.icons[iconName])
                return self.treeIcons[iconName]
        else:
            return self.icons[iconName]

    def setPixmapNames(self, pixmapNames):
        self.__pixmapNames = pixmapNames

    def setFallbackNames(self, fallbackNames):
        self.__fallbackNames = fallbackNames

    def setTreeIconNames(self, treeIconNames):
        self.__treeIconNames = treeIconNames

    def appendIconTheme(self, iconTheme):
        self.iconThemes[iconTheme.themeName] = iconTheme

    def setIconTheme(self, themeName):
        if themeName in self.iconThemes.keys():
            self.logger.debug("Icon theme set.")
            self.iconTheme = self.iconThemes[themeName]
            self.setIcons()
            self.setTreeIcons()
            self.setPixmaps()
        else:
            self.logger.warning("Invalid icon theme '"+themeName+"' in configuration file. "
                                "Reverting to system default.")
            self.iconTheme = self.iconThemes["System Default"]
            self.setIcons()
            self.setTreeIcons()
            self.setPixmaps()

    def setSystemIconTheme(self, systemThemeName):
        self.iconThemes["System Default"].systemThemeName = systemThemeName

    def setIcons(self):
        iconTheme = self.iconTheme
        self.logger.debug(QIcon.themeSearchPaths())
        self.logger.debug("Current Theme Name:"+QIcon.themeName())
        if iconTheme.isSystemTheme:
            if not iconTheme.systemThemeName == "":
                QIcon.setThemeName(iconTheme.systemThemeName)
            self.logger.debug("New Theme Name:" + QIcon.themeName())
            for iconName, iconPath in iconTheme.iconPaths.items():
                self.icons[iconName] = QIcon.fromTheme(iconPath).pixmap(48)
                if self.icons[iconName].isNull():
                    self.logger.debug("Icon Is Null, looking for alternative.")
                    if iconName in iconTheme.iconAlternativeNames():
                        for icon in iconTheme.iconAlternatives[iconName]:
                            self.icons[iconName] = QIcon.fromTheme(icon).pixmap(48)
                            if not self.icons[iconName].isNull():
                                iconTheme.iconPaths[iconName] = icon
                                break
                        if self.icons[iconName].isNull() and self.__fallbackNames.get(iconName):
                            self.icons[iconName] = QIcon(self.__fallbackNames[iconName])
                    elif self.__fallbackNames.get(iconName):
                        self.icons[iconName] = QIcon(self.__fallbackNames[iconName])
                    else:
                        self.icons[iconName] = QIcon()
                        self.logger.debug("Icon for '{}' is missing.".format(iconName))
        else:
            for iconName, iconPath in iconTheme.iconPaths.items():
                self.icons[iconName] = QIcon(iconPath)
                if self.icons[iconName].isNull():
                    if iconName in iconTheme.iconAlternativeNames():
                        for icon in iconTheme.iconAlternatives[iconName]:
                            self.icons[iconName] = QIcon(icon)
                            if not self.icons[iconName].isNull():
                                iconTheme.iconPaths[iconName] = icon
                                break
                        if self.icons[iconName].isNull() and self.__fallbackNames.get(iconName):
                            self.icons[iconName] = QIcon(self.__fallbackNames[iconName])
                    elif self.__fallbackNames.get(iconName):
                        self.icons[iconName] = QIcon(self.__fallbackNames[iconName])
                    else:
                        self.icons[iconName] = QIcon()
                        self.logger.debug("Icon for '{}' is missing.".format(iconName))

    def setTreeIcons(self):
        iconTheme = self.iconTheme
        if iconTheme.isSystemTheme:
            for treeIconName in self.__treeIconNames:
                if not treeIconName in iconTheme.iconNames():
                    continue
                treeIcon = QIcon.fromTheme(iconTheme.iconPaths[treeIconName])
                if not treeIcon.isNull():
                    self.treeIcons[treeIconName] = treeIcon
                else:
                    try:
                        self.treeIcons[treeIconName] = QIcon(self.__fallbackNames[treeIconName])
                    except KeyError as e:
                        self.logger.debug("Tree Icon for '{}' is missing.".format(treeIconName))

    def setPixmaps(self):
        iconTheme = self.iconTheme
        if iconTheme.isSystemTheme:
            for pixmapName in self.__pixmapNames:
                self.pixmaps[pixmapName] = QPixmap(QIcon.fromTheme(iconTheme.iconPaths[pixmapName]).pixmap(48))
        else:
            for pixmapName in self.__pixmapNames:
                self.pixmaps[pixmapName] = QPixmap(iconTheme.iconPaths[pixmapName])


class ÆIconTheme:
    def __init__(self, themeName):
        self.iconPaths = dict()
        self.iconAlternatives = dict()
        self.isSystemTheme = False
        self.themeName = themeName
        self.systemThemeName = ""

    def setIconPaths(self, iconPaths):
        self.iconPaths = iconPaths

    def setIconAlternatives(self, iconPaths):
        self.iconAlternatives = iconPaths

    def iconNames(self):
        return self.iconPaths.keys()

    def iconAlternativeNames(self):
        return self.iconAlternatives.keys()


class ÆTaxonomyList:
    data = list()
    index = 0

    def __init__(self, data=None):
        if data:
            self.data = data

    def __next__(self):
        if self.index == len(self.data):
            raise StopIteration
        else:
            taxonomy = self.data[self.index]
            self.index += 1
        return taxonomy

    def __iter__(self):
        self.index = 0
        return self

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.data[item]
        elif isinstance(item, str):
            for taxonomy in self.data:
                if taxonomy.nounName == item:
                    return taxonomy
                elif taxonomy.pluralName == item:
                    return taxonomy
                elif taxonomy.tableName == item:
                    return taxonomy
                elif taxonomy.dirName == item:
                    return taxonomy

    def __len__(self):
        return len(self.data)

    def append(self, typeObj):
        self.data.append(typeObj)

    def pop(self, index):
        self.data.pop(index)

    def clear(self):
        try:
            self.data.clear()
        except AttributeError:
            del self.data[:]

    def remove(self, objOrName):
        if isinstance(objOrName, ÆTaxonomy):
            self.data.remove(objOrName)
            return True
        elif isinstance(objOrName, str):
            for taxonomy in self.data:
                if taxonomy.nounName == objOrName:
                    self.data.remove(taxonomy)
                    return True
                elif taxonomy.pluralName == objOrName:
                    self.data.remove(taxonomy)
                    return True
                elif taxonomy.tableName == objOrName:
                    self.data.remove(taxonomy)
                    return True
                elif taxonomy.dirName == objOrName:
                    self.data.remove(taxonomy)
                    return True
        return False

    def tableFromPlural(self, pluralName):
        for taxonomy in self.data:
            if taxonomy.pluralName == pluralName:
                return taxonomy.tableName
        return False

    def tableFromNoun(self, nounName):
        for taxonomy in self.data:
            if taxonomy.nounName == nounName:
                return taxonomy.tableName
        return False

    def nounFromPlural(self, pluralName):
        for taxonomy in self.data:
            if taxonomy.pluralName == pluralName:
                return taxonomy.nounName
        return False

    def nounFromTable(self, tableName):
        for taxonomy in self.data:
            if taxonomy.tableName == tableName:
                return taxonomy.nounName
        return False

    def dirFromTable(self, tableName):
        for taxonomy in self.data:
            if taxonomy.tableName == tableName:
                return taxonomy.dirName
        return False

    def dirFromNoun(self, nounName):
        for taxonomy in self.data:
            if taxonomy.nounName == nounName:
                return taxonomy.dirName
        return False

    def dirFromPlural(self, pluralName):
        for taxonomy in self.data:
            if taxonomy.pluralName == pluralName:
                return taxonomy.dirName
        return False

    def pluralFromTable(self, tableName):
        for taxonomy in self.data:
            if taxonomy.tableName == tableName:
                return taxonomy.pluralName
        return False

    def nounNames(self):
        nounList = list()
        for taxonomy in self.data:
            if taxonomy.nounName:
                nounList.append(taxonomy.nounName)
        return nounList

    def tableNames(self, flag=None):
        tableList = list()
        for taxonomy in self.data:
            if flag == Æ.OnlyDisabled:
                if taxonomy.tableName and not taxonomy.enabled:
                    tableList.append(taxonomy.tableName)
            elif flag == Æ.OnlyEnabled:
                if taxonomy.tableName and taxonomy.enabled:
                    tableList.append(taxonomy.tableName)
            elif flag == Æ.NoChildren:
                if taxonomy.tableName and not taxonomy.hasChildren:
                    tableList.append(taxonomy.tableName)
            elif flag == Æ.IsTags:
                if taxonomy.tableName and taxonomy.isTags:
                    tableList.append(taxonomy.tableName)
            elif flag == Æ.NoTags:
                if taxonomy.tableName and not taxonomy.isTags:
                    tableList.append(taxonomy.tableName)
            else:
                if taxonomy.tableName:
                    tableList.append(taxonomy.tableName)
        return tableList

    def pluralNames(self, flag=None):
        pluralList = list()
        for taxonomy in self.data:
            if flag == Æ.OnlyEnabled:
                if taxonomy.pluralName and taxonomy.enabled:
                    pluralList.append(taxonomy.pluralName)
            elif flag == Æ.NoChildren:
                if taxonomy.pluralName and not taxonomy.hasChildren:
                    pluralList.append(taxonomy.pluralName)
            elif flag == Æ.IsTags:
                if taxonomy.pluralName and taxonomy.isTags:
                    pluralList.append(taxonomy.pluralName)
            elif flag == Æ.NoTags:
                if taxonomy.pluralName and not taxonomy.isTags:
                    pluralList.append(taxonomy.pluralName)
            else:
                if taxonomy.pluralName:
                    pluralList.append(taxonomy.pluralName)
        return pluralList

    def validateIcons(self, icons, backupName):
        for taxonomy in self.data:
            if not icons.get(taxonomy.iconName):
                taxonomy.setIconName(backupName)


class ÆTaxonomy:
    pluralName = None
    nounName = None
    dirName = None
    tableName = None
    enabled = True
    iconName = "Categories"
    hasChildren = True
    isTags = False

    def __init__(self, data=None):
        if data:
            self.pluralName = data[0]
            self.nounName = data[1]
            self.tableName = data[2]
            self.extensions = data[3]

    def setPluralName(self, name):
        self.pluralName = name
        if not self.dirName:
            self.dirName = name

    def setNounName(self, name):
        self.nounName = name

    def setDirName(self, name):
        if name not in ("", None):
            self.dirName = name
        else:
            self.dirName = self.pluralName

    def setTableName(self, name):
        self.tableName = name

    def setIconName(self, iconName):
        self.iconName = iconName

    def setEnabled(self, setBool):
        if isinstance(setBool, str):
            if setBool.lower().strip() == "true":
                self.enabled = True
            else:
                self.enabled = False
        elif isinstance(setBool, bool):
            self.enabled = setBool
        elif isinstance(setBool, int):
            if setBool == 1:
                self.enabled = True
            else:
                self.enabled = False

    def setHasChildren(self, setBool):
        if isinstance(setBool, str):
            if setBool.lower().strip() == "true":
                self.hasChildren = True
            else:
                self.hasChildren = False
        elif isinstance(setBool, bool):
            self.hasChildren = setBool
        elif isinstance(setBool, int):
            if setBool == 1:
                self.hasChildren = True
            else:
                self.hasChildren = False

    def setIsTags(self, setBool):
        if isinstance(setBool, str):
            if setBool.lower().strip() == "true":
                self.isTags = True
            else:
                self.isTags = False
        elif isinstance(setBool, bool):
            self.isTags = setBool
        elif isinstance(setBool, int):
            if setBool == 1:
                self.isTags = True
            else:
                self.isTags = False

    def printDetails(self):
        print(bcolours.HEADER+"Noun Name: "+bcolours.ENDC+self.nounName)
        print(bcolours.HEADER+"Plural Name: "+bcolours.ENDC+self.pluralName)
        print(bcolours.HEADER+"Dir Name: "+bcolours.ENDC+self.dirName)
        print(bcolours.HEADER+"Table Name: "+bcolours.ENDC+self.tableName)
        print(bcolours.HEADER+"Icon Name: "+bcolours.ENDC+self.iconName)
        print(bcolours.HEADER+"Enabled: "+bcolours.ENDC+str(self.enabled))
        print(bcolours.HEADER+"Has Children: "+bcolours.ENDC+str(self.hasChildren))
        print(bcolours.HEADER+"Is Tags: "+bcolours.ENDC+str(self.isTags))


class ÆItemTypeList:
    data = list()
    index = 0

    def __init__(self, data=None):
        if data:
            self.data = data

    def __next__(self):
        if self.index == len(self.data):
            raise StopIteration
        else:
            itemType = self.data[self.index]
            self.index += 1
        return itemType

    def __iter__(self):
        self.index = 0
        return self

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.data[item]
        elif isinstance(item, str):
            for itemType in self.data:
                if itemType.nounName == item:
                    return itemType
                elif itemType.pluralName == item:
                    return itemType
                elif itemType.tableName == item:
                    return itemType
                elif itemType.dirName == item:
                    return itemType
        return False

    def __len__(self):
        return len(self.data)

    def append(self, typeObj):
        self.data.append(typeObj)

    def pop(self, index):
        self.data.pop(index)

    def clear(self):
        try:
            self.data.clear()
        except AttributeError:
            del self.data[:]

    def remove(self, objOrName):
        if isinstance(objOrName, ÆItemType):
            self.data.remove(objOrName)
            return True
        elif isinstance(objOrName, str):
            for itemType in self.data:
                if itemType.nounName == objOrName:
                    self.data.remove(itemType)
                    return True
                elif itemType.pluralName == objOrName:
                    self.data.remove(itemType)
                    return True
                elif itemType.tableName == objOrName:
                    self.data.remove(itemType)
                    return True
                elif itemType.dirName == objOrName:
                    self.data.remove(itemType)
                    return True
        return False

    def tableFromPlural(self, pluralName):
        for itemType in self.data:
            if itemType.pluralName == pluralName:
                return itemType.tableName
        return False

    def tableFromNoun(self, nounName):
        for itemType in self.data:
            if itemType.nounName == nounName:
                return itemType.tableName
        return False

    def nounFromPlural(self, pluralName):
        for itemType in self.data:
            if itemType.pluralName == pluralName:
                return itemType.nounName
        return False

    def nounFromTable(self, tableName):
        for itemType in self.data:
            if itemType.tableName == tableName:
                return itemType.nounName
        return False

    def nounFromExtension(self, ext):
        for itemType in self.data:
            if itemType.hasExtension(ext):
                return itemType.nounName
        return False

    def dirFromTable(self, tableName):
        for itemType in self.data:
            if itemType.tableName == tableName:
                return itemType.dirName
        return False

    def dirFromNoun(self, nounName):
        for itemType in self.data:
            if itemType.nounName == nounName:
                return itemType.dirName
        return False

    def dirFromPlural(self, pluralName):
        for itemType in self.data:
            if itemType.pluralName == pluralName:
                return itemType.dirName
        return False

    def pluralFromTable(self, tableName):
        for itemType in self.data:
            if itemType.tableName == tableName:
                return itemType.pluralName
        return False

    def nounNames(self, flag=None):
        nounList = list()
        for itemType in self.data:
            if flag == Æ.OnlyEnabled:
                if itemType.nounName and itemType.enabled:
                    nounList.append(itemType.nounName)
            elif flag == Æ.OnlyDisabled:
                if itemType.nounName and not itemType.enabled:
                    nounList.append(itemType.nounName)
            elif flag == Æ.IsWeblinks:
                if itemType.nounName and itemType.isWeblinks:
                    nounList.append(itemType.nounName)
            elif flag == Æ.NoWeblinks:
                if itemType.nounName and not itemType.isWeblinks:
                    nounList.append(itemType.nounName)
            elif flag == Æ.IsWebpages:
                if itemType.nounName and itemType.isWebpages:
                    nounList.append(itemType.nounName)
            elif flag == Æ.NoWebpages:
                if itemType.nounName and not itemType.isWebpages:
                    nounList.append(itemType.nounName)
            else:
                if itemType.nounName:
                    nounList.append(itemType.nounName)
        return nounList

    def tableNames(self, flag=None):
        tableList = list()
        for itemType in self.data:
            if flag == Æ.OnlyEnabled:
                if itemType.tableName and itemType.enabled:
                    tableList.append(itemType.tableName)
            elif flag == Æ.OnlyDisabled:
                if itemType.tableName and not itemType.enabled:
                    tableList.append(itemType.tableName)
            elif flag == Æ.IsWeblinks:
                if itemType.tableName and itemType.isWeblinks:
                    tableList.append(itemType.tableName)
            elif flag == Æ.NoWeblinks:
                if itemType.tableName and not itemType.isWeblinks:
                    tableList.append(itemType.tableName)
            else:
                if itemType.tableName:
                    tableList.append(itemType.tableName)
        return tableList

    def validateIcons(self, icons, backupName):
        for itemType in self.data:
            if not icons.get(itemType.iconName):
                itemType.setIconName(backupName)


class ÆItemType:
    pluralName = None
    nounName = None
    dirName = None
    tableName = None
    enabled = True
    iconName = "Items"
    isWeblinks = False
    isWebpages = False

    def __init__(self, data=None):
        self.extensions = list()

        if data:
            self.pluralName = data[0]
            self.nounName = data[1]
            self.tableName = data[2]
            self.extensions = data[3]

    def setPluralName(self, name):
        self.pluralName = name
        if not self.dirName:
            self.dirName = name

    def setNounName(self, name):
        self.nounName = name

    def setDirName(self, name):
        if name not in ("", None):
            self.dirName = name
        else:
            self.dirName = self.pluralName

    def setTableName(self, name):
        self.tableName = name

    def setExtensions(self, exts):
        self.clearExtensions()
        for ext in exts:
            if ext not in self.extensions:
                self.extensions.append(ext)

    def addExtension(self, ext):
        if ext not in self.extensions:
            self.extensions.append(ext)

    def hasExtension(self, ext):
        if ext in self.extensions:
            return True
        else:
            return False

    def removeExtension(self, ext):
        self.extensions.remove(ext)

    def clearExtensions(self):
        try:
            self.extensions.clear()
        except AttributeError:
            del self.extensions[:]

    def extensionCount(self):
        return len(self.extensions)

    def setIconName(self, iconName):
        self.iconName = iconName

    def setEnabled(self, setBool):
        if isinstance(setBool, str):
            if setBool.lower().strip() == "true":
                self.enabled = True
            else:
                self.enabled = False
        elif isinstance(setBool, bool):
            self.enabled = setBool
        elif isinstance(setBool, int):
            if setBool == 1:
                self.enabled = True
            else:
                self.enabled = False

    def printDetails(self):
        print(bcolours.HEADER+"Noun Name: "+bcolours.ENDC+self.nounName)
        print(bcolours.HEADER+"Plural Name: "+bcolours.ENDC+self.pluralName)
        print(bcolours.HEADER+"Dir Name: "+bcolours.ENDC+self.dirName)
        print(bcolours.HEADER+"Table Name: "+bcolours.ENDC+self.tableName)
        print(bcolours.HEADER+"Icon Name: "+bcolours.ENDC+self.iconName)
        print(bcolours.HEADER+"Enabled: "+bcolours.ENDC+str(self.enabled))
        print(bcolours.HEADER+"Is Weblinks: "+bcolours.ENDC+str(self.isWeblinks))
        print(bcolours.HEADER+"Is Webpages: "+bcolours.ENDC+str(self.isWebpages))
        print(bcolours.HEADER+"Extensions: "+bcolours.ENDC)
        print(self.extensions)


class ÆDataFolderModel(QAbstractTableModel):
    advancedMode = False
    currentItemType = None
    fileData = None

    def __init__(self, parent, itemType=None, advancedMode=False):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        if advancedMode is True:
            self.advancedMode = True

        self.db = parent.db
        self.config = parent.config
        self.iconsList = parent.app.iconsList
        self.icons = parent.icons
        self.treeIcons = parent.treeIcons

        self.parent = parent
        self.dataDir = parent.dataDir
        self.items = list()

        self.colNames = ("File Name", "Date Modified", "Has Item?", "File Size", "Extension")

        if itemType:
            self.setItemType(itemType)

    def flags(self, index):
        flags = super().flags(index)
        if not index.isValid():
            return 0
        if self.advancedMode is True:
            if index.column() == 0:
                flags |= Qt.ItemIsEditable | Qt.ItemIsUserCheckable
        return flags

    def setItemType(self, itemType):
        if itemType in self.config['itemTypes'].nounNames(Æ.IsWeblinks):
            return False
        else:
            self.currentItemType = itemType
        folderPath = self.dataDir + self.config['itemTypes'].dirFromNoun(itemType) + "/"
        try:
            if os.path.exists(folderPath):
                for file in os.listdir(folderPath):
                    filePath = folderPath+file
                    if os.path.isfile(filePath):
                        fileSize = os.path.getsize(filePath)
                        fileModified = os.path.getmtime(filePath)
                        fileExtension = os.path.splitext(file)[1][1:].lower().strip()
                        fileName = os.path.splitext(file)[0]

                        fileType = self.config['itemTypes'].nounFromExtension(fileExtension)
                        if fileType:
                            itemStatus = self.checkItemExistance(file)
                            if self.advancedMode is False:
                                self.items.append((False, fileName, fileModified, itemStatus,
                                                   fileSize, fileExtension))
                            else:
                                self.items.append([False, fileName, fileModified, itemStatus,
                                                   fileSize, fileExtension])
        except BaseException as e:
            warningMsgBox(self.parent, e, "Error Opening Folder")

    def checkItemExistance(self, file):
        try:
            self.db.open()
            query = QSqlQuery(self.db.con)
            query.setForwardOnly(True)
            typeIden = self.config['itemTypes'].tableFromNoun(self.currentItemType)
            sql = "SELECT COUNT(*) FROM items AS i "\
                  "WHERE (item_name = '{}') "\
                  "AND (type_id = '{}')".format(file, typeIden)
            query.exec_(sql)
            itemStatus = 'No'
            if query.next():
                if query.value(0):
                    itemStatus = 'Yes'
            self.db.close()
            return itemStatus
        except BaseException as e:
            warningMsgBox(self.parent, e, title="Error Checking Item")
            return False

    def data(self, index, role=Qt.DisplayRole):
        itemColIndex = index.column()+1
        itemRowIndex = index.row()
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            if index.column() == 1:
                return time.ctime(self.items[itemRowIndex][itemColIndex])
            elif index.column() == 3:
                return formatBytes(self.items[itemRowIndex][itemColIndex])
            else:
                return self.items[itemRowIndex][itemColIndex]
        elif role == Qt.DecorationRole:
            if index.column() == 2:
                statusToName = dict(Yes='Success', No='Warning')
                hasItem = self.items[itemRowIndex][itemColIndex]
                return self.iconsList.getTreeIcon(statusToName[hasItem])
        elif role == Qt.CheckStateRole:
            if self.advancedMode is True:
                if index.column() == 0:
                    if self.items[itemRowIndex][0] is True:
                        return Qt.Checked
                    else:
                        return Qt.Unchecked
        elif role == Qt.EditRole:
            return self.items[itemRowIndex][itemColIndex]

    def rowCount(self, parent=None):
        return len(self.items)

    def columnCount(self, parent=None):
        return len(self.colNames)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.colNames[section]
        else:
            return None

    def clear(self):
        try:
            self.items.clear()
        except AttributeError:
            del self.items[:]

    def sort(self, col, order):
        itemColIndex = col+1
        self.layoutAboutToBeChanged.emit()
        self.items.sort(key=lambda tup: tup[itemColIndex])
        if order == Qt.AscendingOrder:
            self.items.reverse()
            self.logger.debug("Sorting `{}` by Descending Order.".format(self.colNames[col]))
        else:
            self.logger.debug("Sorting `{}` by Ascending Order.".format(self.colNames[col]))
        self.layoutChanged.emit()

    def setData(self, index, value, role=Qt.DisplayRole):
        row = index.row()
        self.logger.debug("Row ID: "+str(row))
        if not index.isValid():
            return None
        if role == Qt.CheckStateRole:
            if Qt.CheckState(value) == Qt.Checked:
                self.items[row][0] = True
                self.logger.debug("Row `{}` Checked".format(self.data(self.index(index.row(), 0))))
            else:
                self.items[row][0] = False
                self.logger.debug("Row `{}` Unchecked".format(self.data(self.index(index.row(), 0))))
            self.dataChanged.emit(index, index)
            return True
        elif role == Qt.EditRole and value:
            if value == self.items[row][1]:
                return False
            message = "Are you sure you want to rename the file?"
            msgBox = ÆMessageBox(self.parent)
            msgBox.setIcon(ÆMessageBox.Question)
            # msgBox.setStyleSheet("QLabel{min-height: 200px;}");
            msgBox.setWindowTitle("Rename the File?")
            msgBox.setText(message)
            msgBox.setStandardButtons(msgBox.StandardButton.Ok | msgBox.StandardButton.Cancel)
            msgBox.setDefaultButton(msgBox.StandardButton.Cancel)
            if self.items[row][3] == 'Yes':
                msgBox.setCheckable(True)
                msgBox.checkboxes[0].setText("Rename corresponding database item.")
                msgBox.checkboxes[0].setChecked(True)
            ret = msgBox.exec_()
            if ret == msgBox.StandardButton.Ok:
                value = æscape(value)
                oldName = self.items[row][1]+'.'+self.items[row][5]
                newName = value+'.'+self.items[row][5]
                if self.renameFile(index, value):
                    if self.items[row][3] == 'Yes' and msgBox.checkboxes[0].isChecked():
                        try:
                            self.db.open()
                            query = QSqlQuery(self.db.con)
                            query.setForwardOnly(True)
                            tableTypeName = self.config['itemTypes'].tableFromNoun(self.currentItemType)
                            sql = "UPDATE items Set item_name='{}' WHERE (type_id='{}') AND (item_name='{}')"\
                                .format(newName, tableTypeName, oldName)
                            self.logger.debug('\n'+sql)
                            query.exec_(sql)
                            self.db.close()
                        except BaseException as e:
                            warningMsgBox(self.parent, e, title="Error Renaming Item")
                            return False
                    self.items[row][3] = self.checkItemExistance(newName)
                    self.dataChanged.emit(index, index)
                    return True

            return False
        else:
            return False

    def checkAll(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.items:
            row[0] = True
        self.layoutChanged.emit()

    def checkNone(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.items:
            row[0] = False
        self.layoutChanged.emit()

    def checkInverse(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.items:
            if row[0] is False:
                row[0] = True
            else:
                row[0] = False
        self.layoutChanged.emit()

    def renameFile(self, index, value):
        row = index.row()
        oldName = self.items[row][1]+'.'+self.items[row][5]
        newName = value+'.'+self.items[row][5]
        oldFilePath = getDataFilePath(
            self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), oldName)
        self.logger.debug(oldFilePath)
        newFilePath = getDataFilePath(
            self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), newName)
        self.logger.debug(newFilePath)
        try:
            if self.currentItemType in self.config['itemTypes'].nounNames(Æ.IsWebpages):
                oldFolderName = self.items[row][1]+'_files'
                newFolderName = value+'_files'
                oldFolderPath = getDataFilePath(
                    self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), oldFolderName)
                newFolderPath = getDataFilePath(
                    self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), newFolderName)
                if os.path.exists(oldFolderPath):
                    os.rename(oldFolderPath, newFolderPath)
                    file = QFile(oldFilePath)
                    if file.open(QIODevice.ReadWrite):
                        self.fileData = file.readAll()
                        oldFolderNameQuoted = quote(oldFolderName)
                        newFolderNameQuoted = quote(newFolderName)
                        self.fileData.replace(oldFolderName, newFolderNameQuoted)
                        self.fileData.replace(oldFolderNameQuoted, newFolderNameQuoted)
                        file.resize(0)
                        file.seek(0)
                        file.write(self.fileData)
                        file.close()
                        file.deleteLater()

            os.rename(oldFilePath, newFilePath)
            self.items[row][1] = value
            return True
        except BaseException as e:
            warningMsgBox(self.parent, e, title="Error Renaming File")
            return False

    def deleteFile(self, row, bulk=False, withItem=False):
        fileName = self.items[row][1]+'.'+self.items[row][5]
        filePath = getDataFilePath(
            self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), fileName)
        try:
            if bulk is False:
                self.layoutAboutToBeChanged.emit()
            if self.currentItemType in self.config['itemTypes'].nounNames(Æ.IsWebpages):
                folderName = self.items[row][1]+'_files'
                folderPath = getDataFilePath(
                    self.dataDir, self.config['itemTypes'].dirFromNoun(self.currentItemType), folderName)
                if os.path.exists(folderPath):
                    shutil.rmtree(folderPath)
            os.remove(filePath)
            if withItem:
                if not bulk:
                    self.db.open()
                    self.db.transaction(debug=True)
                tableTypeName = self.config['itemTypes'].tableFromNoun(self.currentItemType)
                querySelect = self.db.selectItems(dict(col='item_id', item_name=fileName, type_id=tableTypeName))
                if querySelect.first():
                    self.db.deleteItem(itemid=querySelect.value(0))
                if not bulk:
                    self.db.commit()
                    self.db.close()

            self.logger.info("[{}] {} deleted.".format(str(row), fileName))
            self.items.pop(row)
            if bulk is False:
                self.layoutChanged.emit()
            return True
        except BaseException as e:
            warningMsgBox(self.parent, e, title="Error Deleting File")
            return False

    def deleteFiles(self, rows, withItem=False):
        self.layoutAboutToBeChanged.emit()
        if withItem:
            self.db.open()
            self.db.transaction()
        for row in reversed(rows):
            self.deleteFile(row, bulk=True, withItem=withItem)
        if withItem:
            self.db.commit()
            self.db.close()
        self.layoutChanged.emit()

    def autoCreateItem(self, row, bulk=False):
        tableTypeName = self.config['itemTypes'].tableFromNoun(self.currentItemType)
        try:
            if bulk is False:
                self.layoutAboutToBeChanged.emit()

            itemExists = self.items[row][3]
            if itemExists == "No":
                if not bulk:
                    self.db.open()
                    self.db.transaction(debug=True)
                fileName = self.items[row][1]+'.'+self.items[row][5]
                dbResponse = self.db.newItem(data=dict(name=fileName, type=tableTypeName))
                if dbResponse:
                    self.items[row][3] = "Yes"
                if not bulk:
                    self.db.commit()
                    self.db.close()
            self.items[row][0] = False
            if bulk is False:
                self.layoutChanged.emit()
            return True
        except BaseException as e:
            warningMsgBox(self.parent, e, title="Error Creating Items")
            return False

    def autoCreateItems(self, rows):
        self.layoutAboutToBeChanged.emit()
        self.db.open()
        self.db.transaction()
        for row in reversed(rows):
            self.autoCreateItem(row, bulk=True)
        self.db.commit()
        self.db.close()
        self.layoutChanged.emit()


class ÆMainTableModel(QAbstractTableModel):
    tableType = Æ.TableItems
    curSortColIndex = None
    viewMode = "list"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        if parent:
            self.parent = parent
            self.iconsList = parent.app.iconsList
            self.icons = parent.icons
            self.treeIcons = parent.treeIcons
            self.config = parent.config
        self.colNames = ("Iden", "Name", "Type", "Time", "Source")

        self.rows = list()

    def setParent(self, parent):
        self.parent = parent
        self.iconsList = parent.app.iconsList
        self.icons = parent.icons
        self.treeIcons = parent.treeIcons
        self.config = parent.config
        super().setParent(parent)

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.colNames)

    def headerData(self, section, orientation, role):
        try:
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return self.colNames[section]
            else:
                return None
        except IndexError:
            pass

    def sort(self, col, order):
        itemColIndex = col+1
        self.layoutAboutToBeChanged.emit()
        self.curSortColIndex = (col, order)
        self.rows.sort(key=lambda tup: tup[itemColIndex])
        if order == Qt.AscendingOrder:
            self.rows.reverse()
            self.logger.debug("Sorting `{}` by Descending Order.".format(self.colNames[col]))
        else:
            self.logger.debug("Sorting `{}` by Ascending Order.".format(self.colNames[col]))
        self.layoutChanged.emit()

    def setColNames(self, colNames):
        self.colNames = colNames

    def setTableType(self, tableType):
        if self.tableType in Æ.ItemTableTypes:
            if not tableType in Æ.ItemTableTypes:
                self.curSortColIndex = None
        self.tableType = tableType

    def setQuery(self, sql, db):
        try:
            db.open()
            query = QSqlQuery(db.con)
            query.setForwardOnly(True)
            query.exec_(sql)
            if self.tableType in Æ.ItemTableTypes:
                while query.next():
                    itemIden = query.value(0)
                    itemName = query.value(1)
                    itemType = query.value(2)
                    itemTime = query.value(3)
                    itemSource = unquote(query.value(4))
                    self.rows.append([False, itemIden, itemName, itemType, itemTime, itemSource])
            if self.curSortColIndex:
                self.sort(self.curSortColIndex[0], self.curSortColIndex[1])
            db.close()
        except BaseException as e:
            warningMsgBox(self.parent, e, "Error Reading Database")

    def data(self, index, role=Qt.DisplayRole):
        itemColIndex = index.column()+1
        itemRowIndex = index.row()
        if role == Qt.CheckStateRole:
            if index.column() == 0:
                if self.rows[itemRowIndex][0] is True:
                    return Qt.Checked
                else:
                    return Qt.Unchecked
        elif role == Qt.DisplayRole:
            if self.viewMode == "icons":
                if index.column() == 0:
                    return self.rows[itemRowIndex][2]
                elif index.column() == -666:
                    return self.rows[itemRowIndex][0]
            if index.column() == 3:
                rowValue = self.rows[itemRowIndex][itemColIndex]
                if isinstance(rowValue, str):
                    return rowValue
                elif isinstance(rowValue, QDateTime):
                    if rowValue.isValid():
                        return rowValue
                    else:
                        return rowValue
                else:
                    return "0000-00-00 00:00:00"
            elif index.column() == 2:
                rowValue = self.rows[itemRowIndex][itemColIndex]
                nounName = self.config['itemTypes'].nounFromTable(rowValue)
                if not nounName:
                    nounName = self.createMissingItemType(rowValue).nounName
                return nounName
            else:
                return self.rows[itemRowIndex][itemColIndex]
        elif role == Qt.DecorationRole:
            if index.column() == 1 and self.viewMode == "list":
                rowType = self.rows[itemRowIndex][itemColIndex+1]

                itemTypeObj = self.config['itemTypes'][rowType]
                if itemTypeObj:
                    iconName = itemTypeObj.iconName
                else:
                    itemTypeObj = self.createMissingItemType(rowType)
                    iconName = itemTypeObj.iconName
                return self.iconsList.getTreeIcon(iconName)
            elif index.column() == 0 and self.viewMode == "icons":
                rowType = self.rows[itemRowIndex][itemColIndex+2]

                if rowType == "image":
                    rowName = self.rows[itemRowIndex][itemColIndex+1]
                    dataDir = self.config['options']['defaultDataDir']
                    imagePath = getDataFilePath(dataDir, self.config['itemTypes'].dirFromTable(rowType), rowName)
                    return QIcon(imagePath)
                else:
                    itemTypeObj = self.config['itemTypes'][rowType]
                    if itemTypeObj:
                        iconName = itemTypeObj.iconName
                    else:
                        itemTypeObj = self.createMissingItemType(rowType)
                        iconName = itemTypeObj.iconName
                    return self.iconsList.getTreeIcon(iconName)

    def setData(self, index, value, role=Qt.DisplayRole):
        row = index.row()
        self.logger.debug("Row ID: "+str(row))
        if not index.isValid():
            return None
        if role == Qt.CheckStateRole:
            if Qt.CheckState(value) == Qt.Checked:
                self.rows[row][0] = True
                self.logger.debug("Row `{}` Checked".format(self.data(self.index(index.row(), 0))))
            else:
                self.rows[row][0] = False
                self.logger.debug("Row `{}` Unchecked".format(self.data(self.index(index.row(), 0))))
            self.dataChanged.emit(index, index)
            return True
        else:
            return False

    def checkSelection(self, selectedRows):
        self.layoutAboutToBeChanged.emit()
        for row in selectedRows:
            self.rows[row][0] = True
        self.layoutChanged.emit()

    def uncheckSelection(self, selectedRows):
        self.layoutAboutToBeChanged.emit()
        for row in selectedRows:
            self.rows[row][0] = False
        self.layoutChanged.emit()

    def checkInvertSelection(self, selectedRows):
        self.layoutAboutToBeChanged.emit()
        for row in selectedRows:
            if self.rows[row][0] is False:
                self.rows[row][0] = True
            else:
                self.rows[row][0] = False
        self.layoutChanged.emit()

    def checkAll(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.rows:
            row[0] = True
        self.layoutChanged.emit()

    def checkNone(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.rows:
            row[0] = False
        self.layoutChanged.emit()

    def checkInverse(self):
        self.layoutAboutToBeChanged.emit()
        for row in self.rows:
            if row[0] is False:
                row[0] = True
            else:
                row[0] = False
        self.layoutChanged.emit()

    def createMissingItemType(self, name):
        itemType = ÆItemType()
        itemType.setPluralName(name.title()+"s")
        itemType.setNounName(name.title())
        itemType.setTableName(name)
        self.config['itemTypes'].append(itemType)
        return itemType

    def clear(self):
        try:
            self.rows.clear()
        except AttributeError:
            del self.rows[:]


class ÆCategoryTreeItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        try:
            return len(self.childItems)
        except AttributeError:
            return 0

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        try:
            return self.itemData[column]
        except IndexError:
            return None

    def setData(self, column, data):
        try:
            self.itemData[column] = data
        except IndexError:
            pass

    def sort(self, col, reverse):
        try:
            itemColIndex = col+1
            if self.childCount() > 1:
                self.childItems.sort(key=operator.methodcaller('data', itemColIndex), reverse=reverse)
                for child in self.childItems:
                    child.sort(col, reverse)
        except TypeError:
            pass

    def parent(self):
        try:
            return self.parentItem
        except AttributeError:
            return None

    def row(self):
        try:
            if self.parentItem:
                return self.parentItem.childItems.index(self)
        except ValueError:
            return 0

        return 0

    def checkAll(self):
        if self.parent():
            self.setData(0, True)
        if self.childCount() > 0:
            for child in self.childItems:
                child.checkAll()

    def checkNone(self):
        if self.parent():
            self.setData(0, False)
        if self.childCount() > 0:
            for child in self.childItems:
                child.checkNone()

    def checkInverse(self):
        if self.parent():
            if not self.data(0):
                self.setData(0, True)
            else:
                self.setData(0, False)
        if self.childCount() > 0:
            for child in self.childItems:
                child.checkInverse()

    def checkInverseSingle(self):
        if self.parent():
            if not self.data(0):
                self.setData(0, True)
            else:
                self.setData(0, False)

    def returnCheckedData(self, dataList=None):
        if not dataList:
            dataList = []

        if self.childCount() > 0:
            for child in self.childItems:
                dataList = child.returnCheckedData(dataList)
        if self.parent():
            if self.data(0):
                name = self.data(1)
                iden = self.data(2)
                rowType = self.data(3)
                dataList.append((iden, name, rowType))
        return dataList

    def clear(self):
        self.childItems.clear()


class ÆCategoryTreeModel(QAbstractItemModel):
    curSortColIndex = None
    tableType = Æ.TableCategories

    def __init__(self, mainWindow=None):
        super().__init__(mainWindow)
        self.logger = logging.getLogger(self.__class__.__name__)

        if mainWindow:
            self.mainWindow = mainWindow
            self.iconsList = mainWindow.app.iconsList
            self.icons = mainWindow.icons
            self.treeIcons = mainWindow.treeIcons
            self.config = mainWindow.config

        self.rootItem = ÆCategoryTreeItem(("Name", "Iden", "Taxonomy", "Count", "Slug"))
        self.categories = list()

    def setParent(self, mainWindow):
        self.mainWindow = mainWindow
        self.iconsList = mainWindow.app.iconsList
        self.icons = mainWindow.icons
        self.treeIcons = mainWindow.treeIcons
        self.config = mainWindow.config
        super().setParent(mainWindow)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None
        itemColIndex = index.column()+1
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            if index.column() == 2:
                rowValue = item.data(itemColIndex)
                nounName = self.config['taxonomies'].nounFromTable(rowValue)
                if not nounName:
                    nounName = self.createMissingTaxonomy(rowValue).nounName
                return nounName
            else:
                return item.data(itemColIndex)
        elif role == Qt.CheckStateRole:
            if index.column() == 0:
                if item.data(index.column()):
                    return Qt.Checked
                else:
                    return Qt.Unchecked
        elif role == Qt.DecorationRole:
            if index.column() == 0:
                rowType = item.data(itemColIndex+2)
                taxonomyObj = self.config['taxonomies'][rowType]
                if taxonomyObj:
                    iconName = taxonomyObj.iconName
                else:
                    iconName = self.createMissingTaxonomy(rowType).iconName
                return self.iconsList.getTreeIcon(iconName)

    def setColNames(self, colNames):
        self.rootItem.itemData = colNames

    def setTableType(self, tableType):
        if self.tableType in Æ.ItemTableTypes:
            if not tableType in Æ.ItemTableTypes:
                self.curSortColIndex = None
        elif self.tableType in Æ.CategoryTableTypes:
            if not tableType in Æ.CategoryTableTypes:
                self.curSortColIndex = None
        self.tableType = tableType

    def setData(self, index, value, role=Qt.DisplayRole):
        row = index.row()
        item = index.internalPointer()
        self.logger.debug("Row ID: "+str(row))
        if not index.isValid():
            return None
        if role == Qt.CheckStateRole:
            if Qt.CheckState(value) == Qt.Checked:
                item.setData(0, True)
                self.logger.debug("Row `{}` Checked".format(item.data(2)))
            else:
                item.setData(0, False)
                self.logger.debug("Row `{}` Unchecked".format(item.data(2)))
            self.dataChanged.emit(index, index)
            return True
        else:
            return False

    def checkSelection(self, indexes):
        self.layoutAboutToBeChanged.emit()
        for index in indexes:
            self.setData(index, Qt.Checked, Qt.CheckStateRole)
        self.layoutChanged.emit()

    def uncheckSelection(self, indexes):
        self.layoutAboutToBeChanged.emit()
        for index in indexes:
            self.setData(index, Qt.Unchecked, Qt.CheckStateRole)
        self.layoutChanged.emit()

    def checkInvertSelection(self, indexes):
        self.layoutAboutToBeChanged.emit()
        for index in indexes:
            item = index.internalPointer()
            item.checkInverseSingle()
        self.layoutChanged.emit()

    def checkAll(self):
        self.layoutAboutToBeChanged.emit()
        self.rootItem.checkAll()
        self.layoutChanged.emit()

    def checkNone(self):
        self.layoutAboutToBeChanged.emit()
        self.rootItem.checkNone()
        self.layoutChanged.emit()

    def checkInverse(self):
        self.layoutAboutToBeChanged.emit()
        self.rootItem.checkInverse()
        self.layoutChanged.emit()

    def sort(self, col, order):
        self.layoutAboutToBeChanged.emit()
        if len(self.categories) > 0:
            self.curSortColIndex = (col, order)
            if order == Qt.AscendingOrder:
                reverse = True
                self.logger.debug("Sorting `{}` by Descending Order.".format(self.rootItem.data(col)))
            elif order == Qt.DescendingOrder:
                reverse = False
                self.logger.debug("Sorting `{}` by Ascending Order.".format(self.rootItem.data(col)))
            self.rootItem.sort(col, reverse)
        self.layoutChanged.emit()

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()
        try:
            return self.createIndex(parentItem.row(), 0, parentItem)
        except AttributeError:
            return QModelIndex()

    def rowCount(self, parent=None):
        if parent:
            if parent.column() > 0:
                return 0

            if not parent.isValid():
                parentItem = self.rootItem
            else:
                parentItem = parent.internalPointer()

            return parentItem.childCount()
        else:
            return len(self.categories)

    def setupModelData(self, sqlExtra, db):
        parents = [self.rootItem]
        indentations = [0]
        number = 0

        db.open()
        self.categories = db.selectCategoriesAsTree(args=dict(extra=sqlExtra, complete=True))
        db.close()
        while number < len(self.categories):
            position = self.categories[number]['level']
            # Read the column data from the rest of the line.
            columnData = [False, self.categories[number]['name'], self.categories[number]['id'],
                          self.categories[number]['tax'], self.categories[number]['count'],
                          self.categories[number]['slug']]
            if position > indentations[-1]:
                # The last child of the current parent is now the new
                # parent unless the current parent has no children.
                if parents[-1].childCount() > 0:
                    parents.append(parents[-1].child(parents[-1].childCount() - 1))
                    indentations.append(position)
            else:
                while position < indentations[-1] and len(parents) > 0:
                    parents.pop()
                    indentations.pop()
            # Append a new item to the current parent's list of children.
            parents[-1].appendChild(ÆCategoryTreeItem(columnData, parents[-1]))

            number += 1
        self.logger.debug("Finished creating model data.")

        if self.curSortColIndex:
            self.sort(self.curSortColIndex[0], self.curSortColIndex[1])

    def clear(self):
        self.beginResetModel()
        self.rootItem.clear()
        self.endResetModel()

    def createMissingTaxonomy(self, name):
        taxonomy = ÆTaxonomy()
        taxonomy.setPluralName(name.title()+"s")
        taxonomy.setNounName(name.title())
        taxonomy.setTableName(name)
        self.config['taxonomies'].append(taxonomy)
        return taxonomy


class ÆRelationsTableModel(QAbstractTableModel):
    tableType = "Items"
    curSortColIndex = None

    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.iconsList = parent.app.iconsList
        self.icons = parent.icons
        self.treeIcons = parent.treeIcons
        self.config = parent.config
        self.colNames = ("Name", "Taxonomy")

        self.rows = list()

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.colNames)

    def headerData(self, section, orientation, role):
        try:
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return self.colNames[section]
            else:
                return None
        except IndexError:
            pass

    def setColNames(self, colNames):
        self.colNames = colNames

    def setTableType(self, tableType):
        self.tableType = tableType

    def setQuery(self, sql, db):
        try:
            query = QSqlQuery(db.con)
            query.setForwardOnly(True)
            query.exec_(sql)
            if self.tableType == "Categories":
                while query.next():
                    termName = query.value(0)
                    termTaxonomy = query.value(1)
                    termIden = query.value(2)
                    self.rows.append((termName, termTaxonomy, termIden))
            elif self.tableType == "Items":
                while query.next():
                    itemName = query.value(0)
                    itemType = query.value(1)
                    itemIden = query.value(2)
                    itemSource = unquote(query.value(3))
                    self.rows.append((itemName, itemType, itemIden, itemSource))
        except BaseException as e:
            warningMsgBox(self.parent, e, "Error Reading Database")

    def data(self, index, role=Qt.DisplayRole):
        if self.tableType == "Items":
            return self.dataItems(index, role)
        elif self.tableType == "Categories":
            return self.dataCategories(index, role)

    def dataCategories(self, index, role):
        itemColIndex = index.column()
        itemRowIndex = index.row()
        if role == Qt.DisplayRole:
            if index.column() == 1:
                rowValue = self.rows[itemRowIndex][itemColIndex]
                nounName = self.config['taxonomies'].nounFromTable(rowValue)
                return nounName
            else:
                return self.rows[itemRowIndex][itemColIndex]
        if role == Qt.DecorationRole:
            if index.column() == 0:
                rowType = self.rows[itemRowIndex][itemColIndex+1]
                taxonomyObj = self.config['taxonomies'][rowType]
                iconName = taxonomyObj.iconName
                return self.iconsList.getTreeIcon(iconName)

    def dataItems(self, index, role):
        itemColIndex = index.column()
        itemRowIndex = index.row()
        if role == Qt.DisplayRole:
            if index.column() == 1:
                rowValue = self.rows[itemRowIndex][itemColIndex]
                nounName = self.config['itemTypes'].nounFromTable(rowValue)
                return nounName
            else:
                return self.rows[itemRowIndex][itemColIndex]
        elif role == Qt.DecorationRole:
            if index.column() == 0:
                rowType = self.rows[itemRowIndex][itemColIndex+1]
                itemTypeObj = self.config['itemTypes'][rowType]
                iconName = itemTypeObj.iconName
                return self.iconsList.getTreeIcon(iconName)

    def clear(self):
        try:
            self.rows.clear()
        except AttributeError:
            del self.rows[:]

    def sort(self, col, order):
        itemColIndex = col
        self.layoutAboutToBeChanged.emit()
        self.curSortColIndex = (col, order)
        self.rows.sort(key=lambda tup: tup[itemColIndex])
        if order == Qt.AscendingOrder:
            self.rows.reverse()
            self.logger.debug("Sorting `{}` by Descending Order.".format(self.colNames[col]))
        else:
            self.logger.debug("Sorting `{}` by Ascending Order.".format(self.colNames[col]))
        self.layoutChanged.emit()


class ÆMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super(ÆMessageBox, self).__init__(parent)
        self.checkable = False
        self.checkboxes = list()

    def setCheckable(self, setBool, amount=1):
        if setBool is True:
            self.checkable = True
            # buttonBoxItem = self.layout().takeAt(2)
            # checkboxLayout = QVBoxLayout()
            for i in range(amount):
                self.checkboxes.append(QCheckBox())
                # checkboxLayout.addWidget(self.checkboxes[-1])
                self.layout().addWidget(self.checkboxes[-1])
            # self.layout().addLayout(checkboxLayout, 2, 1)
            # self.layout().addItem(buttonBoxItem, 3, 1)
        else:
            self.checkable = False


class ÆMainTreeView(QTreeView):
    keyPressed = None
    searchString = None
    searchResults = list()
    searchResultsIndex = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setStyleSheet("")
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setProperty("showDropIndicator", False)
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setAcceptDrops(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setIconSize(QSize(22, 22))
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setSortingEnabled(True)
        self.setHeaderHidden(False)
        self.setObjectName("treeView")
        self.header().setStretchLastSection(True)
        self.setAllColumnsShowFocus(True)

        self.expanded.connect(lambda: self.resizeColumnToContents(0))
        self.collapsed.connect(lambda: self.resizeColumnToContents(0))

    def setModel(self, model):
        super().setModel(model)
        try:
            model.layoutChanged.connect(self.modelLayoutChanged, Qt.UniqueConnection)
        except (RuntimeError, AttributeError):
            pass

    def modelLayoutChanged(self):
        self.clearSelection()
        if self.searchString:
            self.searchRefresh()

    def focusOutEvent(self, event):
        self.keyPressed = None
        super().focusOutEvent(event)

    def keyPressEvent(self, keyEvent):
        self.keyPressed = keyEvent.key()
        super().keyPressEvent(keyEvent)

    def keyReleaseEvent(self, keyEvent):
        self.keyPressed = None
        super().keyReleaseEvent(keyEvent)

    def mouseMoveEvent(self, event):
        if not self.keyPressed in (Qt.Key_Shift, Qt.Key_Control):
            self.setSelectionMode(QAbstractItemView.SingleSelection)
        super().mouseMoveEvent(event)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def search(self, searchString):
        searchString = searchString.lower()
        self.searchString = æscape(searchString)
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchResultsIndex = 0
        model = self.model()

        if model.tableType in Æ.ItemTableTypes:
            for rowIndex, rowItem in enumerate(model.rows):
                rowName = rowItem[2].lower()
                if searchString in rowName:
                    self.searchResults.append(model.index(rowIndex, 0))
            if self.searchResults:
                self.setCurrentIndex(self.searchResults[0])
        elif model.tableType in Æ.CategoryTableTypes:
            for rowIndex, childItem in enumerate(model.rootItem.childItems):
                childIndex = model.index(rowIndex, 0, QModelIndex())
                rowName = childItem.data(1).lower()
                if childItem.childCount() > 0:
                    self.recursiveCategorySearch(childItem, childIndex)
                elif searchString in rowName:
                    self.searchResults.append(childIndex)
            if self.searchResults:
                self.setCurrentIndex(self.searchResults[0])

    def recursiveCategorySearch(self, item, currentIndex):
        itemName = item.data(1).lower()
        if self.searchString in itemName:
            self.searchResults.append(currentIndex)
        if item.childCount() > 0:
            for rowIndex, childItem in enumerate(item.childItems):
                childIndex = self.model().index(rowIndex, 0, currentIndex)
                self.recursiveCategorySearch(childItem, childIndex)

    def searchRefresh(self):
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchResultsIndex = 0
        model = self.model()
        if model.tableType in Æ.ItemTableTypes:
            for rowIndex, rowItem in enumerate(model.rows):
                rowName = rowItem[2].lower()
                if self.searchString in rowName:
                    self.searchResults.append(model.index(rowIndex, 0, QModelIndex()))
        elif model.tableType in Æ.CategoryTableTypes:
            for rowIndex, childItem in enumerate(model.rootItem.childItems):
                childIndex = model.index(rowIndex, 0, QModelIndex())
                rowName = childItem.data(1).lower()
                if childItem.childCount() > 0:
                    self.recursiveCategorySearch(childItem, childIndex)
                elif self.searchString in rowName:
                    self.searchResults.append(childIndex)

    def selectAllSearchResults(self):
        selModel = self.selectionModel()
        selModelSelection = selModel.selection()
        selModel.clear()

        for index in self.searchResults:
            modelLeftIndex = index
            itemSelection = QItemSelection(modelLeftIndex, modelLeftIndex)
            selModelSelection.merge(itemSelection, selModel.Select)
        selModel.select(selModelSelection, selModel.SelectCurrent | selModel.Rows)
        self.logger.debug("New Selected Rows: "+str([index.row() for index in selModelSelection.indexes()]))

    def selectNextSearchResult(self):
        if self.searchResults:
            self.searchResultsIndex += 1
            if self.searchResultsIndex <= len(self.searchResults)-1:
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])
            else:
                self.searchResultsIndex = 0
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])

    def selectPreviousSearchResult(self):
        if self.searchResults:
            self.searchResultsIndex -= 1
            if self.searchResultsIndex >= 0:
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])
            else:
                self.searchResultsIndex = len(self.searchResults)-1
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])

    def clearSearchResults(self):
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchString = None


class ÆMainListView(QListView):
    keyPressed = None
    keyModifier = None
    searchString = None
    searchResults = list()
    searchResultsIndex = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setStyleSheet("")
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setProperty("showDropIndicator", False)
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setIconSize(QSize(200, 200))
        self.setObjectName("listView")
        self.setFlow(QListView.TopToBottom)
        self.setViewMode(self.ViewMode.IconMode)

        self.setUniformItemSizes(True)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setFlow(self.Flow.LeftToRight)
        self.setSpacing(10)
        self.setWordWrap(True)
        self.setLayoutMode(self.LayoutMode.Batched)
        self.setMovement(self.Movement.Snap)
        self.setVerticalScrollMode(self.ScrollMode.ScrollPerItem)

        newStyle = '''

        '''
        self.setStyleSheet(newStyle)

    def setModel(self, model):
        super().setModel(model)
        try:
            model.layoutChanged.connect(self.modelLayoutChanged, Qt.UniqueConnection)
        except (RuntimeError, AttributeError):
            pass

    def modelLayoutChanged(self):
        self.clearSelection()
        if self.searchString:
            self.searchRefresh()

    def focusOutEvent(self, event):
        self.keyPressed = None
        super().focusOutEvent(event)

    def keyPressEvent(self, e):
        self.keyPressed = e.key()
        self.keyModifier = e.modifiers()
        # if int(e.modifiers()) == Qt.ControlModifier:
        if Qt.ControlModifier in e.modifiers():
            if e.key() in (Qt.Key_Equal, Qt.Key_Plus):
                iconSize = self.iconSize()
                iconSize.setHeight(iconSize.height()+24)
                iconSize.setWidth(iconSize.width()+24)
                self.setIconSize(iconSize)
                self.logger.debug("Key Combo: Zoom In")
            if e.key() == Qt.Key_Minus:
                iconSize = self.iconSize()
                iconSize.setHeight(iconSize.height()-24)
                iconSize.setWidth(iconSize.width()-24)
                self.setIconSize(iconSize)
                self.logger.debug("Key Combo: Zoom Out")
        super().keyPressEvent(e)

    def wheelEvent(self, event):
        if self.keyModifier == Qt.ControlModifier:
            scaleAmount = event.angleDelta().y()/5
            # scaleAmount = event.delta()/5
            iconSize = self.iconSize()
            iconSize.setHeight(iconSize.height()+scaleAmount)
            iconSize.setWidth(iconSize.width()+scaleAmount)
            # iconSize.scale(scaleAmount, scaleAmount, Qt.KeepAspectRatio)
            self.setIconSize(iconSize)
        super().wheelEvent(event)

    def keyReleaseEvent(self, keyEvent):
        self.keyPressed = None
        self.keyModifier = None
        super().keyReleaseEvent(keyEvent)

    def mouseMoveEvent(self, event):
        #if not self.keyPressed in (Qt.Key_Shift, Qt.Key_Control):
        #    self.setSelectionMode(QAbstractItemView.SingleSelection)
        super().mouseMoveEvent(event)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def search(self, searchString):
        searchString = searchString.lower()
        self.searchString = æscape(searchString)
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchResultsIndex = 0
        model = self.model()

        if model.tableType in Æ.ItemTableTypes:
            for rowIndex, rowItem in enumerate(model.rows):
                rowName = rowItem[2].lower()
                if searchString in rowName:
                    self.searchResults.append(model.index(rowIndex, 0))
            if self.searchResults:
                self.setCurrentIndex(self.searchResults[0])
        elif model.tableType in Æ.CategoryTableTypes:
            for rowIndex, childItem in enumerate(model.rootItem.childItems):
                childIndex = model.index(rowIndex, 0, QModelIndex())
                rowName = childItem.data(1).lower()
                if childItem.childCount() > 0:
                    self.recursiveCategorySearch(childItem, childIndex)
                elif searchString in rowName:
                    self.searchResults.append(childIndex)
            if self.searchResults:
                self.setCurrentIndex(self.searchResults[0])

    def recursiveCategorySearch(self, item, currentIndex):
        itemName = item.data(1).lower()
        if self.searchString in itemName:
            self.searchResults.append(currentIndex)
        if item.childCount() > 0:
            for rowIndex, childItem in enumerate(item.childItems):
                childIndex = self.model().index(rowIndex, 0, currentIndex)
                self.recursiveCategorySearch(childItem, childIndex)

    def searchRefresh(self):
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchResultsIndex = 0
        model = self.model()
        if model.tableType in Æ.ItemTableTypes:
            for rowIndex, rowItem in enumerate(model.rows):
                rowName = rowItem[2].lower()
                if self.searchString in rowName:
                    self.searchResults.append(model.index(rowIndex, 0, QModelIndex()))
        elif model.tableType in Æ.CategoryTableTypes:
            for rowIndex, childItem in enumerate(model.rootItem.childItems):
                childIndex = model.index(rowIndex, 0, QModelIndex())
                rowName = childItem.data(1).lower()
                if childItem.childCount() > 0:
                    self.recursiveCategorySearch(childItem, childIndex)
                elif self.searchString in rowName:
                    self.searchResults.append(childIndex)

    def selectAllSearchResults(self):
        selModel = self.selectionModel()
        selModelSelection = selModel.selection()
        selModel.clear()

        for index in self.searchResults:
            modelLeftIndex = index
            itemSelection = QItemSelection(modelLeftIndex, modelLeftIndex)
            selModelSelection.merge(itemSelection, selModel.Select)
        selModel.select(selModelSelection, selModel.SelectCurrent | selModel.Rows)
        self.logger.debug("New Selected Rows: "+str([index.row() for index in selModelSelection.indexes()]))

    def selectNextSearchResult(self):
        if self.searchResults:
            self.searchResultsIndex += 1
            if self.searchResultsIndex <= len(self.searchResults)-1:
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])
            else:
                self.searchResultsIndex = 0
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])

    def selectPreviousSearchResult(self):
        if self.searchResults:
            self.searchResultsIndex -= 1
            if self.searchResultsIndex >= 0:
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])
            else:
                self.searchResultsIndex = len(self.searchResults)-1
                self.setCurrentIndex(self.searchResults[self.searchResultsIndex])

    def clearSearchResults(self):
        try:
            self.searchResults.clear()
        except AttributeError:
            del self.searchResults[:]
        self.searchString = None


class ÆCompleterLineEdit(QLineEdit):
    textChangedSig = Signal(list, str)

    def __init__(self, *args):
        QLineEdit.__init__(self, *args)
        self.textChanged.connect(self.text_changed)

    def text_changed(self, text):
        all_text = str(text)
        text = all_text[:self.cursorPosition()]
        prefix = text.split(',')[-1].strip()

        text_tags = []
        for t in all_text.split(','):
            t1 = str(t).strip()
            if t1 != '':
                text_tags.append(t)
        text_tags = list(set(text_tags))

        self.textChangedSig.emit(text_tags, prefix)

    def completeText(self, text):
        cursor_pos = self.cursorPosition()
        before_text = str(self.text())[:cursor_pos]
        after_text = str(self.text())[cursor_pos:]
        prefix_len = len(before_text.split(',')[-1].strip())
        self.setText('%s%s, %s' % (before_text[:cursor_pos - prefix_len], text,
            after_text))
        self.setCursorPosition(cursor_pos - prefix_len + len(text) + 2)


class ÆTagsCompleter(QCompleter):
    def __init__(self, parent, all_tags):
        QCompleter.__init__(self, all_tags, parent)
        self.all_tags = set(all_tags)

    def update(self, text_tags, completion_prefix):
        tags = list(self.all_tags.difference(text_tags))
        model = QStringListModel(tags, self)
        self.setModel(model)

        self.setCompletionPrefix(completion_prefix)
        if completion_prefix.strip() != '':
            self.complete()