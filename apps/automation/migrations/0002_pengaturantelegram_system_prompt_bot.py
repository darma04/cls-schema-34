# Generated migration for system_prompt_bot field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pengaturantelegram',
            name='system_prompt_bot',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Instruksi tambahan untuk mengatur perilaku AI chatbot Telegram. Kosongkan untuk menggunakan default.',
                verbose_name='System Prompt Bot AI'
            ),
        ),
    ]
