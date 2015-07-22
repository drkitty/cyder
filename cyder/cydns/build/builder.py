from __future__ import unicode_literals


import errno
import os
from collections import namedtuple
from datetime import datetime
from itertools import islice
from os import path
from time import mktime

from django.conf import settings

from cyder.base.utils import transaction_atomic
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


# FIXME: There's really no reason for this to be a class at the moment.
class DNSBuilder(object):
    @transaction_atomic
    def build(self, force=False):
        times = BuildTime.objects.get()
        old_start = times.start
        times.start = datetime.now()
        times.save(commit=False)

        time_serial = int(mktime(times.start.timetuple()))
        cache = {}
        views = View.objects.all()

        config = {}

        build_dir = settings.DNSBUILD['stage_dir']
        bind_dir = settings.DNSBUILD['bind_prefix']
        config_dir = 'config'
        rev_dir = 'reverse'

        for d in (config_dir, rev_dir):
            try:
                os.makedirs(path.join(build_dir, d))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        for v in views:
            config[v.pk] = open(
                path.join(build_dir, config_dir, 'master.' + v.name), 'w')

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

            try:
                os.makedirs(path.join(build_dir, f_dir))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            new_serial = -1

            f_name_prefix = path.join(f_dir, s.root_domain.name)

            for v in views:
                f_name = f_name_prefix + '.' + v.name

                config[v.pk].write(CONFIG_ZONE.format(
                    zone_name=s.root_domain.name,
                    f_name=path.join(bind_dir, f_name)))

                file_serial = get_serial(path.join(build_dir, f_name))
                if s.dirty or file_serial != s.serial or force:
                    new_serial = max(
                        new_serial - 1, s.serial, time_serial - 1,
                        file_serial) + 1

            if new_serial > -1:
                for v in views:
                    f_name = f_name_prefix + '.' + v.name
                    print f_name
                    with open(path.join(build_dir, f_name), 'wb') as f:
                        f.write(s.dns_build(view=v, serial=new_serial))

                cache[s.pk] = CachedSOA(
                    old_serial=s.serial, new_serial=new_serial,
                    modified=s.modified)

        for pk, c in cache.iteritems():
            SOA.objects.filter(pk=pk, modified=c.modified).update(
                dirty=False, serial=c.new_serial)

        for f in config.itervalues():
            f.close()
