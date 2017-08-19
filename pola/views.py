from datetime import datetime, timedelta
from functools import reduce

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.db.models import Q
from django.db.models.functions import Length
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.timezone import get_default_timezone
from django.views.generic import TemplateView
from django.views.generic.detail import (
    BaseDetailView, SingleObjectTemplateResponseMixin)

from ai_pics.models import AIPics, AIAttachment
from company.models import Company
from pola.models import Stats
from product.models import Product
from report.models import Report

from boto.s3.connection import S3Connection, Bucket, Key
from django.conf import settings

class FrontPageView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/home-cms.html'

    def get_context_data(self, *args, **kwargs):
        c = super(FrontPageView, self).get_context_data(**kwargs)

        c['most_popular_companies'] = (Company.objects
                                       .filter(verified=False)
                                       .order_by('-query_count')[:10])
        c['no_of_companies'] = Company.objects.count()
        c['no_of_not_verified_companies'] = Company.objects\
            .filter(verified=False).count()
        c['no_of_verified_companies'] = Company.objects.\
            filter(verified=True).count()

        c['products_with_most_open_reports'] = \
            Product.objects.raw('select *, '
                                '(select count(*) from report_report where product_id=product_product.id and resolved_at is NULL) as no_of_open_reports '
                                'from product_product order by no_of_open_reports desc limit 10')

        c['most_popular_590_products'] = (Product.objects
                                          .filter(
                                                company__isnull=True,
                                                code__startswith='590')
                                          .order_by('-query_count')[:10])
        c['no_of_590_products'] = (Product.objects
                                   .filter(
                                        company__isnull=True,
                                        code__startswith='590')
                                   .count())

        c['most_popular_not_590_products'] =\
            (Product.objects.filter(company__isnull=True)
                .exclude(code__startswith='590').order_by('-query_count')[:10])
        c['no_of_not_590_products'] = \
            (Product.objects.filter(company__isnull=True).
             exclude(code__startswith='590').count())

        c['companies_by_name_length'] =\
            (Company.objects.annotate(name_length=Length('common_name')).order_by('-name_length'))[:10]

        c['most_popular_products_without_name'] =\
            (Product.objects.filter(name__isnull=True)\
                .order_by('-query_count')[:10])

        c['newest_reports'] = (Report.objects.only_open()
                                     .order_by('-created_at')[:10])
        c['no_of_open_reports'] = Report.objects.only_open().count()
        c['no_of_resolved_reports'] = Report.objects.only_resolved().count()
        c['no_of_reports'] = Report.objects.count()

        return c


class ExprAutocompleteMixin(object):
    def get_search_expr(self):
        if not hasattr(self, 'search_expr'):
            raise ImproperlyConfigured('{0} is missing a {0}.search_expr. Define '
                                       '{0}.search_expr or override {0}.get_search_expr().'
                                       ''.format(self.__class__.__name__))
        return self.search_expr

    def get_filters(self):
        q = [Q(**{x: self.q}) for x in self.get_search_expr()]
        return reduce(lambda x, y: x | y, q)

    def get_queryset(self):
        qs = self.model.objects.all()

        if self.q:
            qs = qs.filter(self.get_filters())

        return qs


class ActionMixin(object):
    success_url = None

    def action(self):
        raise ImproperlyConfigured("No action to do. Provide a action body.")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.action()
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        if self.success_url:
            self.success_url = force_text(self.success_url)
            return self.success_url.format(**self.object.__dict__)
        else:
            raise ImproperlyConfigured(
                "No URL to redirect to. Provide a success_url.")


class BaseActionView(ActionMixin, BaseDetailView):
    """
    Base view for action on an object.
    Using this base class requires subclassing to provide a response mixin.
    """


class ActionView(SingleObjectTemplateResponseMixin, BaseActionView):
    template_name_suffix = '_action'


class StatsPageView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/home-stats.html'

    def get_context_data(self, *args, **kwargs):
        c = super(StatsPageView, self).get_context_data(**kwargs)

        stats = []

        date = timezone.now()
        for i in range(0, 30):
            midnight = datetime(
                date.year, date.month, date.day,
                tzinfo=get_default_timezone()) + \
                timedelta(days=1)
            try:
                stat = Stats.objects.get(
                    year=date.year, month=date.month, day=date.day)
            except ObjectDoesNotExist:
                stat = Stats()
            if stat.year is None or stat.calculated_at < midnight:
                stat.calculate(date.year, date.month, date.day)
                Stats.save(stat)
            date = date - timedelta(days=1)
            setattr(stat, 'index', i)

            stats.append(stat)

        c['stats'] = list(reversed(stats))
        c['stats5'] = [stats[i] for i in range(0, 5)]
        return c


class QueryStatsPageView(LoginRequiredMixin, TemplateView):

    def execute_query(self, sql, params):
        cursor = connection.cursor()

        cursor.execute(sql, params)

        columns = [col[0] for col in cursor.description]

        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class EditorsStatsPageView(QueryStatsPageView):
    template_name = 'pages/home-editors-stats.html'

    def query_log(self, id):
        return self.execute_query(
            "select to_char(reversion_revision.date_created, \'YYYY-MM\'),"
            "username, count(*) "
            "from users_user "
            "join reversion_revision on users_user.id=user_id "
            "join reversion_version on reversion_revision.id = "
            "reversion_version.revision_id "
            "where reversion_version.content_type_id=%s "
            "group by to_char(reversion_revision.date_created, \'YYYY-MM\'), "
            "username "
            "order by 1 desc, 3 desc;", [id])

    def get_context_data(self, *args, **kwargs):
        c = super(QueryStatsPageView, self).get_context_data(**kwargs)

        c['company_log'] = self.query_log(16)
        c['product_log'] = self.query_log(15)
        c['report_log'] = self.execute_query(
            "select to_char(report_report.resolved_at, 'YYYY-MM'), username, "
            "count(*) "
            "from users_user "
            "join report_report on users_user.id=report_report.resolved_by_id "
            "group by to_char(report_report.resolved_at, 'YYYY-MM'), username "
            "order by 1 desc, 3 desc;", None)

        return c


class AdminStatsPageView(QueryStatsPageView):
    template_name = 'pages/home-admin-stats.html'

    def get_context_data(self, *args, **kwargs):
        c = super(QueryStatsPageView, self).get_context_data(**kwargs)

        c['ilim_log'] = self.execute_query(
            "select to_char(ilim_queried_at, 'YYYY-MM-DD'), count(*) "
            "from product_product "
            "group by to_char(ilim_queried_at, 'YYYY-MM-DD') "
            "order by 1 desc", None)

        return c


class AIPicsPageView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/home-ai-pics.html'

    def get_context_data(self, *args, **kwargs):
        c = super(TemplateView, self).get_context_data(**kwargs)

        if 'is_valid' in self.request.GET:
            if self.request.GET['is_valid']=='1':
                aipics = (AIPics.objects
                        .filter(is_valid=True)
                          .prefetch_related('aiattachment_set')
                        .order_by('-id')[:10])
                is_valid = True
            else:
                aipics = (AIPics.objects
                          .filter(is_valid=False)
                          .prefetch_related('aiattachment_set')
                          .order_by('-id')[:10])
                is_valid = False
        else:
            aipics = (AIPics.objects
                        .filter(is_valid__isnull=True)
                        .prefetch_related('aiattachment_set')
                        .order_by('-id')[:10])
            is_valid = None

        c['is_valid'] = is_valid
        c['aipics'] = aipics

        return c

    def post(self, request):
        if request.method == 'POST':
            if 'set_aipic_valid' in request.POST:
                aipic_id = request.POST['set_aipic_valid']
                aipic = AIPics.objects.get(id=aipic_id)
                aipic.is_valid = True
                aipic.save()
            elif 'set_aipic_not_valid' in request.POST:
                aipic_id = request.POST['set_aipic_not_valid']
                aipic = AIPics.objects.get(id=aipic_id)
                aipic.is_valid = False
                aipic.save()
            elif 'set_aipic_unverified' in request.POST:
                aipic_id = request.POST['set_aipic_unverified']
                aipic = AIPics.objects.get(id=aipic_id)
                aipic.is_valid = None
                aipic.save()
            elif 'delete_attachment' in request.POST:
                conn = S3Connection(settings.AWS_ACCESS_KEY_ID,
                                    settings.AWS_SECRET_ACCESS_KEY)
                bucket = Bucket(conn, settings.AWS_STORAGE_BUCKET_AI_NAME)
                key = Key(bucket)

                attachment_id = request.POST['delete_attachment']
                attachment = AIAttachment.objects.get(id=attachment_id)

                key.key = attachment.attachment
                bucket.delete_key(key)

                attachment.delete()
            elif 'delete_aipic' in request.POST:
                conn = S3Connection(settings.AWS_ACCESS_KEY_ID,
                                    settings.AWS_SECRET_ACCESS_KEY)
                bucket = Bucket(conn, settings.AWS_STORAGE_BUCKET_AI_NAME)
                key = Key(bucket)

                aipic_id = request.POST['delete_aipic']

                attachments = AIAttachment.objects.filter(ai_pics_id=aipic_id)
                for attachment in attachments:
                    key.key = attachment.attachment
                    bucket.delete_key(key)

                aipic = AIPics.objects.get(id=aipic_id)
                aipic.delete()

        return  HttpResponseRedirect(request.get_full_path())

