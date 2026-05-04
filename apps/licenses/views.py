"""
==========================================================================
 LICENSES API VIEWS — Endpoint REST API Lisensi
==========================================================================
 Endpoint untuk komunikasi Machine-to-Machine (M2M):
 - POST /api/v1/license/activate/   → Aktivasi + bind hardware
 - POST /api/v1/license/validate/   → Pengecekan berkala
 - POST /api/v1/license/deactivate/ → Unlink device
 - GET  /api/v1/license/status/<key>/ → Cek status (read-only)
==========================================================================
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from .models import LicenseKey, DeviceBinding, LicenseLog


def _get_client_ip(request):
    """Ambil IP asli klien (mendukung reverse proxy)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _parse_json_body(request):
    """Parse body JSON dari request."""
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse(
            {"status": "error", "message": "Format JSON tidak valid."},
            status=400
        )


def _log_action(license_obj, action, detail, ip, hardware_id=None):
    """Catat aksi ke LicenseLog."""
    LicenseLog.objects.create(
        license=license_obj,
        action=action,
        detail=detail,
        ip_address=ip,
        hardware_id=hardware_id or ''
    )


@csrf_exempt
@require_http_methods(["POST"])
def license_activate(request):
    """
    API Aktivasi Lisensi + Device Binding.
    
    Payload JSON:
    {
        "license_key": "SIMKOS-2026-XXXX-YYYY",
        "hardware_id": "HW-A1B2C3D4E5F6",
        "device_name": "Samsung Galaxy A52",      (opsional)
        "domain": "pt-abadi.simkos.com"            (opsional)
    }
    """
    data, error = _parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    device_name = data.get('device_name', '').strip()
    domain = data.get('domain', '').strip()
    client_ip = _get_client_ip(request)

    # Validasi input wajib
    if not license_key:
        return JsonResponse(
            {"status": "error", "message": "license_key wajib diisi."},
            status=400
        )
    if not hardware_id:
        return JsonResponse(
            {"status": "error", "message": "hardware_id wajib diisi."},
            status=400
        )

    # Cari lisensi dan mulai transaksi atomic
    try:
        with transaction.atomic():
            lic = LicenseKey.objects.select_related('product', 'client').select_for_update().get(key=license_key)

            # Cek status lisensi
            if lic.status != 'active':
                _log_action(lic, 'activate', f"Gagal: status {lic.get_status_display()}", client_ip, hardware_id)
                return JsonResponse(
                    {"status": "error", "message": f"Lisensi berstatus: {lic.get_status_display()}"},
                    status=403
                )

            # Cek apakah expired
            if lic.expires_at and timezone.now() > lic.expires_at:
                lic.status = 'expired'
                lic.save(update_fields=['status'])
                _log_action(lic, 'expired', "Lisensi kadaluarsa saat aktivasi.", client_ip, hardware_id)
                return JsonResponse(
                    {"status": "error", "message": "Lisensi telah kadaluarsa."},
                    status=403
                )

            # Cek apakah device sudah terdaftar pada lisensi ini
            existing_binding = DeviceBinding.objects.filter(
                license=lic, hardware_id=hardware_id
            ).first()

            if existing_binding:
                # Perangkat sudah pernah terdaftar — re-activate jika inactive
                if not existing_binding.is_active:
                    existing_binding.is_active = True
                    existing_binding.save(update_fields=['is_active', 'last_seen'])
                    _log_action(lic, 'bind_device', f"Re-aktivasi device: {hardware_id}", client_ip, hardware_id)

                # Update last_seen dan IP
                existing_binding.ip_address = client_ip
                if domain:
                    existing_binding.domain = domain
                existing_binding.save(update_fields=['ip_address', 'domain', 'last_seen'])

            else:
                # Device baru — cek apakah masih ada slot
                if not lic.can_bind_new_device:
                    _log_action(lic, 'activate', f"Gagal: maks perangkat ({lic.max_devices}) tercapai.", client_ip, hardware_id)
                    return JsonResponse({
                        "status": "error",
                        "message": f"Batas perangkat tercapai ({lic.active_device_count}/{lic.max_devices}). "
                                   f"Silakan deaktivasi perangkat lama terlebih dahulu."
                    }, status=403)

                # Bind device baru
                DeviceBinding.objects.create(
                    license=lic,
                    hardware_id=hardware_id,
                    device_name=device_name or None,
                    ip_address=client_ip,
                    domain=domain or None,
                    is_active=True
                )
                _log_action(lic, 'bind_device', f"Device baru terikat: {hardware_id}", client_ip, hardware_id)

            # Aktivasi pertama kali jika belum
            if not lic.is_activated:
                lic.is_activated = True
                lic.activated_at = timezone.now()
                if domain and not lic.registered_domain:
                    lic.registered_domain = domain
                lic.save()
                _log_action(lic, 'activate', f"Aktivasi pertama dari {client_ip}", client_ip, hardware_id)

    except LicenseKey.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Kunci lisensi tidak ditemukan."},
            status=404
        )

    return JsonResponse({
        "status": "success",
        "message": "Lisensi berhasil diaktifkan.",
        "data": {
            "license_key": lic.key,
            "product_code": lic.product.code,
            "product_name": lic.product.name,
            "client_name": lic.client.name,
            "is_activated": lic.is_activated,
            "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "registered_domain": lic.registered_domain,
            "devices_used": lic.active_device_count,
            "devices_max": lic.max_devices,
            "is_maintenance": lic.is_maintenance,
            "maintenance_message": lic.maintenance_message,
            "min_app_version": lic.min_app_version,
            "force_update_url": lic.force_update_url,
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def license_validate(request):
    """
    API Validasi Berkala (dipanggil setiap 12-24 jam oleh middleware klien).
    
    Payload JSON:
    {
        "license_key": "SIMKOS-2026-XXXX-YYYY",
        "hardware_id": "HW-A1B2C3D4E5F6",
        "domain": "pt-abadi.simkos.com"            (opsional)
    }
    """
    data, error = _parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    domain = data.get('domain', '').strip()
    client_ip = _get_client_ip(request)

    if not license_key or not hardware_id:
        return JsonResponse(
            {"status": "error", "message": "license_key dan hardware_id wajib diisi."},
            status=400
        )

    try:
        with transaction.atomic():
            lic = LicenseKey.objects.select_related('product', 'client').select_for_update().get(key=license_key)

            # Cek expired otomatis
            if lic.status == 'active' and lic.expires_at and timezone.now() > lic.expires_at:
                lic.status = 'expired'
                lic.save(update_fields=['status'])
                _log_action(lic, 'expired', "Kadaluarsa terdeteksi saat validasi.", client_ip, hardware_id)

            # Cek status
            is_valid, message = lic.is_valid(domain=domain)

            if not is_valid:
                _log_action(lic, 'validate', f"Gagal: {message}", client_ip, hardware_id)
                return JsonResponse({
                    "status": "success",
                    "is_valid": False,
                    "message": message,
                })

            # Cek device binding — apakah HWID terdaftar dan aktif?
            binding = DeviceBinding.objects.filter(
                license=lic, hardware_id=hardware_id, is_active=True
            ).first()

            if not binding:
                _log_action(lic, 'validate', f"Gagal: HWID tidak terdaftar ({hardware_id})", client_ip, hardware_id)
                return JsonResponse({
                    "status": "success",
                    "is_valid": False,
                    "message": "Perangkat ini tidak terdaftar pada lisensi ini. "
                               "Silakan aktivasi ulang atau hubungi admin."
                })

            # Update last_seen & IP
            binding.ip_address = client_ip
            if domain:
                binding.domain = domain
            binding.save(update_fields=['ip_address', 'domain', 'last_seen'])

    except LicenseKey.DoesNotExist:
        return JsonResponse(
            {"status": "error", "is_valid": False, "message": "Kunci lisensi tidak ditemukan."},
            status=404
        )

    return JsonResponse({
        "status": "success",
        "is_valid": True,
        "message": "Lisensi valid.",
        "data": {
            "license_key": lic.key,
            "product_code": lic.product.code,
            "client_name": lic.client.name,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "devices_used": lic.active_device_count,
            "devices_max": lic.max_devices,
            "is_maintenance": lic.is_maintenance,
            "maintenance_message": lic.maintenance_message,
            "min_app_version": lic.min_app_version,
            "force_update_url": lic.force_update_url,
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def license_deactivate(request):
    """
    API Deaktivasi / Unlink Device.
    
    Payload JSON:
    {
        "license_key": "SIMKOS-2026-XXXX-YYYY",
        "hardware_id": "HW-A1B2C3D4E5F6"
    }
    """
    data, error = _parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    client_ip = _get_client_ip(request)

    if not license_key or not hardware_id:
        return JsonResponse(
            {"status": "error", "message": "license_key dan hardware_id wajib diisi."},
            status=400
        )

    try:
        with transaction.atomic():
            lic = LicenseKey.objects.get(key=license_key)
            
            # Cari binding yang aktif
            binding = DeviceBinding.objects.filter(
                license=lic, hardware_id=hardware_id, is_active=True
            ).select_for_update().first()

            if not binding:
                return JsonResponse(
                    {"status": "error", "message": "Perangkat tidak ditemukan atau sudah dinonaktifkan."},
                    status=404
                )

            binding.is_active = False
            binding.save(update_fields=['is_active', 'last_seen'])

            _log_action(lic, 'unbind_device', f"Device di-unlink: {hardware_id}", client_ip, hardware_id)

    except LicenseKey.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Kunci lisensi tidak ditemukan."},
            status=404
        )

    return JsonResponse({
        "status": "success",
        "message": "Perangkat berhasil di-unlink dari lisensi.",
        "data": {
            "license_key": lic.key,
            "hardware_id": hardware_id,
            "devices_used": lic.active_device_count,
            "devices_max": lic.max_devices,
        }
    })


@require_http_methods(["GET"])
def license_status(request, key):
    """
    API Status Lisensi (Read-Only, tanpa efek samping).
    
    URL: GET /api/v1/license/status/<key>/
    """
    try:
        lic = LicenseKey.objects.select_related('product', 'client').get(key=key)
    except LicenseKey.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Kunci lisensi tidak ditemukan."},
            status=404
        )

    # Auto-expire check
    if lic.status == 'active' and lic.expires_at and timezone.now() > lic.expires_at:
        lic.status = 'expired'
        lic.save(update_fields=['status'])

    is_valid, message = lic.is_valid()

    # Ambil daftar device yang terikat
    devices = list(
        lic.device_bindings.filter(is_active=True).values(
            'hardware_id', 'device_name', 'ip_address', 'domain', 'first_seen', 'last_seen'
        )
    )
    # Konversi datetime ke string
    for d in devices:
        d['first_seen'] = d['first_seen'].isoformat() if d['first_seen'] else None
        d['last_seen'] = d['last_seen'].isoformat() if d['last_seen'] else None

    return JsonResponse({
        "status": "success",
        "data": {
            "license_key": lic.key,
            "product_code": lic.product.code,
            "product_name": lic.product.name,
            "client_name": lic.client.name,
            "license_status": lic.status,
            "is_valid": is_valid,
            "message": message,
            "is_activated": lic.is_activated,
            "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "registered_domain": lic.registered_domain,
            "duration_days": lic.duration_days,
            "devices_used": lic.active_device_count,
            "devices_max": lic.max_devices,
            "active_devices": devices,
            "is_maintenance": lic.is_maintenance,
            "maintenance_message": lic.maintenance_message,
            "min_app_version": lic.min_app_version,
            "force_update_url": lic.force_update_url,
        }
    })
