'###################################################
'## Filecatman XML Symbolic Links Quick Installer ##
'###################################################
'# Reads data from a Filecatman XML (.xml) file and creates a symbolic links hierarchy in the current directory.

Const ForReading = 1, ForWriting = 2, ForAppending = 8

Class InstallerClass
	private objFSO, WshShell
	private xmlFile, relativeLinks, overwriteLinks
	private logCreated, logOverwritten, logAlreadyExists, logErrors
	private cwd, absoluteDataDir
	private taxonomies, itemTypes, newCategories, newItems
	private totalItemsCount, itemsLinkedCount, linksCreatedCount, linksOverwrittenCount
	private linksAlreadyExistCount, errorCount, elapsedTime
	public dataDirName
	
	Private Sub Class_Initialize(  )
		'### User Configurable Settings ###
		dataDirName = "Files"
		'##################################
	
		Set objFSO = CreateObject("Scripting.FileSystemObject")
		Set WshShell = CreateObject("Wscript.shell")
		cwd = objFSO.GetAbsolutePathName(".")+"\"
		Set taxonomies = CreateObject("Scripting.Dictionary")
		Set itemTypes = CreateObject("Scripting.Dictionary")
		Set newCategories = CreateObject("Scripting.Dictionary")
		Set newItems = CreateObject("System.Collections.ArrayList")
		overwriteLinks = 0
		totalItemsCount = 0
		itemsLinkedCount = 0
		linksCreatedCount = 0
		linksOverwrittenCount = 0
		linksAlreadyExistCount = 0
		errorCount = 0
	End Sub
	
	Public Sub run()
		Dim objFolder, objFile
		Set objFolder = objFSO.GetFolder(cwd)
		For Each objFile in objFolder.files
			If (InStr(objFile.Name, ".") > 0) Then
				fileExtension = LCase(Mid(objFile.Name, InStrRev(objFile.Name, ".")))
				If (StrComp(fileExtension, ".xml", 1) = 0) Then
					xmlFile = objFile.Name
					Exit For
				End If
			End If
		Next
		
		If IsEmpty(xmlFile) Then
			Wscript.Echo "No Filecatman XML file is in the current directory."
			Wscript.Quit
		End If
		
		If objFSO.FolderExists(cwd+dataDirName) Then
			absoluteDataDir = cwd+dataDirName+"\"
		Else
			Wscript.Echo "The data folder '"+dataDirName+"' is missing from the current directory."
			Wscript.Quit
		End If
	
		message = "This script will load the '"+xmlFile+"' Filecatman XML file, and create a symbolic links hierarchy representing the categorized data. Do you want to continue?"
		response = MsgBox (message, 4 + 32, "Filecatman XML Symbolic Links Quick Installer")
		If response = 7 Then 
			Wscript.Quit
		End If
		
		response = MsgBox ("Do you want to overwrite existing links?", 4 + 32, "Filecatman XML Symbolic Links Quick Installer")
		If response = 6 Then 
			overwriteLinks = 1
		Else
			overwriteLinks = 0
		End If
		
		initializeLoggers()
		If (parseXML()) Then
			If (runLinkCreation()) Then
				finishMessage = "Symbolic links hierarchy successfully created."	
				finishMessage = finishMessage+vbCrLf+"Elapsed Time: "+elapsedTime+" Seconds"
				If linksCreatedCount > 0 Then
					finishMessage = finishMessage+vbCrLf+"Links Created: "+CStr(linksCreatedCount)
				End If
				If linksAlreadyExistCount > 0 Then
					finishMessage = finishMessage+vbCrLf+"Links Already Exist: "+CStr(linksAlreadyExistCount)
				End If
				If linksOverwrittenCount > 0 Then
					finishMessage = finishMessage+vbCrLf+"Links Overwritten: "+CStr(linksOverwrittenCount)
				End If
				totalLinks = linksCreatedCount+linksAlreadyExistCount+linksOverwrittenCount
				If totalLinks > 0 Then
					finishMessage = finishMessage+vbCrLf+"Total Links Processed: "+CStr(totalLinks)
				End If
			Else
				finishMessage = "Symbolic links hierarchy creation failed."
			End If
		Else
			finishMessage = "Symbolic links hierarchy creation failed."
		End If
		If errorCount > 0 Then
			finishMessage = finishMessage+vbCrLf+"Errors: "+CStr(errorCount)+vbCrLf+"See 'LinkErrors.log' for more details."
		End If
		MsgBox finishMessage, 0+64, "Filecatman XML Symbolic Links Quick Installer"
	End Sub
	
	Private Sub initializeLoggers()
		Set logCreated = objFSO.OpenTextFile("LinksCreated.log", ForWriting, True)
		Set logAlreadyExists = objFSO.OpenTextFile("LinksAlreadyExist.log", ForWriting, True)
		Set logOverwritten = objFSO.OpenTextFile("LinksOverwritten.log", ForWriting, True)
		Set logErrors = objFSO.OpenTextFile("LinkErrors.log", ForWriting, True)
	End Sub
	
	Private Function parseXML()
		Dim objXML, objNodeList
		Set objXML = CreateObject("MSXML2.DOMDocument")
		objXML.async = False
		objXML.Load(xmlFile)
		
		If 0 = objXML.ParseError Then		
			Dim tableName, dirName, extNodeList, specialType
			Dim extensions
			Set objNodeList = objXML.getElementsByTagName("itemType")
			For each element in objNodeList
				On Error Resume Next
				tableName = element.selectSingleNode("tableName").Text
				dirName = element.selectSingleNode("dirName").Text
				On Error Goto 0
				If Not (IsEmpty(tableName) Or IsEmpty(dirName)) Then
					Set extensions = CreateObject("System.Collections.ArrayList")
					Set extNodeList = element.selectNodes("extension")
					For each ext in extNodeList
						extensions.Add ext.Text
					Next
					If extensions.Count = 0 Then
						specialType = "weblink"
					Else
						specialType = "normal"
					End If
					Set extensions = Nothing
					itemTypes.Add tableName, Array(dirName, specialType)
				Else
					logErrors.writeline (Date() & ": " & Time() & " - Item Type has missing fields.")
					Err.Raise 500, "Filecatman Quick Installer", "Item Type has missing fields."
					errorCount = errorCount + 1
				End If
			Next
			
			Set objNodeList = objXML.getElementsByTagName("taxonomy")
			For each element in objNodeList
				On Error Resume Next
				tableName = element.selectSingleNode("tableName").Text
				dirName = element.selectSingleNode("dirName").Text
				On Error Goto 0
				If Not (IsEmpty(tableName) Or IsEmpty(dirName)) Then
					taxonomies.Add tableName, dirName
				Else
					logErrors.writeline (Date() & ": " & Time() & " - Taxonomy has missing fields.")
					Err.Raise 500, "Filecatman Quick Installer", "Taxonomy has missing fields."
					errorCount = errorCount + 1
				End If
			Next
			
			Dim relationNodeList, relationsList, newRelationDict
			Set objNodeList = objXML.getElementsByTagName("item")
			For each element in objNodeList
				Dim newItemDict: Set newItemDict = CreateObject("Scripting.Dictionary")
				Set relationsList = CreateObject("System.Collections.ArrayList")
				On Error Resume Next
				newItemDict.Add "name", element.selectSingleNode("title").Text
				newItemDict.Add "type", element.selectSingleNode("type_id").Text
				newItemDict.Add "id", element.selectSingleNode("item_id").Text
				newItemDict.Add "source", element.selectSingleNode("item_source").Text	
				newItemDict.Add "time", element.selectSingleNode("item_time").Text	
				newItemDict.Add "description", element.selectSingleNode("item_description").Text
				On Error Goto 0
				Set relationNodeList = element.selectNodes("relation")				
				For each relationNode in relationNodeList
					Set newRelationDict = CreateObject("Scripting.Dictionary")
					For each attr in relationNode.attributes
						If attr.Name = "taxonomy" Then
							newRelationDict.Add "taxonomy", attr.Value
						ElseIf attr.Name = "slug" Then
							newRelationDict.Add "slug", attr.Value
						End If
					Next
					relationsList.Add newRelationDict
					Set newRelationDict = Nothing
				Next
				newItemDict.Add "relations", relationsList
				newItems.Add newItemDict
				Set relationsList = Nothing
				Set newItemDict = Nothing
			Next
			
			Set objNodeList = objXML.getElementsByTagName("category")
			For each element in objNodeList
				Dim newCategoryDict: Set newCategoryDict = CreateObject("Scripting.Dictionary")
				On Error Resume Next
				catSlug = element.selectSingleNode("category_slug").Text
				catTax = element.selectSingleNode("category_tax").Text
				newCategoryDict.Add "slug", element.selectSingleNode("category_slug").Text
				newCategoryDict.Add "name", element.selectSingleNode("category_name").Text
				newCategoryDict.Add "taxonomy", element.selectSingleNode("category_tax").Text
				newCategoryDict.Add "id", element.selectSingleNode("category_id").Text
				newCategoryDict.Add "description", element.selectSingleNode("category_description").Text
				newCategoryDict.Add "parent", element.selectSingleNode("category_parent").Text
				On Error Goto 0
				If Not IsEmpty(catSlug) Then
					If Not (newCategories.Exists(catTax+catSlug)) Then
						newCategories.Add catTax+catSlug, newCategoryDict
					End If
				End If
				Set newCategoryDict = Nothing
				Set catSlug = Nothing
				Set catTax = Nothing
			Next
		Else
			WScript.Echo objXML.ParseError.Reason
		End If
		parseXML = True
	End Function
	
	Private Function runLinkCreation()
		startTime = Timer()
		For Each newItem in newItems
			Dim timeLink, filePath
			Dim skipItem: skipItem = 0
			Dim itemName: itemName = newItem("name")
			If InStr(itemName, "\") Or InStr(itemName, "\") Or InStr(itemName, "/") Or InStr(itemName, ":") Or InStr(itemName, "?") Or InStr(itemName, "*") Or InStr(itemName, "<") Or InStr(itemName, ">") Or InStr(itemName, "|") Or InStr(itemName, """") Then
				logErrors.writeline (Date() & ": " & Time() & " - File '"+itemName+"' contains an illegal character in the name.")
				Err.Raise 500, "Filecatman Quick Installer", "File '"+itemName+"' contains an illegal character in the name."
			End If
			Dim itemType: itemType = newItem("type")
			Dim itemSource: itemSource = newItem("source")
			Dim itemTime: itemTime = newItem("time")
			If (IsEmpty(itemName) Or IsEmpty(itemType)) Then
				logErrors.writeline (Date() & ": " & Time() & " - Item has missing fields.")
				Err.Raise 500, "Filecatman Quick Installer", "Item has missing fields."
				errorCount = errorCount + 1
			End If
			If Not (itemTypes.Exists(itemType)) Then
				logErrors.writeline (Date() & ": " & Time() & " - Item Type details are missing for '"+itemType+"'.")
				Err.Raise 500, "Filecatman Quick Installer", "Item Type details are missing for '"+itemType+"'."
				errorCount = errorCount + 1
			Else
				Dim typeDir: typeDir = itemTypes(itemType)(0)
			End If
			If Not (itemTypes(itemType)(1) = "weblink") Then
				filePath = absoluteDataDir+typeDir+"\"+itemName
				If Not (objFSO.FileExists(filePath)) Then
					logErrors.writeline (Date() & ": " & Time() & " - "+"File Error: File '"+itemName+"' not found.")
					errorCount = errorCount + 1
					skipItem = 1
				End If
			Else
				linkPath = cwd+"Media\"+typeDir+"\"+itemName+".url"
				If Not (createDesktopFile(linkPath, itemSource)) Then
					Wscript.Echo "Failed to create: "+linkPath
				End If
			End If
			
			If Not (skipItem = 1) Then
				Dim dateParts: dateParts = Split(Split(itemTime, " ")(0), "-")
				Dim year: year = dateParts(0)
				Dim month: month = dateParts(1)			
				If Not (year = 0 Or month = 0) Then
					Dim timeYear: timeYear = year
					Dim timeMonth: timeMonth = MonthName(month)
					If (itemTypes(itemType)(1) = "weblink") Then
						timeLink = cwd+"Time\"+timeYear+"\"+timeMonth+"\"+typeDir+"\"+itemName+".url"
						If Not (createDesktopFile(timeLink, itemSource)) Then
							Wscript.Echo "Failed to create: "+timeLink
						End If
					Else
						timeLink = cwd+"Time\"+timeYear+"\"+timeMonth+"\"+typeDir+"\"+itemName+".lnk"
						filePath = getFilePath(4, typeDir, itemName)
						If Not (createLink(filePath, timeLink)) Then
							Wscript.Echo "Failed to create: "+timeLink
						End If						
					End If
				End If
				
				For Each relation In newItem("relations")
					termSlug = relation("slug")
					termTaxonomy = relation("taxonomy")
					If (IsEmpty(termSlug) Or IsEmpty(termTaxonomy)) Then
						logErrors.writeline (Date() & ": " & Time() & " - Relation has missing fields.")
						Err.Raise 500, "Filecatman Quick Installer", "Relation has missing fields."
						errorCount = errorCount + 1
					End If
					If Not (taxonomies.Exists(termTaxonomy)) Then
						logErrors.writeline (Date() & ": " & Time() & " - Taxonomy details are missing for '"+termTaxonomy+"'.")
						Err.Raise 500, "Filecatman Quick Installer", "Taxonomy details are missing for '"+termTaxonomy+"'."
						errorCount = errorCount + 1
					End If
					taxonomyDir = taxonomies(termTaxonomy)
					termName = newCategories(termTaxonomy+termSlug)("name")
					termParent = newCategories(termTaxonomy+termSlug)("parent")
					If IsEmpty(termName) Then
						logErrors.writeline (Date() & ": " & Time() & " - Category has missing fields.")
						Err.Raise 500, "Filecatman Quick Installer", "Category has missing fields."
						errorCount = errorCount + 1
					End If
					
					If (itemTypes(itemType)(1) = "weblink") Then
						If (IsEmpty(termParent) Or termParent = "") Then
							linkPath = cwd+taxonomyDir+"\"+termName+"\"+typeDir+"\"+itemName+".url"
						Else
							termParentArray = returnTermParents(termParent, termTaxonomy)
							termParentRoot = termParentArray(0)
							termParentsJoined = termParentArray(1)
							parentLevels = termParentArray(2)
							linkPath = cwd+taxonomyDir+"\"+termParentRoot+"\"+typeDir+"\"+termParentsJoined+termName+"\"+itemName+".url"
						End If
						If Not (createDesktopFile(linkPath, itemSource)) Then
							Wscript.Echo "Failed to create: "+linkPath
						End If
					Else
						If (IsEmpty(termParent) Or termParent = "") Then
							levels = 3
							linkPath = cwd+taxonomyDir+"\"+termName+"\"+typeDir+"\"+itemName+".lnk"
						Else
							termParentArray = returnTermParents(termParent, termTaxonomy)
							termParentRoot = termParentArray(0)
							termParentsJoined = termParentArray(1)
							parentLevels = termParentArray(2)
							levels = 3+parentLevels
							linkPath = cwd+taxonomyDir+"\"+termParentRoot+"\"+typeDir+"\"+termParentsJoined+termName+"\"+itemName+".lnk"
						End If
						filePath = getFilePath(levels, typeDir, itemName)
						If Not (createLink(filePath, linkPath)) Then
							Wscript.Echo "Failed to create: "+linkPath
						End If	
					End If
				Next
				itemsLinkedCount = itemsLinkedCount + 1
			End If
		Next
		endTime = Timer()
		elapsedTime = FormatNumber(endTime - startTime, 2)
		runLinkCreation = True
	End Function
	
	Private Function getFilePath(levels, typeDir, itemName)
		If (relativeLinks = 1) Then
			getFilePath = Replace(Space(levels), " ", "../")+dataDirName+"/"+typeDir+"/"+itemName
		Else
			getFilePath = absoluteDataDir+typeDir+"\"+itemName
		End If
	End Function
	
	Private Function getWorkingPath(levels)
		If (relativeLinks = 1) Then
			getWorkingPath = Replace(Space(levels), " ", "../")
		Else
			getWorkingPath = cwd
		End If
	End Function
	
	Private Function returnTermParents(termParent, termTaxonomy)
		Set termParentNames = recursiveParentSearch(termParent, termTaxonomy)
		parentCount = termParentNames.Count
		termParentRoot = termParentNames.Item(0)
		termParentNames.RemoveAt(0)
		If (parentCount > 1) Then
			termParentsJoined = Join(termParentNames.ToArray(), "\")+"\"
		Else
			termParentsJoined = ""
		End If
		returnTermParents = Array(termParentRoot, termParentsJoined, parentCount)
	End Function
	
	Private Function recursiveParentSearch(termParent, termTaxonomy)
		If newCategories.Exists(termTaxonomy+termParent)Then
			parentName = newCategories(termTaxonomy+termParent)("name")
			parentParent = newCategories(termTaxonomy+termParent)("parent")
			If (IsEmpty(parentParent) Or parentParent = "" Or parentParent = termParent) Then
				Set termParentNames = CreateObject("System.Collections.ArrayList")
				termParentNames.Add parentName
				Set recursiveParentSearch = termParentNames
			Else
				Set termParentNames = recursiveParentSearch(parentParent, termTaxonomy)
				termParentNames.Add parentName
				Set recursiveParentSearch = termParentNames
			End If
		Else
			logErrors.writeline (Date() & ": " & Time() & " - Parent Searching Error: Term '"+termParent+"' not found.")
			errorCount = errorCount + 1
		End If
	End Function
	
	Private Sub createFullPath (byval path)
		Dim parent								' temporary variable
		path	= objFSO.GetAbsolutePathname(path) ' be sure path is fully qualified
		parent  = objFSO.GetParentFolderName(path) ' get name of parent folder
		If Not objFSO.FolderExists(parent) Then	' if parent(s) does not exist..
			createFullPath parent				' ...create it
		End If
		If Not objFSO.FolderExists(path) Then		' if subfolder does not exist...
			objFSO.CreateFolder(path)				' ...create it.
		End If
	End Sub
	
	Private Function createDesktopFile(linkPath, itemSource)
		linkDir = objFSO.GetParentFolderName(linkPath)
		createFullPath linkDir
		If objFSO.FileExists(linkPath) Then
			If (overwriteLinks = 1) Then
				Set newShortcut = WshShell.CreateShortcut(linkPath)
				newShortcut.TargetPath = itemSource
				newShortcut.Save
				logOverwritten.writeline (Date() & ": " & Time() & " - The shortcut to """ & itemSource & """ at """ & linkPath & """ has been overwritten.")
				linksOverwrittenCount = linksOverwrittenCount + 1
				createDesktopFile = True
			Else
				logAlreadyExists.writeline (Date() & ": " & Time() & " - The shortcut to """ & itemSource & """ at """ & linkPath & """ already exists.")
				linksAlreadyExistCount = linksAlreadyExistCount + 1
				createDesktopFile = True
			End If
		Else
			Set newShortcut = WshShell.CreateShortcut(linkPath)
			newShortcut.TargetPath = itemSource
			newShortcut.Save
			logCreated.writeline (Date() & ": " & Time() & " - The shortcut to """ & itemSource & """ at """ & linkPath & """ has been created.")
			linksCreatedCount = linksCreatedCount + 1
			createDesktopFile = True
		End If
	End Function
	
	Private Function createLink(filePath, linkPath)
		linkDir = objFSO.GetParentFolderName(linkPath)
		createFullPath linkDir
		If objFSO.FileExists(linkPath) Then
			If (overwriteLinks = 1) Then
				Set newShortcut = WshShell.CreateShortcut(linkPath)
				newShortcut.WindowStyle = 1 
				newShortcut.TargetPath = filePath
				newShortcut.Save
				logOverwritten.writeline (Date() & ": " & Time() & " - The shortcut to """ & filePath & """ at """ & linkPath & """ has been overwritten.")
				linksOverwrittenCount = linksOverwrittenCount + 1
				createLink = True
			Else
				logAlreadyExists.writeline (Date() & ": " & Time() & " - The shortcut to """ & filePath & """ at """ & linkPath & """ already exists.")
				linksAlreadyExistCount = linksAlreadyExistCount + 1
				createLink = True
			End If
		Else
			Set newShortcut = WshShell.CreateShortcut(linkPath)
			newShortcut.WindowStyle = 1 
			newShortcut.TargetPath = filePath
			newShortcut.Save
			logCreated.writeline (Date() & ": " & Time() & " - The shortcut to """ & filePath & """ at """ & linkPath & """ has been created.")
			linksCreatedCount = linksCreatedCount + 1
			createLink = True
		End If
	End Function

End Class

Set installer = New InstallerClass
installer.run
	
