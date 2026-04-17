"""
Read-only query helpers for the ``tasks`` app.

Centralises "who can see which tasks" logic that used to be duplicated
in ``backoffice_tasks`` and ``dashboard_metrics``, plus small pure
helpers that are tedious to re-derive inline.

These helpers never mutate state — they just return querysets or values.
"""
from .models import Task


def visible_tasks_for(user):
    """
    Return the base Task queryset that ``user`` is allowed to see in the
    backoffice / dashboard.

    - Admins (``manage_all_roles``)          → all tasks
    - Supervisors (``backoffice_access``)    → tasks assigned to their
      ``SupervisorAssignment`` operarios
    - Anyone else                            → empty queryset

    Callers are expected to have already checked ``backoffice_access``
    permission and returned 403 if missing — this helper only narrows the
    queryset; it does not enforce access.
    """
    if user.has_perm_code('manage_all_roles'):
        return Task.objects.all()

    # Lazy import to avoid circular deps (users depends on nothing here,
    # but tasks.models → users.models already is the chain).
    from users.models import SupervisorAssignment

    operario_ids = list(
        SupervisorAssignment.objects.filter(
            supervisor=user
        ).values_list('operario_id', flat=True)
    )
    return Task.objects.filter(assigned_to_id__in=operario_ids)


def build_maps_link(latitude, longitude, provided_link: str = '') -> str:
    """
    Return a Google Maps URL for the given coordinates, preferring any
    link the caller explicitly provided (non-empty strings only).
    """
    if provided_link:
        return provided_link
    return f'https://www.google.com/maps?q={latitude},{longitude}'
