import json, uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.urls import reverse
from django.templatetags.static import static
from .public_pages import site_context
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import *
from .serializers import *
from .services import (
    checkout,
    can_manage,
    can_order,
    currency,
    rounded,
    seller_for,
    change_order,
    cancel_order,
    settle_payment,
    notify,
)
from .payments.registry import initialize_payment, verify_signature


@ensure_csrf_cookie
def home(request):
    context = site_context()
    context["maps_key"] = getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", "")
    return render(request, "store.html", context)


def manifest(request):
    return JsonResponse(
        {
            "id": reverse("store_home"),
            "name": "Ivanka & Stell Closet",
            "short_name": "Ivanka",
            "start_url": reverse("store_home"),
            "scope": reverse("store_home"),
            "display": "standalone",
            "background_color": "#F5F5F5",
            "theme_color": "#0A0A0A",
            "icons": [
                {
                    "src": static("store/icon-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": static("store/icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                },
            ],
        }
    )


def service_worker(request):
    from django.contrib.staticfiles import finders
    worker = finders.find("store/sw.js")
    if not worker:
        raise Http404("Store service worker not found.")
    from pathlib import Path
    script = Path(worker).read_text(encoding="utf-8")
    script = script.replace("__OFFLINE_URL__", json.dumps(reverse("store_offline")))
    response = HttpResponse(script, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = reverse("store_home")
    return response


def assetlinks(request):
    p = settings.BASE_DIR / "assetlinks.json"
    if not p.exists():
        raise Http404("Configure Ivanka Android association first.")
    return FileResponse(open(p, "rb"), content_type="application/json")


class ConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, r):
        rows = list(
            StoreCurrency.objects.filter(enabled=True).values(
                "code", "name", "symbol", "rate", "updated_at"
            )
        )
        if not any(x["code"] == settings.CATALOG_CURRENCY for x in rows):
            rows.insert(
                0,
                {
                    "code": settings.CATALOG_CURRENCY,
                    "name": settings.CATALOG_CURRENCY,
                    "symbol": settings.CATALOG_CURRENCY,
                    "rate": "1",
                },
            )
        return Response(
            {
                "name": "Ivanka",
                "image_background_removal": settings.PRODUCT_REMOVE_BACKGROUND,
                "catalog_currency": settings.CATALOG_CURRENCY,
                "currencies": rows,
                "yoco_configured": bool(settings.YOCO_SECRET_KEY),
                "categories": CategorySerializer(
                    StoreCategory.objects.all(), many=True
                ).data,
            }
        )


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        return (
            [AllowAny()] if self.action in ["list", "retrieve"] else [IsAuthenticated()]
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["currency"] = self.request.query_params.get(
            "currency", settings.CATALOG_CURRENCY
        )
        currency(ctx["currency"])
        return ctx

    def get_queryset(self):
        q = (
            StoreProduct.objects.select_related("store", "category")
            .prefetch_related("variants", "images")
            .order_by("-featured", "-created_at")
        )
        if self.action not in ["list", "retrieve"]:
            return q
        if self.request.query_params.get("mine") == "1":
            if not self.request.user.is_authenticated:
                return q.none()
            return q.filter(
                Q(store__owner=self.request.user)
                | Q(store__staff__user=self.request.user)
            ).distinct()
        q = q.filter(active=True, store__approved=True)
        search = self.request.query_params.get("search", "")
        if search:
            q = q.filter(
                Q(name__icontains=search)
                | Q(brand__icontains=search)
                | Q(description__icontains=search)
            )
        cat = self.request.query_params.get("category")
        if cat:
            try:
                q = q.filter(category_id=int(cat))
            except ValueError:
                raise ValidationError("Invalid category.")
        if self.request.query_params.get("in_stock") == "1":
            q = q.filter(variants__stock__gt=0)
        _, rate = currency(
            self.request.query_params.get("currency", settings.CATALOG_CURRENCY)
        )
        for param, lookup in [
            ("min_price", "variants__price__gte"),
            ("max_price", "variants__price__lte"),
        ]:
            if param in self.request.query_params:
                try:
                    n = Decimal(self.request.query_params[param])
                    if not n.is_finite() or n < 0:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    raise ValidationError("Invalid price filter.")
                q = q.filter(**{lookup: n / rate})
        return q.distinct()

    def perform_create(self, s):
        s.save(store=seller_for(self.request.user))

    def perform_update(self, s):
        if not can_manage(self.request.user, s.instance.store):
            raise PermissionDenied()
        s.save()

    def perform_destroy(self, obj):
        if not can_manage(self.request.user, obj.store):
            raise PermissionDenied()
        obj.active = False
        obj.save(update_fields=["active", "updated_at"])

    @action(detail=True, methods=["post"])
    def variant(self, r, pk=None):
        p = self.get_object()
        if not can_manage(r.user, p.store):
            raise PermissionDenied()
        with transaction.atomic():
            obj = None
            if r.data.get("id"):
                obj = get_object_or_404(
                    StoreProductVariant.objects.select_for_update(),
                    pk=r.data["id"],
                    product=p,
                )
            s = VariantSerializer(
                obj, data=r.data, context=self.get_serializer_context()
            )
            s.is_valid(raise_exception=True)
            before = obj.stock if obj else 0
            obj = s.save(product=p)
            if obj.stock != before:
                StoreInventoryLog.objects.create(
                    variant=obj,
                    delta=obj.stock - before,
                    reason="Seller stock update",
                    actor=r.user,
                )
        return Response(s.data, status=201)

    @action(detail=True, methods=["post"])
    def image(self, r, pk=None):
        p = self.get_object()
        if not can_manage(r.user, p.store):
            raise PermissionDenied()
        if p.images.count() >= 8:
            raise ValidationError("Maximum eight images per product.")
        s = ImageSerializer(data=r.data, context={"request": r})
        s.is_valid(raise_exception=True)
        s.save(product=p)
        return Response(s.data, status=201)


class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def get_queryset(self):
        return StoreDeliveryAddress.objects.filter(user=self.request.user).order_by(
            "-created_at", "-id"
        )

    def perform_create(self, s):
        s.save(user=self.request.user)


class CartView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, r):
        code, rate = currency(r.query_params.get("currency", settings.CATALOG_CURRENCY))
        cart, _ = StoreCart.objects.get_or_create(user=r.user)
        lines = []
        for item in cart.items.select_related(
            "variant__product__store"
        ).prefetch_related("variant__product__images"):
            v = item.variant
            p = v.product
            image = p.images.first()
            lines.append(
                {
                    "id": item.pk,
                    "variant": v.pk,
                    "name": p.name,
                    "label": v.label,
                    "quantity": item.quantity,
                    "stock": v.stock,
                    "price": str(rounded(v.price * rate)),
                    "store_name": p.store.name,
                    "image": r.build_absolute_uri(image.image.url) if image else "",
                }
            )
        return Response(
            {
                "items": lines,
                "currency": code,
                "subtotal": str(
                    sum(Decimal(l["price"]) * l["quantity"] for l in lines)
                ),
            }
        )

    @transaction.atomic
    def post(self, r):
        from django.contrib.auth import get_user_model

        get_user_model().objects.select_for_update().get(pk=r.user.pk)
        try:
            quantity = int(r.data.get("quantity", 1))
            vid = int(r.data.get("variant", 0))
        except (TypeError, ValueError):
            raise ValidationError("Invalid quantity or variant.")
        if quantity < 0 or quantity > 99:
            raise ValidationError("Quantity must be 0 to 99.")
        variant = get_object_or_404(
            StoreProductVariant,
            pk=vid,
            product__active=True,
            product__store__approved=True,
        )
        if quantity > variant.stock:
            raise ValidationError("Not enough stock.")
        cart, _ = StoreCart.objects.get_or_create(user=r.user)
        if quantity:
            StoreCartItem.objects.update_or_create(
                cart=cart, variant=variant, defaults={"quantity": quantity}
            )
        else:
            StoreCartItem.objects.filter(cart=cart, variant=variant).delete()
        return Response({"success": True})


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, r):
        s = CheckoutSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        obj = checkout(
            r.user, d["address_id"], d["idempotency_key"], d["currency"], d["coupon"]
        )
        return Response(
            {
                "id": obj.pk,
                "currency": obj.currency,
                "total": obj.total,
                "orders": OrderSerializer(obj.orders.all(), many=True).data,
            },
            status=201,
        )


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        q = (
            StoreOrder.objects.select_related("store", "buyer", "payment__gateway")
            .prefetch_related("items", "events")
            .order_by("-created_at")
        )
        if self.request.user.is_staff:
            return q
        return q.filter(
            Q(buyer=self.request.user)
            | Q(store__owner=self.request.user)
            | Q(store__staff__user=self.request.user)
        ).distinct()

    @action(detail=True, methods=["post"])
    def pay(self, r, pk=None):
        obj = self.get_object()
        if obj.buyer_id != r.user.pk:
            raise PermissionDenied()
        s = PayInputSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        p = initialize_payment(
            r.user,
            obj.pk,
            **{
                "method": s.validated_data["payment_method"],
                "code": s.validated_data["gateway_code"],
            }
        )
        return Response(
            {
                "success": True,
                "payment": PaymentSerializer(p).data,
                "redirect_url": p.redirect_url,
                "reference": p.provider_id,
            }
        )

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, r, pk=None):
        obj = self.get_object()
        return Response(
            OrderSerializer(change_order(r.user, obj.pk, r.data.get("status"))).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, r, pk=None):
        obj = self.get_object()
        return Response(OrderSerializer(cancel_order(r.user, obj.pk)).data)

    @action(detail=True, methods=["get", "post"])
    def messages(self, r, pk=None):
        obj = self.get_object()
        con, _ = StoreConversation.objects.get_or_create(order=obj)
        if r.method == "POST":
            content = str(r.data.get("content", "")).strip()
            if not content or len(content) > 4000:
                raise ValidationError("Message must be 1–4000 characters.")
            StoreMessage.objects.create(
                conversation=con, sender=r.user, content=content
            )
        return Response(
            list(
                con.messages.order_by("-created_at").values(
                    "id", "sender__username", "content", "created_at"
                )[:100]
            )
        )


class SellerView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, r):
        s = Store.objects.filter(owner=r.user).first()
        return Response(StoreSerializer(s).data if s else None)

    def post(self, r):
        s = Store.objects.filter(owner=r.user).first()
        ser = StoreSerializer(s, data=r.data, partial=bool(s))
        ser.is_valid(raise_exception=True)
        ser.save(owner=r.user)
        return Response(ser.data)


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, r):
        ids = StoreWishlist.objects.filter(user=r.user).values_list(
            "product_id", flat=True
        )
        products = StoreProduct.objects.filter(
            pk__in=ids, active=True, store__approved=True
        )
        return Response(
            ProductSerializer(
                products,
                many=True,
                context={
                    "request": r,
                    "currency": r.query_params.get(
                        "currency", settings.CATALOG_CURRENCY
                    ),
                },
            ).data
        )

    def post(self, r):
        p = get_object_or_404(
            StoreProduct, pk=r.data.get("product"), active=True, store__approved=True
        )
        w, created = StoreWishlist.objects.get_or_create(user=r.user, product=p)
        if not created:
            w.delete()
        return Response({"saved": created})


class ReviewReturnView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, r, kind):
        item = get_object_or_404(
            StoreOrderItem,
            pk=r.data.get("order_item"),
            order__buyer=r.user,
            order__status="delivered",
        )
        if kind == "review":
            try:
                rating = int(r.data.get("rating", 0))
            except (ValueError, TypeError):
                raise ValidationError("Choose 1–5 stars.")
            if not 1 <= rating <= 5:
                raise ValidationError("Choose 1–5 stars.")
            text = str(r.data.get("comment", "")).strip()
            if not text or len(text) > 3000:
                raise ValidationError("Enter a comment up to 3000 characters.")
            obj, _ = StoreReview.objects.update_or_create(
                order_item=item,
                user=r.user,
                defaults={"rating": rating, "comment": text},
            )
        elif kind == "return":
            reason = str(r.data.get("reason", "")).strip()
            if not reason or len(reason) > 3000:
                raise ValidationError("Enter a return reason up to 3000 characters.")
            obj, _ = StoreReturnRequest.objects.get_or_create(
                order_item=item, user=r.user, defaults={"reason": reason}
            )
        else:
            return Response(status=404)
        return Response({"id": obj.pk}, status=201)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, r):
        entries = StoreLedgerEntry.objects.filter(wallet__user=r.user)
        return Response(
            {
                "balances": list(
                    entries.values("currency", "kind").annotate(amount=Sum("amount"))
                ),
                "entries": list(
                    entries.order_by("-created_at").values(
                        "order_id", "currency", "kind", "amount", "created_at"
                    )[:100]
                ),
                "note": "Accounting records only. Bank payouts and refunds are reconciled by staff.",
            }
        )


class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, r):
        return Response(
            list(
                StoreNotification.objects.filter(user=r.user)
                .order_by("-created_at")
                .values("id", "title", "read", "created_at")[:50]
            )
        )

    def post(self, r):
        StoreNotification.objects.filter(user=r.user, pk=r.data.get("id")).update(
            read=True
        )
        return Response({"success": True})


@csrf_exempt
def yoco_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    if not verify_signature(request.body, request.headers):
        return JsonResponse({"detail": "Invalid signature"}, status=403)
    try:
        event = json.loads(request.body)
        if event.get("type") != "payment.succeeded":
            return JsonResponse({"received": True})
        payload = event["payload"]
        checkout_id = payload["metadata"]["checkoutId"]
        with transaction.atomic():
            lookup = StorePayment.objects.get(
                provider_id=checkout_id, gateway__code="yoco"
            )
            StoreOrder.objects.select_for_update().get(pk=lookup.order_id)
            p = (
                StorePayment.objects.select_for_update()
                .select_related("gateway")
                .get(pk=lookup.pk)
            )
            if (
                payload.get("status") != "succeeded"
                or p.gateway.code != "yoco"
                or p.currency != payload.get("currency")
                or int(p.gross_amount * 100) != payload.get("amount")
                or p.provider_id != payload.get("metadata", {}).get("checkoutId")
            ):
                return JsonResponse({"detail": "Payment mismatch"}, status=400)
            eid = event.get("id") or request.headers["webhook-id"]
            _, created = StoreWebhookEvent.objects.get_or_create(event_id=eid)
            if created:
                settle_payment(p)
        return JsonResponse({"received": True})
    except (ValueError, KeyError, TypeError, StorePayment.DoesNotExist):
        return JsonResponse({"detail": "Invalid event"}, status=400)


# store/views.py — page views

def shop_page(request):
    return render(request, "store/shop.html", {"page_title": "Shop · Ivanka"})

def product_page(request, pk):
    return render(request, "store/product.html", {"product_id": pk})

def cart_page(request):
    return render(request, "store/cart.html", {"page_title": "Cart · Ivanka"})

def checkout_page(request):
    return render(request, "store/checkout.html", {"page_title": "Checkout · Ivanka"})

def orders_page(request):
    return render(request, "store/orders.html", {"page_title": "My Orders · Ivanka"})

def order_page(request, pk):
    return render(request, "store/order.html", {"order_id": pk})

def seller_dashboard(request):
    return render(request, "store/seller.html", {"page_title": "Seller · Ivanka"})

def wishlist_page(request):
    return render(request, "store/wishlist.html", {"page_title": "Wishlist · Ivanka"})

def wallet_page(request):
    return render(request, "store/wallet.html", {"page_title": "Wallet · Ivanka"})

def notifications_page(request):
    return render(request, "store/notifications.html", {"page_title": "Notifications · Ivanka"})

def courier_page(request):
    return render(request, "store/courier.html", {"page_title": "Courier · Ivanka"})

def delivery_page(request, pk):
    return render(request, "store/delivery.html", {"delivery_id": pk})
