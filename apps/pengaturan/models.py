"""
Model Pengaturan untuk Central License Server.
PengaturanPerusahaan (singleton), TemplateCetak (factory), BackupHistory.
"""
import os
from django.db import models
from django.conf import settings


class PengaturanPerusahaan(models.Model):
    """Pengaturan perusahaan - Singleton pattern."""
    nama_perusahaan = models.CharField(max_length=200, default='CLS', verbose_name="Nama Perusahaan")
    alamat = models.TextField(blank=True, verbose_name="Alamat")
    telepon = models.CharField(max_length=50, blank=True, verbose_name="Telepon")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Website")
    logo = models.ImageField(upload_to='pengaturan/', blank=True, null=True, verbose_name="Logo")
    favicon = models.ImageField(upload_to='pengaturan/', blank=True, null=True, verbose_name="Favicon")
    deskripsi = models.TextField(blank=True, verbose_name="Deskripsi Perusahaan")
    pajak_default = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Default Pajak (%)")

    # System Settings
    system_title = models.CharField(max_length=200, blank=True, default='CLS', verbose_name="Judul Sistem")
    system_keywords = models.CharField(max_length=500, blank=True, verbose_name="Keywords (SEO)")
    system_description = models.TextField(blank=True, verbose_name="Deskripsi Sistem")
    system_logo = models.ImageField(upload_to='pengaturan/', blank=True, null=True, verbose_name="Logo Sistem")
    system_favicon = models.ImageField(upload_to='pengaturan/', blank=True, null=True, verbose_name="Favicon Sistem")

    # SMTP Settings
    email_smtp_host = models.CharField(max_length=200, blank=True, default='smtp.gmail.com', verbose_name="SMTP Host")
    email_smtp_port = models.IntegerField(default=587, verbose_name="SMTP Port")
    email_smtp_user = models.CharField(max_length=200, blank=True, verbose_name="SMTP User")
    email_smtp_password = models.CharField(max_length=200, blank=True, verbose_name="SMTP Password")
    email_use_tls = models.BooleanField(default=True, verbose_name="Gunakan TLS")

    # Email Templates
    email_header = models.TextField(blank=True, verbose_name="Email Header")
    email_footer = models.TextField(blank=True, verbose_name="Email Footer")
    forgot_password_subject = models.CharField(max_length=200, blank=True, default='Reset Password Anda', verbose_name="Subjek Forgot Password")
    forgot_password_message = models.TextField(blank=True, verbose_name="Pesan Forgot Password")
    register_subject = models.CharField(max_length=200, blank=True, default='Verifikasi Email Anda', verbose_name="Subjek Register")
    register_message = models.TextField(blank=True, verbose_name="Pesan Register")

    # Maintenance Mode
    maintenance_mode = models.BooleanField(default=False, verbose_name="Mode Maintenance")
    maintenance_message = models.TextField(blank=True, default='Sistem sedang dalam maintenance.', verbose_name="Pesan Maintenance")

    # Dynamic Branding
    auth_image = models.ImageField(upload_to='pengaturan/auth/', blank=True, null=True, verbose_name="Ilustrasi Login/Register")
    auth_background_image = models.ImageField(upload_to='pengaturan/auth/', blank=True, null=True, verbose_name="Background Login/Register")
    misc_image = models.ImageField(upload_to='pengaturan/misc/', blank=True, null=True, verbose_name="Ilustrasi Error/Maintenance")
    misc_background_image = models.ImageField(upload_to='pengaturan/misc/', blank=True, null=True, verbose_name="Background Error/Maintenance")

    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diupdate_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pengaturan Perusahaan"
        verbose_name_plural = "Pengaturan Perusahaan"

    def __str__(self):
        return self.nama_perusahaan

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class TemplateCetak(models.Model):
    """
    Template cetak dokumen — sama dengan SIMKOS.
    Digunakan untuk header/footer pada export Excel, PDF, dan cetak dokumen.
    Setiap jenis template hanya boleh ada 1 (unique per jenis).
    """
    JENIS_CHOICES = [
        ('lisensi', 'Sertifikat Lisensi'),
        ('invoice', 'Invoice Pembelian'),
        ('laporan', 'Laporan'),
        ('export_excel', 'Template Export Excel'),
        ('export_pdf', 'Template Export PDF'),
    ]

    nama = models.CharField(max_length=100, verbose_name="Nama Template")
    jenis = models.CharField(max_length=30, choices=JENIS_CHOICES, unique=True, verbose_name="Jenis Template")

    # Informasi Header Dokumen
    header_nama_perusahaan = models.CharField(max_length=200, default="CLS", verbose_name="Nama Perusahaan")
    header_alamat = models.TextField(default="Jl. Contoh Alamat No. 123", blank=True, verbose_name="Alamat")
    header_telepon = models.CharField(max_length=50, default="(021) 1234-5678", blank=True, verbose_name="Telepon")
    header_email = models.EmailField(default="info@cls.com", blank=True, verbose_name="Email")
    header_website = models.CharField(max_length=200, blank=True, verbose_name="Website")

    # Informasi Footer Dokumen
    footer_ucapan = models.CharField(max_length=200, default="Terima kasih atas kepercayaan Anda!", blank=True, verbose_name="Ucapan Terima Kasih")
    footer_keterangan = models.CharField(max_length=200, default="Dokumen ini dicetak secara otomatis.", blank=True, verbose_name="Keterangan Footer")
    footer_copyright = models.CharField(max_length=300, default="© 2026 CLS", blank=True, verbose_name="Footer Copyright")

    # Label Tanda Tangan
    signature_kiri_label = models.CharField(max_length=50, default="Disetujui Oleh", blank=True, verbose_name="Label Tanda Tangan Kiri")
    signature_kanan_label = models.CharField(max_length=50, default="Dibuat Oleh", blank=True, verbose_name="Label Tanda Tangan Kanan")

    # Pengaturan Tambahan
    logo = models.ImageField(upload_to='template_cetak/', blank=True, null=True, verbose_name="Logo Perusahaan", help_text="Upload logo perusahaan. Kosongkan untuk menggunakan logo default.")
    tampilkan_logo = models.BooleanField(default=True, verbose_name="Tampilkan Logo")
    tampilkan_website = models.BooleanField(default=False, verbose_name="Tampilkan Website")

    aktif = models.BooleanField(default=True, verbose_name="Aktif")
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diupdate_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template Cetak"
        verbose_name_plural = "Template Cetak"
        ordering = ['jenis']

    def __str__(self):
        return f"{self.nama} ({self.get_jenis_display()})"

    @classmethod
    def get_template(cls, jenis='lisensi'):
        """Mengambil template berdasarkan jenis, buat default jika belum ada."""
        defaults = cls._get_default_values(jenis)
        obj, created = cls.objects.get_or_create(
            jenis=jenis,
            defaults=defaults
        )
        return obj

    @classmethod
    def _get_default_values(cls, jenis):
        """Nilai default untuk setiap jenis template — sama dengan SIMKOS."""
        defaults_map = {
            'lisensi': {
                'nama': 'Template Sertifikat Lisensi',
                'signature_kiri_label': 'Penerbit',
                'signature_kanan_label': 'Penerima',
            },
            'invoice': {
                'nama': 'Template Invoice Pembelian',
                'signature_kiri_label': 'Penjual',
                'signature_kanan_label': 'Pembeli',
            },
            'laporan': {
                'nama': 'Template Laporan',
                'signature_kiri_label': 'Disetujui Oleh',
                'signature_kanan_label': 'Dibuat Oleh',
            },
            'export_excel': {
                'nama': 'Template Export Excel',
                'signature_kiri_label': '-',
                'signature_kanan_label': '-',
                'footer_ucapan': '',
                'footer_keterangan': 'Diekspor dari CLS.',
                'footer_copyright': '© 2026 CLS',
            },
            'export_pdf': {
                'nama': 'Template Export PDF',
                'signature_kiri_label': '-',
                'signature_kanan_label': '-',
                'footer_ucapan': '',
                'footer_keterangan': 'Diekspor dari CLS.',
                'footer_copyright': '© 2026 CLS',
            },
        }

        base_defaults = {
            'header_nama_perusahaan': 'CLS',
            'header_alamat': 'Jl. Contoh Alamat No. 123',
            'header_telepon': '(021) 1234-5678',
            'header_email': 'info@cls.com',
            'footer_ucapan': 'Terima kasih atas kepercayaan Anda!',
            'footer_keterangan': 'Dokumen ini dicetak secara otomatis.',
            'footer_copyright': '© 2026 CLS',
        }

        base_defaults.update(defaults_map.get(jenis, {'nama': f'Template {jenis}'}))
        return base_defaults


class BackupHistory(models.Model):
    """Riwayat backup/restore database."""
    AKSI_CHOICES = [
        ('backup', 'Backup'),
        ('restore', 'Restore'),
        ('reset', 'Reset'),
    ]
    aksi = models.CharField(max_length=10, choices=AKSI_CHOICES, verbose_name="Aksi")
    nama_file = models.CharField(max_length=200, blank=True, verbose_name="Nama File")
    ukuran_file = models.BigIntegerField(default=0, verbose_name="Ukuran File (bytes)")
    catatan = models.TextField(blank=True, verbose_name="Catatan")
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name="User")
    dibuat_pada = models.DateTimeField(auto_now_add=True, verbose_name="Waktu")

    class Meta:
        verbose_name = "Riwayat Backup"
        verbose_name_plural = "Riwayat Backup"
        ordering = ['-dibuat_pada']

    def __str__(self):
        return f"[{self.aksi}] {self.nama_file or 'N/A'} - {self.dibuat_pada}"
