from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.incidents.lifecycle import sync_hotspot_incidents
from apps.network.models import Hotspot


@receiver(post_save, sender=Hotspot)
def open_incident_when_hotspot_fails(sender, instance, **kwargs):
    sync_hotspot_incidents(instance)
