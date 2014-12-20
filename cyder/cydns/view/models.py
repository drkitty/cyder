from django.db import models

from cyder.base.fields import CharField
from cyder.base.mixins import ObjectUrlMixin


class View(models.Model):
    """
    >>> View(name=name)
    """

    id = models.AutoField(primary_key=True)
    name = CharField(max_length=255, charset='ascii',
                     collation='ascii_general_ci')

    sort_fields = ('name',)

    class Meta:
        app_label = 'cyder'
        db_table = 'view'
        unique_together = ('name',)

    def details(self):
        return (
            ('Name', self.name),
        )

    def __unicode__(self):
        return self.name

    @staticmethod
    def filter_by_ctnr(ctnr, objects=None):
        return objects or View.objects.all()
