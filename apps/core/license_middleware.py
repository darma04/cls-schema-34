import json
import uuid
import urllib.request
import urllib.error
import logging
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

LICENSE_KEY_CACHE_KEY = 'saas_license_status_cache'
LICENSE_CHECK_INTERVAL_SECONDS = 60 * 60 * 24  # 24 jam caching

class SaaSLicenseMiddleware:
    """
    Middleware Sentinel: Mencegat request sebelum masuk ke View.
    Akan mengecek apakah instalasi ini memiliki lisensi SAAS yang valid.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def get_hardware_id(self):
        """Merangkum identitas mesin (MAC Address & UUID)."""
        mac = uuid.getnode()
        return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))

    def __call__(self, request):
        # 0. BYPASS TOTAL: Jika aplikasi ini ADALAH Central License Server,
        #    jangan pernah cek lisensi ke diri sendiri (mencegah loopback timeout).
        is_license_server = getattr(settings, 'IS_LICENSE_SERVER', False)
        if is_license_server:
            return self.get_response(request)
        
        path = request.path_info
        
        # 1. Pengecualian Rute: Jangan block static, media, atau endpoint API lisensi itu sendiri (mencegah loopback di server yang sama)
        if path.startswith('/static/') or path.startswith('/media/') or path.startswith('/api/v1/license/'):
            return self.get_response(request)
            
        # 2. Cek Cache
        cached_status = cache.get(LICENSE_KEY_CACHE_KEY)
        if cached_status == 'valid':
            return self.get_response(request)
            
        # 3. Hubungi Central License Server
        license_key = getattr(settings, 'SAAS_LICENSE_KEY', None)
        if not license_key:
            return self._forbidden_page("SAAS_LICENSE_KEY belum dikonfigurasi. Hubungi administrator.") 
        cls_url = getattr(settings, 'CLS_API_URL', 'http://127.0.0.1:8000/api/v1/license/verify/')
        
        domain = request.get_host()
        ip_address = self._get_client_ip(request)
        hardware_id = self.get_hardware_id()
        device_name = "Server Produksi (CLS)"
        
        payload = {
            "license_key": license_key,
            "domain": domain,
            "ip_address": ip_address,
            "hardware_id": hardware_id,
            "device_name": device_name
        }
        
        try:
            req = urllib.request.Request(
                cls_url, 
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('status') == 'valid':
                    cache.set(LICENSE_KEY_CACHE_KEY, 'valid', LICENSE_CHECK_INTERVAL_SECONDS)
                    return self.get_response(request)
                else:
                    return self._forbidden_page(result.get('message', 'Lisensi ditolak przez server pusat.'))
                    
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode('utf-8'))
                msg = error_body.get('message', 'Validasi Lisensi Gagal.')
            except Exception:
                msg = str(e)
            return self._forbidden_page(f"Akses Dilarang: {msg}")
            
        except Exception as e:
            logger.error(f"SaaS Web Verification Error: {e}")
            return self._forbidden_page(f"Koneksi ke Central License Server gagal / Timeout.")

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
        
    def _forbidden_page(self, reason):
        html = f"""
        <html>
        <head>
            <title>Lisensi Kedaluwarsa - Hubungi Administrator</title>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; background:#f4f7fa; margin:0; }}
                .box {{ background:#fff; padding:40px; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.1); max-width:550px; text-align:center; border-top: 5px solid #d32f2f; }}
                h2 {{ color: #d32f2f; margin-top:0; font-size: 24px; }}
                p {{ color: #555; line-height:1.6; font-size: 15px; margin-bottom: 25px; }}
                .reason-box {{ background: #ffeeee; padding: 15px; border-radius: 8px; color: #b71c1c; font-weight: 500; font-size: 14px; margin-bottom: 25px; }}
                .icon {{ font-size: 48px; margin-bottom: 15px; display: block; }}
            </style>
        </head>
        <body>
            <div class="box">
                <span class="icon">🔒</span>
                <h2>Sistem Telah Diblokir</h2>
                <p>Silakan hubungi administrator langganan perangkat lunak Anda untuk mendaftarkan atau memperbarui lisensi <b>(SaaS)</b>.</p>
                <div class="reason-box">Detail Penolakan: {reason}</div>
            </div>
        </body>
        </html>
        """
        return HttpResponseForbidden(html)
