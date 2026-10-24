import hashlib  # <--- THIS LINE MUST BE HERE
import re
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get('email', '').strip()
    
    if not email:
        return Response({
            'success': False,
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return Response({
            'success': False,
            'error': 'Please enter a valid email address'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'success': True,
            'message': 'If an account exists with this email, a reset link has been sent.'
        }, status=status.HTTP_200_OK)
    
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    frontend_url = settings.FRONTEND_URL or 'https://oppoglobe.co.za'
    reset_url = f"{frontend_url}/reset-password/?uid={uid}&token={token}"
    
    try:
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': 'OppoGlobe',
            'email': user.email,
            'uid': uid,
            'token': token,
        }
        
        html_message = render_to_string('registration/password_reset_email.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Reset Your OppoGlobe Password',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return Response({
            'success': True,
            'message': 'Password reset link has been sent to your email.',
            'reset_url': reset_url if settings.DEBUG else None
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to send email. Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uid = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    if not uid or not token or not new_password:
        return Response({
            'success': False,
            'error': 'All fields are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if len(new_password) < 8:
        return Response({
            'success': False,
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        return Response({
            'success': False,
            'error': 'Invalid reset link. Please request a new one.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not default_token_generator.check_token(user, token):
        return Response({
            'success': False,
            'error': 'The reset link has expired. Please request a new one.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.set_password(new_password)
    user.save()
    
    return Response({
        'success': True,
        'message': 'Password has been reset successfully. You can now login with your new password.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_validate_token(request):
    uid = request.data.get('uid')
    token = request.data.get('token')
    
    if not uid or not token:
        return Response({
            'success': False,
            'error': 'Missing uid or token'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        return Response({
            'success': False,
            'error': 'Invalid user'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    is_valid = default_token_generator.check_token(user, token)
    
    return Response({
        'success': is_valid,
        'message': 'Token is valid' if is_valid else 'Token has expired'
    }, status=status.HTTP_200_OK)