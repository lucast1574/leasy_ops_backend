from django.http import JsonResponse

def health_check(request):
    """
    Endpoint de health check para AWS ECS / Application Load Balancer
    Retorna 200 OK inmediatamente.
    """
    return JsonResponse({"status": "ok", "message": "Backend is running"})
