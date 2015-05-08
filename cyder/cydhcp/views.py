from cyder.base.views import cy_view


def cydhcp_view(request, pk=None):
    return cy_view(request, 'cydhcp/cydhcp_view.html', pk)
