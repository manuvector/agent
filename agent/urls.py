"""
agent/urls.py – routes
Only change: notion_connect path is now /api/notion/connect (was /connect/notion/)
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView
from allauth.account.decorators import secure_admin_login

from agent.views import (
    index_with_csrf, get_csrf_token, chat_completion,
    drive_connect, drive_callback, drive_token, store_selected_files,
    notion_connect, notion_callback, notion_token, notion_pages, store_notion_pages,
)
from rag.views import list_files, search_similar

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    # SPA entry
    path("", index_with_csrf, name="spa-index"),

    # User auth / templates
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("privacy-policy/", TemplateView.as_view(template_name="privacy_policy.html"), name="privacy-policy"),
    path("terms-of-use/",   TemplateView.as_view(template_name="terms_of_use.html"),   name="terms-of-use"),

    # Admin
    path("admin/", admin.site.urls),

    # i18n passthrough
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("allauth.idp.urls")),

    # CSRF helper
    path("api/csrf", get_csrf_token, name="get_csrf_token"),

    # Chat + RAG
    path("api/chat",   chat_completion, name="chat_completion"),
    path("api/files",  list_files,      name="list_files"),
    path("api/search", search_similar,  name="search_similar"),

    # Google Drive
    path("connect/drive/",            drive_connect,        name="drive_connect"),
    path("connect/drive/callback/",   drive_callback,       name="drive_callback"),
    path("api/drive/token",           drive_token,          name="drive_token"),
    path("api/drive/files",           store_selected_files, name="store_selected_files"),

    # Notion OAuth (fixed)
    path("api/notion/connect",   notion_connect,   name="notion_connect"),
    path("api/notion/callback/", notion_callback,  name="notion_callback"),
    path("api/notion/token",     notion_token,     name="notion_token"),
    path("api/notion/pages",     notion_pages,     name="notion_pages"),
    path("api/notion/files",     store_notion_pages, name="notion_files"),
]

urlpatterns += [
    path("connect/notion/",          notion_connect,   name="notion_connect"),
    path("connect/notion/callback/", notion_callback,  name="notion_callback"),
]

