from django.conf.urls.defaults import *

from cyder.cydns.nameserver.views import *
from cyder.cydns.urls import cydns_urls


urlpatterns = cydns_urls('nameserver')
