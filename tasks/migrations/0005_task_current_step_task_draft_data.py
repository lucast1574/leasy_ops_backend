from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_task_google_maps_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='current_step',
            field=models.PositiveSmallIntegerField(default=0, help_text='Last completed step index in the mobile app flow'),
        ),
        migrations.AddField(
            model_name='task',
            name='draft_data',
            field=models.JSONField(blank=True, default=dict, help_text='Partially filled form data before final submission'),
        ),
    ]
