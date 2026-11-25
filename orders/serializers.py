from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):

    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "price",
            "quantity",
            "subtotal",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        
        
class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["status"]
        
    def validate_status(self, new_status):
        allowed_transitions = {
            Order.Status.PENDING: [
                Order.Status.PROCESSING,
                Order.Status.CANCELLED,
            ],
            Order.Status.PROCESSING: [
                Order.Status.SHIPPED,
                Order.Status.CANCELLED,
            ],
            Order.Status.SHIPPED: [
                Order.Status.DELIVERED,
            ],
            Order.Status.DELIVERED: [],
            Order.Status.CANCELLED: [],
            
        }
        
        current_status = self.instance.status
        
        if new_status not in allowed_transitions[current_status]:
            raise serializers.ValidationError(
                f"Cannot change order status from "
                f"'{current_status}' to '{new_status}'."
            )

        return new_status