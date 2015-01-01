from optparse import make_option
from sys import exit

import MySQLdb
import nose
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test.simple import DjangoTestSuiteRunner

from cyder.base.utils import get_cursor


class CorrectTestSuiteRunner(DjangoTestSuiteRunner):
    option_list = tuple(filter(
        lambda x: (
            '-h' not in x._short_opts and '--version' not in x._long_opts),
        nose.config.Config().getParser().option_list
    )) + (
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
            call_command('syncdb', interactive=False)

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        return test_labels

    def run_suite(self, suite, **kwargs):
        print suite
        class Nothing(object):
            failures = ()
            errors = ()
        exit(int(not nose.run(*suite, **kwargs)))

    def teardown_databases(self, *args, **kwargs):
        # Don't remove test databases.
        pass
