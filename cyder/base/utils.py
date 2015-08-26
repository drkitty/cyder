import distutils.dir_util
import errno
import fcntl
import operator
import os
import shlex
import shutil
import subprocess
import syslog
import time
from copy import copy
from os import path
from sys import stderr

import MySQLdb
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q
from django.db.models.loading import get_model

from activate import ROOT
from cyder.base.tablefier import Tablefier


class StopFileExists(Exception):
    pass


def copy_tree(*args, **kwargs):
    distutils.dir_util._path_created = {}
    distutils.dir_util.copy_tree(*args, **kwargs)


def shell_out(command, use_shlex=True):
    """
    A little helper function that will shell out and return stdout,
    stderr, and the return code.
    """
    if use_shlex:
        command_args = shlex.split(command)
    else:
        command_args = command
    p = subprocess.Popen(command_args, stderr=subprocess.PIPE,
                         stdout=subprocess.PIPE)
    out, err = p.communicate()
    return out, err, p.returncode


class Logger(object):
    """
    A Logger logs messages passed to it. Possible destinations include stderr
    and the system journal (syslog).
    """

    def log_debug(self, msg):
        pass

    def log_info(self, msg):
        pass

    def log_notice(self, msg):
        pass

    def error(self, msg):
        raise Exception(msg)


class UnixLogger(Logger):
    def __init__(self, to_syslog, verbosity):
        self.to_syslog = to_syslog
        self.verbosity = verbosity

    def log(self, log_level, msg):
        if self.to_syslog:
            for line in msg.splitlines():
                syslog.syslog(log_level, line)

    def log_debug(self, msg):
        self.log(syslog.LOG_DEBUG, msg)
        if self.verbosity >= 2:
            print msg

    def log_info(self, msg):
        self.log(syslog.LOG_INFO, msg)
        if self.verbosity >= 1:
            print msg

    def log_notice(self, msg):
        self.log(syslog.LOG_NOTICE, msg)
        print msg

    def error(self, msg, set_stop_file=True):
        self.log(syslog.LOG_ERR, msg)
        raise Exception(msg)


class SanityCheckFailure(Exception):
    pass


def build_sanity_check(size_diff, size_increase_limit, size_decrease_limit):
    if size_increase_limit is not None and size_diff > size_increase_limit:
        raise SanityCheckFailure(
            "Size increase ({}) exceeds limit ({})".format(
                size_diff, size_increase_limit))

    if size_decrease_limit is not None and -size_diff > size_decrease_limit:
        raise SanityCheckFailure(
            "Size decrease ({}) exceeds limit ({})".format(
                -size_diff, size_decrease_limit))


def run_command(command, logger=Logger(), ignore_failure=False,
                failure_msg=None):
    # A single default Logger instance is shared between every call to this
    # function. Keep that in mind if you give Logger more state.
    logger.log_debug('Calling `{0}` in {1}'.format(command, os.getcwd()))
    out, err, returncode = shell_out(command)
    if returncode != 0 and not ignore_failure:
        msg = '{}: '.format(failure_msg) if failure_msg else ''
        msg += '`{}` failed in {}\n\n'.format(
            command, os.getcwd())
        if out:
            msg += '=== stdout ===\n{0}\n'.format(out)
        if err:
            msg += '=== stderr ===\n{0}\n'.format(err)
        msg = msg.rstrip('\n') + '\n'
        logger.error(msg)
    return out, err, returncode


def set_attrs(obj, attrs):
    for name, value in attrs.iteritems():
        setattr(obj, name, value)


def dict_merge(*dicts):
    """Later keys override earlier ones"""
    return dict(reduce(lambda x,y: x + y.items(), dicts, []))


def make_paginator(request, qs, num=20, obj_type=None):
    """
    Paginator, returns object_list.
    """
    page_name = 'page' if not obj_type else '{0}_page'.format(obj_type)
    paginator = Paginator(qs, num)
    paginator.page_name = page_name
    page = request.GET.get(page_name)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        return paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        return paginator.page(paginator.num_pages)


def tablefy(objects, users=False, extra_cols=None, request=None,
            update=True, detail_view=False, excluded=[]):
    """Make list of table headers, rows of table data, list of urls
    that may be associated with table data, and postback urls.

    :param  objects: A list of objects to make table from.
    :type   objects: Generic object.
    :param  extra_cols: Extra columns to add outside of objects' .details()
    :type  extra_cols: [{'header': '',
                         'data': [{'value': '',
                                   'url': ''}]
                       },]
    """
    t = Tablefier(objects, request=request, users=users,
                  extra_cols=extra_cols, update=update,
                  detail_view=detail_view, excluded=excluded)
    return t.get_table()


def make_megafilter(Klass, term):
    """
    Builds a query string that searches over fields in model's
    search_fields.
    """
    term = term.strip()
    megafilter = []
    for field in Klass.search_fields:
        if field == 'mac':
            megafilter.append(Q(**{"mac__icontains": term.replace(':', '')}))
        else:
            megafilter.append(Q(**{"{0}__icontains".format(field): term}))
    return reduce(operator.or_, megafilter)


def filter_by_ctnr(ctnr, Klass=None, objects=None):
    if not Klass and objects is not None:
        Klass = objects.model

    if ctnr.name in ['global', 'default']:
        if objects is None:
            return Klass.objects
        else:
            return objects

    return Klass.filter_by_ctnr(ctnr, objects)


def _filter(request, Klass):
    Ctnr = get_model('cyder', 'ctnr')
    if Klass is not Ctnr:
        objects = filter_by_ctnr(request.session['ctnr'], Klass)
    else:
        objects = Klass.objects

    if request.GET.get('filter'):
        try:
            objects = objects.filter(
                make_megafilter(Klass, request.GET.get('filter')))
        except TypeError:
            pass

    return objects.distinct()


def remove_dir_contents(dir_name):
    for file_name in os.listdir(dir_name):
        file_path = os.path.join(dir_name, file_name)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)


class classproperty(property):
    """Enables you to make a classmethod a property"""
    def __get__(self, cls, obj):
        return self.fget.__get__(None, obj)()


def simple_descriptor(func):
    class SimpleDescriptor(object):
        pass
    SimpleDescriptor.__get__ = func

    return SimpleDescriptor()


def django_pretty_type(obj_type):
    if obj_type == 'user':
        return 'user'
    else:
        return None


def transaction_atomic(func):
    """Make the outermost function run in a transaction

    This decorator should be used on any function that saves or deletes model
    instances. This includes `save` and `delete` methods.  An exception will
    roll back any changes performed during the outermost method. If a
    `transaction_atomic`-wrapped function calls another
    `transaction_atomic`-wrapped function (including itself), it should pass
    `commit=False`.

    Exceptions pass through this decorator intact.
    """

    def outer(*args, **kwargs):
        if kwargs.pop('commit', True):
            with transaction.commit_on_success():
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    outer.__name__ = func.__name__
    outer.__module__ = func.__module__
    outer.__doc__ = func.__doc__
    return outer


class savepoint_atomic(object):
    def __enter__(self):
        self.sid = transaction.savepoint()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            transaction.savepoint_rollback(self.sid)
        else:
            transaction.savepoint_commit(self.sid)


def get_cursor(alias, use=True):
    """Return a cursor for database `alias` and the name of the database.

    If `use` is False, don't pass the db argument.
    """
    if alias in settings.DATABASES:
        s = settings.DATABASES[alias]
        kwargs = {
            'host': s['HOST'],
            'port': int(s['PORT'] or '0'),
            'db': s['NAME'],
            'user': s['USER'],
            'passwd': s['PASSWORD'],
        }
        kwargs.update(s['OPTIONS'])
        if use:
            kwargs['db'] = s['NAME']
    elif alias in settings.OTHER_DATABASES:
        kwargs = copy(settings.OTHER_DATABASES[alias])
    else:
        raise Exception('No such database in DATABASES or OTHER_DATABASES')
    conf = copy(kwargs)
    if not use:
        del kwargs['db']
    return MySQLdb.connect(**kwargs).cursor(), conf


def format_exc_verbose():
    import traceback
    s = 'Traceback (most recent call last):\n'
    for line in traceback.format_stack()[:-2]:
        s += line
    last_frame = traceback.format_exc()
    last_frame = last_frame[last_frame.find('\n')+1 : ]
    s += last_frame
    return s


def check_stop_file(filename, interval):
    """
    Returns (exists, reason, send_email). Periodically adjusts the mtime of the
    stop file to schedule future emails.
    """

    try:
        with open(filename) as stop_file:
            now = time.time()
            reason = stop_file.read()
        last_mod = os.path.getmtime(filename)

        send_email = now > last_mod and settings.ENABLE_FAIL_MAIL
        if send_email:
            future = now + settings.DNSBUILD['stop_file_email_interval']
            os.utime(settings.DNSBUILD['stop_file'], (future, future))

        return True, reason, send_email
    except IOError as e:
        if e.errno != errno.ENOENT:  # "No such file or directory"
            raise

    return False, None, False


class mutex(object):
    def __init__(self, lock_file, pid_file, logger):
        self.lock_file = lock_file
        self.pid_file = pid_file
        self.logger = logger

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unlock()

    def lock(self):
        if not os.path.exists(os.path.dirname(self.lock_file)):
            os.makedirs(os.path.dirname(self.lock_file))
        self.logger.log_debug("Attempting to lock {0}..."
                 .format(self.lock_file))

        self.lock_fd = open(self.lock_file, 'w')

        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as exc_value:
            self.lock_fd.close()
            # IOError: [Errno 11] Resource temporarily unavailable
            if exc_value[0] == 11:
                with open(self.pid_file, 'r') as pid_fd:
                    self._lock_failure(pid_fd.read())
            else:
                raise

        self.logger.log_debug("Lock acquired")

        try:
            with open(self.pid_file, 'w') as pid_fd:
                pid_fd.write(unicode(os.getpid()))
        except IOError as exc_value:
            # IOError: [Errno 2] No such file or directory
            if exc_value[0] == 2:
                self.logger.error(
                    "Failed to acquire lock on {0}, but the process that has "
                    "it hasn't written the PID file ({1}) yet.".format(
                        self.lock_file, self.pid_file))
            else:
                raise

    def unlock(self):
        if not self.lock_fd:
            return False

        self.logger.log_debug("Releasing lock ({0})...".format(self.lock_file))

        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        self.lock_fd.close()
        os.remove(self.pid_file)
        os.remove(self.lock_file)

        self.logger.log_debug("Unlock complete")
        return True

    def _lock_failure(self, pid):
        self.logger.error(
            'Failed to acquire lock on {0}. Process {1} currently '
            'has it.'.format(self.lock_file, pid))
