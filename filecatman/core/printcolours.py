class bcolours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    CRITICAL = '\033[1;91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    SQL = '\033[34m'

    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    BRIGHTGREEN = '\033[92m'
    YELLOW = '\033[33m'
    BRIGHTYELLOW = '\033[93m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[38m'
    NORMAL = '\033[39m'

    BBLACK = '\033[1;30m'
    BRED = '\033[1;31m'
    BGREEN = '\033[1;32m'
    BBRIGHTGREEN = '\033[1;92m'
    BYELLOW = '\033[1;33m'
    BBRIGHTYELLOW = '\033[1;93m'
    BBLUE = '\033[1;34m'
    BMAGENTA = '\033[1;35m'
    BCYAN = '\033[1;36m'
    BWHITE = '\033[1;37m'
    BGRAY = '\033[1;38m'
    BNORMAL = '\033[0;39m'

    HRED = '\033[1;41m'
    HGREEN = '\033[1;42m'
    HYELLOW = '\033[1;43m'
    HBLUE = '\033[1;44m'
    HMAGENTA = '\033[1;45m'
    HCYAN = '\033[1;46m'
    HGRAY = '\033[1;47m'

    def test(self):
        print(self.HEADER+"This line is a header."+self.ENDC)
        print(self.OKBLUE+"This line is ok."+self.ENDC)
        print(self.OKGREEN+"This line is ok."+self.ENDC)
        print(self.WARNING+"This line is a warning."+self.ENDC)
        print(self.FAIL+"This line is a failure."+self.ENDC)
        print(self.CRITICAL+"This line is critical."+self.ENDC)
        print(self.BOLD+"This line is bold."+self.ENDC)
        print(self.SQL+"This line is SQL."+self.ENDC)

        print(self.BLACK+"This line is black."+self.ENDC)
        print(self.RED+"This line is red."+self.ENDC)
        print(self.GREEN+"This line is green."+self.ENDC)
        print(self.BRIGHTGREEN+"This line is bright green."+self.ENDC)
        print(self.YELLOW+"This line is yellow."+self.ENDC)
        print(self.BRIGHTYELLOW+"This line is bright yellow."+self.ENDC)
        print(self.BLUE+"This line is blue."+self.ENDC)
        print(self.MAGENTA+"This line is magenta."+self.ENDC)
        print(self.CYAN+"This line is cyan."+self.ENDC)
        print(self.WHITE+"This line is white."+self.ENDC)
        print(self.GRAY+"This line is gray."+self.ENDC)
        print(self.NORMAL+"This line is normal."+self.ENDC)

        print(self.BBLACK+"This line is bold black."+self.ENDC)
        print(self.BRED+"This line is bold red."+self.ENDC)
        print(self.BGREEN+"This line is bold green."+self.ENDC)
        print(self.BBRIGHTGREEN+"This line is bold bright green."+self.ENDC)
        print(self.BYELLOW+"This line is bold yellow."+self.ENDC)
        print(self.BBRIGHTYELLOW+"This line is bold bright yellow."+self.ENDC)
        print(self.BBLUE+"This line is bold blue."+self.ENDC)
        print(self.BMAGENTA+"This line is bold magenta."+self.ENDC)
        print(self.BCYAN+"This line is bold cyan."+self.ENDC)
        print(self.BWHITE+"This line is bold white."+self.ENDC)
        print(self.BGRAY+"This line is bold gray."+self.ENDC)
        print(self.BNORMAL+"This line is bold normal."+self.ENDC)

        print(self.HRED+"This line is highlighted red."+self.ENDC)
        print(self.HGREEN+"This line is highlighted green."+self.ENDC)
        print(self.HYELLOW+"This line is highlighted yellow."+self.ENDC)
        print(self.HBLUE+"This line is highlighted blue."+self.ENDC)
        print(self.HMAGENTA+"This line is highlighted magenta."+self.ENDC)
        print(self.HCYAN+"This line is highlighted cyan."+self.ENDC)
        print(self.HGRAY+"This line is highlighted gray."+self.ENDC)