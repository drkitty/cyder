from django.db import models

from cyder.base.fields import CharField


class DNSManager(models.Manager):
    def get_queryset(self):
        return super(DNSManager, self).get_queryset().filter(ttype='dns')


class Task(models.Model):
    task = CharField(max_length=255, blank=False, charset='ascii',
                     collation='ascii_general_ci')
    ttype = CharField(max_length=255, blank=False, charset='ascii',
                      collation='ascii_bin')

    objects = models.Manager()
    dns = DNSManager()

    class Meta:
        app_label = 'cyder'
        db_table = u'task'
        ordering = ['task']

    def __unicode__(self):
        return "{0} {1}".format(self.ttype, self.task)

    def __str__(self):
        return unicode(self).encode('ascii', 'replace')

    def save(self):
        super(Task, self).save()

    @staticmethod
    def schedule_zone_rebuild(soa):
        Task(task=str(soa.pk), ttype='dns').save()
