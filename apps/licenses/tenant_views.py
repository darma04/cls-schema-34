"""
==========================================================================
 TENANT VIEWS — Manajemen Tenant Multi-Software dari CLS
==========================================================================
 Views untuk mengelola tenant pada server SIMS, SIMKOS, dan SERPTECH.
 CLS bertindak sebagai 'remote control' yang mengirim API request
 ke masing-masing server software untuk membuat, melihat, dan menghapus tenant.

 Koneksi:
 - .env → SIMS_SERVER_URL / SIMKOS_SERVER_URL / SERPTECH_SERVER_URL
 - .env → SIMS_INTERNAL_API_KEY / SIMKOS_INTERNAL_API_KEY / SERPTECH_INTERNAL_API_KEY
 - Software API → /api/internal/tenants/ (endpoint penerima di setiap software)

 RBAC:
 - Module: 'tenant_management'
 - Menggunakan decorator permission_required_func dari core.mixins
==========================================================================
"""
import os
import json
import requests
from types import SimpleNamespace
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from web_project import TemplateLayout
from apps.core.mixins import permission_required_func
from apps.activity_log.middleware import ActivityLogMiddleware


def _init_layout(request, context):
    """Wrapper untuk TemplateLayout.init() dari function-based view."""
    fake_self = SimpleNamespace(request=request)
    return TemplateLayout.init(fake_self, context)


# ==========================================================================
#  KONFIGURASI SERVER PER SOFTWARE
# ==========================================================================

# Daftar software yang dikelola CLS
SOFTWARE_SERVERS = {
    'SIMS': {
        'label': 'SIMS',
        'full_name': 'Sistem Informasi Manajemen & Service',
        'color': 'primary',
        'icon': 'ri-store-2-line',
        'url_env': 'SIMS_SERVER_URL',
        'key_env': 'SIMS_INTERNAL_API_KEY',
    },
    'SIMKOS': {
        'label': 'SIMKOS',
        'full_name': 'Sistem Manajemen Kost',
        'color': 'success',
        'icon': 'ri-building-2-line',
        'url_env': 'SIMKOS_SERVER_URL',
        'key_env': 'SIMKOS_INTERNAL_API_KEY',
    },
    'SERPTECH': {
        'label': 'SERPTECH',
        'full_name': 'SERPTECH ERP System',
        'color': 'warning',
        'icon': 'ri-computer-line',
        'url_env': 'SERPTECH_SERVER_URL',
        'key_env': 'SERPTECH_INTERNAL_API_KEY',
    },
}


def _get_server_config(software_code):
    """Ambil URL dan API Key untuk software tertentu."""
    server = SOFTWARE_SERVERS.get(software_code)
    if not server:
        return '', ''
    url = os.environ.get(server['url_env'], '').rstrip('/')
    key = os.environ.get(server['key_env'], '')
    return url, key


def _software_request(software_code, method, path, data=None, timeout=30):
    """
    Kirim HTTP request ke server software tertentu (SIMS/SIMKOS/SERPTECH).
    Returns: (success: bool, response_data: dict, error_message: str)
    """
    base_url, api_key = _get_server_config(software_code)
    if not base_url or not api_key:
        server = SOFTWARE_SERVERS.get(software_code, {})
        url_env = server.get('url_env', '?')
        key_env = server.get('key_env', '?')
        return False, {}, f"{url_env} atau {key_env} belum dikonfigurasi di .env"

    url = f"{base_url}{path}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method == 'POST':
            resp = requests.post(url, headers=headers, json=data, timeout=timeout)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=headers, timeout=timeout)
        else:
            return False, {}, f"Method {method} tidak didukung."

        try:
            resp_data = resp.json()
        except ValueError:
            # Response bukan JSON (kemungkinan HTML login page karena port salah)
            # Jangan tampilkan raw HTML sebagai error message
            content_type = resp.headers.get('Content-Type', '')
            if 'html' in content_type.lower():
                resp_data = {"message": f"Server mengembalikan halaman HTML, bukan JSON API. Periksa konfigurasi URL server (kemungkinan port salah). HTTP {resp.status_code}"}
            else:
                resp_data = {"message": f"Response tidak valid (bukan JSON). HTTP {resp.status_code}"}

        if resp.status_code in (200, 201):
            return True, resp_data, ""
        else:
            msg = resp_data.get('message', f'HTTP {resp.status_code}')
            # Pastikan pesan error tidak terlalu panjang (max 200 karakter)
            if len(msg) > 200:
                msg = msg[:200] + '...'
            return False, resp_data, msg

    except requests.ConnectionError:
        return False, {}, f"Tidak bisa terhubung ke {software_code} Server ({base_url}). Pastikan server berjalan."
    except requests.Timeout:
        return False, {}, f"Request ke {software_code} Server timeout (>30 detik)."
    except Exception as e:
        return False, {}, f"Error: {str(e)}"


# ==========================================================================
#  TENANT LIST — Daftar semua tenant dari SEMUA software
# ==========================================================================

@login_required
@permission_required_func('read', 'tenant_management')
def tenant_list(request):
    """Halaman daftar semua tenant dari ketiga software server."""
    context = _init_layout(request, {})
    context['title'] = 'Tenant Management'

    # Filter software (dari query param)
    filter_software = request.GET.get('software', '').upper()

    all_tenants = []
    server_statuses = {}

    for code, config in SOFTWARE_SERVERS.items():
        # Jika ada filter, skip software yang tidak dipilih
        if filter_software and filter_software != code:
            server_statuses[code] = {
                'label': config['label'],
                'color': config['color'],
                'icon': config['icon'],
                'connected': None,  # Tidak dicek
                'count': 0,
                'error': '',
            }
            continue

        base_url, _ = _get_server_config(code)
        success, data, error = _software_request(code, 'GET', '/api/internal/tenants/')

        if success:
            tenants = data.get('tenants', [])
            # Tambahkan info software ke setiap tenant
            for t in tenants:
                t['software'] = code
                t['software_label'] = config['label']
                t['software_color'] = config['color']
                t['software_icon'] = config['icon']
                t['server_url'] = base_url
            all_tenants.extend(tenants)
            server_statuses[code] = {
                'label': config['label'],
                'color': config['color'],
                'icon': config['icon'],
                'connected': True,
                'count': len(tenants),
                'error': '',
                'url': base_url,
            }
        else:
            server_statuses[code] = {
                'label': config['label'],
                'color': config['color'],
                'icon': config['icon'],
                'connected': False,
                'count': 0,
                'error': error,
                'url': base_url,
            }

    context['tenants'] = all_tenants
    context['total_tenants'] = len(all_tenants)
    context['server_statuses'] = server_statuses
    context['software_servers'] = SOFTWARE_SERVERS
    context['filter_software'] = filter_software

    return render(request, 'licenses/tenant_list.html', context)


# ==========================================================================
#  TENANT DETAIL — Detail 1 tenant
# ==========================================================================

@login_required
@permission_required_func('read', 'tenant_management')
def tenant_detail(request, software_code, schema_name):
    """Halaman detail satu tenant dari software tertentu."""
    context = _init_layout(request, {})
    context['title'] = 'Detail Tenant'

    software_code = software_code.upper()
    if software_code not in SOFTWARE_SERVERS:
        messages.error(request, f'Software "{software_code}" tidak dikenal.')
        return redirect('licenses_ui:tenant_list')

    success, data, error = _software_request(software_code, 'GET', f'/api/internal/tenants/{schema_name}/')

    if success:
        tenant = data.get('data', {})
        tenant['software'] = software_code
        tenant['software_label'] = SOFTWARE_SERVERS[software_code]['label']
        tenant['software_color'] = SOFTWARE_SERVERS[software_code]['color']
        context['tenant'] = tenant
    else:
        context['tenant'] = None
        context['connection_error'] = error

    base_url, _ = _get_server_config(software_code)
    context['server_url'] = base_url
    context['software_code'] = software_code

    return render(request, 'licenses/tenant_detail.html', context)


# ==========================================================================
#  TENANT CREATE — Buat tenant baru
# ==========================================================================

@login_required
@permission_required_func('create', 'tenant_management')
def tenant_create(request):
    """Halaman dan handler untuk membuat tenant baru pada software tertentu."""
    context = _init_layout(request, {})
    context['title'] = 'Buat Tenant Baru'
    context['software_servers'] = SOFTWARE_SERVERS

    if request.method == 'POST':
        software_code = request.POST.get('software', '').strip().upper()
        nama = request.POST.get('nama', '').strip()
        schema_name = request.POST.get('schema_name', '').strip()
        domain = request.POST.get('domain', '').strip()

        form_data = {
            'software': software_code,
            'nama': nama,
            'schema_name': schema_name,
            'domain': domain,
        }

        if not all([software_code, nama, schema_name, domain]):
            messages.error(request, 'Semua field wajib diisi.')
            context['form_data'] = form_data
            return render(request, 'licenses/tenant_form.html', context)

        if software_code not in SOFTWARE_SERVERS:
            messages.error(request, f'Software "{software_code}" tidak dikenal.')
            context['form_data'] = form_data
            return render(request, 'licenses/tenant_form.html', context)

        payload = {
            'nama': nama,
            'schema_name': schema_name,
            'domain': domain,
        }

        success, data, error = _software_request(software_code, 'POST', '/api/internal/tenants/', data=payload)

        if success:
            superuser_info = data.get('data', {}).get('superuser', {})
            tenant_data = data.get('data', {})

            request.session['new_tenant_info'] = {
                'software': software_code,
                'software_label': SOFTWARE_SERVERS[software_code]['label'],
                'software_color': SOFTWARE_SERVERS[software_code]['color'],
                'nama': tenant_data.get('nama', nama),
                'schema_name': tenant_data.get('schema_name', schema_name),
                'domain': tenant_data.get('domain', domain),
                'username': superuser_info.get('username', 'admin'),
                'password': superuser_info.get('password', ''),
                'email': superuser_info.get('email', ''),
            }

            messages.success(request, f'Tenant "{nama}" berhasil dibuat di {SOFTWARE_SERVERS[software_code]["label"]}!')

            # Log aktivitas pembuatan tenant
            ActivityLogMiddleware.log_activity(
                request,
                action='CREATE',
                model_name='Tenant',
                object_repr=f'{nama} ({schema_name})',
                description=f'Membuat tenant baru "{nama}" (schema: {schema_name}, domain: {domain}) di server {SOFTWARE_SERVERS[software_code]["label"]}'
            )

            return redirect('licenses_ui:tenant_list')
        else:
            messages.error(request, f'Gagal membuat tenant di {SOFTWARE_SERVERS[software_code]["label"]}: {error}')
            context['form_data'] = form_data

    return render(request, 'licenses/tenant_form.html', context)


# ==========================================================================
#  TENANT DELETE (AJAX)
# ==========================================================================

@login_required
@permission_required_func('delete', 'tenant_management')
def tenant_delete(request, software_code, schema_name):
    """AJAX endpoint untuk menghapus tenant dari software tertentu."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    software_code = software_code.upper()
    if software_code not in SOFTWARE_SERVERS:
        return JsonResponse({'success': False, 'message': f'Software "{software_code}" tidak dikenal.'}, status=400)

    if schema_name == 'public':
        return JsonResponse({'success': False, 'message': 'Schema public tidak boleh dihapus.'}, status=403)

    success, data, error = _software_request(software_code, 'DELETE', f'/api/internal/tenants/{schema_name}/')

    if success:
        # Log aktivitas penghapusan tenant
        ActivityLogMiddleware.log_activity(
            request,
            action='DELETE',
            model_name='Tenant',
            object_repr=f'{schema_name}',
            description=f'Menghapus tenant "{schema_name}" dari server {SOFTWARE_SERVERS[software_code]["label"]}'
        )
        return JsonResponse({'success': True, 'message': data.get('message', 'Tenant berhasil dihapus.')})
    else:
        return JsonResponse({'success': False, 'message': error}, status=400)


# ==========================================================================
#  CLEAR SESSION (AJAX) — Hapus info tenant baru dari session
# ==========================================================================

@login_required
def tenant_clear_session(request):
    """Hapus info tenant baru dari session setelah ditampilkan."""
    if request.method == 'POST':
        if 'new_tenant_info' in request.session:
            del request.session['new_tenant_info']
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=405)
