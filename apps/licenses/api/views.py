import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .serializers import LicenseVerificationSerializer
from apps.licenses.models import LicenseKey, DeviceBinding, LicenseLog

logger = logging.getLogger(__name__)

class VerifyLicenseAPIView(APIView):
    """
    Endpoint API untuk memeriksa validitas lisensi dari aplikasi SaaS (Klien).
    Method: POST
    Payload: license_key, domain, ip_address, hardware_id, device_name
    """
    
    # Optional: Tambahkan authentication/throttling class jika diperlukan. Di sini dibuat publik agar middleware bisa mengecek bebas.
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
        ip_addr = data.get('ip_address')
        hw_id = data.get('hardware_id')
        dev_name = data.get('device_name')

        try:
            with transaction.atomic():
                # 1. Cek eksistensi Kunci
                try:
                    license_obj = LicenseKey.objects.select_for_update().get(key=key_str)
                except LicenseKey.DoesNotExist:
                    self._log_action(None, "validate", "Mencoba mengakses kunci lisensi yang tidak ada", dev_name, ip_addr, hw_id)
                    return Response({"status": "invalid", "message": "Kunci lisensi tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)
                
                # 2. Cek validitas global lisensi berdasarkan domain (jika terikat domain)
                is_valid, reason = license_obj.is_valid(domain=domain)
                if not is_valid:
                    self._log_action(license_obj, "validate", f"Gagal validasi: {reason}", dev_name, ip_addr, hw_id)
                    return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)
                
                # 3. Pengecekan Device Binding (Perekaman Sidik Jari)
                device_binding = DeviceBinding.objects.filter(license=license_obj, hardware_id=hw_id).first()
                action_type = "validate"
                
                if device_binding:
                    # Perangkat sudah terdaftar
                    if not device_binding.is_active:
                        reason = "Akses pada perangkat / server ini telah diblokir secara manual."
                        self._log_action(license_obj, "validate", f"Gagal validasi: {reason}", dev_name, ip_addr, hw_id)
                        return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)
                    
                    # Update info terakhir 
                    device_binding.last_seen = timezone.now()
                    if ip_addr: device_binding.ip_address = ip_addr
                    if domain: device_binding.domain = domain
                    if dev_name: device_binding.device_name = dev_name
                    device_binding.save(update_fields=['last_seen', 'ip_address', 'domain', 'device_name'])
                
                else:
                    # Perangkat benar-benar baru, coba register jika slot cukup
                    if not license_obj.can_bind_new_device:
                        reason = f"Kuota maksimum perangkat tercapai ({license_obj.max_devices} perangkat). Silakan nonaktifkan sesi perangkat lama via Portal CLS untuk membebaskan kuota."
                        self._log_action(license_obj, "validate", f"Gagal validasi: {reason}", dev_name, ip_addr, hw_id)
                        return Response({"status": "invalid", "message": reason}, status=status.HTTP_403_FORBIDDEN)
                    
                    # Create the binding
                    DeviceBinding.objects.create(
                        license=license_obj,
                        hardware_id=hw_id,
                        device_name=dev_name,
                        ip_address=ip_addr,
                        domain=domain,
                        is_active=True
                    )
                    action_type = "bind_device"
                    
                # 4. Jika lisensi belum pernah distart, jalankan waktu durasinya!
                if not license_obj.is_activated:
                    license_obj.is_activated = True
                    license_obj.activated_at = timezone.now()
                    # Domain pendaftar pertama jadi domain master
                    if domain and not license_obj.registered_domain:
                        license_obj.registered_domain = domain
                    license_obj.save() # ini mentrigger set expires_at melalui override save() model
                    action_type = "activate"
                else: 
                     # Record domain master automatically if the slot is unused and passed validation
                    if domain and not license_obj.registered_domain:
                        license_obj.registered_domain = domain
                        license_obj.save(update_fields=['registered_domain'])
                
                # 5. Semua lolos
                self._log_action(license_obj, action_type, f"Akses diberikan dari domain: {domain}", dev_name, ip_addr, hw_id)
                
                return Response({
                    "status": "valid",
                    "product": license_obj.product.code,
                    "expires_at": license_obj.expires_at,
                    "registered_domain": license_obj.registered_domain,
                    "is_maintenance": license_obj.is_maintenance,
                    "maintenance_message": license_obj.maintenance_message or "Sistem sedang dalam perbaikan rutin. Silakan kembali lagi nanti.",
                    "min_app_version": license_obj.min_app_version,
                    "force_update_url": license_obj.force_update_url
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"License API Verification Exception: {e}")
            return Response({"status": "error", "message": "Kesalahan server internal"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _log_action(self, license_obj, action, detail, dev_name, ip_addr, hw_id):
        # Prevent logging validation spams from the exact same device if within seconds (optional but helpful)
        detail_msg = f"{detail} (Device: {dev_name})" if dev_name else detail
        
        # Always log critical stuff
        if license_obj:
            LicenseLog.objects.create(
                license=license_obj,
                action=action,
                detail=detail_msg,
                ip_address=ip_addr,
                hardware_id=hw_id
            )
        else:
            logger.warning(f"Unmapped License Attack: {detail_msg} / IP: {ip_addr}")
