from django import forms
from django.forms.widgets import DateInput, TextInput
from django.forms import CheckboxSelectMultiple
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Row, Column
from .models import *


#custom password reset
class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Enter your email",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("No user with this email address found.")
        return email
