# main/migrations/0002_add_address_to_profile.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='address',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
    ]
