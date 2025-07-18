# Generated by Django 5.2 on 2025-05-18 08:48

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('market_research', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='marketpriceresearch',
            name='agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'user_type': 'AGENT'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='market_research', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='marketpriceresearch',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='price_research', to='market_research.market'),
        ),
        migrations.AddField(
            model_name='unsynceddata',
            name='agent',
            field=models.ForeignKey(limit_choices_to={'user_type': 'AGENT'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='unsynced_data', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='synclog',
            name='data',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_logs', to='market_research.unsynceddata'),
        ),
        migrations.AddIndex(
            model_name='unsynceddata',
            index=models.Index(fields=['sync_status'], name='market_rese_sync_st_6f3ddc_idx'),
        ),
        migrations.AddIndex(
            model_name='unsynceddata',
            index=models.Index(fields=['data_type'], name='market_rese_data_ty_5b969e_idx'),
        ),
        migrations.AddIndex(
            model_name='unsynceddata',
            index=models.Index(fields=['timestamp'], name='market_rese_timesta_1fa8ec_idx'),
        ),
        migrations.AddIndex(
            model_name='unsynceddata',
            index=models.Index(fields=['device_id'], name='market_rese_device__98111c_idx'),
        ),
    ]
