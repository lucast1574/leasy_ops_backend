from django.apps import AppConfig
from django.db.models.signals import post_migrate

class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"

    def ready(self):
        # We hook into post_migrate to ensure roles exist
        post_migrate.connect(self._run_seeding, sender=self)

    def _run_seeding(self, **kwargs):
        from core.database.seed import run_seeder
        try:
            run_seeder()
        except Exception:
            # We fail silently if migrations are NOT yet completed or tables DON'T exist
            # though in a more strict environment, we could log this.
            pass
