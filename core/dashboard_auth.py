from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


def is_dashboard_staff(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def is_dashboard_admin(user):
    return is_dashboard_staff(user) and bool(getattr(user, "is_superuser", False))


def _dashboard_gate(check_func):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url=reverse("dashboard-auth-login"))
            if not check_func(request.user):
                raise PermissionDenied("You do not have access to this page.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


dashboard_staff_required = _dashboard_gate(is_dashboard_staff)
dashboard_admin_required = _dashboard_gate(is_dashboard_admin)
