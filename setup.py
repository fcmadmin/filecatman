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

import glob
import os
import shutil
import sys
from setuptools import setup, find_packages
from distutils import cmd
from distutils.command.install_data import install_data as _install_data
from filecatman.core import const

desktopFile = 'filecatman/data/share/applications/filecatman.desktop'

def windowsCheck(): return sys.platform.startswith('win')
def osxCheck(): return sys.platform.startswith('darwin')

class installData(_install_data):
    def run(self):
        _install_data.run(self)
        print("Updating GTK icon cache")
        os.system("sudo gtk-update-icon-cache -q -t -f {0}/share/icons/hicolor".format(self.install_dir))


class createDesktopShortcut(cmd.Command):
    description = "Create a desktop shortcut"
    user_options = []
    def initialize_options(self): pass
    def finalize_options(self): pass
    def run(self):
        print("Creating desktop shortcut")
        desktopSrc = desktopFile
        desktopDst = os.getenv("HOME")+'/Desktop/filecatman.desktop'
        shutil.copyfile(desktopSrc, desktopDst)
        os.chmod(desktopDst, 0o755)


if sys.hexversion < 0x03030000:
    print("WARNING: Python 3.3 or higher is recommended to run this program.")

if osxCheck():
    # sys.exit("Your operating system is not yet supported.")
    pass


cmdClass = {}
dataFiles = []
packageData =  [
        "data/icons/*.png",
        "data/icons/*.gif",
        "data/icons/hicolor/32x32/apps/*.png",
        "data/icons/hicolor/48x48/apps/*.png",
        "data/icons/hicolor/64x64/apps/*.png",
        "data/icons/hicolor/128x128/apps/*.png",
        "data/icons/hicolor/256x256/apps/*.png",
        "data/icons/farmFresh/*.png",
        "data/icons/prettyOffice/*.png",
        "gui/ui/*.ui",
        "core/queries/*.sql"]

if windowsCheck() or osxCheck():
     packageData.append('docs/en/*.html')
     packageData.append('docs/en/resources/*.png')
     packageData.append('docs/en/resources/*.css')
else:
    packageData.append('docs/en/*.html')
    packageData.append('docs/en/resources/*.png')
    packageData.append('docs/en/resources/*.css')
    dataFiles = [
        ('share/icons/hicolor/32x32/apps', ['filecatman/data/icons/hicolor/32x32/apps/filecatman.png']),
        ('share/icons/hicolor/48x48/apps', ['filecatman/data/icons/hicolor/48x48/apps/filecatman.png']),
        ('share/icons/hicolor/64x64/apps', ['filecatman/data/icons/hicolor/64x64/apps/filecatman.png']),
        ('share/icons/hicolor/128x128/apps', ['filecatman/data/icons/hicolor/128x128/apps/filecatman.png']),
        ('share/icons/hicolor/256x256/apps', ['filecatman/data/icons/hicolor/256x256/apps/filecatman.png']),
        ('share/doc/filecatman/en', glob.glob('filecatman/docs/en/*.html')),
        ('share/doc/filecatman/en/resources', glob.glob('filecatman/docs/en/resources/*.png')),
        ('share/doc/filecatman/en/resources', glob.glob('filecatman/docs/en/resources/*.css')),
        ('share/applications', [desktopFile])
    ]
    cmdClass = {
        'install_data': installData,
        'desktop': createDesktopShortcut
    }

setup(
    name='filecatman',
    version=const.VERSION,
    packages=find_packages(),
    package_data={"filecatman": packageData
    },
    data_files= dataFiles,
    author=const.AUTHOR,
    author_email=const.AUTHOREMAIL,
    download_url=const.DOWNLOADURL,
    url=const.WEBSITE,
    license='GPLv3',
    description=const.DESCRIPTION,
    long_description='A file categorization management program, designed to make sorting, '
                     'categorizing and accessing data simple and easy.',
    entry_points={
        "console_scripts": ['filecatman = filecatman.main:main']
    },
    install_requires=[
        'requests',
        'urllib3',
        'PySide6'
    ],
    cmdclass=cmdClass,
    zip_safe=False,
    platforms="Linux, Windows, Mac"
)

# Remove egg-info directory which is no longer needed
try:
    shutil.rmtree("filecatman.egg-info")
except:
    pass
