from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from orders.models import Order

from django.urls import reverse
from products.models import Category, Product
from cart.models import Cart, CartItem

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from rest_framework import status

from queue import Queue
from time import monotonic, sleep
from django.db import connection, transaction


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
        
class CheckoutTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="checkoutcustomer",
            password="TestPassword123!"
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics"
        )

        self.product = Product.objects.create(
            category=self.category,
            name="USB-C Hub",
            slug="usb-c-hub",
            description="USB-C adapter",
            price=Decimal("199.99"),
            stock=10,
            is_available=True
        )

        self.cart = Cart.objects.create(
            user=self.user
        )

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )
        
    def test_successful_checkout_creates_order(self):
        response = self.client.post("/api/orders/checkout/")

        self.assertEqual(response.status_code, 201)

        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.first()

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total_amount, Decimal("399.98"))
        
    
    def test_checkout_creates_order_items(self):
        response = self.client.post("/api/orders/checkout/")

        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(user=self.user)

        self.assertEqual(order.items.count(), 1)

        order_item = order.items.first()

        self.assertEqual(order_item.product, self.product)
        self.assertEqual(order_item.product_name, "USB-C Hub")
        self.assertEqual(order_item.price, Decimal("199.99"))
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.subtotal, Decimal("399.98"))
        
    def test_checkout_reduces_product_stock(self):
        response = self.client.post("/api/orders/checkout/")

        self.assertEqual(response.status_code, 201)

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 8)
        
    def test_checkout_clears_cart(self):
    # Confirm the cart contains one item before checkout
        self.assertEqual(self.cart.items.count(), 1)

    # Perform checkout
        response = self.client.post("/api/orders/checkout/")

    # Verify checkout succeeded
        self.assertEqual(response.status_code, 201)

    # Verify all cart items were deleted
        self.assertEqual(self.cart.items.count(), 0)

    # Verify the cart itself still exists
        self.assertTrue(
        Cart.objects.filter(pk=self.cart.pk).exists()
     )
        
    def test_checkout_rejects_empty_cart(self):
    # Remove all items from the test cart
        self.cart.items.all().delete()

    # Attempt checkout
        response = self.client.post("/api/orders/checkout/")

    # Verify checkout is rejected
        self.assertEqual(response.status_code, 400)

        self.assertEqual(
        response.data["detail"],
        "Your cart is empty."
        )

    # Verify no order was created
        self.assertEqual(Order.objects.count(), 0)

    # Verify product stock was not changed
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        
    def test_checkout_rejects_insufficient_stock(self):
    # Reduce available stock to 1
        self.product.stock = 1
        self.product.save(update_fields=["stock"])

    # Attempt to purchase 2 units
        response = self.client.post("/api/orders/checkout/")

    # Checkout must be rejected
        self.assertEqual(response.status_code, 400)

        self.assertIn(
        "insufficient stock",
        response.data["detail"]
        )

    # No order should be created
        self.assertEqual(Order.objects.count(), 0)

    # Stock must remain unchanged
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    # Cart items must remain available
        self.assertEqual(self.cart.items.count(), 1)
        
    def test_checkout_rolls_back_when_second_product_fails(self):
        second_product = Product.objects.create(
            category=self.category,
            name="Wireless Mouse",
            slug="wireless-mouse",
            description="Wireless computer mouse",
            price=Decimal("49.99"),
            stock=1,
            is_available=True
        )

        CartItem.objects.create(
            cart=self.cart,
            product=second_product,
            quantity=3
        )

        response = self.client.post("/api/orders/checkout/")

        self.assertEqual(response.status_code, 400)

    # No order should be saved
        self.assertEqual(Order.objects.count(), 0)

    # Both products must retain their original stock
        self.product.refresh_from_db()
        second_product.refresh_from_db()

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(second_product.stock, 1)

    # Both cart items must remain
        self.assertEqual(self.cart.items.count(), 2)
        
class OrderStatusUpdateTests(TestCase):

    def setUp(self):
        User = get_user_model()

        # Create a regular customer
        self.customer = User.objects.create_user(
            username="ordercustomer",
            password="TestPassword123!"
        )

        # Create a staff user
        self.staff_user = User.objects.create_user(
            username="orderstaff",
            password="TestPassword123!",
            is_staff=True
        )

        # Create an order belonging to the customer
        self.order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PENDING,
            total_amount=Decimal("199.99")
        )

        # Authenticate as staff
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff_user)

    def test_staff_can_update_order_status(self):
        url = f"/api/orders/{self.order.id}/status/"

        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PROCESSING
        )
        
    def test_customer_cannot_update_order_status(self):
    # Authenticate as a regular customer
        self.client.force_authenticate(user=self.customer)

        url = f"/api/orders/{self.order.id}/status/"

    # Attempt to update the order status
        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
    )

    # Regular customers must be denied access
        self.assertEqual(response.status_code, 403)

    # Verify the order status remains unchanged
        self.order.refresh_from_db()

        self.assertEqual(
        self.order.status,
        Order.Status.PENDING
    )
        
    def test_unauthenticated_user_cannot_update_order_status(self):
    # Remove authentication from the test client
        self.client.force_authenticate(user=None)

        url = f"/api/orders/{self.order.id}/status/"

    # Attempt to update the order without authentication
        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
            )

    # Unauthenticated users must receive HTTP 401
        self.assertEqual(response.status_code, 401)

    # Verify the order status remains unchanged
        self.order.refresh_from_db()

        self.assertEqual(
        self.order.status,
        Order.Status.PENDING
    )
        
    def test_staff_cannot_set_invalid_order_status(self):
        url = f"/api/orders/{self.order.id}/status/"

        response = self.client.patch(
            url,
            {"status": "unknown"},
            format="json"
        )

    # Invalid status must be rejected
        self.assertEqual(response.status_code, 400)

    # Response should identify the invalid field
        self.assertIn("status", response.data)

    # Order status must remain unchanged
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING
        )
        
    def test_staff_cannot_update_nonexistent_order(self):
    # Use an order ID that does not exist
        url = "/api/orders/99999/status/"

        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
        )

    # The API must return 404 Not Found
        self.assertEqual(response.status_code, 404)

    # Verify the existing order remains unchanged
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING
        )
        
    def test_valid_status_transition(self):
        url = f"/api/orders/{self.order.id}/status/"

        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
        )

    # Verify the request succeeds
        self.assertEqual(response.status_code, 200)

    # Verify the new status is saved
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PROCESSING
        )
        
    def test_cannot_skip_order_status_stages(self):
        url = f"/api/orders/{self.order.id}/status/"

        response = self.client.patch(
            url,
            {"status": "delivered"},
            format="json"
        )

    # Invalid transition must be rejected
        self.assertEqual(response.status_code, 400)

    # Error should identify the status field
        self.assertIn("status", response.data)

    # Verify the order status remains unchanged
        self.order.refresh_from_db()

        self.assertEqual(
        self.order.status,
        Order.Status.PENDING
    )
        
    def test_delivered_order_cannot_return_to_pending(self):
    # Set the order's initial status to delivered
        self.order.status = Order.Status.DELIVERED
        self.order.save(update_fields=["status"])

        url = f"/api/orders/{self.order.id}/status/"

    # Attempt to change delivered back to pending
        response = self.client.patch(
            url,
            {"status": "pending"},
            format="json"
        )

    # Invalid transition must be rejected
        self.assertEqual(response.status_code, 400)

    # Verify the response contains a validation error
        self.assertIn("status", response.data)

    # Verify the order remains delivered
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.DELIVERED
        )
        
        
    def test_cancelled_order_cannot_be_reopened(self):
    # Set the order's initial status to cancelled
        self.order.status = Order.Status.CANCELLED
        self.order.save(update_fields=["status"])

        url = f"/api/orders/{self.order.id}/status/"

    # Attempt to reopen the cancelled order
        response = self.client.patch(
            url,
            {"status": "processing"},
            format="json"
        )

    # The transition must be rejected
        self.assertEqual(response.status_code, 400)

    # Verify the validation error
        self.assertIn("status", response.data)

    # Verify the order remains cancelled
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.CANCELLED
        )
        
    def test_full_order_lifecycle(self):
        url = f"/api/orders/{self.order.id}/status/"

        transitions = [
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ]

        for new_status in transitions:
            response = self.client.patch(
                url,
                {"status": new_status},
                format="json"
        )

        # Each transition must succeed
        self.assertEqual(response.status_code, 200)

        # Verify the status was saved
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            new_status
        )
        
class CheckoutConcurrencyTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.user1 = User.objects.create_user(
            username="concurrent_customer1",
            password="TestPassword123!"
        )

        self.user2 = User.objects.create_user(
            username="concurrent_customer2",
            password="TestPassword456!"
        )

        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics"
        )

        self.product = Product.objects.create(
            category=self.category,
            name="USB-C Hub",
            slug="usb-c-hub",
            description="USB-C adapter",
            price=Decimal("199.99"),
            stock=10,
            is_available=True
        )

        self.cart1 = Cart.objects.create(user=self.user1)
        self.cart2 = Cart.objects.create(user=self.user2)

        self.checkout_url = reverse("checkout")

    def concurrent_checkout(self, user_id, barrier):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            client = APIClient()
            client.force_authenticate(user=user)

            barrier.wait(timeout=10)

            response = client.post(self.checkout_url)

            return response.status_code

        finally:
            connections.close_all()

    def run_concurrent_checkouts(self, user1_id, user2_id):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(
                self.concurrent_checkout,
                user1_id,
                barrier
            )

            future2 = executor.submit(
                self.concurrent_checkout,
                user2_id,
                barrier
            )

            return [
                future1.result(timeout=30),
                future2.result(timeout=30)
            ]

    def test_concurrent_checkout_prevents_overselling(self):
        self.product.stock = 1
        self.product.save(update_fields=["stock"])

        CartItem.objects.create(
            cart=self.cart1,
            product=self.product,
            quantity=1
        )

        CartItem.objects.create(
            cart=self.cart2,
            product=self.product,
            quantity=1
        )

        results = self.run_concurrent_checkouts(
            self.user1.pk,
            self.user2.pk
        )

        self.assertCountEqual(
            results,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST
            ]
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().quantity, 1)
        self.assertEqual(
            order.total_amount,
            Decimal("199.99")
        )

        winning_cart = Cart.objects.get(user=order.user)

        losing_cart = Cart.objects.exclude(
            user=order.user
        ).get()

        self.assertEqual(winning_cart.items.count(), 0)
        self.assertEqual(losing_cart.items.count(), 1)
        self.assertEqual(losing_cart.items.get().quantity, 1)

    def test_concurrent_checkout_prevents_duplicate_orders(self):
        CartItem.objects.create(
            cart=self.cart1,
            product=self.product,
            quantity=2
        )

        results = self.run_concurrent_checkouts(
            self.user1.pk,
            self.user1.pk
        )

        self.assertCountEqual(
            results,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST
            ]
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 8)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.cart1.items.count(), 0)

        order = Order.objects.get(user=self.user1)

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(
            order.total_amount,
            Decimal("399.98")
        )
        
    def concurrent_cart_add(self, user_id, quantity, barrier):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            client = APIClient()
            client.force_authenticate(user=user)

            barrier.wait(timeout=10)

            response = client.post(
                reverse("cart-add-item"),
                {
                    "product": self.product.pk,
                    "quantity": quantity
                },
                format="json"
            )

            return response.status_code

        finally:
            connections.close_all()
            
    def test_concurrent_checkout_and_cart_addition(self):
        CartItem.objects.create(
            cart=self.cart1,
            product=self.product,
            quantity=2
        )

        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            checkout_future = executor.submit(
                self.concurrent_checkout,
                self.user1.pk,
                barrier
            )

            add_future = executor.submit(
                self.concurrent_cart_add,
                self.user1.pk,
                3,
                barrier
            )

            checkout_status = checkout_future.result(timeout=30)
            add_status = add_future.result(timeout=30)

        self.assertEqual(
            checkout_status,
            status.HTTP_201_CREATED
        )

        self.assertIn(
            add_status,
            [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED
            ]
        )

        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get(user=self.user1)

        self.assertEqual(order.items.count(), 1)

        order_item = order.items.get()

        self.product.refresh_from_db()

        cart_quantity = sum(
            item.quantity
            for item in self.cart1.items.all()
        )

        self.assertIn(
            (
                order_item.quantity,
                cart_quantity,
                self.product.stock,
                add_status
            ),
            [
                (2, 3, 8, status.HTTP_201_CREATED),
                (5, 0, 5, status.HTTP_200_OK)
            ]
        )

        self.assertEqual(
            order.total_amount,
            Decimal("199.99") * order_item.quantity
        )

        self.assertEqual(
            order_item.quantity + cart_quantity,
            5
        )
        
    def concurrent_cart_update(
        self, user_id, item_id, quantity, barrier
    ):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            client = APIClient()
            client.force_authenticate(user=user)

            barrier.wait(timeout=10)

            response = client.patch(
                reverse(
                    "cart-update-item",
                    kwargs={"pk": item_id}
                ),
                {"quantity": quantity},
                format="json"
            )

            return response.status_code

        finally:
            connections.close_all()
            
    def test_concurrent_checkout_and_cart_update(self):
        item = CartItem.objects.create(
            cart=self.cart1,
            product=self.product,
            quantity=2
        )

        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            checkout_future = executor.submit(
                self.concurrent_checkout,
                self.user1.pk,
                barrier
            )

            update_future = executor.submit(
                self.concurrent_cart_update,
                self.user1.pk,
                item.pk,
                4,
                barrier
            )

            checkout_status = checkout_future.result(timeout=30)
            update_status = update_future.result(timeout=30)

        self.assertEqual(
            checkout_status,
            status.HTTP_201_CREATED
        )

        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get(user=self.user1)

        self.assertEqual(order.items.count(), 1)

        order_item = order.items.get()

        self.product.refresh_from_db()

        self.assertIn(
            (
                order_item.quantity,
                self.product.stock,
                update_status
            ),
            [
                (2, 8, status.HTTP_404_NOT_FOUND),
                (4, 6, status.HTTP_200_OK)
            ]
        )

        self.assertEqual(
            order.total_amount,
            Decimal("199.99") * order_item.quantity
        )

        self.assertEqual(self.cart1.items.count(), 0)

        self.assertEqual(
            self.product.stock + order_item.quantity,
            10
        )
        
    def concurrent_cart_delete(
        self, user_id, item_id, barrier
    ):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            client = APIClient()
            client.force_authenticate(user=user)

            barrier.wait(timeout=10)

            response = client.delete(
                reverse(
                    "cart-delete-item",
                    kwargs={"pk": item_id}
                )
            )

            return response.status_code

        finally:
            connections.close_all()
        
    def test_concurrent_checkout_and_cart_deletion(self):
        item = CartItem.objects.create(
            cart=self.cart1,
            product=self.product,
            quantity=2
        )

        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            checkout_future = executor.submit(
                self.concurrent_checkout,
                self.user1.pk,
                barrier
            )

            delete_future = executor.submit(
                self.concurrent_cart_delete,
                self.user1.pk,
                item.pk,
                barrier
            )

            checkout_status = checkout_future.result(timeout=30)
            delete_status = delete_future.result(timeout=30)

        self.product.refresh_from_db()

        order_count = Order.objects.count()

        self.assertIn(
            (
                checkout_status,
                delete_status,
                order_count,
                self.product.stock
            ),
            [
                (
                    status.HTTP_201_CREATED,
                    status.HTTP_404_NOT_FOUND,
                    1,
                    8
                ),
                (
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_204_NO_CONTENT,
                    0,
                    10
                )
            ]
        )

        self.assertEqual(self.cart1.items.count(), 0)

        if order_count == 1:
            order = Order.objects.get(user=self.user1)

            self.assertEqual(order.items.count(), 1)
            self.assertEqual(order.items.get().quantity, 2)

            self.assertEqual(
                order.total_amount,
                Decimal("399.98")
            )
            
class OrderStatusConcurrencyTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.customer = User.objects.create_user(
            username="status_customer",
            password="TestPassword123!"
        )

        self.staff1 = User.objects.create_user(
            username="staff_one",
            password="TestPassword123!",
            is_staff=True
        )

        self.staff2 = User.objects.create_user(
            username="staff_two",
            password="TestPassword456!",
            is_staff=True
        )

        self.order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PROCESSING,
            total_amount=Decimal("199.99")
        )

        self.status_url = reverse(
            "order-status-update",
            kwargs={"pk": self.order.pk}
        )

    def concurrent_status_update(
        self, user_id, new_status, barrier
    ):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            client = APIClient()
            client.force_authenticate(user=user)

            barrier.wait(timeout=10)

            response = client.patch(
                self.status_url,
                {"status": new_status},
                format="json"
            )

            return response.status_code

        finally:
            connections.close_all()

    def test_conflicting_order_status_updates(self):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            shipped_future = executor.submit(
                self.concurrent_status_update,
                self.staff1.pk,
                Order.Status.SHIPPED,
                barrier
            )

            cancelled_future = executor.submit(
                self.concurrent_status_update,
                self.staff2.pk,
                Order.Status.CANCELLED,
                barrier
            )

            shipped_status = shipped_future.result(timeout=30)
            cancelled_status = cancelled_future.result(timeout=30)

        self.order.refresh_from_db()

        self.assertIn(
            (
                shipped_status,
                cancelled_status,
                self.order.status
            ),
            [
                (
                    status.HTTP_200_OK,
                    status.HTTP_400_BAD_REQUEST,
                    Order.Status.SHIPPED
                ),
                (
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_200_OK,
                    Order.Status.CANCELLED
                )
            ]
        )

        self.assertEqual(Order.objects.count(), 1)
        
class CheckoutLockTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="lock_customer",
            password="TestPassword123!"
        )

        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics"
        )

        self.product = Product.objects.create(
            category=self.category,
            name="USB-C Hub",
            slug="usb-c-hub",
            price=Decimal("199.99"),
            stock=10,
            is_available=True
        )

        self.cart = Cart.objects.create(user=self.user)

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )

    def checkout_worker(self, pid_queue):
        close_old_connections()

        try:
            User = get_user_model()
            user = User.objects.get(pk=self.user.pk)

            client = APIClient()
            client.force_authenticate(user=user)

            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '15s'")
                cursor.execute("SELECT pg_backend_pid()")
                worker_pid = cursor.fetchone()[0]

            pid_queue.put(worker_pid)

            response = client.post(reverse("checkout"))

            return response.status_code

        finally:
            connections.close_all()

    def test_checkout_waits_for_cart_lock(self):
        pid_queue = Queue()

        with ThreadPoolExecutor(max_workers=1) as executor:

            with transaction.atomic():

                Cart.objects.select_for_update().get(
                    pk=self.cart.pk
                )

                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    main_pid = cursor.fetchone()[0]

                future = executor.submit(
                    self.checkout_worker,
                    pid_queue
                )

                worker_pid = pid_queue.get(timeout=5)

                deadline = monotonic() + 5
                blocked = False

                while monotonic() < deadline:

                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_blocking_pids(%s)",
                            [worker_pid]
                        )

                        blocking_pids = cursor.fetchone()[0]

                    if main_pid in blocking_pids:
                        blocked = True
                        break

                    sleep(0.05)

                self.assertTrue(
                    blocked,
                    "Checkout did not wait for the cart lock."
                )

                self.assertFalse(future.done())

            # Transaction committed and cart lock released.

            response_status = future.result(timeout=20)

        self.assertEqual(
            response_status,
            status.HTTP_201_CREATED
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 8)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.cart.items.count(), 0)

        order = Order.objects.get(user=self.user)

        self.assertEqual(
            order.total_amount,
            Decimal("399.98")
        )