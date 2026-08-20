from django.urls import path

from apps.promotions import views

urlpatterns = [
    path("vouchers/redeem", views.redeem, name="voucher-redeem"),
]
