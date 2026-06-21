"""
Activity Log Signals - Auto-logging via Django Signals.
Mencatat setiap create/update/delete di semua model.
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserActivity
import json
from django.core.serializers.json import DjangoJSONEncoder
import datetime
from decimal import Decimal

import logging

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    try:
        from .middleware import get_current_request
        req = get_current_request() or request
        def get_client_ip(req):
            x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return req.META.get('REMOTE_ADDR')
        UserActivity.objects.create(
            user=user,
            action='login',
            description=f"{user.username} logged in",
            ip_address=get_client_ip(req),
            user_agent=req.META.get('HTTP_USER_AGENT', '')[:500]
        )
    except Exception as e:
        logger.warning("Error tidak terduga: %s", e)

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    try:
        if user:
            from .middleware import get_current_request
            req = get_current_request() or request
            def get_client_ip(req):
                x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0]
                return req.META.get('REMOTE_ADDR')
            UserActivity.objects.create(
                user=user,
                action='logout',
                description=f"{user.username} logged out",
                ip_address=get_client_ip(req),
                user_agent=req.META.get('HTTP_USER_AGENT', '')[:500]
            )
    except Exception as e:
        logger.warning("Error tidak terduga: %s", e)


def get_field_diff(instance, old_instance):
    if not old_instance:
        return None
    diff = {}
    skipped_fields = ['diupdate_pada', 'dibuat_pada', 'last_login', 'password',
                      'updated_at', 'created_at']
    for field in instance._meta.fields:
        field_name = field.name
        if field_name in skipped_fields:
            continue
        try:
            old_val = getattr(old_instance, field_name)
            new_val = getattr(instance, field_name)
            if isinstance(old_val, Decimal):
                old_val = float(old_val)
            if isinstance(new_val, Decimal):
                new_val = float(new_val)
            if isinstance(old_val, (datetime.date, datetime.datetime)):
                old_val = str(old_val)
            if isinstance(new_val, (datetime.date, datetime.datetime)):
                new_val = str(new_val)
            if old_val != new_val:
                if field.is_relation and old_val is not None and new_val is not None:
                    try:
                        old_val = str(old_val)
                        new_val = str(new_val)
                    except Exception as e:
                        logger.warning("Error tidak terduga: %s", e)
                diff[field_name] = {'old': old_val, 'new': new_val}
        except Exception:
            continue
    return diff


def log_model_change(sender, instance, created, **kwargs):
    try:
        if sender == UserActivity:
            return
        from .middleware import get_current_request
        request = get_current_request()
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        model_name = sender._meta.verbose_name or sender.__name__
        object_repr = str(instance)[:200]
        object_id = instance.pk
        action = 'create' if created else 'update'
        changes_json = None
        description = f"{request.user.username} {action} {model_name}: {object_repr[:100]}"
        if not created and hasattr(instance, '_old_state'):
            changes = get_field_diff(instance, instance._old_state)
            if changes:
                changes_json = json.dumps(changes, cls=DjangoJSONEncoder)
                change_desc = [f"{field}: {val['old']} -> {val['new']}" for field, val in changes.items()]
                if change_desc:
                    description = f"Update {model_name}: " + ", ".join(change_desc[:3])
                    if len(change_desc) > 3:
                        description += "..."
        def get_client_ip(req):
            x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return req.META.get('REMOTE_ADDR')
        UserActivity.objects.create(
            user=request.user,
            action=action,
            model_name=str(model_name),
            object_id=str(object_id) if object_id else None,
            object_repr=object_repr,
            description=description,
            changes=changes_json,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
    except Exception as e:
        logger.warning("Error tidak terduga: %s", e)


def log_model_delete(sender, instance, **kwargs):
    try:
        if sender == UserActivity:
            return
        from .middleware import get_current_request
        request = get_current_request()
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        model_name = sender._meta.verbose_name or sender.__name__
        object_repr = str(instance)[:200]
        object_id = instance.pk
        def get_client_ip(req):
            x_forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return req.META.get('REMOTE_ADDR')
        UserActivity.objects.create(
            user=request.user,
            action='delete',
            model_name=str(model_name),
            object_id=str(object_id) if object_id else None,
            object_repr=object_repr,
            description=f"{request.user.username} delete {model_name}: {object_repr[:100]}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
    except Exception as e:
        logger.warning("Error tidak terduga: %s", e)


def capture_old_state(sender, instance, **kwargs):
    try:
        if sender == UserActivity:
            return
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._old_state = old_instance
            except sender.DoesNotExist:
                instance._old_state = None
        else:
            instance._old_state = None
    except Exception as e:
        logger.warning("Gagal mengirim email: %s", e)


def register_signals():
    from django.apps import apps
    EXCLUDED_APPS = ['admin', 'auth', 'contenttypes', 'sessions', 'activity_log']
    EXCLUDED_MODELS = ['LogEntry', 'Permission', 'Group', 'ContentType', 'Session', 'UserActivity']
    for model in apps.get_models():
        app_label = model._meta.app_label
        model_name = model.__name__
        if app_label in EXCLUDED_APPS or model_name in EXCLUDED_MODELS:
            continue
        pre_save.connect(capture_old_state, sender=model, weak=False)
        post_save.connect(log_model_change, sender=model, weak=False)
        post_delete.connect(log_model_delete, sender=model, weak=False)
