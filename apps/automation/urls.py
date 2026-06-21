from django.urls import path
from . import views

app_name = 'automation'

urlpatterns = [
    path('telegram/', views.PengaturanTelegramView.as_view(), name='pengaturan_telegram'),
    path('telegram/test/', views.test_kirim_telegram, name='test_kirim_telegram'),
    path('telegram/deteksi-chat-id/', views.deteksi_chat_id, name='deteksi_chat_id'),
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
    path('telegram/set-webhook/', views.set_webhook, name='set_webhook'),
    path('template-pesan/', views.TemplatePesanListView.as_view(), name='template_pesan_list'),
    path('template-pesan/<int:pk>/edit/', views.TemplatePesanUpdateView.as_view(), name='template_pesan_update'),
    path('template-pesan/<int:pk>/reset/', views.reset_template, name='template_pesan_reset'),
    path('log/', views.LogNotifikasiView.as_view(), name='log_notifikasi'),
]
