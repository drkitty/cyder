import errno
import os
import shutil
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from time import sleep

from cyder.base.utils import (
    dict_merge, remove_dir_contents, SanityCheckFailure)
from cyder.core.system.models import System
from cyder.cydhcp.interface.static_intr.models import StaticInterface
from cyder.cydhcp.range.models import Range
from cyder.cydns.build.build import dns_build
from cyder.cydns.cname.models import CNAME
from cyder.cydns.domain.models import Domain
from cyder.cydns.view.models import View


DNSBUILD = dict_merge(settings.DNSBUILD, {
    'stage_dir': '/tmp/cyder_dns_test/stage',
    'prod_dir': '/tmp/cyder_dns_test/prod',
    'bind_prefix': '',
    'lock_file': '/tmp/cyder_dns_test.lock',
    'pid_file': '/tmp/cyder_dns_test.pid',
    'size_decrease_limit': 10,
    'size_increase_limit': 500,
    'stop_file': '/tmp/cyder_dns_test.stop',
    'log_syslog': False,
})


class DNSBuildTest(TestCase):
    fixtures = ['dns_build_test.json']

    def build(self, rebuild_all=False, sanity_check=True,
            size_increase_limit=10000, size_decrease_limit=10000):
        try:
            os.remove(DNSBUILD['stop_file'])
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        DNSBUILD['size_increase_limit'] = size_increase_limit
        DNSBUILD['size_decrease_limit'] = size_decrease_limit
        with self.settings(DNSBUILD=DNSBUILD, ENABLE_FAIL_MAIL=False):
            return dns_build(
                rebuild_all=rebuild_all, sanity_check=sanity_check)

    def setUp(self):
        if not os.path.isdir(DNSBUILD['stage_dir']):
            os.makedirs(DNSBUILD['stage_dir'])

        if not os.path.isdir(DNSBUILD['prod_dir']):
            os.makedirs(DNSBUILD['prod_dir'])
        remove_dir_contents(DNSBUILD['prod_dir'])

        super(DNSBuildTest, self).setUp()

    def test_rebuild_all(self):
        """Test that the 'rebuild_all' argument works"""

        self.assertGreater(
            self.build(rebuild_all=True, sanity_check=False),
            0)

        self.assertEqual(
            self.build(sanity_check=False),
            0)

        self.assertGreater(
            self.build(rebuild_all=True, sanity_check=False),
            0)

    def test_soa_dirty(self):
        """Test that the SOA.dirty flag works."""

        self.assertGreater(
            self.build(rebuild_all=True, sanity_check=False),
            0)

        CNAME.objects.get(fqdn='foo.example.com').delete()

        self.assertEqual(
            self.build(sanity_check=False),
            1)

        s = StaticInterface.objects.get(fqdn='www.example.com')
        s.domain.soa.dirty = True
        s.domain.soa.save()

        self.assertEqual(
            self.build(sanity_check=False),
            1)

    def test_sanity_check_increase(self):
        """Test sanity check when size increases"""

        self.build(rebuild_all=True, sanity_check=False)

        sys = System.objects.get(name='Test system')
        s = StaticInterface.objects.create(
            system=sys,
            label='www3',
            domain=Domain.objects.get(name='example.com'),
            ip_str='192.168.0.50',
            mac='01:23:45:01:23:45',
        )
        s.views.add(
            View.objects.get(name='public'),
            View.objects.get(name='private'))

        self.assertRaises(
            SanityCheckFailure, self.build,
            size_decrease_limit=0,  # No decrease allowed.
            size_increase_limit=1,
        )

        self.build(
            size_decrease_limit=0,  # No decrease allowed.
            size_increase_limit=1000,
        )

    def test_sanity_check_decrease(self):
        """Test sanity check when line count decreases"""

        self.build(rebuild_all=True, sanity_check=False)

        CNAME.objects.get(fqdn='foo.example.com').delete()
        StaticInterface.objects.filter(
            fqdn__in=('www.example.com', 'www2.example.com')).delete()

        self.assertRaises(
            SanityCheckFailure, self.build,
            size_decrease_limit=1,
            size_increase_limit=0,  # No increase allowed.
        )

        self.build(
            size_decrease_limit=1000,
            size_increase_limit=0,  # No increase allowed.
        )
