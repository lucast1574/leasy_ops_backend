"""
Internal helpers for SupervisorAssignment bookkeeping.

These are used by several views (auth, users, location) when a user's role
or city changes and assignments need to be rebuilt.

Extracted from the old monolithic users/views.py; logic is byte-identical.
The leading underscore is kept so callers remember this is internal /
package-private API (the module name also starts with '_').
"""
from django.contrib.auth import get_user_model

from ..models import SupervisorAssignment

User = get_user_model()


def _auto_assign_supervisors(operario):
    """
    Auto-assign all supervisors in the operario's city to this operario.
    Called when a new operario registers or changes city.
    """
    if not operario.city:
        return

    supervisors = User.objects.filter(
        role__name='supervisor',
        city=operario.city,
        is_approved=True,
    )
    for sup in supervisors:
        SupervisorAssignment.objects.get_or_create(
            supervisor=sup,
            operario=operario,
            defaults={'is_adopted': False},
        )


def _auto_assign_operarios(supervisor):
    """
    Auto-assign all operarios in the supervisor's city to this supervisor.
    Called when a user becomes a supervisor or changes city.
    """
    if not supervisor.city:
        return

    operarios = User.objects.filter(
        role__name='operario',
        city=supervisor.city,
        is_approved=True,
    )
    for op in operarios:
        SupervisorAssignment.objects.get_or_create(
            supervisor=supervisor,
            operario=op,
            defaults={'is_adopted': False},
        )


def _rebuild_assignments_for_user(user, old_role_name):
    """
    Rebuild SupervisorAssignment rows when a user's role or city changes.
    """
    role_name = user.role.name if user.role else None

    if old_role_name == 'operario' and role_name != 'operario':
        # Was operario, no longer → remove all assignments where they are the operario
        SupervisorAssignment.objects.filter(operario=user).delete()

    if old_role_name == 'supervisor' and role_name != 'supervisor':
        # Was supervisor, no longer → remove all assignments where they are supervisor
        SupervisorAssignment.objects.filter(supervisor=user).delete()

    if role_name == 'operario':
        # Remove old auto-assignments (keep adopted ones)
        SupervisorAssignment.objects.filter(operario=user, is_adopted=False).delete()
        # Re-create auto-assignments for new city
        _auto_assign_supervisors(user)

    if role_name == 'supervisor':
        # Remove old auto-assignments (keep adopted ones within same country)
        SupervisorAssignment.objects.filter(supervisor=user, is_adopted=False).delete()
        # Remove adopted ones from other countries (safety)
        if user.country:
            SupervisorAssignment.objects.filter(
                supervisor=user, is_adopted=True
            ).exclude(operario__country=user.country).delete()
        # Re-create auto-assignments for new city
        _auto_assign_operarios(user)
