from django.urls import path

from .api import AssignGroupView, DisconnectView

app_name = "dakar_radius_ext"

urlpatterns = [
    path("radius/assign-group/", AssignGroupView.as_view(), name="assign_group"),
    path("radius/disconnect/", DisconnectView.as_view(), name="disconnect"),
]
