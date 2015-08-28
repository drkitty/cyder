from gettext import gettext as _
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist

from cyder.cydns.soa.models import SOA
from cyder.cydns.view.models import View

import json as json


def build_debug_soa(request, soa_pk):
    soa = get_object_or_404(SOA, pk=soa_pk)

    data = []

    try:
        for view in View.objects.all():
            data.append(";====== {} ======".format(view.name))
            data.append(soa.dns_build(public_view, serial=serial))
        data = "\n".join(data) + "\n"
        return cy_render(
            request, 'cybind/sample_build.html', {'data': data, 'soa': soa})
    except Exception, e:
        return HttpResponse(
            json.dumps({"error": "Could not build bind file: %s" % e}))
