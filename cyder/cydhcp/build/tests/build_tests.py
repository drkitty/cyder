import errno
import os

from django.conf import settings
from django.test import TestCase

from activate import cy_path
from cyder.base.eav.models import Attribute
from cyder.base.utils import (
    copy_tree, dict_merge, remove_dir_contents, SanityCheckFailure)
from cyder.core.system.models import System
from cyder.cydhcp.build.build import dhcp_build
from cyder.cydhcp.interface.dynamic_intr.models import DynamicInterface
from cyder.cydhcp.network.models import Network, NetworkAV
from cyder.cydhcp.range.models import Range


DHCPBUILD = dict_merge(settings.DHCPBUILD, {
    'stage_dir': '/tmp/cyder_dhcp_test/stage',
    'prod_dir': '/tmp/cyder_dhcp_test/prod',
    'lock_file': '/tmp/cyder_dhcp_test.lock',
    'pid_file': '/tmp/cyder_dhcp_test.pid',
    'stop_file': '/tmp/cyder_dhcp_test.stop',
    'files_v4': {
        'target_file': 'dhcpd.conf',
        'check_file': None,
    },
    'files_v6': {
        'target_file': 'dhcpd.conf.6',
        'check_file': None,
    },
})


class DHCPBuildTest(TestCase):
    fixtures = ['dhcp_build_test.json']

    def build(self, sanity_check=True, size_decrease_limit=10000,
            size_increase_limit=10000):
        try:
            os.remove(DHCPBUILD['stop_file'])
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        DHCPBUILD['size_decrease_limit'] = size_decrease_limit
        DHCPBUILD['size_increase_limit'] = size_increase_limit
        with self.settings(DHCPBUILD=DHCPBUILD, ENABLE_FAIL_MAIL=False):
            return dhcp_build(sanity_check=sanity_check, to_syslog=False)

    def setUp(self):
        if not os.path.isdir(DHCPBUILD['stage_dir']):
            os.makedirs(DHCPBUILD['stage_dir'])
        copy_tree(
            'cyder/cydhcp/build/tests/files/',
            cy_path(DHCPBUILD['stage_dir']))

        if not os.path.isdir(DHCPBUILD['prod_dir']):
            os.makedirs(DHCPBUILD['prod_dir'])
        remove_dir_contents(DHCPBUILD['prod_dir'])

        super(DHCPBuildTest, self).setUp()

    def test_change_data(self):
        """Test that changing data triggers a rebuild"""

        self.assertGreater(
            self.build(sanity_check=False)['size_diff'],
            0)

        self.assertEqual(
            self.build(sanity_check=False)['size_diff'],
            0)

        NetworkAV.objects.create(
            entity=Network.objects.get(network_str='192.168.0.0/16'),
            attribute=Attribute.objects.get(attribute_type='o',
                                            name='routers'),
            value='192.168.0.1',
        )

        self.assertGreater(
            self.build(sanity_check=False)['size_diff'],
            0)

    def test_sanity_check_increase(self):
        """Test sanity check when size increases"""

        self.build(sanity_check=False)

        d = DynamicInterface.objects.create(
            system=System.objects.get(name='Test_system_5'),
            mac='ab:cd:ef:ab:cd:ef',
            range=Range.objects.get(name='Test range 1'),
        )

        self.assertRaises(
            SanityCheckFailure, self.build,
            size_decrease_limit=0,  # No decrease allowed.
            size_increase_limit=1)

        self.build(
            size_decrease_limit=0,  # No decrease allowed.
            size_increase_limit=1000)

    def test_sanity_check_no_change(self):
        """Test sanity check when size doesn't change"""

        self.build(sanity_check=False)

        DynamicInterface.objects.get(mac='01:02:04:08:10:20').save()

        self.build(
            size_decrease_limit=0,  # No decrease allowed.
            size_increase_limit=0)  # No increase allowed.

    def test_sanity_check_decrease(self):
        """Test sanity check when size decreases"""

        self.build(sanity_check=False)

        DynamicInterface.objects.get(mac='aa:bb:cc:dd:ee:ff').delete()

        self.assertRaises(
            SanityCheckFailure, self.build,
            size_decrease_limit=1,
            size_increase_limit=0)  # No increase allowed

        self.build(
            size_decrease_limit=1000,
            size_increase_limit=0)  # No increase allowed
