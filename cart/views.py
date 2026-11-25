from django.db import transaction

from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    AddToCartSerializer,
    CartItemSerializer,
    UpdateCartItemSerializer
)


class CartDetailView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(
            user=self.request.user
        )

        return Cart.objects.prefetch_related(
            "items__product"
        ).get(pk=cart.pk)


class AddToCartView(generics.CreateAPIView):
    serializer_class = AddToCartSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data["product"]
        quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            cart, _ = Cart.objects.select_for_update().get_or_create(
                user=request.user
            )

            product.refresh_from_db()

            item = CartItem.objects.filter(
                cart=cart,
                product=product
            ).first()

            current_quantity = item.quantity if item else 0
            new_quantity = current_quantity + quantity

            if not product.is_available:
                raise ValidationError({
                    "product": "This product is unavailable."
                })

            if new_quantity > product.stock:
                raise ValidationError({
                    "quantity": "Not enough stock available."
                })

            created = item is None

            if created:
                item = CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=new_quantity
                )
            else:
                item.quantity = new_quantity
                item.save(update_fields=["quantity"])

        return Response(
            CartItemSerializer(item).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )
        )
        
class UpdateCartItemView(generics.UpdateAPIView):
    serializer_class = UpdateCartItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return CartItem.objects.filter(
            cart__user=self.request.user
        ).select_related("product")

    def patch(self, request, *args, **kwargs):
        with transaction.atomic():
            get_object_or_404(
                Cart.objects.select_for_update(),
                user=request.user
            )

            item = self.get_object()

            serializer = self.get_serializer(
                data=request.data
            )
            serializer.is_valid(raise_exception=True)

            quantity = serializer.validated_data["quantity"]

            if not item.product.is_available:
                raise ValidationError({
                    "product": "This product is unavailable."
                })

            if quantity > item.product.stock:
                raise ValidationError({
                    "quantity": "Not enough stock available."
                })

            item.quantity = quantity
            item.save(update_fields=["quantity"])

            return Response(CartItemSerializer(item).data)
    
class DeleteCartItemView(generics.DestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(
            cart__user=self.request.user
        )

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            get_object_or_404(
                Cart.objects.select_for_update(),
                user=request.user
            )

            return super().destroy(
                request, *args, **kwargs
            )