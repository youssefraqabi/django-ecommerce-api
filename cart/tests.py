from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from products.models import Category, Product
from .models import Cart, CartItem


User = get_user_model()


class CartAPITests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="customer1",
            password="TestPassword123!"
        )

        self.other_user = User.objects.create_user(
            username="customer2",
            password="TestPassword456!"
        )

        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics"
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Wireless Headphones",
            slug="wireless-headphones",
            price=Decimal("390.99"),
            stock=10,
            is_available=True
        )

        self.cart = Cart.objects.create(user=self.user)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.cart_url = "/api/cart/"
        self.add_url = "/api/cart/items/"

    def create_cart_item(self, quantity=2):
        return CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=quantity
        )

    # TEST 1
    def test_get_empty_cart(self):
        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["total"], "0.00")

    # TEST 2
    def test_unauthenticated_user_cannot_view_cart(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.cart_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    # TEST 3
    def test_add_product_to_cart(self):
        response = self.client.post(
            self.add_url,
            {"product": self.product.id, "quantity": 2},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(CartItem.objects.first().quantity, 2)

    # TEST 4
    def test_add_existing_product_increases_quantity(self):
        self.create_cart_item(quantity=2)

        response = self.client.post(
            self.add_url,
            {"product": self.product.id, "quantity": 3},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        item = CartItem.objects.get(
            cart=self.cart,
            product=self.product
        )

        self.assertEqual(item.quantity, 5)
        self.assertEqual(CartItem.objects.count(), 1)

    # TEST 5
    def test_cannot_add_zero_quantity(self):
        response = self.client.post(
            self.add_url,
            {"product": self.product.id, "quantity": 0},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    # TEST 6
    def test_cannot_add_more_than_stock(self):
        response = self.client.post(
            self.add_url,
            {"product": self.product.id, "quantity": 20},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    # TEST 7
    def test_cannot_add_unavailable_product(self):
        self.product.is_available = False
        self.product.save()

        response = self.client.post(
            self.add_url,
            {"product": self.product.id, "quantity": 1},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # TEST 8
    def test_update_cart_item_quantity(self):
        item = self.create_cart_item(quantity=2)

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {"quantity": 4},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

    # TEST 9
    def test_cannot_update_to_zero_quantity(self):
        item = self.create_cart_item()

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {"quantity": 0},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    # TEST 10
    def test_delete_cart_item(self):
        item = self.create_cart_item()

        response = self.client.delete(
            f"/api/cart/items/{item.id}/delete/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(
            CartItem.objects.filter(id=item.id).exists()
        )

    # TEST 11
    def test_user_cannot_update_another_users_cart(self):
        item = self.create_cart_item()

        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {"quantity": 5},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    # TEST 12
    def test_user_cannot_delete_another_users_cart_item(self):
        item = self.create_cart_item()

        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(
            f"/api/cart/items/{item.id}/delete/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )
        self.assertTrue(
            CartItem.objects.filter(id=item.id).exists()
        )