"""
Views AI Assistant - Chat, Config, Dashboard, History.
"""
import json
import time
import logging
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from web_project import TemplateLayout
from .models import AIAssistantConfig, ChatHistory, ChatFeedback
from .intents import detect_intent, gather_data
from apps.core.mixins import ReadPermissionMixin, permission_required_func

logger = logging.getLogger(__name__)


class AIAssistantIndexView(LoginRequiredMixin, ReadPermissionMixin, TemplateView):
    permission_module = 'ai'
    permission_sub_module = 'ai_chat'
    template_name = 'ai_assistant/index.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        config = AIAssistantConfig.load()
        context['config'] = config
        context['is_configured'] = bool(config.api_key)
        context['chat_history'] = ChatHistory.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:50]
        return context


class AIAssistantDashboardView(LoginRequiredMixin, ReadPermissionMixin, TemplateView):
    permission_module = 'ai'
    permission_sub_module = 'ai_dashboard'
    template_name = 'ai_assistant/dashboard.html'

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        from django.db.models import Avg, Count, Sum
        from apps.licenses.models import LicenseKey, Client
        from django.utils import timezone
        import datetime

        try:
            from apps.pembelian.models import PembelianLisensi
            has_pembelian = True
        except Exception:
            has_pembelian = False

        # AI Stats
        context['total_chats'] = ChatHistory.objects.filter(role='user').count()
        context['total_responses'] = ChatHistory.objects.filter(role='assistant').count()
        context['avg_response_time'] = ChatHistory.objects.filter(
            role='assistant'
        ).aggregate(avg=Avg('response_time'))['avg'] or 0
        context['avg_rating'] = ChatFeedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0
        context['recent_chats'] = ChatHistory.objects.filter(
            role='user'
        ).order_by('-created_at')[:10]

        # Feedback Stats
        context['total_feedback_up'] = ChatFeedback.objects.filter(rating__gte=4).count()
        context['total_feedback_down'] = ChatFeedback.objects.filter(rating__lte=2).count()

        # License Stats — field yang benar: status, expires_at
        now = timezone.now()
        total_lisensi = LicenseKey.objects.count()
        lisensi_aktif = LicenseKey.objects.filter(status='active').count()
        lisensi_expired = LicenseKey.objects.filter(status='expired').count()
        lisensi_suspended = LicenseKey.objects.filter(status='suspended').count()

        context['total_lisensi'] = total_lisensi
        context['lisensi_aktif'] = lisensi_aktif
        context['lisensi_expired'] = lisensi_expired
        context['lisensi_suspended'] = lisensi_suspended
        context['total_klien'] = Client.objects.count()

        # Revenue Data — field yang benar: total_harga, status, dibuat_pada
        rev_now = 0
        rev_last = 0
        rev_growth = 0.0
        profit = 0

        if has_pembelian:
            try:
                today = now.date()
                rev_now = float(PembelianLisensi.objects.filter(
                    status='completed',
                    dibuat_pada__month=today.month,
                    dibuat_pada__year=today.year
                ).aggregate(total=Sum('total_harga'))['total'] or 0)

                last_month = today.replace(day=1) - datetime.timedelta(days=1)
                rev_last = float(PembelianLisensi.objects.filter(
                    status='completed',
                    dibuat_pada__month=last_month.month,
                    dibuat_pada__year=last_month.year
                ).aggregate(total=Sum('total_harga'))['total'] or 0)

                if rev_last > 0:
                    rev_growth = round(((rev_now - rev_last) / rev_last) * 100, 1)
                else:
                    rev_growth = 100.0 if rev_now > 0 else 0.0

                total_pembelian = PembelianLisensi.objects.filter(status='completed').count()
                avg_trx_value = float(PembelianLisensi.objects.filter(
                    status='completed'
                ).aggregate(avg=Avg('total_harga'))['avg'] or 0)
                context['avg_transaksi'] = avg_trx_value
                profit = rev_now  # CLS mainly tracks income
            except Exception:
                context['avg_transaksi'] = 0
        else:
            context['avg_transaksi'] = 0

        context['rev_now'] = rev_now
        context['rev_growth'] = rev_growth
        context['profit'] = profit

        # Trend Laporan 6 Bulan
        monthly_labels = []
        monthly_values = []
        try:
            today = now.date()
            for i in range(5, -1, -1):
                d = today.replace(day=1) - datetime.timedelta(days=30 * i)
                monthly_labels.append(d.strftime('%b'))
                if has_pembelian:
                    val = float(PembelianLisensi.objects.filter(
                        status='completed',
                        dibuat_pada__month=d.month,
                        dibuat_pada__year=d.year
                    ).aggregate(total=Sum('total_harga'))['total'] or 0)
                    monthly_values.append(val)
                else:
                    monthly_values.append(0)
        except Exception:
            monthly_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            monthly_values = [0] * 6

        context['monthly_labels'] = json.dumps(monthly_labels)
        context['monthly_values'] = json.dumps(monthly_values)

        # Health Score Logic
        score = 100
        if total_lisensi == 0:
            score = 0
        else:
            aktif_ratio = (lisensi_aktif / total_lisensi) * 100
            if aktif_ratio < 50:
                score -= 30
            elif aktif_ratio < 80:
                score -= 10

            if rev_growth < 0:
                score -= 20

        context['health_score'] = max(0, score)
        if score >= 80:
            context['health_level'] = 'Sangat Sehat'
            context['health_color'] = '#28c76f'
        elif score >= 50:
            context['health_level'] = 'Cukup Baik'
            context['health_color'] = '#ff9f43'
        else:
            context['health_level'] = 'Perlu Perhatian'
            context['health_color'] = '#ea5455'

        context['anomalies'] = []
        context['dashboard_error'] = None

        return context


@login_required
@permission_required_func('create', 'ai', 'ai_chat')
def chat_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
    except (json.JSONDecodeError, ValueError):
        user_message = request.POST.get('message', '').strip()

    if not user_message:
        return JsonResponse({'error': 'Pesan tidak boleh kosong'}, status=400)

    config = AIAssistantConfig.load()
    if not config.api_key:
        return JsonResponse({'error': 'AI belum dikonfigurasi. Masukkan API Key di Pengaturan AI.'}, status=400)

    # Save user message
    ChatHistory.objects.create(user=request.user, role='user', message=user_message)

    # Detect intent & gather data
    intent = detect_intent(user_message)
    context_data = gather_data(intent, user_message)

    # Build prompt
    system_prompt = config.system_prompt or "Kamu adalah AI Assistant untuk Central License Server."
    data_prompt = f"\n\nData sistem (konteks):\n{context_data.get('ringkasan', '')}" if context_data else ""

    start_time = time.time()
    try:
        ai_response = _call_ai_provider(config, system_prompt + data_prompt, user_message)
    except Exception as e:
        ai_response = f"Maaf, terjadi error saat menghubungi AI: {str(e)}"
    response_time = round(time.time() - start_time, 2)

    # Save assistant response
    ChatHistory.objects.create(
        user=request.user, role='assistant', message=ai_response,
        intent=intent, provider=config.provider, model_used=config.model_name,
        response_time=response_time
    )

    return JsonResponse({'response': ai_response, 'intent': intent, 'response_time': response_time})


def _call_ai_provider(config, system_prompt, user_message):
    import urllib.request
    import urllib.error
    import ssl

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    if config.provider == 'gemini':
        return _call_gemini(config, system_prompt, user_message, ssl_context)
    elif config.provider == 'openai':
        return _call_openai(config, system_prompt, user_message, ssl_context)
    elif config.provider == 'groq':
        return _call_groq(config, system_prompt, user_message, ssl_context)
    else:
        return "Provider AI tidak dikenali."


def _call_gemini(config, system_prompt, user_message, ssl_ctx):
    import urllib.request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model_name}:generateContent?key={config.api_key}"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {"temperature": config.temperature, "maxOutputTokens": config.max_tokens}
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    candidates = result.get('candidates', [])
    if candidates:
        parts = candidates[0].get('content', {}).get('parts', [])
        if parts:
            return parts[0].get('text', 'Tidak ada respons.')
    return 'Tidak ada respons dari Gemini.'


def _call_openai(config, system_prompt, user_message, ssl_ctx):
    import urllib.request
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": config.model_name or "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {config.api_key}')
    with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    choices = result.get('choices', [])
    if choices:
        return choices[0].get('message', {}).get('content', 'Tidak ada respons.')
    return 'Tidak ada respons dari OpenAI.'


def _call_groq(config, system_prompt, user_message, ssl_ctx):
    import urllib.request
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": config.model_name or "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {config.api_key}')
    with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    choices = result.get('choices', [])
    if choices:
        return choices[0].get('message', {}).get('content', 'Tidak ada respons.')
    return 'Tidak ada respons dari Groq.'


@login_required
@permission_required_func('write', 'ai', 'ai_chat')
def config_api(request):
    if request.method == 'POST':
        config = AIAssistantConfig.load()
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            body = request.POST
        config.provider = body.get('provider', config.provider)
        api_key = body.get('api_key', '')
        if api_key:
            config.api_key = api_key
        config.model_name = body.get('model_name', config.model_name)
        config.max_tokens = int(body.get('max_tokens', config.max_tokens))
        config.temperature = float(body.get('temperature', config.temperature))
        config.system_prompt = body.get('system_prompt', config.system_prompt)
        config.save()
        return JsonResponse({'success': True, 'message': 'Konfigurasi AI berhasil disimpan!'})
    config = AIAssistantConfig.load()
    return JsonResponse({
        'provider': config.provider,
        'model_name': config.model_name,
        'max_tokens': config.max_tokens,
        'temperature': config.temperature,
        'system_prompt': config.system_prompt,
        'has_api_key': bool(config.api_key),
    })


@login_required
@permission_required_func('delete', 'ai', 'ai_chat')
def clear_history(request):
    if request.method == 'POST':
        ChatHistory.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True, 'message': 'Riwayat chat berhasil dihapus'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def feedback_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            chat_id = body.get('chat_id')
            rating = int(body.get('rating', 0))
            komentar = body.get('komentar', '')
            chat = ChatHistory.objects.get(pk=chat_id)
            ChatFeedback.objects.create(
                chat=chat, user=request.user, rating=rating, komentar=komentar
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
