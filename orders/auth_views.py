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


PORTAL_CARD_CONFIG = {
    "admin-register": {
        "title": "Admin Registration",
        "eyebrow": "Create Admin",
        "description": "Register a fresh Admin account with user name, mobile number, mail ID, password, and master password.",
        "button_label": "Register Admin",
        "url_name": "dashboard-auth-admin-register",
    },
    "admin-login": {
        "title": "Login as Admin",
        "eyebrow": "Admin Access",
        "description": "Open the Admin login form and access the operations dashboard with mail ID and password.",
        "button_label": "Admin Login",
        "url_name": "dashboard-auth-admin-login",
    },
    "staff-register": {
        "title": "Staff Registration",
        "eyebrow": "Create Staff",
        "description": "Register a Staff account with user name, mobile number, mail ID, password, and master password.",
        "button_label": "Register Staff",
        "url_name": "dashboard-auth-staff-register",
    },
    "staff-login": {
        "title": "Login as Staff",
        "eyebrow": "Staff Access",
        "description": "Open the Staff login form and sign in with mail ID and password.",
        "button_label": "Staff Login",
        "url_name": "dashboard-auth-staff-login",
    },
}


FORM_PAGE_CONFIG = {
    "admin-register": {
        "title": "Admin Registration",
        "eyebrow": "Create Admin",
        "description": "Fill every field carefully. Admin accounts require the master password and will get full dashboard access.",
        "submit_label": "Register as Admin",
        "form_class": AdminRegistrationForm,
        "prefix": "admin_register",
        "success_redirect": "/admin-dashboard/",
        "mode": "register",
    },
    "admin-login": {
        "title": "Login as Admin",
        "eyebrow": "Admin Access",
        "description": "Use your registered mail ID and password to open the Admin dashboard.",
        "submit_label": "Login as Admin",
        "form_class": AdminEmailLoginForm,
        "prefix": "admin_login",
        "success_redirect": "/admin-dashboard/",
        "mode": "login",
    },
    "staff-register": {
        "title": "Staff Registration",
        "eyebrow": "Create Staff",
        "description": "Create a Staff account with all required profile fields. Staff registration also requires the master password.",
        "submit_label": "Register as Staff",
        "form_class": StaffRegistrationForm,
        "prefix": "staff_register",
        "success_redirect": "/admin-dashboard/",
        "mode": "register",
    },
    "staff-login": {
        "title": "Login as Staff",
        "eyebrow": "Staff Access",
        "description": "Use your registered mail ID and password to enter the Staff dashboard access flow.",
        "submit_label": "Login as Staff",
        "form_class": StaffEmailLoginForm,
        "prefix": "staff_login",
        "success_redirect": "/admin-dashboard/",
        "mode": "login",
    },
}


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


class DashboardAccessPortalView(View):
    template_name = "orders/admin_auth_portal.html"

    def get(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        cards = []
        for slug, item in PORTAL_CARD_CONFIG.items():
            cards.append(
                {
                    "slug": slug,
                    "title": item["title"],
                    "eyebrow": item["eyebrow"],
                    "description": item["description"],
                    "button_label": item["button_label"],
                    "url": reverse(item["url_name"]),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "cards": cards,
                "next_url": request.GET.get("next", ""),
            },
        )


class DashboardAuthFormView(View):
    template_name = "orders/admin_auth_form.html"
    page_key = ""

    def _page_config(self):
        return FORM_PAGE_CONFIG[self.page_key]

    def _form_instance(self, data=None):
        config = self._page_config()
        return config["form_class"](data=data, prefix=config["prefix"])

    def _context(self, request, form, status_code=200):
        config = self._page_config()
        return {
            "page_title": config["title"],
            "page_eyebrow": config["eyebrow"],
            "page_description": config["description"],
            "submit_label": config["submit_label"],
            "form": form,
            "mode": config["mode"],
            "next_url": request.POST.get("next") or request.GET.get("next", ""),
            "portal_url": reverse("dashboard-auth-portal"),
            "status_code": status_code,
        }

    def get(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))
        form = self._form_instance()
        return render(request, self.template_name, self._context(request, form))

    def post(self, request):
        if is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        form = self._form_instance(data=request.POST)
        if not form.is_valid():
            context = self._context(request, form, status_code=400)
            return render(request, self.template_name, context, status=400)

        config = self._page_config()
        if config["mode"] == "register":
            user = form.save()
        else:
            user = form.get_user()

        _login_dashboard_user(request, user)
        return redirect(_safe_next_url(request, config["success_redirect"]))


class DashboardAdminRegisterView(DashboardAuthFormView):
    page_key = "admin-register"


class DashboardAdminLoginView(DashboardAuthFormView):
    page_key = "admin-login"


class DashboardStaffRegisterView(DashboardAuthFormView):
    page_key = "staff-register"


class DashboardStaffLoginView(DashboardAuthFormView):
    page_key = "staff-login"


class DashboardLoginView(View):
    def get(self, request):
        return redirect(reverse("dashboard-auth-portal"))

    def post(self, request):
        return redirect(reverse("dashboard-auth-portal"))


class DashboardLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect(reverse("dashboard-auth-portal"))

    def get(self, request):
        return redirect(reverse("dashboard-auth-portal"))


class DashboardAdminBootstrapView(View):
    def get(self, request):
        return redirect(reverse("dashboard-auth-admin-register"))

    def post(self, request):
        return redirect(reverse("dashboard-auth-admin-register"))


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
                "login_url": reverse("dashboard-auth-portal"),
                "profile_count": DashboardAccountProfile.objects.count(),
            },
        )
