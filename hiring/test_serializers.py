from django.test import TestCase
from .serializers import SignupSerializer

class SerializerTest(TestCase):
    def test_signup_serializer(self):
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'mobile_phone': '1234567890',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        serializer = SignupSerializer(data=data)
        self.assertTrue(serializer.is_valid())