from decimal import Decimal

from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
        ]
        
    
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "description",
            "price",
            "stock",
            "is_available",
            "created_at",
            "updated_at",
        ]
        
    def validate_price(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError(
                     "Product price must be greater than zero."
            )
        return value