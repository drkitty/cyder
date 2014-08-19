from django.core.exceptions import ValidationError
from django.test import TestCase

from cyder.cydns.domain.models import Domain
from cyder.cydns.address_record.models import AddressRecord
from cyder.cydns.cname.models import CNAME
from cyder.cydns.soa.models import SOA
from cyder.cydns.ptr.models import PTR
from cyder.cydns.nameserver.models import Nameserver
from cyder.cydns.ip.utils import ip_to_domain_name
from cyder.cydns.tests.utils import create_fake_zone

from cyder.cydhcp.interface.static_intr.models import StaticInterface
from cyder.cydhcp.range.models import Range
from cyder.cydhcp.constants import STATIC
from cyder.cydhcp.network.models import Network
from cyder.core.system.models import System
from cyder.core.ctnr.models import Ctnr


class NSTestsModels(TestCase):
    def create_domain(self, name, ip_type='4', delegated=False):
        if name in ('arpa', 'in-addr.arpa', 'ip6.arpa'):
            pass
        else:
            name = ip_to_domain_name(name, ip_type=ip_type)
        d = Domain(name=name, delegated=delegated)
        d.clean()
        self.assertTrue(d.is_reverse)
        return d

    def setUp(self):
        self.ctnr = Ctnr(name='abloobloobloo')
        self.ctnr.save()
        self.arpa = self.create_domain(name='arpa')
        self.arpa.save()
        self.i_arpa = self.create_domain(name='in-addr.arpa')
        self.i_arpa.save()
        self.i6_arpa = self.create_domain(name='ip6.arpa')
        self.i6_arpa.save()

        self.r = Domain(name="ru")
        self.r.save()
        self.f_r = Domain(name="foo.ru")
        self.f_r.save()
        self.b_f_r = Domain(name="bar.foo.ru")
        self.b_f_r.save()
        Domain(name="asdf").save()

        self.f = Domain(name="fam")
        self.f.save()

        for d in [self.r, self.f_r, self.b_f_r, self.f]:
            self.ctnr.domains.add(d)

        self._128 = self.create_domain(name='128', ip_type='4')
        self._128.save()

        self.s = System()
        self.s.save()

        self.net1 = Network(network_str='128.193.0.0/17')
        self.net1.update_network()
        self.net1.save()
        self.sr1 = Range(network=self.net1, range_type=STATIC,
                         start_str='128.193.99.2', end_str='128.193.99.14')
        self.sr1.save()
        self.sr2 = Range(network=self.net1, range_type=STATIC,
                         start_str='128.193.1.1', end_str='128.193.1.14')
        self.sr2.save()

        self.net2 = Network(network_str='14.10.1.0/30')
        self.net2.update_network()
        self.net2.save()
        self.sr3 = Range(network=self.net2, range_type=STATIC,
                         start_str='14.10.1.1', end_str='14.10.1.2')
        self.sr3.save()

        for r in [self.sr1, self.sr2, self.sr3]:
            self.ctnr.ranges.add(r)

    def create_fake_zone(self, *args, **kwargs):
        domain = create_fake_zone(*args, **kwargs)
        self.ctnr.domains.add(domain)
        return domain

    def do_add(self, domain, server):
        ns = Nameserver(ctnr=self.ctnr, domain=domain, server=server)
        ns.save()
        self.assertTrue(ns.__repr__())
        self.assertTrue(ns.details())
        ret = Nameserver.objects.filter(domain=domain, server=server)
        self.assertEqual(len(ret), 1)
        return ns

    def test_add_ns(self):
        data = {'domain': self.r, 'server': 'ns2.moot.ru'}
        self.do_add(**data)

        data = {'domain': self.r, 'server': 'ns5.moot.ru'}
        self.do_add(**data)

        data = {'domain': self.r, 'server': u'ns3.moot.ru'}
        self.do_add(**data)

        data = {'domain': self.b_f_r, 'server': 'n1.moot.ru'}
        self.do_add(**data)

        data = {'domain': self.b_f_r, 'server': 'ns2.moot.ru'}
        self.do_add(**data)

        data = {'domain': self.r, 'server': 'asdf.asdf'}
        self.do_add(**data)

    def test_add_invalid(self):
        data = {'domain': self.f_r, 'server': 'ns3.foo.ru'}
        self.assertRaises(ValidationError, self.do_add, **data)

    def testtest_add_ns_in_domain(self):
        # Use an A record as a glue record.
        glue = AddressRecord(label='ns2', ctnr=self.ctnr, domain=self.r,
                             ip_str='128.193.1.10', ip_type='4')
        glue.clean()
        glue.save()
        data = {'domain': self.r, 'server': 'ns2.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.server, ns.glue.fqdn)
        self.assertRaises(ValidationError, glue.delete)

        glue = AddressRecord(label='ns3', ctnr=self.ctnr, domain=self.f_r,
                             ip_str='128.193.1.10', ip_type='4')
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns3.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.server, ns.glue.fqdn)

    def test_disallow_name_update_of_glue_A(self):
        # Glue records should not be allowed to change their name.
        glue = AddressRecord(label='ns39', ctnr=self.ctnr, domain=self.f_r,
                             ip_str='128.193.1.77', ip_type='4')
        glue.clean()
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns39.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.glue, glue)

        glue.label = "ns22"
        self.assertRaises(ValidationError, glue.clean)

    def test_disallow_name_update_of_glue_Intr(self):
        # Glue records should not be allowed to change their name.
        glue = StaticInterface(label='ns24', domain=self.f_r, ctnr=self.ctnr,
                               ip_str='128.193.99.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.clean()
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns24.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.glue, glue)

        glue.label = "ns22"
        self.assertRaises(ValidationError, glue.clean)

    def test_disallow_delete_of_glue_intr(self):
        # Interface glue records should not be allowed to be deleted.
        glue = StaticInterface(label='ns24', domain=self.f_r, ctnr=self.ctnr,
                               ip_str='128.193.99.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.clean()
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns24.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.glue, glue)

        self.assertRaises(ValidationError, glue.delete)

    def test_manual_assign_of_glue(self):
        # Test that assigning a different glue record doesn't get overriden by
        # the auto assinging during the Nameserver's clean function.
        glue = StaticInterface(label='ns25', domain=self.f_r, ctnr=self.ctnr,
                               ip_str='128.193.99.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.clean()
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns25.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.glue, glue)

        glue2 = AddressRecord(label='ns25', ctnr=self.ctnr, domain=self.f_r,
                              ip_str='128.193.1.78', ip_type='4')
        glue2.clean()
        glue2.save()

        ns.clean()

        # Make sure things didn't get overridden.
        self.assertEqual(ns.glue, glue)

        ns.glue = glue2
        ns.save()
        # Refresh the object.
        ns = Nameserver.objects.get(pk=ns.pk)
        # Again, make sure things didn't get overridden.
        self.assertEqual(ns.glue, glue2)
        # Make sure we still can't delete.
        self.assertRaises(ValidationError, glue2.delete)
        self.assertRaises(ValidationError, ns.glue.delete)

        # We shuold be able to delete the other one.
        glue.delete()

    def testtest_add_ns_in_domain_intr(self):
        # Use an Interface as a glue record.
        glue = StaticInterface(label='ns232', domain=self.r, ctnr=self.ctnr,
                               ip_str='128.193.99.10', ip_type='4',
                               system=self.s, mac="12:23:45:45:45:45")
        glue.clean()
        glue.save()
        data = {'domain': self.r, 'server': 'ns232.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.server, ns.glue.fqdn)
        self.assertRaises(ValidationError, glue.delete)

        glue = StaticInterface(label='ns332', domain=self.f_r, ctnr=self.ctnr,
                               ip_str='128.193.1.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.clean()
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns332.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.server, ns.glue.fqdn)

    def test_add_ns_outside_domain(self):
        data = {'domain': self.f_r, 'server': 'ns2.ru'}
        ns = self.do_add(**data)
        self.assertFalse(ns.glue)

    def test_update_glue_to_no_intr(self):
        glue = StaticInterface(label='ns34', domain=self.r, ctnr=self.ctnr,
                               ip_str='128.193.1.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.save()
        data = {'domain': self.r, 'server': 'ns34.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)

        ns.server = "ns4.wee"
        ns.save()
        self.assertTrue(ns.glue is None)

    def test_update_glue_record_intr(self):
        # Glue records can't change their name.
        glue = StaticInterface(label='ns788', domain=self.r, ctnr=self.ctnr,
                               ip_str='128.193.1.10', ip_type='4',
                               system=self.s, mac="11:22:33:44:55:66")
        glue.save()
        data = {'domain': self.r, 'server': 'ns788.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        glue.label = "asdfasdf"
        self.assertRaises(ValidationError, glue.clean)

    def test_update_glue_to_no_glue(self):
        glue = AddressRecord(label='ns3', ctnr=self.ctnr, domain=self.r,
                             ip_str='128.193.1.10', ip_type='4')
        glue.save()
        data = {'domain': self.r, 'server': 'ns3.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)

        ns.server = "ns4.wee"
        ns.save()
        self.assertTrue(ns.glue is None)

    def test_delete_ns(self):
        glue = AddressRecord(label='ns4', ctnr=self.ctnr, domain=self.f_r,
                             ip_str='128.196.1.10', ip_type='4')
        glue.save()
        data = {'domain': self.f_r, 'server': 'ns4.foo.ru'}
        ns = self.do_add(**data)
        self.assertTrue(ns.glue)
        self.assertEqual(ns.server, ns.glue.fqdn)

        ns.delete()
        nsret = Nameserver.objects.filter(
            server='ns2.foo.ru', domain=self.f_r)
        self.assertFalse(nsret)

    def test_invalid_create(self):
        glue = AddressRecord(label='ns2', ctnr=self.ctnr, domain=self.r,
                             ip_str='128.193.1.10', ip_type='4')
        glue.save()

        data = {'domain': self.r, 'server': 'ns2 .ru'}
        self.assertRaises(ValidationError, self.do_add, **data)
        data = {'domain': self.r, 'server': 'ns2$.ru'}
        self.assertRaises(ValidationError, self.do_add, **data)
        data = {'domain': self.r, 'server': 'ns2..ru'}
        self.assertRaises(ValidationError, self.do_add, **data)
        data = {'domain': self.r, 'server': 'ns2.ru '}
        self.assertRaises(ValidationError, self.do_add, **data)
        data = {'domain': self.r, 'server': ''}
        self.assertRaises(ValidationError, self.do_add, **data)

    def test_add_dup(self):
        data = {'domain': self.r, 'server': 'ns2.moot.ru'}
        self.do_add(**data)

        self.assertRaises(ValidationError, self.do_add, **data)

    def _get_post_data(self, random_str):
        """Return a valid set of data"""
        return {
            'root_domain': '{0}.oregonstate.com'.format(random_str),
            'soa_primary': 'ns1.oregonstate.com',
            'soa_contact': 'noc.oregonstate.com',
            'nameserver_1': 'ns1.oregonstate.com',
            'ttl_1': '1234'
        }

    def test_bad_nameserver_soa_state_case_1_0(self):
        # This is Case 1
        root_domain = self.create_fake_zone("asdf10")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        # At this point we should have a domain at the root of a zone with no
        # other records in it.

        # Adding a record shouldn't be allowed because there is no NS record on
        # the zone's root domain.
        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=root_domain, ip_type="6",
            ip_str="1::")
        self.assertRaises(ValidationError, a.save)
        cn = CNAME(label='', ctnr=self.ctnr, domain=root_domain, target="asdf")
        self.assertRaises(ValidationError, cn.save)

    def test_bad_nameserver_soa_state_case_1_1(self):
        # This is Case 1
        root_domain = self.create_fake_zone("asdf111")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        # At this point we should have a domain at the root of a zone with no
        # other records in it.

        # Let's create a child domain and try to add a record there.
        cdomain = Domain(name="test." + root_domain.name)
        cdomain.soa = root_domain.soa
        cdomain.save()

        # Adding a record shouldn't be allowed because there is no NS record on
        # the zone's root domain.
        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=cdomain, ip_type="6",
            ip_str="1::")
        self.assertRaises(ValidationError, a.save)
        cn = CNAME(label='', ctnr=self.ctnr, domain=cdomain, target="asdf")
        self.assertRaises(ValidationError, cn.save)

    def test_bad_nameserver_soa_state_case_1_2(self):
        # This is Case 1 ... with ptr's
        root_domain = self.create_fake_zone("12.in-addr.arpa", suffix="")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        # At this point we should have a domain at the root of a zone with no
        # other records in it.

        # Adding a record shouldn't be allowed because there is no NS record on
        # the zone's root domain.
        ptr = PTR(ctnr=self.ctnr, fqdn="asdf", ip_str="12.10.1.1", ip_type="4")
        self.assertRaises(ValidationError, ptr.save)

    def test_bad_nameserver_soa_state_case_1_3(self):
        # This is Case 1 ... with ptr's
        root_domain = self.create_fake_zone("13.in-addr.arpa", suffix="")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        # At this point we should have a domain at the root of a zone with no
        # other records in it.

        # Let's create a child domain and try to add a record there.
        cdomain = Domain(name="10.13.in-addr.arpa")
        cdomain.soa = root_domain.soa
        cdomain.save()

        # Adding a record shouldn't be allowed because there is no NS record on
        # the zone's root domain.
        ptr = PTR(ctnr=self.ctnr, fqdn="asdf", ip_str="13.10.1.1", ip_type="4")
        self.assertRaises(ValidationError, ptr.save)

    def test_bad_nameserver_soa_state_case_1_4(self):
        # This is Case 1 ... with StaticInterfaces's
        reverse_root_domain = self.create_fake_zone(
            "14.in-addr.arpa", suffix="")
        root_domain = self.create_fake_zone("asdf14")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        # At this point we should have a domain at the root of a zone with no
        # other records in it.

        # Let's create a child domain and try to add a record there.
        cdomain = Domain(name="10.14.in-addr.arpa")
        cdomain.soa = reverse_root_domain.soa
        cdomain.save()

        # Adding a record shouldn't be allowed because there is no NS record on
        # the zone's root domain.
        intr = StaticInterface(
            label="asdf", domain=root_domain, ip_str="14.10.1.1", ip_type="4",
            mac="11:22:33:44:55:66", system=self.s, ctnr=self.ctnr)
        self.assertRaises(ValidationError, intr.save)

    # See record.tests for the case a required view is deleted.
    def test_bad_nameserver_soa_state_case_2_0(self):
        # This is Case 2
        root_domain = self.create_fake_zone("asdf20")
        self.assertEqual(root_domain.nameserver_set.count(), 1)
        ns = root_domain.nameserver_set.all()[0]

        # At this point we should have a domain at the root of a zone with one
        # NS record associated to the domain.

        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=root_domain, ip_type="6",
            ip_str="1::")
        a.save()

        self.assertRaises(ValidationError, ns.delete)

    def test_bad_nameserver_soa_state_case_2_1(self):
        # This is Case 2
        root_domain = self.create_fake_zone("asdf21")
        self.assertEqual(root_domain.nameserver_set.count(), 1)
        ns = root_domain.nameserver_set.all()[0]

        # At this point we should have a domain at the root of a zone with one
        # NS record associated to the domain.

        # Let's create a child domain and add a record there, then try to
        # delete the NS record
        cdomain = Domain(name="test." + root_domain.name)
        cdomain.soa = root_domain.soa
        cdomain.save()
        self.ctnr.domains.add(cdomain)

        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=cdomain, ip_type="6",
            ip_str="1::")
        a.save()

        self.assertRaises(ValidationError, ns.delete)

    def test_bad_nameserver_soa_state_case_2_2(self):
        # This is Case 2 ... with PTRs
        root_domain = self.create_fake_zone("14.in-addr.arpa", suffix="")
        self.assertEqual(root_domain.nameserver_set.count(), 1)
        ns = root_domain.nameserver_set.all()[0]

        # At this point we should have a domain at the root of a zone with one
        # NS record associated to the domain.

        ptr = PTR(ctnr=self.ctnr, fqdn="bloo.asdf", ip_str="14.10.1.1",
                  ip_type="4")
        ptr.save()

        self.assertRaises(ValidationError, ns.delete)

    def test_bad_nameserver_soa_state_case_2_3(self):
        # This is Case 2 ... with PTRs
        root_domain = self.create_fake_zone("10.14.in-addr.arpa", suffix="")
        self.assertEqual(root_domain.nameserver_set.count(), 1)
        ns = root_domain.nameserver_set.all()[0]

        # At this point we should have a domain at the root of a zone with one
        # NS record associated to the domain.

        # Let's create a child domain and add a record there, then try to
        # delete the NS record.
        cdomain = Domain(name="test." + root_domain.name)
        cdomain.soa = root_domain.soa
        cdomain.save()

        ptr = PTR(ctnr=self.ctnr, fqdn="bloo.asdf", ip_str="14.10.1.1",
                  ip_type="4")
        ptr.save()

        self.assertRaises(ValidationError, ns.delete)

    def test_bad_nameserver_soa_state_case_3_0(self):
        # This is Case 3
        root_domain = self.create_fake_zone("asdf30")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        soa = ns.domain.soa
        ns.domain.soa = None
        soa.delete()
        root_domain.soa = None  # Shit's getting cached
        root_domain.save()
        ns.domain.save()

        # At this point we should have a domain pointed at no SOA record with
        # no records attached to it. It also has no child domains.

        # Add a record to the domain.
        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=root_domain, ip_type="6",
            ip_str="1::")
        a.save()

        s = SOA(primary="asdf.asdf", contact="asdf.asdf",
                description="asdf", root_domain=root_domain)

        self.assertRaises(ValidationError, s.save)

    def test_bad_nameserver_soa_state_case_3_1(self):
        # This is Case 3
        root_domain = self.create_fake_zone("asdf31")

        # Try case 3 but add a record to a child domain of root_domain.
        bad_root_domain = Domain(name="below." + root_domain.name)
        bad_root_domain.save()
        cdomain = Domain(name="test." + bad_root_domain.name)
        cdomain.save()
        self.ctnr.domains.add(cdomain)

        # Add a record to the domain.
        a = AddressRecord(
            label='', ctnr=self.ctnr, domain=cdomain, ip_type="6",
            ip_str="1::")
        a.save()

        # Now try to add the domain to the zone that has no NS records at its
        # root.
        s = SOA(root_domain=bad_root_domain, contact="a", primary='b')
        self.assertRaises(ValidationError, s.save)

    def test_bad_nameserver_soa_state_case_3_2(self):
        # This is Case 3 ... with PTRs
        root_domain = self.create_fake_zone("14.in-addr.arpa", suffix="")
        for ns in root_domain.nameserver_set.all():
            ns.delete()

        soa = ns.domain.soa
        soa.delete()
        ns.domain.soa = None
        root_domain = Domain.objects.get(pk=root_domain.pk)
        self.assertIsNone(root_domain.soa)
        ns.domain.save()

        # At this point we should have a domain pointed at no SOA record with
        # no records attached to it. It also has no child domains.

        # Add a record to the domain.

        ptr = PTR(ctnr=self.ctnr, fqdn="bloo.asdf", ip_str="14.10.1.1",
                  ip_type="4")
        ptr.save()

        s = SOA(primary="asdf.asdf", contact="asdf.asdf",
                description="asdf", root_domain=root_domain)

        self.assertRaises(ValidationError, s.save)

    def test_bad_nameserver_soa_state_case_3_3(self):
        # This is Case 3 ... with PTRs
        root_domain = self.create_fake_zone("14.in-addr.arpa", suffix="")

        bad_root_domain = Domain(name="10." + root_domain.name)
        bad_root_domain.save()
        cdomain = Domain(name="1.10.14.in-addr.arpa")
        cdomain.save()

        p = PTR(fqdn=('eh.' + cdomain.name), ctnr=self.ctnr, ip_type="4",
                ip_str="14.10.1.1")
        p.save()

        # Now try to add the domain to the zone that has no NS records at its
        # root.
        s = SOA(root_domain=bad_root_domain, contact="a", primary='b')
        self.assertRaises(ValidationError, s.save)
