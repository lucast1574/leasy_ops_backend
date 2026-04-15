"""
Management command: seed_districts

Idempotent - seeds District rows for every operational city.
Run after seed_db so countries and cities already exist.
"""
from django.core.management.base import BaseCommand


# =========================================================================
# LIMA  (43 distritos)
# =========================================================================
LIMA_DISTRICTS = [
    ("Ate", -12.0256, -76.9188),
    ("Barranco", -12.1464, -77.0220),
    ("Breña", -12.0586, -77.0536),
    ("Carabayllo", -11.8600, -77.0369),
    ("Cercado de Lima", -12.0464, -77.0428),
    ("Chaclacayo", -11.9792, -76.7675),
    ("Chorrillos", -12.1711, -77.0150),
    ("Cieneguilla", -12.0847, -76.7703),
    ("Comas", -11.9458, -77.0489),
    ("El Agustino", -12.0478, -76.9989),
    ("Independencia", -11.9942, -77.0511),
    ("Jesus Maria", -12.0706, -77.0478),
    ("La Molina", -12.0839, -76.9350),
    ("La Victoria", -12.0694, -77.0200),
    ("Lince", -12.0833, -77.0333),
    ("Los Olivos", -11.9547, -77.0678),
    ("Lurigancho-Chosica", -11.9544, -76.7036),
    ("Lurin", -12.2822, -76.8736),
    ("Magdalena del Mar", -12.0919, -77.0689),
    ("Miraflores", -12.1219, -77.0297),
    ("Pachacamac", -12.2314, -76.8603),
    ("Pucusana", -12.4786, -76.7981),
    ("Pueblo Libre", -12.0747, -77.0622),
    ("Puente Piedra", -11.8631, -77.0781),
    ("Punta Hermosa", -12.3428, -76.8264),
    ("Punta Negra", -12.3697, -76.8022),
    ("Rimac", -12.0286, -77.0369),
    ("San Bartolo", -12.3831, -76.7822),
    ("San Borja", -12.1058, -77.0014),
    ("San Isidro", -12.0978, -77.0369),
    ("San Juan de Lurigancho", -11.9686, -77.0081),
    ("San Juan de Miraflores", -12.1614, -76.9714),
    ("San Luis", -12.0764, -77.0050),
    ("San Martin de Porres", -11.9997, -77.0561),
    ("San Miguel", -12.0778, -77.0900),
    ("Santa Anita", -12.0431, -76.9706),
    ("Santa Maria del Mar", -12.3986, -76.7869),
    ("Santa Rosa", -11.7917, -77.1653),
    ("Santiago de Surco", -12.1461, -76.9919),
    ("Surquillo", -12.1128, -77.0125),
    ("Villa El Salvador", -12.2122, -76.9417),
    ("Villa Maria del Triunfo", -12.1664, -76.9333),
    ("Callao", -12.0567, -77.1181),
    ("Bellavista", -12.0597, -77.0686),
    ("La Perla", -12.0692, -77.1078),
    ("La Punta", -12.0697, -77.1583),
    ("Ventanilla", -11.8764, -77.1286),
    ("Mi Peru", -11.8597, -77.1144),
]

# =========================================================================
# AREQUIPA  (29 distritos)
# =========================================================================
AREQUIPA_DISTRICTS = [
    ("Arequipa (Cercado)", -16.3989, -71.5370),
    ("Alto Selva Alegre", -16.3828, -71.5186),
    ("Cayma", -16.3678, -71.5542),
    ("Cerro Colorado", -16.3678, -71.5814),
    ("Characato", -16.4672, -71.4861),
    ("Chiguata", -16.4044, -71.3953),
    ("Hunter", -16.4550, -71.5533),
    ("Jacobo Hunter", -16.4550, -71.5533),
    ("Jose Luis Bustamante y Rivero", -16.4261, -71.5278),
    ("La Joya", -16.5553, -71.7517),
    ("Mariano Melgar", -16.4039, -71.5103),
    ("Miraflores", -16.4064, -71.5222),
    ("Mollebaya", -16.4636, -71.4608),
    ("Paucarpata", -16.4269, -71.4997),
    ("Sabandía", -16.4558, -71.4733),
    ("Sachaca", -16.4194, -71.5714),
    ("Socabaya", -16.4672, -71.5303),
    ("Tiabaya", -16.4592, -71.5997),
    ("Uchumayo", -16.4228, -71.6658),
    ("Yanahuara", -16.3917, -71.5458),
    ("Yarabamba", -16.5094, -71.4606),
    ("Yura", -16.2506, -71.6842),
]

# =========================================================================
# CDMX  (16 alcaldias)
# =========================================================================
CDMX_DISTRICTS = [
    ("Alvaro Obregon", 19.3572, -99.2064),
    ("Azcapotzalco", 19.4869, -99.1836),
    ("Benito Juarez", 19.3714, -99.1592),
    ("Coyoacan", 19.3467, -99.1617),
    ("Cuajimalpa de Morelos", 19.3583, -99.2983),
    ("Cuauhtemoc", 19.4342, -99.1386),
    ("Gustavo A. Madero", 19.4878, -99.1122),
    ("Iztacalco", 19.3953, -99.0969),
    ("Iztapalapa", 19.3550, -99.0928),
    ("Magdalena Contreras", 19.3322, -99.2453),
    ("Miguel Hidalgo", 19.4325, -99.1928),
    ("Milpa Alta", 19.1928, -99.0228),
    ("Tlahuac", 19.2847, -99.0044),
    ("Tlalpan", 19.2961, -99.1678),
    ("Venustiano Carranza", 19.4433, -99.1089),
    ("Xochimilco", 19.2578, -99.1036),
]

# =========================================================================
# GUADALAJARA  (9 municipios del area metropolitana)
# =========================================================================
GUADALAJARA_DISTRICTS = [
    ("Guadalajara Centro", 20.6736, -103.3438),
    ("Zapopan", 20.7167, -103.3950),
    ("Tlaquepaque", 20.6397, -103.3136),
    ("Tonala", 20.6247, -103.2347),
    ("Tlajomulco de Zuniga", 20.4742, -103.4444),
    ("El Salto", 20.5186, -103.2781),
    ("Ixtlahuacan de los Membrillos", 20.3417, -103.1878),
    ("Juanacatlan", 20.5086, -103.1658),
    ("Zapotlanejo", 20.6228, -103.0647),
]

# =========================================================================
# MONTERREY  (13 municipios del area metropolitana)
# =========================================================================
MONTERREY_DISTRICTS = [
    ("Monterrey Centro", 25.6714, -100.3089),
    ("San Nicolas de los Garza", 25.7461, -100.2983),
    ("Guadalupe", 25.6772, -100.2567),
    ("Apodaca", 25.7828, -100.1864),
    ("San Pedro Garza Garcia", 25.6542, -100.3469),
    ("Santa Catarina", 25.6814, -100.4594),
    ("General Escobedo", 25.7972, -100.3189),
    ("Juarez", 25.6506, -100.0944),
    ("Garcia", 25.8128, -100.5911),
    ("Santiago", 25.4306, -100.1564),
    ("Cadereyta Jimenez", 25.5953, -100.0072),
    ("Cienega de Flores", 25.9556, -100.1667),
    ("Salinas Victoria", 25.9656, -100.2983),
]


DISTRICTS_BY_CITY = {
    'Lima': LIMA_DISTRICTS,
    'Arequipa': AREQUIPA_DISTRICTS,
    'CDMX': CDMX_DISTRICTS,
    'Guadalajara': GUADALAJARA_DISTRICTS,
    'Monterrey': MONTERREY_DISTRICTS,
}


class Command(BaseCommand):
    help = 'Seed districts for all operational cities (idempotent).'

    def handle(self, *args, **options):
        from users.models import City, District

        self.stdout.write(self.style.MIGRATE_HEADING('=== Seeding districts ==='))

        total_created = 0
        total_updated = 0
        total_skipped = 0

        for city_name, districts in DISTRICTS_BY_CITY.items():
            try:
                city = City.objects.get(name=city_name)
            except City.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  SKIP: City "{city_name}" not found. Run seed_db first.'
                ))
                continue

            self.stdout.write(f'\n  {city.name} ({city.country.name}): {len(districts)} districts')

            for name, lat, lng in districts:
                obj, created = District.objects.get_or_create(
                    name=name,
                    city=city,
                    defaults={'latitude': lat, 'longitude': lng},
                )
                if created:
                    total_created += 1
                else:
                    # Update coords if they changed
                    changed = False
                    if abs(obj.latitude - lat) > 0.0001 or abs(obj.longitude - lng) > 0.0001:
                        obj.latitude = lat
                        obj.longitude = lng
                        obj.save(update_fields=['latitude', 'longitude'])
                        total_updated += 1
                        changed = True
                    if not changed:
                        total_skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Done: {total_created} created, {total_updated} updated, {total_skipped} unchanged ==='
        ))
