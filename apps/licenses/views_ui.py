"""
==========================================================================
 LICENSES UI VIEWS — CRUD Views dengan Tampilan Materialize
==========================================================================
 Views untuk mengelola data Client, Product, dan LicenseKey
 menggunakan template Materialize (bukan Django Admin).
 Semua views menggunakan TemplateLayout.init() untuk konsistensi layout.
==========================================================================
"""
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from web_project import TemplateLayout
from .models import Client, Product, LicenseKey, DeviceBinding, LicenseLog
from .forms import ClientForm, ProductForm, LicenseKeyForm, LicenseKeyUpdateForm


# ==========================================================================
#  CLIENT VIEWS — CRUD Klien
# ==========================================================================

class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'licenses/client_list.html'
    context_object_name = 'clients'
    ordering = ['-created_at']

    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        
        search_query = self.request.GET.get('q', '')
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
            
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['total_clients'] = self.get_queryset().count()
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        return context


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'licenses/client_form.html'
    success_url = reverse_lazy('licenses_ui:client_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Tambah Klien Baru'
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Klien berhasil ditambahkan.')
        return response


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'licenses/client_form.html'
    success_url = reverse_lazy('licenses_ui:client_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = f'Edit Klien: {self.object.name}'
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Data klien berhasil diperbarui.')
        return response


class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = 'licenses/client_confirm_delete.html'
    success_url = reverse_lazy('licenses_ui:client_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Hapus Klien'
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        obj_name = str(self.object)
        try:
            with transaction.atomic():
                self.object.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Klien "{obj_name}" berhasil dihapus.'})
            messages.success(request, 'Klien berhasil dihapus.')
            return super().form_valid(None)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Gagal menghapus: {str(e)}'}, status=400)
            messages.error(request, f'Gagal menghapus klien: {str(e)}')
            return self.render_to_response(self.get_context_data())


# ==========================================================================
#  PRODUCT VIEWS — CRUD Produk
# ==========================================================================

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'licenses/product_list.html'
    context_object_name = 'products'
    ordering = ['-created_at']

    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        
        search_query = self.request.GET.get('q', '')
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['total_products'] = self.get_queryset().count()
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'licenses/product_form.html'
    success_url = reverse_lazy('licenses_ui:product_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Tambah Produk Baru'
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Produk berhasil ditambahkan.')
        return response


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'licenses/product_form.html'
    success_url = reverse_lazy('licenses_ui:product_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = f'Edit Produk: {self.object.name}'
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Data produk berhasil diperbarui.')
        return response


class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'licenses/product_confirm_delete.html'
    success_url = reverse_lazy('licenses_ui:product_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Hapus Produk'
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        obj_name = str(self.object)
        try:
            with transaction.atomic():
                self.object.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Produk "{obj_name}" berhasil dihapus.'})
            messages.success(request, 'Produk berhasil dihapus.')
            return super().form_valid(None)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Gagal menghapus: {str(e)}'}, status=400)
            messages.error(request, f'Gagal menghapus produk: {str(e)}')
            return self.render_to_response(self.get_context_data())


# ==========================================================================
#  LICENSEKEY VIEWS — CRUD Kunci Lisensi
# ==========================================================================

class LicenseKeyListView(LoginRequiredMixin, ListView):
    model = LicenseKey
    template_name = 'licenses/license_list.html'
    context_object_name = 'licenses'
    ordering = ['-created_at']

    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        
        search_query = self.request.GET.get('q', '')
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(key__icontains=search_query) |
                Q(client__name__icontains=search_query) |
                Q(product__name__icontains=search_query)
            )

        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        queryset = self.get_queryset()
        context['total_licenses'] = queryset.count()
        context['active_licenses'] = queryset.filter(status='active').count()
        context['expired_licenses'] = queryset.filter(status='expired').count()
        context['suspended_licenses'] = queryset.filter(status='suspended').count()
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        return context


class LicenseKeyDetailView(LoginRequiredMixin, DetailView):
    model = LicenseKey
    template_name = 'licenses/license_detail.html'
    context_object_name = 'license'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = f'Detail Lisensi: {self.object.key}'
        # Perangkat terikat (aktif dulu, lalu nonaktif)
        context['device_bindings'] = self.object.device_bindings.all().order_by('-is_active', '-last_seen')
        context['active_devices'] = self.object.device_bindings.filter(is_active=True).count()
        # Log aktivitas lisensi (20 terbaru)
        context['license_logs'] = self.object.logs.all()[:20]
        return context


class LicenseKeyCreateView(LoginRequiredMixin, CreateView):
    model = LicenseKey
    form_class = LicenseKeyForm
    template_name = 'licenses/license_form.html'
    success_url = reverse_lazy('licenses_ui:licensekey_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Buat Kunci Lisensi Baru'
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Kunci lisensi berhasil dibuat.')
        return response


class LicenseKeyUpdateView(LoginRequiredMixin, UpdateView):
    model = LicenseKey
    form_class = LicenseKeyUpdateForm
    template_name = 'licenses/license_form.html'
    success_url = reverse_lazy('licenses_ui:licensekey_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = f'Edit Lisensi: {self.object.key}'
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
        messages.success(self.request, 'Status lisensi berhasil diperbarui.')
        return response


class LicenseKeyDeleteView(LoginRequiredMixin, DeleteView):
    model = LicenseKey
    template_name = 'licenses/license_confirm_delete.html'
    success_url = reverse_lazy('licenses_ui:licensekey_list')

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context['title'] = 'Hapus Lisensi'
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        obj_name = str(self.object)
        try:
            with transaction.atomic():
                self.object.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Lisensi "{obj_name}" berhasil dihapus.'})
            messages.success(request, 'Lisensi berhasil dihapus.')
            return super().form_valid(None)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Gagal menghapus: {str(e)}'}, status=400)
            messages.error(request, f'Gagal menghapus lisensi: {str(e)}')
            return self.render_to_response(self.get_context_data())


# ==========================================================================
#  AJAX VIEWS — Aksi via AJAX (Unlink Device)
# ==========================================================================

@login_required
@require_http_methods(["POST"])
def unlink_device(request, pk):
    """AJAX endpoint untuk Admin mengunlink device dari halaman detail lisensi."""
    with transaction.atomic():
        binding = get_object_or_404(DeviceBinding.objects.select_for_update().select_related('license'), pk=pk)
        binding.is_active = False
        binding.save(update_fields=['is_active', 'last_seen'])

        # Catat log
        LicenseLog.objects.create(
            license=binding.license,
            action='unbind_device',
            detail=f"Admin unlink device: {binding.hardware_id} ({binding.device_name or '-'})",
            ip_address=request.META.get('REMOTE_ADDR'),
            hardware_id=binding.hardware_id,
        )

    return JsonResponse({
        "status": "success",
        "message": f"Perangkat {binding.device_name or binding.hardware_id[:16]} berhasil di-unlink."
    })


# ==========================================================================
#  PRINT VIEWS — Cetak Sertifikat Lisensi
# ==========================================================================

@login_required
def licensekey_print(request, pk):
    """View cetak Sertifikat Lisensi — standalone A4, terhubung TemplateCetak jenis 'lisensi'."""
    from apps.pengaturan.models import TemplateCetak
    license_obj = get_object_or_404(LicenseKey, pk=pk)
    template = TemplateCetak.get_template('lisensi')
    return render(request, 'licenses/licensekey_print.html', {
        'license': license_obj,
        'template': template,
    })
