"""Subscriber: a single email signup.

We store emails locally in Postgres now and stay provider-agnostic so
we can later import the list into Buttondown / ConvertKit / Substack /
self-hosted Listmonk without re-architecting. `confirmed` exists as a
forward-looking field for when we add double-opt-in via SMTP.
"""
from django.db import models


class Subscriber(models.Model):
    SOURCE_CHOICES = [
        ('footer', 'Footer signup'),
        ('post-end', 'Post-end signup'),
        ('about', 'About-page signup'),
        ('admin', 'Manually added in admin'),
    ]

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='footer')
    confirmed = models.BooleanField(
        default=False,
        help_text='Set True when double-opt-in is added later. Currently unused.',
    )
    unsubscribed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email
