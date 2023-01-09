import os
import shutil
import re
from urllib.parse import quote

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QFile, QIODevice
from PySide6.QtUiTools import QUiLoader

from filecatman.core.namespace import Æ
import requests


def getÆDirPath():
    import filecatman
    return os.path.dirname(filecatman.__file__)+"/"


def convToBool(boolStr, fallbackBool=False):
    if isinstance(boolStr, str):
        if boolStr.lower() == "true":
            return True
        elif boolStr.lower() == "false":
            return False
        else:
            return fallbackBool
    elif isinstance(boolStr, bool):
        return boolStr
    elif isinstance(boolStr, int):
        return bool(boolStr)
    else:
        return fallbackBool


def loadUI(filename):
    filename = getÆDirPath()+filename
    file = QFile(filename)
    file.open(QFile.ReadOnly)
    ui = QUiLoader().load(file)
    file.close()
    file.deleteLater()
    return ui


def formatBytes(num):
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if -1024.0 < num < 1024.0:
            return "%3.0f %s" % (num, x)
        num /= 1024.0
    return "%3.0f %s" % (num, 'TB')


def getDataFilePath(dataDir, dataType, fileName=''):
    if os.name == "nt": return os.path.join(dataDir, dataType, fileName).replace("/","\\")
    return os.path.join(dataDir, dataType, fileName)


def warningMsgBox(parent, message, title="Error"):
    if not isinstance(message, str):
        message = str(message)
    if parent:
        parent.logger.error("{}: {}".format(title, message))
    else:
        from filecatman.log import logger
        logger.error("{}: {}".format(title, message))
    msgBox = QMessageBox(parent)
    msgBox.setIcon(QMessageBox.Warning)
    msgBox.setWindowTitle(title)
    msgBox.setText("{}: {}".format(title, message))
    msgBox.exec_()
    msgBox.deleteLater()


def uploadFile(parent, fileSource, fileDestination, fileType=None):
    try:
        baseFilename = os.path.basename(fileSource)
        fileName = os.path.splitext(baseFilename)[0]

        if fileType in parent.config['itemTypes'].nounNames(Æ.IsWebpages):
                destDir = os.path.dirname(fileDestination)
                if not os.path.exists(destDir):
                    os.makedirs(destDir)
                sourceDir = os.path.dirname(fileSource)

                folderSource = sourceDir+"/"+fileName+"_files"
                if os.path.exists(folderSource):
                    folderDestination = destDir+"/"+fileName+"_files"
                    if os.path.exists(folderDestination):
                        shutil.rmtree(folderDestination)
                    shutil.copytree(folderSource, folderDestination)

                shutil.copyfile(fileSource, fileDestination)
        else:
            destDir = os.path.dirname(fileDestination)
            if not os.path.exists(destDir):
                os.makedirs(destDir)
            shutil.copyfile(fileSource, fileDestination)
        if fileType:
            for illegal in ("'", '"', '`', '$'):
                if illegal in baseFilename:
                    escapeFile(parent, baseFilename, fileType)
                    break
        return True
    except BaseException as e:
        warningMsgBox(parent, e, "Error Uploading File")
        return False


def downloadFile(parent, fileSource, fileDestination, fileType=None):
    try:
        baseFilename = os.path.basename(fileSource.split('/')[-1])

        destDir = os.path.dirname(fileDestination)
        if not os.path.exists(destDir):
            os.makedirs(destDir)

        r = requests.get(fileSource)
        with open(fileDestination, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)

        if fileType:
            for illegal in ("'", '"', '`', '$'):
                if illegal in baseFilename:
                    escapeFile(parent, baseFilename, fileType)
                    break
        return True
    except BaseException as e:
        warningMsgBox(parent, e, "Error Downloading File from Internet.")
        return False


def deleteFile(parent, filePath, folderPath=None):
    try:
        if folderPath and os.path.exists(folderPath):
            shutil.rmtree(folderPath)
        os.remove(filePath)
        parent.logger.info("{} deleted.".format(filePath))
        return True
    except BaseException as e:
        warningMsgBox(parent, e, title="Error Deleting File")
        return False


def escapeFile(parent, baseFileName, fileType):
    try:
        dataDir = parent.config['options']['defaultDataDir']
        oldFilePath = getDataFilePath(
            dataDir, parent.config['itemTypes'].dirFromNoun(fileType), baseFileName)
        newFilePath = getDataFilePath(
            dataDir, parent.config['itemTypes'].dirFromNoun(fileType), æscape(baseFileName))

        if fileType in parent.config['itemTypes'].nounNames(Æ.IsWebpages):
            fileName = os.path.splitext(baseFileName)[0]
            oldFolderName = fileName+'_files'
            newFolderName = æscape(fileName)+'_files'

            oldFolderPath = getDataFilePath(
                dataDir, parent.config['itemTypes'].dirFromNoun(fileType), oldFolderName)
            newFolderPath = getDataFilePath(
                dataDir, parent.config['itemTypes'].dirFromNoun(fileType), newFolderName)
            if os.path.exists(oldFolderPath):
                os.rename(oldFolderPath, newFolderPath)
                file = QFile(oldFilePath)
                if file.open(QIODevice.ReadWrite):
                    fileData = file.readAll()
                    oldFolderNameQuoted = quote(oldFolderName)
                    newFolderNameQuoted = quote(newFolderName)
                    fileData.replace(oldFolderName, newFolderNameQuoted)
                    fileData.replace(oldFolderNameQuoted, newFolderNameQuoted)
                    file.resize(0)
                    file.seek(0)
                    file.write(fileData)
                    file.close()
                    file.deleteLater()

        os.rename(oldFilePath, newFilePath)
    except BaseException as e:
        warningMsgBox(parent, e, title="Error Renaming File")
        return False


def æscape(string, chars=("'", '"', '`', '$'), replacement=""):
    string = re.sub("[{}]".format(''.join(chars)), replacement, string)
    return string


def renameFolder(parent, filePath):
    try:
        os.remove(filePath)
        parent.logger.info("{} deleted.".format(filePath))
        return True
    except BaseException as e:
        warningMsgBox(parent, e, title="Error Deleting File")
        return False