"""
==========================================================================
 TELEGRAM BOT CLS - AI Chatbot Handler + Auto Polling
==========================================================================
 File ini menangani pesan masuk dari Telegram via polling otomatis.
 Bot berjalan otomatis saat Django startup tanpa perintah tambahan.
 User bisa langsung mengetik pertanyaan bebas dan bot akan menjawab
 dengan data real-time dari seluruh modul Central License Server.

 Fitur:
 1. Auto-polling — bot otomatis aktif saat server berjalan
 2. Free-text AI chat — ketik apapun, dijawab AI dengan data CLS
 3. Command shortcut — /start, /bantuan, /lisensi, /produk, /klien, dll
 4. Akses data penuh — lisensi, produk, klien, pendapatan, pembelian
 5. System prompt kustom dari Pengaturan Telegram

 Keamanan:
 - Rate limiting per chat (max 10 pesan/menit)
 - Thread pool dengan batas max 5 worker (mencegah thread leak)
 - Response di-truncate agar tidak melebihi batas Telegram (4096 chars)
 - Bot token TIDAK pernah dicetak penuh di log
 - Semua error di-handle tanpa crash
==========================================================================
"""

import json
import logging
import time
import ssl
import urllib.request
import urllib.error
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Flag global untuk mencegah polling ganda
_polling_active = False
_polling_lock = threading.Lock()

# Thread pool untuk memproses pesan — MENCEGAH thread leak
_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="tg_bot")

# Rate limiting — max 10 pesan per menit per chat
_rate_limits = defaultdict(list)
_rate_lock = threading.Lock()
_rate_last_cleanup = time.time()
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_CLEANUP_INTERVAL = 300

# Batas karakter Telegram
TELEGRAM_MAX_LENGTH = 4096


# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT DEFAULT — Personality dan perilaku AI Bot CLS
# ═══════════════════════════════════════════════════════════════
TELEGRAM_SYSTEM_PROMPT = """Kamu adalah CLS AI Assistant, asisten manajemen lisensi software cerdas yang terintegrasi langsung dengan sistem Central License Server.

IDENTITAS:
- Nama: CLS AI Assistant
- Peran: Asisten manajemen lisensi software profesional yang membantu administrator memantau dan menganalisa data lisensi secara real-time
- Platform: Telegram Bot

PERILAKU:
- Selalu gunakan Bahasa Indonesia yang sopan, profesional, dan mudah dipahami
- Sapa pengguna dengan ramah
- Berikan jawaban yang ringkas, padat, dan informatif
- Gunakan emoji secara proporsional untuk memperjelas poin penting
- Gunakan format list/bullet points untuk data yang terstruktur
- JANGAN gunakan tabel markdown karena ini adalah Telegram chat
- Jika data tidak tersedia atau kosong, jelaskan dengan baik dan berikan saran alternatif
- Selalu berikan insight/analisa singkat di akhir jawaban jika memungkinkan
- Format angka uang selalu dalam Rupiah (Rp) dengan pemisah titik, contoh: Rp 1.500.000
- Jika pengguna menyapa (halo, hi, dll), balas dengan ramah DAN berikan ringkasan singkat status lisensi hari ini
- Batasi jawaban maksimal 250 kata agar ringkas di layar Telegram/mobile

KEMAMPUAN:
- Mengakses data lisensi (aktif, kadaluarsa, suspended, segera expired)
- Mengakses data produk software
- Mengakses data klien/pelanggan
- Mengakses data pembelian dan pendapatan
- Mengakses data aktivasi lisensi
- Memberikan analisa manajemen lisensi & rekomendasi
- Memberikan ringkasan eksekutif dan laporan singkat
- Melakukan perbandingan periode (harian, mingguan, bulanan)

BATASAN:
- Hanya menjawab pertanyaan seputar manajemen lisensi dan data CLS
- Tidak melakukan perubahan data (hanya baca/analisa)
- Jika pertanyaan di luar konteks lisensi, arahkan kembali dengan sopan
- Jika diminta hal yang tidak bisa dilakukan, jelaskan dengan jujur"""


def _mask_token(token):
    if not token or len(token) < 10:
        return '***'
    return token[:8] + '...'


def _check_rate_limit(chat_id):
    global _rate_last_cleanup
    now = time.time()
    key = str(chat_id)

    with _rate_lock:
        if now - _rate_last_cleanup > RATE_LIMIT_CLEANUP_INTERVAL:
            expired_keys = [
                k for k, timestamps in _rate_limits.items()
                if not timestamps or (now - max(timestamps)) > RATE_LIMIT_WINDOW
            ]
            for k in expired_keys:
                del _rate_limits[k]
            _rate_last_cleanup = now

        _rate_limits[key] = [
            t for t in _rate_limits[key]
            if now - t < RATE_LIMIT_WINDOW
        ]
        if len(_rate_limits[key]) >= RATE_LIMIT_MAX:
            return False
        _rate_limits[key].append(now)
        return True


def _truncate_response(text):
    if not text or len(text) <= TELEGRAM_MAX_LENGTH:
        return text
    truncated = text[:TELEGRAM_MAX_LENGTH - 30]
    last_newline = truncated.rfind('\n')
    if last_newline > TELEGRAM_MAX_LENGTH - 200:
        truncated = truncated[:last_newline]
    return truncated + "\n\n_(pesan terpotong)_"


# ═══════════════════════════════════════════════════════════════
# AUTO POLLING
# ═══════════════════════════════════════════════════════════════

def start_polling():
    global _polling_active
    with _polling_lock:
        if _polling_active:
            return
        _polling_active = True

    thread = threading.Thread(target=_polling_loop, daemon=True)
    thread.start()
    print("[TelegramBot-CLS] Auto-polling dimulai di background thread")
    logger.info("[TelegramBot-CLS] Auto-polling dimulai di background thread")


def _polling_loop():
    global _polling_active
    time.sleep(3)

    try:
        from .models import PengaturanTelegram
        pengaturan = PengaturanTelegram.load()

        if not pengaturan.bot_token:
            logger.warning("[TelegramBot-CLS] Bot Token belum dikonfigurasi, polling tidak dimulai")
            print("[TelegramBot-CLS] Bot Token belum dikonfigurasi")
            _polling_active = False
            return

        bot_token = pengaturan.bot_token.strip()
        ssl_ctx = ssl.create_default_context()

        _delete_webhook(bot_token, ssl_ctx)
        offset = _get_latest_offset(bot_token, ssl_ctx)

        print(f"[TelegramBot-CLS] Polling aktif - Token: {_mask_token(bot_token)}")
        logger.info(f"[TelegramBot-CLS] Polling aktif - Token: {_mask_token(bot_token)}")

        conflict_count = 0
        conflict_logged = False
        consecutive_errors = 0

        while _polling_active:
            try:
                url = (
                    f"https://api.telegram.org/bot{bot_token}/getUpdates"
                    f"?offset={offset}&timeout=30&limit=10"
                )
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=35, context=ssl_ctx)
                data = json.loads(resp.read().decode('utf-8'))

                conflict_count = 0
                conflict_logged = False
                consecutive_errors = 0

                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        update_id = update.get('update_id', 0)
                        offset = update_id + 1
                        try:
                            _executor.submit(handle_update, update)
                        except RuntimeError:
                            _polling_active = False
                            return

            except urllib.error.HTTPError as e:
                error_body = ''
                try:
                    error_body = e.read().decode('utf-8', errors='replace')
                except Exception as e:
                    logger.warning("Error tidak terduga: %s", e)

                if e.code == 409 or 'conflict' in error_body.lower():
                    conflict_count += 1
                    wait = min(conflict_count * 10, 35)
                    if not conflict_logged:
                        print(f"[TelegramBot-CLS] Ada sesi polling lain yang aktif, menunggu...")
                        conflict_logged = True
                    time.sleep(wait)
                    continue
                else:
                    consecutive_errors += 1
                    logger.warning(f"[TelegramBot-CLS] HTTP error {e.code}: {error_body[:200]}")
                    time.sleep(min(consecutive_errors * 5, 30))

            except urllib.error.URLError as e:
                reason_str = str(e.reason).lower() if e.reason else ''
                if 'timed out' in reason_str or isinstance(e.reason, TimeoutError):
                    continue
                consecutive_errors += 1
                logger.warning(f"[TelegramBot-CLS] Koneksi error: {e.reason}")
                time.sleep(min(consecutive_errors * 5, 60))

            except (TimeoutError, ConnectionError) as e:
                if 'timed out' in str(e).lower():
                    continue
                consecutive_errors += 1
                time.sleep(min(consecutive_errors * 5, 60))

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[TelegramBot-CLS] Polling error: {e}")
                time.sleep(min(consecutive_errors * 5, 60))

            time.sleep(1)

    except Exception as e:
        logger.error(f"[TelegramBot-CLS] Fatal polling error: {e}", exc_info=True)
    finally:
        _polling_active = False


def _delete_webhook(bot_token, ssl_ctx):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
        req = urllib.request.Request(url, method='POST')
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('ok'):
            logger.info("[TelegramBot-CLS] Webhook dihapus (beralih ke polling)")
    except Exception as e:
        logger.warning(f"[TelegramBot-CLS] Gagal hapus webhook: {e}")


def _get_latest_offset(bot_token, ssl_ctx):
    for attempt in range(5):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset=-1&limit=1&timeout=1"
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=5, context=ssl_ctx)
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('ok') and data.get('result'):
                latest_id = data['result'][-1].get('update_id', 0)
                print(f"[TelegramBot-CLS] Skip pesan lama, mulai dari offset {latest_id + 1}")
                return latest_id + 1
            return 0
        except urllib.error.HTTPError as e:
            if e.code == 409:
                time.sleep((attempt + 1) * 10)
                continue
            return 0
        except Exception:
            return 0
    return 0


# ═══════════════════════════════════════════════════════════════
# HANDLER UTAMA
# ═══════════════════════════════════════════════════════════════

def handle_update(update_data):
    try:
        from django.db import close_old_connections
        close_old_connections()

        message = update_data.get('message', {})
        if not message:
            return

        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        user_name = message.get('from', {}).get('first_name', 'User')

        if not chat_id or not text:
            return

        if not _check_rate_limit(chat_id):
            logger.warning(f"[TelegramBot-CLS] Rate limit exceeded: [{chat_id}]")
            _send_reply(chat_id, "Terlalu banyak pesan. Mohon tunggu sebentar.")
            return

        logger.info(f"[TelegramBot-CLS] [{chat_id}] {user_name}: {text[:100]}")

        if text.startswith('/'):
            response_text = _handle_command(text, user_name)
        else:
            response_text = _handle_free_text(text, user_name)

        if response_text:
            response_text = _truncate_response(response_text)
            _send_reply(chat_id, response_text)

    except Exception as e:
        logger.error(f"[TelegramBot-CLS] Error handle update: {e}", exc_info=True)


def _send_reply(chat_id, text):
    try:
        from .telegram_service import kirim_pesan_telegram
        from .models import PengaturanTelegram
        pengaturan = PengaturanTelegram.load()

        if pengaturan.bot_token:
            success, _ = kirim_pesan_telegram(
                pengaturan.bot_token,
                str(chat_id),
                text
            )
            if success:
                logger.info(f"[TelegramBot-CLS] Balasan terkirim ke [{chat_id}]")
            else:
                logger.error(f"[TelegramBot-CLS] Gagal kirim ke [{chat_id}]")
    except Exception as e:
        logger.error(f"[TelegramBot-CLS] Error kirim reply: {e}")


# ═══════════════════════════════════════════════════════════════
# COMMAND HANDLER
# ═══════════════════════════════════════════════════════════════

def _handle_command(text, user_name):
    command = text.split()[0].lower().split('@')[0]

    if command == '/start':
        return (
            f"Halo {user_name}!\n\n"
            "Saya adalah *CLS AI Assistant*\n"
            "Saya bisa membantu Anda memantau dan menganalisa data lisensi "
            "langsung dari Telegram.\n\n"
            "*Langsung ketik pertanyaan Anda!*\n"
            "Saya bisa menjawab apapun tentang data lisensi Anda.\n\n"
            "Contoh:\n"
            "  • _Berapa lisensi aktif saat ini?_\n"
            "  • _Lisensi mana yang segera kadaluarsa?_\n"
            "  • _Siapa klien dengan lisensi terbanyak?_\n"
            "  • _Berapa pendapatan bulan ini?_\n"
            "  • _Ringkasan status lisensi_\n\n"
            "*Command cepat:*\n"
            "/lisensi — Status lisensi\n"
            "/produk — Data produk software\n"
            "/klien — Data klien\n"
            "/pendapatan — Pendapatan & penjualan\n"
            "/laporan — Laporan lengkap AI\n"
            "/bantuan — Menu bantuan"
        )

    elif command in ('/bantuan', '/help'):
        return (
            "*BANTUAN CLS AI BOT*\n"
            "\n\n"
            "*Ketik pertanyaan bebas:*\n"
            "Saya terhubung ke seluruh data Central License Server.\n"
            "Tanya apapun dan saya akan menjawab!\n\n"
            "Contoh:\n"
            "  • _Berapa total lisensi aktif?_\n"
            "  • _Produk apa yang paling laku?_\n"
            "  • _Klien mana yang lisensinya mau expired?_\n"
            "  • _Berapa pendapatan bulan ini?_\n"
            "  • _Ringkasan operasional_\n\n"
            "*Command cepat:*\n"
            "/lisensi /produk /klien\n"
            "/pendapatan /laporan"
        )

    elif command == '/lisensi':
        return _handle_free_text("Tampilkan data lisensi secara detail: total, aktif, kadaluarsa, suspended, dan yang segera expired", user_name)

    elif command == '/produk':
        return _handle_free_text("Tampilkan data semua produk software beserta jumlah lisensinya", user_name)

    elif command == '/klien':
        return _handle_free_text("Tampilkan data klien dan jumlah lisensi masing-masing klien", user_name)

    elif command == '/pendapatan':
        return _handle_free_text("Berikan ringkasan pendapatan: total keseluruhan, bulan ini, dan jumlah transaksi", user_name)

    elif command == '/laporan':
        return _handle_free_text(
            "Berikan laporan ringkasan operasional Central License Server hari ini meliputi "
            "status lisensi, data produk, data klien, pendapatan, dan pembelian secara lengkap",
            user_name
        )

    else:
        clean_text = text.lstrip('/')
        return _handle_free_text(clean_text, user_name)


# ═══════════════════════════════════════════════════════════════
# FREE-TEXT AI HANDLER
# ═══════════════════════════════════════════════════════════════

def _gather_comprehensive_data():
    """
    Kumpulkan data dari SELURUH modul CLS untuk memberikan konteks
    yang luas ke AI.
    """
    from django.utils import timezone
    from django.db.models import Sum, Count, Q
    today = timezone.now().date()
    sections = []

    # ── LISENSI ────────────────────────────
    try:
        from apps.licenses.models import LicenseKey
        from .telegram_service import format_angka

        total = LicenseKey.objects.count()
        aktif = LicenseKey.objects.filter(status='active').count()
        kadaluarsa = LicenseKey.objects.filter(status='expired').count()
        suspended = LicenseKey.objects.filter(status='suspended').count()
        teraktivasi = LicenseKey.objects.filter(is_activated=True).count()
        segera = LicenseKey.objects.filter(
            status='active',
            expires_at__lte=timezone.now() + timedelta(days=30),
            expires_at__gte=timezone.now()
        ).count()

        detail_segera = ""
        lisensi_segera = LicenseKey.objects.filter(
            status='active',
            expires_at__lte=timezone.now() + timedelta(days=30),
            expires_at__gte=timezone.now()
        ).select_related('product', 'client')[:5]
        for ls in lisensi_segera:
            product_name = ls.product.name if ls.product else '-'
            client_name = ls.client.name if ls.client else '-'
            exp_date = ls.expires_at.strftime('%d/%m/%Y') if ls.expires_at else '-'
            detail_segera += f"\n  - {product_name} ({client_name}) — Expired: {exp_date}"

        sections.append(f"""LISENSI:
- Total: {total}
- Aktif: {aktif}
- Kadaluarsa: {kadaluarsa}
- Ditangguhkan: {suspended}
- Teraktivasi: {teraktivasi}
- Segera Kadaluarsa (30 hari): {segera}
- Detail segera expired:{detail_segera if detail_segera else ' (tidak ada)'}""")
    except Exception as e:
        sections.append(f"LISENSI: Data tidak tersedia ({str(e)[:50]})")

    # ── PRODUK SOFTWARE ────────────────────────
    try:
        from apps.licenses.models import Product
        products = Product.objects.annotate(
            total_lisensi=Count('licenses'),
            lisensi_aktif=Count('licenses', filter=Q(licenses__status='active'))
        ).order_by('name')
        product_list = [
            f"  - {p.name} ({p.code}): {p.total_lisensi} lisensi ({p.lisensi_aktif} aktif)"
            for p in products[:10]
        ]
        sections.append(f"""PRODUK SOFTWARE:
- Total Produk: {products.count()}
- Detail:
{chr(10).join(product_list) if product_list else '  (belum ada produk)'}""")
    except Exception:
        sections.append("PRODUK: Data tidak tersedia")

    # ── KLIEN ────────────────────────────
    try:
        from apps.licenses.models import Client
        total_klien = Client.objects.count()
        top_klien = Client.objects.annotate(
            total_lisensi=Count('licenses')
        ).order_by('-total_lisensi')[:10]
        klien_list = [
            f"  - {k.name}: {k.total_lisensi} lisensi"
            for k in top_klien
        ]
        sections.append(f"""KLIEN:
- Total Klien: {total_klien}
- Top 10 Klien (berdasarkan lisensi):
{chr(10).join(klien_list) if klien_list else '  (belum ada klien)'}""")
    except Exception:
        sections.append("KLIEN: Data tidak tersedia")

    # ── PENDAPATAN & PEMBELIAN ────────────────────────
    try:
        from apps.pembelian.models import PembelianLisensi
        from .telegram_service import format_angka

        total_pendapatan = float(
            PembelianLisensi.objects.filter(status='completed').aggregate(
                t=Sum('total_harga')
            )['t'] or 0
        )
        bulan_ini = today.replace(day=1)
        pendapatan_bulan = float(
            PembelianLisensi.objects.filter(
                status='completed', tanggal__gte=bulan_ini
            ).aggregate(t=Sum('total_harga'))['t'] or 0
        )
        trx_selesai = PembelianLisensi.objects.filter(status='completed').count()
        trx_bulan = PembelianLisensi.objects.filter(
            status='completed', tanggal__gte=bulan_ini
        ).count()

        sections.append(f"""PENDAPATAN & PEMBELIAN:
- Total Pendapatan: Rp {format_angka(total_pendapatan)}
- Pendapatan Bulan Ini: Rp {format_angka(pendapatan_bulan)}
- Total Transaksi Selesai: {trx_selesai}
- Transaksi Bulan Ini: {trx_bulan}""")
    except Exception:
        sections.append("PENDAPATAN: Data tidak tersedia")

    return "\n\n".join(sections)


def _handle_free_text(text, user_name):
    """
    Proses pertanyaan bebas menggunakan AI dengan akses data CLS penuh.
    """
    try:
        from django.db import close_old_connections
        close_old_connections()

        from apps.ai_assistant.models import AIAssistantConfig
        from apps.ai_assistant.intents import detect_intent, gather_data
        from .models import PengaturanTelegram

        config = AIAssistantConfig.load()
        tg_config = PengaturanTelegram.load()

        if not config.api_key:
            return (
                "AI Assistant belum dikonfigurasi.\n"
                "Silakan atur API Key di halaman Pengaturan AI Assistant."
            )

        # Deteksi intent
        intent = detect_intent(text)

        # Kumpulkan data
        if intent in ('umum', 'bantuan'):
            ringkasan = _gather_comprehensive_data()
        else:
            data_specific = gather_data(intent, text)
            if isinstance(data_specific, dict):
                ringkasan_spesifik = data_specific.get('ringkasan', '')
            else:
                ringkasan_spesifik = str(data_specific)

            ringkasan_lengkap = _gather_comprehensive_data()
            ringkasan = f"{ringkasan_spesifik}\n\n--- Data Pendukung ---\n{ringkasan_lengkap}"

        # Build system prompt
        system_prompt = TELEGRAM_SYSTEM_PROMPT
        if tg_config.system_prompt_bot:
            system_prompt += f"\n\nINSTRUKSI KUSTOM TELEGRAM:\n{tg_config.system_prompt_bot}"
        if config.system_prompt:
            system_prompt += f"\n\nINSTRUKSI TAMBAHAN:\n{config.system_prompt}"

        user_prompt = f"Data Sistem CLS (real-time):\n{ringkasan}\n\nPesan dari {user_name}: {text}"

        # Panggil AI menggunakan signature CLS: _call_ai_provider(config, system_prompt, user_message)
        from apps.ai_assistant.views import _call_ai_provider
        ai_response = _call_ai_provider(config, system_prompt, user_prompt)

        if ai_response:
            return f"*AI Assistant:*\n\n{ai_response}"
        else:
            return "Maaf, AI tidak bisa memproses pertanyaan Anda saat ini. Coba lagi nanti."

    except Exception as e:
        logger.error(f"[TelegramBot-CLS] Error AI response: {e}", exc_info=True)
        return "Terjadi kesalahan saat memproses. Silakan coba lagi."
