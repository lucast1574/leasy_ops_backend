from django.urls import path
from .views import (
    my_tasks, task_detail, start_task,
    request_upload_url, confirm_upload, submit_task, reschedule_task,
    backoffice_tasks, backoffice_create_task, backoffice_update_task, backoffice_delete_task,
    list_task_types,
)

urlpatterns = [
    # Mobile (operario)
    path('', my_tasks, name='my-tasks'),
    path('<int:task_id>/', task_detail, name='task-detail'),
    path('<int:task_id>/start/', start_task, name='start-task'),
    path('<int:task_id>/photos/request-url/', request_upload_url, name='request-upload-url'),
    path('<int:task_id>/photos/confirm/', confirm_upload, name='confirm-upload'),
    path('<int:task_id>/submit/', submit_task, name='submit-task'),
    path('<int:task_id>/reschedule/', reschedule_task, name='reschedule-task'),

    # Backoffice (supervisor / admin)
    path('backoffice/', backoffice_tasks, name='backoffice-tasks'),
    path('backoffice/create/', backoffice_create_task, name='backoffice-create-task'),
    path('backoffice/<int:task_id>/', backoffice_update_task, name='backoffice-update-task'),
    path('backoffice/<int:task_id>/delete/', backoffice_delete_task, name='backoffice-delete-task'),

    # Catalogs
    path('types/', list_task_types, name='list-task-types'),
]
