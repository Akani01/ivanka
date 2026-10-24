from django.core.management.base import BaseCommand
from django.conf import settings
from store.models import StoreCurrency, StorePaymentGateway


class Command(BaseCommand):
    help = "Create base currency and gateway switches without demo data."

    def handle(self, *args, **kwargs):
        StoreCurrency.objects.get_or_create(
            code=settings.CATALOG_CURRENCY,
            defaults={
                "name": settings.CATALOG_CURRENCY,
                "symbol": settings.CATALOG_CURRENCY,
                "rate": 1,
            },
        )
        for code in ["cash", "yoco"]:
            StorePaymentGateway.objects.get_or_create(code=code)
        self.stdout.write("Base currency and gateway switches ready.")
