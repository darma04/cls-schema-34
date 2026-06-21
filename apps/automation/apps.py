"""
==========================================================================
 AUTOMATION APPS - Konfigurasi Aplikasi Automasi (Telegram)
==========================================================================
 Konfigurasi Django app untuk modul automasi Central License Server.
 Method ready() memulai bot Telegram polling otomatis saat server berjalan,
 baik di development (runserver) maupun production (gunicorn).
==========================================================================
"""
import os
import sys
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AutomationConfig(AppConfig):
    """Konfigurasi aplikasi Automation - integrasi Telegram dan notifikasi otomatis."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    verbose_name = 'Automation (Telegram)'

    def ready(self):
        """
        Memulai bot Telegram polling otomatis saat server berjalan.
        Hindari saat: migrate, shell, collectstatic, test, dll.
        """
        argv_str = ' '.join(sys.argv)

        # Daftar command yang TIDAK boleh menjalankan polling
        skip_commands = (
            'migrate', 'makemigrations', 'shell', 'dbshell',
            'collectstatic', 'test', 'check', 'createsuperuser',
            'flush', 'showmigrations', 'inspectdb', 'compilemessages',
            'run_telegram_bot',
        )
        should_skip = any(cmd in argv_str for cmd in skip_commands)

        if should_skip:
            return

        # Untuk runserver: hanya jalankan di proses utama (RUN_MAIN=true)
        is_runserver = 'runserver' in sys.argv
        if is_runserver:
            is_main_process = os.environ.get('RUN_MAIN') == 'true'
            if not is_main_process:
                return

        # Untuk Gunicorn: gunakan file lock agar hanya 1 worker yang polling
        if not is_runserver:
            if not self._acquire_polling_lock():
                return

        try:
            from .telegram_bot import start_polling
            start_polling()
        except Exception as e:
            logger.warning(f"[AutomationConfig] Gagal start polling: {e}")

    def _acquire_polling_lock(self):
        """
        Buat file lock untuk memastikan hanya 1 Gunicorn worker
        yang menjalankan polling.
        """
        import tempfile
        lock_file = os.path.join(tempfile.gettempdir(), 'cls_telegram_polling.lock')

        try:
            if os.path.exists(lock_file):
                try:
                    with open(lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)
                    # Proses masih hidup, lock valid, skip
                    return False
                except (OSError, ValueError):
                    # Proses sudah mati, lock stale, ambil alih
                    pass

            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True

        except Exception:
            return True
