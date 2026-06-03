"""
==========================================================================
 CONTEXT PROCESSORS - Penyuntik Data Global ke Semua Template
==========================================================================
 File ini berisi context processors — fungsi-fungsi yang menyuntikkan
 data ke SEMUA template Django secara otomatis.

 Apa itu Context Processor?
 - Fungsi yang menerima parameter 'request' dan mengembalikan dictionary
 - Dictionary tersebut otomatis tersedia di SEMUA template HTML
 - Didaftarkan di settings.py → TEMPLATES → OPTIONS → context_processors

 Cara kerja:
 1. User request halaman → Django proses view
 2. SEBELUM template di-render, Django memanggil SEMUA context processors
 3. Data dari setiap processor digabungkan ke template context
 4. Template bisa mengakses data tersebut langsung (contoh: {{ pengaturan.nama_perusahaan }})

 Koneksi:
 - config/settings.py → Tempat context processors didaftarkan
 - apps/pengaturan/models.py → PengaturanPerusahaan & TemplateCetak
 - apps/core/context_processors.py → Context processor untuk RBAC permissions
 - Semua template HTML → Menggunakan variabel yang disuntikkan
==========================================================================
"""

from django.conf import settings  # Modul untuk mengakses pengaturan Django


def my_setting(request):
    """
    Menyuntikkan seluruh object settings Django ke template.

    Penggunaan di template:
    - {{ MY_SETTING.DEBUG }} → True/False
    - {{ MY_SETTING.STATIC_URL }} → '/static/'

    Kenapa dibutuhkan:
    - Template tidak bisa langsung mengakses settings.py
    - Dengan ini, semua pengaturan bisa diakses dari template
    """
    return {'MY_SETTING': settings}


def language_code(request):
    """
    Menyuntikkan kode bahasa aktif ke template.

    Penggunaan di template:
    - {{ LANGUAGE_CODE }} → 'id' atau 'en'

    Kenapa dibutuhkan:
    - Untuk mengatur tampilan berdasarkan bahasa (contoh: format tanggal)
    - Untuk menandai tag <html lang="{{ LANGUAGE_CODE }}">
    """
    return {"LANGUAGE_CODE": request.LANGUAGE_CODE}


def get_cookie(request):
    """
    Menyuntikkan semua cookie request ke template.

    Penggunaan di template:
    - {{ COOKIES.django_language }} → 'id'
    - {{ COOKIES.django_text_direction }} → 'ltr' atau 'rtl'

    Kenapa dibutuhkan:
    - Untuk mengecek preferensi user yang tersimpan di cookie
    - Contoh: dark mode, bahasa, arah teks
    """
    return {"COOKIES": request.COOKIES}


def environment(request):
    """
    Menyuntikkan variabel ENVIRONMENT ke template.

    Penggunaan di template:
    - {% if ENVIRONMENT == 'development' %}...{% endif %}

    Kenapa dibutuhkan:
    - Untuk menampilkan badge/label environment (dev/staging/production)
    - Untuk mengaktifkan/menonaktifkan fitur berdasarkan environment
    """
    return {'ENVIRONMENT': settings.ENVIRONMENT}


def export_templates(request):
    """
    Menyediakan data template cetak Export Excel dan PDF ke semua halaman.

    Penggunaan di template:
    - {{ export_pdf_template.header_nama_perusahaan }} → 'Central License Server'
    - {{ export_excel_template.footer_copyright }} → '© 2026 Central License Server'

    Cara kerja:
    1. Memanggil TemplateCetak.get_template() yang menerapkan pola get_or_create
    2. Jika template belum ada di database, otomatis dibuat dengan nilai default
    3. Jika sudah ada, ambil data yang tersimpan

    OPTIMASI: Cache selama 60 detik agar tidak query DB setiap request.
    """
    from django.core.cache import cache
    from apps.core.cache_utils import build_scoped_cache_key
    cache_key = build_scoped_cache_key('context_processor', 'export_templates', request=request)
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        from apps.pengaturan.models import TemplateCetak
        export_pdf = TemplateCetak.get_template('export_pdf')
        export_excel = TemplateCetak.get_template('export_excel')
    except Exception:
        export_pdf = None
        export_excel = None

    result = {
        'export_pdf_template': export_pdf,
        'export_excel_template': export_excel,
    }
    cache.set(cache_key, result, 60)
    return result


def pengaturan_perusahaan(request):
    """
    Menyediakan data pengaturan perusahaan ke SEMUA template.

    Data yang disuntikkan:
    - pengaturan → Object PengaturanPerusahaan lengkap
    - system_logo_url → URL logo sistem (untuk sidebar)
    - system_favicon_url → URL favicon (untuk tab browser)
    - system_title → Judul sistem (untuk tag <title>)
    - system_description → Deskripsi sistem (untuk meta tag SEO)
    - system_keywords → Keywords sistem (untuk meta tag SEO)

    OPTIMASI: Cache selama 60 detik agar tidak query DB setiap request.

    Koneksi:
    - apps/pengaturan/models.py → Model PengaturanPerusahaan (singleton)
    - templates/layout/ → Template layout yang menggunakan logo, favicon, title
    """
    from django.core.cache import cache

    from apps.core.cache_utils import build_scoped_cache_key
    cache_key = build_scoped_cache_key('context_processor', 'pengaturan_perusahaan', request=request)
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        from apps.pengaturan.models import PengaturanPerusahaan
        pengaturan = PengaturanPerusahaan.load()  # Muat singleton (pk=1)

        # Akses system_logo.url dengan try/except agar aman jika file fisik sudah dihapus
        try:
            system_logo_url = pengaturan.system_logo.url if pengaturan.system_logo else None
        except Exception:
            system_logo_url = None

        # Akses system_favicon.url dengan try/except agar aman jika file fisik sudah dihapus
        try:
            system_favicon_url = pengaturan.system_favicon.url if pengaturan.system_favicon else None
        except Exception:
            system_favicon_url = None

        result = {
            'pengaturan': pengaturan,
            'system_logo_url': system_logo_url,
            'system_favicon_url': system_favicon_url,
            'system_title': pengaturan.system_title or 'CLS',
            'system_description': pengaturan.system_description or '',
            'system_keywords': pengaturan.system_keywords or '',
        }
        cache.set(cache_key, result, 60)  # Cache 60 detik
        return result
    except Exception:
        default = {
            'pengaturan': None,
            'system_logo_url': None,
            'system_favicon_url': None,
            'system_title': 'CLS',
            'system_description': '',
            'system_keywords': '',
        }
        return default
