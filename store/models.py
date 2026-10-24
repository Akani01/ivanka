import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

U = settings.AUTH_USER_MODEL
MONEY = dict(max_digits=12, decimal_places=2)


def money(default="0.00"):
    return models.DecimalField(
        **MONEY, default=Decimal(default), validators=[MinValueValidator(0)]
    )


class Stamp(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StoreCategory(Stamp):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Store(Stamp):
    owner = models.OneToOneField(
        U, on_delete=models.PROTECT, related_name="seller_store"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=300)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    approved = models.BooleanField(default=False)
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    shipping_fee = money("65.00")

    def __str__(self):
        return self.name


class StoreStaff(Stamp):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(U, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "user"], name="unique_store_staff")
        ]


class StoreProduct(Stamp):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(StoreCategory, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class StoreProductVariant(Stamp):
    product = models.ForeignKey(
        StoreProduct, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=100, default="Standard")
    price = money()
    stock = models.PositiveIntegerField(default=0)
    weight_kg = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        default=Decimal("1.000"),
        validators=[MinValueValidator(0)],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="variant_price_positive"
            )
        ]


class StoreProductImage(Stamp):
    product = models.ForeignKey(
        StoreProduct, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/%Y/%m/")
    alt = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def save(self, *args, **kwargs):
        if (
            self.image
            and not self.image._committed
            and not getattr(self.image.file, "_ivanka_normalized", False)
        ):
            from .images import normalize_product_image

            self.image = normalize_product_image(self.image)
        super().save(*args, **kwargs)


class StoreInventoryLog(Stamp):
    variant = models.ForeignKey(StoreProductVariant, on_delete=models.PROTECT)
    delta = models.IntegerField()
    reason = models.CharField(max_length=200)
    actor = models.ForeignKey(U, null=True, on_delete=models.SET_NULL)


class StoreCart(Stamp):
    user = models.OneToOneField(U, on_delete=models.CASCADE)


class StoreCartItem(Stamp):
    cart = models.ForeignKey(StoreCart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(StoreProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(99)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"], name="unique_cart_variant"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=99),
                name="cart_quantity_range",
            ),
        ]


class StoreDeliveryAddress(Stamp):
    user = models.ForeignKey(
        U, on_delete=models.CASCADE, related_name="delivery_addresses"
    )
    recipient = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    line1 = models.CharField(max_length=250)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    place_id = models.CharField(max_length=250, blank=True)


class StoreCoupon(Stamp):
    code = models.CharField(max_length=30, unique=True)
    percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    minimum = money()
    expires_at = models.DateTimeField()
    max_uses = models.PositiveIntegerField(default=100)
    uses = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)


class StoreCheckout(Stamp):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(U, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    total = money()
    currency = models.CharField(max_length=3, default="ZAR")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "idempotency_key"], name="unique_buyer_checkout"
            )
        ]


class StoreOrder(Stamp):
    STATUSES = ["pending", "confirmed", "packing", "shipped", "delivered", "cancelled"]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkout = models.ForeignKey(
        StoreCheckout, on_delete=models.PROTECT, related_name="orders"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="orders")
    buyer = models.ForeignKey(U, on_delete=models.PROTECT, related_name="store_orders")
    currency = models.CharField(max_length=3, default="ZAR")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=1)
    address = models.JSONField()
    subtotal = money()
    shipping = money()
    discount = money()
    total = money()
    status = models.CharField(
        max_length=15, choices=[(s, s.title()) for s in STATUSES], default="pending"
    )
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    payment_status = models.CharField(max_length=15, default="unpaid")


class StoreOrderItem(Stamp):
    order = models.ForeignKey(
        StoreOrder, on_delete=models.PROTECT, related_name="items"
    )
    variant = models.ForeignKey(StoreProductVariant, on_delete=models.PROTECT)
    name = models.CharField(max_length=250)
    sku = models.CharField(max_length=80)
    unit_price = money()
    quantity = models.PositiveIntegerField()


class StoreOrderEvent(Stamp):
    order = models.ForeignKey(
        StoreOrder, on_delete=models.CASCADE, related_name="events"
    )
    status = models.CharField(max_length=30)
    note = models.CharField(max_length=250, blank=True)
    actor = models.ForeignKey(U, null=True, on_delete=models.SET_NULL)


class StoreCouponRedemption(Stamp):
    coupon = models.ForeignKey(StoreCoupon, on_delete=models.PROTECT)
    buyer = models.ForeignKey(U, on_delete=models.PROTECT)
    checkout = models.OneToOneField(StoreCheckout, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "buyer"], name="coupon_once_per_buyer"
            )
        ]


class StorePaymentGateway(Stamp):
    code = models.CharField(
        max_length=30,
        unique=True,
        choices=[("cash", "Cash on delivery"), ("yoco", "Yoco card")],
    )
    active = models.BooleanField(default=True)


class StorePayment(Stamp):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        StoreOrder, on_delete=models.PROTECT, related_name="payment"
    )
    gateway = models.ForeignKey(StorePaymentGateway, on_delete=models.PROTECT)
    payment_method = models.CharField(max_length=20)
    settlement_mode = models.CharField(max_length=20, default="platform_collects")
    currency = models.CharField(max_length=3, default="ZAR")
    gross_amount = money()
    platform_commission = money()
    provider_amount = money()
    status = models.CharField(max_length=20, default="pending")
    provider_id = models.CharField(max_length=150, blank=True)
    redirect_url = models.URLField(max_length=1000, blank=True)


class StorePaymentAttempt(Stamp):
    payment = models.ForeignKey(
        StorePayment, on_delete=models.PROTECT, related_name="attempts"
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, default="created")
    provider_id = models.CharField(max_length=150, blank=True)
    error = models.TextField(blank=True)


class StoreWebhookEvent(Stamp):
    event_id = models.CharField(max_length=150, unique=True)


class StoreWallet(Stamp):
    user = models.OneToOneField(U, on_delete=models.PROTECT)
    # Informational ledger only. No automatic bank payouts.


class StoreLedgerEntry(Stamp):
    wallet = models.ForeignKey(
        StoreWallet, on_delete=models.PROTECT, related_name="entries"
    )
    order = models.ForeignKey(StoreOrder, on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default="ZAR")
    kind = models.CharField(max_length=30)
    amount = models.DecimalField(**MONEY)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "order", "kind"], name="unique_ledger_posting"
            )
        ]


class StorePayoutProfile(Stamp):
    user = models.OneToOneField(U, on_delete=models.PROTECT)
    bank_name = models.CharField(max_length=100)
    account_holder = models.CharField(max_length=150)
    account_reference = models.CharField(
        max_length=150,
        help_text="Gateway recipient token; do not store raw banking credentials.",
    )


class StoreWishlist(Stamp):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_wishlist")
        ]


class StoreReview(Stamp):
    order_item = models.OneToOneField(
        StoreOrderItem, on_delete=models.PROTECT, related_name="review"
    )
    user = models.ForeignKey(U, on_delete=models.PROTECT)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=3000)


class StoreReturnRequest(Stamp):
    order_item = models.OneToOneField(
        StoreOrderItem, on_delete=models.PROTECT, related_name="return_request"
    )
    user = models.ForeignKey(U, on_delete=models.PROTECT)
    reason = models.TextField(max_length=3000)
    status = models.CharField(
        max_length=20,
        default="requested",
        choices=[
            (s, s.title())
            for s in ["requested", "approved", "rejected", "received", "refunded"]
        ],
    )
    resolution_note = models.TextField(blank=True)


class StoreCourierCompany(Stamp):
    owner = models.OneToOneField(
        U, on_delete=models.PROTECT, related_name="courier_company"
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class StoreCourierZone(Stamp):
    company = models.ForeignKey(
        StoreCourierCompany, on_delete=models.CASCADE, related_name="zones"
    )
    city = models.CharField(max_length=100)
    base_fee = money("45")
    per_km = money("3")
    radius_km = models.PositiveIntegerField(default=50)


class StoreDeliveryAgent(Stamp):
    user = models.OneToOneField(
        U, on_delete=models.PROTECT, related_name="delivery_agent"
    )
    company = models.ForeignKey(
        StoreCourierCompany, on_delete=models.PROTECT, related_name="agents"
    )
    vehicle = models.CharField(max_length=100)
    available = models.BooleanField(default=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    location_at = models.DateTimeField(null=True, blank=True)


class StoreDelivery(Stamp):
    order = models.OneToOneField(
        StoreOrder, on_delete=models.PROTECT, related_name="delivery"
    )
    company = models.ForeignKey(
        StoreCourierCompany, on_delete=models.PROTECT, null=True, blank=True
    )
    agent = models.ForeignKey(
        StoreDeliveryAgent, on_delete=models.PROTECT, null=True, blank=True
    )
    status = models.CharField(max_length=20, default="open")
    fee = money()


class StoreDeliveryBid(Stamp):
    delivery = models.ForeignKey(
        StoreDelivery, on_delete=models.CASCADE, related_name="bids"
    )
    company = models.ForeignKey(StoreCourierCompany, on_delete=models.PROTECT)
    amount = money()
    accepted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["delivery", "company"], name="unique_courier_bid"
            )
        ]


class StoreDeliveryEvent(Stamp):
    delivery = models.ForeignKey(
        StoreDelivery, on_delete=models.CASCADE, related_name="events"
    )
    status = models.CharField(max_length=30)
    actor = models.ForeignKey(U, null=True, on_delete=models.SET_NULL)


class StoreConversation(Stamp):
    order = models.OneToOneField(
        StoreOrder, on_delete=models.CASCADE, related_name="conversation"
    )


class StoreMessage(Stamp):
    conversation = models.ForeignKey(
        StoreConversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(U, on_delete=models.PROTECT)
    content = models.TextField(max_length=4000)


class StoreNotification(Stamp):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    read = models.BooleanField(default=False)


class StoreCurrency(Stamp):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=8)
    # Units of this currency per one catalog base-currency unit. Admin-maintained.
    rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.code
