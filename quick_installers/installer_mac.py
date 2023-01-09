#!/usr/bin/env python3

###################################################
## Filecatman XML Symbolic Links Quick Installer ##
###################################################
# Reads data from a Filecatman XML (.xml) file and creates a symbolic links hierarchy in the current directory.

import sys
import os
import logging
import datetime
import xml.etree.ElementTree as ElementTree


class Installer():
    xmlFile = None
    taxonomies, itemTypes, newCategories = dict(), dict(), dict()
    newItems = list()
    totalItemsCount, itemsLinkedCount = 0, 0
    linksCreatedCount, linksOverwrittenCount, linksAlreadyExistCount, errorCount = 0, 0, 0, 0
    elapsedTime = None
    logCreated, logOverwritten, logAlreadyExists, logErrors = None, None, None, None
    overwriteLinks = False
    cwd = None

    ### User Configurable Settings ###
    dataDirName = "Files"
    relativeLinks = True
    ##################################

    def __init__(self):
        print("Filecatman XML Symbolic Links Quick Installer\n")

        if not self.osxCheck():
            input("This is the installer for Mac.")
            sys.exit()

        self.cwd = os.getcwd()+'/'
        for file in os.listdir(self.cwd):
            filePath = self.cwd+file
            if os.path.isfile(filePath):
                fileExtension = os.path.splitext(file)[1][1:].lower().strip()
                if fileExtension == 'xml':
                    self.xmlFile = file
                    break
        if not self.xmlFile:
            input('No Filecatman XML (.xml) file is in the current directory.')
            sys.exit()

        if os.path.isdir(self.cwd+self.dataDirName):
            self.absoluteDataDir = self.cwd+self.dataDirName+"/"
        else:
            input('The data folder ‘{0}’ is missing from the current directory.'.format(self.dataDirName))
            sys.exit()

        response = None
        while response not in ('y', 'yes'):
            response = input(
                "This script will load the ‘{0}’ Filecatman XML file, and create a symbolic links hierarchy "
                "representing the categorized data. Do you want to continue? [Y/N] "
                .format(self.xmlFile)
            ).lower().strip()
            if response in ('n', 'no'):
                sys.exit(0)
            elif response not in ('y', 'yes'):
                print("Wrong character entered. Try again.")

        response = None
        while response not in ('y', 'yes', 'n', 'no'):
            response = input("Do you want to overwrite existing links? [Y/N] ").lower().strip()
            if response in ('n', 'no'):
                self.overwriteLinks = False
            elif response in ('y', 'yes'):
                self.overwriteLinks = True
            else:
                print("Wrong character entered. Try again.")

        self.initializeLoggers()
        if self.iterparseXML(self.xmlFile):
            self.totalItemsCount = len(self.newItems)
            if self.runLinkCreation():
                print("Symbolic links hierarchy successfully created.\n")
                print("Elapsed Time: "+str(self.elapsedTime)+" Seconds")
                if self.linksCreatedCount > 0:
                    print("Links Created: "+str(self.linksCreatedCount))
                if self.linksAlreadyExistCount > 0:
                    print("Links Already Exist: "+str(self.linksAlreadyExistCount))
                if self.linksOverwrittenCount > 0:
                    print("Links Overwritten: "+str(self.linksOverwrittenCount))
                totalLinks = self.linksCreatedCount+self.linksAlreadyExistCount+self.linksOverwrittenCount
                if totalLinks > 0:
                    print("Total Links Processed: "+str(totalLinks))
            else:
                print("Symbolic links hierarchy creation failed.\n")
        else:
            print("Symbolic links hierarchy creation failed.\n")
        if self.errorCount > 0:
            print("Errors: "+str(self.errorCount))
            print("See ‘LinkErrors.log’ for more details.")

        input()

    def windowsCheck(self):
        return sys.platform.startswith('win')

    def osxCheck(self):
        return sys.platform.startswith('darwin')

    def initializeLoggers(self):
        self.logCreated = logging.getLogger('Created')
        self.logCreated.setLevel(logging.INFO)
        logCreatedFH = logging.FileHandler('LinksCreated.log', 'w')
        logCreatedFH.setFormatter(
            logging.Formatter('%(asctime)-s [%(name)-s]: %(message)s', datefmt='%m-%d %H:%M:%S'))
        logCreatedFH.setLevel(logging.INFO)
        self.logCreated.addHandler(logCreatedFH)

        self.logAlreadyExists = logging.getLogger('Already Exists')
        self.logAlreadyExists.setLevel(logging.INFO)
        logAlreadyExistsFH = logging.FileHandler('LinksAlreadyExist.log', 'w')
        logAlreadyExistsFH.setFormatter(
            logging.Formatter('%(asctime)-s [%(name)-s]: %(message)s', datefmt='%m-%d %H:%M:%S'))
        logAlreadyExistsFH.setLevel(logging.INFO)
        self.logAlreadyExists.addHandler(logAlreadyExistsFH)

        self.logOverwritten = logging.getLogger('Overwritten')
        self.logOverwritten.setLevel(logging.INFO)
        logOverwrittenFH = logging.FileHandler('LinksOverwritten.log', 'w')
        logOverwrittenFH.setFormatter(
            logging.Formatter('%(asctime)-s [%(name)-s]: %(message)s', datefmt='%m-%d %H:%M:%S'))
        logOverwrittenFH.setLevel(logging.INFO)
        self.logOverwritten.addHandler(logOverwrittenFH)

        self.logErrors = logging.getLogger('Error')
        self.logErrors.setLevel(logging.ERROR)
        logErrorsFH = logging.FileHandler('LinkErrors.log', 'w')
        logErrorsFH.setFormatter(
            logging.Formatter('%(asctime)-s [%(name)-s]: %(message)s', datefmt='%m-%d %H:%M:%S'))
        logErrorsFH.setLevel(logging.ERROR)
        self.logErrors.addHandler(logErrorsFH)

    def iterparseXML(self, file):
        context = ElementTree.iterparse(file, events=('start', 'end'))
        context = iter(context)
        dummy, root = context.__next__()

        for event, elem in context:
            try:
                if event == 'end' and elem.tag == 'itemType':
                    extensions = list()
                    specialType = None
                    tableName = elem.find('tableName').text
                    dirName = elem.find('dirName').text
                    for ext in elem.iter('extension'):
                        extensions.append(ext.text)
                    if len(extensions) is 0:
                        specialType = "weblink"
                    if dirName and tableName:
                        self.itemTypes[tableName] = dict(name=dirName, extensions=extensions, type=specialType)
                    else:
                        raise Exception("Item Type has missing fields.")
                    elem.clear()
                elif event == 'end' and elem.tag == 'taxonomy':
                    tableName = elem.find('tableName').text
                    dirName = elem.find('dirName').text
                    if dirName and tableName:
                        self.taxonomies[tableName] = dirName
                    else:
                        raise Exception("Taxonomy has missing fields.")
                    elem.clear()
                elif event == 'end' and elem.tag == 'item':
                    self.newItems.append(dict(
                        name=elem.find('title').text,
                        id=elem.find('item_id').text,
                        type=elem.find('type_id').text,
                        source=elem.find('item_source').text,
                        time=elem.find('item_time').text,
                        description=elem.find('item_description').text,
                        relations=[c.attrib for c in elem.iter('relation')]
                    ))
                    elem.clear()
                elif event == 'end' and elem.tag == 'category':
                    self.newCategories[elem.find('category_tax').text + elem.find('category_slug').text] = dict(
                        id=elem.find('category_id').text,
                        slug=elem.find('category_slug').text,
                        name=elem.find('category_name').text,
                        description=elem.find('category_description').text,
                        taxonomy=elem.find('category_tax').text,
                        parent=elem.find('category_parent').text
                    )
                    elem.clear()
                root.clear()
            except BaseException as e:
                self.logErrors.error(
                    "Error parsing XML: {0}. Some markup tags are probably invalid or missing.".format(str(e)))
                self.errorCount += 1
        return True

    def runLinkCreation(self):
        print('')
        startTime = datetime.datetime.now()
        for newItem in self.newItems:
            try:
                itemName = newItem['name']
                itemType = newItem['type']
                itemSource = newItem['source']
                itemTime = newItem['time']
                if None in (itemName, itemType):
                    raise Exception("Item has missing fields.")
                if not self.itemTypes.get(itemType):
                    raise Exception("Item Type details are missing for '{0}'.".format(itemType))
                else:
                    typeDir = self.itemTypes[itemType]['name']

                if not self.itemTypes[itemType]['type'] == 'weblink':
                    filePath = self.absoluteDataDir+typeDir+'/'+itemName
                    if not os.path.exists(filePath):
                        errorMessage = "File Error: File '{}' not found.".format(itemName)
                        self.logErrors.error(errorMessage)
                        self.errorCount += 1
                        continue
                else:
                    linkPath = self.cwd+'Media/'+typeDir+'/'+itemName+'.url'
                    if not self.createDesktopFile(linkPath, itemName, itemSource):
                        return False
                try:
                    dateParts = itemTime.split(" ")[0].split("-")
                    year = int(dateParts[0])
                    month = int(dateParts[1])
                    day = int(dateParts[2])
                    if not 0 in (year, month, day):
                        date = datetime.date(year, month, day)
                        timeYear = date.strftime("%Y")
                        timeMonth = date.strftime("%B")
                        if self.itemTypes[itemType]['type'] == 'weblink':
                            timeLink = self.cwd+'Time/'+timeYear+'/'+timeMonth+'/'\
                                + typeDir+'/'+itemName+'.url'
                            if not self.createDesktopFile(timeLink, itemName, itemSource):
                                return False
                        else:
                            timeLink = self.cwd+'Time/'+timeYear+'/'+timeMonth+'/'\
                                + typeDir+'/'+itemName
                            filePath = self.getFilePath(4, typeDir, itemName)
                            if not self.createLink(filePath, timeLink):
                                return False
                except (ValueError, IndexError) as e:
                    self.logErrors.error("Error creating time link for file '{0}': {1}".format(itemName, str(e)))
                    self.errorCount += 1

                for relation in newItem['relations']:
                    try:
                        termSlug = relation['slug']
                        termTaxonomy = relation['taxonomy']
                        if None in (termSlug, termTaxonomy):
                            raise Exception("Relation has missing fields.")
                        if not self.taxonomies.get(termTaxonomy):
                            raise Exception("Taxonomy details are missing for '{0}'.".format(termTaxonomy))
                        taxonomyDir = self.taxonomies[termTaxonomy]
                        termName = self.newCategories[termTaxonomy+termSlug]['name']
                        termParent = self.newCategories[termTaxonomy+termSlug]['parent']
                        if not termName:
                            raise Exception("Category has missing fields.")

                        if self.itemTypes[itemType]['type'] == 'weblink':
                            if termParent in ("", None, 0):
                                linkPath = self.cwd+taxonomyDir+'/'+termName+'/'+typeDir+'/'+itemName+".url"
                            else:
                                termParentRoot, termParentsJoined, parentLevels = self.returnTermParents(
                                    termParent, termTaxonomy)
                                linkPath = self.cwd+taxonomyDir+'/'+termParentRoot+'/'+typeDir+'/'\
                                    + termParentsJoined+termName+'/'+itemName+".url"

                            if not self.createDesktopFile(linkPath, itemName, itemSource):
                                return False
                        else:
                            if termParent in ("", None, 0):
                                levels = 3
                                linkPath = self.cwd+taxonomyDir+'/'+termName+'/'+typeDir+'/'+itemName
                            else:
                                termParentRoot, termParentsJoined, parentLevels = self.returnTermParents(
                                    termParent, termTaxonomy)
                                levels = 3+parentLevels
                                linkPath = self.cwd+taxonomyDir+'/'+termParentRoot+'/'+typeDir+'/'\
                                    + termParentsJoined+termName+'/'+itemName
                            filePath = self.getFilePath(levels, typeDir, itemName)
                            if not self.createLink(filePath, linkPath):
                                return False
                    except BaseException as e:
                        self.logErrors.error("Error creating link for file '{0}': {1}"
                                             "".format(itemName, str(e)))
                        self.errorCount += 1
                self.itemsLinkedCount += 1
                self.updateProgress()
            except BaseException as e:
                self.logErrors.error("Error creating links: {0}".format(str(e)))
                self.errorCount += 1

        endTime = datetime.datetime.now()
        self.elapsedTime = round((endTime - startTime).total_seconds(), 3)
        print('')
        return True

    def getFilePath(self, levels, typeDir, itemName):
        if self.relativeLinks:
            return ("../"*levels)+self.dataDirName+'/'+typeDir+'/'+itemName
        else:
            return self.absoluteDataDir+typeDir+'/'+itemName

    def getWorkingPath(self, levels):
        if self.relativeLinks:
            return "../"*levels
        else:
            return self.cwd

    def returnTermParents(self, termParent, termTaxonomy):
        termParentNames = self.recursiveParentSearch(termParent, termTaxonomy)
        if len(termParentNames) > 1:
            termParentsJoined = '/'.join(termParentNames[1:])+'/'
        else:
            termParentsJoined = ''
        termParentRoot = termParentNames[0]
        return termParentRoot, termParentsJoined, len(termParentNames)

    def recursiveParentSearch(self, termParent, termTaxonomy):
        if self.newCategories.get(termTaxonomy+termParent):
            parentName = self.newCategories[termTaxonomy+termParent]['name']
            parentParent = self.newCategories[termTaxonomy+termParent]['parent']
            if parentParent in ("", None, 0, termParent):
                return [parentName]
            else:
                termParentNames = self.recursiveParentSearch(parentParent, termTaxonomy)
                termParentNames.append(parentName)
                return termParentNames
        else:
            errorMesssage = "Parent Searching Error: Term not found."
            self.logErrors.error(errorMesssage)
            self.errorCount += 1

    def createDesktopFile(self, linkPath, itemName, itemSource):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir):
                os.makedirs(linkDir)
            if os.path.exists(linkPath):
                if self.overwriteLinks is True:
                    file = open(linkPath, "w")
                    if file.closed:
                        errorMessage = "Desktop File Error: Unable to write desktop file."
                        self.logErrors.error(errorMessage)
                        self.errorCount += 1
                        return False
                    file.write('[InternetShortcut]\n')
                    file.write('URL=%s\n' % itemSource)
                    file.write('IconIndex=0')
                    file.close()
                    os.chmod(linkPath, 0o755)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(itemSource, linkPath)
                    self.logOverwritten.info(creationMessage)
                    self.linksOverwrittenCount += 1
                    return True
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(itemSource, linkPath)
                    self.logAlreadyExists.info(creationMessage)
                    self.linksAlreadyExistCount += 1
                    return True
            else:
                file = open(linkPath, "w")
                if file.closed:
                    errorMessage = "Desktop File Error: Unable to write desktop file."
                    self.logErrors.error(errorMessage)
                    self.errorCount += 1
                    return False
                file.write('[InternetShortcut]\n')
                file.write('URL=%s\n' % itemSource)
                file.write('IconIndex=0')
                file.close()
                os.chmod(linkPath, 0o755)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(itemSource, linkPath)
                self.logCreated.info(creationMessage)
                self.linksCreatedCount += 1
                return True
        except BaseException as e:
            self.logErrors.error("Error: {}".format(str(e)))
            self.errorCount += 1
            return False

    def createLink(self, filePath, linkPath):
        try:
            linkDir = os.path.dirname(linkPath)
            if not os.path.exists(linkDir):
                os.makedirs(linkDir)
            if os.path.lexists(linkPath):
                if self.overwriteLinks is True:
                    os.unlink(linkPath)
                    os.symlink(filePath, linkPath)
                    creationMessage = "The link to ‘{}’ at ‘{}’ has been overwritten.".format(filePath, linkPath)
                    self.logOverwritten.info(creationMessage)
                    self.linksOverwrittenCount += 1
                    return True
                else:
                    creationMessage = "The link to ‘{}’ at ‘{}’ already exists.".format(filePath, linkPath)
                    self.logAlreadyExists.info(creationMessage)
                    self.linksAlreadyExistCount += 1
                    return True
            else:
                os.symlink(filePath, linkPath)
                creationMessage = "The link to ‘{}’ at ‘{}’ has been created.".format(filePath, linkPath)
                self.logCreated.info(creationMessage)
                self.linksCreatedCount += 1
                return True
        except BaseException as e:
            self.logErrors.error("Error: {}".format(str(e)))
            self.errorCount += 1
            return False

    def updateProgress(self):
        progress = (self.itemsLinkedCount/self.totalItemsCount)
        barLength = 40
        status = ""
        if isinstance(progress, int):
            progress = float(progress)
        if not isinstance(progress, float):
            progress = 0
            status = "error: progress var must be float\r\n"
        if progress < 0:
            progress = 0
            status = "Halt...\r\n"
        if progress >= 1:
            progress = 1
            status = "Done...\r\n"
        block = int(round(barLength*progress))
        text = "\rProgress: [{0}] {1}% {2}".format("█"*block + "-"*(barLength-block), round(progress*100, 2), status)
        sys.stdout.write(text)
        sys.stdout.flush()

if __name__ == "__main__":
    Installer()
