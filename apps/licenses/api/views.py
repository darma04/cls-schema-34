import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from .serializers import LicenseVerificationSerializer
from apps.licenses.models import LicenseKey, DeviceBinding
from apps.licenses.services import (
    log_action, resolve_and_lock_license, check_and_update_expired,
    first_activation, find_active_binding,
    update_binding_info, bind_new_device, build_license_info,
)

logger = logging.getLogger(__name__)


class VerifyLicenseAPIView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = LicenseVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": "invalid",
                "message": "Data tidak lengkap atau format tidak sesuai.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        key_str = data.get('license_key')
        domain = data.get('domain')
        ip_addr = data.get('ip_address') or request.META.get('REMOTE_ADDR')
        hw_id = data.get('hardware_id')
        dev_name = data.get('device_name')

        try:
            with transaction.atomic():
                try:
                    license_obj = resolve_and_lock_license(key_str)
                except LicenseKey.DoesNotExist:
                    log_action(None, "validate", "Mencoba mengakses kunci lisensi yang tidak ada", ip_addr, hw_id)
                    return Response({"status": "invalid", "message": "Kunci lisensi tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)

                is_valid, reason = license_obj.is_valid(domain=domain)
                if not is_valid:
                    log_action(license_obj, "validate", f"Gagal validasi: {reason}", ip_addr, hw_id)
                    return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)

                device_binding = DeviceBinding.objects.filter(license=license_obj, hardware_id=hw_id).first()
                action_type = "validate"

                if device_binding:
                    if not device_binding.is_active:
                        reason = "Akses pada perangkat / server ini telah diblokir secara manual."
                        log_action(license_obj, "validate", f"Gagal validasi: {reason}", ip_addr, hw_id)
                        return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)
                    update_binding_info(device_binding, ip=ip_addr, domain=domain, device_name=dev_name)
                else:
                    if not license_obj.can_bind_new_device:
                        reason = f"Kuota maksimum perangkat tercapai ({license_obj.max_devices} perangkat)."
                        log_action(license_obj, "validate", f"Gagal validasi: {reason}", ip_addr, hw_id)
                        return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)
                    bind_new_device(license_obj, hw_id, device_name=dev_name, ip=ip_addr, domain=domain)
                    action_type = "bind_device"

                first_activation(license_obj, domain=domain, ip=ip_addr, hardware_id=hw_id)

                log_action(license_obj, action_type, f"Akses diberikan dari domain: {domain}", ip_addr, hw_id)

                info = build_license_info(license_obj)
                info.update({
                    "registered_domain": license_obj.registered_domain,
                    "is_maintenance": license_obj.is_maintenance,
                    "maintenance_message": license_obj.maintenance_message or "Sistem sedang dalam perbaikan rutin. Silakan kembali lagi nanti.",
                })
                return Response({"status": "valid", **info}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"License API Verification Exception: {e}")
            return Response({"status": "error", "message": "Kesalahan server internal"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
