# agent/urls.py
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView

from allauth.account.decorators import secure_admin_login

from agent.views import *
from rag.views import list_files, search_similar   # ingest_document removed

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html")),
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("allauth.idp.urls")),

    # Core chat + search
    path("api/chat",   chat_completion, name="chat_completion"),
    path("api/files",  list_files,      name="list_files"),
    path("api/search", search_similar,  name="search_similar"),

    # Google Drive OAuth + Picker helpers
    path("connect/drive/",            drive_connect,   name="drive_connect"),
    path("connect/drive/callback/",   drive_callback,  name="drive_callback"),
    path("api/drive/token",           drive_token,     name="drive_token"),
    path("api/drive/files",           store_selected_files, name="store_selected_files"),
]

