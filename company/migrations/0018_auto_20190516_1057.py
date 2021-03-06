# Generated by Django 2.0.2 on 2019-05-16 08:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0017_auto_20190507_1113'),
    ]

    operations = [
        migrations.AlterField(
            model_name='company',
            name='name',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=255,
                null=True,
                unique=True,
                verbose_name='Nazwa (pobrana z ILiM)',
            ),
        ),
    ]
