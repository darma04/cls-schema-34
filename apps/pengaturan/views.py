"""
Views Pengaturan - Profil, Perusahaan, Template Cetak, Manajemen Data.
"""

import logging
logger = logging.getLogger(__name__)

# ==========================================================================
# PANDUAN DJANGO UNTUK DEVELOPER PEMULA (baca ini sebelum mempelajari views)
# ==========================================================================
#
# APA ITU CLASS-BASED VIEW (CBV)?
# - CBV = class Python yang menangani HTTP request dan return response
# - Django menyediakan CBV bawaan: ListView, CreateView, UpdateView, DeleteView
# - Setiap CBV punya "lifecycle" (siklus hidup) yang bisa di-customize
#
# SIKLUS HIDUP CBV (urutan method yang dipanggil):
# 1. as_view()     → Entry point, dipanggil oleh URL router
# 2. dispatch()    → Tentukan method (GET/POST) → panggil get() atau post()
# 3. get()/post()  → Handle request, kumpulkan data
# 4. get_queryset()→ Ambil data dari database (bisa di-filter/optimasi)
# 5. get_context_data() → Siapkan data untuk template (variabel {{ }})
# 6. render()      → Gabungkan template + context → HTML response
#
# METHOD PENTING YANG SERING DI-OVERRIDE:
# - get_queryset()     → Optimasi query (prefetch_related, select_related)
# - get_context_data() → Tambah variabel ke template (self.context)
# - form_valid()       → Proses setelah form divalidasi (sebelum save)
# - get_success_url()  → URL redirect setelah operasi berhasil
#
# DECORATOR YANG SERING DIGUNAKAN:
# @login_required       → User HARUS login, jika tidak → redirect ke /login/
# @permission_required  → User harus punya permission tertentu (RBAC)
# @require_http_methods → Batasi method yang diterima (GET, POST, dll)
# @never_cache          → Response tidak boleh di-cache oleh browser
#
# POLA UMUM VIEW DI PROYEK INI:
# class MyListView(SubModulePermissionMixin, ListView):
#     module_name = 'nama_modul'          # Untuk pengecekan RBAC
#     sub_module_name = 'nama_sub_modul'  # Sub-modul yang diakses
#     model = MyModel                      # Model database yang dipakai
#     template_name = 'modul/page.html'    # File HTML template
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context = TemplateLayout.init(self, context)  # WAJIB: setup layout
#         context['data_tambahan'] = ...    # Tambah data custom
#         return context
# ==========================================================================

import os
import shutil
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from django.conf import settings
from web_project import TemplateLayout
from .models import PengaturanPerusahaan, TemplateCetak, BackupHistory

from .forms import PengaturanPerusahaanForm
from apps.core.mixins import ReadPermissionMixin, permission_required_func
from apps.core.cache_utils import invalidate_tenant_response_cache




class ProfilView(LoginRequiredMixin, TemplateView):
    template_name = 'pengaturan/profil.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        # Add profile to context so avatar and phone display correctly
        try:
            context['profile'] = self.request.user.profile
        except Exception:
            context['profile'] = None
        return context

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            new_password = request.POST.get('new_password', '')
            if new_password:
                user.set_password(new_password)
            user.save()

            # Update Profile
            try:
                profile = user.profile
                profile.phone = request.POST.get('phone', '')
                if request.POST.get('remove_avatar') == '1':
                    profile.avatar = None
                elif request.FILES.get('avatar'):
                    profile.avatar = request.FILES['avatar']
                profile.save()
            except Exception as e:
                logger.warning("Gagal memproses file: %s", e)

        messages.success(request, 'Profil berhasil diperbarui!')
        return redirect('pengaturan:profil')


class PerusahaanView(LoginRequiredMixin, UpdateView):
    model = PengaturanPerusahaan
    form_class = PengaturanPerusahaanForm
    template_name = 'pengaturan/perusahaan.html'
    success_url = reverse_lazy('pengaturan:perusahaan')

    def get_object(self, queryset=None):
        return PengaturanPerusahaan.load()

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        invalidate_tenant_response_cache(request=self.request)
        messages.success(self.request, 'Pengaturan perusahaan berhasil disimpan!')
        return response

    def form_invalid(self, form):
        # Tampilkan error validasi form ke user agar tidak gagal diam-diam
        for field, errors in form.errors.items():
            for error in errors:
                field_label = form.fields[field].label if field in form.fields else field
                messages.error(self.request, f'{field_label}: {error}')
        return super().form_invalid(form)


class TemplateCetakListView(LoginRequiredMixin, ListView):
    model = TemplateCetak
    template_name = 'pengaturan/template_cetak_list.html'
    context_object_name = 'templates'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        for jenis, _ in TemplateCetak.JENIS_CHOICES:
            TemplateCetak.get_template(jenis)
        context['templates'] = TemplateCetak.objects.all()
        return context


class TemplateCetakCreateView(LoginRequiredMixin, CreateView):
    model = TemplateCetak
    template_name = 'pengaturan/template_cetak_form.html'
    fields = ['jenis', 'nama', 'logo', 'header_nama_perusahaan', 'header_alamat', 'header_telepon', 'header_email', 'header_website', 'footer_ucapan', 'footer_keterangan', 'footer_copyright', 'signature_kiri_label', 'signature_kanan_label', 'tampilkan_logo', 'tampilkan_website', 'aktif']
    success_url = reverse_lazy('pengaturan:template_cetak_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Template cetak berhasil dibuat!')
        return response


class TemplateCetakUpdateView(LoginRequiredMixin, UpdateView):
    model = TemplateCetak
    template_name = 'pengaturan/template_cetak_form.html'
    fields = ['jenis', 'nama', 'logo', 'header_nama_perusahaan', 'header_alamat', 'header_telepon', 'header_email', 'header_website', 'footer_ucapan', 'footer_keterangan', 'footer_copyright', 'signature_kiri_label', 'signature_kanan_label', 'tampilkan_logo', 'tampilkan_website', 'aktif']
    success_url = reverse_lazy('pengaturan:template_cetak_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Template cetak berhasil diperbarui!')
        return response


class ManajemenDataView(LoginRequiredMixin, ReadPermissionMixin, TemplateView):
    permission_module = 'pengaturan'
    permission_sub_module = 'manajemen_data'
    template_name = 'pengaturan/manajemen_data.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        db_path = settings.DATABASES['default']['NAME']
        if os.path.exists(db_path):
            context['db_size'] = os.path.getsize(db_path)
            context['db_size_mb'] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        else:
            context['db_size'] = 0
            context['db_size_mb'] = 0
        from apps.licenses.models import Product, Client, LicenseKey
        from apps.pembelian.models import PembelianLisensi, PembelianLisensiItem
        from apps.automation.models import LogNotifikasi
        from .models import BackupHistory

        total_produk = Product.objects.count()
        total_klien = Client.objects.count()
        total_lisensi = LicenseKey.objects.count()
        total_transaksi = PembelianLisensi.objects.count()
        total_item = PembelianLisensiItem.objects.count()
        total_log_notifikasi = LogNotifikasi.objects.count()

        context['total_produk'] = total_produk
        context['total_klien'] = total_klien
        context['total_lisensi'] = total_lisensi
        context['total_master'] = total_produk + total_klien + total_lisensi
        context['total_transaksi'] = total_transaksi
        context['last_backup'] = BackupHistory.objects.filter(aksi='backup').order_by('-dibuat_pada').first()
        context['riwayat_list'] = BackupHistory.objects.all().order_by('-dibuat_pada')[:20]

        context['stats'] = {
            'produk': total_produk,
            'klien': total_klien,
            'lisensi': total_lisensi,
            'pembelian': total_transaksi,
            'item_pembelian': total_item,
            'log_notifikasi': total_log_notifikasi,
            'activity_log': 0, # Placeholder if activity log is not implemented
            'user': 1 # Placeholder, could count auth User
        }
        return context


@login_required
@permission_required_func('create', 'pengaturan', 'manajemen_data')
def backup_data(request):
    if request.method == 'POST':
        import datetime
        import zipfile
        import tempfile
        db_path = settings.DATABASES['default']['NAME']
        media_root = settings.MEDIA_ROOT
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"cls_backup_{timestamp}.zip"
        try:
            # Buat ZIP berisi database + media
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
            os.close(tmp_fd)
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Masukkan database SQLite
                if os.path.exists(str(db_path)):
                    zf.write(str(db_path), 'database.sqlite3')
                # Masukkan seluruh folder media
                media_root_str = str(media_root)
                if os.path.exists(media_root_str):
                    for root, dirs, files in os.walk(media_root_str):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join('media', os.path.relpath(file_path, media_root_str))
                            zf.write(file_path, arcname)

            file_size = os.path.getsize(tmp_path)
            # Simpan salinan di folder backups
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(tmp_path, backup_path)

            BackupHistory.objects.create(
                aksi='backup', nama_file=backup_filename,
                ukuran_file=file_size, user=request.user,
                catatan=f"Backup database + media oleh {request.user.username}"
            )
            with open(tmp_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{backup_filename}"'
            os.unlink(tmp_path)
            return response
        except Exception as e:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            messages.error(request, f'Gagal membuat backup: {str(e)}')
    return redirect('pengaturan:manajemen_data')



@login_required
@permission_required_func('write', 'pengaturan', 'manajemen_data')
def restore_data(request):
    if request.method == 'POST' and request.FILES.get('backup_file'):
        import datetime
        import zipfile
        import tempfile
        db_path = settings.DATABASES['default']['NAME']
        media_root = str(settings.MEDIA_ROOT)
        backup_file = request.FILES['backup_file']
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_restore = f"pre_restore_{timestamp}.sqlite3"
        filename = backup_file.name.lower()

        try:
            # Backup database sebelum restore
            shutil.copy2(str(db_path), os.path.join(backup_dir, pre_restore))

            if filename.endswith('.zip'):
                # === RESTORE DARI ZIP (database + media) ===
                tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
                os.close(tmp_fd)
                with open(tmp_path, 'wb') as f:
                    for chunk in backup_file.chunks():
                        f.write(chunk)

                tmp_extract = tempfile.mkdtemp()
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    zf.extractall(tmp_extract)

                # Restore database
                db_in_zip = os.path.join(tmp_extract, 'database.sqlite3')
                if os.path.exists(db_in_zip):
                    shutil.copy2(db_in_zip, str(db_path))
                else:
                    raise Exception("File database.sqlite3 tidak ditemukan dalam ZIP")

                # Restore media
                media_in_zip = os.path.join(tmp_extract, 'media')
                if os.path.exists(media_in_zip):
                    # Hapus media lama
                    if os.path.exists(media_root):
                        for item_name in os.listdir(media_root):
                            item_path = os.path.join(media_root, item_name)
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.unlink(item_path)
                    else:
                        os.makedirs(media_root, exist_ok=True)
                    # Copy media dari backup
                    for item_name in os.listdir(media_in_zip):
                        src = os.path.join(media_in_zip, item_name)
                        dst = os.path.join(media_root, item_name)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src, dst)

                # Cleanup temp files
                shutil.rmtree(tmp_extract, ignore_errors=True)
                os.unlink(tmp_path)
                restore_note = f"Restore ZIP (database + media) oleh {request.user.username}. Pre-restore: {pre_restore}"

            elif filename.endswith('.sqlite3') or filename.endswith('.db'):
                # === BACKWARD COMPATIBLE: RESTORE DARI FILE SQLITE3 ===
                with open(str(db_path), 'wb') as f:
                    for chunk in backup_file.chunks():
                        f.write(chunk)
                restore_note = f"Restore SQLite oleh {request.user.username}. Pre-restore: {pre_restore}"
            else:
                messages.error(request, 'Format file tidak didukung. Gunakan file .zip atau .sqlite3')
                return redirect('pengaturan:manajemen_data')

            BackupHistory.objects.create(
                aksi='restore', nama_file=backup_file.name,
                ukuran_file=backup_file.size, user=request.user,
                catatan=restore_note
            )
            messages.success(request, 'Database berhasil di-restore! Silakan restart server.')
        except Exception as e:
            messages.error(request, f'Gagal restore: {str(e)}')
    return redirect('pengaturan:manajemen_data')


@login_required
@permission_required_func('delete', 'pengaturan', 'manajemen_data')
def reset_data(request):
    if request.method == 'POST':
        konfirmasi = request.POST.get('konfirmasi', '')
        if konfirmasi == 'HAPUS SEMUA':
            try:
                from apps.licenses.models import Product, Client, LicenseKey
                from apps.pembelian.models import PembelianLisensi, PembelianLisensiItem
                media_root = str(settings.MEDIA_ROOT)
                media_deleted = 0

                with transaction.atomic():
                    PembelianLisensiItem.objects.all().delete()
                    PembelianLisensi.objects.all().delete()
                    LicenseKey.objects.all().delete()
                    Client.objects.all().delete()
                    Product.objects.all().delete()

                # Hapus file media kecuali folder system/
                protected_folders = {'system'}
                if os.path.exists(media_root):
                    for item_name in os.listdir(media_root):
                        if item_name in protected_folders:
                            continue
                        item_path = os.path.join(media_root, item_name)
                        try:
                            if os.path.isdir(item_path):
                                file_count = sum(len(f) for _, _, f in os.walk(item_path))
                                media_deleted += file_count
                                shutil.rmtree(item_path)
                            else:
                                media_deleted += 1
                                os.unlink(item_path)
                        except Exception as e:
                            logger.warning("Error tidak terduga: %s", e)

                BackupHistory.objects.create(
                    aksi='reset', user=request.user,
                    catatan=f"Reset data oleh {request.user.username}. {media_deleted} file media dihapus."
                )
                messages.success(request, f'Semua data berhasil direset! ({media_deleted} file media dihapus)')
            except Exception as e:
                messages.error(request, f'Gagal reset: {str(e)}')
        else:
            messages.warning(request, 'Konfirmasi tidak valid. Ketik HAPUS SEMUA untuk mengonfirmasi.')
    return redirect('pengaturan:manajemen_data')


@login_required
def api_database_stats(request):
    from apps.licenses.models import Product, Client, LicenseKey
    db_path = settings.DATABASES['default']['NAME']
    return JsonResponse({
        'db_size_mb': round(os.path.getsize(db_path) / (1024 * 1024), 2) if os.path.exists(db_path) else 0,
        'total_produk': Product.objects.count(),
        'total_klien': Client.objects.count(),
        'total_lisensi': LicenseKey.objects.count(),
    })
