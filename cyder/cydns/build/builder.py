from __future__ import unicode_literals


import errno
import os
from os import path

from django.conf import settings

from cyder.cydns.soa.models import SOA
from cyder.cydns.view.models import View


STEM = 'gen2/dns/stage'


class DNSBuilder(object):
    def __init__(self):
        pass

    def build(self):
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

            for v in views:
                name = name_base + '.' + v.name
                print name
                with open(name, 'wb') as f:
                    f.write(s.dns_build(view=v))
