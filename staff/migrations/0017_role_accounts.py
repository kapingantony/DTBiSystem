from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('staff', '0016_alter_dataimportbatch_dataset'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='mentor',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mentor_record', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='investor',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='investor_record', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='user_type',
            field=models.CharField(choices=[('admin', 'Admin'), ('staff', 'Staff'), ('mentor', 'Mentor'), ('investor', 'Investor'), ('individual', 'Individual Startup'), ('public', 'Public Startup')], default='public', max_length=20),
        ),
    ]
