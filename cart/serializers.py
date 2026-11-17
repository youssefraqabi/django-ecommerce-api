from decimal import Decimal
from rest_framework import serializers
from .models import Cart, CartItem
from products.models import Product


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    product_price = serializers.DecimalField(
        source="product.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_price",
            "quantity",
            "subtotal",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(
        many=True,
        read_only=True,
    )

    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total",
            "created_at",
            "updated_at",
        ]

    def get_total(self, obj):
        total = sum(
            (item.subtotal for item in obj.items.all()),
            Decimal("0.00"),
        )
        return str(total.quantize(Decimal("0.01")))
    
class AddToCartSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )

    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        product = attrs["product"]
        quantity = attrs["quantity"]

        if not product.is_available:
            raise serializers.ValidationError({
                "product": "This product is unavailable."
            })

        if quantity > product.stock:
            raise serializers.ValidationError({
                "quantity": "Not enough stock available."
            })

        return attrs
    
    
class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)