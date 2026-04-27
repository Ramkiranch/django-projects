"""Tests for the subscribers app.

Covers signup happy path, silent-on-duplicate behavior, honeypot rejection,
admin CSV export, signed-token roundtrip, and confirm/unsubscribe view
behavior. Email sending is patched out — we only verify that send is
called with the right subscriber, not that Resend actually delivers.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Subscriber
from .tokens import make_token, read_token


# Patch Resend send across the whole test module — we never want a real
# API call from CI / local test runs even if RESEND_API_KEY is set.
@patch('subscribers.views.send_confirmation_email', return_value=True)
class SubscribeFormTests(TestCase):
    def test_valid_email_creates_subscriber(self, mock_send):
        response = self.client.post(reverse('subscribe'), {
            'email': 'reader@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subscriber.objects.filter(email='reader@example.com').exists())
        sub = Subscriber.objects.get(email='reader@example.com')
        self.assertEqual(sub.source, 'footer')
        self.assertFalse(sub.confirmed)  # double-opt-in: not confirmed yet
        mock_send.assert_called_once()

    def test_post_end_source_is_recorded(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'reader2@example.com',
            'source': 'post-end',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader2@example.com')
        self.assertEqual(sub.source, 'post-end')

    def test_invalid_source_falls_back_to_footer(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'reader3@example.com',
            'source': 'malicious-injected-value',
            'website': '',
        })
        sub = Subscriber.objects.get(email='reader3@example.com')
        self.assertEqual(sub.source, 'footer')

    def test_duplicate_unconfirmed_resends_confirmation(self, mock_send):
        Subscriber.objects.create(email='dup@example.com', source='footer', confirmed=False)
        response = self.client.post(reverse('subscribe'), {
            'email': 'dup@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Subscriber.objects.filter(email='dup@example.com').count(), 1)
        mock_send.assert_called_once()  # re-send for unconfirmed

    def test_duplicate_already_confirmed_does_not_resend(self, mock_send):
        Subscriber.objects.create(email='conf@example.com', source='footer', confirmed=True)
        response = self.client.post(reverse('subscribe'), {
            'email': 'conf@example.com',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(response.status_code, 302)
        mock_send.assert_not_called()

    def test_honeypot_filled_silently_drops_submission(self, mock_send):
        response = self.client.post(reverse('subscribe'), {
            'email': 'bot@example.com',
            'source': 'footer',
            'website': 'https://spam.example.com',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Subscriber.objects.filter(email='bot@example.com').exists())
        mock_send.assert_not_called()

    def test_get_returns_405(self, mock_send):
        response = self.client.get(reverse('subscribe'))
        self.assertEqual(response.status_code, 405)

    def test_invalid_email_does_not_create_subscriber(self, mock_send):
        self.client.post(reverse('subscribe'), {
            'email': 'not-an-email',
            'source': 'footer',
            'website': '',
        })
        self.assertEqual(Subscriber.objects.count(), 0)
        mock_send.assert_not_called()


class TokenTests(TestCase):
    def test_token_roundtrip_returns_subscriber_id(self):
        token = make_token(42, action='confirm')
        self.assertEqual(read_token(token, action='confirm', max_age_seconds=3600), 42)

    def test_token_with_wrong_action_salt_fails(self):
        token = make_token(42, action='confirm')
        with self.assertRaises(signing.BadSignature):
            read_token(token, action='unsubscribe', max_age_seconds=3600)

    def test_expired_token_raises(self):
        token = make_token(42, action='confirm')
        with self.assertRaises(signing.SignatureExpired):
            # max_age=0 forces immediate expiration
            read_token(token, action='confirm', max_age_seconds=0)

    def test_unknown_action_raises_value_error(self):
        with self.assertRaises(ValueError):
            make_token(42, action='nonsense')


class ConfirmViewTests(TestCase):
    def setUp(self):
        self.subscriber = Subscriber.objects.create(
            email='unconfirmed@example.com', source='footer', confirmed=False,
        )

    def test_valid_token_confirms_subscriber(self):
        token = make_token(self.subscriber.id, action='confirm')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.confirmed)
        self.assertContains(response, "You're in", status_code=200)

    def test_tampered_token_returns_400(self):
        response = self.client.get(reverse('subscribe_confirm', args=['not-a-real-token']))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.confirmed)

    def test_token_for_missing_subscriber_returns_400(self):
        token = make_token(99999, action='confirm')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_token_does_not_confirm(self):
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.confirmed)

    def test_confirm_re_subscribes_unsubscribed_user(self):
        self.subscriber.unsubscribed = True
        self.subscriber.save()
        token = make_token(self.subscriber.id, action='confirm')
        self.client.get(reverse('subscribe_confirm', args=[token]))
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.confirmed)
        self.assertFalse(self.subscriber.unsubscribed)


class UnsubscribeViewTests(TestCase):
    def setUp(self):
        self.subscriber = Subscriber.objects.create(
            email='subscribed@example.com', source='footer', confirmed=True,
        )

    def test_valid_token_unsubscribes(self):
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.subscriber.refresh_from_db()
        self.assertTrue(self.subscriber.unsubscribed)

    def test_confirm_token_does_not_unsubscribe(self):
        token = make_token(self.subscriber.id, action='confirm')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.subscriber.refresh_from_db()
        self.assertFalse(self.subscriber.unsubscribed)

    def test_already_unsubscribed_is_idempotent(self):
        self.subscriber.unsubscribed = True
        self.subscriber.save()
        token = make_token(self.subscriber.id, action='unsubscribe')
        response = self.client.get(reverse('subscribe_unsubscribe', args=[token]))
        self.assertEqual(response.status_code, 200)


@override_settings(RESEND_API_KEY='re_fake_key_for_tests')
class EmailSendTests(TestCase):
    """Verify our wrapper calls the Resend SDK with the right shape."""

    def test_send_confirmation_email_calls_resend(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target@example.com', source='footer')

        with patch('resend.Emails.send') as mock_send:
            ok = emails.send_confirmation_email(sub)

        self.assertTrue(ok)
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        params = args[0]
        self.assertEqual(params['to'], ['target@example.com'])
        self.assertIn('Confirm your subscription', params['subject'])
        # Both html + text bodies sent (multipart)
        self.assertIn('html', params)
        self.assertIn('text', params)
        # Body contains a confirm URL with /subscribe/confirm/ in it
        self.assertIn('/subscribe/confirm/', params['html'])
        self.assertIn('/subscribe/confirm/', params['text'])

    def test_send_returns_false_when_resend_raises(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target2@example.com', source='footer')

        with patch('resend.Emails.send', side_effect=Exception('boom')):
            ok = emails.send_confirmation_email(sub)

        self.assertFalse(ok)

    @override_settings(RESEND_API_KEY='')
    def test_send_returns_false_when_no_api_key(self):
        from subscribers import emails

        sub = Subscriber.objects.create(email='target3@example.com', source='footer')
        ok = emails.send_confirmation_email(sub)
        self.assertFalse(ok)


class CSVExportTests(TestCase):
    def setUp(self):
        Subscriber.objects.create(email='a@example.com', source='footer')
        Subscriber.objects.create(email='b@example.com', source='post-end')
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pwd-not-used')
        self.client.force_login(self.admin)

    def test_admin_csv_export_returns_csv(self):
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
