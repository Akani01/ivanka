from django.core.mail import send_mail
from django.conf import settings
from ..models import SentNotification, EmailTemplate

class NotificationService:
    """
    Service for handling all types of notifications
    """
    
    @staticmethod
    def send_application_submission(application):
        """
        Send notification when application is submitted
        """
        try:
            # Get or create email template
            template, created = EmailTemplate.objects.get_or_create(
                template_type='application_submitted',
                defaults={
                    'name': 'Application Submitted',
                    'subject': 'Application Submitted Successfully',
                    'body': f"""
Dear {application.applicant.first_name},

Your application for {application.job_listing.title} at {application.job_listing.company_name} has been submitted successfully.

Application Reference: APP-{application.id.hex[:8].upper()}

We will review your application and contact you if you are shortlisted.

Best regards,
{application.job_listing.company_name} Team
                    """.strip()
                }
            )
            
            # Send email notification
            if application.applicant.user.email:
                send_mail(
                    template.subject,
                    template.body,
                    settings.DEFAULT_FROM_EMAIL,
                    [application.applicant.user.email],
                    fail_silently=True,
                )
            
            # Create in-app notification
            SentNotification.objects.create(
                applicant=application.applicant,
                notification_type='application_submitted',
                subject=template.subject,
                message=template.body,
                sent_via='both'
            )
            
            # Create alert
            from ..models import Alert
            Alert.objects.create(
                applicant=application.applicant,
                title='Application Submitted',
                message=f'Your application for {application.job_listing.title} has been submitted successfully.'
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending application submission notification: {str(e)}")
            return False
    
    @staticmethod
    def send_application_status_update(application, old_status, new_status):
        """
        Send notification when application status changes
        """
        try:
            status_messages = {
                'shortlisted': 'Congratulations! Your application has been shortlisted.',
                'interview': 'You have been invited for an interview!',
                'successful': 'Congratulations! Your application has been successful!',
                'unsuccessful': 'Thank you for your application. Unfortunately...'
            }
            
            message = status_messages.get(new_status, f'Your application status has changed to {new_status}.')
            
            # Create in-app notification
            SentNotification.objects.create(
                applicant=application.applicant,
                notification_type='application_status_update',
                subject=f'Application Status Update - {application.job_listing.title}',
                message=message,
                sent_via='both'
            )
            
            # Create alert
            from ..models import Alert
            Alert.objects.create(
                applicant=application.applicant,
                title='Application Status Updated',
                message=f'Your application for {application.job_listing.title} has been updated to {new_status}.'
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending status update notification: {str(e)}")
            return False
    
    @staticmethod
    def send_welcome_email(applicant_profile):
        """
        Send welcome email to new applicant
        """
        try:
            template, created = EmailTemplate.objects.get_or_create(
                template_type='welcome',
                defaults={
                    'name': 'Welcome Email',
                    'subject': 'Welcome to Our Job Portal',
                    'body': f"""
Dear {applicant_profile.first_name},

Welcome to our job portal! Your account has been created successfully.

We're excited to help you find your next career opportunity.

Please complete your profile to increase your chances of getting hired.

Best regards,
The Hiring Team
                    """.strip()
                }
            )
            
            if applicant_profile.user.email:
                send_mail(
                    template.subject,
                    template.body,
                    settings.DEFAULT_FROM_EMAIL,
                    [applicant_profile.user.email],
                    fail_silently=True,
                )
            
            return True
            
        except Exception as e:
            print(f"Error sending welcome email: {str(e)}")
            return False