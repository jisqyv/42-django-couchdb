from time import time
from itertools import izip

import couchdb


__all__ = ('ConnectionWrapper', 'CursorWrapper', 'DatabaseError',
           'DebugCursorWrapper', 'IntegrityError', 'InternalError',
           'SQL', 'Sequence')

DatabaseError = couchdb.ServerError
IntegrityError = couchdb.ResourceConflict

class Sequence(object):
    def __init__(self, server, name):
        if not 'sequences' in server.__iter__():
            table = server.create('sequences')
        else:
            table = server['sequences']

        try:
            seq = table[name]
        except couchdb.ResourceNotFound:
            seq = {'nextval': 1}
        self._nextval = seq['nextval']
        seq['nextval']=seq['nextval'] + 1
        table[name] = seq

    def nextval(self): # doesn't increment
        return self._nextval

    def currval(self):
        return self._nextval - 1

class InternalError(DatabaseError):
    """
    @summary: Exception raised when the database encounters an internal error,
    e.g. the cursor is not valid anymore, the transaction is out of sync, etc.
    It must be a subclass of DatabaseError.
    """

class SQL(object):
    def __init__(self, command, params):
        self.command = command
        self.params = params

    def execute_create(self, server):
        # params --- (model opts, field_params)
        opts = self.params[0]
        table = server.create(opts.db_table)
        meta = {'_id': '_meta'}
        if opts.unique_together:
            meta['UNIQUE'] = list(opts.unique_together)
        for field, field_params in self.params[1].iteritems():
            params_list = []
            for param, value in field_params.iteritems():
                if value:
                    params_list.append(param)
            meta[field] = params_list
        table['_meta'] = meta

    def execute_add_foreign_key(self, server):
        # params - (r_table, r_col, table)
        table = server[self.params[0]]
        meta = table['_meta']
        try:
            refs = meta['REFERENCES']
        except KeyError:
            refs = []
        refs.append('%s=%s' % (self.params[1], self.params[2]))
        meta['REFERENCES'] = refs
        table['_meta'] = meta

    def execute_insert(self, server, params):
        # params --- (table name, columns, values)
        table = server[self.params[0]]
        seq = Sequence(server, ("%s_seq"% (self.params[0], )))
        id = str(seq.nextval())
        obj = {'_id': id}
        for key, view, val in izip(self.params[1], self.params[2], params):
            obj[key] = view % val
        table[id] = obj

    def execute_sql(self, server, params):
        if self.command == 'create':
            return self.execute_create(server)
        elif self.command == 'add_foreign_key':
            return self.execute_add_foreign_key(server)
        elif self.command == 'insert':
            return self.execute_insert(server, params)

    def __unicode__(self):
        return u"command %s with params = %s" % (self.command, self.params)

class ConnectionWrapper(object):
    """
    @summary: DB-API 2.0 Connection object for Django CouchDB backend.
    """
    def __init__(self, host, username, password, cache=None, timeout=None):
        self._cursor = None
        self._server = couchdb.Server(host, cache, timeout)
        self._username, self._password = username, password

    def close(self):
        if self._server is not None:
            self._server = None

    def commit(self):
        #~ raise NotImplementedError
        pass

    def cursor(self):
        if self._server is None:
            raise InternalError, 'Connection to server was closed.'

        if self._cursor is None:
            self._cursor = CursorWrapper(self._server,
                                         self._username,
                                         self._password)
        return self._cursor

    def rollback(self):
        raise NotImplementedError

class CursorWrapper(object):
    """
    @summary: DB-API 2.0 Cursor object for Django CouchDB backend.
    """
    def __init__(self, server, username=None, password=None):
        assert isinstance(server, couchdb.Server), \
            'Please, supply ``couchdb.Server`` instance as first argument.'

        self.server = server
        self._username, self._password = username, password

    def execute(self, sql, params=()):
        if isinstance(sql, SQL):
            sql.execute_sql(self.server, params)

class DebugCursorWrapper(CursorWrapper):
    """
    @summary: Special cursor class, that stores all queries to database for
    current session.
    """
    def __init__(self, cursor):
        super(DebugCursorWrapper, self).__init__(cursor.server,
                                                 cursor._username,
                                                 cursor._password)

    def execute(self, sql, params=()):
        start = time()
        try:
            super(DebugCursorWrapper, self).execute(sql, params)
        finally:
            stop = time()
            #~ sql = self.db.ops.last_executed_query(self.cursor, sql, params)
            #~ self.db.queries.append({
                #~ 'sql': sql,
                #~ 'time': "%.3f" % (stop - start),
            #~ })



