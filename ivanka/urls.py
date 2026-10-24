# ivanka/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
import os

from hiring import views as hiring_views


def assetlinks(request):
    path = os.path.join(settings.BASE_DIR, "assetlinks.json")
    if not os.path.exists(path):
        raise Http404("assetlinks.json not found")
    return FileResponse(open(path, "rb"), content_type="application/json")


urlpatterns = [
    # ============================================================
    # PWA — root scope (must come first)
    # ============================================================
    path('manifest.json', hiring_views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', hiring_views.pwa_sw, name='pwa_sw'),
    path('serviceworker.js', hiring_views.pwa_sw, name='pwa_sw_alias'),
    path('offline/', hiring_views.offline_page, name='offline_page'),
    path(".well-known/assetlinks.json", assetlinks),

    # ============================================================
    # Django admin
    # ============================================================
    path('admin/', admin.site.urls),

    # ============================================================
    # ✅ STORE AT ROOT — "/" lands here
    # ============================================================
    path('', include('store.urls')),

    # ============================================================
    # ✅ HIRING AT /hiring/ — never touches "/"
    # ============================================================
    path('hiring/', include('hiring.urls')),

    # ============================================================
    # Push (root-scoped)
    # ============================================================
    path('api/push/subscribe/', hiring_views.save_push_subscription,
         name='save_push_subscription'),
    path('api/push/test/', hiring_views.send_test_notification,
         name='send_test_notification'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)