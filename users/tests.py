from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class AuthenticationAPITests(APITestCase):

    def setUp(self):
        self.register_url = reverse("user-register")
        self.login_url = reverse("token_obtain_pair")
        self.refresh_url = reverse("token_refresh")
        self.profile_url = reverse("user-profile")

        self.password = "TestPassword123!Secure"

        self.user = User.objects.create_user(
            username="existingcustomer",
            email="existing@example.com",
            password=self.password,
        )

    def test_valid_registration(self):
        data = {
            "username": "newcustomer",
            "email": "new@example.com",
            "password": "StrongPassword456!Test",
            "password2": "StrongPassword456!Test",
        }

        response = self.client.post(
            self.register_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(
            User.objects.filter(username="newcustomer").exists()
        )
        self.assertNotIn("password", response.data)
        self.assertNotIn("password2", response.data)

        new_user = User.objects.get(username="newcustomer")
        self.assertTrue(
            new_user.check_password("StrongPassword456!Test")
        )

    def test_password_mismatch(self):
        data = {
            "username": "newcustomer",
            "email": "new@example.com",
            "password": "StrongPassword456!Test",
            "password2": "DifferentPassword456!Test",
        }

        response = self.client.post(
            self.register_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username(self):
        data = {
            "username": "existingcustomer",
            "email": "another@example.com",
            "password": "StrongPassword456!Test",
            "password2": "StrongPassword456!Test",
        }

        response = self.client.post(
            self.register_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("username", response.data)

    def test_duplicate_email(self):
        data = {
            "username": "anothercustomer",
            "email": "existing@example.com",
            "password": "StrongPassword456!Test",
            "password2": "StrongPassword456!Test",
        }

        response = self.client.post(
            self.register_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("email", response.data)

    def test_weak_password(self):
        data = {
            "username": "newcustomer",
            "email": "new@example.com",
            "password": "12345678",
            "password2": "12345678",
        }

        response = self.client.post(
            self.register_url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(User.objects.count(), 1)

    def test_valid_jwt_login(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "existingcustomer",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_invalid_jwt_login(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "existingcustomer",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_token(self):
        login_response = self.client.post(
            self.login_url,
            {
                "username": "existingcustomer",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        refresh_token = login_response.data["refresh"]

        response = self.client.post(
            self.refresh_url,
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("access", response.data)

    def test_profile_requires_authentication(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_profile(self):
        login_response = self.client.post(
            self.login_url,
            {
                "username": "existingcustomer",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["username"],
            "existingcustomer",
        )
        self.assertEqual(
            response.data["email"],
            "existing@example.com",
        )
        self.assertNotIn("password", response.data)