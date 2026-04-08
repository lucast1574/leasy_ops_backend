"""
Management command: seed_db

Idempotent — safe to run multiple times.
Creates countries, cities, permissions, roles, and the admin user.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


COUNTRIES = [
    {'name': 'Peru', 'code': 'PE', 'domain_suffix': 'leasyauto.com'},
    {'name': 'Mexico', 'code': 'MX', 'domain_suffix': 'floty.mx'},
]

CITIES = {
    'PE': ['Lima', 'Arequipa'],
    'MX': ['CDMX', 'Guadalajara', 'Monterrey'],
}

PERMISSIONS = [
    {'codename': 'backoffice_access', 'description': 'Can access the backoffice panel'},
    {'codename': 'mobile_access', 'description': 'Can access the mobile app'},
    {'codename': 'manage_users', 'description': 'Can list and manage users'},
    {'codename': 'assign_operario_role', 'description': 'Can assign the operario role to users'},
    {'codename': 'assign_supervisor_role', 'description': 'Can assign the supervisor role to users'},
    {'codename': 'manage_all_roles', 'description': 'Can assign any role to users'},
]

ROLES = {
    'admin': {
        'description': 'Administrator - full access',
        'permissions': [
            'backoffice_access', 'mobile_access', 'manage_users',
            'assign_operario_role', 'assign_supervisor_role', 'manage_all_roles'
        ],
    },
    'supervisor': {
        'description': 'Supervisor - manages operarios',
        'permissions': [
            'backoffice_access', 'mobile_access', 'manage_users', 'assign_operario_role'
        ],
    },
    'operario': {
        'description': 'Operario - mobile access only',
        'permissions': ['mobile_access'],
    },
}

ADMIN_USER = {
    'email': 'lsantillan@leasyauto.com',
    'username': 'lsantillan',
    'first_name': 'Luis',
    'last_name': 'Santillan',
    'country_code': 'PE',
    'city_name': 'Lima',
    'role_name': 'admin',
}


class Command(BaseCommand):
    help = 'Seed the database with initial data (idempotent).'

    def handle(self, *args, **options):
        from users.models import Country, City, Permission, Role, RolePermission

        self.stdout.write(self.style.MIGRATE_HEADING('=== Seeding database ==='))

        # --- Countries ---
        country_map = {}
        for c in COUNTRIES:
            obj, created = Country.objects.get_or_create(
                code=c['code'],
                defaults={'name': c['name'], 'domain_suffix': c['domain_suffix']}
            )
            country_map[c['code']] = obj
            status = 'OK Created' if created else '  Exists'
            self.stdout.write(f"{status}: Country {obj.name}")

        # --- Cities ---
        city_map = {}
        for country_code, city_names in CITIES.items():
            country = country_map[country_code]
            for city_name in city_names:
                obj, created = City.objects.get_or_create(
                    name=city_name,
                    country=country
                )
                city_map[city_name] = obj
                status = 'OK Created' if created else '  Exists'
                self.stdout.write(f"{status}: City {obj.name} ({country.name})")

        # --- Permissions ---
        perm_map = {}
        for p in PERMISSIONS:
            obj, created = Permission.objects.get_or_create(
                codename=p['codename'],
                defaults={'description': p['description']}
            )
            perm_map[p['codename']] = obj
            status = 'OK Created' if created else '  Exists'
            self.stdout.write(f"{status}: Permission {obj.codename}")

        # --- Roles ---
        role_map = {}
        for role_name, role_data in ROLES.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={'description': role_data['description']}
            )
            role_map[role_name] = role
            status = 'OK Created' if created else '  Exists'
            self.stdout.write(f"{status}: Role {role.name}")

            for perm_codename in role_data['permissions']:
                perm = perm_map[perm_codename]
                rp, rp_created = RolePermission.objects.get_or_create(
                    role=role, permission=perm
                )
                if rp_created:
                    self.stdout.write(f"    + Assigned permission: {perm_codename}")

        # --- Admin user ---
        admin_country = country_map[ADMIN_USER['country_code']]
        admin_city = city_map[ADMIN_USER['city_name']]
        admin_role = role_map[ADMIN_USER['role_name']]

        user, created = User.objects.get_or_create(
            email=ADMIN_USER['email'],
            defaults={
                'username': ADMIN_USER['username'],
                'first_name': ADMIN_USER['first_name'],
                'last_name': ADMIN_USER['last_name'],
                'country': admin_country,
                'city': admin_city,
                'role': admin_role,
                'is_approved': True,
                'is_staff': True,
                'is_superuser': True,
                'registered_from': 'backoffice',
            }
        )
        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(f'OK Created admin user: {user.email}'))
        else:
            # Ensure existing admin has correct flags
            changed = False
            for field, value in [
                ('is_staff', True), ('is_superuser', True), ('is_approved', True),
                ('role', admin_role), ('country', admin_country), ('city', admin_city),
            ]:
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if changed:
                user.save()
                self.stdout.write(f'  Updated admin user: {user.email}')
            else:
                self.stdout.write(f'  Exists: Admin user {user.email}')

        self.stdout.write(self.style.SUCCESS('=== Seeding complete ==='))
