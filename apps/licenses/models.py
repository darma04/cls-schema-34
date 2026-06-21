"""
==========================================================================
 LICENSES MODELS — Model Data Lisensi Central License Server
==========================================================================
 Model utama untuk manajemen lisensi software SIMKOS & SERPTECH.
 Mencakup: Product, Client, LicenseKey, DeviceBinding, LicenseLog.
==========================================================================
"""
import uuid
import random
import string
from datetime import timedelta
from django.db import models
from django.utils import timezone


class Product(models.Model):
    """Produk software yang dilisensikan (SIMKOS, SERPTECH, dll)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nama Produk")
    code = models.CharField(max_length=20, unique=True, verbose_name="Kode Produk", help_text="Contoh: ERP, SIMKOS")
    description = models.TextField(blank=True, null=True, verbose_name="Deskripsi")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = "Produk"
        verbose_name_plural = "Produk"


class Client(models.Model):
    """Data klien/perusahaan yang membeli lisensi."""
    name = models.CharField(max_length=150, verbose_name="Nama Klien / Perusahaan")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nomor Telepon")
    address = models.TextField(blank=True, null=True, verbose_name="Alamat")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Klien"
        verbose_name_plural = "Klien"


class LicenseKey(models.Model):
    """
    Kunci lisensi yang diterbitkan untuk klien.
    Setiap kunci terikat ke 1 produk dan 1 klien.
    Field max_devices mengontrol berapa perangkat yang boleh terikat.
    """
    STATUS_CHOICES = (
        ('active', 'Aktif'),
        ('suspended', 'Ditangguhkan / Diblokir'),
        ('expired', 'Kadaluarsa'),
    )

    key = models.CharField(
        max_length=50, unique=True, verbose_name="Kunci Lisensi",
        help_text="Otomatis digenerate atau masukkan manual"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='licenses', verbose_name="Produk"
    )
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='licenses', verbose_name="Klien"
    )

    registered_domain = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Domain Terdaftar",
        help_text="Domain tempat lisensi ini diaktifkan (contoh: pt-abadi.erpserver.com)"
    )

    duration_days = models.PositiveIntegerField(
        default=365, verbose_name="Durasi (Hari)",
        help_text="Berapa lama lisensi ini berlaku sejak diaktifkan"
    )
    max_devices = models.PositiveIntegerField(
        default=1, verbose_name="Maks Perangkat",
        help_text="Jumlah maksimal perangkat yang boleh terikat pada lisensi ini"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status Lisensi")

    is_activated = models.BooleanField(default=False, verbose_name="Sudah Diaktifkan?")
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Aktivasi")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Kadaluarsa")

    # === Maintenance & Force Update Control ===
    is_maintenance = models.BooleanField(
        default=False, verbose_name="Mode Maintenance",
        help_text="Aktifkan untuk mengunci akses klien ini ke halaman maintenance."
    )
    maintenance_message = models.TextField(
        blank=True, null=True, verbose_name="Pesan Maintenance",
        help_text="Pesan yang akan ditampilkan di klien. Kosongkan untuk pesan default."
    )
    min_app_version = models.CharField(
        max_length=20, default="v1.0", verbose_name="Minimal Versi Aplikasi",
        help_text="Versi minimal aplikasi klien agar bisa beroperasi. Contoh: v2.0"
    )
    force_update_url = models.URLField(
        blank=True, null=True, verbose_name="URL Update",
        help_text="URL tombol update jika versi klien lebih kecil dari Minimal Versi. Bisa link WhatsApp."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.key:
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.key = f"{self.product.code}-{timezone.now().year}-{random_str[:4]}-{random_str[4:]}"

        # Hitung tanggal kadaluarsa jika baru diaktifkan
        if self.is_activated and self.activated_at and not self.expires_at:
            self.expires_at = self.activated_at + timedelta(days=self.duration_days)

        super().save(*args, **kwargs)

    def is_valid(self, domain=None):
        """Cek apakah lisensi ini valid."""
        if self.status != 'active':
            return False, f"Lisensi ini berstatus: {self.get_status_display()}"

        if not self.is_activated:
            return False, "Lisensi belum diaktifkan."

        if self.expires_at and timezone.now() > self.expires_at:
            return False, "Lisensi telah kadaluarsa. Silahkan perpanjang biaya maintenance."
        if domain and self.registered_domain and self.registered_domain != domain:
            return False, f"Lisensi ini terdaftar untuk domain lain ({self.registered_domain})."

        return True, "Lisensi valid."

    @property
    def active_device_count(self):
        """Jumlah perangkat aktif yang terikat pada lisensi ini."""
        return self.device_bindings.filter(is_active=True).count()

    @property
    def can_bind_new_device(self):
        """Apakah masih bisa mengikat perangkat baru."""
        return self.active_device_count < self.max_devices

    def __str__(self):
        return f"{self.key} - {self.client.name}"

    class Meta:
        verbose_name = "Kunci Lisensi"
        verbose_name_plural = "Kunci Lisensi"


class DeviceBinding(models.Model):
    """
    Perekaman sidik jari perangkat (Device Binding).
    Mencatat Hardware ID, IP, dan Domain perangkat klien
    yang terikat pada suatu lisensi.
    """
    license = models.ForeignKey(
        LicenseKey, on_delete=models.CASCADE, related_name='device_bindings',
        verbose_name="Kunci Lisensi"
    )
    hardware_id = models.CharField(
        max_length=255, verbose_name="Hardware ID",
        help_text="ID unik perangkat (MAC Address hash, Android ID, dll)"
    )
    device_name = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Nama Perangkat",
        help_text="Contoh: Samsung Galaxy A52, VPS-Server-01"
    )
    ip_address = models.GenericIPAddressField(
        blank=True, null=True, verbose_name="IP Address"
    )
    domain = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Domain/URL"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    first_seen = models.DateTimeField(auto_now_add=True, verbose_name="Pertama Terlihat")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="Terakhir Terlihat")

    def __str__(self):
        return f"{self.hardware_id[:16]}... → {self.license.key}"

    class Meta:
        verbose_name = "Perangkat Terikat"
        verbose_name_plural = "Perangkat Terikat"
        unique_together = ('license', 'hardware_id')
        ordering = ['-last_seen']


class LicenseLog(models.Model):
    """
    Audit trail untuk semua aktivitas terkait lisensi.
    Mencatat siapa melakukan apa, kapan, dan dari IP mana.
    """
    ACTION_CHOICES = (
        ('activate', 'Aktivasi'),
        ('validate', 'Validasi'),
        ('deactivate', 'Deaktivasi'),
        ('suspend', 'Suspend'),
        ('renew', 'Perpanjangan'),
        ('bind_device', 'Bind Perangkat'),
        ('unbind_device', 'Unbind Perangkat'),
        ('expired', 'Kadaluarsa'),
    )

    license = models.ForeignKey(
        LicenseKey, on_delete=models.CASCADE, related_name='logs',
        verbose_name="Kunci Lisensi"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name="Aksi")
    detail = models.TextField(blank=True, null=True, verbose_name="Detail")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP Address")
    hardware_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Hardware ID")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Waktu")

    def __str__(self):
        return f"[{self.get_action_display()}] {self.license.key} @ {self.timestamp}"

    class Meta:
        verbose_name = "Log Lisensi"
        verbose_name_plural = "Log Lisensi"
        ordering = ['-timestamp']
