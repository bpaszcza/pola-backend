from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse, reverse_lazy
from django_webtest import WebTestMixin
from reversion.models import Version
from test_plus.test import TestCase

from company.factories import CompanyFactory
from company.forms import CompanyCreateFromKRSForm
from company.models import Company
from pola.mojepanstwo_api2.krs import CompanyInfo
from pola.tests import PermissionMixin
from pola.users.factories import StaffFactory, UserFactory


class TemplateUsedMixin:
    def test_template_used(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, self.template_name)


class InstanceMixin:
    def setUp(self):
        super().setUp()
        self.instance = CompanyFactory()

    def test_contains_official_name(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertContains(resp, self.instance.official_name)


class CompanyCreateViewTestCase(PermissionMixin, TemplateUsedMixin, TestCase):
    url = reverse_lazy('company:create')
    template_name = 'company/company_form.html'


class CompanyCreateFromKRSViewTestCase(PermissionMixin, TemplateUsedMixin, WebTestMixin, TestCase):
    url = reverse_lazy('company:create_from_krs')
    template_name = 'company/company_from_krs.html'

    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_success_by_nip(self, mock_tool):
        mock_tool.return_value = [self._get_mock()]

        page = self.app.get(self.url, user=self.user)
        page.form['is_krs'] = 0
        page.form['no'] = "123"
        page = page.form.submit()

        self.assertTrue(page.url.count("TEST1") == 1)
        self.assertTrue(page.url.count("TEST2") == 1)
        self.assertTrue(page.url.count("TEST3") == 1)
        self.assertTrue(page.url.count("123") == 1)
        self.assertTrue(page.url.count("URL") == 1)
        self.assertTrue(page.url.count(reverse('company:create')) == 1)

    def _get_mock(self):
        data = {
            "id": 1,
            "nazwa": "TEST1",
            "nazwa_skrocona": "TEST2",
            "nip": "123",
            "adres": "TEST3",
            "liczba_wspolnikow": 3,
            "score": "333",
            "url": "URL",
        }
        return CompanyInfo(**data)


class CompanyUpdateTestCase(InstanceMixin, PermissionMixin, TemplateUsedMixin, TestCase):
    template_name = 'company/company_form.html'

    def setUp(self):
        super().setUp()
        self.url = reverse('company:edit', kwargs={'pk': self.instance.pk})


class CompanyUpdateWebTestCase(WebTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.instance = CompanyFactory(name="company_name")
        self.url = reverse('company:edit', kwargs={'pk': self.instance.pk})
        self.user = StaffFactory()

    def test_form_success(self):
        page = self.app.get(self.url, user=self.user)
        page.form['official_name'] = "New name"
        page.form['commit_desc'] = "Commit description"
        page = page.form.submit()

        self.assertRedirects(page, self.instance.get_absolute_url())
        self.instance.refresh_from_db()
        versions = Version.objects.get_for_object(self.instance)
        self.assertEqual(versions[0].revision.comment, "Commit description")
        self.assertEqual(versions[0].revision.user, self.user)
        self.assertEqual(self.instance.official_name, "New name")

    @override_settings(LANGUAGE_CODE='en-EN')
    def test_form_commit_desc_required(self):
        page = self.app.get(self.url, user=self.user)
        page.form['official_name'] = "New name"
        page = page.form.submit()

        self.assertContains(page, "This field is required.")

        page.form['commit_desc'] = "AAA"
        page = page.form.submit()

        self.assertRedirects(page, self.instance.get_absolute_url())

    @override_settings(LANGUAGE_CODE='en-EN')
    def test_form_readonly_fields(self):
        page = self.app.get(self.url, user=self.user)
        self.assertEqual(page.form['name'].attrs['disabled'], 'true')

        page.form['name'] = "789789789"
        page.form['commit_desc'] = "Commit desc"
        page = page.form.submit()

        self.assertRedirects(page, self.instance.get_absolute_url())
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.name, "company_name")


class ConcurencyComapnyUpdateTestCase(TestCase):
    user_factory = UserFactory

    def setUp(self):
        super().setUp()
        self.instance = CompanyFactory()

    def test_restrictions(self):
        user1 = self.make_user('u1', perms=['company.view_company', 'company.change_company'])
        user2 = self.make_user('u2', perms=['company.view_company', 'company.change_company'])
        url = reverse('company:edit', kwargs={'pk': self.instance.pk})

        with self.login(username=user1.username):
            response = self.get(url)
            self.response_200(response)

        with self.login(username=user2.username):
            response = self.get(url)
            self.response_302(response)


class CompanyDeleteViewTestCase(InstanceMixin, PermissionMixin, TemplateUsedMixin, TestCase):
    template_name = 'company/company_confirm_delete.html'

    def setUp(self):
        super().setUp()
        self.url = reverse('company:delete', kwargs={'pk': self.instance.pk})

    def test_object_delete(self):
        self.login()
        self.client.post(self.url)
        self.assertFalse(Company.objects.filter(pk=self.instance.pk).exists())


class CompanyDetailViewTestCase(InstanceMixin, PermissionMixin, TemplateUsedMixin, TestCase):
    template_name = 'company/company_detail.html'

    def setUp(self):
        super().setUp()
        self.url = reverse('company:detail', kwargs={'pk': self.instance.pk})


class CompanyListViewTestCase(PermissionMixin, TemplateUsedMixin, WebTestMixin, TestCase):
    url = reverse_lazy('company:list')
    template_name = 'company/company_filter.html'

    def test_empty(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertContains(resp, "Nie znaleziono producentów spełniających zadane kryteria")

    def test_filled(self):
        products = CompanyFactory.create_batch(100)
        page = self.app.get(self.url, user=self.user)
        # self.assertTrue("1 z 4" in page)
        self.assertTrue(str(products[-1]) in page)
        page2 = page.click("Następne")
        page2.click("Poprzednie")


class CompanyCreateFromKRSFormTestCase(TestCase):
    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_existings_compnay_in_db(self, mock_tool):
        CompanyFactory(nip=123)
        mock_tool.return_value = [self._get_mock()]
        data = {'is_krs': '1', 'no': 123}
        form = CompanyCreateFromKRSForm(data=data)
        self.assertFalse(form.is_valid())

    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_multiple_company(self, mock_tool):
        mock_tool.return_value = [
            self._get_mock(),
            self._get_mock(),
        ]
        data = {'is_krs': '1', 'no': 123}
        form = CompanyCreateFromKRSForm(data=data)
        self.assertFalse(form.is_valid())

    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_no_company_in_remote_api(self, mock_tool):
        mock_tool.return_value = []
        data = {'is_krs': '1', 'no': 123}
        form = CompanyCreateFromKRSForm(data=data)
        self.assertFalse(form.is_valid())

    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_success(self, mock_tool):
        mock_tool.return_value = [self._get_mock()]
        data = {'is_krs': '1', 'no': 123}
        form = CompanyCreateFromKRSForm(data=data)
        self.assertTrue(form.is_valid())

    @patch('pola.mojepanstwo_api2.krs.Krs.get_companies')
    def test_success_by_nip(self, mock_tool):
        mock_tool.return_value = [self._get_mock()]
        data = {'is_krs': '0', 'no': 123}
        form = CompanyCreateFromKRSForm(data=data)
        self.assertTrue(form.is_valid())

    def _get_mock(self):
        data = {
            "id": 1,
            "nazwa": "AA",
            "nazwa_skrocona": "BB",
            "nip": "123",
            "adres": "AAAA",
            "liczba_wspolnikow": 3,
            "score": "333",
            "url": "",
        }
        return CompanyInfo(**data)


class CompanyAutocomplete(PermissionMixin, TestCase):
    url = reverse_lazy('company:company-autocomplete')
