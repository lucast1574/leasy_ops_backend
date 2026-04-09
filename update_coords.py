import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from users.models import City

COORDS = {
    'Lima': (-12.0464, -77.0428),
    'Arequipa': (-16.4090, -71.5375),
    'CDMX': (19.4326, -99.1332),
    'Guadalajara': (20.6597, -103.3496),
    'Monterrey': (25.6866, -100.3161),
}

for name, (lat, lng) in COORDS.items():
    updated = City.objects.filter(name=name).update(latitude=lat, longitude=lng)
    print(f"{'OK' if updated else 'SKIP'}: {name} = ({lat}, {lng})")
