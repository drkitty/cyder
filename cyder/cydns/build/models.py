from django.db import models

from cyder.base.utils import transaction_atomic


class BuildTime(models.Model):
    class Meta:
        app_label = 'cyder'
        db_table = 'buildtime'

    id = models.AutoField(primary_key=True)
    start = models.DateTimeField()

    @transaction_atomic
    def save(self, *args, **kwargs):
        self.full_clean()
        super(BuildTime, self).save(*args, **kwargs)
