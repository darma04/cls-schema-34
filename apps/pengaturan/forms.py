from django import forms
from .models import PengaturanPerusahaan

class PengaturanPerusahaanForm(forms.ModelForm):
    """
    Form Pengaturan Perusahaan — explicit field list.
    PENTING: Jangan gunakan fields = '__all__' karena model memiliki
    field auto-managed (dibuat_pada, diupdate_pada) yang tidak boleh
    dimasukkan ke form. Jika dimasukkan, form akan gagal validasi
    tanpa pesan error yang jelas.
    """
    class Meta:
        model = PengaturanPerusahaan
        fields = [
            # Identitas Perusahaan
            'nama_perusahaan', 'logo', 'alamat', 'telepon', 'email', 'website', 'pajak_default',
            # Pengaturan Sistem
            'system_title', 'system_description', 'system_keywords', 'system_logo', 'system_favicon',
            'maintenance_mode', 'maintenance_message',
            # Email/SMTP
            'email_smtp_host', 'email_smtp_port', 'email_smtp_user', 'email_smtp_password', 'email_use_tls',
            # Template Email
            'email_header', 'email_footer',
            'forgot_password_subject', 'forgot_password_message',
            'register_subject', 'register_message',
            # Dynamic Branding
            'auth_image', 'auth_background_image', 'misc_image', 'misc_background_image',
        ]
