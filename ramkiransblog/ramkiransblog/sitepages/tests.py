from django.test import TestCase
from django.urls import reverse


class AboutViewTests(TestCase):
    def test_about_returns_200(self):
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)

    def test_about_uses_template(self):
        response = self.client.get(reverse('about'))
        self.assertTemplateUsed(response, 'sitepages/about.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_about_renders_bio(self):
        response = self.client.get(reverse('about'))
        self.assertContains(response, 'Ramkiran')

    def test_about_includes_dark_cta(self):
        """The May 2026 redesign added an inverted dark subscribe block
        at the bottom of the about page."""
        response = self.client.get(reverse('about'))
        self.assertContains(response, 'class="subs-about-prominent"')
        # CTA form still posts to the existing subscribe endpoint
        self.assertContains(response, 'action="/subscribe/"')
