import os

import json

from pathlib import Path



from dotenv import load_dotenv

import dj_database_url

from decouple import config

from google.oauth2 import service_account





# ============================================================

# LOAD ENVIRONMENT

# ============================================================



load_dotenv()



BASE_DIR = Path(__file__).resolve().parent.parent





# ============================================================

# SECURITY

# ============================================================



SECRET_KEY = config(

    'SECRET_KEY',

    default='change-this-secret-key-in-production'

)



DEBUG = config(

    'DEBUG',

    default=False,

    cast=bool

)





# ============================================================

# ALLOWED HOSTS

# ============================================================



ALLOWED_HOSTS = [

    'ivanka-production.up.railway.app',

    '127.0.0.1',

    'localhost',

    '0.0.0.0',

]





# ============================================================

# CSRF TRUSTED ORIGINS

# ============================================================



CSRF_TRUSTED_ORIGINS = [

   
    'https://ivanka-production.up.railway.app',
    

    'http://127.0.0.1:8000',

    'http://localhost:8000',

]





# ============================================================

# CORS

# ============================================================



CORS_ALLOWED_ORIGINS = [

    'https://ivanka-production.up.railway.app',
     
    'http://127.0.0.1:8000',

    'http://localhost:8000',

]



CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True





# ============================================================

# SESSION SETTINGS

# ============================================================



SESSION_ENGINE = 'django.contrib.sessions.backends.db'

SESSION_COOKIE_AGE = 1209600

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = 'Lax'

SESSION_COOKIE_SECURE = not DEBUG





# ============================================================

# CSRF COOKIE

# ============================================================



CSRF_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_HTTPONLY = False

CSRF_COOKIE_SAMESITE = 'Lax'





# ============================================================

# SSL / RAILWAY PROXY

# ============================================================



SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_SSL_REDIRECT = False





# ============================================================

# SECURITY HEADERS

# ============================================================



if not DEBUG:

    SECURE_CONTENT_TYPE_NOSNIFF = True

    SECURE_BROWSER_XSS_FILTER = True

    X_FRAME_OPTIONS = 'DENY'

    SECURE_HSTS_SECONDS = 31536000

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True





# ============================================================

# APPLICATIONS

# ============================================================



INSTALLED_APPS = [

    # Django

    'django.contrib.admin',

    'django.contrib.auth',

    'django.contrib.contenttypes',

    'django.contrib.sessions',

    'django.contrib.messages',

    'django.contrib.staticfiles',

    'django.contrib.sites',



    # Utilities

    'django_extensions',



    # Forms

    'crispy_forms',

    'crispy_bootstrap5',



    # REST API

    'rest_framework',

    'django_filters',

    'rest_framework_simplejwt',



    # Authentication

    'allauth',

    'allauth.account',

    'allauth.socialaccount',

    'allauth.socialaccount.providers.google',



    # Project apps

    'hiring',
    'store',


    # Communication

    'channels',

    'corsheaders',



    # Utilities

    'phonenumber_field',



    # PWA

    'pwa',

    'webpush',

    'storages',

    'whitenoise',

]





# ============================================================

# CUSTOM USER

# ============================================================



AUTH_USER_MODEL = 'hiring.CustomUser'





# ============================================================

# DJANGO SITES

# ============================================================



SITE_ID = 1





# ============================================================

# AUTHENTICATION BACKENDS

# ============================================================



AUTHENTICATION_BACKENDS = [

    'django.contrib.auth.backends.ModelBackend',

    'allauth.account.auth_backends.AuthenticationBackend',

]





# ============================================================

# ALLAUTH - ACCOUNT

# ============================================================



ACCOUNT_LOGIN_METHODS = {'email', 'username'}



ACCOUNT_SIGNUP_FIELDS = [

    'email*',

    'username*',

    'password1*',

    'password2*',

]



ACCOUNT_EMAIL_VERIFICATION = 'optional'

ACCOUNT_UNIQUE_EMAIL = True

ACCOUNT_LOGOUT_ON_GET = False

ACCOUNT_LOGOUT_REDIRECT_URL = '/'

ACCOUNT_LOGIN_REDIRECT_URL = '/'

ACCOUNT_SIGNUP_REDIRECT_URL = '/'

LOGIN_REDIRECT_URL = '/'



ACCOUNT_ADAPTER = 'hiring.adapters.OppoGlobeAccountAdapter'





# ============================================================

# ALLAUTH - SOCIAL ACCOUNTS

# ============================================================



SOCIALACCOUNT_AUTO_SIGNUP = True

SOCIALACCOUNT_QUERY_EMAIL = True

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_LOGIN_ON_GET = True





# ============================================================

# GOOGLE OAUTH

# ============================================================



SOCIALACCOUNT_PROVIDERS = {

    'google': {

        'SCOPE': ['profile', 'email'],

        'AUTH_PARAMS': {'access_type': 'online'},

        'OAUTH_PKCE_ENABLED': True,

    },

}





# ============================================================

# PWA  (single, clean block — no duplicates)

# ============================================================



PWA_APP_NAME = 'OppoGlobe - Find Your Dream Property'

PWA_APP_SHORT_NAME = 'OppoGlobe'

PWA_APP_DESCRIPTION = 'Property rental, sales, and job platform'

PWA_APP_THEME_COLOR = "#ffffff"

PWA_APP_BACKGROUND_COLOR = '#ffffff'

PWA_APP_DISPLAY = 'standalone'

PWA_APP_SCOPE = '/'

PWA_APP_START_URL = '/?source=pwa'

PWA_APP_STATUS_BAR_COLOR = 'default'

PWA_APP_DIR = 'ltr'

PWA_APP_LANG = 'en'

PWA_APP_ORIENTATION = 'portrait'



PWA_APP_ICONS = [

    {'src': '/static/hiring/icons/icon-72.png',           'sizes': '72x72',   'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-72-maskable.png',  'sizes': '72x72',   'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-96.png',           'sizes': '96x96',   'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-96-maskable.png',  'sizes': '96x96',   'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-128.png',          'sizes': '128x128', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-128-maskable.png', 'sizes': '128x128', 'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-144.png',          'sizes': '144x144', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-144-maskable.png', 'sizes': '144x144', 'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-152.png',          'sizes': '152x152', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-152-maskable.png', 'sizes': '152x152', 'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-192.png',          'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-192-maskable.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-384.png',          'sizes': '384x384', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-384-maskable.png', 'sizes': '384x384', 'type': 'image/png', 'purpose': 'maskable'},

    {'src': '/static/hiring/icons/icon-512.png',          'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},

    {'src': '/static/hiring/icons/icon-512-maskable.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},

]



PWA_APP_SCREENSHOTS = [

    {

        'src': '/static/hiring/screenshots/desktop.png',

        'sizes': '1280x720',

        'type': 'image/png',

        'platform': 'wide',

        'label': 'Browse properties on desktop',

    },

    {

        'src': '/static/hiring/screenshots/mobile.png',

        'sizes': '750x1334',

        'type': 'image/png',

        'platform': 'narrow',

        'label': 'Search rentals and jobs on mobile',

    },

]



PWA_APP_SHORTCUTS = [

    {

        'name': 'Properties',

        'short_name': 'Properties',

        'description': 'View available properties',

        'url': '/?tab=properties',

        'icons': [

            {'src': '/static/hiring/icons/shortcut-properties.png', 'sizes': '96x96', 'type': 'image/png'}

        ],

    },

    {

        'name': 'Jobs',

        'short_name': 'Jobs',

        'description': 'Browse job listings',

        'url': '/?tab=jobs',

        'icons': [

            {'src': '/static/hiring/icons/shortcut-jobs.png', 'sizes': '96x96', 'type': 'image/png'}

        ],

    },

    {

        'name': 'Maintenance',

        'short_name': 'Maintenance',

        'description': 'Submit maintenance requests',

        'url': '/?tab=maintenance',

        'icons': [

            {'src': '/static/hiring/icons/shortcut-maintenance.png', 'sizes': '96x96', 'type': 'image/png'}

        ],

    },

]



PWA_APP_SPLASH_SCREEN = [

    {

        'src': '/static/hiring/icons/icon-512.png',

        'sizes': '512x512',

        'type': 'image/png',

    },

]



# ============================================================
# WEB PUSH / PWA NOTIFICATIONS
# ============================================================

PWA_VAPID_PUBLIC_KEY = os.environ.get(
    'VAPID_PUBLIC_KEY',
    ''
).strip()

PWA_VAPID_EMAIL = os.environ.get(
    'VAPID_EMAIL',
    'akaniivinmiyen@gmail.com'
).strip()

VAPID_PRIVATE_KEY_ENV = os.environ.get(
    'VAPID_PRIVATE_KEY',
    ''
).strip()

LOCAL_VAPID_PRIVATE_KEY = BASE_DIR / 'private_key.pem'

if VAPID_PRIVATE_KEY_ENV:
    PWA_VAPID_PRIVATE_KEY = VAPID_PRIVATE_KEY_ENV
elif LOCAL_VAPID_PRIVATE_KEY.exists():
    PWA_VAPID_PRIVATE_KEY = str(LOCAL_VAPID_PRIVATE_KEY)
else:
    PWA_VAPID_PRIVATE_KEY = ''

PWA_SETTINGS = {
    'VAPID_PUBLIC_KEY': PWA_VAPID_PUBLIC_KEY,
    'VAPID_PRIVATE_KEY': PWA_VAPID_PRIVATE_KEY,
    'VAPID_EMAIL': PWA_VAPID_EMAIL,
}

WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': PWA_VAPID_PUBLIC_KEY,
    'VAPID_PRIVATE_KEY': PWA_VAPID_PRIVATE_KEY,
    'VAPID_CLAIM': {
        'sub': f'mailto:{PWA_VAPID_EMAIL}'
    },
}


# ============================================================

# MIDDLEWARE

# ============================================================



MIDDLEWARE = [

    'django.middleware.security.SecurityMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',

    'corsheaders.middleware.CorsMiddleware',

    'django.middleware.common.CommonMiddleware',

    'django.middleware.csrf.CsrfViewMiddleware',

    'hiring.middleware.PWAThrottleMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',

    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'allauth.account.middleware.AccountMiddleware',

]





# ============================================================

# URL CONFIGURATION

# ============================================================



ROOT_URLCONF = 'ivanka.urls'





# ============================================================

# TEMPLATES

# ============================================================



TEMPLATES = [

    {

        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        'DIRS': [BASE_DIR / 'templates'],

        'APP_DIRS': True,

        'OPTIONS': {

            'context_processors': [

                'django.template.context_processors.debug',

                'django.template.context_processors.request',

                'django.contrib.auth.context_processors.auth',

                'django.contrib.messages.context_processors.messages',

                'django.template.context_processors.media',

                'core.context_processors.google_maps_api_key',

            ],

        },

    },

]





# ============================================================

# WSGI / ASGI

# ============================================================



WSGI_APPLICATION = 'ivanka.wsgi.application'

ASGI_APPLICATION = 'ivanka.asgi.application'





# ============================================================

# DATABASE

# ============================================================



if os.environ.get('DATABASE_URL'):

    DATABASES = {

        'default': dj_database_url.config(

            default=os.environ.get('DATABASE_URL'),

            conn_max_age=600,

            ssl_require=True,

        )

    }

else:

    DATABASES = {

        'default': {

            'ENGINE': 'django.db.backends.sqlite3',

            'NAME': BASE_DIR / 'db.sqlite3',

        }

    }





# ============================================================

# API KEYS

# ============================================================



DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')





YOCO_PUBLIC_KEY = os.getenv("YOCO_PUBLIC_KEY", "")

YOCO_SECRET_KEY = os.getenv("YOCO_SECRET_KEY", "")

# ============================================================

# STATIC FILES

# ============================================================



STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')



STATICFILES_DIRS = [

    os.path.join(BASE_DIR, 'static'),

    os.path.join(BASE_DIR, 'hiring', 'static'),

]





# ============================================================

# CREATE STATIC DIRECTORIES IF NEEDED

# ============================================================



for directory in STATICFILES_DIRS:

    if not os.path.exists(directory):

        os.makedirs(directory, exist_ok=True)



if not os.path.exists(STATIC_ROOT):

    os.makedirs(STATIC_ROOT, exist_ok=True)





# ============================================================

# UPLOAD LIMITS

# ============================================================



MAX_UPLOAD_SIZE = 314572800

DATA_UPLOAD_MAX_MEMORY_SIZE = 314572800

FILE_UPLOAD_MAX_MEMORY_SIZE = 314572800





# ============================================================

# PASSWORD VALIDATION

# ============================================================



AUTH_PASSWORD_VALIDATORS = [

    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},

    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},

    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},

    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},

]





# ============================================================

# INTERNATIONALIZATION

# ============================================================



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True





# ============================================================

# REST FRAMEWORK

# ============================================================



REST_FRAMEWORK = {

    'DEFAULT_AUTHENTICATION_CLASSES': [

        'rest_framework.authentication.SessionAuthentication',

        'rest_framework_simplejwt.authentication.JWTAuthentication',

    ],

    'DEFAULT_PERMISSION_CLASSES': [

        'rest_framework.permissions.IsAuthenticatedOrReadOnly',

    ],

    'DEFAULT_RENDERER_CLASSES': [

        'rest_framework.renderers.JSONRenderer',

    ],

    'DEFAULT_FILTER_BACKENDS': [

        'django_filters.rest_framework.DjangoFilterBackend',

        'rest_framework.filters.SearchFilter',

        'rest_framework.filters.OrderingFilter',

    ],

    'DEFAULT_THROTTLE_CLASSES': [

        'rest_framework.throttling.AnonRateThrottle',

        'rest_framework.throttling.UserRateThrottle',

    ],

    'DEFAULT_THROTTLE_RATES': {

        'anon': '1000/day',

        'user': '1000/day',

    },

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',

    'PAGE_SIZE': 20,

}





# ============================================================

# FRONTEND URL

# ============================================================



FRONTEND_URL = config(

    'FRONTEND_URL',

    default='https://www.oppoglobe.co.za'

)





# ============================================================

# PRODUCTION EMAIL

# ============================================================



EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'

EMAIL_PORT = 587

EMAIL_USE_TLS = True

EMAIL_USE_SSL = False



EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')

EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

DEFAULT_FROM_EMAIL = config(

    'DEFAULT_FROM_EMAIL',

    default='OppoGlobe <ivinakani@gmail.com>'

)



SERVER_EMAIL = DEFAULT_FROM_EMAIL





# ============================================================

# PASSWORD RESET

# ============================================================



PASSWORD_RESET_TIMEOUT = 86400

PASSWORD_RESET_EMAIL_TEMPLATE = 'registration/password_reset_email.html'





# ============================================================

# CRISPY FORMS

# ============================================================



CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'

CRISPY_TEMPLATE_PACK = 'bootstrap5'





# ============================================================

# PROJECT IDENTIFIERS

# ============================================================



RESIDENT_ID_PREFIX = 'ugr'

BUSINESS_ID_PREFIX = 'lec'





# ============================================================

# DEFAULT PRIMARY KEY

# ============================================================



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'





# ============================================================

# REAL ESTATE SETTINGS

# ============================================================



REALESTATE_SETTINGS = {

    'ENABLE_REAL_TIME_TRACKING': False,

    'ENABLE_GOOGLE_MAPS': True,

    'GOOGLE_MAPS_API_KEY': GOOGLE_MAPS_API_KEY,

    'MAX_NEARBY_RADIUS': 20,

    'DEFAULT_BOOKING_MODE': 'traditional',

}





# ============================================================

# CHANNELS / WEBSOCKETS

# ============================================================



CHANNEL_LAYERS = {

    'default': {

        'BACKEND': 'channels.layers.InMemoryChannelLayer',

    },

}





# ============================================================

# LOGGING

# ============================================================



LOGGING = {

    'version': 1,

    'disable_existing_loggers': False,

    'formatters': {

        'verbose': {

            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',

        },

    },

    'handlers': {

        'console': {

            'level': 'INFO',

            'class': 'logging.StreamHandler',

            'formatter': 'verbose',

        },

    },

    'root': {

        'level': 'INFO',

        'handlers': ['console'],

    },

}





# ============================================================

# GOOGLE CLOUD STORAGE

# ============================================================



GS_BUCKET_NAME = os.environ.get('GS_BUCKET_NAME', 'tolleya-storage')





def get_google_credentials():

    """Load Google Cloud credentials from Railway or local environment."""



    if 'GS_CREDENTIALS_JSON' in os.environ:

        try:

            creds_json = json.loads(os.environ['GS_CREDENTIALS_JSON'])

            return service_account.Credentials.from_service_account_info(creds_json)

        except Exception as e:

            print(f'Error loading GS_CREDENTIALS_JSON: {e}')



    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:

        cred_path = os.environ['GOOGLE_APPLICATION_CREDENTIALS']

        if os.path.exists(cred_path):

            try:

                return service_account.Credentials.from_service_account_file(cred_path)

            except Exception as e:

                print(f'Error loading GOOGLE_APPLICATION_CREDENTIALS: {e}')



    if 'GS_CREDENTIALS' in os.environ:

        cred_path = os.environ['GS_CREDENTIALS']

        if os.path.exists(cred_path):

            try:

                return service_account.Credentials.from_service_account_file(cred_path)

            except Exception as e:

                print(f'Error loading GS_CREDENTIALS: {e}')



    local_cred_path = os.path.join(BASE_DIR, 'credentials', 'service-account-key.json')

    if os.path.exists(local_cred_path):

        try:

            return service_account.Credentials.from_service_account_file(local_cred_path)

        except Exception as e:

            print(f'Error loading local credentials: {e}')



    return None





GS_CREDENTIALS = get_google_credentials()





# ============================================================

# GOOGLE CLOUD STORAGE CONFIGURATION

# ============================================================



GS_FILE_OVERWRITE = False

GS_QUERYSTRING_AUTH = False





if GS_CREDENTIALS and GS_BUCKET_NAME:

    STORAGES = {

        'default': {

            'BACKEND': 'storages.backends.gcloud.GoogleCloudStorage',

            'OPTIONS': {

                'bucket_name': GS_BUCKET_NAME,

                'credentials': GS_CREDENTIALS,

                'file_overwrite': GS_FILE_OVERWRITE,

                'querystring_auth': GS_QUERYSTRING_AUTH,

            },

        },

        'staticfiles': {

            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',

        },

    }

    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'

else:

    STORAGES = {

        'default': {

            'BACKEND': 'django.core.files.storage.FileSystemStorage',

        },

        'staticfiles': {

            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',

        },

    }

    MEDIA_URL = '/media/'

    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')





# ============================================================

# WHITENOISE

# ============================================================



STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'





# ============================================================

# CUSTOM THROTTLE

# ============================================================



from rest_framework.throttling import BaseThrottle





class NoThrottle(BaseThrottle):

    def allow_request(self, request, view):

        return True





# ============================================================

# END OF SETTINGS

# ============================================================