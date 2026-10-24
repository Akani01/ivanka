from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Property, PropertyAnalytics


@receiver(post_save, sender=Property)
def ensure_property_analytics(sender, instance, **kwargs):
    """Ensure every saved property has a PropertyAnalytics row."""
    PropertyAnalytics.objects.get_or_create(property=instance)
