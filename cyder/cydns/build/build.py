from __future__ import unicode_literals


import errno
import os
import syslog
from collections import namedtuple
from datetime import datetime
from itertools import islice
from os import path
from time import mktime

from django.conf import settings

from cyder.base.utils import (
    build_sanity_check, check_stop_file, copy_tree, mutex, remove_dir_contents,
    run_command, transaction_atomic, UnixLogger)
from cyder.core.utils import dont_mail_if_failure, fail_mail, mail_if_failure
from cyder.cydns.build.models import BuildTime
from cyder.cydns.soa.models import SOA
from cyder.cydns.view.models import View


CONFIG_ZONE = """\
zone "{zone_name}" IN {{
    type master;
    file "{f_name}";
}};

"""


def get_serial(filename):
    try:
        with open(filename) as f:
            f.readline()
            line = f.readline()
            line = line.lstrip()
            line = line[:line.find(' ')]
            return int(line)
    except (IOError, ValueError):
        return -2


CachedSOA = namedtuple('CachedSOA', ('old_serial', 'new_serial', 'modified'))


ConfigFile = namedtuple('ConfigFile', ('f', 'name'))


class DNSBuildLogger(UnixLogger):
    def error(self, msg, set_stop_file=True):
        if set_stop_file:
            with open(settings.DNSBUILD['stop_file'], 'w') as f:
                f.write(msg)
        super(DNSBuildLogger, self).error(msg, set_stop_file=set_stop_file)


def check_zone(zonename, filename, logger):
    run_command(
        settings.DNSBUILD['named_checkzone'] + ' ' + zonename + ' ' + filename,
        logger=logger)


def check_conf(filename, logger):
    run_command(
        settings.DNSBUILD['named_checkconf'] + ' ' + filename,
        logger=logger)


@transaction_atomic
def dns_build(rebuild_all=False, dry_run=False, sanity_check=True, verbosity=0,
        to_syslog=False):
    l = DNSBuildLogger(to_syslog=to_syslog, verbosity=verbosity)

    with mail_if_failure("Cyder DNS build failed", logger=l), \
            mutex(
                lock_file=settings.DNSBUILD['lock_file'],
                pid_file=settings.DNSBUILD['pid_file'], logger=l):

        check_stop_file(
            "Cyder DNS build",
            filename=settings.DNSBUILD['stop_file'],
            interval=settings.DNSBUILD['stop_file_email_interval'])

        if rebuild_all:
            l.log_notice("Building all zones...")
        else:
            l.log_notice("Building out-of-date zones...")

        times = BuildTime.objects.get()
        old_start = times.start
        times.start = datetime.now()
        times.save(commit=False)

        time_serial = int(mktime(times.start.timetuple()))
        cache = {}
        views = View.objects.all()

        config = {}

        # Set up directories.

        stage_dir = settings.DNSBUILD['stage_dir']
        prod_dir = settings.DNSBUILD['prod_dir']
        bind_dir = settings.DNSBUILD['bind_prefix']
        config_dir = 'config'
        rev_dir = 'reverse'

        in_db = set()
        built = set()

        remove_dir_contents(stage_dir)
        if dry_run:
            copy_tree(prod_dir, stage_dir)

        for d in (config_dir, rev_dir):
            try:
                os.makedirs(path.join(stage_dir, d))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        # Open config files.

        for v in views:
            name = 'master.' + v.name
            config[v.pk] = ConfigFile(
                f=open(path.join(stage_dir, config_dir, name), 'w'), name=name)

        # Build zone files.

        zones_built = 0

        for s in SOA.objects.filter(dns_enabled=True):
            if s.is_reverse:
                last_two = list(islice(
                    reversed(s.root_domain.name.split('.')),
                    0, 2))

                f_dir = path.join(
                    rev_dir,
                    '.'.join(reversed(last_two))
                )
            else:
                f_dir = '/'.join(reversed(s.root_domain.name.split('.')))

            new_serial = -1

            f_name_prefix = path.join(f_dir, s.root_domain.name)

            for v in views:
                f_name = f_name_prefix + '.' + v.name

                config[v.pk].f.write(CONFIG_ZONE.format(
                    zone_name=s.root_domain.name,
                    f_name=path.join(bind_dir, f_name)))

                file_serial = get_serial(path.join(prod_dir, f_name))
                if s.dirty or file_serial != s.serial or rebuild_all:
                    new_serial = max(
                        new_serial - 1, s.serial, time_serial - 1,
                        file_serial) + 1

                in_db.add(f_name)

            if new_serial > -1:
                # For each view, build zone file and check it.

                try:
                    os.makedirs(path.join(stage_dir, f_dir))
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise

                for v in views:
                    f_name = f_name_prefix + '.' + v.name
                    l.log_debug("Building " + f_name)

                    f_path = path.join(stage_dir, f_name)

                    with open(f_path, 'wb') as f:
                        f.write(s.dns_build(view=v, serial=new_serial) + '\n')
                    check_zone(s.root_domain.name, f_path, logger=l)

                    built.add(f_name)

                cache[s.pk] = CachedSOA(
                    old_serial=s.serial, new_serial=new_serial,
                    modified=s.modified)

                zones_built += 1
            else:
                # For each view, check prod zone file.

                for v in views:
                    f_name = f_name_prefix + '.' + v.name
                    check_zone(
                        s.root_domain.name, path.join(prod_dir, f_name),
                        logger=l)


        # Close config files.

        for f, name in config.itervalues():
            f.close()
            check_conf(path.join(stage_dir, config_dir, name), l)

        # Get size difference between prod and stage.

        size_diff = 0
        to_remove = []
        to_rmdir = []

        striplen = len(prod_dir) + 1
        for dirpath, dirnames, filenames in os.walk(prod_dir, topdown=False):
            if dirpath.endswith('/' + config_dir):
                continue

            empty = True
            for filename in filenames:
                p = path.join(dirpath, filename)
                n = p[striplen:]

                prod_size = os.stat(p).st_size
                if n in in_db:
                    empty = False
                    if n in built:
                        stage_size = os.stat(path.join(stage_dir, n)).st_size
                        size_diff += stage_size - prod_size
                        built.remove(n)
                else:
                    size_diff -= prod_size
                    to_remove.append(p)

            if empty and all(
                    (path.join(dirpath, d) in to_rmdir) for d in dirnames):
                to_rmdir.append(dirpath)

        for n in built:
            size_diff += os.stat(path.join(stage_dir, n)).st_size

        l.log_notice("prod size - stage size = {}".format(size_diff))

        # Do sanity check.

        if sanity_check:
            build_sanity_check(
                size_diff, settings.DNSBUILD['size_increase_limit'],
                settings.DNSBUILD['size_decrease_limit'])

        # Sync to prod directory if requested.

        if dry_run:
            l.log_notice("Not syncing to production directory")
        else:
            l.log_notice("Syncing to production directory...")

            for n in to_remove:
                os.remove(n)
            for d in to_rmdir:
                os.rmdir(d)

            copy_tree(stage_dir, prod_dir)

            for pk, c in cache.iteritems():
                SOA.objects.filter(pk=pk, modified=c.modified).update(
                    dirty=False, serial=c.new_serial)

        l.log_notice("Build complete")

        return {
            'zones_built': zones_built,
            'size_diff': size_diff,
        }
