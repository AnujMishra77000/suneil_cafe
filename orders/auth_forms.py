from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.crypto import constant_time_compare


User = get_user_model()


class DashboardLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="User ID",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Invalid user ID or password.",
        "inactive": "This account is inactive.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("This account does not have dashboard access.", code="not_staff")


class AdminBootstrapRegistrationForm(UserCreationForm):
    master_password = forms.CharField(
        label="Master Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Required to create the first admin account.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def clean_master_password(self):
        provided = (self.cleaned_data.get("master_password") or "").strip()
        expected = (getattr(settings, "ADMIN_MASTER_PASSWORD", "") or "").strip()
        if not expected:
            raise forms.ValidationError("ADMIN_MASTER_PASSWORD is not configured on the server.")
        if not constant_time_compare(provided, expected):
            raise forms.ValidationError("Master password is invalid.")
        return provided

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user


class DashboardUserProvisionForm(forms.Form):
    ROLE_STAFF = "staff"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = (
        (ROLE_STAFF, "Staff"),
        (ROLE_ADMIN, "Admin"),
    )

    full_name = forms.CharField(label="Team Member Name", max_length=150)
    email = forms.EmailField(label="Email", required=False)
    role = forms.ChoiceField(label="Role", choices=ROLE_CHOICES)
    master_password = forms.CharField(
        label="Master Password",
        strip=False,
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Required only when creating an Admin account.",
    )

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        provided = (cleaned_data.get("master_password") or "").strip()
        if role == self.ROLE_ADMIN:
            expected = (getattr(settings, "ADMIN_MASTER_PASSWORD", "") or "").strip()
            if not expected:
                self.add_error("master_password", "ADMIN_MASTER_PASSWORD is not configured on the server.")
            elif not constant_time_compare(provided, expected):
                self.add_error("master_password", "Master password is invalid.")
        return cleaned_data
