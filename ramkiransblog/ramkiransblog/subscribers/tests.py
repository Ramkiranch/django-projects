"""Tests for the subscribers app.

Covers the happy path (POST a valid email creates a Subscriber), the
silent-on-duplicate behavior (don't leak which addresses are subscribed),
honeypot rejection (spam returns success but writes nothing), and the
admin CSV export.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Subscriber


class SubscribeFormTests(TestCase):
    def test_valid_email_creates_subscriber(self):
        response = self.client.post(reverse('subscribe'), {
            'email': 'reader@example.com',
            'source': 'footer',
            'website': '',
        })
        # Redirects back (to home in this case since no Referer)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subscriber.objects.filter(email='reader@example.com').exists())
        sub = Subscriber.objects.get(email='reader@example.com')
        self.assertEqual(sub.source, 'footer')

    def test_post_end_source_is_recorded(self):
        self.client.post(reverse('subscribe'), {
            'email': 'reader2@example.com',
            'source': 'post-end',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader2@example.com')
        self.assertEqual(sub.source, 'post-end')

    def test_invalid_source_falls_back_to_footer(self):
        self.client.post(reverse('subscribe'), {
            'email': 'reader3@example.com',
            'source': 'malicious-injected-value',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader3@example.com')
        self.assertEqual(sub.source, 'footer')

    def test_duplicate_email_does_not_error_or_duplicate(self):
        Subscriber.objects.create(email='dup@example.com', source='footer')
        response = self.client.post(reverse('subscribe'), {
            'email': 'dup@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Subscriber.objects.filter(email='dup@example.com').count(), 1)

    def test_honeypot_filled_silently_drops_submission(self):
        response = self.client.post(reverse('subscribe'), {
            'email': 'bot@example.com',
            'source': 'footer',
            'website': 'https://spam.example.com',
        })
        self.assertEqual(response.status_code, 302)  # success-shaped redirect
        self.assertFalse(Subscriber.objects.filter(email='bot@example.com').exists())

    def test_get_returns_405(self):
        response = self.client.get(reverse('subscribe'))
        self.assertEqual(response.status_code, 405)

    def test_invalid_email_does_not_create_subscriber(self):
        self.client.post(reverse('subscribe'), {
            'email': 'not-an-email',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(Subscriber.objects.count(), 0)


class CSVExportTests(TestCase):
    def setUp(self):
        Subscriber.objects.create(email='a@example.com', source='footer')
        Subscriber.objects.create(email='b@example.com', source='post-end')
        # Create a superuser and log in to access admin
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pwd-not-used')
        self.client.force_login(self.admin)

    def test_admin_csv_export_returns_csv(self):
        # Trigger the admin action via the changelist view
        response = self.client.post(
            '/rk-admin/subscribers/subscriber/',
            {
                'action': 'export_as_csv',
                '_selected_action': [str(s.pk) for s in Subscriber.objects.all()],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('email,source,confirmed,unsubscribed,created_at', body)
        self.assertIn('a@example.com', body)
        self.assertIn('b@example.com', body)
