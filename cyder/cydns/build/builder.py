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


STEM = 'gen2/dns/stage'


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


class DNSBuilder(object):
    def __init__(self):
        pass

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

        config_dir = path.join(STEM, 'config')
        try:
            os.makedirs(config_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        rev_dir = path.join(STEM, 'reverse')
        try:
            os.makedirs(rev_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        for v in views:
            config[v.pk] = open(
                path.join(config_dir, 'master.' + v.name), 'w')

        for s in SOA.objects.filter(dns_enabled=True):
            if s.is_reverse:
                suffix = list(islice(
                    reversed(s.root_domain.name.split('.')),
                    0, 2))
                suffix = '.'.join(reversed(suffix))

                f_dir = path.join(
                    rev_dir,
                    suffix
                )
            else:
                f_dir = path.join(
                    STEM,
                    '/'.join(list(reversed(s.root_domain.name.split('.'))))
                )

            try:
                os.makedirs(f_dir)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            f_name_base = path.join(f_dir, s.root_domain.name)

            new_serial = -1

            for v in views:
                f_name = f_name_base + '.' + v.name

                config[v.pk].write(CONFIG_ZONE.format(
                    zone_name=s.root_domain.name, f_name=f_name))

                file_serial = get_serial(f_name)
                if s.dirty or file_serial != s.serial or force:
                    new_serial = max(
                        new_serial - 1, s.serial, time_serial - 1,
                        file_serial) + 1

            if new_serial > -1:
                for v in views:
                    f_name = f_name_base + '.' + v.name
                    print f_name
                    with open(f_name, 'wb') as f:
                        f.write(s.dns_build(view=v, serial=new_serial))

                cache[s.pk] = CachedSOA(
                    old_serial=s.serial, new_serial=new_serial,
                    modified=s.modified)

        for pk, c in cache.iteritems():
            SOA.objects.filter(pk=pk, modified=c.modified).update(
                dirty=False, serial=c.new_serial)

        for f in config.itervalues():
            f.close()
