from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView

from allauth.account.decorators import secure_admin_login

from agent.views import chat_completion

from rag.views import ingest_document, list_files, search_similar

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html")),
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("allauth.idp.urls")),
    path("api/chat", chat_completion, name="chat_completion"),
    path("api/ingest", ingest_document, name="ingest_document"),
    path("api/files",   list_files,    name="list_files"),
    path("api/search",  search_similar, name="search_similar"),
]

