=============================
 Filecatman Quick Installers 
=============================

When a Filecatman project's data has been exported to an XML file, it can then be imported with the quick installer, and the item-category relations will be recreated as a shortcuts hierarchy in the directory of the installer. The directory must contain the data folder associated with the XML file. Packaging the project data with the quick installers, the categorization hierarchy can be installed and viewed without requiring Filecatman.

Packaging Instructions:
-----------------------

To create a project package, you will need 3 things:

* The Filecatman project's Data Folder.
This is the folder that contains all the files used in the Filecatman project. 
The name of the data folder must be renamed to "Files", else the installers won't know where to look. If you want the installers to look for a different name, the "dataDirName" variable in each quick installer must be changed.

* The XML file.
The Filecatman project's categorization data that has been exported to XML.

* The quick installers.
It would be best to include all of them to be sure the project will be compatible with the supported operating systems.

Example Package Structure:
--------------------------

My Filecatman Project/
|-- Files/
|   |-- Documents/
|   |-- Webpages/
|		|-- page.html
|
|-- filecatman-project.xml
|-- installer_linux.py
|-- installer_windows.vbs
|-- installer_windows.py
|-- installer_mac.py
|-- readme.txt

Quick Installer Requirements & Usage:
-------------------------------------

## Windows ##

* 'installer_windows.vbs'
This installer is written in VBScript. All versions of Windows from Windows 98 onward include a VBScript interpreter. Microsoft .NET Framework 2.0 or later is required if the operating system is Windows XP or older.

.NET Framework 2.0: http://filehippo.com/download_dotnet_framework_2

Usage:
A. Double click the quick installer.
B. Open it with Command Prompt. E.g. "cscript installer_windows.vbs".

* 'installer_windows.py'
Written in Python. Make sure Python version 3 or above is installed and the 'Python for Windows extensions'.

Python: http://python.org/
Python for Windows extensions: http://sourceforge.net/projects/pywin32/

Usage:
A. Double click the quick installer. If the dependencies are installed correctly it should open in a Python console.
B. Open it with Command Prompt. E.g. "python installer_windows.py". This will work if the "python" command is bound to the Python executable.

## Linux ##

* 'installer_linux.py'
Written in Python. Make sure Python version 3 or above is installed.

Usage:
A. Double click the quick installer and run in terminal if the option is available.
B. Open it in a Terminal. E.g. "./installer_linux.py".

## Mac ##

* 'installer_mac.py'
Written in Python. Make sure Python version 3 or above is installed.

Usage:
A. Double click the quick installer and run in terminal if the option is available.
B. Open it in a Terminal. E.g. "./installer_mac.py".


Notes:
------

* The usage of the installer could take seconds or minutes depending on the size of the XML file, operating system, quick installer or computer hardware.
* The VBScript quick installer won't show any progress bar or messages while installing.
* The Linux quick installer supports the creation of relative links or absolute links. This setting can be changed in the quick installer code. Relative links are default for Linux, while only absolute links are available for Windows. Relative links don't break if the parent directory above the project changes.
