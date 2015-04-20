ALLOW_ALL = 'a'
ALLOW_KNOWN = 'k'
ALLOW_LEGACY = 'l'
ALLOW_STANDARD = 's'
ALLOW_VRF = 'v'

ALLOW_OPTIONS = [
    (ALLOW_STANDARD, 'STANDARD: All clients in this range'),
    (ALLOW_ALL, 'ALL: All clients, even those not registered in Cyder'),
    (ALLOW_KNOWN, 'KNOWN: All clients registered in Cyder'),
    (ALLOW_LEGACY,
        'LEGACY: All clients that are in this range and in one of its '
        'containers'),
    (ALLOW_VRF, "VRF: All clients in this range's VRF")
]

STATIC = 'st'
DYNAMIC = 'dy'
RANGE_TYPE = (
    (STATIC, 'Static'),
    (DYNAMIC, 'Dynamic'),
)

DHCP_EAV_MODELS = ("range_av", "network_av", "workgroup_av", "vlan_av",
                   "vrf_av", "site_av")

SYSTEM_INTERFACE_CTNR_ERROR = (
    "Cannot change container; interface's container and system's container "
    "must be the same. Please change the system's container instead.")
DEFAULT_WORKGROUP = 1
