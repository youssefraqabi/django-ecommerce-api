from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product

User = get_user_model()

# Create your tests here.

class ProductAPITestCase(APITestCase):
    
    def setUp(self):
        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics",
        )
        
        self.product = Product.objects.create(
            category=self.category,
            name="Wireless Headphones",
            slug="wireless-headphones",
            description="Bluetooth headphones",
            price=Decimal("299.99"),
            stock=15,
            is_available=True,
        )
        
        self.admin_user = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="TestPassword123!",
        )
        
        self.normal_user = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="TestPassword123!",
        )
        
        self.list_url = reverse("product-list")
        self.detail_url = reverse(
            "product-detail",
            args=[self.product.id],
        ) 
        
    def test_product_list(self):
        response = self.client.get(self.list_url)
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        
        self.assertEqual(response.data["count"], 1)
    
    def test_retrieve_product_detail(self):
        response = self.client.get(self.detail_url)
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        
        self.assertEqual(response.data["name"], "Wireless Headphones")
        
        
    def test_product_not_found(self):
        url = reverse(
            "product-detail",
            args=[999],
        )
        
        response = self.client.get(url)
        
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        
    def test_anonymous_user_cannot_create_product(self):
        data = {
            "category": self.category.id,
            "name": "Gaming Mouse",
            "slug": "gaming-mouse",
            "price": "149.99",
            "stock": 10,
        }
        
        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )
        
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )
        
        self.assertEqual(Product.objects.count(), 1)
        
        
    def test_customer_cannot_create_product(self):
        self.client.force_authenticate(
            user=self.normal_user
        )
        
        data = {
            "category": self.category.id,
            "name": "Gaming Mouse",
            "slug": "gaming-mouse",
            "price": "149.99",
            "stock": 10,
        }
        
        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )
        
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        
        self.assertEqual(Product.objects.count(), 1)
        
    def test_admin_can_create_product(self):
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            "category": self.category.id,
            "name": "Gaming Mouse",
            "slug": "gaming-mouse",
            "price": "149.99",
            "stock": 10,
            "is_available": True,
        }
        
        response = self.client.post(
            self.list_url,
            data,
            format="json",
            
        )
        
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        
        self.assertEqual(Product.objects.count(), 2)
        
    def test_admin_can_update_product(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.patch(
            self.detail_url,
            {"price": "249.99"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.price,
            Decimal("249.99"),
        )
        
    def test_admin_can_delete_product(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.delete(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Product.objects.filter(
                id=self.product.id
            ).exists()
        )
    
    def test_negative_price_rejected(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        data = {
            "category": self.category.id,
            "name": "Invalid Product",
            "slug": "invalid-product",
            "price": "-50.00",
            "stock": 5,
        }

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn("price", response.data)
        
    def test_negative_stock_rejected(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        data = {
            "category": self.category.id,
            "name": "Invalid Stock Product",
            "slug": "invalid-stock-product",
            "price": "100.00",
            "stock": -5,
        }

        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn("stock", response.data)

    def test_customer_cannot_delete_product(self):
        self.client.force_authenticate(
            user=self.normal_user
        )

        response = self.client.delete(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            Product.objects.filter(
                id=self.product.id
            ).exists()
        )