from django.contrib import admin
from django import forms
from django.conf import settings
from . import models as m

admin.site.site_header = "Ivanka administration"
admin.site.site_title = "Ivanka"
admin.site.index_title = "Marketplace operations"


@admin.register(m.Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "approved", "commission_percent"]
    list_filter = ["approved"]
    search_fields = ["name", "owner__username"]


@admin.register(m.StoreCourierCompany)
class CourierAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "approved"]
    list_filter = ["approved"]


class CurrencyForm(forms.ModelForm):
    class Meta:
        model = m.StoreCurrency
        fields = "__all__"

    def clean(self):
        data = super().clean()
        code = data.get("code", "").upper()
        data["code"] = code
        if code not in [
            "ZAR",
            "USD",
            "EUR",
            "GBP",
            "NAD",
            "BWP",
            "SZL",
            "LSL",
            "AUD",
            "CAD",
            "CHF",
            "NZD",
            "KES",
            "GHS",
            "NGN",
            "ZMW",
            "MZN",
            "CNY",
            "INR",
            "AED",
        ]:
            raise forms.ValidationError(
                "Use a supported two-decimal ISO currency code. Add new currency minor-unit handling before extending this list."
            )
        if code == settings.CATALOG_CURRENCY and data.get("rate") != 1:
            raise forms.ValidationError("Catalog base currency must have rate 1.")
        return data


@admin.register(m.StoreCurrency)
class CurrencyAdmin(admin.ModelAdmin):
    form = CurrencyForm
    list_display = ["code", "name", "rate", "enabled", "updated_at"]


@admin.register(m.StoreOrder)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "store",
        "buyer",
        "currency",
        "total",
        "status",
        "payment_status",
    ]
    list_filter = ["status", "currency"]
    readonly_fields = [f.name for f in m.StoreOrder._meta.fields]

    def has_add_permission(self, r):
        return False

    def has_delete_permission(self, r, obj=None):
        return False


class FinancialAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, r, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, r):
        return False

    def has_delete_permission(self, r, obj=None):
        return False


for model in [
    m.StorePayment,
    m.StorePaymentAttempt,
    m.StoreWebhookEvent,
    m.StoreLedgerEntry,
    m.StoreCheckout,
    m.StoreOrderItem,
    m.StoreInventoryLog,
    m.StoreCouponRedemption,
]:
    admin.site.register(model, FinancialAdmin)
# Returns are staff-managed. 'refunded' is a reconciliation record, not a gateway refund.
for name in [
    "StoreCategory",
    "StoreStaff",
    "StoreProduct",
    "StoreProductVariant",
    "StoreCart",
    "StoreCartItem",
    "StoreDeliveryAddress",
    "StoreCoupon",
    "StoreWallet",
    "StorePayoutProfile",
    "StoreWishlist",
    "StoreReview",
    "StoreReturnRequest",
    "StoreCourierZone",
    "StoreDeliveryAgent",
    "StoreDeliveryBid",
    "StoreConversation",
    "StoreMessage",
    "StoreNotification",
    "StorePaymentGateway",
]:
    admin.site.register(getattr(m, name))
# Delivery is read-only in admin: use authenticated transition endpoints for audit/settlement.
admin.site.register(m.StoreDelivery, FinancialAdmin)
admin.site.register(m.StoreDeliveryEvent, FinancialAdmin)
admin.site.register(m.StoreOrderEvent, FinancialAdmin)


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = m.StoreProductImage
        fields = "__all__"

    def clean_image(self):
        from .images import normalize_product_image
        from rest_framework.exceptions import ValidationError

        image = self.cleaned_data.get("image")
        if not image or not hasattr(image, "content_type"):
            return image
        try:
            return normalize_product_image(image)
        except ValidationError as exc:
            raise forms.ValidationError(str(exc.detail))


@admin.register(m.StoreProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    form = ProductImageForm
    list_display = ["product", "alt", "position"]
