import os
import logging
from urllib.parse import quote, unquote

from PySide6.QtSql import QSqlDatabase, QSqlQuery, QSql

from filecatman.lib.slugify import slugify
from filecatman.core.functions import getÆDirPath


class ÆDatabase(QSqlDatabase):
    con, lastInsertId, error, appConfig = None, None, None, None
    defaultTables = (
        'items', 'terms', 'term_relationships', 'options', 'item_types', 'taxonomies'
    )
    conSuccess = False
    debug = True

    def __init__(self, config):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        if config['type'] == 'mysql':
            self.config = {
                'host': config['host'],
                'port': int(config['port']),
                'user': config['user'],
                'passwd': config['passwd'],
                'db': config['db'],
                'charset': 'utf8',
                'type': 'mysql'
            }
        elif config['type'] == 'sqlite':
            self.config = {
                'db': config['db'],
                'charset': 'utf8',
                'type': 'sqlite'
            }
        else:
            raise Exception('Unknown database driver in configuration file: '+config['type'])
        if config.get('create') and config['create'] is True:
            self.createDatabase()
        else:
            self.newConnection()

    def newConnection(self):
        self.error = None
        if self.config['type'] == 'mysql':
            if self.database(self.config['db']).isValid():
                db = self.database(self.config['db'])
                self.logger.debug("Using previously loaded connection: '{}'".format(self.config['db']))
            else:
                db = self.addDatabase("QMYSQL", self.config['db'])
            db.setHostName(self.config['host'])
            db.setPort(self.config['port'])
            db.setDatabaseName(self.config['db'])
            db.setUserName(self.config['user'])
            db.setPassword(self.config['passwd'])
            self.con = db
            self.con.open()
            if self.con.isOpen():
                for table in self.defaultTables:
                    if table not in self.con.tables(QSql.AllTables):
                        self.logger.warning("Table '{}' was missing from the database.".format(table))
                        self.createTables()
                        break
                self.con.close()
                self.logger.info("Successfully opened database `{}`.".format(self.config['db']))
                self.conSuccess = True
                return True
            else:
                self.conSuccess = False
                raise Exception(str(self.con.lastError().databaseText()))
        elif self.config['type'] == 'sqlite':
            databaseName = os.path.basename(self.config['db'])
            if self.database(databaseName).isValid():
                db = self.database(databaseName)
                self.logger.debug("Using previously loaded connection: '{}'".format(self.config['db']))
            else:
                db = self.addDatabase("QSQLITE", os.path.basename(self.config['db']))
            db.setDatabaseName(self.config['db'])
            self.con = db
            self.con.open()
            if self.con.isOpen():
                QSqlQuery("PRAGMA foreign_keys = ON;", self.con)
                for table in self.defaultTables:
                    if table not in self.con.tables(QSql.AllTables):
                        self.logger.warning("Table '{}' was missing from the database.".format(table))
                        self.createTables()
                        break
                self.con.close()
                self.logger.info("Successfully opened database `{}`.".format(self.config['db']))
                self.conSuccess = True
                return True
            else:
                self.conSuccess = False
                raise Exception(self.con.lastError().databaseText())

    def removeConnection(self):
        self.removeDatabase(self.config['db'])

    def createDatabase(self):
        self.error = None
        if self.config['type'] == 'mysql':
            if self.database(self.config['db']).isValid():
                db = self.database(self.config['db'])
                self.logger.debug("Using previously loaded connection: '{}'".format(self.config['db']))
            else:
                db = self.addDatabase("QMYSQL", self.config['db'])
            db.setHostName(self.config['host'])
            db.setPort(self.config['port'])
            db.setUserName(self.config['user'])
            db.setPassword(self.config['passwd'])
            db.setDatabaseName(None)
            self.con = db

            self.con.open()
            if self.con.isOpen():
                SQL = "CREATE DATABASE IF NOT EXISTS `{0}`; USE `{0}`;".format(self.config['db'])
                self.logger.debug('\n'+SQL)
                queryCreate = QSqlQuery(SQL, self.con)
                if queryCreate:
                    self.con.setDatabaseName(self.config['db'])
                    if self.createTables():
                        self.logger.info("Database successfully created.")
                        self.con.close()
                        self.conSuccess = True
                        self.newConnection()
                    else:
                        self.conSuccess = False
                        raise Exception(self.con.lastError().databaseText())
                else:
                    self.conSuccess = False
                    raise Exception(self.con.lastError().databaseText())
            else:
                self.conSuccess = False
                raise Exception(self.con.lastError().databaseText())
        elif self.config['type'] == 'sqlite':
            databaseName = os.path.basename(self.config['db'])
            if self.database(databaseName).isValid():
                db = self.database(databaseName)
                self.logger.debug("Using previously loaded connection: '{}'".format(self.config['db']))
            else:
                db = self.addDatabase("QSQLITE", databaseName)
            db.setDatabaseName(self.config['db'])
            self.con = db
            self.con.open()
            if self.con.isOpen():
                if self.createTables():
                    self.logger.info("Database successfully created.")
                    self.con.close()
                    self.conSuccess = True
                    self.newConnection()
            else:
                self.conSuccess = False
                raise Exception(self.con.lastError().databaseText())

    def createTables(self):
        if self.config['type'] == 'sqlite':
            file = open(os.path.join(getÆDirPath(),'core', 'queries','newsqlitedatabase.sql'), 'r')
            with file:
                SQL = file.read()

            sqlStatements = SQL.split(";")
            queryTablesCreate = QSqlQuery(self.con)
            self.transaction()
            for SQL in sqlStatements:
                self.logger.debug('\n'+SQL)
                queryTablesCreate.exec_(SQL)
            self.commit()
            for table in self.defaultTables:
                if table not in self.con.tables(QSql.AllTables):
                    raise Exception("Unable to create database tables.")
            self.logger.info("Tables successfully created.")
            return True
        elif self.config['type'] == 'mysql':
            file = open(os.path.join(getÆDirPath(),'core','queries','newmysqldatabase.sql'), 'r')
            with file:
                SQL = file.read()
            self.logger.debug('\n'+SQL)
            queryTablesCreate = QSqlQuery(SQL, self.con)
            if queryTablesCreate:
                self.logger.info("Tables successfully created.")
                return True
        else:
            return False

    def lastError(self):
        if not self.con.lastError().type() == 0:
            return self.con.lastError().databaseText()
        elif self.error is not None:
            return self.error

    def printQueryError(self, e):
        if self.config['type'] == 'mysql':
            self.logger.error("Error: "+str(e))
            self.error = str(e)
        elif self.config['type'] == 'sqlite':
            self.logger.error("Error: "+str(e))
            self.error = str(e)

    def open(self):
        if self.con:
            self.con.open()
            if self.config['type'] == 'sqlite':
                QSqlQuery("PRAGMA foreign_keys = ON;", self.con)
        else:
            self.logger.error("Error: No connection to open.")

    def close(self):
        if self.con:
            self.con.close()
        else:
            self.logger.error("Error: No connection to close.")

    def transaction(self, debug=False):
        if self.debug is False:
            if debug is True:
                self.logger.disabled = False
            else:
                self.logger.disabled = True
        else:
            self.logger.disabled = False
        return self.con.transaction()

    def commit(self):
        return self.con.commit()

    def rollback(self):
        return self.con.rollback()

    def versionInfo(self):
        if self.config['type'] == 'mysql':
            query = QSqlQuery('SELECT VERSION()', self.con)
            if query.first():
                version = query.value(0)
                return version
        elif self.config['type'] == 'sqlite':
            query = QSqlQuery('SELECT SQLITE_VERSION()', self.con)
            if query.first():
                version = query.value(0)
                return version

    def tables(self):
        return self.con.tables(QSql.AllTables)

    def newItem(self, data):
        self.lastInsertId = None

        queryData = dict()
        colnames = dict(name="item_name", type="type_id", source="item_source",
                        datetime="item_time", description="item_description")

        if data.get('name') is None or data.get('type') is None:
            self.logger.error("Error creating new item: name or typeID field is missing.")
            return
        else:
            if data.get('datetime') is None:
                if data.get('date') is None:
                    data['date'] = "0000-00-00"
                if data.get('time') is None:
                    data['time'] = "00:00:00"
                data['datetime'] = data['date']+" "+data['time']

            if data.get('description'):
                data['description'] = quote(data['description'])
            if data.get('source'):
                data['source'] = quote(data['source'])

            for colabb, value in data.items():
                if value is not None and value != "":
                    if colabb in colnames:
                        queryData[colnames[colabb]] = value

            sql = "INSERT INTO items (" + ", ".join(queryData.keys())\
                  + ") VALUES('" + "', '".join(queryData.values()) + "')"
            self.logger.debug('\n'+sql)
            for key, value in queryData.items():
                self.logger.debug(key+": "+value)
            query = QSqlQuery(sql, self.con)
            self.lastInsertId = query.lastInsertId()
            self.logger.debug("Last Id: "+str(self.lastInsertId))
            if self.lastInsertId:
                self.logger.info("Item successfully inserted.")
            else:
                self.logger.warning("Item already exists.")
            return True

    def newCategory(self, data, args=None):
        self.lastInsertId = None
        if args is not None:
            if args.get('replace') and args['replace'] is True:
                pass
            else:
                args['replace'] = False
        else:
            args = dict()
            args['replace'] = False
        queryData = dict()
        colnames = {"name": "term_name",
                    "slug": "term_slug",
                    "taxonomy": "term_taxonomy",
                    "parent": "term_parent",
                    "description": "term_description"}

        if data.get('name') is None or data.get('taxonomy') is None:
            self.logger.error("Error creating new category: name or taxonomy field is missing.")
            return
        else:
            if data.get('slug') in ("", None):
                data['slug'] = slugify(data['name'])
            else:
                data['slug'] = slugify(data['slug'])
            if data.get('description'):
                data['description'] = quote(data['description'])
            else:
                data['description'] = ""

            for colabb, value in data.items():
                if value is not None and value != "":
                    if colabb in colnames:
                        queryData[colnames[colabb]] = value

            if data.get('parent') in ("", None):
                data['parent'] = "NULL"

            for key, value in queryData.items():
                self.logger.debug(key+": "+value)

            queryTerm = QSqlQuery(self.con)
            queryTerm.setForwardOnly(True)
            if args['replace'] is True:
                if self.config['type'] == 'mysql':
                    termSQL = "INSERT INTO terms ("+", ".join(queryData.keys())\
                              + ") VALUES('"+"', '".join(queryData.values())+"')"\
                              + " ON DUPLICATE KEY UPDATE term_id=LAST_INSERT_ID(term_id)"
                    self.logger.debug('\n'+termSQL)
                    queryTerm.exec_(termSQL)
                    self.logger.info("Category successfully inserted.")
                    self.lastInsertId = str(queryTerm.lastInsertId())
                elif self.config['type'] == 'sqlite':
                    termSQL = "INSERT INTO terms ("+", ".join(queryData.keys())\
                              + ") VALUES('"+"', '".join(queryData.values())+"')"
                    self.logger.debug('\n'+termSQL)
                    queryTerm.exec_(termSQL)
                    if queryTerm.lastInsertId() is None:
                        termSelectSQL = "SELECT term_id from terms WHERE term_slug = '{}' AND term_taxonomy = '{}'"\
                                        .format(data['slug'], data['taxonomy'])
                        self.logger.debug('\n'+termSelectSQL)
                        queryTerm.exec_(termSelectSQL)
                        if queryTerm.first():
                            termIden = queryTerm.value(0)
                            termUpdateSQL = "UPDATE terms SET term_name='{}', term_slug='{}', term_parent={}, term_taxonomy='{}', " \
                                            "term_description='{}' WHERE term_id = {}"\
                                            .format(data['name'], data['slug'], data['parent'], data['taxonomy'],
                                                    data['description'], termIden)
                            self.logger.debug('\n'+termUpdateSQL)
                            queryTerm.exec_(termUpdateSQL)
                            self.lastInsertId = str(termIden)
                            self.logger.warning("Category successfully replaced.")
                    else:
                        self.lastInsertId = str(queryTerm.lastInsertId())
            else:
                termSQL = "INSERT INTO terms ("+", ".join(queryData.keys())\
                          + ") VALUES('"+"', '".join(queryData.values())+"')"
                self.logger.debug('\n'+termSQL)
                queryTerm.exec_(termSQL)
                self.lastInsertId = queryTerm.lastInsertId()
                self.logger.info("Category successfully inserted.")
            self.logger.debug("Last Term Id: "+str(self.lastInsertId))
            return True

    def newRelation(self, data):
        self.lastInsertId = None

        if data.get('item') is None or data.get('term') is None:
            self.logger.error("Error creating new relation: ID field is missing.")
            return
        else:
            queryData = data
            sql = "INSERT INTO term_relationships (item_id, term_id) VALUES('{}', '{}')"\
                .format(queryData['item'], queryData['term'])
            self.logger.debug('\n'+sql)
            for key, value in queryData.items():
                self.logger.debug(str(key)+": "+str(value))
            query = QSqlQuery(self.con)
            if query.exec_(sql):
                self.logger.info("Relation successfully inserted.")
                self.incrementTermCount(queryData['term'])
            else:
                self.logger.warning("Relation already exists.")

            self.lastInsertId = query.lastInsertId()
            self.logger.debug("Last Id: "+str(self.lastInsertId))

            return True

    def updateItem(self, data):
        colnames = dict(name="item_name",
                        type="type_id",
                        source="item_source",
                        datetime="item_time",
                        description="item_description")
        queryData = dict()

        if data.get('id') is None:
            return

        if data.get('datetime') is None:
            if data.get('date') is None:
                data['date'] = "0000-00-00"
            if data.get('time') is None:
                data['time'] = "00:00:00"
            data['datetime'] = data['date']+" "+data['time']

        if data.get('description'):
                data['description'] = quote(data['description'])
        if data.get('source'):
            data['source'] = quote(data['source'])

        for colabb, value in data.items():
            if value is not None:
                if colabb in colnames:
                    queryData[colnames[colabb]] = value

        SQL = "UPDATE items Set "
        i = 0
        for key, value in queryData.items():
            line = key+"='"+value+"'"
            if i < len(queryData)-1:
                line += ", "
            i += 1
            SQL += line
        SQL += " WHERE item_id='{}'".format(data.get('id'))
        self.logger.debug('\n'+SQL)
        query = QSqlQuery(SQL, self.con)
        self.lastInsertId = query.lastInsertId()
        self.logger.info("Item successfully updated.")

    def updateItemType(self, oldItemType, newItemType):
        SQL = "UPDATE items Set type_id='{}' WHERE type_id='{}'".format(newItemType, oldItemType)
        self.logger.debug('\n'+SQL)
        query = QSqlQuery(SQL, self.con)
        self.lastInsertId = query.lastInsertId()
        self.logger.info("Item Type `{}` successfully updated to `{}`.".format(oldItemType, newItemType))

    def updateTaxonomy(self, oldTaxonomy, newTaxonomy):
        SQL = "UPDATE terms Set term_taxonomy='{}' WHERE term_taxonomy='{}'"\
              .format(newTaxonomy, oldTaxonomy)
        self.logger.debug('\n'+SQL)
        query = QSqlQuery(SQL, self.con)
        self.lastInsertId = query.lastInsertId()
        self.logger.info("Taxonomy `{}` successfully updated to `{}`.".format(oldTaxonomy, newTaxonomy))

    def updateCategory(self, data):
        if data.get('termid') is None or data.get('name') is None:
            return

        if data.get('slug') in ("", None):
            data['slug'] = slugify(data['name'])
        else:
            data['slug'] = slugify(data['slug'])
        if data.get('description'):
                data['description'] = quote(data['description'])
        else:
            data['description'] = ""

        if data.get('parent') in ("", None):
            data['parent'] = 'NULL'

        termSQL = "UPDATE terms SET term_name='{}', term_slug='{}', term_parent={}, term_taxonomy='{}', " \
                  "term_description='{}' WHERE term_id = '{}'"\
            .format(data['name'], data['slug'], data['parent'], data['taxonomy'], data['description'], data['termid'])
        self.logger.debug('\n'+termSQL)
        queryTerm = QSqlQuery(termSQL, self.con)
        self.lastInsertId = queryTerm.lastInsertId()
        self.logger.info("Category successfully updated.")

    def deleteItem(self, itemid):
        sql = "SELECT term_id FROM term_relationships as tr " \
              "WHERE (tr.item_id = {})".format(itemid)
        self.logger.debug("\n"+sql)
        query = QSqlQuery(sql, self.con)
        while query.next():
            self.decrementTermCount(query.value(0))
        sql = "DELETE FROM items WHERE item_id = '{}'".format(itemid)
        self.logger.debug("\n"+sql)
        QSqlQuery(sql, self.con)
        self.logger.info("Item successfully deleted.")
        return True

    def deleteCategory(self, termIden):
        queryDelete = QSqlQuery(self.con)
        sql = "DELETE FROM terms WHERE term_id = '{}'".format(termIden)
        if queryDelete.exec_(sql):
            self.logger.info("Category successfully deleted.")
            return True

    def deleteRelation(self, itemid, termid):
        sql = "DELETE FROM term_relationships WHERE (item_id = '{}') AND (term_id = '{}')"\
            .format(itemid, termid)
        self.logger.debug('\n'+sql)
        QSqlQuery(sql, self.con)
        self.decrementTermCount(termid)
        self.logger.info("Relation successfully deleted.")
        return True

    def deleteRelations(self, iden, col='item_id'):
        sql = "SELECT item_id, term_id FROM term_relationships WHERE {} = {}".format(col, iden)
        relations = QSqlQuery(self.con)
        relations.setForwardOnly(True)
        relations.exec_(sql)
        while relations.next():
            sql = "DELETE FROM term_relationships WHERE (item_id = '{}') AND (term_id = '{}')"\
                  .format(relations.value(0), relations.value(1))
            QSqlQuery(sql, self.con)
            self.decrementTermCount(relations.value(1))
        self.logger.info("Relations successfully deleted.")
        return True

    def deleteItemTypes(self):
        query = QSqlQuery(self.con)
        query.exec_("DELETE FROM item_types")
        if self.config['type'] == 'mysql':
            query.exec_("ALTER TABLE item_types AUTO_INCREMENT = 1;")
        elif self.config['type'] == 'sqlite':
            query.exec_("UPDATE SQLITE_SEQUENCE SET seq = 0 WHERE name = 'item_types';")
        self.logger.info("Item Types successfully deleted.")
        return True

    def deleteTaxonomies(self):
        query = QSqlQuery(self.con)
        query.exec_("DELETE FROM taxonomies")
        if self.config['type'] == 'mysql':
            query.exec_("ALTER TABLE taxonomies AUTO_INCREMENT = 1;")
        elif self.config['type'] == 'sqlite':
            query.exec_("UPDATE SQLITE_SEQUENCE SET seq = 0 WHERE name = 'taxonomies';")
        self.logger.info("Taxonomies successfully deleted.")
        return True

    def bulkDeleteItems(self, itemIdens):
        self.transaction()
        sql = "SELECT term_id FROM term_relationships as tr " \
              "WHERE item_id IN ({})".format(", ".join(itemIdens))
        self.logger.debug('\n'+sql)
        relations = QSqlQuery(sql, self.con)
        while relations.next():
            self.decrementTermCount(relations.value(0))
        sql = "DELETE FROM items WHERE (item_id) IN ({})".format(", ".join(itemIdens))
        self.logger.debug('\n'+sql)
        QSqlQuery(sql, self.con)
        self.commit()
        self.logger.info("Items successfully deleted.")
        return True

    def selectItem(self, itemID, col="*"):
        query = QSqlQuery("SELECT {} FROM items AS i "
                          "WHERE (item_id= '{}')".format(col, itemID), self.con)
        if query.first():
            return query

    def selectItems(self, args=None):
        where = ["( i.item_id is not null )", ]
        startLimit = 0
        col = "*"
        limit = ""

        if args:
            if args.get('item_id'):
                where.append("( i.item_id = '{}' )".format(args['item_id']))
            if args.get('type_id'):
                where.append("( i.type_id = '{}' )".format(args['type_id']))
            if args.get('item_name'):
                where.append("( i.item_name = '{}' )".format(args['item_name']))
            if args.get('col'):
                col = args['col']
            if args.get('limit'):
                if args.get('start'):
                    startLimit = args['start']
                limit = "LIMIT {}, {}".format(startLimit, args['limit'])
        whereJoined = " AND ".join(where)
        query = QSqlQuery(self.con)
        sql = "SELECT {} FROM items AS i " \
              "WHERE {} " \
              "{}".format(col, whereJoined, limit)
        self.logger.debug('\n'+sql)
        query.exec_(sql)
        return query

    def selectCategory(self, catID, col="*"):
        sql = "SELECT {} FROM terms AS t " \
              "WHERE (t.term_id = '{}')".format(col, catID)
        query = QSqlQuery(sql, self.con)
        self.logger.debug('\n'+sql)
        if query.first():
            return query

    def selectCategories(self, args=None):
        where = ["( t.term_id is not null )", ]
        col = "*"
        if args:
            if args.get('term_id'):
                where.append("( t.term_id = '{}' )".format(args['term_id']))
            if args.get('term_taxonomy'):
                where.append("( t.term_taxonomy = '{}' )".format(args['term_taxonomy']))
            if args.get('col'):
                col = args['col']
        whereJoined = " AND ".join(where)
        query = QSqlQuery(self.con)
        query.setForwardOnly(True)
        sql = "SELECT {} FROM terms AS t " \
              "WHERE {}".format(col, whereJoined)
        self.logger.debug('\n'+sql)
        query.exec_(sql)
        return query

    def selectCategoriesAsTree(self, args=None):
        queryArgs = dict()
        if args is None:
            args = dict()
        if args.get('taxonomy') is not None:
            queryArgs['tax'] = args['taxonomy']
        if args.get('complete') is not None:
            selectComplete = args['complete']
        else:
            selectComplete = False
        if args.get('extra') is not None:
            queryArgs['extra'] = args['extra']
        else:
            queryArgs['extra'] = None
        catLvls = self.appConfig['options']['catLvls']
        if selectComplete:
            sql = "SELECT root.term_id AS root_id, " \
                  "root.term_taxonomy AS root_tax, root.term_name AS root_name, " \
                  "root.term_slug AS root_slug, root.term_count AS root_count"
        else:
            sql = """SELECT root.term_id AS root_id, root.term_name AS root_name"""
        if catLvls > 0:
            sql += ","
        i = 1
        while i <= catLvls:
            curLevel = str(i)
            if selectComplete:
                sql += "\ndown{0}.term_id AS down{0}_id, " \
                       "down{0}.term_taxonomy AS down{0}_tax, down{0}.term_name as down{0}_name, " \
                       "down{0}.term_slug AS down{0}_slug, down{0}.term_count AS down{0}_count".format(curLevel)
            else:
                sql += "\ndown{0}.term_id AS down{0}_id, down{0}.term_name as down{0}_name"\
                    .format(curLevel)
            if i < catLvls:
                sql += ","
            i += 1
        sql += "\nFROM terms AS root"
        i = 1
        while i <= catLvls:
            curLevel = str(i)
            if i is 1:
                lastLevel = "root"
            else:
                lastLevel = "down"+str(i-1)
            sql += "\nLEFT JOIN terms AS down{0} ON down{0}.term_parent = {1}.term_id "\
                .format(curLevel, lastLevel)
            i += 1
        if queryArgs['extra']:
            sql += "\nWHERE (root.term_parent is NULL) AND ({})".format(queryArgs['extra'])
        else:
            sql += "\nWHERE (root.term_parent is NULL) AND (root.term_taxonomy = '{}')".format(queryArgs['tax'])
        sql += "\nORDER BY root_name"
        i = 1
        while i <= catLvls:
            curLevel = str(i)
            sql += ", down{}_name".format(curLevel)

            i += 1
        query = QSqlQuery(self.con)
        query.setForwardOnly(True)
        query.exec_(sql)
        self.logger.debug(sql)
        pool = []
        categories = []
        while query.next():
            rootIdIndex = query.record().indexOf("root_id")
            rootNameIndex = query.record().indexOf("root_name")
            if query.value(rootIdIndex) not in pool and query.value(rootNameIndex) is not '':
                c = {'id': query.value(rootIdIndex),
                     'name': query.value(rootNameIndex),
                     'level': 0}
                if selectComplete:
                    c['slug'] = query.value(query.record().indexOf("root_slug"))
                    c['count'] = query.value(query.record().indexOf("root_count"))
                    c['tax'] = query.value(query.record().indexOf("root_tax"))
                categories.append(c)
            pool.append(query.value(rootIdIndex))
            i = 1
            while i <= catLvls:
                curLevel = str(i)
                downIdIndex = query.record().indexOf("down{}_id".format(curLevel))
                downNameIndex = query.record().indexOf("down{}_name".format(curLevel))
                if query.value(downIdIndex) not in pool and query.value(downNameIndex) is not '':
                    c = {'id': query.value(downIdIndex),
                         'name': query.value(downNameIndex),
                         'level': i}
                    if selectComplete:
                        c['slug'] = query.value(query.record().indexOf("down{}_slug".format(curLevel)))
                        c['count'] = query.value(query.record().indexOf("down{}_count".format(curLevel)))
                        c['tax'] = query.value(query.record().indexOf("down{}_tax".format(curLevel)))
                    categories.append(c)
                pool.append(query.value(downIdIndex))
                i += 1
        return categories

    def selectRelations(self, itemID):
        query = QSqlQuery("SELECT term_id FROM term_relationships AS tr "
                          "WHERE (tr.item_id= '{}')".format(itemID), self.con)
        return query

    def selectRelatedTags(self, itemID, taxonomy="tag"):
        query = QSqlQuery("SELECT t.term_name from terms AS t "
                          "INNER JOIN term_relationships AS tr ON (tr.term_id = t.term_id) "
                          "WHERE (tr.item_id = {}) AND (t.term_taxonomy = '{}')".format(itemID, taxonomy),
                          self.con)
        return query

    def selectCount(self, table="items"):
        query = QSqlQuery('SELECT COUNT(*) FROM {}'.format(table), self.con)
        if query.first():
            count = query.value(0)
            self.logger.debug(table+" count: "+str(count))
            return count

    def selectCountRelations(self, iden, col="item_id"):
        query = QSqlQuery('SELECT COUNT(*) FROM term_relationships '
                          'WHERE {} = "{}"'.format(col, iden), self.con)
        if query.first():
            count = query.value(0)
            return count

    def selectOption(self, option):
        query = QSqlQuery('SELECT option_value FROM options WHERE option_name = "{}"'.format(option),
                          self.con)
        if query.first():
            optionValue = query.value(0)
            self.logger.debug("Option {}: {}".format(option, optionValue))
            return unquote(optionValue)

    def selectOptions(self):
        return QSqlQuery('SELECT option_name, option_value FROM options', self.con)

    def selectItemTypes(self):
        return QSqlQuery('SELECT * FROM item_types', self.con)

    def selectTaxonomies(self):
        return QSqlQuery('SELECT * FROM taxonomies', self.con)

    def selectDistinctItemTypes(self):
        return QSqlQuery('SElECT DISTINCT type_id from items', self.con)

    def selectDistinctTaxonomies(self):
        return QSqlQuery('SElECT DISTINCT term_taxonomy from terms', self.con)

    def selectCopypasta(self, itemIdens):
        query = QSqlQuery(self.con)
        query.setForwardOnly(True)
        SQL = "Select item_name, item_source, item_description, type_id FROM items " \
              "WHERE item_id IN ({})".format(", ".join(itemIdens))
        self.logger.debug('\n'+SQL)
        query.exec_(SQL)
        return query

    def selectCopypastaFromCategories(self, catIdens):
        query = QSqlQuery(self.con)
        query.setForwardOnly(True)
        SQL = "Select DISTINCT i.item_name, i.item_source, i.item_description, i.type_id, i.item_id FROM items AS i " \
              "INNER JOIN term_relationships AS tr ON (tr.item_id = i.item_id) " \
              "WHERE tr.term_id IN ({})".format(", ".join(catIdens))
        self.logger.debug('\n'+SQL)
        query.exec_(SQL)
        return query

    def incrementTermCount(self, catid):
        QSqlQuery("UPDATE terms SET term_count = term_count + 1 "
                  "WHERE term_id = '{}'".format(catid), self.con)
        return True

    def decrementTermCount(self, catid):
        QSqlQuery("UPDATE terms SET term_count = term_count - 1 "
                  "WHERE term_id = '{}'".format(catid), self.con)
        return True

    def checkRelation(self, itemID, taxID):
        query = QSqlQuery("SELECT * FROM term_relationships AS tr "
                          "WHERE (tr.item_id = '{}') AND (tr.term_id = '{}')".format(itemID, taxID),
                          self.con)
        if query.first():
            return True

    def insertOption(self, option, value):
        SQL = str()
        if self.config['type'] == 'mysql':
            SQL = "INSERT INTO options(option_name, option_value) \n" \
                  "VALUES('{0}', '{1}') \n" \
                  "ON DUPLICATE KEY UPDATE option_id=LAST_INSERT_ID(option_id), " \
                  "option_value='{1}'".format(option, value)
            QSqlQuery(SQL, self.con)
        elif self.config['type'] == 'sqlite':
            SQL = "INSERT OR REPLACE INTO options (option_id, option_name, option_value) \n" \
                  "SELECT old.option_id, new.option_name, new.option_value \n" \
                  "FROM ( SELECT '{}' AS option_name, '{}' AS option_value ) AS new \n" \
                  "LEFT JOIN ( SELECT option_id, option_name, option_value FROM options ) AS old \n" \
                  "ON new.option_name = old.option_name;".format(option, value)
            QSqlQuery(SQL, self.con)
        self.logger.debug('\n'+SQL)
        return True

    def insertItemType(self, data):
        if data.get('table_name') is None or data.get('plural_name') is None:
            self.logger.error("Error creating new item type: field is missing.")
            return False
        else:
            SQL = str()
            if self.config['type'] == 'mysql':
                SQL = "INSERT INTO item_types(noun_name, plural_name, dir_name, " \
                      "table_name, icon_name, enabled, extensions) \n" \
                      "VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}')" \
                    .format(data['noun_name'], data['plural_name'], data['dir_name'], data['table_name'],
                            data['icon_name'], data['enabled'], data['extensions'])
                QSqlQuery(SQL, self.con)
            elif self.config['type'] == 'sqlite':
                SQL = "INSERT INTO item_types (noun_name, plural_name, dir_name, " \
                      "table_name, icon_name, enabled, extensions) \n" \
                      "VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}')" \
                    .format(data['noun_name'], data['plural_name'], data['dir_name'], data['table_name'],
                            data['icon_name'], data['enabled'], data['extensions'])
                QSqlQuery(SQL, self.con)
            self.logger.debug('\n'+SQL)
            return True

    def insertTaxonomy(self, data):
        if data.get('table_name') is None or data.get('plural_name') is None:
            self.logger.error("Error creating new taxonomy: field is missing.")
            return False
        else:
            SQL = str()
            if self.config['type'] == 'mysql':
                SQL = "INSERT INTO taxonomies(noun_name, plural_name, dir_name, " \
                      "table_name, icon_name, enabled, has_children, is_tags) \n" \
                      "VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')" \
                    .format(data['noun_name'], data['plural_name'], data['dir_name'], data['table_name'],
                            data['icon_name'], data['enabled'], data['has_children'], data['is_tags'])
                QSqlQuery(SQL, self.con)
            elif self.config['type'] == 'sqlite':
                SQL = "INSERT INTO taxonomies (noun_name, plural_name, dir_name, " \
                      "table_name, icon_name, enabled, has_children, is_tags) \n" \
                      "VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')" \
                    .format(data['noun_name'], data['plural_name'], data['dir_name'], data['table_name'],
                            data['icon_name'], data['enabled'], data['has_children'], data['is_tags'])
                QSqlQuery(SQL, self.con)
            self.logger.debug('\n'+SQL)
            return True

    def deleteAllData(self):
        query = QSqlQuery(self.con)
        query.exec_("DELETE FROM items;")
        query.exec_("DELETE FROM terms;")
        query.exec_("DELETE FROM term_relationships;")
        if self.config['type'] == 'mysql':
            query.exec_("ALTER TABLE terms AUTO_INCREMENT = 1;")
            query.exec_("ALTER TABLE items AUTO_INCREMENT = 1;")
            query.exec_("UPDATE SQLITE_SEQUENCE SET seq = 0 WHERE name = 'terms';")
            query.exec_("UPDATE SQLITE_SEQUENCE SET seq = 0 WHERE name = 'items';")
        self.logger.info("Data successfully deleted.")
        return True

    def dropDatabase(self):
        if self.config['type'] == 'mysql':
            SQL = "DROP DATABASE `{}`".format(self.config['db'])
            self.logger.debug('\n'+SQL)
            QSqlQuery(SQL, self.con)
        elif self.config['type'] == 'sqlite':
            os.remove(self.config['db'])
        self.logger.info("Database successfully dropped.")
        return True

    def vacuumDatabase(self):
        if self.config['type'] == 'sqlite':
            QSqlQuery("VACUUM", self.con)
            self.logger.info("Database Vacuumed.")