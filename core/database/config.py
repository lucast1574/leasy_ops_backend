from core.config.env import env

def get_database_config():
    """
    Returns the database configuration for Django.
    Centrally manages database connection settings.
    """
    db_config = env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
    
    # Apply SSL configuration if provided
    ssl_mode = env('DB_SSLMODE', default=None)
    ssl_root_cert = env('DB_SSLROOTCERT', default=None)
    
    if db_config.get('ENGINE') == 'django.db.backends.postgresql':
        if 'OPTIONS' not in db_config:
            db_config['OPTIONS'] = {}
            
        if ssl_mode:
            db_config['OPTIONS']['sslmode'] = ssl_mode
        
        if ssl_root_cert:
            import os
            from core.config.env import BASE_DIR
            cert_path = os.path.join(BASE_DIR, ssl_root_cert)
            if os.path.exists(cert_path):
                db_config['OPTIONS']['sslrootcert'] = cert_path

    return {
        'default': db_config
    }

# Production standards: define persistent connections to improve performance
# by reusing connections across requests.
def get_production_database_config():
    config = get_database_config()
    # CONN_MAX_AGE: The number of seconds a database connection should stay open.
    # A value of 0 means the connection is closed after each request.
    # 60 seconds is a common production value.
    config['default']['CONN_MAX_AGE'] = 60
    return config
