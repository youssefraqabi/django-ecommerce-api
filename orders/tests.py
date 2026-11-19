from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from orders.models import Order


class OrderHistoryTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testcustomer",
            password="TestPassword123!"
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("399.98")
        )

    def test_customer_can_list_own_orders(self):
        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.order.id
        )
        
    def test_customer_cannot_list_other_users_orders(self):
        User = get_user_model()

        other_user = User.objects.create_user(
            username="othercustomer",
            password="TestPassword456!"
        )

        self.client.force_authenticate(user=other_user)

        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
    
    def test_customer_can_retrieve_own_order(self):
        response = self.client.get(
            f"/api/orders/{self.order.id}/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["id"],
            self.order.id
        )

        self.assertEqual(
            response.data["total_amount"],
            "399.98"
        )
        
    def test_customer_cannot_retrieve_other_users_order(self):
        User = get_user_model()

        other_user = User.objects.create_user(
            username="othercustomer",
            password="TestPassword456!"
        )

        self.client.force_authenticate(user=other_user)

        response = self.client.get(
            f"/api/orders/{self.order.id}/"
        )

        self.assertEqual(response.status_code, 404)
        
    def test_unauthenticated_user_cannot_access_orders(self):
        self.client.force_authenticate(user=None)

        list_response = self.client.get("/api/orders/")

        detail_response = self.client.get(
            f"/api/orders/{self.order.id}/"
        )

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(detail_response.status_code, 401)