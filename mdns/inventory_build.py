from truth.models import Truth
from systems.models import System
from mdns.build_nics import *

import ipaddr

import re
import copy
import pprint

pp = pprint.PrettyPrinter(indent=2)


def generate_hostname(nic, site_name):
    """
    Determine the correct fqdn from the nic's hostname key, site the name is
    going into, and any other additional options in nic_meta_data.

    :param hostname: The hostname on the nic.
    :type hostname: str
    :param site_name: The site_name that this nic's ip is in.
    :type site_name: str
    :param nic_meta_data: Other options that pertain to the nic.
    :type nic_meta_data: dict.
    :return build_hostname: The hostname to use in the A/PTR record.
    :type build_hostname: str
    """
    # Hey look Values are stored as strings.
    if nic.dns_auto_hostname is False:
        return hostname
    if len(nic.hostname.split('.')) == 1:
        return "{0}.{1}.mozilla.com".format(nic.hostname, site_name)
    else:
        return "{0}.mozilla.com".format(nic.hostname)

def inventory_build_sites(sites):
    """
    For each site in sites partition data into logical site groups. Later these
    groups will be used to print BIND Zone files.

    Sites have the form::

        ('<vlan-name>.<site-name>', <'network-mask'>)

    For example::

        ('dmz.scl3', '10.22.1.0/24')

    :param sites: The sites that data should be aggrigated for.
    :type sites: tuple
    """
    # Aggregated data goes in these dicts.
    agg_sites = {}
    agg_reverse = {}
    for site in sites:
        # Pre-calculate the regular expressions so we can do this in one pass.
        name, network = site
        # Add address family logic here if need be.
        try:
            agg_sites[name] = (ipaddr.IPv4Network(network), [])
        except ipaddr.AddressValueError, e:
            # Eventually send an email or do something more serious about an
            # error here.
            print str(e)

    for intr in get_nic_objs():
        if intr.dns_auto_build is False:
            continue

        for site_name, data in agg_sites.items():
            network, entries = data
            for ip in intr.ips:
                if ipaddr.IPv4Network(ip).overlaps(network):
                    intr.hostname = generate_hostname(intr, site_name)
                    entries.append(intr)
                    rev_file_name = '.'.join(ip.split('.')[:3])
                    reverse_data = agg_reverse.setdefault(rev_file_name, [])
                    reverse_data.append(intr)
                # TODO Should we add all hosts to reverse zones? Even if it
                # doesn't belong to a site?  Or should we only add to the
                # reverse when there is a corresponding record A in forward?
                # For now only add if we find a forward match. I'm pretty sure
                # there is an RFC that says A records should always have a PTR.
                # Is that the same for PTR's?

    return (agg_sites, agg_reverse)

