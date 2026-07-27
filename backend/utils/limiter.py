from slowapi import Limiter
from slowapi.util import get_remote_address
from decouple import config

def get_client_ip(request):
    """Get the real client IP, respecting X-Forwarded-For from reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For may contain multiple IPs; the first is the original client
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip)
