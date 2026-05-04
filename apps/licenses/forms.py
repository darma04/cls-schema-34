"""
==========================================================================
 LICENSES FORMS — Form untuk Client, Product, LicenseKey
==========================================================================
 ModelForm dengan widget Materialize (Bootstrap 5 classes).
 Digunakan oleh views_ui.py untuk CRUD.
==========================================================================
"""
from django import forms
from .models import Client, Product, LicenseKey


class ClientForm(forms.ModelForm):
    """Form untuk menambah/edit data klien."""

    class Meta:
        model = Client
        fields = ['name', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nama klien/perusahaan',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contoh@email.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+62 812-xxxx-xxxx',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Alamat lengkap klien',
            }),
        }


class ProductForm(forms.ModelForm):
    """Form untuk menambah/edit data produk."""

    class Meta:
        model = Product
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: SERPTECH ERP System',
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: ERP, SIMKOS',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Deskripsi singkat produk',
            }),
        }


class LicenseKeyForm(forms.ModelForm):
    """Form untuk membuat kunci lisensi baru."""

    class Meta:
        model = LicenseKey
        fields = [
            'product', 'client', 'duration_days', 'max_devices', 'status', 'registered_domain',
            'is_maintenance', 'maintenance_message', 'min_app_version', 'force_update_url'
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '365', 'min': '1'}),
            'max_devices': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1', 'min': '1'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'registered_domain': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'contoh: pt-abadi.erpserver.com (opsional)'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maintenance_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Opsional: pesan maintenance'}),
            'min_app_version': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: v2.0'}),
            'force_update_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Misal: https://wa.me/...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial/default values agar form tidak kosong saat create baru
        if not self.instance.pk:
            self.fields['duration_days'].initial = 365
            self.fields['max_devices'].initial = 1
            self.fields['status'].initial = 'active'


class LicenseKeyUpdateForm(forms.ModelForm):
    """Form untuk mengupdate lisensi (status, durasi, domain, maks perangkat)."""

    class Meta:
        model = LicenseKey
        fields = [
            'status', 'duration_days', 'max_devices', 'registered_domain',
            'is_maintenance', 'maintenance_message', 'min_app_version', 'force_update_url'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_devices': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'registered_domain': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'contoh: pt-abadi.erpserver.com'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maintenance_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Opsional: pesan maintenance'}),
            'min_app_version': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misal: v2.0'}),
            'force_update_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Misal: https://wa.me/...'}),
        }
