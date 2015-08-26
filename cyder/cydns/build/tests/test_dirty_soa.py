from cyder.core.system.models import System
from cyder.cydhcp.constants import STATIC
from cyder.cydhcp.interface.static_intr.models import StaticInterface
from cyder.cydhcp.network.models import Network
from cyder.cydhcp.range.models import Range
from cyder.cydns.address_record.models import AddressRecord
from cyder.cydns.cname.models import CNAME
from cyder.cydns.domain.models import Domain
from cyder.cydns.mx.models import MX
from cyder.cydns.nameserver.models import Nameserver
from cyder.cydns.ptr.models import PTR
from cyder.cydns.soa.models import SOA
from cyder.cydns.srv.models import SRV
from cyder.cydns.tests.utils import create_zone, DNSTest
from cyder.cydns.txt.models import TXT
from cyder.cydns.view.models import View


class DirtySOATests(DNSTest):
    def setUp(self):
        super(DirtySOATests, self).setUp()

        self.r1 = create_zone(name='10.in-addr.arpa')
        self.sr = self.r1.soa
        self.sr.dirty = False
        self.sr.save()

        Domain.objects.create(name='bgaz')
        self.dom = create_zone('azg.bgaz')
        self.soa = self.dom.soa
        self.soa.dirty = False
        self.soa.save()
        Domain.objects.create(name='com')
        Domain.objects.create(name='bar.com')
        create_zone('foo.bar.com')

        self.rdom = create_zone('123.in-addr.arpa')
        self.rsoa = self.r1.soa
        self.rsoa.dirty = False
        self.rsoa.save()

        self.ctnr.domains.add(self.dom, self.rdom)

        self.s = System.objects.create(name='test_system', ctnr=self.ctnr)

        self.net = Network.objects.create(network_str='10.2.3.0/30')
        self.range = Range.objects.create(
            network=self.net, range_type=STATIC, start_str='10.2.3.1',
            end_str='10.2.3.2')
        self.ctnr.ranges.add(self.range)

    def test_print_soa(self):
        v = View.objects.create(name='test_view')
        self.assertNotIn(self.soa.dns_build(serial=12, view=v), ('', None))
        self.assertNotIn(self.rsoa.dns_build(serial=12, view=v), ('', None))

    def generic_dirty(self, Klass, create_data, update_data, soa,
            build_args=()):
        SOA.objects.filter(pk=soa.pk).update(dirty=False)

        rec = Klass.objects.create(**create_data)
        self.assertNotIn(rec.dns_build(*build_args), ('', None))
        self.assertTrue(soa.reload().dirty)

        # Now try updating
        SOA.objects.filter(pk=soa.pk).update(dirty=False)
        self.assertFalse(soa.reload().dirty)
        for k, v in update_data.iteritems():
            setattr(rec, k, v)
        rec.save()
        self.assertTrue(soa.reload().dirty)

        # Now delete
        SOA.objects.filter(pk=soa.pk).update(dirty=False)
        self.assertFalse(soa.reload().dirty)
        rec.delete()
        self.assertTrue(soa.reload().dirty)

    def test_dirty_a(self):
        create_data = {
            'ctnr': self.ctnr,
            'label': 'asdf',
            'domain': self.dom,
            'ip_str': '10.2.3.1',
            'ip_type': '4',
        }
        update_data = {
            'label': 'asdfx',
        }
        self.generic_dirty(AddressRecord, create_data, update_data, self.soa)

    def test_dirty_intr(self):
        create_data = {
            'label': 'asdf1',
            'domain': self.dom,
            'ip_str': '10.2.3.1',
            'ip_type': '4',
            'system': self.s,
            'mac': '11:22:33:44:55:66',
        }
        update_data = {
            'label': 'asdfx1',
        }
        self.generic_dirty(
            StaticInterface, create_data, update_data, self.soa,
            build_args=(False,))

    def test_dirty_cname(self):
        create_data = {
            'ctnr': self.ctnr,
            'label': 'asdf2',
            'domain': self.dom,
            'target': 'foo.bar.com',
        }
        update_data = {
            'label': 'asdfx2',
        }
        self.generic_dirty(CNAME, create_data, update_data, self.soa)

    def test_dirty_ptr(self):
        create_data = {
            'ctnr': self.ctnr,
            'ip_str': '10.2.3.1',
            'ip_type': '4',
            'fqdn': 'foo.bar.com',
        }
        update_data = {
            'label': 'asdfx2',
        }
        self.generic_dirty(PTR, create_data, update_data, soa=self.sr)

    def test_dirty_mx(self):
        create_data = {
            'ctnr': self.ctnr,
            'label': '',
            'domain': self.dom,
            'priority': 10,
            'server': 'foo.bar.com',
        }
        update_data = {
            'label': 'asdfx3',
        }
        self.generic_dirty(MX, create_data, update_data, self.soa)

    def test_dirty_ns(self):
        create_data = {
            'domain': self.dom,
            'server': 'foo.bar.com',
        }
        update_data = {
            'label': 'asdfx4',
        }
        self.generic_dirty(Nameserver, create_data, update_data, self.soa)

    def test_dirty_srv(self):
        create_data = {
            'ctnr': self.ctnr,
            'label': '_asdf7',
            'domain': self.dom,
            'priority': 10,
            'port': 10,
            'weight': 10,
            'target': 'foo.bar.com',
        }
        update_data = {
            'label': '_asdfx4',
        }
        self.generic_dirty(SRV, create_data, update_data, self.soa)

    def test_dirty_txt(self):
        create_data = {
            'ctnr': self.ctnr,
            'label': 'asdf8',
            'domain': self.dom,
            'txt_data': 'some stuff',
        }
        update_data = {
            'label': 'asdfx5',
        }
        self.generic_dirty(TXT, create_data, update_data, self.soa)
