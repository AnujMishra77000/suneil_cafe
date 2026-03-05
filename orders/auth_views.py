from django.contrib.auth import get_user_model, login, logout
from django.db import DatabaseError, IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
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
from .models import DashboardLoginActivity


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


def _is_active_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


def _active_admin_exists():
    return User.objects.filter(is_active=True, is_staff=True, is_superuser=True).exists()



def _dashboard_session_expiry_seconds():
    from django.conf import settings

    return int(getattr(settings, "DASHBOARD_SESSION_AGE_SECONDS", 12 * 60 * 60))



def _login_dashboard_user(request, user):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.cycle_key()
    request.session.set_expiry(_dashboard_session_expiry_seconds())



def _resolved_profile_contact(user):
    profile = getattr(user, "dashboard_profile", None)
    email = (getattr(profile, "email", "") or user.email or "").strip().lower()
    mobile_number = (getattr(profile, "mobile_number", "") or "").strip()
    return email, mobile_number


def _request_ip_address(request):
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    return remote_addr or None


def _track_staff_login_activity(request, user):
    if not user.is_authenticated or not user.is_staff or user.is_superuser:
        return
    email, mobile_number = _resolved_profile_contact(user)
    try:
        DashboardLoginActivity.objects.create(
            user=user,
            email=email,
            mobile_number=mobile_number,
            session_key=(request.session.session_key or "").strip(),
            ip_address=_request_ip_address(request),
        )
    except DatabaseError:
        # Do not break auth flow if activity-log table is unavailable.
        return


def _track_staff_logout_activity(request, user):
    if not user.is_authenticated or not user.is_staff or user.is_superuser:
        return

    session_key = (request.session.session_key or "").strip()
    try:
        pending_rows = DashboardLoginActivity.objects.filter(
            user=user,
            logout_at__isnull=True,
        )
    except DatabaseError:
        return

    row = None
    if session_key:
        row = pending_rows.filter(session_key=session_key).order_by("-login_at").first()
    if row is None:
        row = pending_rows.order_by("-login_at").first()
    if row is None:
        return

    try:
        row.logout_at = timezone.now()
        row.save(update_fields=["logout_at"])
    except DatabaseError:
        return


class DashboardAccessPortalView(View):
    template_name = "orders/admin_auth_portal.html"

    def get(self, request):
        if is_dashboard_staff(request.user) and not _is_active_admin(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        admin_exists = _active_admin_exists()
        cards = []
        for slug, item in PORTAL_CARD_CONFIG.items():
            # Once an admin exists, registration flows are admin-only.
            if admin_exists and slug in {"admin-register", "staff-register"} and not _is_active_admin(request.user):
                continue

            # During first bootstrap, only admin registration/login should appear.
            if not admin_exists and slug in {"staff-register", "staff-login"}:
                continue

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

        blocked = (request.GET.get("blocked") or "").strip()
        blocked_message = ""
        if blocked in {"admin-register", "staff-register"}:
            blocked_message = "Only Admin can open registration pages. Login as Admin first."

        return render(
            request,
            self.template_name,
            {
                "cards": cards,
                "next_url": request.GET.get("next", ""),
                "blocked_message": blocked_message,
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

    def _registration_allowed(self, request):
        if self.page_key == "admin-register":
            if not _active_admin_exists():
                return True
            return _is_active_admin(request.user)

        if self.page_key == "staff-register":
            return _is_active_admin(request.user)

        return True

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
        config = self._page_config()

        if config["mode"] == "login" and is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        if config["mode"] == "register" and not self._registration_allowed(request):
            if is_dashboard_staff(request.user) and not _is_active_admin(request.user):
                logout(request)
            return redirect(f"{reverse('dashboard-auth-portal')}?blocked={self.page_key}")

        form = self._form_instance()
        return render(request, self.template_name, self._context(request, form))

    def post(self, request):
        config = self._page_config()

        if config["mode"] == "login" and is_dashboard_staff(request.user):
            return redirect(_safe_next_url(request, "/admin-dashboard/"))

        if config["mode"] == "register" and not self._registration_allowed(request):
            if is_dashboard_staff(request.user) and not _is_active_admin(request.user):
                logout(request)
            return redirect(f"{reverse('dashboard-auth-portal')}?blocked={self.page_key}")

        form = self._form_instance(data=request.POST)
        if not form.is_valid():
            context = self._context(request, form, status_code=400)
            return render(request, self.template_name, context, status=400)

        if config["mode"] == "register":
            try:
                user = form.save()
            except (IntegrityError, DatabaseError):
                form.add_error(
                    None,
                    "Registration could not be completed. Please run pending migrations and try again.",
                )
                context = self._context(request, form, status_code=400)
                return render(request, self.template_name, context, status=400)
        else:
            user = form.get_user()

        _login_dashboard_user(request, user)
        _track_staff_login_activity(request, user)
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
        if request.user.is_authenticated:
            _track_staff_logout_activity(request, request.user)
        logout(request)
        return redirect(reverse("dashboard-auth-portal"))

    def get(self, request):
        if request.user.is_authenticated:
            _track_staff_logout_activity(request, request.user)
            logout(request)
        return redirect(reverse("dashboard-auth-portal"))


class DashboardAdminBootstrapView(View):
    def get(self, request):
        if _active_admin_exists() and not _is_active_admin(request.user):
            return redirect(reverse("dashboard-auth-admin-login"))
        return redirect(reverse("dashboard-auth-admin-register"))

    def post(self, request):
        if _active_admin_exists() and not _is_active_admin(request.user):
            return redirect(reverse("dashboard-auth-admin-login"))
        return redirect(reverse("dashboard-auth-admin-register"))


@method_decorator(dashboard_admin_required, name="dispatch")
class AdminStaffManageView(View):
    template_name = "orders/admin_staff_manage.html"

    def get(self, request):
        activities = list(
            DashboardLoginActivity.objects.select_related("user")
            .filter(user__is_staff=True, user__is_superuser=False)
            .order_by("-login_at")
        )
        rows = []
        for activity in activities:
            profile = getattr(activity.user, "dashboard_profile", None)
            rows.append(
                {
                    "username": (getattr(profile, "display_name", "") or activity.user.username).strip(),
                    "email": activity.email,
                    "mobile_number": activity.mobile_number,
                    "login_at": activity.login_at,
                    "logout_at": activity.logout_at,
                }
            )

        active_count = sum(1 for row in rows if row["logout_at"] is None)

        return render(
            request,
            self.template_name,
            {
                "rows": rows,
                "profile_count": DashboardAccountProfile.objects.filter(user__is_staff=True, user__is_superuser=False).count(),
                "active_count": active_count,
            },
        )
