import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views import View

from core.dashboard_auth import dashboard_admin_required, is_dashboard_staff

from .auth_forms import AdminBootstrapRegistrationForm, DashboardLoginForm, DashboardUserProvisionForm


User = get_user_model()


def _safe_next_url(request, default):
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def _dashboard_session_expiry_seconds():
    return int(getattr(settings, "DASHBOARD_SESSION_AGE_SECONDS", 12 * 60 * 60))


def _active_admin_exists():
    return User.objects.filter(is_active=True, is_staff=True, is_superuser=True).exists()


def _role_label(user):
    return "Admin" if user.is_superuser else "Staff"


def _generate_dashboard_user_id(full_name, role):
    base = slugify(full_name or "").replace("-", "") or role
    base = base[:12]
    prefix = "admin" if role == DashboardUserProvisionForm.ROLE_ADMIN else "staff"
    username = f"{prefix}{base}"[:20]

    while User.objects.filter(username__iexact=username).exists():
        suffix = str(secrets.randbelow(9000) + 1000)
        username = f"{prefix}{base[: max(1, 20 - len(prefix) - len(suffix))]}{suffix}"[:20]

    return username


def _generate_staff_password(length=14):
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(ch.islower() for ch in password) and any(ch.isupper() for ch in password) and any(ch.isdigit() for ch in password):
            return password


class DashboardLoginView(View):
    template_name = "orders/admin_auth_login.html"

    def get(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        return render(
            request,
            self.template_name,
            {
                "form": DashboardLoginForm(request=request),
                "next_url": request.GET.get("next", ""),
                "bootstrap_open": not _active_admin_exists(),
            },
        )

    def post(self, request):
        form = DashboardLoginForm(request=request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            request.session.cycle_key()
            request.session.set_expiry(_dashboard_session_expiry_seconds())
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "next_url": request.POST.get("next", ""),
                "bootstrap_open": not _active_admin_exists(),
            },
        )


class DashboardLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("/dashboard-auth/login/")

    def get(self, request):
        return redirect("/dashboard-auth/login/")


class DashboardAdminBootstrapView(View):
    template_name = "orders/admin_auth_register_admin.html"

    def get(self, request):
        if is_dashboard_staff(request.user):
            return redirect("/admin-dashboard/")

        bootstrap_open = not _active_admin_exists()
        status_code = 200 if bootstrap_open else 403
        return render(
            request,
            self.template_name,
            {
                "form": AdminBootstrapRegistrationForm(),
                "bootstrap_open": bootstrap_open,
            },
            status=status_code,
        )

    def post(self, request):
        if _active_admin_exists():
            return render(
                request,
                self.template_name,
                {
                    "form": AdminBootstrapRegistrationForm(),
                    "bootstrap_open": False,
                },
                status=403,
            )

        form = AdminBootstrapRegistrationForm(data=request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            request.session.cycle_key()
            request.session.set_expiry(_dashboard_session_expiry_seconds())
            return redirect("/admin-dashboard/")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "bootstrap_open": True,
            },
        )


@method_decorator(dashboard_admin_required, name="dispatch")
class AdminStaffManageView(View):
    template_name = "orders/admin_staff_manage.html"

    def _context(self, request, **kwargs):
        users = User.objects.filter(is_staff=True).order_by("-is_superuser", "username")
        rows = [
            {
                "username": user.username,
                "role": _role_label(user),
                "display_name": (f"{user.first_name} {user.last_name}".strip() or user.username),
                "email": user.email,
                "is_active": user.is_active,
                "last_login": user.last_login,
            }
            for user in users
        ]
        context = {
            "form": kwargs.get("form") or DashboardUserProvisionForm(),
            "rows": rows,
            "generated_user_id": kwargs.get("generated_user_id", ""),
            "generated_password": kwargs.get("generated_password", ""),
            "generated_name": kwargs.get("generated_name", ""),
            "generated_role": kwargs.get("generated_role", ""),
            "admin_master_password_configured": bool((getattr(settings, "ADMIN_MASTER_PASSWORD", "") or "").strip()),
        }
        return context

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        form = DashboardUserProvisionForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._context(request, form=form))

        full_name = form.cleaned_data["full_name"].strip()
        email = form.cleaned_data.get("email", "").strip()
        role = form.cleaned_data["role"]
        username = _generate_dashboard_user_id(full_name, role)
        password = _generate_staff_password()
        name_parts = full_name.split(None, 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        is_admin = role == DashboardUserProvisionForm.ROLE_ADMIN

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name[:150],
            last_name=last_name[:150],
            is_active=True,
            is_staff=True,
            is_superuser=is_admin,
        )

        return render(
            request,
            self.template_name,
            self._context(
                request,
                form=DashboardUserProvisionForm(initial={"role": DashboardUserProvisionForm.ROLE_STAFF}),
                generated_user_id=user.username,
                generated_password=password,
                generated_name=full_name,
                generated_role=_role_label(user),
            ),
        )
