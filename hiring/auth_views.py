from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
import secrets
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Custom token generator with 24-hour expiry
class CustomTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Include user's password hash and last login to invalidate token when password changes
        return (
            str(user.pk) + str(timestamp) + 
            str(user.is_active) + 
            str(user.last_login) +
            user.password
        )
    
    def check_token(self, user, token):
        # Check if token is valid and not expired (24 hours)
        if not super().check_token(user, token):
            return False
        
        # Check if token was created within 24 hours
        timestamp = int(token.split('-')[0])
        token_date = datetime.fromtimestamp(timestamp)
        expiry_date = token_date + timedelta(hours=24)
        
        return datetime.now() < expiry_date

token_generator = CustomTokenGenerator()

class PasswordResetRequestView(APIView):
    """
    API endpoint for requesting password reset
    POST: Send password reset email
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            
            if not email:
                return Response({
                    'success': False,
                    'error': 'Email is required',
                    'errors': {'email': ['Email is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user exists with this email
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                # For security, don't reveal if email exists or not
                return Response({
                    'success': True,
                    'message': 'If your email exists in our system, you will receive a password reset link shortly.'
                }, status=status.HTTP_200_OK)
            
            # Generate token
            timestamp = int(datetime.now().timestamp())
            token = token_generator.make_token(user)
            full_token = f"{timestamp}-{token}"
            
            # Encode user ID for URL
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset link
            reset_url = f"{settings.FRONTEND_URL}/reset-password/?token={full_token}&email={email}"
            
            # Send email
            subject = 'Reset Your JobPortal Password'
            
            # Email template context
            context = {
                'user': user,
                'reset_url': reset_url,
                'support_email': settings.SUPPORT_EMAIL,
                'site_name': 'JobPortal',
                'expiry_hours': 24
            }
            
            # Render email templates
            text_message = render_to_string('emails/password_reset.txt', context)
            html_message = render_to_string('emails/password_reset.html', context)
            
            try:
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False
                )
                
                logger.info(f"Password reset email sent to {email}")
                
                # Store token in user's profile or session (optional)
                # You can store it in a cache or database for validation
                
                return Response({
                    'success': True,
                    'message': 'Password reset link has been sent to your email.'
                }, status=status.HTTP_200_OK)
                
            except Exception as email_error:
                logger.error(f"Failed to send password reset email to {email}: {str(email_error)}")
                return Response({
                    'success': False,
                    'error': 'Failed to send email. Please try again later.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except json.JSONDecodeError:
            return Response({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetConfirmView(APIView):
    """
    API endpoint for confirming password reset
    POST: Set new password with token validation
    """
    permission_classes = [AllowAny]
    
    def validate_password(self, password):
        """Validate password strength"""
        errors = []
        
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if not any(char.isupper() for char in password):
            errors.append('Password must contain at least one uppercase letter.')
        
        if not any(char.islower() for char in password):
            errors.append('Password must contain at least one lowercase letter.')
        
        if not any(char.isdigit() for char in password):
            errors.append('Password must contain at least one number.')
        
        # Optional: Add special character requirement
        # if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
        #     errors.append('Password must contain at least one special character.')
        
        return errors
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            token = data.get('token', '')
            email = data.get('email', '').strip().lower()
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
            
            errors = {}
            
            # Validate required fields
            if not token:
                errors['token'] = ['Reset token is required']
            if not email:
                errors['email'] = ['Email is required']
            if not new_password:
                errors['new_password'] = ['New password is required']
            if not confirm_password:
                errors['confirm_password'] = ['Please confirm your password']
            
            if errors:
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if passwords match
            if new_password != confirm_password:
                errors['confirm_password'] = ['Passwords do not match']
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate password strength
            password_errors = self.validate_password(new_password)
            if password_errors:
                errors['new_password'] = password_errors
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                errors['email'] = ['Invalid email address']
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse token (format: timestamp-token)
            try:
                token_parts = token.split('-', 1)
                if len(token_parts) != 2:
                    raise ValueError("Invalid token format")
                
                timestamp_part = token_parts[0]
                actual_token = token_parts[1]
                
                # Validate token
                if not token_generator.check_token(user, actual_token):
                    errors['token'] = ['Invalid or expired reset token. Please request a new link.']
                    return Response({
                        'success': False,
                        'errors': errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            except (ValueError, IndexError) as e:
                logger.error(f"Token parsing error: {str(e)}")
                errors['token'] = ['Invalid token format']
                return Response({
                    'success': False,
                    'errors': errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Set new password
            try:
                user.set_password(new_password)
                user.save()
                
                # Optional: Invalidate all user sessions
                # You can implement this if you're tracking sessions
                
                # Optional: Send confirmation email
                try:
                    subject = 'Your Password Has Been Reset'
                    message = f"Hello {user.username},\n\nYour JobPortal password has been successfully reset.\n\nIf you did not request this change, please contact our support team immediately at {settings.SUPPORT_EMAIL}.\n\nBest regards,\nJobPortal Team"
                    
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=True
                    )
                except Exception as email_error:
                    logger.warning(f"Failed to send password change confirmation: {str(email_error)}")
                
                logger.info(f"Password reset successful for user: {user.username}")
                
                return Response({
                    'success': True,
                    'message': 'Password has been reset successfully. You can now login with your new password.'
                }, status=status.HTTP_200_OK)
                
            except Exception as save_error:
                logger.error(f"Failed to save new password for user {user.username}: {str(save_error)}")
                return Response({
                    'success': False,
                    'error': 'Failed to update password. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except json.JSONDecodeError:
            return Response({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset confirm error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)