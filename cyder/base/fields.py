from django import forms
from django.db import models
from django.db.models import CharField, SubfieldBase
from django.core.exceptions import ValidationError
from south.modelsinspector import add_introspection_rules

from cyder.cydhcp.validation import validate_mac


class CharField(models.CharField):
    def __init__(self, *args, **kwargs):
        self.charset = kwargs.pop('charset', 'utf8mb4')
        self.collation = kwargs.pop('collation', 'utf8mb4_general_ci')

        return super(CharField, self).__init__(*args, **kwargs)

    def db_type(self, connection):
        if connection.settings_dict['ENGINE'] == 'django.db.backends.mysql':
            return (
                super(CharField, self).db_type(connection) +
                ' CHARACTER SET {} COLLATE {}'.format(
                    self.charset, self.collation)
            )
        else:
            raise Exception('Database backend not supported')


class TextField(models.TextField):
    def __init__(self, *args, **kwargs):
        self.charset = kwargs.pop('charset', 'utf8mb4')
        self.collation = kwargs.pop('collation', 'utf8mb4_general_ci')

        return super(TextField, self).__init__(*args, **kwargs)

    def db_type(self, connection):
        if connection.settings_dict['ENGINE'] == 'django.db.backends.mysql':
            return (
                super(TextField, self).db_type(connection) +
                ' CHARACTER SET {} COLLATE {}'.format(
                    self.charset, self.collation)
            )
        else:
            raise Exception('Database backend not supported')


class MacAddrField(CharField):
    """A general purpose MAC address field
    This field holds a MAC address. clean() removes colons and hyphens from the
    field value, raising an exception if the value is invalid or empty.

    Arguments:

    dhcp_enabled (string):
        The name of another attribute (possibly a field) in the model that
        holds a boolean specifying whether to validate this MacAddrField; if
        not specified, always validate.
    """

    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        self.dhcp_enabled = kwargs.pop('dhcp_enabled', True)

        kwargs['max_length'] = 17
        kwargs['blank'] = False  # always call MacAddrField.clean
        kwargs['null'] = True
        kwargs['charset'] = 'ascii'
        kwargs['collation'] = 'ascii_general_ci'

        super(MacAddrField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value:
            return value.lower().replace(':', '').replace('-', '')
        else:
            return None

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type == 'exact' and value == '':
            raise Exception(
                "When using the __exact lookup type, use a query value of "
                "None instead of ''. Even though get_prep_value transforms "
                "'' into None, Django only converts __exact queries into "
                "__isnull queries if the *user*-provided query value is None.")
        else:
            return super(MacAddrField, self).get_prep_lookup(
                lookup_type, value)

    def to_python(self, value):
        value = super(MacAddrField, self).to_python(value)

        if value:
            value = value.lower().replace(':', '').replace('-', '')
            value = reduce(lambda x,y: x + ':' + y,
                           (value[i:i+2] for i in xrange(0, 12, 2)))
        elif value == '':
            value = None
        return value

    def clean(self, value, model_instance):
        value_required = (self.dhcp_enabled is True
            or (isinstance(self.dhcp_enabled, basestring) and
                getattr(model_instance, self.dhcp_enabled)))

        if (value_required and not value):
            raise ValidationError(
                "This field is required when DHCP is enabled")

        if value:
            validate_mac(value)
            return super(MacAddrField, self).clean(value, model_instance)
        else:
            # If value is blank, CharField.clean will choke.
            return value

    def formfield(self, **kwargs):
        kwargs.update({
            'required': False,
            'max_length': self.max_length,
        })
        return forms.CharField(**kwargs)


add_introspection_rules([
    (
        [CharField],  # model
        [],  # args
        {'charset': ('charset', {}), 'collation': ('collation', {})},  # kwargs
    ),
    (
        [TextField],  # model
        [],  # args
        {'charset': ('charset', {}), 'collation': ('collation', {})},  # kwargs
    ),
    (
        [MacAddrField], # model
        [], # args
        {'dhcp_enabled': ('dhcp_enabled', {})}, # kwargs
    )
], [
    r'^cyder\.base\.fields\.CharField',
    r'^cyder\.base\.fields\.TextField',
    r'^cyder\.base\.fields\.MacAddrField',
])
