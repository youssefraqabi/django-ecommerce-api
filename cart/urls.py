from django.urls import path

from .views import (
    CartDetailView,
    AddToCartView,
    UpdateCartItemView,
    DeleteCartItemView,
)

urlpatterns = [
    path(
        "",
        CartDetailView.as_view(),
        name="cart-detail",
    ),
    path(
        "items/",
        AddToCartView.as_view(),
        name="cart-add-item",
    ),
    
    path(
    "items/<int:pk>/",
    UpdateCartItemView.as_view(),
    name="cart-update-item",
),
    
    path(
    "items/<int:pk>/delete/",
    DeleteCartItemView.as_view(),
    name="cart-delete-item",
),
    
]