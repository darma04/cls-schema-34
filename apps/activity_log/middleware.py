"""
ActivityLog Middleware - Menyimpan request ke thread-local
agar signals bisa mengakses user yang sedang login.
"""
from django.utils.deprecation import MiddlewareMixin
from .models import UserActivity
from threading import local

import logging

logger = logging.getLogger(__name__)


_thread_locals = local()


def get_current_request():
    return getattr(_thread_locals, 'request', None)


def set_current_request(request):
    _thread_locals.request = request


class ActivityLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        set_current_request(request)
        request._activity_logged = False
        return None

    def process_response(self, request, response):
        set_current_request(None)
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def log_activity(request, action, model_name=None, object_id=None, object_repr=None, description=None, changes=None):
        if not request.user.is_authenticated:
            return
        if hasattr(request, '_activity_logged') and request._activity_logged:
            return
        try:
            activity = UserActivity.objects.create(
                user=request.user,
                action=action,
                model_name=model_name,
                object_id=str(object_id) if object_id else None,
                object_repr=object_repr,
                description=description,
                ip_address=ActivityLogMiddleware().get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if changes:
                activity.set_changes(changes)
                activity.save()
            request._activity_logged = True
        except Exception as e:
            logger.warning("Gagal mencatat activity log: %s", e)
