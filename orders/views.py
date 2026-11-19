from decimal import Decimal

from django.db import transaction, DatabaseError
from django.db.models import F
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from cart.models import Cart
from products.models import Product
from .models import Order, OrderItem
from .serializers import OrderSerializer


class CheckoutError(Exception):
    pass


class CheckoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            with transaction.atomic():
                cart = Cart.objects.filter(
                    user=request.user
                ).first()

                if cart is None:
                    raise CheckoutError("Your cart is empty.")

                items = list(
                    cart.items.select_related("product")
                    .order_by("product_id")
                )

                if not items:
                    raise CheckoutError("Your cart is empty.")

                total_amount = Decimal("0.00")
                order_items = []

                for item in items:
                    product = item.product

                    updated = Product.objects.filter(
                        pk=product.pk,
                        is_available=True,
                        stock__gte=item.quantity
                    ).update(
                        stock=F("stock") - item.quantity
                    )

                    if updated == 0:
                        raise CheckoutError(
                            f"{product.name} is unavailable "
                            "or has insufficient stock."
                        )

                    total_amount += (
                        product.price * item.quantity
                    )

                    order_items.append({
                        "product": product,
                        "product_name": product.name,
                        "price": product.price,
                        "quantity": item.quantity
                    })

                order = Order.objects.create(
                    user=request.user,
                    status=Order.Status.PENDING,
                    total_amount=total_amount
                )

                for data in order_items:
                    OrderItem.objects.create(
                        order=order,
                        **data
                    )

                cart.items.all().delete()

            serializer = OrderSerializer(order)

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        except CheckoutError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except DatabaseError:
            return Response(
                {
                    "detail": (
                        "Checkout could not be completed. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )