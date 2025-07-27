# Django settings for agent project.
import os
from pathlib import Path

USE_X_FORWARDED_HOST      = True
SECURE_PROXY_SSL_HEADER   = ('HTTP_X_FORWARDED_PROTO', 'https')

# Canonical redirect URIs – must EXACTLY match what you entered in the
# Google Cloud and Notion dashboards.
DRIVE_REDIRECT_URI  = "https://manuvector.net/connect/drive/callback/"
NOTION_REDIRECT_URI = "https://manuvector.net/api/notion/callback/"
NOTION_CONNECT_REDIRECT_URI = "https://manuvector.net/connect/notion/callback/"


CSRF_TRUSTED_ORIGINS = ["https://manuvector.net", "http://localhost:8000"]
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False          # <-- allow JS to read it
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"


BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = True

ADMINS = (
    # ('Your Name', 'your_email@agent.com'),
)

MANAGERS = ADMINS

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


import dj_database_url
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:                       # production / docker-compose run
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:                                  # image-build time → use a temp SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "tmp_build.db",
        }
    }






# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "America/Chicago"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en"

LANGUAGES = [
    ("ar", "Arabic"),
    ("az", "Azerbaijani"),
    ("bg", "Bulgarian"),
    ("ca", "Catalan"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("de", "German"),
    ("el", "Greek"),
    ("en", "English"),
    ("es", "Spanish"),
    ("et", "Estonian"),
    ("eu", "Basque"),
    ("fa", "Persian"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("he", "Hebrew"),
    ("hr", "Croatian"),
    ("hu", "Hungarian"),
    ("id", "Indonesian"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ka", "Georgian"),
    ("ko", "Korean"),
    ("ky", "Kyrgyz"),
    ("lt", "Lithuanian"),
    ("lv", "Latvian"),
    ("mn", "Mongolian"),
    ("nb", "Norwegian Bokmål"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("sk", "Slovak"),
    ("sl", "Slovenian"),
    ("sr", "Serbian"),
    ("sr-Latn", "Serbian (Latin)"),
    ("sv", "Swedish"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("zh-hans", "Chinese (Simplified)"),
    ("zh-hant", "Chinese (Traditional)"),
]

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ""

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://agent.com/media/"
MEDIA_URL = ""

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/chat/static/"

# Additional locations of static files
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'agent', 'static'),
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "t8_)kj3v!au0!_i56#gre**mkg0&z1df%3bw(#5^#^5e_64!$_"

# List of callables that know how to import templates from various sources.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "agent" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
)



AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # for Django admin
    'allauth.account.auth_backends.AuthenticationBackend',  # for allauth
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'key': ''
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

SOCIALACCOUNT_PROVIDERS["notion"] = {
    "APP": {
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "secret": os.getenv("NOTION_CLIENT_SECRET"),
        "key": "",
    },
    # no default scopes needed
}



ROOT_URLCONF = "agent.urls"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "allauth.socialaccount.providers.dropbox",
    "allauth.socialaccount.providers.dingtalk",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.edx",
    "allauth.socialaccount.providers.evernote",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.linkedin_oauth2",
    "allauth.socialaccount.providers.notion",
    "allauth.socialaccount.providers.mediawiki",
    "allauth.socialaccount.providers.pinterest",
    "allauth.socialaccount.providers.pocket",
    "allauth.socialaccount.providers.reddit",
    "allauth.socialaccount.providers.saml",
    "allauth.socialaccount.providers.shopify",
    "allauth.socialaccount.providers.slack",
    "allauth.socialaccount.providers.snapchat",
    "allauth.socialaccount.providers.soundcloud",
    "allauth.socialaccount.providers.stackexchange",
    "allauth.socialaccount.providers.telegram",
    "allauth.socialaccount.providers.twitch",
    "allauth.socialaccount.providers.twitter",
    "allauth.socialaccount.providers.twitter_oauth2",
    "allauth.socialaccount.providers.vimeo",
    "allauth.socialaccount.providers.vimeo_oauth2",
    "allauth.socialaccount.providers.weibo",
    "allauth.socialaccount.providers.xing",
    "allauth.usersessions",
    "agent.users",
    "agent",
    "pgvector.django",
    "rag"
)


AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 9,
        },
    }
]

ALLOWED_HOSTS = ["*"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_METHODS = {
    "email",
}
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_ADAPTER = "agent.users.allauth.AccountAdapter"
LOGIN_REDIRECT_URL = "/chat"         # After successful login
ACCOUNT_SIGNUP_REDIRECT_URL = "/chat"  # After successful signup
ACCOUNT_LOGOUT_REDIRECT_URL = "/chat"  # Optional: where to go after logout


MFA_SUPPORTED_TYPES = [
    "webauthn",
    "totp",
    "recovery_codes",
]
MFA_PASSKEY_LOGIN_ENABLED = False
MFA_PASSKEY_SIGNUP_ENABLED = False

try:
    from .local_settings import *  # noqa
except ImportError:
    pass
