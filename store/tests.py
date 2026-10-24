import base64, hashlib, hmac, json, time, uuid
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from .models import *
from .services import checkout, cancel_order, change_order
from .payments.registry import initialize_payment


class MarketplaceTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.buyer = U.objects.create_user(
            "buyer", password="Shoppers!48291", email="buyer@example.test"
        )
        self.seller = U.objects.create_user("seller")
        self.other = U.objects.create_user("other")
        self.store = Store.objects.create(
            owner=self.seller,
            name="Studio",
            address="Elim",
            approved=True,
            shipping_fee=65,
        )
        self.category = StoreCategory.objects.create(name="Home", slug="home")
        self.product = StoreProduct.objects.create(
            store=self.store, category=self.category, name="Lamp", description="A lamp"
        )
        self.v = StoreProductVariant.objects.create(
            product=self.product, sku="LAMP", price="100", stock=10
        )
        self.address = StoreDeliveryAddress.objects.create(
            user=self.buyer,
            recipient="Buyer",
            phone="0700000000",
            line1="1 Main Street",
            city="Elim",
            province="Limpopo",
            postal_code="0960",
        )
        self.cart = StoreCart.objects.create(user=self.buyer)
        StoreCartItem.objects.create(cart=self.cart, variant=self.v, quantity=2)
        StoreCurrency.objects.create(code="USD", name="Dollar", symbol="$", rate="0.05")
        StorePaymentGateway.objects.create(code="cash")
        StorePaymentGateway.objects.create(code="yoco")
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def order(self, code="ZAR"):
        return checkout(self.buyer, self.address.pk, uuid.uuid4(), code).orders.get()

    def test_conversion_and_rate_snapshot(self):
        order = self.order("USD")
        self.assertEqual(order.subtotal, Decimal("10"))
        self.assertEqual(order.shipping, Decimal("3.25"))
        self.assertEqual(order.currency, "USD")
        StoreCurrency.objects.filter(code="USD").update(rate="0.1")
        self.v.price = 200
        self.v.save()
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("13.25"))
        self.assertEqual(order.exchange_rate, Decimal("0.05"))

    def test_checkout_is_idempotent(self):
        key = uuid.uuid4()
        first = checkout(self.buyer, self.address.pk, key, "ZAR")
        second = checkout(self.buyer, self.address.pk, key, "ZAR")
        self.assertEqual(first.pk, second.pk)
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 8)

    def test_multiple_sellers_split(self):
        s = Store.objects.create(
            owner=self.other,
            name="Two",
            address="Cape Town",
            approved=True,
            shipping_fee=30,
        )
        p = StoreProduct.objects.create(
            store=s, category=self.category, name="Bag", description="Bag"
        )
        v = StoreProductVariant.objects.create(product=p, sku="BAG", price=50, stock=3)
        StoreCartItem.objects.create(cart=self.cart, variant=v, quantity=1)
        batch = checkout(self.buyer, self.address.pk, uuid.uuid4(), "ZAR")
        self.assertEqual(batch.orders.count(), 2)
        self.assertEqual(batch.total, 345)

    def test_stock_failure_rolls_back_entire_checkout(self):
        p = StoreProduct.objects.create(
            store=self.store, category=self.category, name="Bag", description="Bag"
        )
        v = StoreProductVariant.objects.create(product=p, sku="BAG", price=50, stock=0)
        StoreCartItem.objects.create(cart=self.cart, variant=v, quantity=1)
        with self.assertRaises(ValidationError):
            self.order()
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 10)
        self.assertEqual(StoreOrder.objects.count(), 0)
        self.assertEqual(self.cart.items.count(), 2)

    def test_customer_cannot_view_other_orders(self):
        o = self.order()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/store/api/orders/{o.pk}/").status_code, 404)

    def test_buyer_cannot_modify_product(self):
        self.assertEqual(
            self.client.patch(
                f"/store/api/products/{self.product.pk}/", {"name": "stolen"}
            ).status_code,
            403,
        )

    def test_seller_cannot_move_product_to_another_store(self):
        s = Store.objects.create(owner=self.other, name="Other", address="X")
        self.client.force_authenticate(self.seller)
        r = self.client.patch(
            f"/store/api/products/{self.product.pk}/", {"store": s.pk, "name": "New"}
        )
        self.assertEqual(r.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.store_id, self.store.pk)

    def test_address_ownership(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.patch(
                f"/store/api/addresses/{self.address.pk}/", {"line1": "stolen"}
            ).status_code,
            404,
        )

    def test_cash_not_paid_on_selection(self):
        o = self.order()
        p = initialize_payment(self.buyer, o.pk, "cash", "cash")
        self.assertEqual(p.status, "awaiting_collection")
        o.refresh_from_db()
        self.assertEqual(o.payment_status, "unpaid")
        self.assertEqual(o.status, "confirmed")

    def test_cancel_restores_stock_once(self):
        o = self.order()
        cancel_order(self.buyer, o.pk)
        cancel_order(self.buyer, o.pk)
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 10)

    @override_settings(YOCO_SECRET_KEY="sk_test_example")
    def test_yoco_blocks_non_zar_without_network(self):
        o = self.order("USD")
        with patch("store.payments.registry.requests.post") as req:
            with self.assertRaises(ValidationError):
                initialize_payment(self.buyer, o.pk, "card", "yoco")
            req.assert_not_called()

    @override_settings(YOCO_SECRET_KEY="sk_test_example")
    def test_uncertain_yoco_retry_keeps_reference(self):
        import requests

        o = self.order()
        with patch(
            "store.payments.registry.requests.post", side_effect=requests.Timeout
        ):
            with self.assertRaises(ValidationError):
                initialize_payment(self.buyer, o.pk, "card", "yoco")
        a = StorePaymentAttempt.objects.get()
        ref = a.reference
        response = Mock()
        response.json.return_value = {
            "id": "ch_test",
            "redirectUrl": "https://payments.yoco.com/test",
        }
        with patch(
            "store.payments.registry.requests.post", return_value=response
        ) as req:
            p = initialize_payment(self.buyer, o.pk, "card", "yoco")
            self.assertEqual(
                req.call_args.kwargs["headers"]["Idempotency-Key"], str(ref)
            )
            self.assertEqual(p.provider_id, "ch_test")
        self.assertEqual(StorePaymentAttempt.objects.count(), 1)

    def sign(self, event, secret, stamp=None):
        body = json.dumps(event, separators=(",", ":")).encode()
        stamp = str(stamp or int(time.time()))
        eid = "msg_test"
        key = base64.b64decode(secret[6:])
        sig = base64.b64encode(
            hmac.new(
                key, (eid + "." + stamp + ".").encode() + body, hashlib.sha256
            ).digest()
        ).decode()
        return body, {
            "HTTP_WEBHOOK_ID": eid,
            "HTTP_WEBHOOK_TIMESTAMP": stamp,
            "HTTP_WEBHOOK_SIGNATURE": "v1," + sig,
        }

    def test_webhook_replay_and_amount_validation(self):
        secret = (
            "whsec_" + base64.b64encode(b"test-webhook-secret-32-characters").decode()
        )
        o = self.order()
        g = StorePaymentGateway.objects.get(code="yoco")
        StorePayment.objects.create(
            order=o,
            gateway=g,
            payment_method="card",
            gross_amount=o.total,
            platform_commission=20,
            provider_amount=o.total - 20,
            provider_id="ch_123",
            currency="ZAR",
        )
        e = {
            "id": "evt_123",
            "type": "payment.succeeded",
            "payload": {
                "amount": int(o.total * 100),
                "currency": "ZAR",
                "status": "succeeded",
                "metadata": {"checkoutId": "ch_123"},
            },
        }
        with override_settings(YOCO_WEBHOOK_SECRET=secret):
            body, h = self.sign(e, secret, int(time.time()) - 400)
            self.assertEqual(
                self.client.post(
                    "/store/api/payments/yoco/webhook/",
                    body,
                    content_type="application/json",
                    **h,
                ).status_code,
                403,
            )
            e["payload"]["amount"] = 1
            body, h = self.sign(e, secret)
            self.assertEqual(
                self.client.post(
                    "/store/api/payments/yoco/webhook/",
                    body,
                    content_type="application/json",
                    **h,
                ).status_code,
                400,
            )
            e["payload"]["amount"] = int(o.total * 100)
            body, h = self.sign(e, secret)
            for _ in range(2):
                self.assertEqual(
                    self.client.post(
                        "/store/api/payments/yoco/webhook/",
                        body,
                        content_type="application/json",
                        **h,
                    ).status_code,
                    200,
                )
        self.assertEqual(StoreLedgerEntry.objects.count(), 1)
        self.assertEqual(StoreWebhookEvent.objects.count(), 1)
        o.refresh_from_db()
        self.assertEqual(o.payment_status, "paid")

    def test_coupon_discount_and_one_use(self):
        from datetime import timedelta

        StoreCoupon.objects.create(
            code="TEN",
            percent=10,
            minimum=100,
            expires_at=timezone.now() + timedelta(days=1),
        )
        o = checkout(
            self.buyer, self.address.pk, uuid.uuid4(), "ZAR", "TEN"
        ).orders.get()
        self.assertEqual(o.discount, 20)
        self.assertEqual(o.total, 245)
        StoreCartItem.objects.create(cart=self.cart, variant=self.v, quantity=1)
        with self.assertRaises(ValidationError):
            checkout(self.buyer, self.address.pk, uuid.uuid4(), "ZAR", "TEN")

    def test_cart_bounds_and_invalid_currency(self):
        self.assertEqual(
            self.client.post(
                "/store/api/cart/", {"variant": self.v.pk, "quantity": -1}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/store/api/products/?currency=XXX").status_code, 400
        )

    def test_driver_delivery_and_cod_settlement(self):
        U = get_user_model()
        owner = U.objects.create_user("courier")
        driver = U.objects.create_user("driver")
        c = StoreCourierCompany.objects.create(
            owner=owner, name="Courier", phone="123", approved=True
        )
        a = StoreDeliveryAgent.objects.create(company=c, user=driver, vehicle="Van")
        o = self.order()
        initialize_payment(self.buyer, o.pk, "cash", "cash")
        change_order(self.seller, o.pk, "packing")
        change_order(self.seller, o.pk, "shipped")
        d = StoreDelivery.objects.get(order=o)
        d.company = c
        d.agent = a
        d.status = "assigned"
        d.save()
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/store/api/delivery/{d.pk}/track/").status_code, 403
        )
        self.client.force_authenticate(driver)
        for s in ["picked_up", "in_transit"]:
            self.assertEqual(
                self.client.post(
                    f"/store/api/delivery/{d.pk}/track/",
                    {"action": "status", "status": s},
                    format="json",
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client.post(
                f"/store/api/delivery/{d.pk}/track/",
                {"action": "status", "status": "delivered"},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f"/store/api/delivery/{d.pk}/track/",
                {"action": "status", "status": "delivered", "cash_collected": True},
                format="json",
            ).status_code,
            200,
        )
        o.refresh_from_db()
        self.assertEqual(o.status, "delivered")
        self.assertEqual(o.payment_status, "paid")
        self.assertEqual(
            StoreLedgerEntry.objects.get(kind="commission_due").amount, -20
        )
        self.assertEqual(
            self.client.post(
                "/store/api/delivery/location/",
                {"latitude": "-26.2000000", "longitude": "28.0400000"},
                format="json",
            ).status_code,
            400,
        )

    def test_invalid_gps(self):
        self.assertEqual(
            self.client.get("/store/api/geocode/reverse/?lat=999&lng=28").status_code,
            400,
        )

    def test_image_normalization(self):
        from .images import normalize_product_image

        out = BytesIO()
        Image.new("RGBA", (400, 200), (255, 0, 0, 128)).save(out, "PNG")
        u = SimpleUploadedFile("x.png", out.getvalue(), content_type="image/png")
        im = Image.open(normalize_product_image(u))
        self.assertEqual(im.size, (1200, 1200))
        self.assertEqual(im.mode, "RGB")
        self.assertEqual(im.format, "WEBP")
        with self.assertRaises(ValidationError):
            normalize_product_image(SimpleUploadedFile("bad.png", b"not an image"))

    def test_csrf_for_auth_and_cart(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(
            c.post(
                "/api/auth/login/", {"username": "buyer", "password": "Shoppers!48291"}
            ).status_code,
            403,
        )
        c.force_login(self.buyer)
        self.assertEqual(
            c.post(
                "/store/api/cart/", {"variant": self.v.pk, "quantity": 1}
            ).status_code,
            403,
        )

    def test_hiring_application_unique(self):
        from hiring.models import JobListing, Application
        from datetime import timedelta

        j = JobListing.objects.create(
            employer=self.seller,
            title="Role",
            company_name="Store",
            location="Elim",
            description="Role",
            apply_by=timezone.localdate() + timedelta(days=1),
            published=True,
        )
        for _ in range(2):
            self.assertIn(
                self.client.post(
                    "/hiring/api/applications/",
                    {"job": j.pk, "cover_letter": "My skills"},
                ).status_code,
                [200, 201],
            )
        self.assertEqual(Application.objects.count(), 1)

    def test_opaque_photos_require_background_removal(self):
        from .images import normalize_product_image

        out = BytesIO()
        Image.new("RGB", (400, 200), "red").save(out, "JPEG")
        with self.assertRaises(ValidationError):
            normalize_product_image(SimpleUploadedFile("opaque.jpg", out.getvalue()))

    def test_seller_upload_endpoint_and_one_normalization(self):
        from django.test import override_settings
        import tempfile

        with tempfile.TemporaryDirectory() as directory, override_settings(
            MEDIA_ROOT=directory
        ):
            self.client.force_authenticate(self.seller)
            out = BytesIO()
            Image.new("RGBA", (300, 400), (0, 100, 0, 100)).save(out, "PNG")
            result = self.client.post(
                f"/store/api/products/{self.product.pk}/image/",
                {
                    "image": SimpleUploadedFile(
                        "cutout.png", out.getvalue(), content_type="image/png"
                    ),
                    "alt": "A cutout",
                    "position": 0,
                },
                format="multipart",
            )
            self.assertEqual(result.status_code, 201)
            image = StoreProductImage.objects.get()
            with image.image.open("rb") as data:
                self.assertEqual(Image.open(data).size, (1200, 1200))
