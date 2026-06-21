"""
Views untuk Log Aktifitas - Menampilkan riwayat aktivitas user.
"""

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

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from web_project import TemplateLayout
from .models import UserActivity


class ActivityLogIndexView(LoginRequiredMixin, ListView):
    model = UserActivity
    template_name = 'activity_log/index.html'
    context_object_name = 'activities'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related('user')
        # Filter berdasarkan aksi
        action = self.request.GET.get('action')
        if action:
            qs = qs.filter(action=action)
        # Filter berdasarkan user
        user_id = self.request.GET.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)
        # Filter berdasarkan tanggal
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        # Filter pencarian
        search = self.request.GET.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(model_name__icontains=search) |
                Q(object_repr__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        from django.contrib.auth.models import User
        context['users'] = User.objects.all().order_by('username')
        context['action_choices'] = UserActivity.ACTION_CHOICES
        context['total_activities'] = UserActivity.objects.count()
        context['filter_action'] = self.request.GET.get('action', '')
        context['filter_user'] = self.request.GET.get('user', '')
        context['filter_date_from'] = self.request.GET.get('date_from', '')
        context['filter_date_to'] = self.request.GET.get('date_to', '')
        context['filter_search'] = self.request.GET.get('search', '')
        return context
