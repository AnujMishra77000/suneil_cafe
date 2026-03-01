from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from core.dashboard_auth import dashboard_admin_required, is_dashboard_staff

from .auth_forms import (
    AdminEmailLoginForm,
    AdminRegistrationForm,
    StaffEmailLoginForm,
    StaffRegistrationForm,
)
from .models import DashboardAccountProfile


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
    from django.conf import settings

    return int(getattr(settings, "DASHBOARD_SESSION_AGE_SECONDS", 12 * 60 * 60))


def _login_dashboard_user(request, user):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.cycle_key()
    request.session.set_expiry(_dashboard_session_expiry_seconds())


def _role_label(user):
    return "Admin" if user.is_superuser else "Staff"


class DashboardLoginView(View):
    template_name = "orders/admin_auth_login.html"

    form_map = {
        "admin_register": ("admin_registration_form", AdminRegistrationForm, "admin_register"),
        "admin_login": ("admin_login_form", AdminEmailLoginForm, "admin_login"),
        "staff_register": ("staff_registration_form", StaffRegistrationForm, "staff_register"),
        "staff_login": ("staff_login_form", StaffEmailLoginForm, "staff_login"),
    }

    def _build_forms(self, data=None, action=None):
        forms = {}
        for action_name, (context_key, form_class, prefix) in self.form_map.items():
            bound_data = data if action_name == action else None
            forms[context_key] = form_class(data=bound_data, prefix=prefix)
        return forms

    def _context(self, request, **kwargs):
        context = {
            "next_url": request.POST.get("next") or request.GET.get("next", ""),
            "active_action": kwargs.get("active_action", ""),
        }
        context.update(kwargs.get("forms") or self._build_forms())
        return context

    def get(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        action = (request.POST.get("action") or "").strip()
        if action not in self.form_map:
            return render(request, self.template_name, self._context(request), status=400)

        forms = self._build_forms(data=request.POST, action=action)
        context_key, _, _ = self.form_map[action]
        form = forms[context_key]
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self._context(request, forms=forms, active_action=action),
                status=400,
            )

        if action.endswith("register"):
            user = form.save()
        else:
            user = form.get_user()

        _login_dashboard_user(request, user)
        return redirect(_safe_next_url(request, "/admin-dashboard/"))


class DashboardLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect(reverse("dashboard-auth-login"))

    def get(self, request):
        return redirect(reverse("dashboard-auth-login"))


class DashboardAdminBootstrapView(View):
    def get(self, request):
        return redirect(f"{reverse('dashboard-auth-login')}#admin-register")

    def post(self, request):
        return redirect(f"{reverse('dashboard-auth-login')}#admin-register")


@method_decorator(dashboard_admin_required, name="dispatch")
class AdminStaffManageView(View):
    template_name = "orders/admin_staff_manage.html"

    def get(self, request):
        users = User.objects.filter(is_staff=True).select_related("dashboard_profile").order_by("-is_superuser", "username")
        rows = []
        for user in users:
            profile = getattr(user, "dashboard_profile", None)
            rows.append(
                {
                    "username": user.username,
                    "role": _role_label(user),
                    "email": getattr(profile, "email", user.email or "-"),
                    "mobile_number": getattr(profile, "mobile_number", "-"),
                    "is_active": user.is_active,
                    "last_login": user.last_login,
                }
            )

        return render(
            request,
            self.template_name,
            {
                "rows": rows,
                "login_url": reverse("dashboard-auth-login"),
                "profile_count": DashboardAccountProfile.objects.count(),
            },
        )
