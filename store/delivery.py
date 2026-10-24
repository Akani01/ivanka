from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import *
from .serializers import CourierSerializer, DeliverySerializer, LocationSerializer
from .services import can_order, can_manage, settle_payment, notify


def company_for(user):
    c = StoreCourierCompany.objects.filter(owner=user, approved=True).first()
    if not c:
        raise PermissionDenied("An approved courier account is required.")
    return c


class CourierView(APIView):
    def get(self, r):
        c = StoreCourierCompany.objects.filter(owner=r.user).first()
        return Response(CourierSerializer(c).data if c else None)

    def post(self, r):
        c = StoreCourierCompany.objects.filter(owner=r.user).first()
        s = CourierSerializer(c, data=r.data, partial=bool(c))
        s.is_valid(raise_exception=True)
        s.save(owner=r.user)
        return Response(s.data)


class AgentsView(APIView):
    def get(self, r):
        c = company_for(r.user)
        return Response(
            list(
                c.agents.values(
                    "id", "user_id", "user__username", "vehicle", "available"
                )
            )
        )

    def post(self, r):
        from django.contrib.auth import get_user_model

        c = company_for(r.user)
        u = get_object_or_404(get_user_model(), username=r.data.get("username"))
        # Staff assigns drivers after consent/onboarding; companies cannot seize user accounts.
        if not r.user.is_staff:
            raise PermissionDenied("Staff must assign a consenting driver in admin.")
        agent = StoreDeliveryAgent.objects.create(
            user=u, company=c, vehicle=str(r.data.get("vehicle", ""))[:100]
        )
        return Response({"id": agent.pk}, status=201)


class LocationView(APIView):
    def post(self, r):
        a = get_object_or_404(StoreDeliveryAgent, user=r.user, company__approved=True)
        if not StoreDelivery.objects.filter(
            agent=a, status__in=["assigned", "picked_up", "in_transit"]
        ).exists():
            raise ValidationError(
                "No active assigned delivery. Location sharing is stopped."
            )
        s = LocationSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        a.latitude = s.validated_data["latitude"]
        a.longitude = s.validated_data["longitude"]
        a.location_at = timezone.now()
        a.save()
        return Response({"success": True})


class JobsView(APIView):
    def get(self, r):
        c = StoreCourierCompany.objects.filter(owner=r.user, approved=True).first()
        agent = StoreDeliveryAgent.objects.filter(
            user=r.user, company__approved=True
        ).first()
        if not c and not agent and not r.user.is_staff:
            raise PermissionDenied("Approved courier or driver required.")
        q = StoreDelivery.objects.select_related("order").filter(
            order__status__in=["packing", "shipped"]
        )
        if c:
            q = q.filter(Q(status="open") | Q(company=c))
        elif agent:
            q = q.filter(agent=agent)
        return Response(DeliverySerializer(q.order_by("-created_at"), many=True).data)

    @transaction.atomic
    def post(self, r):
        c = company_for(r.user)
        d = get_object_or_404(
            StoreDelivery.objects.select_for_update(),
            pk=r.data.get("delivery"),
            status="open",
        )
        if d.order.status not in ["packing", "shipped"]:
            raise ValidationError("Order is not ready for delivery.")
        action = r.data.get("action", "claim")
        if action == "bid":
            try:
                amount = Decimal(str(r.data.get("amount")))
                if (
                    not amount.is_finite()
                    or amount <= 0
                    or amount > Decimal("9999999")
                    or amount.as_tuple().exponent < -2
                ):
                    raise ValueError()
            except Exception:
                raise ValidationError("Enter a positive bid with at most two decimals.")
            bid, _ = StoreDeliveryBid.objects.update_or_create(
                delivery=d, company=c, defaults={"amount": amount}
            )
            return Response({"id": bid.pk, "currency": d.order.currency})
        if action != "claim":
            raise ValidationError("Choose claim or bid.")
        d.company = c
        d.status = "assigned"
        d.save()
        StoreDeliveryEvent.objects.create(delivery=d, status="assigned", actor=r.user)
        return Response(DeliverySerializer(d).data)


class DeliveryView(APIView):
    def get(self, r, pk):
        d = get_object_or_404(
            StoreDelivery.objects.select_related(
                "order__store", "company", "agent__user"
            ),
            pk=pk,
        )
        if not can_order(r.user, d.order):
            raise PermissionDenied()
        a = d.agent
        fresh = bool(
            a
            and a.location_at
            and a.location_at > timezone.now() - timedelta(minutes=2)
            and d.status in ["assigned", "picked_up", "in_transit"]
        )
        lat = d.order.address.get("latitude")
        lng = d.order.address.get("longitude")
        destination = (
            f"{lat},{lng}"
            if lat and lng
            else ", ".join(
                str(d.order.address.get(k, ""))
                for k in ["line1", "city", "province", "postal_code"]
            )
        )
        data = {
            "delivery": DeliverySerializer(d).data,
            "destination": d.order.address,
            "driver": (
                {
                    "name": a.user.get_full_name() or a.user.username,
                    "latitude": a.latitude if fresh else None,
                    "longitude": a.longitude if fresh else None,
                    "fresh": fresh,
                }
                if a
                else None
            ),
            "events": list(
                d.events.order_by("created_at").values("status", "created_at")
            ),
            "navigation_url": "https://www.google.com/maps/dir/?"
            + urlencode(
                {"api": 1, "destination": destination, "travelmode": "driving"}
            ),
        }
        if can_manage(r.user, d.order.store):
            data["bids"] = list(
                d.bids.values("id", "company__name", "amount", "accepted")
            )
        return Response(data)

    @transaction.atomic
    def post(self, r, pk):
        d = get_object_or_404(
            StoreDelivery.objects.select_for_update().select_related(
                "order__store", "agent", "company"
            ),
            pk=pk,
        )
        action = r.data.get("action")
        if action == "accept_bid":
            if not can_manage(r.user, d.order.store):
                raise PermissionDenied()
            if d.status != "open":
                raise ValidationError("Delivery is already assigned.")
            bid = get_object_or_404(
                StoreDeliveryBid,
                pk=r.data.get("bid"),
                delivery=d,
                company__approved=True,
            )
            # Shipping charged to buyer stays fixed; do not silently raise it after checkout.
            if bid.amount > d.order.shipping:
                raise ValidationError("Bid exceeds the prepaid shipping budget.")
            bid.accepted = True
            bid.save()
            d.company = bid.company
            d.fee = bid.amount
            d.status = "assigned"
            d.save()
        elif action == "assign":
            if not d.company_id or (
                not r.user.is_staff and d.company.owner_id != r.user.pk
            ):
                raise PermissionDenied()
            if d.status != "assigned":
                raise ValidationError("Only assigned deliveries accept a driver.")
            a = get_object_or_404(
                StoreDeliveryAgent.objects.select_for_update(),
                pk=r.data.get("agent"),
                company=d.company,
                available=True,
            )
            if (
                StoreDelivery.objects.filter(
                    agent=a, status__in=["assigned", "picked_up", "in_transit"]
                )
                .exclude(pk=d.pk)
                .exists()
            ):
                raise ValidationError("Driver already has an active job.")
            d.agent = a
            d.save()
            a.available = False
            a.save()
        else:
            if not r.user.is_staff and (not d.agent_id or d.agent.user_id != r.user.pk):
                raise PermissionDenied()
            transitions = {
                "assigned": "picked_up",
                "picked_up": "in_transit",
                "in_transit": "delivered",
            }
            target = r.data.get("status")
            if transitions.get(d.status) != target:
                raise ValidationError("Invalid delivery transition.")
            if target == "picked_up" and d.order.status != "shipped":
                raise ValidationError("Seller must mark order shipped before pickup.")
            if (
                target == "delivered"
                and hasattr(d.order, "payment")
                and d.order.payment.gateway.code == "cash"
            ):
                if r.data.get("cash_collected") is not True:
                    raise ValidationError("Confirm that cash was collected.")
                settle_payment(d.order.payment)
            d.status = target
            d.save()
            if target == "delivered":
                d.order.status = "delivered"
                d.order.save(update_fields=["status", "updated_at"])
                if d.agent_id:
                    d.agent.available = True
                    d.agent.save()
                StoreOrderEvent.objects.create(
                    order=d.order, status="delivered", actor=r.user
                )
                notify(d.order.buyer, f"Delivered: {str(d.order_id)[:8]}")
                if d.company_id:
                    w, _ = StoreWallet.objects.get_or_create(user=d.company.owner)
                    StoreLedgerEntry.objects.get_or_create(
                        wallet=w,
                        order=d.order,
                        kind="courier_pending",
                        defaults={"currency": d.order.currency, "amount": d.fee},
                    )
                    sw, _ = StoreWallet.objects.get_or_create(user=d.order.store.owner)
                    StoreLedgerEntry.objects.get_or_create(
                        wallet=sw,
                        order=d.order,
                        kind="courier_cost",
                        defaults={"currency": d.order.currency, "amount": -d.fee},
                    )
        StoreDeliveryEvent.objects.create(delivery=d, status=d.status, actor=r.user)
        return Response(DeliverySerializer(d).data)


class ReverseGeocodeView(APIView):
    def get(self, r):
        s = LocationSerializer(
            data={
                "latitude": r.query_params.get("lat"),
                "longitude": r.query_params.get("lng"),
            }
        )
        s.is_valid(raise_exception=True)
        if not settings.GOOGLE_MAPS_API_KEY:
            return Response(
                {"detail": "Google Maps server key is not configured."}, status=503
            )
        p = s.validated_data
        try:
            res = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "latlng": f"{p['latitude']},{p['longitude']}",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                },
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("status") != "OK":
                raise ValueError()
            first = data["results"][0]
            return Response(
                {
                    "formatted_address": first["formatted_address"],
                    "place_id": first.get("place_id", ""),
                }
            )
        except (requests.RequestException, ValueError, KeyError, IndexError):
            return Response({"detail": "Could not resolve this location."}, status=502)


class RouteView(APIView):
    def get(self, r, pk):
        d = get_object_or_404(
            StoreDelivery.objects.select_related("order__store", "agent"), pk=pk
        )
        if not can_order(r.user, d.order):
            raise PermissionDenied()
        if not settings.GOOGLE_MAPS_API_KEY:
            return Response(
                {"detail": "Google Routes server key is not configured."}, status=503
            )
        a = d.agent
        if (
            not a
            or not a.location_at
            or a.location_at < timezone.now() - timedelta(minutes=2)
            or d.status not in ["assigned", "picked_up", "in_transit"]
        ):
            raise ValidationError("No fresh active driver location.")
        dest = d.order.address
        if not dest.get("latitude") or not dest.get("longitude"):
            raise ValidationError("Delivery address needs GPS coordinates.")
        body = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": float(a.latitude),
                        "longitude": float(a.longitude),
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": float(dest["latitude"]),
                        "longitude": float(dest["longitude"]),
                    }
                }
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
        }
        try:
            result = requests.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                json=body,
                headers={
                    "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
                    "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
                },
                timeout=10,
            )
            result.raise_for_status()
            return Response(result.json())
        except (requests.RequestException, ValueError):
            return Response({"detail": "Route unavailable."}, status=502)
