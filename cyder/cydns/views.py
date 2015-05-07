from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.utils import DatabaseError
from django.forms.util import ErrorDict, ErrorList
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from cyder.base.constants import ACTION_CREATE, get_klasses
from cyder.base.mixins import UsabilityFormMixin
from cyder.base.helpers import do_sort
from cyder.base.utils import (make_paginator, _filter, tablefy)
from cyder.base.views import cy_render, search_obj, table_update
from cyder.core.cyuser.utils import perm

import json


def cydns_view(request, pk=None):
    from cyder.base.views import cy_view
    return cy_view(request, 'cydns/cydns_view.html', pk)


def cydns_table_update(request, pk, object_type=None):
    return table_update(request, pk, object_type)


def cydns_search_obj(request):
    return search_obj(request)


def cydns_index(request):
    from cyder.models import (AddressRecord, CNAME, Domain, Nameserver, PTR,
                              MX, SOA, SRV, SSHFP, TXT)
    ctnr = request.session['ctnr']
    counts = []
    Klasses = [(AddressRecord, 'Address Records'), (PTR, 'PTRs'), (MX, 'MXs'),
        (SRV,'SRVs'), (SSHFP, 'SSHFPs'), (TXT, 'TXTs'), (CNAME, 'CNAMES')]

    if ctnr.name != 'global':
        domains = ctnr.domains.all()
        soa_list = []
        for Klass in Klasses:
            counts.append((Klass[1], Klass[0].objects.filter(ctnr=ctnr).count()))

        ns_count = 0
        for domain in domains:
            ns_count += domain.nameserver_set.count()

            if domain.soa not in soa_list:
                soa_list.append(domain.soa)

        counts.append(('SOAs', len(soa_list)))
        counts.append(('Nameservers', ns_count))

    else:
        domains = Domain.objects.all()
        Klasses.append((SOA, 'SOAs'))
        Klasses.append((Nameserver, 'Nameservers'))
        for Klass in Klasses:
            counts.append((Klass[1], Klass[0].objects.all().count()))


    counts.append(('Domains', domains.filter(is_reverse=False).count()))
    counts.append(('Reverse Domains',
               domains.filter(is_reverse=True).count()))

    return cy_render(request, 'cydns/cydns_index.html', {'counts': counts})
