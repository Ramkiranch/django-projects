"""Newsletter signup form.

Plain `forms.Form` (NOT a ModelForm) so we don't fire Django's
UniqueValidator on duplicate emails — duplicates are handled by
`get_or_create` in the view (which lets us re-send confirmation
emails when an existing-but-unconfirmed user re-signs up).

Honeypot pattern: the `website` field is hidden via CSS in the
template; bots see/fill it, humans don't, view drops any submission
where it's non-empty.
"""
from django import forms


class SubscribeForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'you@example.com',
            'class': 'form-control',
            'autocomplete': 'email',
            'required': True,
        }),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    def is_spam(self) -> bool:
        """True if the honeypot field was filled in."""
        return bool(self.data.get('website', '').strip())
