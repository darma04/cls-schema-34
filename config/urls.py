"""
==========================================================================
 CONFIG URLS - Routing URL Master SIMKOS (Sistem Manajemen Kost)
==========================================================================
 /                   -> Dashboard
 /properti/          -> Properti, Tipe Kamar, Kamar
 /penyewa/           -> Data Penyewa
 /sewa/              -> Kontrak Sewa, Tagihan, Pembayaran
 /biaya/             -> Transaksi Biaya
 /laporan/           -> Laporan Keuangan Kost
 /users/             -> User Management
 /access/            -> Permission & Role Management
 /activity-log/      -> Activity Log
 /pengaturan/        -> Pengaturan Sistem
 /automation/        -> Notifikasi Telegram
==========================================================================
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from apps.core.cache_views import refresh_cache_view
from web_project.views import custom_error_404, custom_error_403, custom_error_400, custom_error_500


@login_required
def global_search_api(request):
    """API pencarian global — mencari di semua model utama SIMKOS."""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    try:


        # 6. User
        from django.contrib.auth.models import User
        for u in User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query))[:3]:
            results.append({
                'title': u.get_full_name() or u.username,
                'subtitle': f'@{u.username}',
                'icon': 'ri-user-line',
                'category': 'User',
                'url': '/users/',
            })

    except Exception:
        pass

    return JsonResponse({'results': results[:20]})


urlpatterns = [
    # Admin Interface Django
    path('admin/', admin.site.urls),

    # Test Error Routes
    path("test-error/404/", lambda request: custom_error_404(request, Exception("Test 404"))),
    path("test-error/403/", lambda request: custom_error_403(request, Exception("Test 403"))),
    path("test-error/400/", lambda request: custom_error_400(request, Exception("Test 400"))),
    path("test-error/500/", lambda request: custom_error_500(request)),

    # Global Search API
    path("api/search/", global_search_api, name='global_search'),
    path("core/cache/refresh/", refresh_cache_view, name='core_refresh_cache'),

    # License Management REST API endpoints (FASE 1)
    path("api/v1/license/", include("apps.licenses.api.urls", namespace='api_licenses')),

    # License Legacy API endpoints
    path("api/v1/", include("apps.licenses.urls")),

    # Auth URLs
    path("", include("auth.urls")),

    # SIMKOS Module URLs
    path("", include("apps.dashboard.urls")),
    path("users/", include("apps.user_management.urls")),

    # License UI (Custom Materialize views)
    path("licenses/", include("apps.licenses.ui_urls")),

    # Access Control / Permission Management
    path("access/", include("apps.permission_management.urls")),

    # Modul Terintegrasi SIMKOS
    path("activity-log/", include("apps.activity_log.urls")),
    path("automation/", include("apps.automation.urls")),
    path("pengaturan/", include("apps.pengaturan.urls")),
    path("laporan/", include("apps.laporan.urls")),
    path("ai/", include("apps.ai_assistant.urls")),
    path("pembelian/", include("apps.pembelian.urls")),

    # Original URLs
    path("", include("apps.pages.urls")),
]

# Media files — dilayani di semua environment (development & production)
# WhiteNoise hanya menangani static files, bukan media files.
# Agar foto/upload berfungsi di production, Django harus tetap melayani media.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error Handlers
handler404 = custom_error_404
handler403 = custom_error_403
handler400 = custom_error_400
handler500 = custom_error_500
