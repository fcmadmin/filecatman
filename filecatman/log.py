import os
import sys
import logging
from PySide6.QtCore import QSettings
from filecatman.core import const
from filecatman.core.objects import ÆColoredFormatter

levels = dict(
    info=logging.INFO,
    warning=logging.WARNING,
    error=logging.ERROR,
    none=logging.CRITICAL,
    debug=logging.DEBUG
)


def initializeLogger(level):
    if const.PORTABLEMODE:
        logPath = os.path.splitext(os.path.basename(QSettings().fileName()))[0]+".log"
    else:
        configDir = os.path.dirname(QSettings().fileName())
        if not os.path.exists(configDir):
            os.makedirs(configDir)
        logPath = os.path.splitext(QSettings().fileName())[0]+".log"

    if not level or level not in levels:
        level = "error"

    rootLogger = logging.getLogger('')
    rootLogger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(stream=sys.stdout)
    if os.name == "nt":
        console.setFormatter(logging.Formatter('%(lineno)-s %(name)-s: %(levelname)-s %(message)s'))
    else:
        console.setFormatter(ÆColoredFormatter('%(lineno)-s %(name)-s: %(levelname)-s %(message)s'))
    console.setLevel(levels[level])
    rootLogger.addHandler(console)

    fh = logging.FileHandler(logPath, 'w')
    fh.setFormatter(logging.Formatter('[%(asctime)-s] %(lineno)s %(name)-s: %(levelname)-8s %(message)s',
                                      datefmt='%m-%d %H:%M'))
    fh.setLevel(logging.DEBUG)
    rootLogger.addHandler(fh)

logger = logging.getLogger("Filecatman")