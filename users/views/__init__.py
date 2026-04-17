"""
users.views package.

Split from the old monolithic `users/views.py` (806 lines) into domain modules:

    auth       — Google OAuth login + account status check
    users      — self-service + backoffice user management
    location   — live GPS upsert + nearest-city snap
    tracking   — live locations + supervisor-assignment management
    catalogs   — public countries/cities/districts/roles

Private modules:
    _google_oauth — Google token/code exchange helpers
    _assignments  — SupervisorAssignment rebuild helpers

All public view callables are re-exported here so existing `from users.views
import ...` imports (notably `users/urls.py`) keep working with no changes.
"""

# Auth
from .auth import google_auth, check_user_status

# Users (self-service + backoffice)
from .users import me, update_user_city, list_users, assign_role, update_user

# Location (live GPS)
from .location import set_location

# Tracking / supervisor assignments
from .tracking import (
    tracking_locations,
    my_assignments,
    adoptable_operarios,
    adopt_operario,
    release_operario,
)

# Public catalogs
from .catalogs import list_countries, list_cities, list_districts, list_roles

__all__ = [
    # auth
    'google_auth', 'check_user_status',
    # users
    'me', 'update_user_city', 'list_users', 'assign_role', 'update_user',
    # location
    'set_location',
    # tracking
    'tracking_locations', 'my_assignments', 'adoptable_operarios',
    'adopt_operario', 'release_operario',
    # catalogs
    'list_countries', 'list_cities', 'list_districts', 'list_roles',
]
