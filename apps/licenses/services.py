import json
import logging
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from .models import LicenseKey, DeviceBinding, LicenseLog

logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def parse_json_body(request):
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse(
            {"status": "error", "message": "Format JSON tidak valid."},
            status=400
        )


def log_action(license_obj, action, detail, ip, hardware_id=None):
    if license_obj is None:
        logger.warning(f"Unmapped License Action: {action} {detail} / IP: {ip}")
        return
    LicenseLog.objects.create(
        license=license_obj,
        action=action,
        detail=detail,
        ip_address=ip,
        hardware_id=hardware_id or ''
    )


def resolve_and_lock_license(key):
    return LicenseKey.objects.select_related(
        'product', 'client'
    ).select_for_update().get(key=key)


def check_and_update_expired(license_obj):
    if license_obj.status == 'active' and license_obj.expires_at and timezone.now() > license_obj.expires_at:
        license_obj.status = 'expired'
        license_obj.save(update_fields=['status'])
        return True
    return False


def first_activation(license_obj, domain=None, ip=None, hardware_id=None):
    if license_obj.is_activated:
        return False
    license_obj.is_activated = True
    license_obj.activated_at = timezone.now()
    if domain and not license_obj.registered_domain:
        license_obj.registered_domain = domain
    license_obj.save()
    log_action(license_obj, 'activate', f"Aktivasi pertama dari {ip}", ip, hardware_id)
    return True


def find_active_binding(license_obj, hardware_id):
    return DeviceBinding.objects.filter(
        license=license_obj, hardware_id=hardware_id, is_active=True
    ).first()


def update_binding_info(binding, ip=None, domain=None, device_name=None):
    binding.last_seen = timezone.now()
    if ip:
        binding.ip_address = ip
    if domain:
        binding.domain = domain
    if device_name:
        binding.device_name = device_name
    binding.save(update_fields=['last_seen', 'ip_address', 'domain', 'device_name'])


def bind_new_device(license_obj, hardware_id, device_name=None, ip=None, domain=None):
    return DeviceBinding.objects.create(
        license=license_obj,
        hardware_id=hardware_id,
        device_name=device_name or None,
        ip_address=ip,
        domain=domain or None,
        is_active=True
    )


def build_license_info(license_obj):
    return {
        "license_key": license_obj.key,
        "product_code": license_obj.product.code,
        "product_name": license_obj.product.name,
        "client_name": license_obj.client.name,
        "expires_at": license_obj.expires_at.isoformat() if license_obj.expires_at else None,
        "devices_used": license_obj.active_device_count,
        "devices_max": license_obj.max_devices,
        "is_maintenance": license_obj.is_maintenance,
        "maintenance_message": license_obj.maintenance_message,
        "min_app_version": license_obj.min_app_version,
        "force_update_url": license_obj.force_update_url,
    }


def build_license_info_with_devices(license_obj):
    data = build_license_info(license_obj)
    data.update({
        "is_activated": license_obj.is_activated,
        "activated_at": license_obj.activated_at.isoformat() if license_obj.activated_at else None,
        "registered_domain": license_obj.registered_domain,
        "license_status": license_obj.status,
        "duration_days": license_obj.duration_days,
    })
    devices = list(
        license_obj.device_bindings.filter(is_active=True).values(
            'hardware_id', 'device_name', 'ip_address', 'domain', 'first_seen', 'last_seen'
        )
    )
    for d in devices:
        d['first_seen'] = d['first_seen'].isoformat() if d['first_seen'] else None
        d['last_seen'] = d['last_seen'].isoformat() if d['last_seen'] else None
    data["active_devices"] = devices
    return data
