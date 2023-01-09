#Namespace Container Class
class Æ:
    OnlyDisabled = 0
    OnlyEnabled = 1

    NoChildren = 2
    IsTags = 3
    NoTags = 4

    IsWeblinks = 2
    NoWeblinks = 3
    IsWebpages = 4
    NoWebpages = 5

    #Main Table Types
    TableItems = 0
    TableCategories = 1
    TableSearch = 2
    TableMissing = 3
    TableBrokenLinks = 4

    ItemTableTypes = (TableItems, TableSearch, TableMissing, TableBrokenLinks)
    CategoryTableTypes = (TableCategories,)