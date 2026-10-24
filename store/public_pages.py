"""Company and Support pages; no changes to marketplace models or payment services."""
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe


def site_context():
    brand = {
        "name": "Ivanka & Stell Closet",
        "director": "Stella Gabriella Muwata",
        "phone_sa": "+27 67 325 4662",
        "phone_sa_href": "+27673254662",
        "whatsapp": "https://wa.me/27673254662",
        "phone_drc": "+243 835 599 139",
        "phone_drc_href": "+243835599139",
        "email": "Ivanka&Stellcloset26@gmail.com",
        "social_handle": "@Ivanka&stellcloset",
        "website_reference": "Ivanka&StellCloset.com",
        "locations": "Kinshasa, DRC · Johannesburg, South Africa",
    }
    brand.update(getattr(settings, "IVANKA_BRAND", {}))
    return {
        "brand": brand,
        "platform_home_url": getattr(settings, "IVANKA_PLATFORM_HOME_URL", "/"),
        "store_worker_enabled": getattr(settings, "IVANKA_ENABLE_STORE_WORKER", False),
        "jobs_api_url": getattr(settings, "IVANKA_JOBS_API_URL", ""),
        "jobs_page_url": getattr(settings, "IVANKA_JOBS_PAGE_URL", ""),
        "newsletter_api_url": getattr(settings, "IVANKA_NEWSLETTER_API_URL", ""),
        "business_hours": [
            ("Monday", "Closed"),
            ("Tuesday", "07:00–19:00"),
            ("Wednesday", "07:00–19:00"),
            ("Thursday", "07:00–19:00"),
            ("Friday", "07:00–19:00"),
            ("Saturday", "07:00–19:00"),
            ("Sunday", "09:00–15:00"),
        ],
    }


def _page(request, slug, title, description):
    context = site_context()
    context.update(page_slug=slug, page_title=title, page_description=description)
    return render(request, f"store/pages/{slug}.html", context)


@require_safe
@ensure_csrf_cookie
def about(request):
    return _page(request, "about", "About us", "Meet Ivanka & Stell Closet: fashion, accessories and natural beauty.")


@require_safe
@ensure_csrf_cookie
def contact(request):
    return _page(request, "contact", "Contact", "Contact the closet in South Africa and the DRC, and see our trading hours.")


@require_safe
@ensure_csrf_cookie
def careers(request):
    return _page(request, "careers", "Careers", "Enquire about work, selling and courier opportunities.")


@require_safe
@ensure_csrf_cookie
def help_centre(request):
    return _page(request, "help", "Help centre", "Help with shopping, accounts, orders and deliveries.")


@require_safe
@ensure_csrf_cookie
def faq(request):
    return _page(request, "faq", "FAQ", "Answers to common questions about the closet and marketplace.")


@require_safe
@ensure_csrf_cookie
def privacy(request):
    return _page(request, "privacy", "Privacy policy", "How account, order and delivery information is handled.")


@require_safe
@ensure_csrf_cookie
def terms(request):
    return _page(request, "terms", "Terms of service", "Terms for using the marketplace and placing orders.")


@require_safe
@ensure_csrf_cookie
def cookies(request):
    return _page(request, "cookies", "Cookies", "Essential cookies and app storage used by the website.")


@require_safe
def offline(request):
    return render(request, "store/pages/offline.html", site_context())
