from __future__ import unicode_literals


import errno
import os
from collections import namedtuple
from datetime import datetime
from os import path
from time import mktime

from django.conf import settings

from cyder.base.utils import transaction_atomic
from cyder.cydns.build.models import BuildTime
from cyder.cydns.soa.models import SOA
from cyder.cydns.view.models import View


STEM = 'gen2/dns/stage'


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

        for s in SOA.objects.filter(dns_enabled=True):
            d = path.join(
                STEM,
                'reverse' if s.is_reverse else '',
                '/'.join(list(reversed(s.root_domain.name.split('.'))))) + '/'

            try:
                os.makedirs(d)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            name_base = d + s.root_domain.name

            new_serial = -1

            for v in views:
                name = name_base + '.' + v.name
                file_serial = get_serial(name)
                if s.dirty or file_serial != s.serial or force:
                    new_serial = max(
                        new_serial - 1, s.serial, time_serial - 1,
                        file_serial) + 1

            if new_serial > -1:
                for v in views:
                    name = name_base + '.' + v.name
                    print name
                    with open(name, 'wb') as f:
                        f.write(s.dns_build(view=v, serial=new_serial))

                cache[s.pk] = CachedSOA(
                    old_serial=s.serial, new_serial=new_serial,
                    modified=s.modified)

        for pk, c in cache.iteritems():
            SOA.objects.filter(pk=pk, modified=c.modified).update(
                dirty=False, serial=c.new_serial)
