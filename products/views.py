from rest_framework import generics, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .permissions import IsAdminOrReadOnly


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductListView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "category",
        "is_available",
    ]

    search_fields = [
        "name",
        "description",
    ]

    ordering_fields = [
        "price",
        "name",
        "created_at",
    ]

    ordering = ["-created_at"]


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]