from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import uuid
from django.conf import settings
import os
from .validators import validate_file_size, validate_video_file_extension, validate_image_file_extension
from django.db.models import Avg, Count
import json
from datetime import timedelta
from django.urls import reverse
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
import random
import string
from decimal import Decimal, InvalidOperation

# ============================================
# NO get_user_model() HERE - Use CustomUser directly
# ============================================

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('applicant', 'Applicant'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='applicant')
    mobile_phone = models.CharField(max_length=15, blank=True, null=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.username} ({self.user_type})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name or self.username
    
    @property
    def liked_posts(self):
        """Return posts liked by this user"""
        return self.post_likes.all()


class ApplicantProfile(models.Model):
    TITLE_CHOICES = (
        ('mr', 'Mr'), ('ms', 'Ms'), ('mrs', 'Mrs'), ('dr', 'Dr')
    )
    GENDER_CHOICES = (
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')
    )
    ETHNICITY_CHOICES = (
        ('african', 'African'), ('coloured', 'Coloured'), ('indian', 'Indian'), 
        ('white', 'White'), ('other', 'Other')
    )
    CITIZENSHIP_CHOICES = (
        ('south_african', 'South African Citizen'), 
        ('permanent_resident', 'Permanent Resident'), 
        ('work_permit', 'Work Permit'), 
        ('other', 'Other')
    )
    SALARY_RANGE_CHOICES = (
        ('0_50k', '0 - 50K Annually'), 
        ('50_100k', '50 - 100K Annually'), 
        ('100_150k', '100 - 150K Annually'), 
        ('150_200k', '150 - 200K Annually'), 
        ('200k_plus', '200K+ Annually')
    )
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=10, choices=TITLE_CHOICES, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    ethnicity = models.CharField(max_length=20, choices=ETHNICITY_CHOICES, blank=True, null=True)
    disabled = models.BooleanField(default=False)
    is_citizen = models.CharField(max_length=20, choices=CITIZENSHIP_CHOICES, blank=True, null=True)
    national_id = models.CharField(max_length=20, blank=True, null=True)
    passport_number = models.CharField(max_length=20, blank=True, null=True)
    birth_date = models.DateField(null=True, blank=True)
    current_home_location = models.CharField(max_length=100, blank=True)
    has_drivers_license = models.BooleanField(default=False)
    has_own_transport = models.BooleanField(default=False)
    preferred_job_title = models.CharField(max_length=100, blank=True)
    availability = models.CharField(max_length=50, default='Immediate')
    willing_to_relocate = models.BooleanField(default=False)
    current_salary = models.CharField(max_length=20, choices=SALARY_RANGE_CHOICES, blank=True, null=True)
    desired_salary = models.CharField(max_length=20, choices=SALARY_RANGE_CHOICES, blank=True, null=True)
    introduction = models.TextField(blank=True)
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]
    )
    profile_completeness = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Skill(models.Model):
    PROFICIENCY_CHOICES = (
        ('beginner', 'Beginner'), 
        ('intermediate', 'Intermediate'), 
        ('good', 'Good'), 
        ('expert', 'Expert')
    )
    
    profile = models.ForeignKey(
        'ApplicantProfile', 
        on_delete=models.CASCADE, 
        related_name='skills',
        null=True,
        blank=True
    )
    skill_name = models.CharField(max_length=100)
    proficiency = models.CharField(max_length=15, choices=PROFICIENCY_CHOICES, default='good')
    
    is_business_recommended = models.BooleanField(default=False)
    recommended_by_business = models.ForeignKey(
        'BusinessProfile', 
        on_delete=models.CASCADE,
        null=True, 
        blank=True,
        related_name='recommended_skills'
    )
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.skill_name} ({self.proficiency})"
    
    def save(self, *args, **kwargs):
        if self.is_business_recommended:
            if not self.recommended_by_business:
                raise ValueError("Business recommended skills must have a business profile")
            if self.profile:
                raise ValueError("Business recommended skills should not have an applicant profile")
        else:
            if not self.profile:
                raise ValueError("Applicant skills must have an applicant profile")
            if self.recommended_by_business:
                raise ValueError("Applicant skills should not have a business profile")
        super().save(*args, **kwargs)


class Education(models.Model):
    profile = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='education')
    qualification = models.CharField(max_length=200)
    institution = models.CharField(max_length=200)
    completion_year = models.IntegerField()
    major_subject = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Education'
    
    def __str__(self):
        return f"{self.qualification} - {self.institution}"


class Document(models.Model):
    DOCUMENT_TYPES = (
        ('cv', 'CV'), 
        ('id', 'ID Document'), 
        ('certificate', 'Certificate'), 
        ('transcript', 'Transcript'), 
        ('other', 'Other')
    )
    
    profile = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/', 
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'])]
    )
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.file_name} ({self.document_type})"


class Industry(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Industries'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CompanySize(models.Model):
    size_range = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    min_employees = models.IntegerField()
    max_employees = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Company Sizes'
        ordering = ['min_employees']
    
    def __str__(self):
        return self.size_range


class JobCategory(models.Model):
    name = models.CharField(max_length=100)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='job_categories')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Job Categories'
        ordering = ['name']
        unique_together = ['name', 'industry']
    
    def __str__(self):
        return f"{self.name} ({self.industry.name})"


class BusinessProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='business_profile')
    company_name = models.CharField(max_length=200)
    company_description = models.TextField(blank=True)
    company_size = models.ForeignKey(CompanySize, on_delete=models.SET_NULL, null=True, blank=True)
    industry = models.ForeignKey(Industry, on_delete=models.SET_NULL, null=True, blank=True)
    website = models.URLField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    company_logo = models.ImageField(
        upload_to='company_logos/%Y/%m/%d/', 
        blank=True, 
        null=True, 
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg', 'webp'])]
    )
    
    is_verified = models.BooleanField(default=False)
    verification_document = models.FileField(upload_to='verification_docs/%Y/%m/%d/', blank=True, null=True)
    
    receive_applicant_notifications = models.BooleanField(default=True)
    receive_newsletter = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.company_name} - {self.user.username}"
    
    def get_company_logo_url(self):
        if self.company_logo:
            return self.company_logo.url
        return '/static/hiring/images/default-company-logo.png'


class BusinessPreference(models.Model):
    PREFERENCE_TYPES = (
        ('education', 'Education'),
        ('skills', 'Skills'), 
        ('employment', 'Employment'),
        ('experience', 'Experience'),
        ('certifications', 'Certifications'),
        ('languages', 'Languages'),
        ('location', 'Location'),
        ('industry', 'Industry'),
        ('custom', 'Custom'),
    )
    
    business_profile = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='preferences')
    preference_type = models.CharField(max_length=20, choices=PREFERENCE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    criteria = models.JSONField(default=dict, blank=True)
    
    positions_available = models.PositiveIntegerField(default=1)
    priority_level = models.CharField(max_length=20, choices=(
        ('low', 'Low'),
        ('medium', 'Medium'), 
        ('high', 'High'),
        ('critical', 'Critical'),
    ), default='medium')
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
        ordering = ['-priority_level', '-created_at']
    
    def __str__(self):
        return f"{self.preference_type}: {self.title} ({self.positions_available} positions)"
    
    @property
    def criteria_summary(self):
        if not self.criteria:
            return "No specific criteria"
        
        summary = []
        for key, value in self.criteria.items():
            if value:
                if isinstance(value, list):
                    summary.append(f"{key}: {', '.join(str(v) for v in value)}")
                else:
                    summary.append(f"{key}: {value}")
        
        return "; ".join(summary)


class BusinessEmploymentPreference(models.Model):
    CONTRACT_TYPE_CHOICES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    )
    
    business_profile = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='employment_preferences')
    preferred_contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES)
    positions_available = models.PositiveIntegerField(default=1)
    job_title_keywords = models.JSONField(default=list, blank=True)
    required_experience_years = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Business Employment Preferences'
    
    def __str__(self):
        return f"{self.get_preferred_contract_type_display()} - {self.positions_available} positions"


class EmploymentHistory(models.Model):
    CONTRACT_TYPE_CHOICES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
    )
    
    profile = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE, related_name='employment_history')
    job_title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, null=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    currently_working = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
        verbose_name_plural = 'Employment Histories'
    
    def __str__(self):
        return f"{self.job_title} at {self.company}"
    
    @property
    def experience_months(self):
        end_date = self.end_date if not self.currently_working else timezone.now().date()
        if self.start_date and end_date:
            return (end_date.year - self.start_date.year) * 12 + (end_date.month - self.start_date.month)
        return 0


class JobListing(models.Model):
    LISTING_STATUS = (
        ('draft', 'Draft'), 
        ('under_review', 'Under Review'), 
        ('published', 'Published'), 
        ('closed', 'Closed')
    )
    
    listing_reference = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=LISTING_STATUS, default='draft')
    apply_by = models.DateField()
    position_summary = models.TextField()
    industry = models.CharField(max_length=100)
    job_category = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    contract_type = models.CharField(max_length=50)
    ee_position = models.BooleanField(default=True)
    company_name = models.CharField(max_length=200, default='Admin')
    company_logo = models.ImageField(
        upload_to='company_logos/%Y/%m/%d/', 
        blank=True, 
        null=True, 
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg', 'webp'])]
    )
    company_description = models.TextField()
    job_description = models.TextField()
    knowledge_requirements = models.TextField()
    skills_requirements = models.TextField()
    competencies_requirements = models.TextField()
    experience_requirements = models.TextField()
    education_requirements = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.title} - {self.listing_reference}"
    
    def get_company_logo_url(self):
        if self.company_logo:
            return self.company_logo.url
        return '/static/hiring/images/default-company-logo.png'


class Application(models.Model):
    APPLICATION_STATUS = (
        ('submitted', 'Submitted'), 
        ('under_review', 'Under Review'), 
        ('shortlisted', 'Shortlisted'), 
        ('interview', 'Interview'), 
        ('successful', 'Successful'), 
        ('unsuccessful', 'Unsuccessful')
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='applications')
    job_listing = models.ForeignKey('JobListing', on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='submitted')
    applied_date = models.DateTimeField(auto_now_add=True)
    cover_letter = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        app_label = 'hiring'
        unique_together = ['applicant', 'job_listing']
    
    def __str__(self):
        return f"{self.applicant} - {self.job_listing}"


class NotificationPreference(models.Model):
    NOTIFICATION_TYPES = (
        ('email', 'Email'), 
        ('in_app', 'In-App'), 
        ('both', 'Both')
    )
    
    applicant = models.OneToOneField('ApplicantProfile', on_delete=models.CASCADE, related_name='notification_preferences')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='both')
    application_updates = models.BooleanField(default=True)
    job_alerts = models.BooleanField(default=True)
    profile_reminders = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"Notification preferences for {self.applicant}"


class Alert(models.Model):
    applicant = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='alerts')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"Alert for {self.applicant}: {self.title}"


class EmailTemplate(models.Model):
    TEMPLATE_TYPES = (
        ('application_submitted', 'Application Submitted'), 
        ('application_status_update', 'Application Status Update'), 
        ('job_alert', 'Job Alert'), 
        ('profile_reminder', 'Profile Reminder'), 
        ('weekly_digest', 'Weekly Digest'), 
        ('welcome', 'Welcome Email')
    )
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"


class SentNotification(models.Model):
    applicant = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    sent_via = models.CharField(max_length=10, choices=NotificationPreference.NOTIFICATION_TYPES)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'hiring'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.subject} to {self.applicant}"


class JobAlert(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'), 
        ('weekly', 'Weekly'), 
        ('instant', 'Instant')
    )
    
    applicant = models.ForeignKey('ApplicantProfile', on_delete=models.CASCADE, related_name='job_alerts')
    keywords = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=100, blank=True)
    job_category = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"Job alert for {self.applicant}"


class SearchHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='search_history')
    query = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)
    results_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']
        verbose_name_plural = 'Search Histories'

    def __str__(self):
        return f"{self.user.username} - {self.query}"


class BusinessNotificationPreference(models.Model):
    business = models.OneToOneField(BusinessProfile, on_delete=models.CASCADE, related_name='notification_preferences')
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    new_applications = models.BooleanField(default=True)
    job_expiry_alerts = models.BooleanField(default=True)
    candidate_updates = models.BooleanField(default=True)
    system_maintenance = models.BooleanField(default=False)
    marketing_emails = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'hiring'
    
    def __str__(self):
        return f"Notifications for {self.business.company_name}"


class BusinessAlert(models.Model):
    ALERT_TYPES = (
        ('application', 'New Application'),
        ('expiry', 'Job Expiry'),
        ('custom', 'Custom Alert'),
        ('system', 'System Alert')
    )
    
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='business_alerts')
    job_listing = models.ForeignKey(JobListing, on_delete=models.CASCADE, null=True, blank=True, related_name='business_alerts')
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES, default='custom')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_active = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.business.company_name}"


class BusinessSentNotification(models.Model):
    NOTIFICATION_TYPES = (
        ('application', 'Application Update'),
        ('job', 'Job Update'),
        ('system', 'System Notification'),
        ('marketing', 'Marketing')
    )
    
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='sent_notifications')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='system')
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'hiring'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.subject} - {self.business.company_name}"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(CustomUser, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-updated_at']

    def __str__(self):
        participant_names = [user.username for user in self.participants.all()]
        return f"Conversation between {', '.join(participant_names)}"


class Message(models.Model):
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('file', 'File'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    file = models.FileField(upload_to='message_files/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    file_mime_type = models.CharField(max_length=100, blank=True, null=True)
    
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    is_forwarded = models.BooleanField(default=False)
    original_sender = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='forwarded_messages')
    
    is_read = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} in {self.conversation.id}"


class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='recipients')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'hiring'
        unique_together = ['message', 'recipient']


class UserStatus(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='chat_status')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    typing_to = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'hiring'

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"


class BusinessProfileView(models.Model):
    business_profile = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'business_profile_views'


class Post(models.Model):
    POST_TYPES = [
        ('job', 'Job Post'),
        ('update', 'Company Update'),
        ('news', 'Industry News'),
        ('general', 'General Post'),
        ('question', 'Question'),
        ('achievement', 'Achievement'),
        ('advice', 'Career Advice'),
    ]
    
    VISIBILITY_CHOICES = [
        ('public', 'Public - Everyone'),
        ('connections', 'Connections Only'),
        ('company', 'Company Only'),
        ('private', 'Private - Just Me'),
    ]
    
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    company = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, null=True, blank=True)
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='general')
    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.ImageField(
        upload_to='posts/images/%Y/%m/%d/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_image_file_extension]
    )
    video = models.FileField(
        upload_to='posts/videos/%Y/%m/%d/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_video_file_extension]
    )
    video_url = models.URLField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    views = models.PositiveIntegerField(default=0)
    likes = models.ManyToManyField(CustomUser, related_name='post_likes', blank=True)
    dislikes = models.ManyToManyField(CustomUser, related_name='post_dislikes', blank=True)
    shares = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    
    average_rating = models.FloatField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='public')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    is_published = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['post_type']),
            models.Index(fields=['author']),
            models.Index(fields=['is_published']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.author.username}"
    
    def total_engagement(self):
        return self.likes.count() + self.comment_count + self.shares
    
    def update_comment_count(self):
        count = self.comments.count()
        if self.comment_count != count:
            self.comment_count = count
            self.save(update_fields=['comment_count'])
        return count

    def get_tags_list(self):
        if not self.tags:
            return []
        tag_list = [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return tag_list
    
    def set_tags_list(self, tag_list):
        if tag_list:
            self.tags = ', '.join([str(tag).strip() for tag in tag_list])
        else:
            self.tags = ''


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    job_listing = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    likes = models.ManyToManyField(CustomUser, related_name='comment_likes', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_edited = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.post:
            return f"Comment by {self.author.username} on post: {self.post.title}"
        elif self.job_listing:
            return f"Comment by {self.author.username} on job: {self.job_listing.title}"
        return f"Comment by {self.author.username}"
    
    def clean(self):
        if not self.post and not self.job_listing:
            raise ValidationError("Comment must be attached to either a post or a job listing")
        if self.post and self.job_listing:
            raise ValidationError("Comment cannot be attached to both a post and a job listing")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Rating(models.Model):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='ratings')
    rating = models.IntegerField(choices=RATING_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'post']


class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='post_views')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['post', 'ip_address']


class JobInteraction(models.Model):
    INTERACTION_TYPES = (
        ('like', 'Like'),
        ('dislike', 'Dislike'),
        ('comment', 'Comment'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    job_listing = models.ForeignKey('JobListing', on_delete=models.CASCADE)
    
    interaction_type = models.CharField(max_length=10, choices=INTERACTION_TYPES)
    comment_text = models.TextField(blank=True, null=True)
    
    parent_interaction = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'job_listing', 'interaction_type']
    
    def __str__(self):
        return f"{self.user.username} {self.interaction_type} on {self.job_listing.title}"


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    video_file = models.FileField(
        upload_to='videos/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(['mp4', 'mov', 'avi', 'webm'])
        ],
        help_text="Upload video file (MP4, MOV, AVI, WEBM)"
    )
    thumbnail = models.ImageField(
        upload_to='videos/thumbnails/%Y/%m/%d/',
        null=True, blank=True
    )
    
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    author = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='videos'
    )
    
    PRIVACY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
        ('connections', 'Connections Only'),
        ('company', 'Company Only'),
    )
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    is_published = models.BooleanField(default=True)
    
    views = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    
    likes = models.ManyToManyField(
        CustomUser,
        related_name='liked_videos',
        blank=True
    )
    
    watch_time = models.BigIntegerField(default=0, help_text="Total watch time in seconds")
    average_watch_percentage = models.FloatField(default=0, help_text="Average % of video watched")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'realestate_videos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['is_published', 'privacy']),
        ]
    
    def __str__(self):
        return f"{self.title or 'Untitled'} by {self.author.username}"
    
    def get_likes_count(self):
        return self.likes.count()
    
    def get_comments_count(self):
        return self.comments.filter(is_active=True).count()
    
    def get_engagement_score(self):
        return (
            self.likes.count() * 2 +
            self.comments.filter(is_active=True).count() * 3 +
            self.shares * 5
        )
    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])
    
    def increment_shares(self):
        self.shares += 1
        self.save(update_fields=['shares'])
    
    @property
    def video_url(self):
        if self.video_file:
            return self.video_file.url
        return None
    
    @property
    def thumbnail_url(self):
        if self.thumbnail:
            return self.thumbnail.url
        return '/static/images/default-video-thumbnail.jpg'


class VideoComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='video_comments'
    )
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='replies'
    )
    
    content = models.TextField(max_length=1000)
    
    likes = models.ManyToManyField(
        CustomUser,
        related_name='liked_video_comments',
        blank=True
    )
    
    is_active = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'realestate_video_comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['video', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['parent_comment', '-created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.video.title}"
    
    def get_likes_count(self):
        return self.likes.count()
    
    def get_replies_count(self):
        return self.replies.filter(is_active=True).count()
    
    def has_liked(self, user):
        return self.likes.filter(id=user.id).exists()


class PushSubscription(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        null=True,
        blank=True,
    )

    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.endpoint[:40]}"

        
class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class Page(models.Model):
    """Editable static pages: About, Contact, Privacy, Terms, Cookies, Help, etc."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="URL slug, e.g., 'about'")
    content = models.TextField(help_text="Use HTML for rich formatting.")
    meta_description = models.CharField(max_length=160, blank=True, help_text="SEO description")
    keywords = models.CharField(max_length=200, blank=True, help_text="Comma-separated keywords")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:page_detail', kwargs={'slug': self.slug})

    class Meta:
        ordering = ['title']

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.CharField(max_length=300, blank=True)
    featured_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    author = models.CharField(max_length=100, default='OppoGlobe Team')
    publish_date = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    meta_description = models.CharField(max_length=160, blank=True)
    keywords = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:blog_detail', kwargs={'slug': self.slug})

    class Meta:
        ordering = ['-publish_date']

class Career(models.Model):
    EMPLOYMENT_TYPES = (
        ('full_time', 'Full-Time'),
        ('part_time', 'Part-Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('remote', 'Remote'),
    )
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='full_time')
    description = models.TextField(help_text="Detailed job description")
    requirements = models.TextField(blank=True, help_text="Optional requirements")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

class FAQ(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True, default='General')
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    def __str__(self):
        return self.question

    class Meta:
        ordering = ['category', 'order']


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.subject}"



class StaticPage(models.Model):
    """
    Model for static pages like Privacy Policy, Terms of Service, etc.
    """
    PAGE_TYPES = [
        ('privacy', 'Privacy Policy'),
        ('terms', 'Terms of Service'),
        ('cookies', 'Cookies Policy'),
        ('help', 'Help Center'),
        ('about', 'About Us'),
        ('contact', 'Contact Us'),
        ('faq', 'FAQ'),
        ('careers', 'Careers'),
        ('blog', 'Blog'),
    ]
    
    page_type = models.CharField(max_length=50, choices=PAGE_TYPES, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="HTML content for the page. Use <h1>, <p>, <ul>, etc.")
    meta_description = models.CharField(max_length=200, blank=True, help_text="SEO meta description")
    meta_keywords = models.CharField(max_length=200, blank=True, help_text="SEO meta keywords")
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # For sections (like Privacy Policy sections)
    sections = models.JSONField(default=list, blank=True, help_text="List of sections with title and content. Format: [{\"title\": \"Section 1\", \"content\": \"Content here\"}]")
    
    # FIXED: Use CustomUser instead of User
    updated_by = models.ForeignKey(
        'CustomUser',  # Changed from 'User' to 'CustomUser'
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='updated_static_pages'
    )
    
    class Meta:
        ordering = ['page_type']
        verbose_name = 'Static Page'
        verbose_name_plural = 'Static Pages'
    
    def __str__(self):
        return f"{self.get_page_type_display()} - {self.title}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        try:
            return reverse(self.page_type)
        except:
            return f'/{self.page_type}/'
    
    def get_sections_as_list(self):
        """Return sections as a list of dicts"""
        if isinstance(self.sections, list):
            return self.sections
        return []
    
    def get_sections_as_json(self):
        """Return sections as JSON string"""
        import json
        return json.dumps(self.get_sections_as_list())
    
    def save(self, *args, **kwargs):
        # Ensure sections is always a list
        if not self.sections:
            self.sections = []
        super().save(*args, **kwargs)


class HelpCenterPage(models.Model):
    """Editable content displayed below the built-in Help Center guides."""
    title = models.CharField(max_length=160, default="Help Center")
    description = models.CharField(
        max_length=300,
        default="Find practical guides and answers about using OppoGlobe.",
    )
    content = models.TextField(blank=True, help_text="Optional HTML for additional help information.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Help Center page"
        verbose_name_plural = "Help Center pages"

    def __str__(self):
        return self.title
