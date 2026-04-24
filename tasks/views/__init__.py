"""
tasks.views package.

Split from the old monolithic ``tasks/views.py`` (609 lines) into domain
modules, mirroring the same pattern used in ``users/views/``:

    mobile     — operario endpoints (Flutter app)
    backoffice — supervisor / admin CRUD
    dashboard  — metrics & analytics
    catalogs   — public task-type listing

All public view callables are re-exported here so existing imports like
``from tasks.views import ...`` (notably ``tasks/urls.py``) keep working
with no changes.
"""

from .mobile import (
    my_tasks, task_detail, start_task, update_progress,
    request_upload_url, confirm_upload, submit_task, reschedule_task,
)
from .backoffice import (
    backoffice_tasks, backoffice_create_task, backoffice_task_detail,
    backoffice_reassign_task, backoffice_delete_task,
)
from .dashboard import dashboard_metrics
from .catalogs import list_task_types

__all__ = [
    # mobile
    'my_tasks', 'task_detail', 'start_task', 'update_progress',
    'request_upload_url', 'confirm_upload', 'submit_task', 'reschedule_task',
    # backoffice
    'backoffice_tasks', 'backoffice_create_task', 'backoffice_task_detail',
    'backoffice_reassign_task', 'backoffice_delete_task',
    # dashboard
    'dashboard_metrics',
    # catalogs
    'list_task_types',
]
