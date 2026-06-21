from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from .models import LicenseKey, DeviceBinding
from .services import (
    get_client_ip, parse_json_body, log_action,
    resolve_and_lock_license, check_and_update_expired,
    first_activation, find_active_binding,
    update_binding_info, bind_new_device, build_license_info,
    build_license_info_with_devices,
)


@csrf_exempt
@require_http_methods(["POST"])
def license_activate(request):
    data, error = parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    device_name = data.get('device_name', '').strip()
    domain = data.get('domain', '').strip()
    client_ip = get_client_ip(request)

    if not license_key:
        return JsonResponse({"status": "error", "message": "license_key wajib diisi."}, status=400)
    if not hardware_id:
        return JsonResponse({"status": "error", "message": "hardware_id wajib diisi."}, status=400)

    try:
        with transaction.atomic():
            lic = resolve_and_lock_license(license_key)

            if lic.status != 'active':
                log_action(lic, 'activate', f"Gagal: status {lic.get_status_display()}", client_ip, hardware_id)
                return JsonResponse({"status": "error", "message": f"Lisensi berstatus: {lic.get_status_display()}"}, status=403)

            check_and_update_expired(lic)
            if lic.status == 'expired':
                log_action(lic, 'expired', "Lisensi kadaluarsa saat aktivasi.", client_ip, hardware_id)
                return JsonResponse({"status": "error", "message": "Lisensi telah kadaluarsa."}, status=403)

            existing_binding = DeviceBinding.objects.filter(
                license=lic, hardware_id=hardware_id
            ).first()

            if existing_binding:
                if not existing_binding.is_active:
                    existing_binding.is_active = True
                    existing_binding.save(update_fields=['is_active', 'last_seen'])
                    log_action(lic, 'bind_device', f"Re-aktivasi device: {hardware_id}", client_ip, hardware_id)
                update_binding_info(existing_binding, ip=client_ip, domain=domain)
            else:
                if not lic.can_bind_new_device:
                    log_action(lic, 'activate', f"Gagal: maks perangkat ({lic.max_devices}) tercapai.", client_ip, hardware_id)
                    return JsonResponse({
                        "status": "error",
                        "message": f"Batas perangkat tercapai ({lic.active_device_count}/{lic.max_devices}). "
                                   f"Silakan deaktivasi perangkat lama terlebih dahulu."
                    }, status=403)
                bind_new_device(lic, hardware_id, device_name=device_name, ip=client_ip, domain=domain)
                log_action(lic, 'bind_device', f"Device baru terikat: {hardware_id}", client_ip, hardware_id)

            first_activation(lic, domain=domain, ip=client_ip, hardware_id=hardware_id)

    except LicenseKey.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Kunci lisensi tidak ditemukan."}, status=404)

    info = build_license_info(lic)
    info.update({
        "is_activated": lic.is_activated,
        "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
        "registered_domain": lic.registered_domain,
    })
    return JsonResponse({"status": "success", "message": "Lisensi berhasil diaktifkan.", "data": info})


@csrf_exempt
@require_http_methods(["POST"])
def license_validate(request):
    data, error = parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    domain = data.get('domain', '').strip()
    client_ip = get_client_ip(request)

    if not license_key or not hardware_id:
        return JsonResponse({"status": "error", "message": "license_key dan hardware_id wajib diisi."}, status=400)

    try:
        with transaction.atomic():
            lic = resolve_and_lock_license(license_key)
            check_and_update_expired(lic)

            is_valid, message = lic.is_valid(domain=domain)
            if not is_valid:
                log_action(lic, 'validate', f"Gagal: {message}", client_ip, hardware_id)
                return JsonResponse({"status": "success", "is_valid": False, "message": message})

            binding = find_active_binding(lic, hardware_id)
            if not binding:
                log_action(lic, 'validate', f"Gagal: HWID tidak terdaftar ({hardware_id})", client_ip, hardware_id)
                return JsonResponse({
                    "status": "success", "is_valid": False,
                    "message": "Perangkat ini tidak terdaftar pada lisensi ini. "
                               "Silakan aktivasi ulang atau hubungi admin."
                })

            update_binding_info(binding, ip=client_ip, domain=domain)

    except LicenseKey.DoesNotExist:
        return JsonResponse({"status": "error", "is_valid": False, "message": "Kunci lisensi tidak ditemukan."}, status=404)

    info = build_license_info(lic)
    return JsonResponse({"status": "success", "is_valid": True, "message": "Lisensi valid.", "data": info})


@csrf_exempt
@require_http_methods(["POST"])
def license_deactivate(request):
    data, error = parse_json_body(request)
    if error:
        return error

    license_key = data.get('license_key', '').strip()
    hardware_id = data.get('hardware_id', '').strip()
    client_ip = get_client_ip(request)

    if not license_key or not hardware_id:
        return JsonResponse({"status": "error", "message": "license_key dan hardware_id wajib diisi."}, status=400)

    try:
        with transaction.atomic():
            lic = resolve_and_lock_license(license_key)
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
            log_action(lic, 'unbind_device', f"Device di-unlink: {hardware_id}", client_ip, hardware_id)

    except LicenseKey.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Kunci lisensi tidak ditemukan."}, status=404)

    return JsonResponse({
        "status": "success",
        "message": "Perangkat berhasil di-unlink dari lisensi.",
        "data": {"license_key": lic.key, "hardware_id": hardware_id, "devices_used": lic.active_device_count, "devices_max": lic.max_devices}
    })


@require_http_methods(["GET"])
def license_status(request, key):
    try:
        lic = LicenseKey.objects.select_related('product', 'client').get(key=key)
    except LicenseKey.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Kunci lisensi tidak ditemukan."}, status=404)

    if lic.status == 'active' and lic.expires_at and timezone.now() > lic.expires_at:
        with transaction.atomic():
            lic = LicenseKey.objects.select_for_update().get(pk=lic.pk)
            check_and_update_expired(lic)

    is_valid, message = lic.is_valid()
    data = build_license_info_with_devices(lic)
    data.update({"is_valid": is_valid, "message": message})
    return JsonResponse({"status": "success", "data": data})
