from django.urls import reverse_lazy
from test_plus.test import TestCase

from pola.users.factories import StaffFactory


class PermissionMixin:
    def setUp(self):
        super().setUp()
        self.user = StaffFactory()

    def login(self, username=None):
        self.client.login(username=username or self.user.username, password='pass')

    def test_anonymous_denied(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)


class TemplateUsedMixin:
    def test_template_used(self):
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, self.template_name)


class HomeTestCase(TemplateUsedMixin, TestCase):
    url = reverse_lazy('home')
    template_name = 'index.html'


class SelectLangTestCase(PermissionMixin, TemplateUsedMixin, TestCase):
    url = reverse_lazy('select_lang')
    template_name = 'pages/lang-cms.html'

    def test_template_used(self):
        self.login()
        super().test_template_used()


class AboutTestCase(TemplateUsedMixin, TestCase):
    url = reverse_lazy('about')
    template_name = 'pages/about.html'


class FaviconsTestCase(TestCase):
    def test_redirect_happens(self):
        from pola.config.urls import FAVICON_FILES

        for filename in FAVICON_FILES:
            resp = self.client.get('/' + filename, follow=False)
            self.assertEqual(resp.status_code, 301, "Invalid redirect status code")
