from django.apps import AppConfig


class PermissionManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.permission_management'
    verbose_name = 'Permission Management'

    def ready(self):
        import apps.permission_management.signals  # lazy import
