from django.urls import path
from . import public_pages

urlpatterns = [
    path("about/", public_pages.about, name="store_about"),
    path("contact/", public_pages.contact, name="store_contact"),
    path("careers/", public_pages.careers, name="store_careers"),
    path("help/", public_pages.help_centre, name="store_help"),
    path("faq/", public_pages.faq, name="store_faq"),
    path("privacy/", public_pages.privacy, name="store_privacy"),
    path("terms/", public_pages.terms, name="store_terms"),
    path("site-cookies/", public_pages.cookies, name="store_cookies"),
    path("offline/", public_pages.offline, name="store_offline"),
]
