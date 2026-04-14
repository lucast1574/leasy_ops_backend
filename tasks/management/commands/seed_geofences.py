from django.core.management.base import BaseCommand
from tasks.models import CityGeofence
from users.models import City


# Large radii to cover suburban/rural areas (taxi drivers live far out)
GEOFENCE_CONFIG = {
    'Lima': {'radius_km': 80},           # Covers Cañete, Huaral, etc.
    'Arequipa': {'radius_km': 60},       # Covers surrounding valleys
    'CDMX': {'radius_km': 100},          # Huge metro area + Estado de México
    'Guadalajara': {'radius_km': 70},    # Covers Zapopan, Tlaquepaque, etc.
    'Monterrey': {'radius_km': 70},      # Covers García, Escobedo, etc.
}


class Command(BaseCommand):
    help = 'Create geofences for all operational cities'

    def handle(self, *args, **options):
        cities = City.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        )

        for city in cities:
            config = GEOFENCE_CONFIG.get(city.name, {'radius_km': 60})
            gf, created = CityGeofence.objects.update_or_create(
                city=city,
                defaults={
                    'center_latitude': city.latitude,
                    'center_longitude': city.longitude,
                    'radius_km': config['radius_km'],
                    'is_active': True,
                },
            )
            status = 'CREATED' if created else 'UPDATED'
            self.stdout.write(f'  {status}: {city.name} ({gf.radius_km}km radius)')

        self.stdout.write(self.style.SUCCESS(
            f'Done. {CityGeofence.objects.count()} geofences active.'
        ))
