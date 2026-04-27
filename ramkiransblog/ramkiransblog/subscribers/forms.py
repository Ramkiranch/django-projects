"""Newsletter signup form.

Single email field plus a honeypot for cheap spam protection (no
reCAPTCHA — kills UX). The honeypot field is hidden via CSS in the
template; bots see/fill it, humans don't, and we silently drop any
submission where it's non-empty.
"""
from django import forms

from .models import Subscriber


class SubscribeForm(forms.ModelForm):
    # Honeypot — must remain blank. Don't add `required=False` to the
    # widget's HTML attrs because that would tip bots off; instead we
    # just check the value in the view and treat any input as spam.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Subscriber
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'you@example.com',
                'class': 'form-control',
                'autocomplete': 'email',
                'required': True,
            }),
        }

    def clean_website(self):
        # Always returns empty string. The view checks if the raw POST
        # value was non-empty and silently drops if so.
        return ''

    def is_spam(self):
        """True if the honeypot field was filled in."""
        return bool(self.data.get('website', '').strip())
