"""
Telegram Service - Layanan pengiriman pesan via Telegram Bot API.
Menggunakan urllib bawaan Python (tanpa library eksternal).
"""
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import logging
import threading

logger = logging.getLogger(__name__)


def kirim_pesan_telegram(bot_token, chat_id, pesan, parse_mode='Markdown'):
    if not bot_token or not chat_id:
        return False, "Bot Token atau Chat ID belum dikonfigurasi"
    bot_token = bot_token.strip()
    chat_id = str(chat_id).strip()
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    ssl_context = ssl.create_default_context()

    for attempt_parse_mode in [parse_mode, None]:
        data = {'chat_id': chat_id, 'text': pesan}
        if attempt_parse_mode:
            data['parse_mode'] = attempt_parse_mode
        try:
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    return True, result
                else:
                    error_desc = result.get('description', 'Unknown error')
                    if attempt_parse_mode and 'parse' in error_desc.lower():
                        continue
                    return False, error_desc
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('description', str(e))
                if e.code == 401:
                    error_msg = "Bot Token tidak valid."
                elif e.code == 400 and 'parse' in error_msg.lower() and attempt_parse_mode:
                    continue
            except (json.JSONDecodeError, ValueError):
                error_msg = f"HTTP {e.code}: {error_body[:200]}"
            return False, error_msg
        except urllib.error.URLError as e:
            return False, f"Koneksi gagal: {str(e.reason)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    return False, "Gagal mengirim pesan."


def format_angka(angka):
    try:
        return f"{float(angka):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def render_template(template_str, data):
    result = template_str
    for key, value in data.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def kirim_notifikasi_async(jenis_transaksi, nomor_referensi, data_transaksi):
    thread = threading.Thread(
        target=_kirim_notifikasi_sync,
        args=(jenis_transaksi, nomor_referensi, data_transaksi),
        daemon=True
    )
    thread.start()


def _kirim_notifikasi_sync(jenis_transaksi, nomor_referensi, data_transaksi):
    from .models import PengaturanTelegram, TemplatePesan, LogNotifikasi
    try:
        pengaturan = PengaturanTelegram.load()
        if not pengaturan.aktif or not pengaturan.bot_token or not pengaturan.chat_id:
            return
        toggle_map = {
            'aktivasi': pengaturan.notif_aktivasi,
            'kadaluarsa': pengaturan.notif_kadaluarsa,
            'pembelian': pengaturan.notif_pembelian,
            'suspend': pengaturan.notif_suspend,
        }
        if not toggle_map.get(jenis_transaksi, False):
            return
        template = TemplatePesan.get_template(jenis_transaksi)
        if not template.aktif:
            return
        pesan = render_template(template.template_pesan, data_transaksi)
        success, response = kirim_pesan_telegram(pengaturan.bot_token, pengaturan.chat_id, pesan)
        LogNotifikasi.objects.create(
            jenis_transaksi=jenis_transaksi,
            nomor_referensi=nomor_referensi,
            pesan=pesan,
            status='sukses' if success else 'gagal',
            respons=json.dumps(response) if isinstance(response, dict) else None,
            error_message=response if not success and isinstance(response, str) else None,
        )
    except Exception as e:
        logger.error(f"Error kirim notifikasi Telegram: {str(e)}")
        try:
            from .models import LogNotifikasi
            LogNotifikasi.objects.create(
                jenis_transaksi=jenis_transaksi,
                nomor_referensi=nomor_referensi,
                pesan=f"[Error] {str(e)}",
                status='gagal',
                error_message=str(e),
            )
        except Exception as e:
            logger.warning("Gagal mencatat activity log: %s", e)
