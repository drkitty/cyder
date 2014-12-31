#!/usr/bin/env python

import manage

import MySQLdb
from django.conf import settings

from cyder.base.utils import get_cursor


def main():
    cur, name = get_cursor('default', use=False)
    # We can't use django.db.connection because the database might not exist.
    print 'Dropping Cyder database...'
    try:
        cur.execute('DROP DATABASE `{}`'.format(name))
    except MySQLdb.OperationalError:
        pass

    print 'Creating Cyder database...'
    cur.execute(
        'CREATE DATABASE `{}` CHARACTER SET ascii '
        'COLLATE ascii_general_ci'.format(name))


if __name__ == '__main__':
    main()
