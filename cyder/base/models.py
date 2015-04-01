from datetime import datetime
from django.contrib.auth.models import User
from django.db import models
from django.utils.safestring import mark_safe

from rest_framework.renderers import JSONRenderer

from cyder.base.utils import classproperty, dict_diff
from cyder.settings import MAX_LOG_ENTRIES


class DeleteLog(models.Model):
    obj_type = models.CharField(max_length=30)
    deleted = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, blank=True, null=True)
    log = models.TextField()
    
    class Meta:
        app_label = 'cyder'
        db_table = 'deletelog'


class Serializable(object):
    """Supports translating an object to a serialized representation using
    Django REST Framework serializers.
    """
    def serializer(self):
        """
        Should call a Django REST Framework serializer on self and return the
        result. This is a function to avoid a circular import where the
        serializer file imports the model and the model file imports the
        serializer at the top level.
        """
        raise NotImplementedError("This model inherits from LoggedModel, but "
                                  "it doesn't specify a serializer to use")

    def serialized(self):
        """
        Serializes the model instance to a dict.
        """
        return self.serializer().data

    @staticmethod
    def render_to_json(data):
        return JSONRenderer().render(data)


class LoggedModel(Serializable, models.Model):
    """Allows changes to objects to be logged for auditing purposes.

    Objects inheriting from this class must specify an attribute audit_fields
    listing the names of fields to be logged as strings.

    On deletion, a LoggedModel object will cause the creation of a DeleteLog
    entry, which will record the deleted object's class name, date of deletion,
    and the data contained in the deleted object's log.
    """
    log = models.TextField(blank=True)
    last_save_user = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        abstract = True

    def last_saved_version(self):
        """
        Returns a model instance corresponding to the last saved version of
        this object.
        """
        return self.__class__.objects.get(pk=self.pk)

    def to_json(self):
        """
        Creates a JSON-serialized string representing the record.
        """
        return self.render_to_json(self.serialized())

    def diff_to_json(self):
        """
        Creates a JSON-serialized string from the record containing what has
        changed from the last saved version.

        Preconditions: must be run after the model instance is modified but
        before it is saved.
        """
        self_data = self.serialized()
        old_data = self.last_saved_version().serialized()
        changes = dict_diff(old_data, self_data)

        # remove the metadata keys that we keep at the top-level of the dict
        changes.pop('last_save_user', None)
        changes.pop('modified', None)

        if changes:
            return self.render_to_json({
                'last_save_user': self_data['last_save_user'],
                'modified': datetime.now().strftime('%m/%d/%Y %H:%M:%S'),
                'changes': changes})
        else:
            return None

    def save(self, *args, **kwargs):
        # only update the log if the record has already been saved
        if self.pk:
            old_data = self.__class__.objects.get(pk=self.pk)
            log_lines = self.log.split('\n')

            # get the serialized representation
            change_log = self.diff_to_json()

            # don't update the log if there are no changes
            if change_log is not None:
                log_lines.insert(0, change_log)

                # remove log entries if we're over the limit
                if len(log_lines) > MAX_LOG_ENTRIES:
                    log_lines = log_lines[:MAX_LOG_ENTRIES]

                self.log = '\n'.join(log_lines)

        return super(LoggedModel, self).save(*args, **kwargs)

    def delete(self, user=None, *args, **kwargs):
        # before deleting, save the data to the DeleteLog
        dl = DeleteLog(obj_type=self.__class__.__name__,
                       log=self.log + "\n" + self.to_json(),
                       user=user)
        dl.save()
        return super(LoggedModel, self).delete(*args, **kwargs)


class BaseModel(models.Model):
    """
    Base class for models to abstract some common features.

    * Adds automatic created and modified fields to the model.
    """
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True
        get_latest_by = 'created'

    def __str__(self):
        return unicode(self).encode('ascii', 'replace')

    @classproperty
    @classmethod
    def pretty_type(cls):
        return cls.__name__.lower()

    @property
    def pretty_name(self):
        return unicode(self)

    def get_ctnrs(self):
        from cyder.base.eav.models import EAVBase
        if isinstance(self, EAVBase):
            obj = self.entity
        else:
            obj = self
        if hasattr(obj, "ctnr") and obj.ctnr.name.lower() != "global":
            return [obj.ctnr]
        elif hasattr(obj, "ctnr_set"):
            return obj.ctnr_set.exclude(name="global")
        else:
            raise TypeError("This object has no container.")

    def cyder_unique_error_message(self, model_class, unique_check):
        """
        Override this method to provide a custom error message for
        unique or unique_together fields. It should return a descriptive error
        message that ends in a period.
        """

        return super(BaseModel, self).unique_error_message(
            model_class, unique_check)

    def unique_error_message(self, model_class, unique_check):
        """
        Don't override this method. Override cyder_unique_error_message
        instead.
        """

        error = self.cyder_unique_error_message(model_class, unique_check)
        kwargs = {}
        for field in unique_check:
            kwargs[field] = getattr(self, field)
        obj = model_class.objects.filter(**kwargs)
        if obj and hasattr(obj.get(), 'get_detail_url'):
            error = error[:-1] + u' at <a href="{0}">{1}.</a>'.format(
                obj.get().get_detail_url(), obj.get())
            error = mark_safe(error)
        return error

    def reload(self):
        return self.__class__.objects.get(pk=self.pk)


class ExpirableMixin(models.Model):
    expire = models.DateTimeField(null=True, blank=True,
                                  help_text='Format: MM/DD/YYYY')

    class Meta:
        abstract = True
