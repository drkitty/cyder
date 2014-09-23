from django.forms import ModelForm

from cyder.cydns.domain.models import Domain
from cyder.base.mixins import UsabilityFormMixin


class DomainForm(ModelForm, UsabilityFormMixin):
    class Meta:
        model = Domain
        exclude = ('master_domain', 'is_reverse', 'dirty', 'purgeable',
                   'last_save_user', 'log')


class DomainUpdateForm(ModelForm):
    class Meta:
        model = Domain
        exclude = ('name', 'master_domain', 'purgeable', 'last_save_user',
                   'log')
