from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def run_seeder():
    """
    Main entry point for database seeding.
    Calls specific seeder functions to populate the DB.
    """
    logger.info("Starting database seeding...")
    try:
        with transaction.atomic():
            ensure_roles_exist()
            # Add more seeding logic as needed (e.g., set up initial categories, areas, etc.)
        logger.info("Database seeding completed successfully.")
    except Exception as e:
        logger.error(f"Error during database seeding: {str(e)}")
        raise

def ensure_roles_exist():
    """
    Ensures that the basic roles exist in the database.
    Roles: admin, supervisor, motorizado
    """
    from apps.users.models import Role # lazy import to avoid app-not-ready issues
    
    roles = [
        ('admin', 'Administrador del sistema con acceso total'),
        ('supervisor', 'Supervisor de operaciones de campo'),
        ('motorizado', 'Usuario motorizado de campo (operativo)'),
    ]
    
    for role_name, description in roles:
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={'description': description}
        )
        if created:
            logger.info(f"Created role: {role_name}")
        else:
            # Update description if it changed
            if role.description != description:
                role.description = description
                role.save()
                logger.info(f"Updated role description: {role_name}")
                
    # Create default Admin if not exists
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    admin_role = Role.objects.get(name='admin')
    
    if not User.objects.filter(username='admin').exists():
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@leasyauto.com',
            password='admin-password-123', # Change this in production
            first_name='Admin',
            last_name='Sist'
        )
        admin_user.role = admin_role
        admin_user.plain_password = 'admin-password-123'
        admin_user.save()
        logger.info("Created default admin user: admin")
    else:
        logger.info("Admin user already exists.")
