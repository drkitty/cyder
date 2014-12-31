from optparse import make_option

import MySQLdb
from django.db import connections
from django.test.simple import DjangoTestSuiteRunner

from cyder.base.utils import get_cursor


class CorrectTestSuiteRunner(DjangoTestSuiteRunner):
    option_list = (
        make_option('-r', '--recreate-db',
                    action='store_true',
                    dest='recreate_db',
                    help='Recreate the test database'),
    )

    def __init__(self, **options):
        self.recreate_db = options.pop('recreate_db', False)
        super(CorrectTestSuiteRunner, self).__init__(**options)

    def setup_databases(self, **kwargs):
        """
        Note: This function doesn't properly handle databases that are set as
        test mirrors.
        """
        old_names = []
        for connection in connections.all():
            old_name = connection.settings_dict['NAME']
            old_names.append(
                (connection, old_name, True))
            connection.settings_dict['NAME'] = 'test_' + old_name

        if self.recreate_db:
            cur, db = get_cursor('default', use=False)
            try:
                print 'Dropping test database...'
                cur.execute('DROP DATABASE `{}`'.format(db))
            except MySQLdb.OperationalError:
                pass
            print 'Creating test database...'
            cur.execute(
                'CREATE DATABASE `{}` CHARACTER SET ascii '
                'COLLATE ascii_general_ci'.format(db))

        return old_names, []

    def teardown_databases(self, *args, **kwargs):
        # Don't remove test databases.
        pass
