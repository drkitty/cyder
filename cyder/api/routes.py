from rest_framework import routers

from cyder.api import api

router = routers.DefaultRouter()
router.register(r'cname', api.CNAMEViewSet)
router.register(r'txt', api.TXTViewSet)
router.register(r'srv', api.SRVViewSet)
router.register(r'mx', api.MXViewSet)
router.register(r'addressrecord', api.AddressRecordViewSet)
router.register(r'nameserver', api.NameserverViewSet)
router.register(r'ptr', api.PTRViewSet)
router.register(r'system', api.SystemViewSet)
router.register(r'staticinterface', api.StaticInterfaceViewSet)
