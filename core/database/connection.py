from django.db import connections
from django.db.utils import OperationalError
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Service to manage database interactions and health checks.
    Acts as a central 'endpoint' for database management within the core.
    """
    
    @staticmethod
    def check_health():
        """
        Verifies if the database is reachable.
        Returns True if healthy, False otherwise.
        """
        db_conn = connections['default']
        try:
            db_conn.cursor()
        except OperationalError:
            logger.error("Database health check failed: Connection unavailable.")
            return False
        else:
            return True

    @staticmethod
    def get_connection_info():
        """
        Returns basic info about the current database connection (safe for logs).
        """
        from django.conf import settings
        db_config = settings.DATABASES['default']
        return {
            'engine': db_config.get('ENGINE'),
            'host': db_config.get('HOST'),
            'name': db_config.get('NAME'),
        }

# Singleton instance to be used throughout the app
db_service = DatabaseService()
