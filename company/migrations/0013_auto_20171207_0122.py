# Generated by Django 1.11.8 on 2017-12-07 00:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0012_company_query_count'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='company',
            options={'ordering': ['-created_at'], 'permissions': (('view_company', 'Can see all company'),), 'verbose_name': 'Producent', 'verbose_name_plural': 'Producenci'},
        ),
    ]
