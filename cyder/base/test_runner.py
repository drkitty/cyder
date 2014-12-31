from optparse import make_option

import MySQLdb
from django.conf import settings
from django.core.management import call_command
from django.db import connection
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
        connection.settings_dict['NAME'] = (
            connection.creation._get_test_db_name())
        if self.recreate_db:
            cur, name = get_cursor('default', use=False)
            try:
                cur.execute('DROP DATABASE `{}`'.format(name))
            except MySQLdb.OperationalError:
                pass
            cur.execute(
                'CREATE DATABASE `{}` CHARACTER SET ascii '
                'COLLATE ascii_general_ci'.format(name))
                #connection.creation.create_test_db(autoclobber=True)
            call_command('syncdb', interactive=False)

    def teardown_databases(self, *args, **kwargs):
        # Don't remove test databases.
        pass
