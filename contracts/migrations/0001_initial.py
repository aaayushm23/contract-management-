# Generated by Django 5.0.6 on 2024-11-27 08:55

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='contracts/')),
                ('upload_date', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ExtractedData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('party_names', models.TextField(blank=True, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('renewal_terms', models.TextField(blank=True, null=True)),
                ('payment_details', models.TextField(blank=True, null=True)),
                ('contract', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='contracts.contract')),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_date', models.DateTimeField()),
                ('sent', models.BooleanField(default=False)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contracts.contract')),
            ],
        ),
    ]
