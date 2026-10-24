# store/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .delivery import (
    CourierView, AgentsView, JobsView,
    LocationView, DeliveryView, RouteView, ReverseGeocodeView,
)

router = DefaultRouter()
router.register("products",  views.ProductViewSet,  basename="product")
router.register("addresses", views.AddressViewSet,  basename="address")
router.register("orders",    views.OrderViewSet,    basename="order")

urlpatterns = [
    # ---- the single page ----
    path("", views.home, name="store_home"),

    # ---- API ----
    path("api/", include(router.urls)),
    path("api/config/", views.ConfigView.as_view(), name="api_config"),
    path("api/cart/", views.CartView.as_view(), name="api_cart"),
    path("api/checkout/", views.CheckoutView.as_view(), name="api_checkout"),
    path("api/seller/", views.SellerView.as_view(), name="api_seller"),
    path("api/wishlist/", views.WishlistView.as_view(), name="api_wishlist"),
    path("api/wallet/", views.WalletView.as_view(), name="api_wallet"),
    path("api/notifications/", views.NotificationsView.as_view(), name="api_notifications"),
    path("api/feedback/<str:kind>/", views.ReviewReturnView.as_view(), name="api_feedback"),
    path("api/payments/yoco/webhook/", views.yoco_webhook, name="api_yoco_webhook"),
    path("api/courier/", CourierView.as_view(), name="api_courier"),
    path("api/courier/agents/", AgentsView.as_view(), name="api_courier_agents"),
    path("api/courier/jobs/", JobsView.as_view(), name="api_courier_jobs"),
    path("api/delivery/location/", LocationView.as_view(), name="api_delivery_location"),
    path("api/delivery/<int:pk>/track/", DeliveryView.as_view(), name="api_delivery_track"),
    path("api/delivery/<int:pk>/route/", RouteView.as_view(), name="api_delivery_route"),
    path("api/geocode/reverse/", ReverseGeocodeView.as_view(), name="api_geocode_reverse"),
]