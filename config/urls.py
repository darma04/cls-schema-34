"""
==========================================================================
 CONFIG URLS - Routing URL Master CLS (Central License Server)
==========================================================================
 /                   -> Dashboard
 /licenses/          -> Manajemen Lisensi
 /users/             -> User Management
 /access/            -> Permission & Role Management
 /activity-log/      -> Activity Log
 /pengaturan/        -> Pengaturan Sistem
 /automation/        -> Notifikasi Telegram
 /pembelian/         -> Pembelian Lisensi
 /laporan/           -> Laporan
==========================================================================
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.generic.base import RedirectView
from apps.core.cache_views import refresh_cache_view
from web_project.views import custom_error_404, custom_error_403, custom_error_400, custom_error_500


@never_cache
@login_required
def global_search_api(request):
    """API pencarian global — mencari di semua model utama CLS."""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    try:
        # 1. Product
        from apps.licenses.models import Product
        for p in Product.objects.filter(Q(name__icontains=query) | Q(code__icontains=query))[:3]:
            results.append({
                'title': p.name,
                'subtitle': f'Kode: {p.code}',
                'icon': 'ri-box-3-line',
                'category': 'Produk',
                'url': '/licenses/products/',
            })

        # 2. Client
        from apps.licenses.models import Client
        for c in Client.objects.filter(Q(name__icontains=query) | Q(email__icontains=query))[:3]:
            results.append({
                'title': c.name,
                'subtitle': c.email or 'Klien',
                'icon': 'ri-building-line',
                'category': 'Klien',
                'url': '/licenses/clients/',
            })

        # 3. LicenseKey
        from apps.licenses.models import LicenseKey
        for lk in LicenseKey.objects.filter(
            Q(key__icontains=query) | Q(registered_domain__icontains=query)
        ).select_related('product', 'client')[:3]:
            results.append({
                'title': f'{lk.key[:20]}...',
                'subtitle': f'{lk.product.name} \u2014 {lk.client.name}',
                'icon': 'ri-key-2-line',
                'category': 'Lisensi',
                'url': f'/licenses/keys/{lk.pk}/',
            })

        # 4. User
        from django.contrib.auth.models import User
        for u in User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query))[:3]:
            results.append({
                'title': u.get_full_name() or u.username,
                'subtitle': f'@{u.username}',
                'icon': 'ri-user-line',
                'category': 'User',
                'url': f'/users/detail/{u.pk}/',
            })

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"Global search error: {e}")

    return JsonResponse({'results': results[:20]})


urlpatterns = [
    # Admin Interface Django
    path('admin/', admin.site.urls),

    # Global Search API
    path("api/search/", global_search_api, name='global_search'),
    path("core/cache/refresh/", refresh_cache_view, name='core_refresh_cache'),

    # License Management REST API endpoints (FASE 1)
    path("api/v1/license/", include("apps.licenses.api.urls", namespace='api_licenses')),

    # License Legacy API endpoints
    path("api/v1/", include("apps.licenses.urls")),

    # Auth URLs
    path("", include("auth.urls")),

    # CLS Module URLs
    path("", include("apps.dashboard.urls")),
    path("users/", include("apps.user_management.urls")),

    # License UI (Custom Materialize views)
    path("licenses/", include("apps.licenses.ui_urls")),

    # Access Control / Permission Management
    path("access/", include("apps.permission_management.urls")),

    # Modul Terintegrasi CLS
    path("activity-log/", include("apps.activity_log.urls")),
    path("automation/", include("apps.automation.urls")),
    path("pengaturan/", include("apps.pengaturan.urls")),
    path("laporan/", include("apps.laporan.urls")),
    path("ai/", include("apps.ai_assistant.urls")),
    path("pembelian/", include("apps.pembelian.urls")),

    # Original URLs
    path("", include("apps.pages.urls")),
    path("", RedirectView.as_view(url='/', permanent=True), name='landing-page'),
]

# Test Error Routes — only available in DEBUG mode
if settings.DEBUG:
    urlpatterns += [
        path("test-error/404/", lambda request: custom_error_404(request, Exception("Test 404"))),
        path("test-error/403/", lambda request: custom_error_403(request, Exception("Test 403"))),
        path("test-error/400/", lambda request: custom_error_400(request, Exception("Test 400"))),
        path("test-error/500/", lambda request: custom_error_500(request)),
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
