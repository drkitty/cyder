from django.conf.urls.defaults import include, patterns, url

from cyder.base.views import cy_render, cy_view, search_obj, table_update
from cyder.cydhcp.views import cydhcp_view
from cyder.cydhcp.constants import DHCP_EAV_MODELS


def cydhcp_urls(object_type):
    """Url generator for DHCP views"""
    return patterns(
        '',
        url(r'^$', cy_view, {'template': 'cydhcp/cydhcp_view.html'},
            name=object_type),
        url(r'^(?P<pk>[\w-]+)/update/$', cy_view,
            {'template': 'cydhcp/cydhcp_view.html'},
            name=object_type + '-update'),
        url(r'^(?P<pk>[\w-]+)/tableupdate/$', table_update,
            name=object_type + '-table-update'),
    )


urlpatterns = patterns(
    '',
    url(r'^$', cy_render, {'template': 'cydhcp/cydhcp_index.html'},
        name='cydhcp-index'),
    url(r'^build/', include('cyder.cydhcp.build.urls')),
    url(r'^network/', include('cyder.cydhcp.network.urls')),
    url(r'^range/', include('cyder.cydhcp.range.urls')),
    url(r'^site/', include('cyder.cydhcp.site.urls')),
    url(r'^vlan/', include('cyder.cydhcp.vlan.urls')),
    url(r'^interface/', include('cyder.cydhcp.interface.urls')),
    url(r'^static_interface/',
        include('cyder.cydhcp.interface.static_intr.urls')),
    url(r'^dynamic_interface/',
        include('cyder.cydhcp.interface.dynamic_intr.urls')),
    url(r'^vrf/', include('cyder.cydhcp.vrf.urls')),
    url(r'^workgroup/', include('cyder.cydhcp.workgroup.urls')),
)
for eav in DHCP_EAV_MODELS:
    urlpatterns += patterns(
        '',
        url(r'^{0}/'.format(eav), include(cydhcp_urls(eav))))
