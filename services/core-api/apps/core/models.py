import uuid

from django.db import models


class UUIDTimeStampedModel(models.Model):
    """Base for every business entity.

    Public identifiers are UUIDs so that sequential ids never leak volumes, and
    every row carries UTC timestamps (cahier des charges §9).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
