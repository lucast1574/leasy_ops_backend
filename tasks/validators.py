"""
Geofence validation rules for task assignment.

Rules:
1. Every task MUST have lat/lng coordinates
2. Coordinates MUST fall within an active city geofence
3. The assigned operario MUST belong to the SAME city as the geofence
4. Supervisors can only assign tasks within their OWN country
5. Supervisors can only assign to operarios in cities they supervise
6. Admins can assign within any city of any country, but still must match operario↔city
"""
from .models import CityGeofence


class TaskValidationError(Exception):
    pass


def validate_task_location(latitude, longitude, required=True):
    """
    Validate that the coordinates fall within an active geofence.
    Returns the CityGeofence if valid, raises TaskValidationError otherwise.
    """
    if latitude is None or longitude is None:
        if required:
            raise TaskValidationError(
                'Latitud y longitud son obligatorios. Toda tarea debe tener ubicación.'
            )
        return None

    try:
        lat = float(latitude)
        lng = float(longitude)
    except (ValueError, TypeError):
        raise TaskValidationError('Coordenadas inválidas.')

    geofence = CityGeofence.find_geofence(lat, lng)
    if geofence is None:
        raise TaskValidationError(
            'La ubicación no está dentro de ninguna zona operativa de Leasy. '
            'Las ciudades operativas son: Lima, Arequipa (Perú) y CDMX, Guadalajara, Monterrey (México).'
        )

    return geofence


def validate_task_assignment(assigner, operario, geofence):
    """
    Validate that the assigner can assign a task to the operario in the given geofence.

    Rules:
    - Operario must belong to the same city as the geofence
    - Supervisor: can only assign within their own country
    - Admin: can assign in any country, but operario must still match the geofence city
    """
    if geofence is None:
        # If no geofence (e.g. Conversion task), we just check basic assignment rules.
        # Supervisor can only assign to operarios in their same country.
        is_admin = assigner.has_perm_code('manage_all_roles')
        if not is_admin:
            if assigner.country_id != operario.country_id:
                raise TaskValidationError(
                    f'No puedes asignar tareas a operarios de otro país. '
                    f'Tu país es {assigner.country.name if assigner.country else "—"} '
                    f'y el operario es de {operario.country.name if operario.country else "—"}.'
                )
            
            # Check if supervisor has the operario assigned
            from users.models import SupervisorAssignment
            has_assignment = SupervisorAssignment.objects.filter(
                supervisor=assigner,
                operario=operario,
            ).exists()
            if not has_assignment:
                raise TaskValidationError(
                    f'No tienes asignado al operario {operario.first_name} {operario.last_name}.'
                )
        return

    geofence_city = geofence.city
    geofence_country = geofence_city.country

    # 1. Operario must be in the same city as the task geofence
    if operario.city_id != geofence_city.id:
        raise TaskValidationError(
            f'El operario {operario.first_name} {operario.last_name} pertenece a '
            f'{operario.city.name if operario.city else "ninguna ciudad"}, '
            f'pero la tarea está en {geofence_city.name}. '
            f'Solo puedes asignar tareas a operarios de la misma ciudad.'
        )

    # 2. Check assigner permissions
    is_admin = assigner.has_perm_code('manage_all_roles')

    if not is_admin:
        # Supervisor rules
        # a) Supervisor must be in the same country as the geofence
        if assigner.country_id != geofence_country.id:
            raise TaskValidationError(
                f'No puedes crear tareas en {geofence_country.name}. '
                f'Solo puedes operar en tu propio país ({assigner.country.name if assigner.country else "—"}).'
            )

        # b) Supervisor must have the operario assigned (same city or adopted)
        from users.models import SupervisorAssignment
        has_assignment = SupervisorAssignment.objects.filter(
            supervisor=assigner,
            operario=operario,
        ).exists()

        if not has_assignment:
            raise TaskValidationError(
                f'No tienes asignado al operario {operario.first_name} {operario.last_name}. '
                f'Solo puedes asignar tareas a operarios bajo tu supervisión.'
            )

    else:
        # Admin rules: can assign across countries,
        # but operario must still match the geofence city (rule 1 above handles this)
        pass


def validate_task_reassignment(assigner, new_operario, task):
    """
    Validate reassignment: same rules as assignment but uses existing task geofence.
    """
    if task.city_geofence is None:
        # Legacy task without geofence, just check country
        if assigner.country_id and new_operario.country_id:
            if not assigner.has_perm_code('manage_all_roles'):
                if assigner.country_id != new_operario.country_id:
                    raise TaskValidationError(
                        'No puedes reasignar a un operario de otro país.'
                    )
        return

    validate_task_assignment(assigner, new_operario, task.city_geofence)
