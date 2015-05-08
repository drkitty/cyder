from django.conf.urls.defaults import include, patterns, url

from cyder.base.views import cy_view, search_obj, table_update
from cyder.cydns.views import *
from cyder.cydns.constants import DNS_EAV_MODELS


def cydns_urls(obj_type):
    """Url generator for DNS record views."""
    return patterns(
        '',
        url(r'^$', cy_view, {'template': 'cydns/cydns_view.html'},
            name=obj_type),
        url(r'(?P<pk>[\w-]+)/update/$', cy_view,
            {'template': 'cydns/cydns_view.html'}, name=obj_type + '-update'),
        url(r'(?P<pk>[\w-]+)/tableupdate/$', table_update,
            name=obj_type + '-table-update'),
    )


urlpatterns = patterns(
    '',
    url(r'^$', cydns_index, name='cydns-index'),
    url(r'^address_record/', include('cyder.cydns.address_record.urls')),
    url(r'^cname/', include('cyder.cydns.cname.urls')),
    url(r'^domain/', include('cyder.cydns.domain.urls')),
    url(r'^mx/', include('cyder.cydns.mx.urls')),
    url(r'^nameserver/', include('cyder.cydns.nameserver.urls')),
    url(r'^ptr/', include('cyder.cydns.ptr.urls')),
    url(r'^soa/', include('cyder.cydns.soa.urls')),
    url(r'^srv/', include('cyder.cydns.srv.urls')),
    url(r'^txt/', include('cyder.cydns.txt.urls')),
    url(r'^sshfp/', include('cyder.cydns.sshfp.urls')),

    url(r'^view/', include('cyder.cydns.view.urls')),
    url(r'^bind/', include('cyder.cydns.cybind.urls')),
)
for eav in DNS_EAV_MODELS:
    urlpatterns += patterns(
        '',
        url(r'^{0}/'.format(eav), include(cydns_urls(eav))))
