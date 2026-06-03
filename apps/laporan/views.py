"""
Views Laporan - Laporan Lisensi, Klien, Pendapatan, Keuangan.
Data diambil dari model di module licenses dan pembelian.
"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q
from django.utils import timezone
from web_project import TemplateLayout
from apps.core.mixins import TenantScopedResponseCacheMixin
from apps.licenses.models import Product, Client, LicenseKey


class LaporanLisensiView(TenantScopedResponseCacheMixin, LoginRequiredMixin, TemplateView):
    template_name = 'laporan/lisensi.html'
    cache_timeout = 120

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        context['start_date'] = start_date or ''
        context['end_date'] = end_date or ''

        qs_license = LicenseKey.objects.all()
        if start_date:
            qs_license = qs_license.filter(created_at__date__gte=start_date)
        if end_date:
            qs_license = qs_license.filter(created_at__date__lte=end_date)

        context['total_lisensi'] = qs_license.count()
        context['lisensi_aktif'] = qs_license.filter(status='active').count()
        context['lisensi_kadaluarsa'] = qs_license.filter(status='expired').count()
        context['lisensi_suspended'] = qs_license.filter(status='suspended').count()
        context['lisensi_teraktivasi'] = qs_license.filter(is_activated=True).count()
        context['lisensi_belum_aktif'] = qs_license.filter(is_activated=False).count()

        context['per_produk'] = Product.objects.annotate(
            total_lisensi=Count('licenses'),
            lisensi_aktif=Count('licenses', filter=Q(licenses__status='active')),
            lisensi_kadaluarsa=Count('licenses', filter=Q(licenses__status='expired')),
        ).order_by('name')

        # Lisensi segera kadaluarsa (30 hari ke depan)
        now = timezone.now()
        from datetime import timedelta
        context['segera_kadaluarsa'] = LicenseKey.objects.filter(
            status='active', is_activated=True,
            expires_at__lte=now + timedelta(days=30),
            expires_at__gte=now
        ).select_related('product', 'client').order_by('expires_at')[:10]

        # Daftar Lisensi untuk DataTables
        context['lisensi_list'] = qs_license.select_related('product', 'client').order_by('-created_at')

        return context


class LaporanKlienView(TenantScopedResponseCacheMixin, LoginRequiredMixin, TemplateView):
    template_name = 'laporan/klien.html'
    cache_timeout = 120

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        context['start_date'] = start_date or ''
        context['end_date'] = end_date or ''

        qs_klien = Client.objects.all()
        qs_lisensi = LicenseKey.objects.all()

        if start_date:
            qs_klien = qs_klien.filter(created_at__date__gte=start_date)
            qs_lisensi = qs_lisensi.filter(created_at__date__gte=start_date)
        if end_date:
            qs_klien = qs_klien.filter(created_at__date__lte=end_date)
            qs_lisensi = qs_lisensi.filter(created_at__date__lte=end_date)

        total_klien = qs_klien.count()
        context['total_klien'] = total_klien
        
        total_lisensi = qs_lisensi.count()
        total_aktif = qs_lisensi.filter(status='active').count()
        total_nonaktif = total_lisensi - total_aktif
        
        context['total_lisensi_all'] = total_lisensi
        context['total_lisensi_aktif'] = total_aktif
        context['total_lisensi_nonaktif'] = total_nonaktif
        
        rasio = round((total_aktif / total_lisensi * 100) if total_lisensi > 0 else 0)
        context['rasio_aktif'] = rasio
        
        context['klien_list'] = qs_klien.annotate(
            total_lisensi=Count('licenses'),
            lisensi_aktif=Count('licenses', filter=Q(licenses__status='active')),
        ).order_by('-total_lisensi')
        context['top_klien'] = context['klien_list'].order_by('-lisensi_aktif')[:10]
        return context


class LaporanPendapatanView(TenantScopedResponseCacheMixin, LoginRequiredMixin, TemplateView):
    template_name = 'laporan/pendapatan.html'
    cache_timeout = 120

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        try:
            from apps.pembelian.models import PembelianLisensi
            from apps.licenses.models import Client
            
            start_date = self.request.GET.get('start_date', '')
            end_date = self.request.GET.get('end_date', '')
            filter_klien = self.request.GET.get('klien', '')

            qs = PembelianLisensi.objects.filter(status='completed').select_related('klien')
            if start_date:
                qs = qs.filter(tanggal__gte=start_date)
            if end_date:
                qs = qs.filter(tanggal__lte=end_date)
            if filter_klien:
                qs = qs.filter(klien__id=filter_klien)

            context['pembayaran_list'] = qs.order_by('-tanggal')
            context['total_pendapatan'] = qs.aggregate(total=Sum('total_harga'))['total'] or 0
            context['total_transaksi'] = qs.count()
            context['start_date'] = start_date
            context['end_date'] = end_date
            context['filter_klien'] = filter_klien
            context['klien_list'] = Client.objects.all().order_by('name')

        except Exception:
            context['pembayaran_list'] = []
            context['total_pendapatan'] = 0
            context['total_transaksi'] = 0
            context['start_date'] = ''
            context['end_date'] = ''
            context['filter_klien'] = ''
            context['klien_list'] = []
        return context


class LaporanKeuanganView(TenantScopedResponseCacheMixin, LoginRequiredMixin, TemplateView):
    template_name = 'laporan/keuangan.html'
    cache_timeout = 120

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        try:
            from apps.pembelian.models import PembelianLisensi
            start_date = self.request.GET.get('start_date', '')
            end_date = self.request.GET.get('end_date', '')
            jenis_filter = self.request.GET.get('jenis', '')

            qs = PembelianLisensi.objects.filter(status='completed').select_related('klien')
            if start_date:
                qs = qs.filter(dibuat_pada__gte=start_date)
            if end_date:
                qs = qs.filter(dibuat_pada__lte=end_date)
            
            total_pendapatan = qs.aggregate(total=Sum('total_harga'))['total'] or 0
            
            context['total_pemasukan'] = total_pendapatan
            context['total_pengeluaran'] = 0 # License server primarily tracks income
            context['laba_bersih'] = total_pendapatan
            context['margin_persen'] = 100 if total_pendapatan > 0 else 0
            context['total_trx_masuk'] = qs.count()
            context['total_trx_keluar'] = 0
            
            context['pemasukan_list'] = qs.order_by('-dibuat_pada')[:20]
            context['pengeluaran_list'] = []
            
            # Tren Pendapatan Tahunan (12 bulan)
            from django.db.models.functions import ExtractMonth
            current_year = timezone.now().year
            monthly_data = qs.filter(tanggal__year=current_year).annotate(
                month=ExtractMonth('tanggal')
            ).values('month').annotate(total=Sum('total_harga')).order_by('month')
            
            revenue_by_month = [0] * 12
            for item in monthly_data:
                if 1 <= item['month'] <= 12:
                    revenue_by_month[item['month'] - 1] = float(item['total'])
            context['revenue_by_month'] = revenue_by_month
            
            context['start_date'] = start_date
            context['end_date'] = end_date
            context['jenis_filter'] = jenis_filter
        except Exception:
            context['total_pemasukan'] = 0
            context['total_pengeluaran'] = 0
            context['laba_bersih'] = 0
            context['margin_persen'] = 0
            context['total_trx_masuk'] = 0
            context['total_trx_keluar'] = 0
            context['pemasukan_list'] = []
            context['pengeluaran_list'] = []
        return context
