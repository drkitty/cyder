from cyder.base.views import cy_detail
from cyder.cydns.nameserver.forms import Nameserver, NameserverForm,
from cyder.cydns.views import cy_render


def nameserver_detail(request, pk):
    return cy_detail(request, Nameserver, 'cydns/cydns_detail.html', {}, pk=pk)


class NSView(object):
    model = Nameserver
    form_class = NameserverForm
    queryset = Nameserver.objects.all()
    extra_context = {'obj_type': 'nameserver'}
