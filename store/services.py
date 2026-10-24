# store/services.py
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    StoreCurrency, Store, StoreStaff,
    StoreProduct, StoreProductVariant, StoreProductImage,
    StoreInventoryLog,
    StoreCart, StoreCartItem,
    StoreDeliveryAddress,
    StoreCoupon, StoreCouponRedemption,
    StoreCheckout, StoreOrder, StoreOrderItem, StoreOrderEvent,
    StorePayment, StoreWallet, StoreLedgerEntry,
    StoreDelivery, StoreConversation, StoreNotification,
)

CENT = Decimal("0.01")


# ============================================================
# MONEY / CURRENCY
# ============================================================

def rounded(value, places=2):
    """
    Round to `places` decimals, ROUND_HALF_UP.
    Accepts Decimal, int, float, str, or None. Never raises.
    """
    if value is None:
        return Decimal("0.00")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"Invalid monetary value: {value!r}")
    q = Decimal(1).scaleb(-places)
    return n.quantize(q, rounding=ROUND_HALF_UP)


def catalog_currency():
    """Return the storage/base currency code (all variant prices are in it)."""
    return getattr(settings, "CATALOG_CURRENCY", "ZAR")


def currency(code):
    """
    Return (code, rate). `rate` = how many units of `code` = 1 base currency unit.
    Falls back to base with rate=1 if code is None.
    Raises ValidationError for unknown/disabled currencies.
    """
    base = catalog_currency()
    if not code:
        return base, Decimal("1")
    code = code.strip().upper()
    if code == base:
        return base, Decimal("1")
    try:
        row = StoreCurrency.objects.get(code=code, enabled=True)
    except StoreCurrency.DoesNotExist:
        raise ValidationError(f"Currency {code} is not enabled.")
    if not row.rate or row.rate <= 0:
        raise ValidationError(f"Currency {code} has an invalid exchange rate.")
    return row.code, Decimal(row.rate)


# ============================================================
# ACCESS
# ============================================================

def seller_for(user):
    store = Store.objects.filter(owner=user, approved=True).first()
    if not store:
        raise PermissionDenied("An approved seller account is required.")
    return store


def can_manage(user, store):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if store.owner_id == user.pk:
        return True
    return store.staff.filter(user=user).exists()


def can_order(user, order):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if order.buyer_id == user.pk:
        return True
    if can_manage(user, order.store):
        return True
    d = StoreDelivery.objects.filter(order=order).first()
    return bool(
        d
        and (
            (d.company_id and d.company.owner_id == user.pk)
            or (d.agent_id and d.agent.user_id == user.pk)
        )
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

def notify(user, title):
    """Create an in-app store notification. Non-blocking, best-effort."""
    try:
        StoreNotification.objects.create(user=user, title=title)
    except Exception:
        # Never let a notification failure roll back a transaction.
        pass


# ============================================================
# CHECKOUT
# ============================================================

@transaction.atomic
def checkout(user, address_id, key, code, coupon_code=""):
    """
    Create a checkout batch + per-store orders.

    - All variant prices are stored in CATALOG_CURRENCY (base).
    - Totals on StoreCheckout / StoreOrder are ALSO stored in base currency.
    - Buyer's chosen currency + rate are snapshotted on both models.
    - Charge provider (Yoco) always receives `order.total` (base/ZAR).
    """
    # Lock the buyer for this checkout (idempotency + cart consistency).
    get_user_model().objects.select_for_update().get(pk=user.pk)

    # Idempotency: return the existing checkout if this key was used.
    previous = StoreCheckout.objects.filter(
        buyer=user, idempotency_key=key
    ).first()
    if previous:
        return previous

    # Resolve currency (buyer's chosen code, e.g. USD → rate 0.053).
    base_code = catalog_currency()
    code, rate = currency(code)

    # Delivery address.
    address = StoreDeliveryAddress.objects.filter(
        pk=address_id, user=user
    ).first()
    if not address:
        raise ValidationError("Select your delivery address.")

    # Cart must not be empty.
    cart, _ = StoreCart.objects.get_or_create(user=user)
    lines = list(
        cart.items.select_related("variant__product__store").order_by("variant_id")
    )
    if not lines:
        raise ValidationError("Your cart is empty.")

    # Lock + decrement stock, group by store.
    grouped = defaultdict(list)
    for line in lines:
        variant = (
            StoreProductVariant.objects.select_for_update()
            .select_related("product__store")
            .get(pk=line.variant_id)
        )
        if not variant.product.active or not variant.product.store.approved:
            raise ValidationError("A product is no longer available.")
        if not 1 <= line.quantity <= 99:
            raise ValidationError("Invalid quantity.")
        updated = StoreProductVariant.objects.filter(
            pk=variant.pk, stock__gte=line.quantity
        ).update(stock=F("stock") - line.quantity)
        if not updated:
            raise ValidationError(f"Not enough stock for {variant.product.name}.")
        grouped[variant.product.store_id].append((variant, line.quantity))

    # Subtotals are ALWAYS computed in base currency (never round the rate first).
    def base_subtotal(items):
        return sum(
            (rounded(v.price) * q for v, q in items),
            Decimal("0.00"),
        )

    subtotal_base = base_subtotal(
        [(v, q) for group in grouped.values() for v, q in group]
    )

    # Coupon validation (in base currency).
    coupon = None
    if coupon_code:
        coupon = (
            StoreCoupon.objects.select_for_update()
            .filter(
                code=coupon_code.strip().upper(),
                active=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not coupon:
            raise ValidationError("Coupon is unavailable or expired.")
        if coupon.uses >= coupon.max_uses:
            raise ValidationError("Coupon usage limit has been reached.")
        minimum_base = rounded(coupon.minimum)
        if subtotal_base < minimum_base:
            raise ValidationError(
                f"Minimum spend of {minimum_base} {base_code} not met."
            )
        if StoreCouponRedemption.objects.filter(
            coupon=coupon, buyer=user
        ).exists():
            raise ValidationError("You have already used this coupon.")

    # Create the checkout batch.
    batch = StoreCheckout.objects.create(
        buyer=user,
        idempotency_key=key,
        currency=code,             # buyer's currency (e.g. USD)
        exchange_rate=rate,        # 1 base = rate × chosen
        total=Decimal("0.00"),
    )

    # Address snapshot (JSON field on StoreOrder.address).
    snapshot = model_to_dict(address, exclude=["id", "user"])
    snapshot = {
        k: str(v) if isinstance(v, Decimal) else v
        for k, v in snapshot.items()
    }

    # Per-store orders.
    for store_id, group in grouped.items():
        store = group[0][0].product.store
        sub_base = base_subtotal(group)

        discount_base = (
            rounded(sub_base * coupon.percent / Decimal("100"))
            if coupon else Decimal("0.00")
        )
        shipping_base = rounded(store.shipping_fee)
        total_base = rounded(sub_base + shipping_base - discount_base)

        order = StoreOrder.objects.create(
            checkout=batch,
            store=store,
            buyer=user,
            address=snapshot,
            subtotal=sub_base,
            shipping=shipping_base,
            discount=discount_base,
            total=total_base,
            commission_percent=store.commission_percent,
            currency=code,
            exchange_rate=rate,
        )

        # Order items — unit_price is stored in BASE currency.
        for v, q in group:
            StoreOrderItem.objects.create(
                order=order,
                variant=v,
                name=f"{v.product.name} · {v.label}",
                sku=v.sku,
                unit_price=rounded(v.price),   # base
                quantity=q,
            )
            StoreInventoryLog.objects.create(
                variant=v,
                delta=-q,
                reason=f"Order {order.pk}",
                actor=user,
            )

        StoreOrderEvent.objects.create(
            order=order, status="pending", actor=user
        )
        StoreConversation.objects.create(order=order)
        notify(store.owner, f"New order {str(order.pk)[:8]}")

    # Roll up the checkout total in base currency.
    batch.total = sum(
        (o.total for o in batch.orders.all()),
        Decimal("0.00"),
    )
    batch.save(update_fields=["total", "updated_at"])

    # Redeem coupon.
    if coupon:
        coupon.uses = F("uses") + 1
        coupon.save(update_fields=["uses", "updated_at"])
        coupon.refresh_from_db(fields=["uses"])
        StoreCouponRedemption.objects.create(
            coupon=coupon, buyer=user, checkout=batch
        )

    # Clear cart.
    cart.items.all().delete()

    return batch


# ============================================================
# PAYMENT
# ============================================================

@transaction.atomic
def settle_payment(payment):
    """
    Mark the payment paid and the order confirmed.
    Ledger entries are written in the ORDER's currency (the snapshot),
    so refunds/receipts match what the buyer saw.
    """
    order = StoreOrder.objects.select_for_update().get(pk=payment.order_id)
    p = (
        StorePayment.objects.select_for_update()
        .select_related("order__store", "gateway")
        .get(pk=payment.pk)
    )
    if p.status == "paid":
        return p
    if order.status == "cancelled":
        raise ValidationError(
            "Cancelled order requires manual payment reconciliation."
        )

    # Confirm payment.
    p.status = "paid"
    p.save(update_fields=["status", "updated_at"])

    order.payment_status = "paid"
    if order.status == "pending":
        order.status = "confirmed"
    order.save(update_fields=["payment_status", "status", "updated_at"])

    # Ledger — recorded in the order's snapshot currency.
    wallet, _ = StoreWallet.objects.get_or_create(user=order.store.owner)
    if p.gateway.code == "cash":
        # COD: platform owes seller nothing until they collect; we only track
        # the commission the seller will owe the platform.
        kind = "commission_due"
        amount = -p.platform_commission
    else:
        kind = "sale_pending"
        amount = p.provider_amount

    StoreLedgerEntry.objects.get_or_create(
        wallet=wallet,
        order=order,
        kind=kind,
        defaults={"amount": amount, "currency": order.currency},
    )

    StoreOrderEvent.objects.create(
        order=order, status="paid", note="Payment verified"
    )
    notify(order.buyer, f"Payment confirmed: {str(order.pk)[:8]}")
    return p


# ============================================================
# CANCEL
# ============================================================

@transaction.atomic
def cancel_order(user, order_id):
    """
    Cancel a still-pending, unpaid order. Restores stock.
    Refuses if the order has a payment (needs staff reconciliation),
    or if it is past 'pending'.
    """
    order = (
        StoreOrder.objects.select_for_update()
        .select_related("store")
        .get(pk=order_id)
    )
    if order.buyer_id != user.pk and not user.is_staff:
        raise PermissionDenied()

    if order.status == "cancelled":
        return order

    # Refuse if payment exists, or if the order moved past pending.
    if hasattr(order, "payment") or order.status != "pending":
        raise ValidationError(
            "This order needs staff cancellation and payment reconciliation."
        )

    # Restore stock.
    for item in order.items.select_related("variant").order_by("variant_id"):
        StoreProductVariant.objects.filter(pk=item.variant_id).update(
            stock=F("stock") + item.quantity
        )
        StoreInventoryLog.objects.create(
            variant=item.variant,
            delta=item.quantity,
            reason=f"Cancelled {order.pk}",
            actor=user,
        )

    order.status = "cancelled"
    order.save(update_fields=["status", "updated_at"])
    StoreOrderEvent.objects.create(
        order=order, status="cancelled", actor=user
    )
    notify(order.buyer, f"Order cancelled: {str(order.pk)[:8]}")
    return order


# ============================================================
# STATUS TRANSITIONS (seller-side)
# ============================================================

@transaction.atomic
def change_order(user, order_id, status):
    """
    Seller-side state machine:
      confirmed → packing → shipped
      (delivery/cancel handled by delivery/cancel paths)
    Requires payment to be paid, or COD (cash) on file.
    """
    order = (
        StoreOrder.objects.select_for_update()
        .select_related("store")
        .get(pk=order_id)
    )
    if not can_manage(user, order.store):
        raise PermissionDenied()

    transitions = {
        "confirmed": "packing",
        "packing": "shipped",
    }
    if transitions.get(order.status) != status:
        raise ValidationError(
            f"Invalid order transition: {order.status} → {status}."
        )

    # Paid check (allow COD even if not yet collected).
    paid = order.payment_status == "paid"
    cod = hasattr(order, "payment") and order.payment.gateway.code == "cash"
    if not paid and not cod:
        raise ValidationError(
            "Payment is required before fulfillment."
        )

    order.status = status
    order.save(update_fields=["status", "updated_at"])

    if status == "packing":
        StoreDelivery.objects.get_or_create(
            order=order, defaults={"fee": order.shipping}
        )

    StoreOrderEvent.objects.create(
        order=order, status=status, actor=user
    )
    notify(order.buyer, f"Order {str(order.pk)[:8]}: {status}")
    return order