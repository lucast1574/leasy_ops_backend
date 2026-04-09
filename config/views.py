import time
import socket
import requests
from django.http import JsonResponse

def health_check(request):
    """
    Endpoint de health check para AWS ECS / Application Load Balancer
    Retorna 200 OK inmediatamente.
    """
    return JsonResponse({"status": "ok", "message": "Backend is running"})

def debug_network(request):
    """Temporary debug endpoint to test outbound connectivity."""
    results = {}
    
    # Test DNS
    try:
        t0 = time.time()
        ip = socket.getaddrinfo('oauth2.googleapis.com', 443)
        results['dns'] = {'ok': True, 'ip': str(ip[0][4]), 'ms': round((time.time()-t0)*1000)}
    except Exception as e:
        results['dns'] = {'ok': False, 'error': str(e)}
    
    # Test HTTPS GET
    try:
        t0 = time.time()
        r = requests.get('https://oauth2.googleapis.com/.well-known/openid-configuration', timeout=10)
        results['https_get'] = {'ok': True, 'status': r.status_code, 'ms': round((time.time()-t0)*1000)}
    except Exception as e:
        results['https_get'] = {'ok': False, 'error': str(e)}
    
    # Test HTTPS POST (token endpoint with dummy data)
    try:
        t0 = time.time()
        r = requests.post('https://oauth2.googleapis.com/token', data={'grant_type':'test'}, timeout=10)
        results['https_post'] = {'ok': True, 'status': r.status_code, 'ms': round((time.time()-t0)*1000), 'body': r.text[:200]}
    except Exception as e:
        results['https_post'] = {'ok': False, 'error': str(e)}
    
    return JsonResponse(results)

def debug_db(request):
    """Test database connectivity."""
    import time
    from django.db import connection
    try:
        t0 = time.time()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            row = cursor.fetchone()
        return JsonResponse({'ok': True, 'result': row[0], 'ms': round((time.time()-t0)*1000)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)