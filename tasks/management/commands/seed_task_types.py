from django.core.management.base import BaseCommand
from tasks.models import TaskType


class Command(BaseCommand):
    help = 'Seed the 8 task types'

    def handle(self, *args, **options):
        types = [
            {'slug': 'verificacion', 'name': 'Verificación', 'icon': 'check.svg'},
            {'slug': 'recupero', 'name': 'Recupero', 'icon': 'car.svg'},
            {'slug': 'entrega', 'name': 'Entrega unidad', 'icon': 'entrega.svg'},
            {'slug': 'conversion', 'name': 'Conversión', 'icon': 'GasPump.svg'},
            {'slug': 'traslado', 'name': 'Traslado', 'icon': 'traslado.svg'},
            {'slug': 'verificar_vehiculo', 'name': 'Verificar Vehículo', 'icon': 'verificar.svg'},
            {'slug': 'notaria', 'name': 'Notaría', 'icon': 'notaria.svg'},
            {'slug': 'gestiones', 'name': 'Gestiones/Otros', 'icon': 'gestiones.svg'},
        ]

        for t in types:
            obj, created = TaskType.objects.update_or_create(
                slug=t['slug'],
                defaults={'name': t['name'], 'icon': t['icon']},
            )
            status = 'CREATED' if created else 'EXISTS'
            self.stdout.write(f'  {status}: {obj.name} ({obj.slug})')

        self.stdout.write(self.style.SUCCESS(f'Done. {TaskType.objects.count()} task types.'))
