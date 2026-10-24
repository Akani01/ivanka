"""Explicit gateway registry, same initialize_payment pattern as the source project."""

import base64, hashlib, hmac, time
import requests
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError
from store.models import (
    StoreOrder,
    StorePaymentGateway,
    StorePayment,
    StorePaymentAttempt,
)
from store.services import rounded


class CashGateway:
    def initialize_payment(self, payment, attempt):
        return {
            "reference": str(attempt.reference),
            "redirect_url": "",
            "status": "awaiting_collection",
        }


class YocoGateway:
    def initialize_payment(self, payment, attempt):
        if payment.currency != "ZAR":
            raise ValidationError(
                "Yoco accepts ZAR orders only. Choose ZAR or cash on delivery."
            )
        if not settings.YOCO_SECRET_KEY:
            raise ValidationError("Yoco is not configured.")
        if payment.gross_amount < 2:
            raise ValidationError("Minimum Yoco payment is ZAR 2.")
        payload = {
            "amount": int(payment.gross_amount * 100),
            "currency": "ZAR",
            "successUrl": settings.SITE_URL + "/#orders",
            "cancelUrl": settings.SITE_URL + "/#orders",
            "failureUrl": settings.SITE_URL + "/#orders",
            "metadata": {"payment_id": str(payment.pk)},
        }
        try:
            r = requests.post(
                "https://payments.yoco.com/api/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.YOCO_SECRET_KEY}",
                    "Idempotency-Key": str(attempt.reference),
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("id") or not data.get("redirectUrl"):
                raise ValueError("Incomplete gateway response")
        except (requests.RequestException, ValueError) as exc:
            # Retry uses the SAME attempt/reference; never blindly create another checkout.
            raise ValidationError(
                "Gateway response uncertain. Retry this payment to recover the same checkout."
            ) from exc
        return {
            "reference": data["id"],
            "redirect_url": data["redirectUrl"],
            "status": "pending",
        }


def get_store_gateway(code):
    registry = {"cash": CashGateway, "yoco": YocoGateway}
    if code not in registry:
        raise ValidationError("Unsupported payment gateway.")
    return registry[code]()


def initialize_payment(user, order_id, method, code):
    # Persist the gateway idempotency reference BEFORE an external request.
    with transaction.atomic():
        order = StoreOrder.objects.select_for_update().get(pk=order_id, buyer=user)
        if order.status == "cancelled":
            raise ValidationError("Order is cancelled.")
        if (method, code) not in [("cash", "cash"), ("card", "yoco")]:
            raise ValidationError("Payment method does not match gateway.")
        if code == "yoco" and (order.currency != "ZAR" or not settings.YOCO_SECRET_KEY):
            raise ValidationError(
                "Yoco requires configured credentials and a ZAR order."
            )
        gateway = StorePaymentGateway.objects.filter(code=code, active=True).first()
        if not gateway:
            raise ValidationError("Payment gateway is disabled.")
        commission = rounded(
            (order.subtotal - order.discount) * order.commission_percent / 100
        )
        p, _ = StorePayment.objects.get_or_create(
            order=order,
            defaults={
                "gateway": gateway,
                "payment_method": method,
                "currency": order.currency,
                "gross_amount": order.total,
                "platform_commission": commission,
                "provider_amount": order.total - commission,
                "settlement_mode": "cash" if code == "cash" else "platform_collects",
            },
        )
        if p.gateway_id != gateway.pk:
            raise ValidationError("A payment already exists using a different gateway.")
        if p.status == "paid" or p.redirect_url or p.status == "awaiting_collection":
            return p
        attempt, _ = StorePaymentAttempt.objects.get_or_create(
            payment=p, defaults={"status": "created"}
        )
    try:
        result = get_store_gateway(code).initialize_payment(p, attempt)
    except ValidationError:
        StorePaymentAttempt.objects.filter(pk=attempt.pk).update(
            status="uncertain", error="Gateway call incomplete; retry same reference."
        )
        raise
    with transaction.atomic():
        order = StoreOrder.objects.select_for_update().get(pk=order.pk)
        p = StorePayment.objects.select_for_update().get(pk=p.pk)
        if p.status == "paid":
            return p
        p.provider_id = result["reference"]
        p.redirect_url = result["redirect_url"]
        p.status = result["status"]
        p.save()
        attempt.provider_id = p.provider_id
        attempt.status = p.status
        attempt.save()
        if code == "cash" and order.status == "pending":
            order.status = "confirmed"
            order.save(update_fields=["status", "updated_at"])
        return p


def verify_signature(body, headers):
    try:
        stamp = headers["webhook-timestamp"]
        event = headers["webhook-id"]
        if abs(time.time() - int(stamp)) > 180:
            return False
        secret = settings.YOCO_WEBHOOK_SECRET
        if not secret.startswith("whsec_"):
            return False
        key = base64.b64decode(secret[6:], validate=True)
        signed = event.encode() + b"." + stamp.encode() + b"." + body
        expected = base64.b64encode(
            hmac.new(key, signed, hashlib.sha256).digest()
        ).decode()
        return any(
            hmac.compare_digest(expected, entry[3:])
            for entry in headers["webhook-signature"].split()
            if entry.startswith("v1,")
        )
    except (KeyError, ValueError, TypeError):
        return False
