"""Signal invalidasi cache untuk data lisensi, pembelian, laporan, dan pengaturan."""
from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save


WATCHED_APP_LABELS = {
    'licenses',
    'pembelian',
    'pengaturan',
    'permission_management',
    'user_management',
    'automation',
    'ai_assistant',
}


def invalidate_cache_after_model_change(sender, instance, raw=False, **kwargs):
    if raw:
        return

    def bump_cache_version():
        from apps.core.cache_utils import invalidate_tenant_response_cache
        invalidate_tenant_response_cache()

    try:
        transaction.on_commit(bump_cache_version)
    except Exception:
        bump_cache_version()


def register_data_cache_invalidation_signals():
    for app_label in WATCHED_APP_LABELS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            continue

        for model in app_config.get_models():
            dispatch_uid = f'core_cache_invalidation_{model._meta.label_lower}'
            post_save.connect(
                invalidate_cache_after_model_change,
                sender=model,
                dispatch_uid=f'{dispatch_uid}_save',
                weak=False,
            )
            post_delete.connect(
                invalidate_cache_after_model_change,
                sender=model,
                dispatch_uid=f'{dispatch_uid}_delete',
                weak=False,
            )
