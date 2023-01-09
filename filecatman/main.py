#!/usr/bin/env python3

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
import argparse
from filecatman.core import const
from filecatman.filecatman import Filecatman
import filecatman.log as log


class main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="Show program's version number and exit", action="store_true")
    parser.add_argument("-db", "--database", help="Specify a filepath to load an SQLite database",
                        action="store", dest="database")
    parser.add_argument("-L", "--loglevel", help="Set the log level: none, info, warning, error, critical, debug",
                        action="store", dest="loglevel")
    parser.add_argument("-q", "--quiet", help="Sets the log level to 'none', this is the same as `-L none`",
                        dest="quiet", action="store_true", default=False)
    args = parser.parse_args()
    if args.quiet:
        const.LOGGERLEVEL = "none"
    if args.loglevel:
        const.LOGGERLEVEL = args.loglevel.lower()
    if args.version:
        sys.exit("Filecatman: "+const.VERSION)

    app = Filecatman(sys.argv)
    app.setOrganizationName(const.ORGNAME)
    app.setApplicationName(const.APPNAME)
    app.setApplicationVersion(const.VERSION)
    app.setPortableMode(const.PORTABLEMODE)

    log.initializeLogger(const.LOGGERLEVEL)
    if sys.hexversion < 0x03030000:
        log.logger.warning("Python 3.3 or higher is recommended to run this program.")

    app.exec_(args.database)

if __name__ == "__main__":
    main()