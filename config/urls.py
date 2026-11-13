"""Top-level URL table: maps URL prefixes to apps."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

admin.site.site_header = "Family Tree"
admin.site.site_title = "Family Tree admin"
admin.site.index_title = "Data entry"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Phase 1 only: the home page does not exist yet, so send "/" to the admin.
    # Phase 2 replaces this line with the tree page.
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
]

# In development, let Django serve uploaded photos from MEDIA_ROOT.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
