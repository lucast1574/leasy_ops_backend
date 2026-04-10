"""
Management command: rebuild_assignments

Rebuilds all SupervisorAssignment rows based on current user data.
- Auto-assigns all operarios in a city to all supervisors in that city.
- Preserves existing adopted (cross-city) assignments if still valid.
- Removes stale assignments (cross-country, deleted users, etc.).

Safe to run multiple times.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Rebuild supervisor-operario assignments based on current city data.'

    def handle(self, *args, **options):
        from users.models import SupervisorAssignment

        self.stdout.write(self.style.MIGRATE_HEADING('=== Rebuilding supervisor assignments ==='))

        # Remove stale cross-country adopted assignments
        for a in SupervisorAssignment.objects.filter(is_adopted=True).select_related(
            'supervisor__country', 'operario__country'
        ):
            if a.supervisor.country_id != a.operario.country_id:
                self.stdout.write(f'  Removing stale cross-country: {a}')
                a.delete()

        # Remove auto-assignments where city no longer matches
        for a in SupervisorAssignment.objects.filter(is_adopted=False).select_related(
            'supervisor', 'operario'
        ):
            if a.supervisor.city_id != a.operario.city_id:
                self.stdout.write(f'  Removing stale auto-assignment: {a}')
                a.delete()

        # Create auto-assignments
        supervisors = User.objects.filter(
            role__name='supervisor', is_approved=True, city__isnull=False
        ).select_related('city')

        created_count = 0
        for sup in supervisors:
            operarios = User.objects.filter(
                role__name='operario', city=sup.city, is_approved=True
            )
            for op in operarios:
                _, created = SupervisorAssignment.objects.get_or_create(
                    supervisor=sup,
                    operario=op,
                    defaults={'is_adopted': False},
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'=== Done. Created {created_count} new auto-assignments ==='
        ))
