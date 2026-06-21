"""
Views Pembelian Lisensi - CRUD transaksi pembelian.
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

from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.db.models import Sum
from web_project import TemplateLayout
from .models import PembelianLisensi, PembelianLisensiItem
from apps.licenses.models import Product, Client
from apps.pengaturan.models import TemplateCetak





class PembelianListView(LoginRequiredMixin, ListView):
    model = PembelianLisensi
    template_name = 'pembelian/pembelian_list.html'
    context_object_name = 'pembelian_list'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('klien', 'dibuat_oleh')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
            
        search_query = self.request.GET.get('q', '')
        if search_query:
            from django.db.models import Q
            qs = qs.filter(
                Q(nomor_transaksi__icontains=search_query) |
                Q(klien__name__icontains=search_query)
            )

        # Filter by Date
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            qs = qs.filter(tanggal__gte=start_date)
        if end_date:
            qs = qs.filter(tanggal__lte=end_date)
            
        return qs

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Calculate totals from the filtered QuerySet, NOT the entire table
        filtered_qs = self.get_queryset()
        context['total_pembelian'] = filtered_qs.count()
        context['total_completed'] = filtered_qs.filter(status='completed').count()
        context['total_pending'] = filtered_qs.filter(status='pending').count()
        context['total_pendapatan'] = filtered_qs.filter(
            status='completed'
        ).aggregate(total=Sum('total_harga'))['total'] or 0
        
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        return context


class PembelianCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'pembelian/pembelian_form.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['klien_list'] = Client.objects.all().order_by('name')
        context['produk_list'] = Product.objects.all().order_by('name')
        return context

    def post(self, request, *args, **kwargs):
        klien_id = request.POST.get('klien')
        catatan = request.POST.get('catatan', '')
        produk_ids = request.POST.getlist('produk[]')
        jumlah_list = request.POST.getlist('jumlah[]')
        harga_list = request.POST.getlist('harga[]')
        durasi_list = request.POST.getlist('durasi[]')

        if not klien_id or not produk_ids:
            messages.error(request, 'Pilih klien dan minimal 1 produk!')
            return redirect('pembelian:pembelian_create')

        try:
            with transaction.atomic():
                klien = Client.objects.get(pk=klien_id)
                pembelian = PembelianLisensi.objects.create(
                    klien=klien, catatan=catatan, dibuat_oleh=request.user
                )

                for i, produk_id in enumerate(produk_ids):
                    produk = Product.objects.get(pk=produk_id)
                    jumlah = int(jumlah_list[i]) if i < len(jumlah_list) else 1
                    harga = float(harga_list[i]) if i < len(harga_list) else 0
                    durasi = int(durasi_list[i]) if i < len(durasi_list) else 365
                    PembelianLisensiItem.objects.create(
                        pembelian=pembelian, produk=produk,
                        jumlah=jumlah, harga_satuan=harga, durasi_hari=durasi
                    )
                pembelian.update_total()

            # Kirim notifikasi Telegram
            try:
                from apps.automation.telegram_service import kirim_notifikasi_async
                kirim_notifikasi_async('pembelian', pembelian.nomor_transaksi, {
                    'nomor_transaksi': pembelian.nomor_transaksi,
                    'client_name': klien.name,
                    'product_name': ', '.join([Product.objects.get(pk=pid).name for pid in produk_ids]),
                    'total': f"{float(pembelian.total_harga):,.0f}",
                    'tanggal': pembelian.tanggal.strftime('%d/%m/%Y'),
                })
            except Exception as e:
                logger.warning("Gagal kirim notifikasi: %s", e)

            messages.success(request, f'Pembelian {pembelian.nomor_transaksi} berhasil dibuat!')
            return redirect('pembelian:pembelian_detail', pk=pembelian.pk)
        except Exception as e:
            messages.error(request, f'Gagal membuat pembelian: {str(e)}')
            return redirect('pembelian:pembelian_create')


class PembelianDetailView(LoginRequiredMixin, DetailView):
    model = PembelianLisensi
    template_name = 'pembelian/pembelian_detail.html'
    context_object_name = 'pembelian'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['items'] = self.object.items.select_related('produk').all()
        return context


class PembelianEditView(LoginRequiredMixin, TemplateView):
    """View edit pembelian lisensi — ubah klien, catatan, dan item."""
    template_name = 'pembelian/pembelian_edit.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        pembelian = get_object_or_404(PembelianLisensi, pk=self.kwargs['pk'])
        context['pembelian'] = pembelian
        context['items'] = pembelian.items.select_related('produk').all()
        context['klien_list'] = Client.objects.all().order_by('name')
        context['produk_list'] = Product.objects.all().order_by('name')
        context['is_edit'] = True
        return context

    def post(self, request, *args, **kwargs):
        pembelian = get_object_or_404(PembelianLisensi, pk=self.kwargs['pk'])
        klien_id = request.POST.get('klien')
        catatan = request.POST.get('catatan', '')
        status_val = request.POST.get('status', pembelian.status)
        produk_ids = request.POST.getlist('produk[]')
        jumlah_list = request.POST.getlist('jumlah[]')
        harga_list = request.POST.getlist('harga[]')
        durasi_list = request.POST.getlist('durasi[]')

        if not klien_id or not produk_ids:
            messages.error(request, 'Pilih klien dan minimal 1 produk!')
            return redirect('pembelian:pembelian_edit', pk=pembelian.pk)

        try:
            with transaction.atomic():
                klien = Client.objects.get(pk=klien_id)
                pembelian.klien = klien
                pembelian.catatan = catatan
                pembelian.status = status_val
                pembelian.save()

                # Hapus item lama dan buat ulang
                pembelian.items.all().delete()
                for i, produk_id in enumerate(produk_ids):
                    produk = Product.objects.get(pk=produk_id)
                    jumlah = int(jumlah_list[i]) if i < len(jumlah_list) else 1
                    harga = float(harga_list[i]) if i < len(harga_list) else 0
                    durasi = int(durasi_list[i]) if i < len(durasi_list) else 365
                    PembelianLisensiItem.objects.create(
                        pembelian=pembelian, produk=produk,
                        jumlah=jumlah, harga_satuan=harga, durasi_hari=durasi
                    )
                pembelian.update_total()

            messages.success(request, f'Pembelian {pembelian.nomor_transaksi} berhasil diperbarui!')
            return redirect('pembelian:pembelian_detail', pk=pembelian.pk)
        except Exception as e:
            messages.error(request, f'Gagal memperbarui pembelian: {str(e)}')
            return redirect('pembelian:pembelian_edit', pk=pembelian.pk)


@login_required
def pembelian_update_status(request, pk):
    if request.method == 'POST':
        with transaction.atomic():
            pembelian = get_object_or_404(PembelianLisensi.objects.select_for_update(), pk=pk)
            new_status = request.POST.get('status')
            if new_status in dict(PembelianLisensi.STATUS_CHOICES):
                pembelian.status = new_status
                pembelian.save()
                messages.success(request, f'Status pembelian {pembelian.nomor_transaksi} diubah menjadi {pembelian.get_status_display()}')
        return redirect('pembelian:pembelian_detail', pk=pk)
    return redirect('pembelian:pembelian_list')


@login_required
def pembelian_delete(request, pk):
    if request.method == 'POST':
        with transaction.atomic():
            pembelian = get_object_or_404(PembelianLisensi.objects.select_for_update(), pk=pk)
            nomor = pembelian.nomor_transaksi
            pembelian.delete()
        messages.success(request, f'Pembelian {nomor} berhasil dihapus!')
    return redirect('pembelian:pembelian_list')


@login_required
def pembelian_print(request, pk):
    """View cetak Invoice Pembelian — standalone A4, terhubung TemplateCetak jenis 'invoice'."""
    pembelian = get_object_or_404(PembelianLisensi, pk=pk)
    items = pembelian.items.select_related('produk').all()
    template = TemplateCetak.get_template('invoice')
    return render(request, 'pembelian/pembelian_print.html', {
        'pembelian': pembelian,
        'items': items,
        'template': template,
    })
