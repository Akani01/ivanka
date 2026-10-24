# store/serializers.py
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Avg
from rest_framework import serializers

from .models import (
    StoreCategory, StoreProductImage, StoreProductVariant, StoreProduct,
    StoreDeliveryAddress, Store, StoreCourierCompany,
    StorePayment, StoreOrderItem, StoreOrder, StoreDelivery, StoreReview,
)
from .services import currency, rounded, catalog_currency


# ============================================================
# HELPERS
# ============================================================

def _rate_for(context, code=None):
    """
    Resolve rate for a currency code (fallback to base with rate=1).
    Never raises — a bad/unknown code resolves to the base currency.
    """
    base = catalog_currency()
    if not code:
        return Decimal("1")
    try:
        _, rate = currency(code)
        return rate
    except Exception:
        return Decimal("1")


def _display(value, rate):
    """Convert a base amount to a display amount."""
    return str(rounded(Decimal(str(value or 0)) * rate))


# ============================================================
# CATEGORY / IMAGES
# ============================================================

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreCategory
        fields = ["id", "name", "slug", "parent"]


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreProductImage
        fields = ["id", "image", "alt", "position"]


# ============================================================
# PRODUCTS / VARIANTS
# ============================================================

class VariantSerializer(serializers.ModelSerializer):
    """
    `price` is always the base currency (ZAR) price.
    `display_price` is converted to the currency set in context
    (or the base currency if none).
    """
    display_price = serializers.SerializerMethodField()

    def get_display_price(self, obj):
        code = self.context.get("currency")
        rate = _rate_for(self.context, code)
        return _display(obj.price, rate)

    class Meta:
        model = StoreProductVariant
        fields = [
            "id", "sku", "label",
            "price",                 # base currency
            "display_price",         # buyer's currency
            "stock", "weight_kg",
        ]


class ProductSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    variants = VariantSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    rating = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    def get_rating(self, obj):
        return StoreReview.objects.filter(
            order_item__variant__product=obj
        ).aggregate(value=Avg("rating"))["value"]

    def get_currency(self, obj):
        return (self.context.get("currency") or catalog_currency()).upper()

    class Meta:
        model = StoreProduct
        fields = [
            "id", "store", "store_name", "category",
            "name", "brand", "description",
            "active", "featured",
            "images", "variants", "rating", "currency",
        ]
        read_only_fields = ["store", "featured"]


# ============================================================
# ADDRESSES
# ============================================================

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreDeliveryAddress
        exclude = ["user", "created_at", "updated_at"]

    def validate(self, data):
        lat = data.get("latitude")
        lng = data.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                "Latitude and longitude must be supplied together."
            )
        return data


# ============================================================
# STORE / COURIER
# ============================================================

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "id", "name", "description", "address",
            "latitude", "longitude",
            "approved", "shipping_fee",
        ]
        read_only_fields = ["approved"]

    def validate_latitude(self, v):
        if v is not None and not -90 <= v <= 90:
            raise serializers.ValidationError("Invalid latitude.")
        return v

    def validate_longitude(self, v):
        if v is not None and not -180 <= v <= 180:
            raise serializers.ValidationError("Invalid longitude.")
        return v


class CourierSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreCourierCompany
        fields = ["id", "name", "phone", "approved"]
        read_only_fields = ["approved"]


# ============================================================
# PAYMENT
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):
    """
    Payment amounts are ALWAYS in the payment gateway's currency
    (`self.currency`). Yoco is ZAR-only.
    `display_currency` / `display_amount` show the buyer's chosen currency
    snapshot for reference.
    """
    gateway_code = serializers.CharField(source="gateway.code")
    display_currency = serializers.SerializerMethodField()
    display_amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    def get_display_currency(self, obj):
        try:
            return obj.order.currency
        except Exception:
            return obj.currency

    def get_display_amount(self, obj):
        try:
            rate = obj.order.exchange_rate or Decimal("1")
            return str(rounded(Decimal(str(obj.gross_amount or 0)) * rate))
        except Exception:
            return str(obj.gross_amount or 0)

    def get_currency_symbol(self, obj):
        from .models import StoreCurrency
        try:
            return obj.order.currency_symbol
        except Exception:
            row = StoreCurrency.objects.filter(code=obj.currency).first()
            return row.symbol if row else obj.currency

    class Meta:
        model = StorePayment
        fields = [
            "id", "gateway_code", "payment_method",
            "currency",                   # charge currency (Yoco: ZAR)
            "gross_amount",               # charge amount in that currency
            "platform_commission",
            "provider_amount",
            "settlement_mode", "status",
            "display_currency",           # buyer's currency
            "display_amount",             # buyer's amount
            "currency_symbol",
            "redirect_url",
        ]


# ============================================================
# ORDER ITEMS / ORDERS
# ============================================================

class OrderItemSerializer(serializers.ModelSerializer):
    display_unit_price = serializers.SerializerMethodField()
    display_line_total = serializers.SerializerMethodField()

    def _order(self, obj):
        return getattr(obj, "order", None)

    def _rate(self, obj):
        order = self._order(obj)
        if order and order.exchange_rate:
            return Decimal(str(order.exchange_rate))
        return Decimal("1")

    def get_display_unit_price(self, obj):
        return _display(obj.unit_price, self._rate(obj))

    def get_display_line_total(self, obj):
        return _display(
            Decimal(str(obj.unit_price or 0)) * obj.quantity,
            self._rate(obj),
        )

    class Meta:
        model = StoreOrderItem
        fields = [
            "id", "name", "sku",
            "unit_price",             # base currency
            "quantity",
            "display_unit_price",     # buyer's currency
            "display_line_total",     # buyer's currency
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    payment = PaymentSerializer(read_only=True)
    events = serializers.SerializerMethodField()
    delivery_id = serializers.SerializerMethodField()

    # Display (buyer-currency) mirror fields
    display_subtotal = serializers.SerializerMethodField()
    display_shipping = serializers.SerializerMethodField()
    display_discount = serializers.SerializerMethodField()
    display_total = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    def get_events(self, obj):
        return list(
            obj.events.order_by("created_at").values(
                "status", "note", "created_at"
            )
        )

    def get_delivery_id(self, obj):
        d = StoreDelivery.objects.filter(order=obj).first()
        return d.pk if d else None

    def _rate(self, obj):
        return Decimal(str(obj.exchange_rate or 1))

    def get_display_subtotal(self, obj):
        return _display(obj.subtotal, self._rate(obj))

    def get_display_shipping(self, obj):
        return _display(obj.shipping, self._rate(obj))

    def get_display_discount(self, obj):
        return _display(obj.discount, self._rate(obj))

    def get_display_total(self, obj):
        return _display(obj.total, self._rate(obj))

    def get_currency_symbol(self, obj):
        return obj.currency_symbol  # property on the model

    class Meta:
        model = StoreOrder
        fields = [
            "id", "store_name", "buyer",
            "currency",                  # buyer's snapshot code
            "currency_symbol",
            "exchange_rate",
            "address",
            "subtotal",                  # base currency
            "shipping",                  # base currency
            "discount",                  # base currency
            "total",                     # base currency
            "display_subtotal",          # buyer's currency
            "display_shipping",          # buyer's currency
            "display_discount",          # buyer's currency
            "display_total",             # buyer's currency
            "status", "payment_status",
            "items", "payment", "events",
            "delivery_id", "created_at",
        ]


# ============================================================
# CHECKOUT INPUT
# ============================================================

class CheckoutSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.UUIDField()
    currency = serializers.CharField(
        max_length=3, required=False,
        default=catalog_currency,
    )
    coupon = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default="",
    )

    def validate_currency(self, value):
        """
        Ensure the requested currency is enabled. Empty → base currency.
        """
        base = catalog_currency()
        if not value:
            return base
        code = value.strip().upper()
        if code == base:
            return base
        try:
            resolved_code, _ = currency(code)
        except Exception:
            raise serializers.ValidationError(
                f"Currency {code} is not enabled."
            )
        return resolved_code

    def validate_coupon(self, value):
        return (value or "").strip().upper()


# ============================================================
# PAY INPUT
# ============================================================

class PayInputSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=["cash", "card"])
    gateway_code = serializers.ChoiceField(choices=["cash", "yoco"])

    def validate(self, data):
        # Card must go through Yoco; cash must go through cash.
        if data["payment_method"] == "card" and data["gateway_code"] != "yoco":
            raise serializers.ValidationError(
                "Card payments must use the 'yoco' gateway."
            )
        if data["payment_method"] == "cash" and data["gateway_code"] != "cash":
            raise serializers.ValidationError(
                "Cash payments must use the 'cash' gateway."
            )
        return data


# ============================================================
# DELIVERY / GEO
# ============================================================

class LocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7,
        min_value=Decimal("-90"), max_value=Decimal("90"),
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7,
        min_value=Decimal("-180"), max_value=Decimal("180"),
    )


class DeliverySerializer(serializers.ModelSerializer):
    order_reference = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    currency = serializers.CharField(source="order.currency")
    display_fee = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    def get_order_reference(self, obj):
        return str(obj.order_id)[:8]

    def get_city(self, obj):
        return (obj.order.address or {}).get("city", "")

    def get_display_fee(self, obj):
        rate = Decimal(str(obj.order.exchange_rate or 1))
        return _display(obj.fee, rate)

    def get_currency_symbol(self, obj):
        try:
            return obj.order.currency_symbol
        except Exception:
            return obj.order.currency

    class Meta:
        model = StoreDelivery
        fields = [
            "id", "order_reference", "city",
            "currency", "currency_symbol",
            "company", "agent",
            "status",
            "fee",                 # base currency
            "display_fee",         # buyer's currency
        ]