from django.core.urlresolvers import NoReverseMatch, reverse
from django.db.models.loading import get_model
from django.forms import ModelChoiceField, HiddenInput

from cyder.base.utils import filter_by_ctnr


class ObjectUrlMixin(object):
    """
    This is a mixin that adds important url methods to a model. This
    class uses the ``_meta.db_table`` instance variable of an object to
    calculate URLs. Because of this, you must use the app label of your
    class when declaring urls in your urls.py.
    """
    @classmethod
    def get_list_url(cls):
        """
        Return the 'list' url of an object. Class method since don't
        need specific instance of object.
        """
        return reverse(cls._meta.db_table)

    @classmethod
    def get_create_url(cls):
        """Return the create url of the type of object (to be posted to)."""
        return cls.get_list_url()

    def get_update_url(self):
        """Return the update url of an object."""
        return reverse(self._meta.db_table + '-update', args=[self.pk])

    def get_delete_url(self):
        """Return the delete url of an object."""
        return reverse('delete')

    def get_detail_url(self):
        """Return the detail url of an object."""
        try:
            return reverse(self._meta.db_table + '-detail', args=[self.pk])
        except NoReverseMatch:
            return ''

    def get_table_update_url(self):
        """Return the editableGrid update url of an object."""
        try:
            return reverse(self._meta.db_table + '-table-update',
                           args=[self.pk])
        except NoReverseMatch:
            return ''

    def details(self):
        """
        Return base details with generic postback URL for editable tables.
        """
        return {'url': self.get_table_update_url()}


class UsabilityFormMixin(object):
    def append_required_all(self):
        for fieldname, field in self.fields.items():
            if self.fields[fieldname].required is True:
                if self.fields[fieldname].label is None:
                    fname = fieldname.replace('_', ' ')
                    self.fields[fieldname].label = fname.capitalize() + '*'
                else:
                    self.fields[fieldname].label += '*'

    def alphabetize_all(self):
        for fieldname, field in self.fields.items():
            if hasattr(field, 'queryset'):
                self.fields[fieldname].queryset = field.queryset.order_by(
                    *field.queryset.model.sort_fields)

    def filter_by_ctnr_all(self, request, skip=None):
        from cyder.core.ctnr.models import Ctnr
        ctnr = request.session['ctnr']
        for fieldname, field in self.fields.items():
            if skip and fieldname in skip:
                continue

            if not hasattr(field, 'queryset'):
                continue

            queryset = self.fields[fieldname].queryset
            if queryset.model is Ctnr:
                ctnrs = set(c.pk for c in request.session['ctnrs'])
                for pk in [1, 2]:
                    if pk in ctnrs:
                        ctnrs.remove(pk)

                if self.fields[fieldname].initial:
                    ctnrs.add(self.fields[fieldname].initial.pk)

                queryset = queryset.filter(pk__in=ctnrs)
            else:
                queryset = filter_by_ctnr(ctnr=ctnr,
                                          objects=field.queryset).distinct()

            if queryset.count() == 1:
                self.fields[fieldname].initial = queryset[0]

            self.fields[fieldname].queryset = queryset

    def autoselect_system(self):
        System = get_model('cyder', 'system')
        if 'system' in self.initial:
            self.fields['system'] = ModelChoiceField(
                widget=HiddenInput(),
                empty_label='',
                queryset=System.objects.filter(pk=int(self.initial['system'])))
        elif 'system' in self.fields:
            del(self.fields['system'])

    def autoselect_ctnr(self, request):
        if 'ctnr' not in self.fields:
            return

        session_ctnr = request.session['ctnr']
        if 'ctnr' not in self.initial and session_ctnr.name != "global":
            self.fields['ctnr'].initial = session_ctnr
            self.fields['ctnr'].widget = HiddenInput()

    def make_usable(self, request):
        self.autoselect_system()
        self.autoselect_ctnr(request)
        if 'ctnr' in request.session:
            self.filter_by_ctnr_all(request)
        self.alphabetize_all()
        self.append_required_all()
