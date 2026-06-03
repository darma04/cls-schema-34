"""
==========================================================================
 CORE APPS - Konfigurasi Aplikasi Core
==========================================================================
 File ini mengkonfigurasi aplikasi 'apps.core' sebagai Django App.

 Core adalah modul INTI yang berisi:
 - RolePermission model (RBAC)
 - Permission checking functions
 - Permission mixins untuk views
 - Context processors untuk template
 - Cache utilities

 Koneksi:
 - config/settings.py → INSTALLED_APPS: "apps.core"
 - Semua apps lain → Menggunakan mixin dan permission dari core
==========================================================================
"""

from django.apps import AppConfig  # Base class untuk konfigurasi app


class CoreConfig(AppConfig):
    """
    Konfigurasi aplikasi Core.

    Atribut:
    - default_auto_field: Tipe field ID otomatis (BigAutoField = integer 64-bit)
    - name: Nama modul Python lengkap (harus 'apps.core' karena ada di subfolder apps/)
    - verbose_name: Nama yang ditampilkan di admin panel
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'   # Path modul Python (folder apps/core/)
    verbose_name = 'Core'  # Nama yang ditampilkan di Django admin

    def ready(self):
        try:
            from apps.core.cache_invalidation import register_data_cache_invalidation_signals
            register_data_cache_invalidation_signals()
        except Exception:
            pass

        try:
            from django.db.models.signals import post_delete, post_save
            from apps.core.models import RolePermission
            from apps.core.cache_utils import invalidate_role_permissions_cache

            def invalidate_role_permission_cache(sender, instance, **kwargs):
                invalidate_role_permissions_cache(instance.role)

            post_save.connect(
                invalidate_role_permission_cache,
                sender=RolePermission,
                dispatch_uid='core_role_permission_cache_save',
                weak=False,
            )
            post_delete.connect(
                invalidate_role_permission_cache,
                sender=RolePermission,
                dispatch_uid='core_role_permission_cache_delete',
                weak=False,
            )
        except Exception:
            pass
