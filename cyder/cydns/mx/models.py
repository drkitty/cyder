from gettext import gettext as _

from django.db import models
from django.core.exceptions import ValidationError

from cyder.base.utils import transaction_atomic
from cyder.cydns.cname.models import CNAME
from cyder.cydns.models import CydnsRecord, LabelDomainMixin
from cyder.cydns.validation import validate_fqdn, validate_mx_priority


class MX(LabelDomainMixin, CydnsRecord):
    pretty_type = 'MX'

    id = models.AutoField(primary_key=True)
    # The mail server this record should point to.
    server = models.CharField(max_length=100, validators=[validate_fqdn],
                              help_text="The name of the mail server this "
                              "record points to.")
    priority = models.PositiveIntegerField(null=False,
                                           validators=[validate_mx_priority])
    ctnr = models.ForeignKey("cyder.Ctnr", null=False,
                             verbose_name="Container")
    search_fields = ('fqdn', 'server')

    class Meta:
        app_label = 'cyder'
        db_table = 'mx'
        unique_together = (('domain', 'label', 'server'),)

    def __unicode__(self):
        return u'{} MX {} {}'.format(self.fqdn, self.priority, self.server)

    def details(self):
        """For tables."""
        data = super(MX, self).details()
        data['data'] = [
            ('Label', 'label', self.label),
            ('Domain', 'domain', self.domain),
            ('Server', 'server', self.server),
            ('Priority', 'priority', self.priority),
            ('TTL', 'ttl', self.ttl)
        ]
        return data

    @staticmethod
    def eg_metadata():
        """EditableGrid metadata."""
        return {'metadata': [
            {'name': 'label', 'datatype': 'string', 'editable': True},
            {'name': 'domain', 'datatype': 'string', 'editable': True},
            {'name': 'server', 'datatype': 'string', 'editable': True},
            {'name': 'priority', 'datatype': 'integer', 'editable': True},
            {'name': 'ttl', 'datatype': 'integer', 'editable': True},
        ]}

    def dns_build(self):
        from cyder.cydns.utils import render_dns_record

        return render_dns_record(
            name=self.fqdn + '.',
            ttl=self.ttl,
            cls='IN',
            type='MX',
            priority=self.priority,
            rdata=self.server + '.',
        )

    @transaction_atomic
    def save(self, *args, **kwargs):
        self.full_clean()

        super(MX, self).save(*args, **kwargs)

    def clean(self, *args, **kwargs):
        super(MX, self).clean(*args, **kwargs)
        super(MX, self).check_for_cname()
        self.no_point_to_cname()

    def no_point_to_cname(self):
        """MX records should not point to CNAMES."""
        # TODO, cite an RFC.
        if CNAME.objects.filter(fqdn=self.server):
            raise ValidationError("MX records should not point to CNAMES.")
