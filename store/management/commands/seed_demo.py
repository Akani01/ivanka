"""Idempotent illustrative catalog. No default passwords or payment credentials."""

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from decimal import Decimal
from PIL import Image, ImageDraw
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from store.models import *
from hiring.models import JobListing


def artwork(kind):
    im = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if kind == "headphones":
        d.arc((230, 180, 770, 770), 180, 360, fill="#394038", width=72)
        d.arc((275, 220, 725, 740), 180, 360, fill="#565f51", width=26)
        for x in [210, 640]:
            d.rounded_rectangle((x, 430, x + 150, 770), radius=65, fill="#30392f")
            d.rounded_rectangle((x + 30, 460, x + 110, 740), radius=35, fill="#66705b")
    elif kind == "lamp":
        d.ellipse((250, 775, 750, 850), fill="#c4c6b0")
        d.ellipse((255, 755, 745, 820), fill="#dedfc6")
        d.rounded_rectangle((470, 405, 530, 790), radius=20, fill="#c8ccb3")
        d.pieslice((175, 160, 825, 720), 180, 360, fill="#bdc6a1")
        d.ellipse((175, 425, 825, 500), fill="#d7dfbc")
        d.ellipse((420, 450, 580, 480), fill="#fff4be")
    elif kind == "bag":
        d.rounded_rectangle(
            (320, 145, 680, 570), radius=140, outline="#866744", width=35
        )
        d.polygon([(250, 350), (750, 350), (820, 820), (180, 820)], fill="#c4a77e")
        d.line(
            [(250, 350), (180, 820), (820, 820), (750, 350)], fill="#9d805d", width=8
        )
        d.rounded_rectangle((355, 485, 645, 730), radius=12, outline="#a28763", width=6)
    elif kind == "speaker":
        d.rounded_rectangle((200, 300, 800, 730), radius=95, fill="#495044")
        for x in range(245, 760, 16):
            for y in range(350, 680, 14):
                d.ellipse((x, y, x + 3, y + 3), fill="#8d9781")
        d.rounded_rectangle((420, 250, 580, 290), radius=15, fill="#2b332a")
        d.ellipse((460, 470, 540, 550), fill="#293029")
    elif kind == "bottle":
        d.rounded_rectangle((365, 180, 635, 285), radius=30, fill="#303f36")
        d.rounded_rectangle((350, 250, 650, 830), radius=80, fill="#72927b")
        d.rounded_rectangle((375, 295, 395, 760), radius=10, fill="#9ab69c")
        d.ellipse((350, 760, 650, 850), fill="#64846c")
    elif kind == "watch":
        d.rounded_rectangle((385, 80, 615, 930), radius=55, fill="#8c997e")
        d.rounded_rectangle((330, 315, 670, 690), radius=80, fill="#30372d")
        d.rounded_rectangle((350, 335, 650, 670), radius=65, fill="#171f18")
        d.line((500, 500, 500, 390), fill="#d2ddc3", width=12)
        d.line((500, 500, 580, 540), fill="#d2ddc3", width=10)
        d.ellipse((486, 486, 514, 514), fill="#d2ddc3")
    elif kind == "mug":
        d.ellipse((600, 380, 830, 680), outline="#b88e6c", width=55)
        d.rounded_rectangle((220, 300, 680, 770), radius=95, fill="#cfa988")
        d.ellipse((220, 265, 680, 365), fill="#e0bea1")
        d.ellipse((250, 285, 650, 340), fill="#8d7058")
    else:
        d.rounded_rectangle((210, 190, 790, 820), radius=28, fill="#bda987")
        d.line((270, 190, 270, 820), fill="#857257", width=14)
        d.rounded_rectangle((340, 350, 660, 530), radius=6, fill="#d8c9aa")
        d.text((420, 425), "NOTES", fill="#665841", stroke_width=1)
    return im


class Command(BaseCommand):
    help = "Seed original illustrated demo products; exchange rates are EXAMPLES, not live rates."

    def handle(self, *args, **opts):
        U = get_user_model()
        user, created = U.objects.get_or_create(
            username="ivanka-demo-seller", defaults={"email": "demo@example.invalid"}
        )
        if created:
            user.set_unusable_password()
            user.save()
        store, _ = Store.objects.get_or_create(
            owner=user,
            defaults={
                "name": "The Everyday Studio",
                "description": "Considered essentials for everyday living. Illustrative demo catalog.",
                "address": "Johannesburg, South Africa",
                "approved": True,
                "latitude": Decimal("-26.2041"),
                "longitude": Decimal("28.0473"),
            },
        )
        for code, name, symbol, rate in [
            (
                settings.CATALOG_CURRENCY,
                "Catalog base currency",
                settings.CATALOG_CURRENCY,
                "1",
            ),
            ("USD", "US Dollar — DEMO rate", "$", "0.055"),
            ("EUR", "Euro — DEMO rate", "€", "0.05"),
            ("GBP", "Pound — DEMO rate", "£", "0.043"),
        ]:
            StoreCurrency.objects.get_or_create(
                code=code, defaults={"name": name, "symbol": symbol, "rate": rate}
            )
        for code in ["cash", "yoco"]:
            StorePaymentGateway.objects.get_or_create(code=code)
        records = [
            (
                "headphones",
                "Sound & tech",
                "Studio wireless headphones",
                "SONORA",
                "1299",
            ),
            ("lamp", "Home & living", "Mushroom desk lamp", "FORM & FIELD", "649"),
            (
                "bag",
                "Style essentials",
                "The everyday carry tote",
                "COMMON GROUND",
                "389",
            ),
            ("speaker", "Sound & tech", "Portable bluetooth speaker", "SONORA", "799"),
            (
                "bottle",
                "Everyday essentials",
                "The daily water bottle",
                "FIELDWORK",
                "249",
            ),
            ("watch", "Sound & tech", "Everyday smart watch", "MOTION", "1599"),
            ("mug", "Home & living", "Stoneware morning mug", "FORM & FIELD", "189"),
            (
                "notebook",
                "Everyday essentials",
                "The thoughtful notebook",
                "PAPERWORK",
                "149",
            ),
        ]
        for index, (kind, cat, name, brand, price) in enumerate(records):
            from django.utils.text import slugify

            category, _ = StoreCategory.objects.get_or_create(
                slug=slugify(cat), defaults={"name": cat}
            )
            p, _ = StoreProduct.objects.get_or_create(
                store=store,
                name=name,
                defaults={
                    "category": category,
                    "brand": brand,
                    "description": f"{name}. A considered addition to your everyday. This is a demonstration listing with an original product illustration, not an item available for purchase.",
                    "featured": index < 2,
                },
            )
            StoreProductVariant.objects.get_or_create(
                sku="DEMO-" + kind.upper(),
                defaults={
                    "product": p,
                    "label": (
                        "Sage / Standard"
                        if kind in ["headphones", "lamp"]
                        else "Standard"
                    ),
                    "price": price,
                    "stock": 25,
                },
            )
            if not p.images.exists():
                out = BytesIO()
                artwork(kind).save(out, "PNG")
                StoreProductImage.objects.create(
                    product=p,
                    image=ContentFile(out.getvalue(), name=kind + ".png"),
                    alt=f"Original illustration of {name}",
                )
        JobListing.objects.get_or_create(
            employer=user,
            title="Marketplace customer experience associate",
            defaults={
                "company_name": "Ivanka demo",
                "location": "Johannesburg",
                "description": "Illustrative vacancy: help shoppers and independent sellers create a thoughtful marketplace experience. This demo role is not a live recruitment offer.",
                "apply_by": timezone.localdate() + timedelta(days=60),
                "published": True,
            },
        )
        StoreCoupon.objects.get_or_create(
            code="HELLO10",
            defaults={
                "percent": 10,
                "minimum": 100,
                "expires_at": timezone.now() + timedelta(days=60),
            },
        )
        path = Path(settings.BASE_DIR) / "static/store"
        path.mkdir(parents=True, exist_ok=True)
        hero = Image.new("RGBA", (1100, 900), (0, 0, 0, 0))
        lamp = (
            artwork("lamp")
            .resize((720, 720))
            .rotate(-10, resample=Image.Resampling.BICUBIC, expand=True)
        )
        hero.alpha_composite(lamp, (410, -10))
        phones = (
            artwork("headphones")
            .resize((800, 800))
            .rotate(12, resample=Image.Resampling.BICUBIC, expand=True)
        )
        hero.alpha_composite(phones, (-60, 60))
        hero.save(path / "hero.png")
        for size in [192, 512]:
            icon = Image.new("RGB", (size, size), "#183d2d")
            d = ImageDraw.Draw(icon)
            d.rounded_rectangle(
                (size * 0.42, size * 0.34, size * 0.58, size * 0.78),
                radius=int(size * 0.04),
                fill="#d5ef8c",
            )
            d.ellipse(
                (size * 0.42, size * 0.14, size * 0.58, size * 0.30), fill="#d5ef8c"
            )
            icon.save(path / f"icon-{size}.png")
        Image.new("RGB", (1200, 1200), "#f4f4f2").save(path / "placeholder.png")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo catalog ready. No login passwords created. DEMO exchange rates must be replaced before real use."
            )
        )
