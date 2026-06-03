"""
==========================================================================
 DASHBOARD VIEW — Halaman Utama Central License Server
==========================================================================
 Menampilkan statistik real-time dan grafik tren lisensi 12 bulan.
==========================================================================
"""
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from web_project import TemplateLayout
from apps.core.mixins import TenantScopedResponseCacheMixin
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
import json
import logging
import traceback

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class DashboardView(TenantScopedResponseCacheMixin, TemplateView):
    """View utama DASHBOARD CENTRAL LICENSE SERVER."""
    template_name = 'dashboard/dashboard.html'
    cache_timeout = 60

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        try:
            from apps.licenses.models import Product, Client, LicenseKey
            from django.utils.dateparse import parse_date
            import datetime

            start_date_str = self.request.GET.get('start_date')
            end_date_str = self.request.GET.get('end_date')

            products_qs = Product.objects.all()
            clients_qs = Client.objects.all()
            licenses_qs = LicenseKey.objects.all()

            filter_start_date = None
            filter_end_date = None
            is_filtered = False
            start_date_obj = None
            end_date_obj = None

            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    end_date_inclusive = end_date + datetime.timedelta(days=1)
                    products_qs = products_qs.filter(created_at__gte=start_date, created_at__lt=end_date_inclusive)
                    clients_qs = clients_qs.filter(created_at__gte=start_date, created_at__lt=end_date_inclusive)
                    licenses_qs = licenses_qs.filter(created_at__gte=start_date, created_at__lt=end_date_inclusive)
                    
                    filter_start_date = start_date_str
                    filter_end_date = end_date_str
                    is_filtered = True
                    start_date_obj = start_date
                    end_date_obj = end_date

            total_product = products_qs.count()
            total_client = clients_qs.count()
            total_licenses = licenses_qs.count()
            active_licenses = licenses_qs.filter(status='active').count()
            suspended_licenses = licenses_qs.filter(status='suspended').count()
            expired_licenses = licenses_qs.filter(status='expired').count()

            # 5 recent clients
            recent_clients = clients_qs.order_by('-created_at')[:5]

            # 5 recent licenses
            recent_licenses = licenses_qs.select_related('product', 'client').order_by('-created_at')[:5]

            # ===== DATA GRAFIK GELOMBANG DINAMIS =====
            now = timezone.now()
            chart_labels = []
            chart_total = []
            chart_active = []
            chart_expired = []
            chart_suspended = []

            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                           'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']

            if is_filtered and start_date_obj and end_date_obj:
                delta_days = (end_date_obj - start_date_obj).days
                if delta_days <= 62:
                    current_date = start_date_obj
                    while current_date <= end_date_obj:
                        label = current_date.strftime("%d %b %Y")
                        chart_labels.append(label)
                        
                        next_day = current_date + datetime.timedelta(days=1)
                        daily_qs = LicenseKey.objects.filter(
                            created_at__gte=current_date, created_at__lt=next_day
                        )
                        chart_total.append(daily_qs.count())
                        chart_active.append(daily_qs.filter(status='active').count())
                        chart_expired.append(daily_qs.filter(status='expired').count())
                        chart_suspended.append(daily_qs.filter(status='suspended').count())
                        current_date = next_day
                else:
                    current_date = start_date_obj.replace(day=1)
                    while current_date <= end_date_obj:
                        label = f"{month_names[current_date.month - 1]} {current_date.year}"
                        chart_labels.append(label)
                        
                        if current_date.month == 12:
                            next_month = current_date.replace(year=current_date.year + 1, month=1)
                        else:
                            next_month = current_date.replace(month=current_date.month + 1)
                            
                        monthly_qs = LicenseKey.objects.filter(
                            created_at__gte=current_date, created_at__lt=next_month
                        )
                        chart_total.append(monthly_qs.count())
                        chart_active.append(monthly_qs.filter(status='active').count())
                        chart_expired.append(monthly_qs.filter(status='expired').count())
                        chart_suspended.append(monthly_qs.filter(status='suspended').count())
                        current_date = next_month
            else:
                for i in range(11, -1, -1):
                    # Hitung bulan ke-i yang lalu secara presisi
                    current_month = now.month - i
                    current_year = now.year
                    
                    if current_month <= 0:
                        current_month += 12
                        current_year -= 1
                    
                    month_start = now.replace(year=current_year, month=current_month, day=1, hour=0, minute=0, second=0, microsecond=0)

                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year + 1, month=1)
                    else:
                        month_end = month_start.replace(month=month_start.month + 1)

                    label = f"{month_names[month_start.month - 1]} {month_start.year}"
                    chart_labels.append(label)

                    # Count lisensi yang dibuat di bulan ini
                    total_in_month = LicenseKey.objects.filter(
                        created_at__gte=month_start, created_at__lt=month_end
                    ).count()
                    active_in_month = LicenseKey.objects.filter(
                        created_at__gte=month_start, created_at__lt=month_end, status='active'
                    ).count()
                    expired_in_month = LicenseKey.objects.filter(
                        created_at__gte=month_start, created_at__lt=month_end, status='expired'
                    ).count()
                    suspended_in_month = LicenseKey.objects.filter(
                        created_at__gte=month_start, created_at__lt=month_end, status='suspended'
                    ).count()

                    chart_total.append(total_in_month)
                    chart_active.append(active_in_month)
                    chart_expired.append(expired_in_month)
                    chart_suspended.append(suspended_in_month)

            context.update({
                'is_dashboard_page': True,
                'filter_start_date': filter_start_date or '',
                'filter_end_date': filter_end_date or '',
                'is_filtered': is_filtered,
                'bulan_ini': f"{filter_start_date} hingga {filter_end_date}" if is_filtered else "Total Keseluruhan",
                'total_product': total_product,
                'total_client': total_client,
                'total_licenses': total_licenses,
                'active_licenses': active_licenses,
                'suspended_licenses': suspended_licenses,
                'expired_licenses': expired_licenses,
                'recent_clients': recent_clients,
                'recent_licenses': recent_licenses,
                # Chart data (JSON-safe untuk JavaScript)
                'chart_labels': json.dumps(chart_labels),
                'chart_total': json.dumps(chart_total),
                'chart_active': json.dumps(chart_active),
                'chart_expired': json.dumps(chart_expired),
                'chart_suspended': json.dumps(chart_suspended),
            })

        except Exception as e:
            logger.error(f"Error loading dashboard data: {e}")
            logger.error(traceback.format_exc())
            context.update({
                'is_dashboard_page': True,
                'total_product': 0, 'total_client': 0, 'total_licenses': 0,
                'active_licenses': 0, 'suspended_licenses': 0, 'expired_licenses': 0,
                'recent_clients': [], 'recent_licenses': [],
                'chart_labels': json.dumps([]),
                'chart_total': json.dumps([]),
                'chart_active': json.dumps([]),
                'chart_expired': json.dumps([]),
                'chart_suspended': json.dumps([]),
            })

        return context
