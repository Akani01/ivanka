"""
hiring/views.py — OppoGlobe Hiring + Social (CLEAN)
Only hiring, applicants, businesses, jobs, applications, posts,
messaging, alerts, PWA, admin portal, blog, careers, FAQ, contact.
No realestate / carwash / education / video code.
"""

import csv
import json
import os
import re
import time
import uuid
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import connection, transaction
from django.db.models import Count, Q, Avg, F, Max
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, parser_classes, action,
)
from rest_framework.parsers import (
    MultiPartParser, FormParser, JSONParser,
)
from rest_framework.permissions import (
    AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

# ---- HIRING MODELS ONLY ----
from .models import (
    CustomUser, ApplicantProfile, BusinessProfile,
    Skill, Education, EmploymentHistory, Document,
    Industry, CompanySize, JobCategory,
    JobListing, Application,
    Alert, BusinessAlert, SentNotification, BusinessSentNotification,
    NotificationPreference, BusinessNotificationPreference,
    JobAlert, EmailTemplate, SearchHistory,
    Conversation, Message, MessageRecipient, UserStatus,
    BusinessPreference, BusinessEmploymentPreference,
    BusinessProfileView,
    Post, Comment, Rating, PostView, JobInteraction,
    NewsletterSubscriber, Page, BlogPost, Career, FAQ,
    ContactMessage, StaticPage, HelpCenterPage,
    PushSubscription,
)

from .serializers import *  # hiring serializers only
from .utils import calculate_profile_completeness

logger = logging.getLogger(__name__)

# ============================================================
# ACCESS CONTROL HELPERS (single definition each)
# ============================================================

def has_admin_access(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if getattr(user, 'user_type', None) == 'admin':
        return True
    return False


def has_business_access(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if getattr(user, 'user_type', None) == 'admin':
        return True
    try:
        if hasattr(user, 'business_profile'):
            return True
    except Exception:
        pass
    return False


def has_superuser_access(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/')
        if not has_admin_access(request.user):
            return HttpResponseForbidden("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/')
        if not has_superuser_access(request.user):
            return HttpResponseForbidden("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _infer_notification_source(title, message):
    value = f'{title} {message}'.lower()
    if any(x in value for x in ('job', 'application', 'candidate', 'profile')):
        return 'hiring'
    if any(x in value for x in ('message', 'comment', 'reply')):
        return 'messaging'
    return 'system'


# ============================================================
# NOTIFICATION SERVICE (hiring-only, pywebpush based)
# ============================================================

class NotificationService:
    DEFAULT_ICON = '/static/hiring/icons/icon-192.png'
    DEFAULT_BADGE = '/static/hiring/icons/icon-72x72.png'

    @staticmethod
    def _payload(title, message, action_url='/alerts/', app_source='hiring',
                 notification_type='system', sound=True, icon=None, badge=None):
        return {
            'head': title,
            'title': title,
            'body': message,
            'icon': icon or NotificationService.DEFAULT_ICON,
            'badge': badge or NotificationService.DEFAULT_BADGE,
            'url': action_url or '/alerts/',
            'action_url': action_url or '/alerts/',
            'app_source': app_source or 'hiring',
            'notification_type': notification_type or 'system',
            'silent': not bool(sound),
            'sound': bool(sound),
            'tag': f"oppoglobe-{app_source or 'hiring'}-{notification_type or 'system'}",
        }

    @staticmethod
    def _send_push(user, payload, ttl=86400):
        """Send web push via pywebpush to all of user's PushSubscriptions."""
        if not user or not getattr(user, 'is_active', True):
            return False
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            logger.warning('pywebpush not installed; skipping push.')
            return False

        vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_email = getattr(settings, 'VAPID_EMAIL', None) or 'admin@oppoglobe.com'
        if not vapid_private:
            logger.warning('VAPID_PRIVATE_KEY not configured; skipping push.')
            return False

        payload_str = json.dumps(payload)
        sent = False
        for sub in PushSubscription.objects.filter(user=user):
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                    },
                    data=payload_str,
                    vapid_private_key=vapid_private,
                    vapid_claims={'sub': f'mailto:{vapid_email}'},
                    ttl=ttl,
                )
                sent = True
            except WebPushException as exc:
                status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
                logger.warning('Push failed for user %s: %s', user.id, exc)
                if status_code in (404, 410):
                    sub.delete()
            except Exception as exc:
                logger.warning('Push error for user %s: %s', user.id, exc)
        return sent

    @staticmethod
    def notify(user, title, message, notification_type='system',
               app_source='hiring', action_url='/alerts/', send_push=True,
               sound=True, icon=None, badge=None, ttl=86400, create_in_app=True):
        if not user:
            return {'success': False, 'alert': None, 'push_sent': False,
                    'error': 'No user supplied'}
        try:
            payload = NotificationService._payload(
                title, message, action_url, app_source, notification_type,
                sound, icon, badge,
            )
            alert_obj = None
            business_profile = BusinessProfile.objects.filter(user=user).first()

            if create_in_app:
                if business_profile:
                    valid = {'application', 'expiry', 'custom', 'system'}
                    alert_obj = BusinessAlert(
                        business=business_profile,
                        alert_type=notification_type if notification_type in valid else 'custom',
                        title=title,
                        message=message,
                        is_active=True,
                        is_read=False,
                    )
                    alert_obj._oppoglobe_push_payload = payload if send_push else False
                    alert_obj._oppoglobe_push_ttl = ttl
                    alert_obj.save()
                    try:
                        BusinessSentNotification.objects.create(
                            business=business_profile,
                            subject=title,
                            message=message,
                            notification_type=(
                                notification_type
                                if notification_type in {'application', 'job', 'system', 'marketing'}
                                else 'system'
                            ),
                        )
                    except Exception as exc:
                        logger.warning('Business notification history failed: %s', exc)
                else:
                    profile = ApplicantProfile.objects.filter(user=user).first()
                    if profile is None:
                        profile = ApplicantProfile.objects.create(user=user)
                    alert_obj = Alert(
                        applicant=profile, title=title, message=message, is_read=False,
                    )
                    alert_obj._oppoglobe_push_payload = payload if send_push else False
                    alert_obj._oppoglobe_push_ttl = ttl
                    alert_obj.save()
                    try:
                        SentNotification.objects.create(
                            applicant=profile,
                            notification_type=notification_type,
                            subject=title,
                            message=message,
                            sent_via='in_app',
                        )
                    except Exception as exc:
                        logger.warning('Notification history failed: %s', exc)
                push_sent = bool(send_push)
            else:
                push_sent = NotificationService._send_push(user, payload, ttl=ttl) if send_push else False

            return {'success': True, 'alert': alert_obj, 'push_sent': push_sent}
        except Exception as exc:
            logger.exception('NotificationService.notify failed: %s', exc)
            return {'success': False, 'alert': None, 'push_sent': False, 'error': str(exc)}

    # ---- hiring-specific shortcuts ----
    @staticmethod
    def send_application_submission(application):
        return NotificationService.notify(
            application.applicant.user,
            'Application Submitted',
            f'Your application for {application.job_listing.title} at '
            f'{application.job_listing.company_name} has been submitted successfully.',
            'application', 'hiring', '/applications/', True, True,
        )

    @staticmethod
    def send_application_status_update(application, sound=True):
        return NotificationService.notify(
            application.applicant.user,
            'Application Status Updated',
            f'Your application for {application.job_listing.title} is now '
            f'{application.get_status_display()}.',
            'application', 'hiring', '/applications/', True, sound,
        )

    @staticmethod
    def send_job_alert(applicant, job_listing):
        return NotificationService.notify(
            applicant.user,
            'New Job Match',
            f'A new job matching your criteria: {job_listing.title} at '
            f'{job_listing.company_name}',
            'job', 'hiring', f'/jobs/{job_listing.id}/', True, True,
        )

    @staticmethod
    def send_profile_reminder(applicant):
        if applicant.profile_completeness >= 70:
            return None
        return NotificationService.notify(
            applicant.user,
            'Complete Your Profile',
            f'Your profile is {applicant.profile_completeness}% complete. '
            f'Complete it to increase your chances of getting hired.',
            'system', 'hiring', '/profile/', True, False,
        )

    @staticmethod
    def send_message_notification(message, recipient, sound=True):
        sender_name = message.sender.get_full_name() or message.sender.username
        preview = message.content or f'Sent you a {message.message_type}.'
        if len(preview) > 100:
            preview = preview[:97] + '...'
        return NotificationService.notify(
            recipient,
            f'New message from {sender_name}',
            preview,
            'message', 'messaging',
            f'/messaging/?conversation={message.conversation.id}',
            True, sound,
        )


@receiver(post_save, sender=Alert)
def _oppoglobe_alert_push(sender, instance, created, **kwargs):
    if not created:
        return
    marker = getattr(instance, '_oppoglobe_push_payload', 'missing')
    if marker is False:
        return
    payload = marker if marker != 'missing' else NotificationService._payload(
        instance.title, instance.message, '/alerts/',
        _infer_notification_source(instance.title, instance.message),
        'system', True,
    )
    NotificationService._send_push(
        instance.applicant.user, payload,
        getattr(instance, '_oppoglobe_push_ttl', 86400),
    )


@receiver(post_save, sender=BusinessAlert)
def _oppoglobe_business_alert_push(sender, instance, created, **kwargs):
    if not created:
        return
    marker = getattr(instance, '_oppoglobe_push_payload', 'missing')
    if marker is False:
        return
    payload = marker if marker != 'missing' else NotificationService._payload(
        instance.title, instance.message, '/alerts/',
        _infer_notification_source(instance.title, instance.message),
        instance.alert_type or 'system', True,
    )
    NotificationService._send_push(
        instance.business.user, payload,
        getattr(instance, '_oppoglobe_push_ttl', 86400),
    )


# ============================================================
# HTML PAGE VIEWS (hiring only)
# ============================================================

def profile_page(request):
    return render(request, 'hiring/profile.html')


def applications_page(request):
    return render(request, 'hiring/applications.html')


def dashboard_page(request):
    return render(request, 'hiring/dashboard.html')


def documents_page(request):
    return render(request, 'hiring/documents.html')


def education_page(request):
    return render(request, 'hiring/education.html')


def skills_page(request):
    return render(request, 'hiring/skills.html')


def employment_page(request):
    return render(request, 'hiring/employment.html')


def alerts_page(request):
    return render(request, 'hiring/alerts.html', {
        'page_title': 'Notifications',
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    })


def preferences_page(request):
    return render(request, 'hiring/preferences.html')


def logout_page(request):
    return render(request, 'hiring/logout.html')


def feed_page(request):
    return render(request, 'feed_page.html', {'user': request.user})


@login_required
def posts_page(request):
    return render(request, 'post.html')


def connections_page(request):
    return render(request, 'connections.html')


def messaging_page(request):
    return render(request, 'messaging.html')


def job_detail_page(request, job_id):
    return render(request, 'hiring/job_detail.html')


@login_required
def settings_page(request):
    context = {
        'user': request.user,
        'user_type': request.user.user_type,
        'page_title': 'Settings',
    }
    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
            context['profile'] = profile
            context['profile_completeness'] = profile.profile_completeness
        except ApplicantProfile.DoesNotExist:
            pass
    elif request.user.user_type == 'admin':
        try:
            business_profile = BusinessProfile.objects.get(user=request.user)
            context['business_profile'] = business_profile
        except BusinessProfile.DoesNotExist:
            pass
    return render(request, 'hiring/settings.html', context)


@login_required
def notifications_page(request):
    return render(request, 'hiring/notifications.html', {
        'user': request.user, 'page_title': 'Notifications',
    })


@login_required
def privacy_page(request):
    return render(request, 'hiring/privacy.html', {
        'user': request.user, 'page_title': 'Privacy Settings',
    })


@login_required
def security_page(request):
    return render(request, 'hiring/security.html', {
        'user': request.user, 'page_title': 'Security Settings',
    })


@login_required
def account_page(request):
    return render(request, 'hiring/account.html', {
        'user': request.user, 'page_title': 'Account Settings',
    })


@login_required
def analytics_page(request):
    return render(request, 'hiring/analytics.html', {
        'page_title': 'Analytics Dashboard',
    })


@login_required
def black_theme_settings(request):
    return render(request, 'black-theme.html')


def custom_logout(request):
    if request.user.is_authenticated:
        logout(request)
    return render(request, 'hiring/logout.html')


# ============================================================
# AUTH / SIGNUP / LOGIN / LOGOUT
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def api_login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.user_type == 'applicant':
                try:
                    profile = ApplicantProfile.objects.get(user=user)
                    if profile.profile_completeness < 30:
                        NotificationService.send_profile_reminder(profile)
                except ApplicantProfile.DoesNotExist:
                    pass
                return Response({
                    'success': True, 'message': 'Login successful',
                    'user': UserSerializer(user).data,
                    'redirect_to': 'applicant_dashboard',
                    'user_type': 'applicant',
                })
            elif has_admin_access(user):
                return Response({
                    'success': True, 'message': 'Admin login successful',
                    'user': UserSerializer(user).data,
                    'redirect_to': 'admin_portal',
                    'user_type': 'admin',
                })
            return Response({
                'success': True, 'message': 'Login successful',
                'user': UserSerializer(user).data,
                'redirect_to': 'home',
                'user_type': user.user_type,
            })
        return Response({'success': False, 'error': 'Invalid credentials'},
                        status=status.HTTP_401_UNAUTHORIZED)
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def api_signup(request):
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                user = serializer.save()
                profile = ApplicantProfile.objects.create(user=user)
                NotificationPreference.objects.create(applicant=profile)
                Alert.objects.create(
                    applicant=profile,
                    title="Welcome to OppoGlobe!",
                    message="Thank you for joining OppoGlobe. Complete your "
                            "profile to start applying for jobs.",
                )
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return Response({
                    'success': True, 'message': 'Registration successful',
                    'user': UserSerializer(user).data,
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error during signup: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to create user profile. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser])
def api_business_signup(request):
    data = {k: v for k, v in request.POST.items()}
    data.update({k: v for k, v in request.FILES.items()})

    for field in ['username', 'email', 'password', 'company_name']:
        if not data.get(field):
            return Response({'success': False, 'error': f'{field} is required'},
                            status=status.HTTP_400_BAD_REQUEST)

    if data.get('password') != data.get('password_confirm'):
        return Response({'success': False, 'error': 'Passwords do not match'},
                        status=status.HTTP_400_BAD_REQUEST)

    if CustomUser.objects.filter(email=data['email']).exists():
        return Response({'success': False, 'error': 'Email already exists'},
                        status=status.HTTP_400_BAD_REQUEST)
    if CustomUser.objects.filter(username=data['username']).exists():
        return Response({'success': False, 'error': 'Username already exists'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                user_type='admin',
                mobile_phone=data.get('phone_number', ''),
            )
            industry = None
            if data.get('industry'):
                try:
                    industry = Industry.objects.get(id=data['industry'])
                except Industry.DoesNotExist:
                    pass
            company_size = None
            if data.get('company_size'):
                try:
                    company_size = CompanySize.objects.get(id=data['company_size'])
                except CompanySize.DoesNotExist:
                    pass

            business_profile = BusinessProfile.objects.create(
                user=user,
                company_name=data['company_name'],
                company_description=data.get('company_description', ''),
                industry=industry,
                company_size=company_size,
                website=data.get('website', ''),
                phone_number=data.get('phone_number', ''),
                address=data.get('address', ''),
                city=data.get('city', ''),
                country=data.get('country', 'South Africa'),
                postal_code=data.get('postal_code', ''),
            )
            if 'company_logo' in request.FILES:
                business_profile.company_logo = request.FILES['company_logo']
                business_profile.save()
            BusinessNotificationPreference.objects.create(business=business_profile)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return Response({
                'success': True,
                'message': 'Business account created successfully!',
                'user': {
                    'id': user.id, 'username': user.username,
                    'email': user.email, 'user_type': user.user_type,
                },
                'business_profile': {
                    'id': business_profile.id,
                    'company_name': business_profile.company_name,
                    'has_logo': bool(business_profile.company_logo),
                },
                'redirect_to': '/admin-portal/',
            }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    logout(request)
    return Response({'success': True, 'message': 'Logged out successfully'})


# ============================================================
# PASSWORD RESET
# ============================================================

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email = data.get('email', '').strip().lower()
            else:
                email = request.POST.get('email', '').strip().lower()

            if not email:
                return Response({'success': False, 'message': 'Email is required'},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                user = CustomUser.objects.get(email=email, is_active=True)
            except CustomUser.DoesNotExist:
                return Response({
                    'success': True,
                    'message': 'If an account exists with this email, you will receive a reset link.',
                })

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(f'/reset-password/{uid}/{token}/')
            api_confirm_link = request.build_absolute_uri('/api/auth/password-reset-confirm/')
            combined_token = f"{uid}-{token}"

            subject = "Password Reset Request - OppoGlobe"
            message = (
                f"Hello {user.get_full_name() or user.username},\n\n"
                f"You requested a password reset for your OppoGlobe account.\n\n"
                f"Click the link below to reset your password:\n{reset_link}\n\n"
                f"Or use the API endpoint: {api_confirm_link}\n"
                f"Token: {combined_token}\n\n"
                f"This token will expire in 24 hours.\n\n"
                f"If you didn't request this, ignore this email.\n\n"
                f"Best regards,\nOppoGlobe Team\n"
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email],
                      fail_silently=False)
            logger.info(f"Password reset requested for user: {user.username}")

            return Response({
                'success': True,
                'message': 'Password reset link sent to your email',
                'reset_link': reset_link,
                'token': combined_token,
            })
        except json.JSONDecodeError:
            return Response({'success': False, 'message': 'Invalid JSON data'},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def validate_password(self, password):
        errors = []
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not any(c.isupper() for c in password):
            errors.append('Password must contain at least one uppercase letter.')
        if not any(c.islower() for c in password):
            errors.append('Password must contain at least one lowercase letter.')
        if not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one number.')
        return errors

    def post(self, request):
        try:
            data = json.loads(request.body)
            combined_token = data.get('token', '').strip()
            email = data.get('email', '').strip().lower()
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')

            errors = {}
            if not combined_token:
                errors['token'] = ['Reset token is required']
            if not email:
                errors['email'] = ['Email is required']
            if not new_password:
                errors['new_password'] = ['New password is required']
            if not confirm_password:
                errors['confirm_password'] = ['Please confirm your password']
            if errors:
                return Response({'success': False, 'errors': errors},
                                status=status.HTTP_400_BAD_REQUEST)

            if new_password != confirm_password:
                return Response({'success': False,
                                 'errors': {'confirm_password': ['Passwords do not match']}},
                                status=status.HTTP_400_BAD_REQUEST)

            pw_errors = self.validate_password(new_password)
            if pw_errors:
                return Response({'success': False,
                                 'errors': {'new_password': pw_errors}},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                uid, token = combined_token.split('-', 1)
            except ValueError:
                return Response({'success': False,
                                 'errors': {'token': ['Invalid token format.']}},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                uid_decoded = force_str(urlsafe_base64_decode(uid))
                user = CustomUser.objects.get(pk=uid_decoded, is_active=True)
            except (TypeError, ValueError, CustomUser.DoesNotExist):
                return Response({'success': False,
                                 'errors': {'email': ['Invalid email or user.']}},
                                status=status.HTTP_400_BAD_REQUEST)

            if not default_token_generator.check_token(user, token):
                return Response({'success': False,
                                 'errors': {'token': ['Invalid or expired token.']}},
                                status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()
            logger.info(f"Password reset successful for user: {user.username}")
            return Response({'success': True,
                             'message': 'Password has been reset successfully.'})
        except json.JSONDecodeError:
            return Response({'success': False, 'error': 'Invalid JSON data'},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset confirm error: {str(e)}")
            return Response({'success': False,
                             'error': 'An unexpected error occurred.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# PROFILE / SKILLS / EDUCATION / EMPLOYMENT / DOCUMENTS
# ============================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_profile(request):
    if request.method == 'GET':
        if request.user.user_type == 'applicant':
            profile, _ = ApplicantProfile.objects.get_or_create(user=request.user)
            return Response({
                'success': True,
                'profile': ApplicantProfileSerializer(profile).data,
                'skills': SkillSerializer(profile.skills.all(), many=True).data,
                'employment': EmploymentHistorySerializer(
                    profile.employment_history.all(), many=True).data,
                'education': EducationSerializer(profile.education.all(), many=True).data,
                'documents': DocumentSerializer(profile.documents.all(), many=True).data,
                'user_type': 'applicant',
            })
        elif request.user.user_type == 'admin':
            business_profile = BusinessProfile.objects.filter(user=request.user).first()
            return Response({
                'success': True,
                'user': UserSerializer(request.user).data,
                'business_profile': BusinessProfileSerializer(business_profile).data
                    if business_profile else None,
                'user_type': 'admin',
            })
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    # PUT
    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response({'error': 'Profile not found'},
                            status=status.HTTP_404_NOT_FOUND)
        old_completeness = profile.profile_completeness
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            profile.profile_completeness = calculate_profile_completeness(profile)
            profile.save()
            if profile.profile_completeness > old_completeness + 20:
                NotificationService.send_profile_reminder(profile)
            return Response({
                'success': True,
                'profile': ApplicantProfileSerializer(profile).data,
                'completeness': profile.profile_completeness,
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.user.user_type == 'admin':
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'user': serializer.data,
                             'message': 'Profile updated successfully'})
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def api_edit_profile(request):
    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response({'error': 'Profile not found'},
                            status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        for f in ['title', 'gender', 'current_home_location', 'introduction']:
            if f in data and data[f] == '':
                data[f] = None
        serializer = ProfileUpdateSerializer(profile, data=data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            profile.profile_completeness = calculate_profile_completeness(profile)
            profile.save()
            return Response({
                'success': True,
                'profile': ApplicantProfileSerializer(updated).data,
                'completeness': profile.profile_completeness,
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.user.user_type == 'admin':
        business_profile, _ = BusinessProfile.objects.get_or_create(user=request.user)
        data = request.data.copy()
        for f in ['company_description', 'website', 'phone_number',
                  'address', 'city', 'country', 'postal_code']:
            if f in data and data[f] == '':
                data[f] = None
        for f in ['industry', 'company_size']:
            if f in data and data[f] == '':
                data[f] = None
        if 'company_logo' in request.FILES:
            data['company_logo'] = request.FILES['company_logo']
        serializer = BusinessProfileSerializer(business_profile, data=data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response({
                'success': True,
                'business_profile': BusinessProfileSerializer(updated).data,
                'message': 'Business profile updated successfully',
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_skills(request, skill_id=None):
    if request.user.user_type not in ['applicant', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response({'error': 'Profile not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            user_skills = profile.skills.all()
            business_skills = Skill.objects.filter(
                is_business_recommended=True,
            ).exclude(profile=profile)
            serializer = SkillSerializer(
                list(user_skills) + list(business_skills), many=True,
            )
            return Response({'success': True, 'skills': serializer.data,
                             'user_type': 'applicant'})

        if request.method == 'POST':
            serializer = SkillCreateSerializer(data=request.data)
            if serializer.is_valid():
                skill = serializer.save(profile=profile)
                profile.profile_completeness = calculate_profile_completeness(profile)
                profile.save()
                return Response({
                    'success': True,
                    'skill': SkillSerializer(skill).data,
                    'completeness': profile.profile_completeness,
                }, status=status.HTTP_201_CREATED)
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            if not skill_id:
                return Response({'success': False,
                                 'error': 'Skill ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            skill = get_object_or_404(Skill, id=skill_id, profile=profile)
            skill.delete()
            profile.profile_completeness = calculate_profile_completeness(profile)
            profile.save()
            return Response({'success': True,
                             'message': 'Skill deleted successfully',
                             'completeness': profile.profile_completeness})

    # business user
    try:
        business_profile = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False,
                         'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        skills = Skill.objects.filter(
            is_business_recommended=True,
            recommended_by_business=business_profile,
        ).order_by('skill_name')
        return Response({
            'success': True,
            'skills': SkillSerializer(skills, many=True).data,
            'user_type': 'business',
            'company_name': business_profile.company_name,
        })

    if request.method == 'POST':
        serializer = BusinessSkillCreateSerializer(data=request.data)
        if serializer.is_valid():
            d = serializer.validated_data
            skill = Skill.objects.create(
                skill_name=d['name'],
                proficiency=d.get('proficiency_level', 'intermediate'),
                is_business_recommended=True,
                recommended_by_business=business_profile,
            )
            return Response({
                'success': True,
                'skill': SkillSerializer(skill).data,
                'message': f'Skill "{skill.skill_name}" added',
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        if not skill_id:
            return Response({'success': False, 'error': 'Skill ID is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        skill = get_object_or_404(Skill, id=skill_id,
                                  recommended_by_business=business_profile)
        name = skill.skill_name
        skill.delete()
        return Response({'success': True,
                         'message': f'Skill "{name}" removed'})


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_education(request, education_id=None):
    if request.user.user_type not in ['applicant', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response({'success': False, 'error': 'Applicant profile not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            education = profile.education.all().order_by('-completion_year')
            return Response({
                'success': True,
                'education': EducationSerializer(education, many=True).data,
                'user_type': 'applicant',
            })

        if request.method == 'POST':
            serializer = EducationCreateSerializer(data=request.data)
            if serializer.is_valid():
                edu = serializer.save(profile=profile)
                return Response({
                    'success': True,
                    'education': EducationSerializer(edu).data,
                    'message': 'Education added successfully',
                }, status=status.HTTP_201_CREATED)
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            if not education_id:
                return Response({'success': False, 'error': 'Education ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                edu = Education.objects.get(id=education_id, profile=profile)
                edu.delete()
                return Response({'success': True,
                                 'message': 'Education deleted successfully'})
            except Education.DoesNotExist:
                return Response({'success': False, 'error': 'Education not found'},
                                status=status.HTTP_404_NOT_FOUND)

    # business
    try:
        business_profile = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False, 'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        prefs = BusinessPreference.objects.filter(
            business_profile=business_profile, preference_type='education',
        ).order_by('-created_at')
        return Response({
            'success': True,
            'preferences': BusinessPreferenceSerializer(prefs, many=True).data,
            'user_type': 'business',
            'company_name': business_profile.company_name,
        })

    if request.method == 'POST':
        data = request.data.copy()
        data['preference_type'] = 'education'
        serializer = BusinessPreferenceCreateSerializer(data=data)
        if serializer.is_valid():
            pref = serializer.save(business_profile=business_profile)
            return Response({
                'success': True,
                'preference': BusinessPreferenceSerializer(pref).data,
                'message': 'Education preference added successfully',
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        if not education_id:
            return Response({'success': False, 'error': 'Preference ID is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            pref = BusinessPreference.objects.get(
                id=education_id, business_profile=business_profile,
            )
            title = pref.title
            pref.delete()
            return Response({'success': True,
                             'message': f'Preference "{title}" deleted'})
        except BusinessPreference.DoesNotExist:
            return Response({'success': False, 'error': 'Preference not found'},
                            status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def update_education(request, education_id):
    if not education_id:
        return Response({'success': False, 'error': 'ID is required'},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
            edu = Education.objects.get(id=education_id, profile=profile)
        except (ApplicantProfile.DoesNotExist, Education.DoesNotExist):
            return Response({'success': False, 'error': 'Education not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = EducationCreateSerializer(edu, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            profile.profile_completeness = calculate_profile_completeness(profile)
            profile.save()
            return Response({
                'success': True,
                'education': EducationSerializer(updated).data,
                'message': 'Education updated successfully',
                'completeness': profile.profile_completeness,
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        business_profile = BusinessProfile.objects.get(user=request.user)
        pref = BusinessPreference.objects.get(
            id=education_id, business_profile=business_profile,
        )
    except (BusinessProfile.DoesNotExist, BusinessPreference.DoesNotExist):
        return Response({'success': False, 'error': 'Preference not found'},
                        status=status.HTTP_404_NOT_FOUND)
    serializer = BusinessPreferenceCreateSerializer(
        pref, data=request.data, partial=True,
    )
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'success': True,
            'preference': BusinessPreferenceSerializer(updated).data,
            'message': 'Education preference updated successfully',
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def api_documents(request, document_id=None):
    if request.user.user_type != 'applicant':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(ApplicantProfile, user=request.user)

    if request.method == 'GET':
        docs = profile.documents.all()
        return Response({'success': True,
                         'documents': DocumentSerializer(docs, many=True).data})

    if request.method == 'POST':
        serializer = DocumentCreateSerializer(data=request.data)
        if serializer.is_valid():
            doc = serializer.save(profile=profile)
            doc.file_name = request.FILES['file'].name
            doc.save()
            Alert.objects.create(
                applicant=profile,
                title="Document Uploaded",
                message=f"Your {doc.get_document_type_display()} has been uploaded successfully.",
            )
            return Response({
                'success': True,
                'document': DocumentSerializer(doc).data,
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        doc = get_object_or_404(Document, id=document_id, profile=profile)
        doc.delete()
        return Response({'success': True, 'message': 'Document deleted successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def api_add_document(request):
    if request.user.user_type != 'applicant':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(ApplicantProfile, user=request.user)
    data = request.data.copy()
    data['profile'] = profile.id
    serializer = DocumentCreateSerializer(data=data)
    if serializer.is_valid():
        doc = serializer.save()
        return Response({
            'success': True,
            'document': DocumentSerializer(doc).data,
            'message': 'Document uploaded successfully',
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def api_edit_document(request, document_id):
    if request.user.user_type != 'applicant':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(ApplicantProfile, user=request.user)
    doc = get_object_or_404(Document, id=document_id, profile=profile)
    data = request.data.copy()
    if 'description' in data and data['description'] == '':
        data['description'] = None
    if 'file' in request.FILES:
        data['file_name'] = request.FILES['file'].name
    serializer = DocumentCreateSerializer(doc, data=data, partial=True)
    if serializer.is_valid():
        updated = serializer.save()
        return Response({'success': True,
                         'document': DocumentSerializer(updated).data})
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_document_detail(request, document_id):
    if request.user.user_type != 'applicant':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(ApplicantProfile, user=request.user)
    doc = get_object_or_404(Document, id=document_id, profile=profile)
    return Response({'success': True, 'document': DocumentSerializer(doc).data})


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_employment(request, employment_id=None):
    if request.user.user_type not in ['applicant', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
        except ApplicantProfile.DoesNotExist:
            return Response({'success': False, 'error': 'Applicant profile not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            employment = profile.employment_history.all().order_by('-start_date')
            return Response({
                'success': True,
                'employment': EmploymentHistorySerializer(employment, many=True).data,
                'user_type': 'applicant',
            })

        if request.method == 'POST':
            serializer = EmploymentCreateSerializer(data=request.data)
            if serializer.is_valid():
                emp = serializer.save(profile=profile)
                profile.profile_completeness = calculate_profile_completeness(profile)
                profile.save()
                return Response({
                    'success': True,
                    'employment': EmploymentHistorySerializer(emp).data,
                    'message': 'Employment history added successfully',
                    'completeness': profile.profile_completeness,
                }, status=status.HTTP_201_CREATED)
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            if not employment_id:
                return Response({'success': False, 'error': 'Employment ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                emp = EmploymentHistory.objects.get(id=employment_id, profile=profile)
                emp.delete()
                profile.profile_completeness = calculate_profile_completeness(profile)
                profile.save()
                return Response({'success': True,
                                 'message': 'Employment history deleted successfully',
                                 'completeness': profile.profile_completeness})
            except EmploymentHistory.DoesNotExist:
                return Response({'success': False, 'error': 'Employment not found'},
                                status=status.HTTP_404_NOT_FOUND)

    # business
    try:
        business_profile = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False, 'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        prefs = BusinessEmploymentPreference.objects.filter(
            business_profile=business_profile,
        ).order_by('-created_at')
        return Response({
            'success': True,
            'preferences': BusinessEmploymentPreferenceSerializer(prefs, many=True).data,
            'user_type': 'business',
            'company_name': business_profile.company_name,
        })

    if request.method == 'POST':
        serializer = BusinessEmploymentPreferenceCreateSerializer(data=request.data)
        if serializer.is_valid():
            pref = serializer.save(business_profile=business_profile)
            return Response({
                'success': True,
                'preference': BusinessEmploymentPreferenceSerializer(pref).data,
                'message': 'Employment preference added successfully',
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        if not employment_id:
            return Response({'success': False, 'error': 'Preference ID is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            pref = BusinessEmploymentPreference.objects.get(
                id=employment_id, business_profile=business_profile,
            )
            pref.delete()
            return Response({'success': True,
                             'message': 'Employment preference deleted successfully'})
        except BusinessEmploymentPreference.DoesNotExist:
            return Response({'success': False, 'error': 'Preference not found'},
                            status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def update_employment(request, employment_id):
    if not employment_id:
        return Response({'success': False, 'error': 'ID is required'},
                        status=status.HTTP_400_BAD_REQUEST)

    if request.user.user_type == 'applicant':
        try:
            profile = ApplicantProfile.objects.get(user=request.user)
            emp = EmploymentHistory.objects.get(id=employment_id, profile=profile)
        except (ApplicantProfile.DoesNotExist, EmploymentHistory.DoesNotExist):
            return Response({'success': False, 'error': 'Employment not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = EmploymentCreateSerializer(emp, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            profile.profile_completeness = calculate_profile_completeness(profile)
            profile.save()
            return Response({
                'success': True,
                'employment': EmploymentHistorySerializer(updated).data,
                'message': 'Employment history updated successfully',
                'completeness': profile.profile_completeness,
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        business_profile = BusinessProfile.objects.get(user=request.user)
        pref = BusinessEmploymentPreference.objects.get(
            id=employment_id, business_profile=business_profile,
        )
    except (BusinessProfile.DoesNotExist, BusinessEmploymentPreference.DoesNotExist):
        return Response({'success': False, 'error': 'Preference not found'},
                        status=status.HTTP_404_NOT_FOUND)
    serializer = BusinessEmploymentPreferenceCreateSerializer(
        pref, data=request.data, partial=True,
    )
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'success': True,
            'preference': BusinessEmploymentPreferenceSerializer(updated).data,
            'message': 'Employment preference updated successfully',
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# BUSINESS PROFILE
# ============================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def api_business_profile(request):
    if not has_business_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    business_profile = BusinessProfile.objects.filter(user=request.user).first()
    if not business_profile:
        return Response({'error': 'Business profile not found'},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({
            'success': True,
            'business_profile': BusinessProfileSerializer(business_profile).data,
        })

    data = request.data.copy()
    if 'company_logo' in request.FILES:
        data['company_logo'] = request.FILES['company_logo']
    elif data.get('company_logo') == '':
        data['company_logo'] = None
    serializer = BusinessProfileSerializer(business_profile, data=data, partial=True)
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'success': True,
            'business_profile': BusinessProfileSerializer(updated).data,
            'message': 'Business profile updated successfully',
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# LOOKUP APIS (industries, sizes, categories)
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_industries(request):
    industries = Industry.objects.filter(is_active=True).order_by('name')
    return Response({
        'success': True,
        'industries': IndustrySerializer(industries, many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_company_sizes(request):
    sizes = CompanySize.objects.filter(is_active=True).order_by('min_employees')
    return Response({
        'success': True,
        'company_sizes': CompanySizeSerializer(sizes, many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_job_categories(request):
    industry_id = request.GET.get('industry_id')
    if industry_id:
        categories = JobCategory.objects.filter(industry_id=industry_id, is_active=True)
    else:
        categories = JobCategory.objects.filter(is_active=True)
    return Response({
        'success': True,
        'categories': JobCategorySerializer(categories.order_by('name'), many=True).data,
    })


# ============================================================
# JOB LISTING / APPLICATION
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_job_listings(request):
    try:
        job_listings = JobListing.objects.filter(status='published')

        if request.user.is_authenticated:
            if has_admin_access(request.user):
                if has_business_access(request.user) and not request.user.is_superuser:
                    try:
                        business_profile = BusinessProfile.objects.get(user=request.user)
                        business_jobs = JobListing.objects.filter(
                            company_name=business_profile.company_name,
                        )
                        if business_jobs.exists():
                            job_listings = business_jobs
                    except BusinessProfile.DoesNotExist:
                        pass
                else:
                    job_listings = JobListing.objects.all()

        job_listings = job_listings.order_by('-created_at')
        serializer = JobListingSerializer(
            job_listings, many=True, context={'request': request},
        )
        return Response({
            'success': True,
            'jobs': serializer.data,
            'total': job_listings.count(),
        })
    except Exception as e:
        logger.error(f"Error in api_job_listings: {str(e)}")
        return Response({'success': False, 'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_job_detail(request, job_id):
    try:
        jobs = JobListing.objects.filter(status='published')
        if not jobs.exists():
            return Response({'success': False, 'error': 'No jobs available'},
                            status=status.HTTP_404_NOT_FOUND)
        if job_id == '1':
            job_listing = jobs.first()
        else:
            try:
                job_listing = JobListing.objects.get(id=job_id)
            except (ValueError, JobListing.DoesNotExist):
                job_listing = jobs.first()
        serializer = JobListingSerializer(job_listing, context={'request': request})
        return Response({
            'success': True,
            'job': serializer.data,
            'has_applied': False,
        })
    except Exception as e:
        logger.error(f"Error in api_job_detail: {str(e)}")
        return Response({'success': False, 'error': 'Failed to load job details.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_applications(request):
    if request.user.user_type != 'applicant':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    profile = get_object_or_404(ApplicantProfile, user=request.user)
    applications = Application.objects.filter(
        applicant=profile,
    ).select_related('job_listing').order_by('-applied_date')
    return Response({
        'success': True,
        'applications': ApplicationSerializer(
            applications, many=True, context={'request': request},
        ).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_apply_job(request, job_id):
    try:
        if request.user.user_type != 'applicant':
            return Response({
                'success': False,
                'error': 'Unauthorized. Only applicants can apply for jobs.',
            }, status=status.HTTP_403_FORBIDDEN)

        profile = get_object_or_404(ApplicantProfile, user=request.user)
        job_listing = get_object_or_404(JobListing, id=job_id, status='published')

        if job_listing.apply_by < timezone.now().date():
            return Response({
                'success': False,
                'error': 'The application deadline has passed.',
            }, status=status.HTTP_400_BAD_REQUEST)

        existing = Application.objects.filter(
            applicant=profile, job_listing=job_listing,
        ).first()
        if existing:
            return Response({
                'success': False,
                'error': 'You have already applied for this position.',
                'application_id': str(existing.id),
                'current_status': existing.status,
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = ApplicationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        application = serializer.save(
            applicant=profile, job_listing=job_listing, status='submitted',
        )
        NotificationService.send_application_submission(application)

        return Response({
            'success': True,
            'message': 'Application submitted successfully!',
            'application': {
                'id': str(application.id),
                'job_title': job_listing.title,
                'company': job_listing.company_name,
                'location': job_listing.location,
                'applied_date': application.applied_date.isoformat(),
                'status': application.status,
                'reference_number': f"APP-{application.id.hex[:8].upper()}",
                'listing_reference': job_listing.listing_reference,
            },
            'next_steps': [
                'Your application has been received and is under review',
                'You will be notified about updates',
                'Check your application status in "My Applications"',
            ],
        }, status=status.HTTP_201_CREATED)
    except JobListing.DoesNotExist:
        return Response({'success': False, 'error': 'Job listing not found.'},
                        status=status.HTTP_404_NOT_FOUND)
    except ApplicantProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Applicant profile not found. Please complete your profile.',
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Unexpected error in api_apply_job: {str(e)}")
        return Response({'success': False, 'error': 'An unexpected error occurred.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# ALERTS / NOTIFICATIONS (unified)
# ============================================================

def _serialize_unified_alert(alert, user_type):
    return {
        'id': str(alert.id),
        'title': alert.title,
        'message': alert.message,
        'is_read': bool(alert.is_read),
        'created_at': alert.created_at.isoformat(),
        'type': getattr(alert, 'alert_type', 'system') or 'system',
        'app_source': _infer_notification_source(alert.title, alert.message),
        'user_type': user_type,
    }


def _unified_alerts_for_user(user):
    data = []
    business_profile = BusinessProfile.objects.filter(user=user).first()
    if business_profile:
        qs = BusinessAlert.objects.filter(
            business=business_profile, is_active=True,
        ).order_by('-created_at')[:100]
        data = [_serialize_unified_alert(x, 'business') for x in qs]
    else:
        profile = ApplicantProfile.objects.filter(user=user).first()
        if profile:
            qs = Alert.objects.filter(applicant=profile).order_by('-created_at')[:100]
            data = [_serialize_unified_alert(x, 'applicant') for x in qs]
    data.sort(key=lambda x: x['created_at'], reverse=True)
    return data


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_alerts(request):
    try:
        alerts = _unified_alerts_for_user(request.user)
        return Response({
            'success': True,
            'alerts': alerts,
            'total': len(alerts),
            'unread_count': sum(1 for x in alerts if not x['is_read']),
        })
    except Exception as exc:
        logger.exception('Alerts load failed: %s', exc)
        return Response({'success': False, 'alerts': [],
                         'error': 'Failed to load notifications.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_current_user_alert(user, alert_id):
    business_profile = BusinessProfile.objects.filter(user=user).first()
    if business_profile:
        return get_object_or_404(BusinessAlert, id=alert_id, business=business_profile)
    profile = get_object_or_404(ApplicantProfile, user=user)
    return get_object_or_404(Alert, id=alert_id, applicant=profile)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mark_alert_read(request, alert_id):
    try:
        alert = _get_current_user_alert(request.user, alert_id)
        alert.is_read = True
        alert.save(update_fields=['is_read'])
        return Response({'success': True, 'message': 'Marked as read.'})
    except Exception as exc:
        logger.exception('Mark read failed: %s', exc)
        return Response({'success': False, 'error': 'Unable to mark as read.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_delete_alert(request, alert_id):
    try:
        alert = _get_current_user_alert(request.user, alert_id)
        alert.delete()
        return Response({'success': True, 'message': 'Notification deleted.'})
    except Exception as exc:
        logger.exception('Delete failed: %s', exc)
        return Response({'success': False, 'error': 'Unable to delete notification.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# legacy aliases for backward-compat
legacy_api_alerts = api_alerts
legacy_api_mark_alert_read = api_mark_alert_read
legacy_api_delete_alert = api_delete_alert
api_user_alerts = api_alerts


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_notification_preferences(request):
    if request.user.user_type not in ['applicant', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.user_type == 'applicant':
        profile = get_object_or_404(ApplicantProfile, user=request.user)
        prefs, _ = NotificationPreference.objects.get_or_create(applicant=profile)
        if request.method == 'GET':
            return Response({
                'success': True,
                'preferences': NotificationPreferenceSerializer(prefs).data,
                'user_type': 'applicant',
            })
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'preferences': serializer.data,
                'user_type': 'applicant',
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    business_profile = BusinessProfile.objects.filter(user=request.user).first()
    if not business_profile:
        return Response({'success': False, 'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)
    prefs, _ = BusinessNotificationPreference.objects.get_or_create(
        business=business_profile,
        defaults={
            'email_notifications': True, 'in_app_notifications': True,
            'new_applications': True, 'job_expiry_alerts': True,
            'candidate_updates': True, 'system_maintenance': False,
            'marketing_emails': False,
        },
    )
    if request.method == 'GET':
        return Response({
            'success': True,
            'preferences': {
                'email_notifications': prefs.email_notifications,
                'in_app_notifications': prefs.in_app_notifications,
                'new_applications': prefs.new_applications,
                'job_expiry_alerts': prefs.job_expiry_alerts,
                'candidate_updates': prefs.candidate_updates,
                'system_maintenance': prefs.system_maintenance,
                'marketing_emails': prefs.marketing_emails,
                'user_type': 'business',
                'company_name': business_profile.company_name,
            },
            'user_type': 'business',
        })
    for field in ['email_notifications', 'in_app_notifications', 'new_applications',
                  'job_expiry_alerts', 'candidate_updates', 'system_maintenance',
                  'marketing_emails']:
        if field in request.data:
            setattr(prefs, field, request.data[field])
    prefs.save()
    return Response({
        'success': True,
        'message': 'Notification preferences updated',
        'user_type': 'business',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_sent_notifications(request):
    if request.user.user_type not in ['applicant', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.user_type == 'applicant':
        profile = get_object_or_404(ApplicantProfile, user=request.user)
        notifications = profile.sent_notifications.all()[:50]
        return Response({
            'success': True,
            'notifications': SentNotificationSerializer(notifications, many=True).data,
            'user_type': 'applicant',
            'total_count': notifications.count(),
        })

    business_profile = BusinessProfile.objects.filter(user=request.user).first()
    if not business_profile:
        return Response({'success': False, 'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)
    notifications = business_profile.sent_notifications.all()[:50]
    return Response({
        'success': True,
        'notifications': [
            {'id': n.id, 'subject': n.subject, 'message': n.message,
             'notification_type': n.notification_type,
             'sent_at': n.sent_at, 'is_read': n.is_read}
            for n in notifications
        ],
        'user_type': 'business',
        'total_count': notifications.count(),
    })


# ============================================================
# ADMIN / BUSINESS JOB MANAGEMENT
# ============================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def api_admin_jobs(request):
    if not (has_admin_access(request.user) or has_business_access(request.user)):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        if has_business_access(request.user) and not request.user.is_superuser:
            try:
                business_profile = BusinessProfile.objects.get(user=request.user)
                jobs = JobListing.objects.filter(
                    company_name=business_profile.company_name,
                ).order_by('-created_at')
            except BusinessProfile.DoesNotExist:
                return Response({'success': False,
                                 'error': 'Business profile not found'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            jobs = JobListing.objects.all().order_by('-created_at')

        status_filter = request.GET.get('status', 'all')
        if status_filter != 'all':
            jobs = jobs.filter(status=status_filter)

        if has_business_access(request.user) and not request.user.is_superuser:
            try:
                bp = BusinessProfile.objects.get(user=request.user)
                base = JobListing.objects.filter(company_name=bp.company_name)
            except BusinessProfile.DoesNotExist:
                base = JobListing.objects.none()
        else:
            base = JobListing.objects.all()

        return Response({
            'success': True,
            'jobs': JobListingSerializer(jobs, many=True,
                                         context={'request': request}).data,
            'counts': {
                'total': base.count(),
                'published': base.filter(status='published').count(),
                'draft': base.filter(status='draft').count(),
                'archived': base.filter(status='closed').count(),
            },
        })

    # POST
    business_profile = None
    if has_business_access(request.user) and not request.user.is_superuser:
        try:
            business_profile = BusinessProfile.objects.get(user=request.user)
        except BusinessProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Business profile not found. Please complete your business profile.',
            }, status=status.HTTP_400_BAD_REQUEST)

    data = request.data.copy()
    if 'company_logo' in request.FILES:
        data['company_logo'] = request.FILES['company_logo']
    elif data.get('company_logo') in ['', 'null', 'undefined']:
        data['company_logo'] = None

    if business_profile and not request.user.is_superuser:
        data['company_name'] = business_profile.company_name

    serializer = AdminJobCreateSerializer(data=data, context={'request': request})
    if serializer.is_valid():
        try:
            job = serializer.save()
            logger.info(
                f"User {request.user.username} created job: {job.title} "
                f"for company: {job.company_name}",
            )
            return Response({
                'success': True,
                'message': 'Job created successfully!',
                'job': JobListingSerializer(job, context={'request': request}).data,
                'job_id': str(job.id),
                'redirect_url': '/admin-portal/jobs/',
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error saving job: {str(e)}")
            return Response({'success': False, 'error': f'Failed to save job: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    error_list = []
    for field, errors in serializer.errors.items():
        if isinstance(errors, list):
            for error in errors:
                error_list.append(f"{field}: {error}")
        else:
            error_list.append(f"{field}: {errors}")
    return Response({
        'success': False,
        'message': 'Please fix the errors below',
        'errors': serializer.errors,
        'error_list': error_list,
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def api_admin_job_detail(request, job_id):
    if not (has_admin_access(request.user) or has_business_access(request.user)):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        job = JobListing.objects.get(id=job_id)
    except JobListing.DoesNotExist:
        return Response({'success': False, 'error': 'Job not found'},
                        status=status.HTTP_404_NOT_FOUND)

    if has_business_access(request.user) and not request.user.is_superuser:
        try:
            business_profile = BusinessProfile.objects.get(user=request.user)
            if job.company_name != business_profile.company_name:
                return Response({'success': False, 'error': 'Unauthorized'},
                                status=status.HTTP_403_FORBIDDEN)
        except BusinessProfile.DoesNotExist:
            return Response({'success': False, 'error': 'Business profile not found'},
                            status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        return Response({
            'success': True,
            'job': JobListingSerializer(job, context={'request': request}).data,
            'application_count': Application.objects.filter(job_listing=job).count(),
        })

    if request.method == 'PUT':
        data = request.data.copy()
        if 'company_logo' in request.FILES:
            data['company_logo'] = request.FILES['company_logo']
        elif data.get('company_logo') in ['', 'null', 'undefined']:
            data['company_logo'] = None
        if has_business_access(request.user) and not request.user.is_superuser:
            data.pop('company_name', None)
        serializer = AdminJobCreateSerializer(job, data=data, partial=True,
                                              context={'request': request})
        if serializer.is_valid():
            updated = serializer.save()
            return Response({
                'success': True,
                'job': JobListingSerializer(updated, context={'request': request}).data,
                'message': 'Job updated successfully',
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    title = job.title
    job.delete()
    return Response({'success': True, 'message': f'Job "{title}" deleted'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_admin_job_status(request, job_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        job = JobListing.objects.get(id=job_id)
    except JobListing.DoesNotExist:
        return Response({'success': False, 'error': 'Job not found'},
                        status=status.HTTP_404_NOT_FOUND)
    if has_business_access(request.user) and not request.user.is_superuser:
        try:
            bp = BusinessProfile.objects.get(user=request.user)
            if job.company_name != bp.company_name:
                return Response({'error': 'Unauthorized'},
                                status=status.HTTP_403_FORBIDDEN)
        except BusinessProfile.DoesNotExist:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    new_status = request.data.get('status')
    valid = ['draft', 'under_review', 'published', 'closed']
    if new_status not in valid:
        return Response({'success': False,
                         'error': f'Invalid status. Use one of: {", ".join(valid)}'},
                        status=status.HTTP_400_BAD_REQUEST)
    job.status = new_status
    job.save()
    return Response({
        'success': True,
        'message': f'Job status updated to {new_status}',
        'job': JobListingSerializer(job, context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_job_applications(request, job_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        job = JobListing.objects.get(id=job_id)
    except JobListing.DoesNotExist:
        return Response({'success': False, 'error': 'Job not found'},
                        status=status.HTTP_404_NOT_FOUND)
    applications = Application.objects.filter(job_listing=job).select_related(
        'applicant', 'applicant__user',
    ).order_by('-applied_date')
    data = [{
        'id': str(app.id),
        'applicant_name': f"{app.applicant.first_name} {app.applicant.last_name}",
        'applicant_email': app.applicant.user.email,
        'status': app.status,
        'applied_date': app.applied_date,
        'cover_letter': app.cover_letter,
        'reference_number': f"APP-{app.id.hex[:8].upper()}",
    } for app in applications]
    return Response({
        'success': True,
        'job_title': job.title,
        'applications': data,
        'total_applications': len(data),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_admin_application_status(request, application_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        return Response({'success': False, 'error': 'Application not found'},
                        status=status.HTTP_404_NOT_FOUND)

    serializer = AdminApplicationStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)
    new_status = serializer.validated_data['status']
    old_status = application.status
    application.status = new_status
    application.save()
    try:
        Alert.objects.create(
            applicant=application.applicant,
            title="Application Status Updated",
            message=f"Your application for {application.job_listing.title} "
                    f"has been updated from {old_status} to {new_status}.",
        )
        SentNotification.objects.create(
            applicant=application.applicant,
            notification_type='application_status_update',
            subject="Application Status Update",
            message=f"Your application status for {application.job_listing.title} "
                    f"at {application.job_listing.company_name} is now "
                    f"{new_status.replace('_', ' ').title()}.",
            sent_via='in_app',
        )
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
    return Response({
        'success': True,
        'message': f'Application status updated to {new_status}',
        'application': {
            'id': application.id,
            'applicant_name': f"{application.applicant.first_name} "
                              f"{application.applicant.last_name}",
            'job_title': application.job_listing.title,
            'status': application.status,
        },
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def api_edit_job(request, job_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        job = JobListing.objects.get(id=job_id)
    except JobListing.DoesNotExist:
        return Response({'success': False, 'error': 'Job not found'},
                        status=status.HTTP_404_NOT_FOUND)
    if has_business_access(request.user) and not request.user.is_superuser:
        try:
            bp = BusinessProfile.objects.get(user=request.user)
            if job.company_name != bp.company_name:
                return Response({'error': 'Unauthorized'},
                                status=status.HTTP_403_FORBIDDEN)
        except BusinessProfile.DoesNotExist:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data.copy()
    if 'company_logo' in request.FILES:
        data['company_logo'] = request.FILES['company_logo']
    elif 'company_logo' in data and data['company_logo'] in ('', 'null'):
        if has_business_access(request.user) and not request.user.is_superuser:
            try:
                bp = BusinessProfile.objects.get(user=request.user)
                data['company_logo'] = bp.company_logo if bp.company_logo else None
            except BusinessProfile.DoesNotExist:
                data['company_logo'] = None
        else:
            data['company_logo'] = None
    elif data.get('company_logo') is None:
        data.pop('company_logo', None)

    if has_business_access(request.user) and not request.user.is_superuser:
        data.pop('company_name', None)

    if 'apply_by' in data and not data['apply_by']:
        return Response({'success': False, 'error': 'Apply by date is required'},
                        status=status.HTTP_400_BAD_REQUEST)
    if 'ee_position' in data and isinstance(data['ee_position'], str):
        data['ee_position'] = data['ee_position'].lower() in ('true', '1', 'yes')

    serializer = AdminJobCreateSerializer(job, data=data, partial=True,
                                          context={'request': request})
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'success': True,
            'job': JobListingSerializer(updated, context={'request': request}).data,
            'message': 'Job updated successfully',
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# ADMIN PAGES
# ============================================================

@admin_required
def admin_portal(request):
    return render(request, 'hiring/admin_portal.html')


@admin_required
def admin_jobs_page(request):
    return render(request, 'hiring/admin_jobs.html')


@admin_required
def admin_applications_page(request):
    return render(request, 'hiring/admin_applications.html')


@admin_required
def admin_users_page(request):
    return render(request, 'hiring/admin_users.html')


@admin_required
def admin_analytics_page(request):
    return render(request, 'hiring/admin_analytics.html')


@admin_required
def admin_job_edit_page(request):
    job_id = request.GET.get('job_id')
    if not job_id:
        return render(request, 'hiring/admin_job_edit.html',
                      {'page_title': 'Create New Job - Admin Portal',
                       'job': None, 'is_edit': False})
    try:
        job = get_object_or_404(JobListing, id=job_id)
        return render(request, 'hiring/admin_job_edit.html', {
            'page_title': f'Edit Job - {job.title}',
            'job': job, 'is_edit': True,
        })
    except Exception:
        return redirect('/admin-portal/jobs/')


@admin_required
def save_job(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    try:
        data = json.loads(request.body)
        job_id = data.get('id')
        for field in ['title', 'location', 'position_summary', 'job_description']:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required',
                })
        if job_id:
            job = get_object_or_404(JobListing, id=job_id)
            action = 'updated'
        else:
            job = JobListing()
            action = 'created'
        job.title = data.get('title', '')
        job.company_name = data.get('company_name', 'OppoGlobe')
        job.location = data.get('location', '')
        job.position_summary = data.get('position_summary', '')
        job.job_description = data.get('job_description', '')
        job.apply_by = data.get('apply_by')
        job.status = data.get('status', 'draft')
        job.is_remote = data.get('is_remote', False)
        job.vacancies = data.get('vacancies', 1)
        if not job.listing_reference:
            job.listing_reference = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        job.save()
        return JsonResponse({
            'success': True,
            'message': f'Job {action} successfully!',
            'job_id': job.id,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@admin_required
def get_job_data(request, job_id):
    try:
        job = get_object_or_404(JobListing, id=job_id)
        return JsonResponse({
            'success': True,
            'job': {
                'id': job.id, 'title': job.title,
                'company_name': job.company_name, 'location': job.location,
                'position_summary': job.position_summary,
                'job_description': job.job_description,
                'apply_by': job.apply_by.strftime('%Y-%m-%d') if job.apply_by else '',
                'status': job.status, 'listing_reference': job.listing_reference,
                'is_remote': job.is_remote, 'vacancies': job.vacancies,
            },
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================
# ADMIN DASHBOARD / STATS / ANALYTICS
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    if has_business_access(request.user) and not request.user.is_superuser:
        try:
            bp = BusinessProfile.objects.get(user=request.user)
            base = JobListing.objects.filter(company_name=bp.company_name)
            total_jobs = base.filter(status='published').count()
            total_applications = Application.objects.filter(
                job_listing__in=base,
            ).count()
            total_companies = 1
        except BusinessProfile.DoesNotExist:
            total_jobs = total_applications = total_companies = 0
    else:
        total_jobs = JobListing.objects.filter(status='published').count()
        total_applications = Application.objects.count()
        total_companies = JobListing.objects.values('company_name').distinct().count()

    return Response({
        'success': True,
        'stats': {
            'total_users': CustomUser.objects.filter(user_type='applicant').count(),
            'total_jobs': total_jobs,
            'total_applications': total_applications,
            'total_companies': total_companies,
            'user_type': request.user.user_type,
            'is_business_admin': has_business_access(request.user),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_dashboard_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    total_users = CustomUser.objects.filter(user_type='applicant').count()
    new_users_week = CustomUser.objects.filter(
        user_type='applicant', date_joined__date__gte=week_ago,
    ).count()
    new_users_month = CustomUser.objects.filter(
        user_type='applicant', date_joined__date__gte=month_ago,
    ).count()

    total_jobs = JobListing.objects.filter(status='published').count()
    draft_jobs = JobListing.objects.filter(status='draft').count()
    expired_jobs = JobListing.objects.filter(apply_by__lt=today).count()

    total_applications = Application.objects.count()
    applications_week = Application.objects.filter(
        applied_date__date__gte=week_ago,
    ).count()
    applications_month = Application.objects.filter(
        applied_date__date__gte=month_ago,
    ).count()
    application_statuses = Application.objects.values('status').annotate(
        count=Count('id'),
    ).order_by('status')

    profile_stats = ApplicantProfile.objects.aggregate(
        avg_completeness=Avg('profile_completeness'),
        high_completeness=Count('id', filter=Q(profile_completeness__gte=80)),
        medium_completeness=Count('id', filter=Q(profile_completeness__gte=50,
                                                  profile_completeness__lt=80)),
        low_completeness=Count('id', filter=Q(profile_completeness__lt=50)),
    )

    return Response({
        'success': True,
        'stats': {
            'users': {
                'total': total_users,
                'new_this_week': new_users_week,
                'new_this_month': new_users_month,
                'growth_rate_week': round(
                    (new_users_week / max(total_users, 1)) * 100, 1),
            },
            'jobs': {
                'total': total_jobs, 'draft': draft_jobs,
                'expired': expired_jobs,
                'active': total_jobs - expired_jobs,
            },
            'applications': {
                'total': total_applications,
                'this_week': applications_week,
                'this_month': applications_month,
                'status_breakdown': list(application_statuses),
            },
            'alerts': {
                'total': Alert.objects.count(),
                'unread': Alert.objects.filter(is_read=False).count(),
            },
            'profiles': profile_stats,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_quick_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    profile_stats = ApplicantProfile.objects.aggregate(
        avg_completeness=Avg('profile_completeness'),
        high_completeness=Count('id', filter=Q(profile_completeness__gte=80)),
        low_completeness=Count('id', filter=Q(profile_completeness__lt=50)),
    )
    return Response({
        'success': True,
        'stats': {
            'today_applications': Application.objects.filter(
                applied_date__date=today).count(),
            'week_applications': Application.objects.filter(
                applied_date__date__gte=week_ago).count(),
            'pending_jobs': JobListing.objects.filter(status='draft').count(),
            'new_users': CustomUser.objects.filter(
                user_type='applicant', date_joined__date__gte=week_ago).count(),
            'active_jobs': JobListing.objects.filter(
                status='published', apply_by__gte=today).count(),
            'expired_jobs': JobListing.objects.filter(apply_by__lt=today).count(),
            'avg_profile_complete': round(profile_stats['avg_completeness'] or 0, 1),
            'high_complete_profiles': profile_stats['high_completeness'] or 0,
            'low_complete_profiles': profile_stats['low_completeness'] or 0,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_recent_activity(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    recent_users = CustomUser.objects.filter(
        user_type='applicant').order_by('-date_joined')[:5]
    recent_applications = Application.objects.select_related(
        'applicant', 'job_listing').order_by('-applied_date')[:5]
    recent_jobs = JobListing.objects.order_by('-created_at')[:5]

    activity = []
    for user in recent_users:
        activity.append({
            'type': 'user_registration',
            'title': 'New user registration',
            'description': f'{user.get_full_name() or user.username} registered',
            'timestamp': user.date_joined,
            'badge': 'User',
        })
    for app in recent_applications:
        activity.append({
            'type': 'application',
            'title': 'Job application submitted',
            'description': f'{app.applicant.first_name} {app.applicant.last_name} '
                           f'applied for {app.job_listing.title}',
            'timestamp': app.applied_date,
            'badge': 'Application',
        })
    for job in recent_jobs:
        activity.append({
            'type': 'job_listing',
            'title': 'New job listing published',
            'description': f'{job.title} published',
            'timestamp': job.created_at,
            'badge': 'Job',
        })
    activity.sort(key=lambda x: x['timestamp'], reverse=True)
    return Response({'success': True, 'activity': activity[:10]})


# alias
api_recent_activity = api_admin_recent_activity


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_system_health(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    checks = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks.append({'component': 'Database Connection', 'status': 'healthy',
                       'message': 'Database is accessible',
                       'icon': 'check-circle', 'color': 'success'})
    except Exception as e:
        checks.append({'component': 'Database Connection', 'status': 'unhealthy',
                       'message': f'Database error: {str(e)}',
                       'icon': 'exclamation-triangle', 'color': 'danger'})
    try:
        media_path = settings.MEDIA_ROOT
        if os.path.exists(media_path) and os.access(media_path, os.W_OK):
            checks.append({'component': 'File System', 'status': 'healthy',
                           'message': 'Media directory is writable',
                           'icon': 'check-circle', 'color': 'success'})
        else:
            checks.append({'component': 'File System', 'status': 'warning',
                           'message': 'Media directory may not be writable',
                           'icon': 'exclamation-triangle', 'color': 'warning'})
    except Exception as e:
        checks.append({'component': 'File System', 'status': 'unhealthy',
                       'message': f'File system error: {str(e)}',
                       'icon': 'exclamation-triangle', 'color': 'danger'})
    try:
        if getattr(settings, 'EMAIL_BACKEND', None):
            checks.append({'component': 'Email Service', 'status': 'configured',
                           'message': 'Email backend is configured',
                           'icon': 'check-circle', 'color': 'success'})
        else:
            checks.append({'component': 'Email Service', 'status': 'warning',
                           'message': 'Email configuration needed',
                           'icon': 'exclamation-triangle', 'color': 'warning'})
    except Exception as e:
        checks.append({'component': 'Email Service', 'status': 'unhealthy',
                       'message': str(e),
                       'icon': 'exclamation-triangle', 'color': 'danger'})
    return Response({'success': True, 'health_checks': checks})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_simple_health_check(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    return Response({'success': True, 'health_checks': [
        {'component': 'Export System', 'status': 'healthy',
         'message': 'Export system is ready',
         'icon': 'check-circle', 'color': 'success'},
        {'component': 'Database', 'status': 'healthy',
         'message': 'Database is accessible',
         'icon': 'check-circle', 'color': 'success'},
        {'component': 'File System', 'status': 'healthy',
         'message': 'File downloads enabled',
         'icon': 'check-circle', 'color': 'success'},
    ]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_database_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    models = [
        (CustomUser, 'CustomUser'), (ApplicantProfile, 'ApplicantProfile'),
        (BusinessProfile, 'BusinessProfile'), (JobListing, 'JobListing'),
        (Application, 'Application'), (Alert, 'Alert'),
        (BusinessAlert, 'BusinessAlert'), (Document, 'Document'),
        (Skill, 'Skill'), (EmploymentHistory, 'EmploymentHistory'),
        (Education, 'Education'), (Post, 'Post'), (Comment, 'Comment'),
    ]
    stats = [{'table_name': name, 'row_count': model.objects.count(),
              'size': 'N/A'} for model, name in models]
    return Response({'success': True, 'database_stats': {
        'tables': stats, 'total_tables': len(stats)}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_analytics(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    data = request.data
    days = data.get('days', 30)
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    if start_date_str and end_date_str:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

    today = timezone.now().date()
    total_users = CustomUser.objects.filter(user_type='applicant').count()
    total_jobs = JobListing.objects.filter(status='published').count()
    total_applications = Application.objects.count()
    conversion_rate = round((total_applications / total_jobs) * 100, 1) if total_jobs else 0
    avg_profile = ApplicantProfile.objects.aggregate(
        a=Avg('profile_completeness'))['a'] or 0

    user_growth_data, user_growth_labels = [], []
    applications_data, applications_labels = [], []
    for i in range(days, 0, -1):
        d = end_date - timedelta(days=i)
        user_growth_data.append(CustomUser.objects.filter(
            user_type='applicant', date_joined__date=d).count())
        user_growth_labels.append(d.strftime('%m/%d'))
        applications_data.append(Application.objects.filter(
            applied_date__date=d).count())
        applications_labels.append(d.strftime('%m/%d'))

    status_distribution = Application.objects.values('status').annotate(
        count=Count('id')).order_by('status')
    status_labels = [x['status'].replace('_', ' ').title() for x in status_distribution]
    status_data = [x['count'] for x in status_distribution]

    top_locations = JobListing.objects.filter(status='published').values(
        'location').annotate(count=Count('id')).order_by('-count')[:10]
    location_labels = [x['location'] for x in top_locations]
    location_data = [x['count'] for x in top_locations]

    high = ApplicantProfile.objects.filter(profile_completeness__gte=80).count()
    medium = ApplicantProfile.objects.filter(
        profile_completeness__gte=50, profile_completeness__lt=80).count()
    low = ApplicantProfile.objects.filter(profile_completeness__lt=50).count()
    total_profiles = high + medium + low
    profile_completion = {
        'high': round((high / total_profiles) * 100, 1) if total_profiles else 0,
        'medium': round((medium / total_profiles) * 100, 1) if total_profiles else 0,
        'low': round((low / total_profiles) * 100, 1) if total_profiles else 0,
    }

    activity_timeline = {'labels': [], 'registrations': [], 'applications': []}
    for i in range(7, 0, -1):
        d = end_date - timedelta(days=i)
        activity_timeline['labels'].append(d.strftime('%a'))
        activity_timeline['registrations'].append(CustomUser.objects.filter(
            user_type='applicant', date_joined__date=d).count())
        activity_timeline['applications'].append(Application.objects.filter(
            applied_date__date=d).count())

    popular_jobs = JobListing.objects.annotate(
        application_count=Count('applications')).order_by('-application_count')[:5]
    popular_jobs_data = []
    for job in popular_jobs:
        successful = job.applications.filter(status='successful').count()
        rate = round((successful / job.application_count) * 100, 1) \
            if job.application_count else 0
        popular_jobs_data.append({
            'title': job.title, 'company': job.company_name,
            'applications': job.application_count, 'success_rate': rate,
        })

    return Response({
        'success': True,
        'analytics': {
            'stats': {
                'total_users': total_users, 'active_jobs': total_jobs,
                'total_applications': total_applications,
                'conversion_rate': conversion_rate,
                'avg_profile_complete': round(avg_profile, 1),
                'new_users_today': CustomUser.objects.filter(
                    user_type='applicant', date_joined__date=today).count(),
                'new_applications_today': Application.objects.filter(
                    applied_date__date=today).count(),
                'active_jobs_today': JobListing.objects.filter(
                    status='published', apply_by__gte=today).count(),
            },
            'user_growth': {'labels': user_growth_labels, 'data': user_growth_data},
            'applications_overview': {
                'labels': applications_labels, 'data': applications_data},
            'status_distribution': {'labels': status_labels, 'data': status_data},
            'top_locations': {'labels': location_labels, 'data': location_data},
            'profile_completion': profile_completion,
            'activity_timeline': activity_timeline,
            'popular_jobs': popular_jobs_data,
        },
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_generate_report(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    report_type = request.data.get('type', 'users')
    try:
        if report_type == 'users':
            users = list(CustomUser.objects.filter(user_type='applicant').values(
                'username', 'email', 'date_joined', 'last_login'))
            return Response({
                'success': True, 'report_type': 'users', 'data': users,
                'summary': {
                    'total_users': len(users),
                    'active_users': CustomUser.objects.filter(
                        last_login__isnull=False).count(),
                    'new_this_month': CustomUser.objects.filter(
                        date_joined__month=timezone.now().month).count(),
                },
            })
        if report_type == 'applications':
            applications = list(Application.objects.select_related(
                'applicant', 'job_listing').values(
                'id', 'status', 'applied_date',
                'applicant__first_name', 'applicant__last_name',
                'job_listing__title', 'job_listing__company_name'))
            status_counts = list(Application.objects.values('status').annotate(
                count=Count('id')))
            return Response({
                'success': True, 'report_type': 'applications',
                'data': applications,
                'summary': {
                    'total_applications': len(applications),
                    'status_breakdown': status_counts,
                },
            })
        if report_type == 'jobs':
            jobs = list(JobListing.objects.values(
                'title', 'company_name', 'location', 'status',
                'apply_by', 'created_at'))
            return Response({
                'success': True, 'report_type': 'jobs', 'data': jobs,
                'summary': {
                    'total_jobs': len(jobs),
                    'active_jobs': JobListing.objects.filter(
                        status='published').count(),
                    'expired_jobs': JobListing.objects.filter(
                        apply_by__lt=timezone.now().date()).count(),
                },
            })
        return Response({'success': False, 'error': 'Invalid report type'},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error generating {report_type} report: {str(e)}")
        return Response({'success': False, 'error': f'Failed: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# EXPORT
# ============================================================

def export_simple_csv(export_type):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    response = HttpResponse(content_type='text/csv')
    try:
        if export_type == 'users':
            response['Content-Disposition'] = f'attachment; filename="users_{timestamp}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Username', 'Email', 'First Name',
                             'Last Name', 'Date Joined'])
            for u in CustomUser.objects.filter(user_type='applicant')[:20]:
                writer.writerow([
                    u.id, u.username, u.email, u.first_name or '',
                    u.last_name or '',
                    u.date_joined.strftime('%Y-%m-%d') if u.date_joined else '',
                ])
        elif export_type == 'applications':
            response['Content-Disposition'] = f'attachment; filename="applications_{timestamp}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Applicant', 'Job Title', 'Company',
                             'Status', 'Applied Date'])
            for app in Application.objects.select_related(
                    'applicant', 'job_listing')[:20]:
                name = f"{app.applicant.first_name} {app.applicant.last_name}".strip() \
                    or app.applicant.username
                writer.writerow([
                    app.id, name,
                    app.job_listing.title if app.job_listing else 'N/A',
                    app.job_listing.company_name if app.job_listing else 'N/A',
                    app.status,
                    app.applied_date.strftime('%Y-%m-%d') if app.applied_date else '',
                ])
        elif export_type == 'jobs':
            response['Content-Disposition'] = f'attachment; filename="jobs_{timestamp}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Title', 'Company', 'Location', 'Status'])
            for j in JobListing.objects.all()[:20]:
                writer.writerow([j.id, j.title, j.company_name, j.location, j.status])
        elif export_type == 'profiles':
            response['Content-Disposition'] = f'attachment; filename="profiles_{timestamp}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Username', 'Title', 'Completeness', 'Created'])
            for p in ApplicantProfile.objects.select_related('user')[:20]:
                writer.writerow([
                    p.id, p.user.username if p.user else 'N/A',
                    p.title or '', f"{p.profile_completeness}%",
                    p.created_at.strftime('%Y-%m-%d') if p.created_at else '',
                ])
        else:
            response['Content-Disposition'] = f'attachment; filename="export_{timestamp}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Type', 'Message'])
            writer.writerow([export_type, 'Export completed'])
    except Exception as e:
        response['Content-Disposition'] = f'attachment; filename="error_{timestamp}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Error', 'Message'])
        writer.writerow(['Export Error', str(e)])
    return response


def export_simple_json(export_type):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        if export_type == 'users':
            data = [{'id': u.id, 'username': u.username, 'email': u.email,
                     'first_name': u.first_name, 'last_name': u.last_name,
                     'date_joined': u.date_joined.isoformat() if u.date_joined else None}
                    for u in CustomUser.objects.filter(user_type='applicant')[:10]]
            filename = f"users_{timestamp}.json"
        elif export_type == 'applications':
            data = [{
                'id': str(a.id),
                'applicant_name': (f"{a.applicant.first_name} "
                                   f"{a.applicant.last_name}").strip()
                                   or a.applicant.username,
                'job_title': a.job_listing.title if a.job_listing else 'N/A',
                'company': a.job_listing.company_name if a.job_listing else 'N/A',
                'status': a.status,
                'applied_date': a.applied_date.isoformat() if a.applied_date else None,
            } for a in Application.objects.select_related(
                'applicant', 'job_listing')[:10]]
            filename = f"applications_{timestamp}.json"
        elif export_type == 'jobs':
            data = [{'id': j.id, 'title': j.title, 'company': j.company_name,
                     'location': j.location, 'status': j.status}
                    for j in JobListing.objects.all()[:10]]
            filename = f"jobs_{timestamp}.json"
        elif export_type == 'profiles':
            data = [{'id': p.id, 'username': p.user.username if p.user else 'N/A',
                     'title': p.title, 'profile_completeness': p.profile_completeness,
                     'created_at': p.created_at.isoformat() if p.created_at else None}
                    for p in ApplicantProfile.objects.select_related('user')[:10]]
            filename = f"profiles_{timestamp}.json"
        else:
            data = [{'error': 'Invalid export type', 'type': export_type}]
            filename = f"error_{timestamp}.json"

        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        response = HttpResponse(
            json.dumps({'error': f'Export failed: {str(e)}'}, indent=2),
            content_type='application/json',
        )
        response['Content-Disposition'] = f'attachment; filename="error_{timestamp}.json"'
        return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_test_export(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="test_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Test ID', 'Test Name', 'Test Date'])
    writer.writerow(['1', 'Sample User', datetime.now().strftime('%Y-%m-%d')])
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_export_simple(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        export_type = request.data.get('type', 'users')
        format_type = request.data.get('format', 'csv')
        if format_type == 'csv':
            return export_simple_csv(export_type)
        if format_type == 'json':
            return export_simple_json(export_type)
        return Response({'success': False,
                         'error': 'Only CSV and JSON formats supported'},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': f'Export failed: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# aliases
api_export_data_simple = api_export_simple
api_export_data = api_export_simple


def export_data_page(request):
    if not request.user.is_authenticated or not has_admin_access(request.user):
        return redirect('/')
    return render(request, 'hiring/export_data.html')


# ============================================================
# BUSINESS DASHBOARD
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False,
                         'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)
    today = timezone.now().date()
    active_jobs = JobListing.objects.filter(
        company_name=bp.company_name, status='published', apply_by__gte=today,
    ).count()
    business_jobs = JobListing.objects.filter(company_name=bp.company_name)
    total_applications = Application.objects.filter(
        job_listing__in=business_jobs).count()
    successful = Application.objects.filter(
        job_listing__in=business_jobs, status='successful').count()
    success_rate = round((successful / total_applications) * 100) \
        if total_applications else 0
    profile_views = BusinessProfileView.objects.filter(
        business_profile=bp).count()
    return Response({
        'success': True,
        'stats': {
            'active_jobs': active_jobs,
            'total_applications': total_applications,
            'profile_views': profile_views,
            'success_rate': f'{success_rate}%',
            'company_name': bp.company_name,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_dashboard_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False,
                         'error': 'Business profile not found.'},
                        status=status.HTTP_404_NOT_FOUND)
    business_jobs = JobListing.objects.filter(company_name=bp.company_name)
    total_jobs = business_jobs.filter(status='published').count()
    draft_jobs = business_jobs.filter(status='draft').count()
    total_applications = Application.objects.filter(
        job_listing__in=business_jobs).count()
    recent = Application.objects.filter(
        job_listing__in=business_jobs).order_by('-applied_date')[:5]
    statuses = Application.objects.filter(
        job_listing__in=business_jobs).values('status').annotate(
        count=Count('id')).order_by('status')
    return Response({
        'success': True,
        'stats': {
            'company_name': bp.company_name,
            'total_jobs': total_jobs, 'draft_jobs': draft_jobs,
            'total_applications': total_applications,
            'application_statuses': list(statuses),
        },
        'recent_applications': [{
            'id': str(a.id),
            'applicant_name': f"{a.applicant.first_name} {a.applicant.last_name}",
            'job_title': a.job_listing.title, 'status': a.status,
            'applied_date': a.applied_date,
        } for a in recent],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_jobs(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False,
                         'error': 'Business profile not found'},
                        status=status.HTTP_404_NOT_FOUND)
    jobs = JobListing.objects.filter(company_name=bp.company_name).order_by('-created_at')
    return Response({
        'success': True,
        'jobs': JobListingSerializer(jobs, many=True,
                                     context={'request': request}).data,
        'company_name': bp.company_name,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_applications(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
    except BusinessProfile.DoesNotExist:
        return Response({'success': False,
                         'error': 'Business profile not found'},
                        status=status.HTTP_404_NOT_FOUND)
    business_jobs = JobListing.objects.filter(company_name=bp.company_name)
    applications = Application.objects.filter(
        job_listing__in=business_jobs).select_related(
        'applicant', 'job_listing').order_by('-applied_date')
    data = [{
        'id': str(a.id),
        'applicant_name': f"{a.applicant.first_name} {a.applicant.last_name}",
        'applicant_email': a.applicant.user.email,
        'job_title': a.job_listing.title,
        'status': a.status, 'applied_date': a.applied_date,
        'cover_letter': a.cover_letter,
        'reference_number': f"APP-{a.id.hex[:8].upper()}",
    } for a in applications]
    return Response({'success': True, 'applications': data,
                     'company_name': bp.company_name,
                     'total_applications': len(data)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_applicant_documents(request, application_id):
    if request.user.user_type != 'admin':
        return Response({'error': 'Unauthorized'},
                        status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
        application = get_object_or_404(
            Application, id=application_id,
            job_listing__company_name=bp.company_name)
        docs = application.applicant.documents.all()
        return Response({
            'success': True,
            'applicant': {
                'id': application.applicant.id,
                'first_name': application.applicant.first_name,
                'last_name': application.applicant.last_name,
                'email': application.applicant.user.email,
            },
            'job_listing': {
                'id': application.job_listing.id,
                'title': application.job_listing.title,
                'reference': application.job_listing.listing_reference,
            },
            'documents': DocumentSerializer(docs, many=True).data,
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_business_applications_with_documents(request):
    if request.user.user_type != 'admin':
        return Response({'error': 'Unauthorized'},
                        status=status.HTTP_403_FORBIDDEN)
    try:
        bp = BusinessProfile.objects.get(user=request.user)
        applications = Application.objects.filter(
            job_listing__company_name=bp.company_name).select_related(
            'applicant', 'applicant__user', 'job_listing').order_by('-applied_date')
        data = []
        for a in applications:
            count = a.applicant.documents.count()
            data.append({
                'application_id': str(a.id),
                'applicant': {
                    'id': a.applicant.id,
                    'first_name': a.applicant.first_name,
                    'last_name': a.applicant.last_name,
                    'email': a.applicant.user.email,
                    'profile_completeness': a.applicant.profile_completeness,
                },
                'job_listing': {
                    'id': a.job_listing.id,
                    'title': a.job_listing.title,
                    'reference': a.job_listing.listing_reference,
                    'location': a.job_listing.location,
                },
                'application_status': a.status,
                'applied_date': a.applied_date,
                'document_count': count,
                'has_documents': count > 0,
            })
        return Response({
            'success': True, 'applications': data,
            'company_name': bp.company_name,
            'total_applications': len(data),
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_record_business_profile_view(request, business_id):
    try:
        bp = BusinessProfile.objects.get(id=business_id)
        ip = request.META.get('REMOTE_ADDR')
        BusinessProfileView.objects.create(
            business_profile=bp,
            viewer=request.user if request.user.is_authenticated else None,
            ip_address=ip,
        )
        return Response({'success': True})
    except BusinessProfile.DoesNotExist:
        return Response({'success': False, 'error': 'Business not found'})


# ============================================================
# ADMIN APPLICATIONS / USERS MANAGEMENT
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_applications_list(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    if request.method != 'POST':
        return Response({'error': 'POST required'}, status=405)
    data = request.data
    page = data.get('page', 1)
    page_size = data.get('page_size', 10)
    applications = Application.objects.select_related(
        'applicant', 'applicant__user', 'job_listing').all().order_by('-applied_date')
    if data.get('status') and data['status'] != 'all':
        applications = applications.filter(status=data['status'])
    if data.get('job_id') and data['job_id'] != 'all':
        applications = applications.filter(job_listing_id=data['job_id'])
    if data.get('date'):
        d = timezone.datetime.strptime(data['date'], '%Y-%m-%d').date()
        applications = applications.filter(applied_date__date=d)
    if data.get('search'):
        s = data['search']
        applications = applications.filter(
            Q(applicant__first_name__icontains=s) |
            Q(applicant__last_name__icontains=s) |
            Q(applicant__user__email__icontains=s) |
            Q(job_listing__title__icontains=s) |
            Q(job_listing__company_name__icontains=s))
    total = applications.count()
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    paginated = applications[start:start + page_size]
    data_out = [{
        'id': str(a.id),
        'applicant_name': f"{a.applicant.first_name} {a.applicant.last_name}",
        'applicant_email': a.applicant.user.email,
        'applicant_phone': a.applicant.user.mobile_phone,
        'job_title': a.job_listing.title,
        'company_name': a.job_listing.company_name,
        'job_location': a.job_listing.location,
        'job_reference': a.job_listing.listing_reference,
        'status': a.status, 'applied_date': a.applied_date,
        'cover_letter': a.cover_letter, 'notes': a.notes,
        'reference_number': f"APP-{a.id.hex[:8].upper()}",
    } for a in paginated]
    return Response({
        'success': True,
        'applications': data_out,
        'total_pages': total_pages,
        'current_page': page,
        'total_applications': total,
        'stats': {
            'total': Application.objects.count(),
            'submitted': Application.objects.filter(status='submitted').count(),
            'under_review': Application.objects.filter(status='under_review').count(),
            'shortlisted': Application.objects.filter(status='shortlisted').count(),
            'interview': Application.objects.filter(status='interview').count(),
            'successful': Application.objects.filter(status='successful').count(),
            'unsuccessful': Application.objects.filter(status='unsuccessful').count(),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_application_detail(request, application_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        a = Application.objects.select_related(
            'applicant', 'applicant__user', 'job_listing').get(id=application_id)
        profile = a.applicant
        return Response({
            'success': True,
            'application': {
                'id': str(a.id),
                'applicant_name': f"{profile.first_name} {profile.last_name}",
                'applicant_email': profile.user.email,
                'applicant_phone': profile.user.mobile_phone,
                'applicant_title': profile.title,
                'applicant_gender': profile.gender,
                'applicant_ethnicity': profile.ethnicity,
                'applicant_location': profile.current_home_location,
                'job_title': a.job_listing.title,
                'company_name': a.job_listing.company_name,
                'job_location': a.job_listing.location,
                'job_reference': a.job_listing.listing_reference,
                'status': a.status, 'applied_date': a.applied_date,
                'cover_letter': a.cover_letter, 'notes': a.notes,
                'reference_number': f"APP-{a.id.hex[:8].upper()}",
                'profile_completeness': profile.profile_completeness,
            },
        })
    except Application.DoesNotExist:
        return Response({'success': False, 'error': 'Application not found'},
                        status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_update_application_status(request, application_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        return Response({'success': False, 'error': 'Application not found'},
                        status=status.HTTP_404_NOT_FOUND)
    serializer = AdminApplicationStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)
    new_status = serializer.validated_data['status']
    notes = request.data.get('notes', '')
    old_status = application.status
    application.status = new_status
    if notes:
        header = f"--- Status Update {timezone.now().strftime('%Y-%m-%d %H:%M')} ---\n"
        application.notes = (application.notes + "\n\n" + header + notes) \
            if application.notes else (header + notes)
    application.save()
    try:
        Alert.objects.create(
            applicant=application.applicant,
            title="Application Status Updated",
            message=f"Your application for {application.job_listing.title} "
                    f"is now {new_status.replace('_', ' ').title()}.",
        )
        SentNotification.objects.create(
            applicant=application.applicant,
            notification_type='application_status_update',
            subject="Application Status Update",
            message=f"Your application status for {application.job_listing.title} "
                    f"is now {new_status.replace('_', ' ').title()}.",
            sent_via='in_app',
        )
    except Exception as e:
        logger.error(f"Notification failed: {str(e)}")
    return Response({
        'success': True,
        'message': f'Application status updated to {new_status}',
        'application': {
            'id': application.id,
            'applicant_name': f"{application.applicant.first_name} "
                              f"{application.applicant.last_name}",
            'job_title': application.job_listing.title,
            'status': application.status,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_jobs_simple_list(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    jobs = JobListing.objects.all().values('id', 'title', 'company_name').order_by('title')
    return Response({'success': True, 'jobs': list(jobs)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_application_stats(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    status_breakdown = list(Application.objects.values('status').annotate(
        count=Count('id')).order_by('status'))
    recent = Application.objects.select_related(
        'applicant', 'job_listing').order_by('-applied_date')[:10]
    return Response({
        'success': True,
        'stats': {
            'total': Application.objects.count(),
            'today': Application.objects.filter(applied_date__date=today).count(),
            'this_week': Application.objects.filter(
                applied_date__date__gte=week_ago).count(),
            'this_month': Application.objects.filter(
                applied_date__date__gte=month_ago).count(),
            'status_breakdown': status_breakdown,
            'recent_applications': [{
                'id': str(a.id),
                'applicant_name': f"{a.applicant.first_name} {a.applicant.last_name}",
                'job_title': a.job_listing.title, 'status': a.status,
                'applied_date': a.applied_date,
                'company_name': a.job_listing.company_name,
            } for a in recent],
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_users_list(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    data = request.data
    page = data.get('page', 1)
    page_size = data.get('page_size', 10)
    users = CustomUser.objects.all().order_by('-date_joined')
    if data.get('user_type') and data['user_type'] != 'all':
        users = users.filter(user_type=data['user_type'])
    if data.get('search'):
        s = data['search']
        users = users.filter(
            Q(username__icontains=s) | Q(email__icontains=s) |
            Q(first_name__icontains=s) | Q(last_name__icontains=s))
    if data.get('date'):
        d = timezone.datetime.strptime(data['date'], '%Y-%m-%d').date()
        users = users.filter(date_joined__date=d)
    total = users.count()
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    paginated = users[start:start + page_size]
    data_out = []
    for u in paginated:
        info = {
            'id': u.id, 'username': u.username, 'email': u.email,
            'first_name': u.first_name, 'last_name': u.last_name,
            'full_name': u.get_full_name(), 'user_type': u.user_type,
            'mobile_phone': u.mobile_phone,
            'date_joined': u.date_joined, 'last_login': u.last_login,
            'has_profile': hasattr(u, 'applicantprofile'),
        }
        if hasattr(u, 'applicantprofile'):
            p = u.applicantprofile
            info.update({
                'profile_completeness': p.profile_completeness,
                'profile_title': p.title,
                'preferred_job_title': p.preferred_job_title,
                'location': p.current_home_location,
                'applications_count': p.applications.count(),
                'skills_count': p.skills.count(),
                'documents_count': p.documents.count(),
            })
        data_out.append(info)
    today = timezone.now().date()
    return Response({
        'success': True,
        'users': data_out,
        'total_pages': total_pages,
        'current_page': page,
        'total_users': total,
        'stats': {
            'total': CustomUser.objects.count(),
            'applicants': CustomUser.objects.filter(user_type='applicant').count(),
            'admins': CustomUser.objects.filter(user_type='admin').count(),
            'active_today': CustomUser.objects.filter(
                last_login__date=today).count(),
            'new_today': CustomUser.objects.filter(
                date_joined__date=today).count(),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_user_detail(request, user_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        u = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return Response({'success': False, 'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND)
    info = {
        'id': u.id, 'username': u.username, 'email': u.email,
        'first_name': u.first_name, 'last_name': u.last_name,
        'full_name': u.get_full_name(), 'user_type': u.user_type,
        'mobile_phone': u.mobile_phone, 'date_joined': u.date_joined,
        'last_login': u.last_login, 'is_active': u.is_active,
        'is_staff': u.is_staff, 'is_superuser': u.is_superuser,
        'has_profile': hasattr(u, 'applicantprofile'),
    }
    if hasattr(u, 'applicantprofile'):
        p = u.applicantprofile
        info.update({
            'profile_completeness': p.profile_completeness,
            'profile_title': p.title, 'profile_gender': p.gender,
            'profile_ethnicity': p.ethnicity,
            'preferred_job_title': p.preferred_job_title,
            'location': p.current_home_location,
            'has_drivers_license': p.has_drivers_license,
            'has_own_transport': p.has_own_transport,
            'willing_to_relocate': p.willing_to_relocate,
            'availability': p.availability,
            'current_salary': p.current_salary,
            'desired_salary': p.desired_salary,
            'introduction': p.introduction,
            'applications_count': p.applications.count(),
            'skills_count': p.skills.count(),
            'employment_count': p.employment_history.count(),
            'education_count': p.education.count(),
            'documents_count': p.documents.count(),
        })
    return Response({'success': True, 'user': info})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_update_user(request, user_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    try:
        u = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return Response({'success': False, 'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND)
    data = request.data
    for field in ['username', 'email', 'first_name', 'last_name',
                  'user_type', 'mobile_phone']:
        if field in data:
            setattr(u, field, data[field])
    u.save()
    return Response({'success': True, 'message': 'User updated successfully'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_admin_delete_user(request, user_id):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    if request.user.id == user_id:
        return Response({'success': False,
                         'error': 'Cannot delete your own account'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        u = CustomUser.objects.get(id=user_id)
        u.delete()
        return Response({'success': True, 'message': 'User deleted successfully'})
    except CustomUser.DoesNotExist:
        return Response({'success': False, 'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def api_admin_quick_action(request):
    if not has_admin_access(request.user):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    action = request.data.get('action')
    if action == 'create_job':
        return Response({'success': True, 'message': 'Redirecting to job creation',
                         'redirect_url': '/admin-portal/jobs/'})
    if action == 'send_notification':
        return Response({'success': True, 'message': 'Bulk notification sent'})
    if action == 'export_data':
        return api_export_simple(request)
    if action == 'system_check':
        return api_system_health(request)
    if action == 'view_stats':
        return api_database_stats(request)
    return Response({'success': False, 'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# POSTS / FEED / COMMENTS / LIKES
# ============================================================

ALLOWED_POST_TYPES = ['all', 'general', 'job', 'update', 'news',
                      'question', 'achievement', 'advice']
ALLOWED_SORT_OPTIONS = ['newest', 'popular', 'top']


def error_response(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'error': message}, status=status_code)


def success_response(message, data=None, status_code=status.HTTP_200_OK):
    payload = {'success': True, 'message': message}
    if data:
        payload.update(data)
    return Response(payload, status=status_code)


def can_user_view_post(post, user):
    if not user.is_authenticated:
        return post.visibility == 'public'
    if post.visibility == 'public':
        return True
    if post.visibility == 'private':
        return user == post.author
    if post.visibility == 'company':
        return user == post.author or (
            user.user_type == 'admin'
            and post.company and post.company.user == user)
    if post.visibility == 'connections':
        return user == post.author
    return False


def get_paginated_data(queryset, page, page_size, serializer_class, context=None):
    total = queryset.count()
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    items = queryset[start:start + page_size]
    serializer = serializer_class(items, many=True, context=context)
    return {
        'data': serializer.data,
        'pagination': {
            'current_page': page, 'total_pages': total_pages,
            'total_items': total, 'page_size': page_size,
        },
    }


def get_user_visibility_filters(user):
    if not user.is_authenticated:
        return Q(visibility='public', is_published=True)
    filters = Q(is_published=True) & (
        Q(visibility='public') |
        Q(author=user) |
        Q(visibility='private', author=user) |
        Q(visibility='connections', author=user))
    if getattr(user, 'user_type', None) == 'admin':
        filters |= Q(visibility='company')
    return filters


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def api_posts(request):
    if request.method == 'GET':
        try:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            post_type = request.GET.get('type', 'all')
            show_all = request.GET.get('show_all', 'false').lower() == 'true'
            if show_all:
                posts = Post.objects.filter(
                    Q(is_published=True) | Q(author=request.user)).distinct()
            else:
                posts = Post.objects.filter(author=request.user)
            if post_type != 'all':
                posts = posts.filter(post_type=post_type)
            total = posts.count()
            total_pages = (total + page_size - 1) // page_size
            start = (page - 1) * page_size
            paginated = posts.order_by('-created_at')[start:start + page_size]
            return Response({
                'success': True,
                'posts': PostSerializer(paginated, many=True,
                                        context={'request': request}).data,
                'pagination': {
                    'current_page': page, 'total_pages': total_pages,
                    'total_posts': total, 'page_size': page_size,
                },
                'show_all': show_all,
            })
        except Exception as e:
            logger.error(f"Error loading posts: {str(e)}")
            return error_response('Failed to load posts',
                                  status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST
    try:
        post_data = request.data.copy()
        if 'title' not in post_data or not post_data.get('title'):
            content = post_data.get('content', '')
            if content:
                words = content.strip().split()[:5]
                post_data['title'] = ' '.join(words) + '...'
            else:
                return error_response('Title is required.')
        post_data.setdefault('post_type', 'general')
        post_data.setdefault('visibility', 'public')
        post_data.setdefault('is_published', True)

        serializer = PostCreateSerializer(data=post_data,
                                          context={'request': request})
        if serializer.is_valid():
            post = serializer.save(author=request.user)
            if post.is_published:
                try:
                    if hasattr(request.user, 'business_profile'):
                        BusinessAlert.objects.create(
                            business=request.user.business_profile,
                            title="New Post Published",
                            message=f"Your post '{post.title}' is published.",
                            alert_type='custom',
                        )
                    elif hasattr(request.user, 'applicantprofile'):
                        Alert.objects.create(
                            applicant=request.user.applicantprofile,
                            title="New Post Published",
                            message=f"Your post '{post.title}' is published.",
                        )
                except Exception as e:
                    logger.warning(f"Notification error: {e}")
            request.user.last_login = timezone.now()
            request.user.save(update_fields=['last_login'])
            return Response({
                'success': True,
                'message': 'Post created successfully!',
                'post': PostSerializer(post, context={'request': request}).data,
                'user_info': {
                    'username': request.user.username,
                    'user_type': request.user.user_type,
                    'is_superuser': request.user.is_superuser,
                },
            }, status=status.HTTP_201_CREATED)
        error_list = []
        for field, errors in serializer.errors.items():
            if isinstance(errors, list):
                error_list += [f"{field}: {e}" for e in errors]
            else:
                error_list.append(f"{field}: {errors}")
        return Response({
            'success': False,
            'message': 'Please fix the errors below',
            'errors': serializer.errors,
            'error_list': error_list,
            'required_fields': ['title', 'content'],
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"Error creating post: {str(e)}")
        return error_response(f'Failed to create post: {str(e)}',
                              status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_home_feed(request):
    try:
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        return error_response('Invalid page or page_size parameter')
    post_type = request.GET.get('type', 'all')
    sort_by = request.GET.get('sort', 'newest')
    search = request.GET.get('search', '').strip()
    if post_type not in ALLOWED_POST_TYPES:
        return error_response(f'Invalid post type. Use {", ".join(ALLOWED_POST_TYPES)}')
    if sort_by not in ALLOWED_SORT_OPTIONS:
        return error_response(f'Invalid sort option. Use {", ".join(ALLOWED_SORT_OPTIONS)}')

    posts = Post.objects.filter(is_published=True, visibility='public')
    if post_type != 'all':
        posts = posts.filter(post_type=post_type)
    if search:
        posts = posts.filter(
            Q(title__icontains=search) | Q(content__icontains=search) |
            Q(tags__icontains=search) | Q(author__username__icontains=search))

    if sort_by == 'popular':
        posts = posts.annotate(
            popularity_score=Count('likes') + Count('comments') * 2 +
                             F('views') * 0.1 + F('shares') * 3,
        ).order_by('-popularity_score', '-created_at')
    elif sort_by == 'top':
        posts = posts.filter(rating_count__gte=3).order_by(
            '-average_rating', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    total = posts.count()
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    paginated = posts[start:start + page_size]
    serialized = PostSerializer(paginated, many=True,
                                context={'request': request}).data

    if request.user.is_authenticated:
        liked_ids = set(request.user.liked_posts.values_list('id', flat=True))
        for p in serialized:
            p['user_has_liked'] = p['id'] in liked_ids

    return Response({
        'success': True,
        'posts': serialized,
        'pagination': {
            'current_page': page, 'total_pages': total_pages,
            'total_posts': total, 'page_size': page_size,
        },
        'filters': {
            'current_type': post_type, 'current_sort': sort_by,
            'search_query': search or None,
            'allowed_types': ALLOWED_POST_TYPES,
            'allowed_sort_options': ALLOWED_SORT_OPTIONS,
        },
        'user_info': {
            'is_authenticated': request.user.is_authenticated,
            'username': request.user.username if request.user.is_authenticated else None,
            'user_type': getattr(request.user, 'user_type', None)
                if request.user.is_authenticated else None,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_feed_posts(request):
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        posts = Post.objects.filter(
            is_published=True, visibility='public').order_by('-created_at')
        total = posts.count()
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        paginated = posts[start:start + page_size]
        serialized = PostSerializer(paginated, many=True,
                                    context={'request': request}).data
        liked_ids = set(request.user.liked_posts.values_list('id', flat=True))
        for p in serialized:
            p['user_has_liked'] = p['id'] in liked_ids
        return Response({
            'success': True,
            'posts': serialized,
            'pagination': {
                'current_page': page, 'total_pages': total_pages,
                'total_posts': total, 'page_size': page_size,
            },
        })
    except Exception as e:
        logger.error(f"Error loading feed posts: {str(e)}")
        return error_response('Failed to load feed',
                              status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def api_post_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if not can_user_view_post(post, request.user):
        return error_response('No permission', status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        if request.user != post.author:
            post.views += 1
            post.save(update_fields=['views'])
        comments = Comment.objects.filter(
            post=post, parent_comment__isnull=True).order_by('-created_at')
        return Response({
            'success': True,
            'post': PostSerializer(post, context={'request': request}).data,
            'comments': CommentSerializer(comments, many=True,
                                          context={'request': request}).data,
            'can_edit': request.user == post.author or request.user.is_staff,
            'can_delete': request.user == post.author or request.user.is_staff,
        })

    if request.method == 'PUT':
        if request.user != post.author and not request.user.is_staff:
            return error_response('No permission', status.HTTP_403_FORBIDDEN)
        serializer = PostUpdateSerializer(post, data=request.data, partial=True,
                                          context={'request': request})
        if serializer.is_valid():
            updated = serializer.save()
            return Response({
                'success': True,
                'message': 'Post updated successfully!',
                'post': PostSerializer(updated, context={'request': request}).data,
            })
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    if request.user != post.author and not request.user.is_staff:
        return error_response('No permission', status.HTTP_403_FORBIDDEN)
    title = post.title
    post.delete()
    return Response({'success': True, 'message': f'Post "{title}" deleted'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_post_like_dislike(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if not can_user_view_post(post, request.user):
        return error_response('No permission', status.HTTP_403_FORBIDDEN)
    serializer = LikeDislikeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)
    action = serializer.validated_data['action']
    if action == 'like':
        post.dislikes.remove(request.user)
        post.likes.add(request.user)
        msg = 'Post liked'
    elif action == 'dislike':
        post.likes.remove(request.user)
        post.dislikes.add(request.user)
        msg = 'Post disliked'
    else:
        post.likes.remove(request.user)
        post.dislikes.remove(request.user)
        msg = 'Reaction removed'
    return Response({
        'success': True, 'message': msg,
        'likes_count': post.likes.count(),
        'dislikes_count': post.dislikes.count(),
        'user_has_liked': post.likes.filter(id=request.user.id).exists(),
        'user_has_disliked': post.dislikes.filter(id=request.user.id).exists(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if not can_user_view_post(post, request.user):
        return error_response('No permission', status.HTTP_403_FORBIDDEN)
    post.shares += 1
    post.save(update_fields=['shares'])
    return Response({'success': True, 'message': 'Post shared',
                     'shares_count': post.shares})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_post_rating(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if not can_user_view_post(post, request.user):
        return error_response('No permission', status.HTTP_403_FORBIDDEN)
    serializer = RatingSerializer(data=request.data,
                                  context={'request': request, 'post': post})
    if serializer.is_valid():
        rating = serializer.save()
        post.average_rating = post.ratings.aggregate(
            a=Avg('rating'))['a'] or 0
        post.rating_count = post.ratings.count()
        post.save(update_fields=['average_rating', 'rating_count'])
        return Response({
            'success': True, 'message': 'Rating submitted',
            'average_rating': post.average_rating,
            'rating_count': post.rating_count,
            'user_rating': rating.rating,
        })
    return Response({'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_post_comments(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if not can_user_view_post(post, request.user):
        return error_response('No permission', status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        comments = Comment.objects.filter(
            post=post, parent_comment__isnull=True)
        total = comments.count()
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size
        paginated = comments.order_by('-created_at')[start:start + page_size]
        return Response({
            'success': True, 'message': 'Comments loaded',
            'comments': CommentSerializer(paginated, many=True,
                                          context={'request': request}).data,
            'total_comments': total,
            'pagination': {
                'current_page': page, 'total_pages': total_pages,
                'page_size': page_size,
            },
            'post_id': post_id, 'post_title': post.title,
        })

    content = request.data.get('content', '').strip()
    if not content:
        return error_response('Comment cannot be empty')
    parent_id = request.data.get('parent_comment_id')
    parent = None
    if parent_id:
        try:
            parent = Comment.objects.get(id=parent_id, post=post)
        except Comment.DoesNotExist:
            return error_response('Parent comment not found',
                                  status.HTTP_404_NOT_FOUND)
    comment = Comment.objects.create(
        post=post, author=request.user, content=content, parent_comment=parent,
    )
    post.comment_count = Comment.objects.filter(post=post).count()
    post.save(update_fields=['comment_count'])

    if post.author != request.user:
        try:
            if hasattr(post.author, 'applicantprofile'):
                Alert.objects.create(
                    applicant=post.author.applicantprofile,
                    title="New Comment",
                    message=f"{request.user.username} commented on your post: "
                            f"'{post.title[:50]}...'")
            elif hasattr(post.author, 'business_profile'):
                BusinessAlert.objects.create(
                    business=post.author.business_profile,
                    title="New Comment",
                    message=f"{request.user.username} commented on your post: "
                            f"'{post.title[:50]}...'",
                    alert_type='custom')
        except Exception as e:
            logger.warning(f"Notification error: {e}")
    if parent and parent.author != request.user:
        try:
            if hasattr(parent.author, 'applicantprofile'):
                Alert.objects.create(
                    applicant=parent.author.applicantprofile,
                    title="Reply to Your Comment",
                    message=f"{request.user.username} replied on post: "
                            f"'{post.title[:50]}...'")
            elif hasattr(parent.author, 'business_profile'):
                BusinessAlert.objects.create(
                    business=parent.author.business_profile,
                    title="Reply to Your Comment",
                    message=f"{request.user.username} replied on post: "
                            f"'{post.title[:50]}...'",
                    alert_type='custom')
        except Exception as e:
            logger.warning(f"Notification error: {e}")

    return Response({
        'success': True,
        'message': 'Comment added successfully',
        'comment': CommentSerializer(comment, context={'request': request}).data,
        'comment_count': post.comment_count,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_job_like_dislike(request, job_id):
    job = get_object_or_404(JobListing, id=job_id)
    action = request.data.get('action', 'like').lower()
    if action == 'like':
        JobInteraction.objects.filter(
            user=request.user, job_listing=job, interaction_type='dislike').delete()
        JobInteraction.objects.get_or_create(
            user=request.user, job_listing=job, interaction_type='like')
        msg = 'Job liked'
    elif action == 'dislike':
        JobInteraction.objects.filter(
            user=request.user, job_listing=job, interaction_type='like').delete()
        JobInteraction.objects.get_or_create(
            user=request.user, job_listing=job, interaction_type='dislike')
        msg = 'Job disliked'
    else:
        JobInteraction.objects.filter(
            user=request.user, job_listing=job,
            interaction_type__in=['like', 'dislike']).delete()
        msg = 'Reaction removed'
    return Response({
        'success': True, 'message': msg,
        'likes_count': JobInteraction.objects.filter(
            job_listing=job, interaction_type='like').count(),
        'dislikes_count': JobInteraction.objects.filter(
            job_listing=job, interaction_type='dislike').count(),
        'user_has_liked': JobInteraction.objects.filter(
            user=request.user, job_listing=job, interaction_type='like').exists(),
        'user_has_disliked': JobInteraction.objects.filter(
            user=request.user, job_listing=job, interaction_type='dislike').exists(),
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_job_comments(request, job_id):
    job = get_object_or_404(JobListing, id=job_id)
    if request.method == 'GET':
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(50, max(1, int(request.GET.get('page_size', 20))))
        comments = Comment.objects.filter(
            job_listing=job, parent_comment__isnull=True).order_by('-created_at')
        data = get_paginated_data(comments, page, page_size, CommentSerializer,
                                  context={'request': request})
        return Response({
            'success': True, 'message': 'Comments loaded',
            'comments': data['data'],
            'pagination': data['pagination'],
            'total_comments': Comment.objects.filter(job_listing=job).count(),
            'job_id': job_id, 'job_title': job.title,
        })

    content = request.data.get('content', '').strip()
    if not content:
        return error_response('Comment cannot be empty')
    parent_id = request.data.get('parent_comment_id')
    parent = None
    if parent_id:
        try:
            parent = Comment.objects.get(id=parent_id, job_listing=job)
        except Comment.DoesNotExist:
            return error_response('Parent comment not found',
                                  status.HTTP_404_NOT_FOUND)
    comment = Comment.objects.create(
        job_listing=job, author=request.user, content=content,
        parent_comment=parent)
    return Response({
        'success': True, 'message': 'Comment added successfully',
        'comment': CommentSerializer(comment, context={'request': request}).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_post_stats(request):
    total_posts = Post.objects.filter(is_published=True).count()
    total_comments = Comment.objects.count()
    post_types = list(Post.objects.filter(is_published=True).values(
        'post_type').annotate(count=Count('id')).order_by('-count'))
    recent = Post.objects.filter(is_published=True).order_by('-created_at')[:5]
    most_liked = Post.objects.filter(is_published=True).annotate(
        likes_count=Count('likes')).order_by('-likes_count')[:5]
    return Response({
        'success': True,
        'stats': {
            'total_posts': total_posts,
            'total_comments': total_comments,
            'post_type_distribution': post_types,
            'recent_posts': PostSerializer(recent, many=True,
                                           context={'request': request}).data,
            'most_liked_posts': [{
                'id': p.id, 'title': p.title,
                'author': p.author.username,
                'likes_count': p.likes.count(),
                'post_type': p.post_type,
            } for p in most_liked],
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_user_post_stats(request):
    user_posts = Post.objects.filter(author=request.user)
    total_likes = 0
    total_comments = 0
    total_views = 0
    for p in user_posts:
        total_likes += p.likes.count()
        total_comments += p.comments.count()
        total_views += p.views
    most_popular = user_posts.annotate(
        engagement=Count('likes') + Count('comments') + F('shares'),
    ).order_by('-engagement').first()
    return Response({
        'success': True,
        'stats': {
            'total_posts': user_posts.count(),
            'published_posts': user_posts.filter(is_published=True).count(),
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_views': total_views,
            'recent_posts': PostSerializer(
                user_posts.order_by('-created_at')[:5], many=True,
                context={'request': request}).data,
            'most_popular_post': {
                'id': most_popular.id, 'title': most_popular.title,
                'views': most_popular.views,
            } if most_popular else None,
        },
    })


# ============================================================
# BLOG / CAREERS / FAQ / CONTACT / STATIC PAGES
# ============================================================

def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True).order_by('-created_at')
    paginator = Paginator(posts, 10)
    page = request.GET.get('page')
    try:
        posts_page = paginator.page(page)
    except PageNotAnInteger:
        posts_page = paginator.page(1)
    except EmptyPage:
        posts_page = paginator.page(paginator.num_pages)
    return render(request, 'hiring/blog_list.html', {
        'page_title': 'Blog',
        'page_description': 'Read the latest property tips and news',
        'active_page': 'blog',
        'posts': posts_page,
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
        'total_posts': posts.count(),
    })


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    related = BlogPost.objects.filter(is_published=True).exclude(id=post.id)[:3]
    return render(request, 'hiring/blog_detail.html', {
        'page_title': post.title,
        'page_description': post.meta_description or post.excerpt[:160],
        'active_page': 'blog',
        'post': post, 'related_posts': related,
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
        'can_delete': request.user.is_superuser,
    })


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def blog_create_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        excerpt = data.get('excerpt', '')[:300]
        if not title or not content:
            return JsonResponse({'success': False,
                                 'error': 'Title and content are required'})
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
        if BlogPost.objects.filter(slug=slug).exists():
            slug = f"{slug}-{BlogPost.objects.count() + 1}"
        post = BlogPost.objects.create(
            title=title, slug=slug, content=content, excerpt=excerpt,
            author=request.user.username, is_published=True,
            publish_date=timezone.now())
        return JsonResponse({
            'success': True, 'message': 'Blog post created successfully!',
            'post_id': post.id, 'slug': post.slug,
            'redirect_url': f'/blog/{post.slug}/',
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def blog_update_api(request, post_id):
    if request.method != 'PUT':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        post = get_object_or_404(BlogPost, id=post_id)
        data = json.loads(request.body)
        if data.get('title'):
            post.title = data['title'].strip()
        if data.get('content'):
            post.content = data['content'].strip()
        if 'excerpt' in data:
            post.excerpt = data['excerpt'][:300]
        if 'is_published' in data:
            post.is_published = data['is_published']
        post.save()
        return JsonResponse({'success': True, 'message': 'Blog post updated!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def blog_delete_api(request, post_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        post = get_object_or_404(BlogPost, id=post_id)
        post.delete()
        return JsonResponse({'success': True, 'message': 'Blog post deleted!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def career_list(request):
    jobs = Career.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'hiring/careers.html', {
        'page_title': 'Careers',
        'page_description': 'Join the OppoGlobe team',
        'active_page': 'careers',
        'jobs': jobs,
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
        'total_jobs': jobs.count(),
        'benefits': [
            'Competitive salary package', 'Health insurance',
            'Flexible working hours', 'Annual learning budget',
            'Team retreats', 'Performance bonuses',
        ],
    })


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def career_create_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        location = data.get('location', '').strip()
        description = data.get('description', '').strip()
        if not title or not location or not description:
            return JsonResponse({'success': False,
                                 'error': 'Title, location, description required'})
        career = Career.objects.create(
            title=title, location=location,
            employment_type=data.get('employment_type', 'full_time'),
            description=description,
            requirements=data.get('requirements', ''), is_active=True)
        return JsonResponse({'success': True,
                             'message': 'Career created successfully!',
                             'career_id': career.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def career_update_api(request, career_id):
    if request.method != 'PUT':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        career = get_object_or_404(Career, id=career_id)
        data = json.loads(request.body)
        for f in ['title', 'location', 'description', 'requirements']:
            if f in data:
                setattr(career, f, data[f].strip())
        if 'employment_type' in data:
            career.employment_type = data['employment_type']
        if 'is_active' in data:
            career.is_active = data['is_active']
        career.save()
        return JsonResponse({'success': True, 'message': 'Career updated!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def career_delete_api(request, career_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        get_object_or_404(Career, id=career_id).delete()
        return JsonResponse({'success': True, 'message': 'Career deleted!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def faq_list(request):
    faqs = FAQ.objects.filter(is_published=True).order_by('category', 'order')
    categories = {}
    for faq in faqs:
        categories.setdefault(faq.category or 'General', []).append(faq)
    return render(request, 'hiring/faq.html', {
        'page_title': 'FAQ',
        'page_description': 'Find answers to common questions',
        'active_page': 'faq',
        'categories': categories,
        'faq_count': faqs.count(),
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def faq_create_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        data = json.loads(request.body)
        q = data.get('question', '').strip()
        a = data.get('answer', '').strip()
        if not q or not a:
            return JsonResponse({'success': False,
                                 'error': 'Question and answer required'})
        category = data.get('category', 'General').strip()
        max_order = FAQ.objects.filter(category=category).aggregate(
            m=Max('order'))['m'] or 0
        faq = FAQ.objects.create(
            question=q, answer=a, category=category,
            order=max_order + 1, is_published=True)
        return JsonResponse({'success': True,
                             'message': 'FAQ created!', 'faq_id': faq.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def faq_update_api(request, faq_id):
    if request.method != 'PUT':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        faq = get_object_or_404(FAQ, id=faq_id)
        data = json.loads(request.body)
        for f in ['question', 'answer', 'category']:
            if f in data:
                setattr(faq, f, data[f].strip())
        if 'order' in data:
            faq.order = int(data['order'])
        if 'is_published' in data:
            faq.is_published = data['is_published']
        faq.save()
        return JsonResponse({'success': True, 'message': 'FAQ updated!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def faq_delete_api(request, faq_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        get_object_or_404(FAQ, id=faq_id).delete()
        return JsonResponse({'success': True, 'message': 'FAQ deleted!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject', 'General')
        message = request.POST.get('message')
        if name and email and message:
            ContactMessage.objects.create(
                name=name, email=email, subject=subject, message=message)
            return render(request, 'hiring/contact.html', {
                'success': True,
                'page_title': 'Contact Us',
                'active_page': 'contact',
                'is_superuser': request.user.is_superuser,
                'contact_info': {
                    'address': '123 Property Street, Sandton, Johannesburg, 2196',
                    'phone': '+27 10 123 4567',
                    'email': 'support@oppoglobe.com',
                    'hours': 'Mon - Fri: 8:00 AM - 5:00 PM SAST',
                },
            })
    return render(request, 'hiring/contact.html', {
        'page_title': 'Contact Us',
        'page_description': 'Get in touch with the OppoGlobe team',
        'active_page': 'contact',
        'is_superuser': request.user.is_superuser,
        'contact_info': {
            'address': '123 Property Street, Sandton, Johannesburg, 2196',
            'phone': '+27 10 123 4567',
            'email': 'support@oppoglobe.com',
            'hours': 'Mon - Fri: 8:00 AM - 5:00 PM SAST',
        },
    })


@login_required
@user_passes_test(is_superuser)
def contact_messages_view(request):
    messages_list = ContactMessage.objects.all().order_by('-created_at')
    return render(request, 'hiring/contact_messages.html', {
        'page_title': 'Contact Messages',
        'active_page': 'contact',
        'messages': messages_list,
        'is_superuser': request.user.is_superuser,
    })


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def contact_message_mark_read_api(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    msg = get_object_or_404(ContactMessage, id=message_id)
    msg.is_read = True
    msg.save()
    return JsonResponse({'success': True, 'message': 'Marked as read'})


def about_view(request):
    return render(request, 'hiring/about.html', {
        'page_title': 'About OppoGlobe',
        'page_description': 'Learn about OppoGlobe',
        'active_page': 'about',
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


def privacy_view(request):
    return render(request, 'hiring/privacy.html', {
        'page_title': 'Privacy Policy',
        'page_description': 'Learn how OppoGlobe protects your privacy',
        'active_page': 'privacy',
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


def cookies_view(request):
    return render(request, 'hiring/cookies.html', {
        'page_title': 'Cookies Policy',
        'page_description': 'Learn how OppoGlobe uses cookies',
        'active_page': 'cookies',
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


def terms_view(request):
    return render(request, 'hiring/terms.html', {
        'page_title': 'Terms of Service',
        'page_description': 'Read the terms and conditions',
        'active_page': 'terms',
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


def help_view(request):
    return render(request, 'hiring/help.html', {
        'page_title': 'Help Center',
        'page_description': 'Find answers to common questions',
        'active_page': 'help',
        'is_superuser': request.user.is_superuser,
        'can_edit': request.user.is_superuser,
    })


def help_center(request):
    page = HelpCenterPage.objects.order_by('pk').first()
    return render(request, 'hiring/help_center.html', {
        'page': page,
        'page_title': page.title if page else 'Help Center',
        'page_description': (
            page.description if page else
            'Explore OppoGlobe help guides, troubleshooting and contact options.'),
    })


@csrf_exempt
def subscribe_newsletter(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'},
                            status=405)
    try:
        data = json.loads(request.body)
        email = data.get('email')
        if not email:
            return JsonResponse({'success': False, 'error': 'Email required'},
                                status=400)
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return JsonResponse({'success': False, 'error': 'Invalid email'},
                                status=400)
        sub, created = NewsletterSubscriber.objects.get_or_create(email=email)
        return JsonResponse({
            'success': True, 'message': 'Subscribed successfully!',
            'created': created,
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'},
                            status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================
# PWA / PUSH
# ============================================================

@cache_control(max_age=3600, public=True)
def pwa_manifest(request):
    manifest = {
        "id": "/?source=pwa",
        "name": "OppoGlobe - Find Your Dream Property",
        "short_name": "OppoGlobe",
        "description": "Hiring + Property platform",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone"],
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": "#c62828",
        "lang": "en", "dir": "ltr",
        "categories": ["jobs", "property"],
        "prefer_related_applications": False,
        "icons": [
            {"src": f"/static/hiring/icons/icon-{s}.png", "sizes": f"{s}x{s}",
             "type": "image/png", "purpose": "any"}
            for s in [72, 96, 128, 144, 152, 192, 384, 512]
        ] + [
            {"src": f"/static/hiring/icons/icon-{s}-maskable.png",
             "sizes": f"{s}x{s}", "type": "image/png", "purpose": "maskable"}
            for s in [72, 96, 128, 144, 152, 192, 384, 512]
        ],
        "shortcuts": [
            {"name": "Jobs", "short_name": "Jobs",
             "description": "Browse job listings",
             "url": "/?tab=jobs",
             "icons": [{"src": "/static/hiring/icons/shortcut-jobs.png",
                        "sizes": "96x96", "type": "image/png"}]},
            {"name": "Alerts", "short_name": "Alerts",
             "description": "View notifications",
             "url": "/alerts/",
             "icons": [{"src": "/static/hiring/icons/shortcut-jobs.png",
                        "sizes": "96x96", "type": "image/png"}]},
        ],
    }
    response = JsonResponse(manifest, content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=3600'
    response['Access-Control-Allow-Origin'] = '*'
    return response


def pwa_sw(request):
    """Serve the service worker (root-capable) with push handlers."""
    push_logic = r"""

// ===== OppoGlobe push =====
self.addEventListener('push', function(event) {
    let data = {};
    try { data = event.data ? event.data.json() : {}; }
    catch (e) { data = {body: event.data ? event.data.text() : 'New notification'}; }
    const title = data.title || data.head || 'OppoGlobe';
    const silent = data.silent === true;
    const options = {
        body: data.body || 'You have a new notification.',
        icon: data.icon || '/static/hiring/icons/icon-192.png',
        badge: data.badge || '/static/hiring/icons/icon-72x72.png',
        tag: data.tag || 'oppoglobe',
        renotify: true, silent: silent,
        vibrate: silent ? undefined : [200, 100, 200],
        data: { url: data.url || data.action_url || '/alerts/' }
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const targetUrl = (event.notification.data && event.notification.data.url) || '/alerts/';
    event.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true})
        .then(async function(windowClients) {
            for (const client of windowClients) {
                if ('focus' in client) {
                    await client.focus();
                    if ('navigate' in client) return client.navigate(targetUrl);
                    return client;
                }
            }
            if (clients.openWindow) return clients.openWindow(targetUrl);
        }));
});
"""

    sw_paths = [
        os.path.join(settings.BASE_DIR, 'hiring', 'static', 'hiring', 'js', 'sw.js'),
        os.path.join(settings.BASE_DIR, 'hiring', 'static', 'sw.js'),
    ]
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        sw_paths += [
            os.path.join(static_root, 'hiring', 'sw.js'),
            os.path.join(static_root, 'hiring', 'js', 'sw.js'),
        ]

    content = ("self.addEventListener('install',()=>self.skipWaiting());\n"
               "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));\n")
    for path in sw_paths:
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as handle:
                content = handle.read()
            break
    if "addEventListener('push'" not in content and 'addEventListener("push"' not in content:
        content += push_logic
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def offline_page(request):
    return render(request, 'hiring/offline.html', {'title': 'You are offline'})


@csrf_exempt
def subscribe_to_notifications(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        if not data.get('subscription'):
            return JsonResponse({'error': 'Subscription required'}, status=400)
        return JsonResponse({'success': True,
                             'message': 'Subscription saved'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def save_push_subscription(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'},
                            status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        if not endpoint:
            return JsonResponse({'success': False,
                                 'error': 'Push endpoint is missing.'},
                                status=400)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': keys.get('p256dh', ''),
                'auth': keys.get('auth', ''),
            },
        )
        return JsonResponse({'success': True,
                             'message': 'Push notifications enabled.'})
    except Exception as exc:
        logger.exception('Saving push subscription failed: %s', exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@login_required
def send_test_notification(request):
    result = NotificationService.notify(
        request.user,
        'OppoGlobe Test',
        'Your in-app and phone notification system is working.',
        'system', 'system', '/alerts/', True, True,
    )
    safe = {'success': bool(result.get('success')),
            'push_sent': bool(result.get('push_sent'))}
    if result.get('error'):
        safe['error'] = result['error']
    return JsonResponse(safe, status=200 if safe['success'] else 400)


@csrf_exempt
@login_required
def update_user_status(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        request.user.last_login = timezone.now()
        request.user.save(update_fields=['last_login'])
        return JsonResponse({'success': True, 'status': 'online'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_notification_sound_preferences(request):
    return JsonResponse({
        'success': True,
        'preferences': {
            'selected_sound': 'default', 'sound_volume': 70,
            'sound_enabled': True,
        },
    })


@csrf_exempt
@login_required
def sync_pending_data(request):
    return JsonResponse({'success': True, 'message': 'Sync complete'})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_test(request):
    return Response({'success': True, 'message': 'API is working!',
                     'timestamp': timezone.now().isoformat()})

                
@api_view(['GET'])
@permission_classes([AllowAny])
def user_stats(request):
    total = CustomUser.objects.filter(user_type='applicant').count()
    return Response({'success': True, 'count': total})
    