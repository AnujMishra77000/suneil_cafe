from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils.crypto import constant_time_compare
import re

from .models import DashboardAccountProfile


User = get_user_model()


class _DashboardMasterPasswordMixin:
    @staticmethod
    def _expected_master_password():
        return (getattr(settings, "ADMIN_MASTER_PASSWORD", "") or "").strip()

    def clean_master_password(self):
        provided = (self.cleaned_data.get("master_password") or "").strip()
        expected = self._expected_master_password()
        if not expected:
            raise forms.ValidationError("ADMIN_MASTER_PASSWORD is not configured on the server.")
        if not constant_time_compare(provided, expected):
            raise forms.ValidationError("Master password is invalid.")
        return provided


class BaseDashboardRegistrationForm(_DashboardMasterPasswordMixin, UserCreationForm):
    username = forms.CharField(
        label="User Name",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
        help_text="Use letters and spaces only. Example: Anuj Mishra",
    )
    email = forms.EmailField(
        label="Mail ID",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    mobile_number = forms.CharField(
        label="Mobile No.",
        max_length=15,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "tel"}),
    )
    master_password = forms.CharField(
        label="Master Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    target_is_superuser = False
    target_role_label = "Staff"

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "User Name"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "placeholder": "Enter full name"})
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm Password"

    @staticmethod
    def normalize_mobile_number(value):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if len(digits) != 10:
            raise forms.ValidationError("Mobile number must be exactly 10 digits.")
        return digits

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Mail ID is required.")
        if DashboardAccountProfile.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This mail ID is already in use.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This mail ID is already in use.")
        return email

    def clean_username(self):
        display_name = " ".join(str(self.cleaned_data.get("username") or "").strip().split())
        if not display_name:
            raise forms.ValidationError("User Name is required.")
        if not re.fullmatch(r"[A-Za-z ]+", display_name):
            raise forms.ValidationError("User Name can contain only letters and spaces.")

        # Keep a clean display name while storing a backend-safe username key.
        self.cleaned_data["display_name"] = display_name
        username = display_name.lower().replace(" ", "_")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This user name is already in use.")
        return username

    def clean_mobile_number(self):
        mobile_number = self.normalize_mobile_number(self.cleaned_data.get("mobile_number"))
        if DashboardAccountProfile.objects.filter(mobile_number=mobile_number).exists():
            raise forms.ValidationError("This mobile number is already in use.")
        return mobile_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = True
        user.is_staff = True
        user.is_superuser = self.target_is_superuser
        if commit:
            with transaction.atomic():
                user.save()
                DashboardAccountProfile.objects.create(
                    user=user,
                    display_name=self.cleaned_data.get("display_name", ""),
                    email=self.cleaned_data["email"],
                    mobile_number=self.cleaned_data["mobile_number"],
                )
        return user


class AdminRegistrationForm(BaseDashboardRegistrationForm):
    target_is_superuser = True
    target_role_label = "Admin"


class StaffRegistrationForm(BaseDashboardRegistrationForm):
    target_is_superuser = False
    target_role_label = "Staff"


class BaseDashboardEmailLoginForm(forms.Form):
    email = forms.EmailField(
        label="Mail ID",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    required_role = "staff"
    role_label = "Staff"
    user_cache = None

    def _resolve_user(self, email):
        profile = DashboardAccountProfile.objects.select_related("user").filter(email__iexact=email).first()
        if profile:
            return profile.user

        matches = list(User.objects.filter(email__iexact=email, is_active=True, is_staff=True).order_by("id")[:2])
        if len(matches) == 1:
            return matches[0]
        return None

    def clean(self):
        cleaned_data = super().clean()
        email = (cleaned_data.get("email") or "").strip().lower()
        password = cleaned_data.get("password") or ""
        if not email or not password:
            return cleaned_data

        user = self._resolve_user(email)
        if user is None or not user.check_password(password):
            raise forms.ValidationError("Invalid mail ID or password.")
        if not user.is_active:
            raise forms.ValidationError("This account is inactive.")
        if not user.is_staff:
            raise forms.ValidationError("This account does not have dashboard access.")
        if self.required_role == "admin" and not user.is_superuser:
            raise forms.ValidationError("This mail ID is not registered as an Admin account.")
        if self.required_role == "staff" and user.is_superuser:
            raise forms.ValidationError("This mail ID is not registered as a Staff account.")

        self.user_cache = user
        cleaned_data["email"] = email
        return cleaned_data

    def get_user(self):
        return self.user_cache


class AdminEmailLoginForm(BaseDashboardEmailLoginForm):
    required_role = "admin"
    role_label = "Admin"


class StaffEmailLoginForm(BaseDashboardEmailLoginForm):
    required_role = "staff"
    role_label = "Staff"
