from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.db.models import Count
from django.forms.models import model_to_dict
from django.utils.translation import ugettext_lazy as _
from model_utils.managers import PassThroughManager
import reversion


class IntegerRangeField(models.IntegerField):

    def __init__(self, min_value=None, max_value=None, *args, **kwargs):
        super(models.IntegerField, self).__init__(*args, **kwargs)
        self.min_value, self.max_value = min_value, max_value

    def formfield(self, **kwargs):
        defaults = {'min_value': self.min_value,
                    'max_value': self.max_value}
        defaults.update(kwargs)
        return super(IntegerRangeField, self).formfield(**defaults)


class CompanyQuerySet(models.query.QuerySet):

    def get_or_create(self, commit_desc=None, commit_user=None, *args, **kwargs):
        if not commit_desc:
            return super(CompanyQuerySet, self).get_or_create(*args, **kwargs)

        with transaction.atomic(), reversion.create_revision(manage_manually=True):
            obj = super(CompanyQuerySet, self).get_or_create(*args, **kwargs)
            reversion.default_revision_manager.save_revision([obj[0]],
                comment=commit_desc, user=commit_user)
            return obj

    def with_query_count(self):
        return self.annotate(query_count=Count('product__query__id'))


class Company(models.Model):
    VALUE_0_OR_100 = ((0,0),(100,100))
    nip = models.CharField(max_length=10, db_index=True, null=True,
                           blank=True, verbose_name="Company's NIP#")
    name = models.CharField(max_length=128, null=True, blank=True,
                            db_index=True,
                            verbose_name=
                            "Name as retrieved from produkty_w_sieci API")
    official_name = models.CharField(max_length=128, blank=True, null=True,
                                     verbose_name="Official company name")
    common_name = models.CharField(max_length=128, blank=True,
                                   verbose_name="Common company name")
    address = models.TextField(null=True, blank=True)
    plCapital = IntegerRangeField(
        verbose_name=_("Percentage share of Polish capital"),
        min_value=0, max_value=100, null=True, blank=True)
    plCapital_notes = models.TextField(
        _("Notes about share of Polish capital"), null=True, blank=True)
    plRegistered = IntegerRangeField(
        verbose_name=_("Registered in Poland?"), min_value=0, max_value=100,
        null=True, blank=True, choices=VALUE_0_OR_100)
    plRegistered_notes = models.TextField(
        _("Notes about registered in Poland"), null=True, blank=True, choices=VALUE_0_OR_100)
    plRnD = IntegerRangeField(
        verbose_name=_("Information about R&D center"), min_value=0,
        max_value=100, null=True, blank=True, choices=VALUE_0_OR_100)
    plRnD_notes = models.TextField(
        _("Notes about R&D center"), null=True, blank=True)
    plWorkers = IntegerRangeField(
        verbose_name=_("Information about workers"), min_value=0,
        max_value=100, null=True, blank=True, choices=VALUE_0_OR_100)
    plWorkers_notes = models.TextField(
        _("Notes about workers"), null=True, blank=True)
    plNotGlobEnt = IntegerRangeField(
        verbose_name=_("Isn't it a global enterprise?"), min_value=0,
        max_value=100, null=True, blank=True, choices=VALUE_0_OR_100)
    plNotGlobEnt_notes = models.TextField(
        _("Notes about global enterprise"), null=True, blank=True)
    verified = models.BooleanField(default=False)

    objects = PassThroughManager.for_queryset_class(CompanyQuerySet)()

    def to_dict(self):
        dict = model_to_dict(self)
        return dict

    def get_absolute_url(self):
        return reverse('company:detail', args=[self.pk])

    def __unicode__(self):
        return self.common_name or self.official_name or self.name

    def save(self, commit_desc=None, commit_user=None, *args, **kwargs):
        if not commit_desc:
            return super(Company, self).save(*args, **kwargs)

        with transaction.atomic(), reversion.create_revision(manage_manually=True):
            obj = super(Company, self).save(*args, **kwargs)
            reversion.default_revision_manager.save_revision([self],
                comment=commit_desc, user=commit_user )
            return obj

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")

reversion.register(Company)
