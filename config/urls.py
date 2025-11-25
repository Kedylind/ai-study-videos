from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("web.urls")),
]

# Serve static and media files
if settings.DEBUG:
    # In DEBUG mode, use staticfiles_urlpatterns() to serve static files
    # This automatically finds files from all app 'static' directories
    urlpatterns += staticfiles_urlpatterns()
    # Serve media files explicitly
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # In production, static files are handled by WhiteNoise middleware
    # Serve media files through Django (for Railway)
    # Note: For large-scale deployments, consider using a CDN or object storage
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
            'show_indexes': False,
        }),
    ]
