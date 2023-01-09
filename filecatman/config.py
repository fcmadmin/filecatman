import os
from urllib.parse import unquote, quote
from PySide6.QtCore import QSettings
from filecatman.log import logger
from filecatman.core import const
from filecatman.core.functions import convToBool


class Config():
    defaultCopypastaTemplates = {
        'Default': ('{0}', '{0}', '{0}', '{0}'),
        'html': ('<b>{0}</b><br/>', '<a href="{0}">{0}</a><br/>', '<i>{0}</i><br/>', '{0}<br/>')
    }

    def __init__(self):
        if const.PORTABLEMODE:
            configPath = os.path.splitext(os.path.basename(QSettings().fileName()))[0]+".conf"
            self.settings = QSettings(configPath, QSettings.IniFormat)
        else:
            self.settings = QSettings()
        self.__config = dict()

        self.readConfig()

    def __contains__(self, item):
        return item in self.__config

    def __getitem__(self, key):
        return self.__config[key]

    def get(self, key, default=None):
        if key in self.__config:
            return True
        elif default:
            return default
        else:
            return False

    def __setitem__(self, key, value):
        return self.setItem(key, value)

    def setItem(self, key, value):
        logger.debug("Setting '{0}' to {1} of {2}".format(key, value, type(value)))
        self.__config[key] = value

    def readConfig(self):
        self.__config["iconTheme"] = str(self.settings.value("iconTheme", "Farm Fresh"))
        self.__config["customSystemTheme"] = str(self.settings.value("customSystemTheme", ""))
        self.__config["autoloadDatabase"] = convToBool(self.settings.value("autoloadDatabase", False), False)
        self.__config["style"] = str(self.settings.value("style", "System Default"))
        self.__config["standardPalette"] = convToBool(self.settings.value("standardPalette", True), True)

        self.__config['mainWindow'] = dict()
        self.settings.beginGroup('mainWindow')

        self.__config["mainWindow"]['toggleMainToolbar'] = convToBool(
            self.settings.value("toggleMainToolbar", True), True)
        self.__config["mainWindow"]['toggleSearchToolbar'] = convToBool(
            self.settings.value("toggleSearchToolbar", True), True)
        self.__config["mainWindow"]['toggleBulkActionsToolbar'] = convToBool(
            self.settings.value("toggleBulkActionsToolbar", True), True)
        self.__config["mainWindow"]['toggleSidebar'] = convToBool(
            self.settings.value("toggleSidebar", True), True)
        self.__config["mainWindow"]['toggleStatusbar'] = convToBool(
            self.settings.value("toggleStatusbar", True), True)
        self.__config["mainWindow"]['toggleSelectionDetails'] = convToBool(
            self.settings.value("toggleSelectionDetails", True), True)
        self.settings.endGroup()

        if 'db' in self.settings.childGroups():
            self.__config['db'] = dict()
            self.settings.beginGroup('db')
            for key in self.settings.childKeys():
                self.__config['db'][key] = self.settings.value(key)
            self.settings.endGroup()

        if 'copypasta' in self.settings.childGroups():
            self.__config['copypasta'] = dict()
            self.settings.beginGroup('copypasta')
            self.__config["copypasta"]['enabledName'] = convToBool(
                self.settings.value("enabledName", True), True)
            self.__config["copypasta"]['enabledSource'] = convToBool(
                self.settings.value("enabledSource", True), True)
            self.__config["copypasta"]['enabledDescription'] = convToBool(
                self.settings.value("enabledDescription", True), True)
            self.__config["copypasta"]['keepFileExtension'] = convToBool(
                self.settings.value("keepFileExtension", False), False)
            self.__config["copypasta"]['formatEachLineOfDesc'] = convToBool(
                self.settings.value("formatEachLineOfDesc", False), False)
            self.__config["copypasta"]['formatName'] = self.settings.value("formatName", '{0}')
            self.__config["copypasta"]['formatSource'] = self.settings.value("formatSource", '{0}')
            self.__config["copypasta"]['formatDescription'] = self.settings.value("formatDescription", '{0}')
            self.__config["copypasta"]['outerFormatting'] = self.settings.value("outerFormatting", '{0}')
            self.settings.endGroup()
        else:
            self.createDefaultCopypasta()

        if 'copypastaTemplates' in self.settings.childGroups():
            self.__config['copypastaTemplates'] = dict()
            self.settings.beginGroup('copypastaTemplates')
            for key in self.settings.childKeys():
                try:
                    value = self.settings.value(key)
                    tem = value.split(', ')
                    self.__config['copypastaTemplates'][key] = (
                        unquote(tem[0]), unquote(tem[1]), unquote(tem[2]), unquote(tem[3]))
                except IndexError:
                    logger.warning("Configuration file contained invalid Copypasta Template settings.")
            self.settings.endGroup()
        else:
            self.createDefaultCopypastaTemplates()

        if 'openWith' in self.settings.childGroups():
            self.__config['openWith'] = dict()
            self.settings.beginGroup('openWith')
            for ext in self.settings.childKeys():
                try:
                    value = self.settings.value(ext)
                    commandsList = value.split(', ')
                    self.__config['openWith'][ext] = dict()
                    for command in commandsList:
                        if command != "":
                            appPath = unquote(command)
                            appName = appPath
                            # appName = appPath.split("/")[-1]
                            self.__config['openWith'][ext][appName] = appPath
                except IndexError:
                    logger.warning("Configuration file contained invalid Open With settings.")
            self.settings.endGroup()
        else:
            self.__config['openWith'] = dict()

    def writeConfig(self):
        self.settings.setValue("iconTheme", str(self.__config['iconTheme']))
        self.settings.setValue("customSystemTheme", str(self.__config['customSystemTheme']))
        self.settings.setValue("autoloadDatabase", str(self.__config['autoloadDatabase']))
        self.settings.setValue("style", str(self.__config['style']))
        self.settings.setValue("standardPalette", str(self.__config['standardPalette']))

        self.settings.beginGroup('mainWindow')
        self.settings.setValue('toggleMainToolbar', self.__config['mainWindow']['toggleMainToolbar'])
        self.settings.setValue('toggleSearchToolbar', self.__config['mainWindow']['toggleSearchToolbar'])
        self.settings.setValue('toggleBulkActionsToolbar', self.__config['mainWindow']['toggleBulkActionsToolbar'])
        self.settings.setValue('toggleSidebar', self.__config['mainWindow']['toggleSidebar'])
        self.settings.setValue('toggleStatusbar', self.__config['mainWindow']['toggleStatusbar'])
        self.settings.setValue('toggleSelectionDetails', self.__config['mainWindow']['toggleSelectionDetails'])
        self.settings.endGroup()

        if self.__config['autoloadDatabase'] and self.__config['db'].get('type'):
            self.settings.beginGroup("db")
            if self.__config['db']['type'] == 'mysql':
                self.settings.setValue('host', str(self.__config['db']['host']))
                self.settings.setValue('port', str(self.__config['db']['port']))
                self.settings.setValue('user', str(self.__config['db']['user']))
                self.settings.setValue('passwd', str(self.__config['db']['passwd']))
                self.settings.setValue('db', str(self.__config['db']['db']))
                self.settings.setValue('type', str(self.__config['db']['type']))
            elif self.__config['db']['type'] == 'sqlite':
                self.settings.setValue('db', str(self.__config['db']['db']))
                self.settings.setValue('type', str(self.__config['db']['type']))
            self.settings.endGroup()

        self.settings.beginGroup("copypasta")
        self.settings.setValue('enabledName', self.__config['copypasta']['enabledName'])
        self.settings.setValue('enabledSource', self.__config['copypasta']['enabledSource'])
        self.settings.setValue('enabledDescription', self.__config['copypasta']['enabledDescription'])
        self.settings.setValue('keepFileExtension', self.__config['copypasta']['keepFileExtension'])
        self.settings.setValue('formatEachLineOfDesc', self.__config['copypasta']['formatEachLineOfDesc'])
        self.settings.setValue('formatName', self.__config['copypasta']['formatName'])
        self.settings.setValue('formatSource', self.__config['copypasta']['formatSource'])
        self.settings.setValue('formatDescription', self.__config['copypasta']['formatDescription'])
        self.settings.setValue('outerFormatting', self.__config['copypasta']['outerFormatting'])
        self.settings.endGroup()

        self.settings.beginGroup("copypastaTemplates")
        for name, template in self.__config['copypastaTemplates'].items():
            template = [quote(item) for item in template]
            self.settings.setValue(name, ", ".join(template))
        self.settings.endGroup()

        self.settings.beginGroup("openWith")
        for ext, commandList in self.__config['openWith'].items():
            commandList = [quote(item) for item in commandList]
            self.settings.setValue(ext, ", ".join(commandList))
        self.settings.endGroup()

        logger.debug('Configuration file written.')

    def createDefaultCopypasta(self):
        self.__config['copypasta'] = dict(
            enabledName=True,
            enabledSource=True,
            enabledDescription=True,
            keepFileExtension=False,
            formatEachLineOfDesc=False,
            formatName="{0}",
            formatSource="{0}",
            formatDescription="{0}",
            outerFormatting="{0}"
        )
        logger.debug("Default copypasta created.")

    def createDefaultCopypastaTemplates(self):
        self.__config['copypastaTemplates'] = dict()
        for name, template in self.defaultCopypastaTemplates.items():
            self.__config['copypastaTemplates'][name] = template
        logger.debug("Default copypasta templates created.")
