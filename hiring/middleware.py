# hiring/middleware.py
import time
from django.http import JsonResponse

class PWAThrottleMiddleware:
    """Middleware to prevent rate limiting on PWA files"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.last_request_time = {}
        
    def __call__(self, request):
        # Skip throttling for PWA files
        if request.path in ['/manifest.json', '/sw.js'] or request.path.startswith('/static/'):
            # Add header to indicate this is a PWA request
            request._is_pwa = True
            request.META['HTTP_CACHE_CONTROL'] = 'max-age=86400'
            
            # Rate limit check - allow more requests for PWA
            ip = self.get_client_ip(request)
            current_time = time.time()
            
            if ip in self.last_request_time:
                time_diff = current_time - self.last_request_time[ip]
                if time_diff < 0.1:  # Allow 10 requests per second
                    # Still process but don't block
                    pass
            
            self.last_request_time[ip] = current_time
            
        response = self.get_response(request)
        
        # Add cache headers to response
        if request.path in ['/manifest.json', '/sw.js']:
            response['Cache-Control'] = 'public, max-age=86400, immutable'
            response['Access-Control-Allow-Origin'] = '*'
            
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip