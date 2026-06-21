"""
Model Notifikasi Telegram untuk Central License Server.
Notifikasi untuk event lisensi: aktivasi, kadaluarsa, pembelian, suspend.
"""
from django.db import models


class PengaturanTelegram(models.Model):
    """Pengaturan bot Telegram (Singleton Pattern)."""
    bot_token = models.CharField(max_length=200, blank=True, verbose_name="Bot Token",
        help_text="Token dari @BotFather")
    chat_id = models.CharField(max_length=100, blank=True, verbose_name="Chat ID",
        help_text="Chat ID tujuan (grup atau personal)")
    aktif = models.BooleanField(default=False, verbose_name="Aktif")

    # Toggle per jenis event lisensi
    notif_aktivasi = models.BooleanField(default=True, verbose_name="Notifikasi Aktivasi Lisensi")
    notif_kadaluarsa = models.BooleanField(default=True, verbose_name="Notifikasi Kadaluarsa Lisensi")
    notif_pembelian = models.BooleanField(default=True, verbose_name="Notifikasi Pembelian Lisensi")
    notif_suspend = models.BooleanField(default=True, verbose_name="Notifikasi Suspend Lisensi")

    # System Prompt Bot Telegram - instruksi kustom untuk AI chatbot
    system_prompt_bot = models.TextField(
        blank=True,
        default='',
        verbose_name="System Prompt Bot AI",
        help_text="Instruksi tambahan untuk mengatur perilaku AI chatbot Telegram. Kosongkan untuk menggunakan default."
    )

    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diupdate_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pengaturan Telegram"
        verbose_name_plural = "Pengaturan Telegram"

    def __str__(self):
        return f"Pengaturan Telegram ({'Aktif' if self.aktif else 'Nonaktif'})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class TemplatePesan(models.Model):
    """Template pesan notifikasi per jenis event lisensi."""
    JENIS_CHOICES = [
        ('aktivasi', 'Aktivasi Lisensi'),
        ('kadaluarsa', 'Kadaluarsa Lisensi'),
        ('pembelian', 'Pembelian Lisensi'),
        ('suspend', 'Suspend Lisensi'),
    ]

    jenis = models.CharField(max_length=30, choices=JENIS_CHOICES, unique=True, verbose_name="Jenis Event")
    nama = models.CharField(max_length=100, verbose_name="Nama Template")
    template_pesan = models.TextField(verbose_name="Template Pesan",
        help_text="Gunakan variabel {{variabel}} untuk placeholder")
    aktif = models.BooleanField(default=True, verbose_name="Aktif")

    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diupdate_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template Pesan"
        verbose_name_plural = "Template Pesan"
        ordering = ['jenis']

    def __str__(self):
        return f"{self.get_jenis_display()} - {self.nama}"

    @classmethod
    def get_template(cls, jenis):
        obj, created = cls.objects.get_or_create(
            jenis=jenis,
            defaults={
                'nama': f'Template {dict(cls.JENIS_CHOICES).get(jenis, jenis)}',
                'template_pesan': cls._get_default_template(jenis),
                'aktif': True,
            }
        )
        return obj

    @classmethod
    def _get_default_template(cls, jenis):
        templates = {
            'aktivasi': (
                "🔑 *AKTIVASI LISENSI BARU*\n"
                "━━━━━━━━━━━━━━━\n"
                "📋 Kunci: {{license_key}}\n"
                "📦 Produk: {{product_name}}\n"
                "👤 Klien: {{client_name}}\n"
                "🌐 Domain: {{domain}}\n"
                "📅 Aktif Sampai: {{expires_at}}\n"
                "📊 Status: Aktif ✅"
            ),
            'kadaluarsa': (
                "⚠️ *LISENSI KADALUARSA*\n"
                "━━━━━━━━━━━━━━━\n"
                "📋 Kunci: {{license_key}}\n"
                "📦 Produk: {{product_name}}\n"
                "👤 Klien: {{client_name}}\n"
                "📅 Kadaluarsa: {{expires_at}}\n"
                "📊 Status: Kadaluarsa ❌"
            ),
            'pembelian': (
                "💰 *PEMBELIAN LISENSI BARU*\n"
                "━━━━━━━━━━━━━━━\n"
                "📋 No Transaksi: {{nomor_transaksi}}\n"
                "👤 Klien: {{client_name}}\n"
                "📦 Produk: {{product_name}}\n"
                "💵 Total: Rp {{total}}\n"
                "📅 Tanggal: {{tanggal}}"
            ),
            'suspend': (
                "🚫 *LISENSI DI-SUSPEND*\n"
                "━━━━━━━━━━━━━━━\n"
                "📋 Kunci: {{license_key}}\n"
                "📦 Produk: {{product_name}}\n"
                "👤 Klien: {{client_name}}\n"
                "📊 Status: Ditangguhkan 🔒"
            ),
        }
        return templates.get(jenis, "{{license_key}} - {{product_name}}")


class LogNotifikasi(models.Model):
    """Log riwayat pengiriman notifikasi Telegram."""
    STATUS_CHOICES = [
        ('sukses', 'Sukses'),
        ('gagal', 'Gagal'),
    ]
    JENIS_CHOICES = TemplatePesan.JENIS_CHOICES

    jenis_transaksi = models.CharField(max_length=30, choices=JENIS_CHOICES, verbose_name="Jenis Event")
    nomor_referensi = models.CharField(max_length=100, verbose_name="Nomor Referensi")
    pesan = models.TextField(verbose_name="Pesan yang Dikirim")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name="Status")
    respons = models.TextField(blank=True, null=True, verbose_name="Respons API")
    error_message = models.TextField(blank=True, null=True, verbose_name="Pesan Error")
    dikirim_pada = models.DateTimeField(auto_now_add=True, verbose_name="Dikirim Pada")

    class Meta:
        verbose_name = "Log Notifikasi"
        verbose_name_plural = "Log Notifikasi"
        ordering = ['-dikirim_pada']

    def __str__(self):
        return f"[{self.status}] {self.jenis_transaksi} - {self.nomor_referensi}"
