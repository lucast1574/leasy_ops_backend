from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_city_latitude_city_longitude'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='location', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['updated_at'], name='users_userl_updated_a3d5f7_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='SupervisorAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_adopted', models.BooleanField(default=False, help_text='True when the supervisor manually adopted this operario from another city in the same country.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('operario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='supervisor_assignments', to=settings.AUTH_USER_MODEL)),
                ('supervisor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='supervised_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('supervisor', 'operario')},
            },
        ),
    ]
