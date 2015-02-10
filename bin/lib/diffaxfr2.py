#!/usr/bin/env python2

import manage

import errno
from os import chdir, path
from subprocess import PIPE, Popen
from sys import argv, stderr, stdout

import dns.zone
from django.conf import settings
from dns import rdatatype
from dns.rdatatype import CNAME, MX, PTR
from iscpy.iscpy_core.core import ParseISCString


def main():
    chdir(settings.BINDBUILD['prod_dir'])
    config_file_name = 'config/master.public'
    prefix_len = len(settings.BINDBUILD['bind_prefix'].rstrip('/')) + 1

    with open(config_file_name, 'r') as config_file:
        config = ParseISCString(config_file.read())

    zone_file_names = [
        val['file'].strip('"')[prefix_len:]
        for _, val in config.iteritems()]

    for n in zone_file_names:
        origin = path.basename(n)[:-len('.public')] + '.'

        try:
            cyder_zone = dns.zone.from_file(n, origin=origin)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
            stderr.write("Zone file '{}' not found\n".format(n))
            continue

        po = Popen(('dig', '+nocmd', '+nostats', '@ns1.oregonstate.edu',
            cyder_zone.origin.to_text(), 'axfr'), stdout=PIPE)
        out, _ = po.communicate()
        if po.returncode != 0:
            stderr.write('dig failed\n')
            continue
        try:
            maintain_zone = dns.zone.from_text(out, origin=origin)
        except dns.zone.NoSOA:
            stderr.write("Zone '{}' doesn't exist on ns1\n".format(
                origin))
            continue

        def rd_str(name, rdata):
            rdata_text = rdata.to_text(relativize=False).lower()
            if rdata_text == '@':
                rdata_text = origin
            elif rdata.rdtype in (CNAME, MX, PTR) and rdata_text[-1] != '.':
                rdata_text += '.' + origin
            return (
                ('' if name == '@' else name + '.') + origin + ' in ' +
                rdatatype.to_text(rdata.rdtype).lower() + ' ' + rdata_text
            )

        maintain_records = {}  # name -> records
        for name, _, rdata in maintain_zone.iterate_rdatas():
            if rdata.rdtype == rdatatype.from_text('SOA'):
                rdata.serial = 0
            name = name.to_text().lower()
            maintain_records.setdefault(name, set()).add(rdata)

        cyder_records = {}  # name -> records
        for name, _, rdata in cyder_zone.iterate_rdatas():
            if rdata.rdtype == rdatatype.from_text('SOA'):
                rdata.serial = 0
            name = name.to_text().lower()
            cyder_records.setdefault(name, set()).add(rdata)

        diff = []

        for name, mrs in maintain_records.iteritems():
            crs = cyder_records.get(name, None)
            if crs is None:
                for mrdata in mrs:
                    diff.append((name, 0, mrdata))
                continue
            for mrdata in sorted(mrs - crs):
                diff.append((name, 0, mrdata))
            for crdata in sorted(crs - mrs):
                diff.append((name, 1, crdata))

        for name, crs in cyder_records.iteritems():
            mrs = maintain_records.get(name, None)
            if mrs is None:
                for crdata in crs:
                    diff.append((name, 1, crdata))

        for name, new, rdata in sorted(diff):
            print ('> ' if new else '< ') + rd_str(name, rdata)

    return 0


if __name__ == '__main__':
    exit(main())
