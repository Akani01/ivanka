from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django import forms
from django.urls import reverse
from .models import *

# ─── Custom User Admin ──────────────────────────────────────────────
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'mobile_phone', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login')

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'mobile_phone')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('applicantprofile')


# ─── ApplicantProfile ───────────────────────────────────────────────
class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'first_name', 'last_name', 'profile_completeness', 'created_at')
    list_filter = ('ethnicity', 'disabled', 'willing_to_relocate', 'created_at')
    search_fields = ('first_name', 'last_name', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'profile_completeness')
    list_per_page = 20

    fieldsets = (
        ('Personal Information', {
            'fields': (
                'user', 'title', 'gender', 'first_name', 'last_name',
                'ethnicity', 'disabled', 'birth_date'
            )
        }),
        ('Citizenship & Identification', {
            'fields': ('is_citizen', 'national_id', 'passport_number')
        }),
        ('Location & Transport', {
            'fields': ('current_home_location', 'has_drivers_license', 'has_own_transport')
        }),
        ('Career Preferences', {
            'fields': (
                'preferred_job_title', 'availability', 'willing_to_relocate',
                'current_salary', 'desired_salary', 'introduction'
            )
        }),
        ('System Information', {
            'fields': ('profile_completeness', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'


# ─── JobListing ─────────────────────────────────────────────────────
class JobListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'listing_reference', 'status', 'company_name', 'location', 'apply_by', 'created_at')
    list_filter = ('status', 'industry', 'contract_type', 'created_at')
    search_fields = ('title', 'company_name', 'listing_reference', 'location')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status',)
    list_per_page = 25

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'listing_reference', 'title', 'status', 'apply_by',
                'industry', 'job_category', 'location', 'contract_type'
            )
        }),
        ('Company Information', {
            'fields': ('company_name', 'company_logo', 'company_description')
        }),
        ('Position Details', {
            'fields': ('position_summary', 'job_description', 'ee_position')
        }),
        ('Requirements', {
            'fields': (
                'knowledge_requirements', 'skills_requirements',
                'competencies_requirements', 'experience_requirements',
                'education_requirements'
            )
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# ─── Application ────────────────────────────────────────────────────
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('get_applicant_name', 'get_job_title', 'status', 'applied_date', 'get_company')
    list_filter = ('status', 'applied_date', 'job_listing__company_name')
    search_fields = (
        'applicant__first_name', 'applicant__last_name',
        'job_listing__title', 'job_listing__company_name'
    )
    readonly_fields = ('applied_date',)
    list_per_page = 30

    def get_applicant_name(self, obj):
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    get_applicant_name.short_description = 'Applicant'
    get_applicant_name.admin_order_field = 'applicant__first_name'

    def get_job_title(self, obj):
        return obj.job_listing.title
    get_job_title.short_description = 'Job Title'
    get_job_title.admin_order_field = 'job_listing__title'

    def get_company(self, obj):
        return obj.job_listing.company_name
    get_company.short_description = 'Company'
    get_company.admin_order_field = 'job_listing__company_name'


# ─── Skill ──────────────────────────────────────────────────────────
class SkillAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'skill_name', 'proficiency')
    list_filter = ('proficiency',)
    search_fields = ('skill_name', 'profile__first_name', 'profile__last_name')

    def get_applicant(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'profile__first_name'


# ─── EmploymentHistory ──────────────────────────────────────────────
class EmploymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'job_title', 'company', 'start_date', 'end_date', 'contract_type')
    list_filter = ('contract_type', 'start_date')
    search_fields = ('job_title', 'company', 'profile__first_name', 'profile__last_name')

    def get_applicant(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'profile__first_name'


# ─── Education ──────────────────────────────────────────────────────
class EducationAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'qualification', 'institution', 'completion_year')
    list_filter = ('completion_year',)
    search_fields = ('qualification', 'institution', 'profile__first_name', 'profile__last_name')

    def get_applicant(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'profile__first_name'


# ─── Document ──────────────────────────────────────────────────────
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'document_type', 'file_name', 'uploaded_at')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('file_name', 'profile__first_name', 'profile__last_name')
    readonly_fields = ('uploaded_at',)

    def get_applicant(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'profile__first_name'


# ─── Alert ──────────────────────────────────────────────────────────
class AlertAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('title', 'message', 'applicant__first_name', 'applicant__last_name')
    readonly_fields = ('created_at',)

    def get_applicant(self, obj):
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'applicant__first_name'


# ─── NotificationPreference ────────────────────────────────────────
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'notification_type', 'application_updates', 'job_alerts')
    list_filter = ('notification_type', 'application_updates', 'job_alerts')

    def get_applicant(self, obj):
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'applicant__first_name'


# ─── EmailTemplate ──────────────────────────────────────────────────
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'created_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'subject', 'template_type')
    readonly_fields = ('created_at',)
    list_editable = ('is_active',)


# ─── SentNotification ──────────────────────────────────────────────
class SentNotificationAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'subject', 'notification_type', 'sent_via', 'is_read', 'sent_at')
    list_filter = ('notification_type', 'sent_via', 'is_read', 'sent_at')
    search_fields = ('subject', 'applicant__first_name', 'applicant__last_name')
    readonly_fields = ('sent_at',)

    def get_applicant(self, obj):
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'applicant__first_name'


# ─── JobAlert ───────────────────────────────────────────────────────
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ('get_applicant', 'keywords', 'location', 'frequency', 'is_active', 'created_at')
    list_filter = ('frequency', 'is_active', 'created_at')
    search_fields = ('keywords', 'location', 'applicant__first_name', 'applicant__last_name')
    readonly_fields = ('created_at', 'last_sent')

    def get_applicant(self, obj):
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    get_applicant.short_description = 'Applicant'
    get_applicant.admin_order_field = 'applicant__first_name'


# ═════════════════════════════════════════════════════════════════════
#  POST & VIDEO SECTIONS (FULLY ENABLED)
# ═════════════════════════════════════════════════════════════════════

# ─── Post ───────────────────────────────────────────────────────────
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'post_type', 'visibility', 'is_published', 'created_at', 'total_engagement')
    list_filter = ('post_type', 'visibility', 'is_published', 'created_at')
    search_fields = ('title', 'content', 'author__username', 'author__email', 'tags')
    readonly_fields = ('created_at', 'updated_at', 'edited_at', 'views', 'likes', 'dislikes', 'shares', 'comment_count', 'average_rating', 'rating_count')
    list_per_page = 25
    filter_horizontal = ('likes', 'dislikes')
    fieldsets = (
        ('Basic Information', {
            'fields': ('author', 'company', 'post_type', 'title', 'content')
        }),
        ('Media & Attachments', {
            'fields': ('image', 'video', 'video_url')
        }),
        ('Visibility & Tags', {
            'fields': ('visibility', 'tags')
        }),
        ('Engagement Metrics', {
            'fields': ('views', 'likes', 'dislikes', 'shares', 'comment_count', 'average_rating', 'rating_count'),
            'classes': ('collapse',)
        }),
        ('Publishing', {
            'fields': ('is_published', 'is_edited', 'created_at', 'updated_at', 'edited_at')
        })
    )

    def total_engagement(self, obj):
        return obj.total_engagement()
    total_engagement.short_description = 'Total Engagement'


# ─── Comment ────────────────────────────────────────────────────────
class CommentAdmin(admin.ModelAdmin):
    list_display = ('get_content_preview', 'author', 'post_or_job', 'created_at', 'is_edited')
    list_filter = ('created_at', 'is_edited')
    search_fields = ('content', 'author__username', 'author__email', 'post__title', 'job_listing__title')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 30
    fieldsets = (
        (None, {
            'fields': ('post', 'job_listing', 'author', 'content', 'parent_comment')
        }),
        ('System', {
            'fields': ('is_edited', 'created_at', 'updated_at')
        })
    )

    def get_content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    get_content_preview.short_description = 'Content Preview'

    def post_or_job(self, obj):
        if obj.post:
            return f"Post: {obj.post.title}"
        elif obj.job_listing:
            return f"Job: {obj.job_listing.title}"
        return "Orphan"
    post_or_job.short_description = 'Attached To'


# ─── Rating ─────────────────────────────────────────────────────────
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'post__title')
    readonly_fields = ('created_at',)


# ─── PostView ──────────────────────────────────────────────────────
class PostViewAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('post__title', 'user__username', 'ip_address')
    readonly_fields = ('viewed_at',)


# ─── Video ──────────────────────────────────────────────────────────
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'privacy', 'is_published', 'views', 'created_at')
    list_filter = ('privacy', 'is_published', 'created_at')
    search_fields = ('title', 'description', 'author__username', 'author__email')
    readonly_fields = ('views', 'shares', 'watch_time', 'average_watch_percentage', 'created_at', 'updated_at')
    filter_horizontal = ('likes',)
    fieldsets = (
        ('Video Information', {
            'fields': ('title', 'description', 'video_file', 'thumbnail', 'author', 'privacy', 'is_published')
        }),
        ('Tags & Metadata', {
            'fields': ('tags',)
        }),
        ('Engagement', {
            'fields': ('views', 'shares', 'likes', 'watch_time', 'average_watch_percentage'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# ─── VideoComment ──────────────────────────────────────────────────
class VideoCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'video', 'author', 'content_preview', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('content', 'author__username', 'author__email', 'video__title')
    readonly_fields = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('likes',)

    def content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    content_preview.short_description = 'Content'


# ─── Conversation & Messages ────────────────────────────────────────
class MessageRecipientInline(admin.TabularInline):
    model = MessageRecipient
    extra = 1
    fields = ('recipient', 'is_read', 'read_at')
    readonly_fields = ('read_at',)


class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'message_type', 'content_preview', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('content', 'sender__username', 'sender__email', 'conversation__id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'delivered_at', 'read_at')
    inlines = [MessageRecipientInline]
    list_per_page = 30
    fieldsets = (
        (None, {
            'fields': ('conversation', 'sender', 'content', 'message_type')
        }),
        ('File Attachment', {
            'fields': ('file', 'file_name', 'file_size', 'file_mime_type')
        }),
        ('Threading', {
            'fields': ('parent_message', 'is_forwarded', 'original_sender')
        }),
        ('Status', {
            'fields': ('is_read', 'delivered_at', 'read_at', 'created_at', 'updated_at')
        })
    )

    def content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '') if obj.content else '(No text)'
    content_preview.short_description = 'Content Preview'


class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant_list', 'created_at', 'updated_at', 'is_active')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('id', 'participants__username', 'participants__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('participants',)
    list_per_page = 30
    fieldsets = (
        (None, {
            'fields': ('participants', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

    def participant_list(self, obj):
        return ", ".join([user.username for user in obj.participants.all()])
    participant_list.short_description = 'Participants'


class UserStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online', 'last_seen', 'typing_to')
    list_filter = ('is_online', 'last_seen')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('last_seen',)


# ─── Static Pages & Other Models ────────────────────────────────────

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ['title', 'slug', 'is_published', 'updated_at']
    search_fields = ['title', 'content']


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ['title', 'author', 'publish_date', 'is_published']
    list_filter = ['is_published', 'publish_date']
    search_fields = ['title', 'content']


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ['title', 'location', 'employment_type', 'is_active', 'created_at']
    list_filter = ['is_active', 'employment_type']
    search_fields = ['title', 'description']


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'order', 'is_published']
    list_editable = ['order', 'is_published']
    list_filter = ['category', 'is_published']
    search_fields = ['question', 'answer']


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'subscribed_at', 'is_active']
    list_editable = ['is_active']
    search_fields = ['email']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'is_read']
    list_editable = ['is_read']
    search_fields = ['name', 'email', 'message']


class StaticPageForm(forms.ModelForm):
    class Meta:
        model = StaticPage
        fields = '__all__'
        widgets = {
            'content': forms.Textarea(attrs={'rows': 20, 'class': 'monospace', 'style': 'width: 100%; font-family: monospace;'}),
            'sections': forms.Textarea(attrs={'rows': 10, 'class': 'monospace', 'style': 'width: 100%; font-family: monospace;'}),
        }

    def clean_sections(self):
        data = self.cleaned_data.get('sections', [])
        if isinstance(data, str):
            try:
                import json
                return json.loads(data)
            except json.JSONDecodeError:
                return []
        return data


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    form = StaticPageForm
    list_display = ['page_type', 'title', 'last_updated', 'is_active', 'updated_by', 'preview_link']
    list_filter = ['page_type', 'is_active', 'last_updated']
    search_fields = ['title', 'content', 'meta_description', 'page_type']
    readonly_fields = ['created_at', 'last_updated', 'preview_link']

    fieldsets = (
        ('Page Information', {
            'fields': ('page_type', 'title', 'is_active')
        }),
        ('Content', {
            'fields': ('content', 'sections'),
            'classes': ('wide',),
            'description': 'For pages with sections (like Privacy Policy), use the sections field with JSON format: [{"title": "Section 1", "content": "Content here"}]'
        }),
        ('SEO & Meta', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'last_updated', 'updated_by', 'preview_link'),
            'classes': ('collapse',)
        }),
    )

    def preview_link(self, obj):
        try:
            url = reverse(obj.page_type)
            return mark_safe(f'<a href="{url}" target="_blank">🔗 View Page</a>')
        except:
            return f'/{obj.page_type}/ (no URL configured)'
    preview_link.short_description = 'Preview'

    def save_model(self, request, obj, form, change):
        if request.user.is_superuser:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ═════════════════════════════════════════════════════════════════════
#  REGISTRATIONS (including Video & VideoComment)
# ═════════════════════════════════════════════════════════════════════

# Existing registrations
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(ApplicantProfile, ApplicantProfileAdmin)
admin.site.register(JobListing, JobListingAdmin)
admin.site.register(Application, ApplicationAdmin)
admin.site.register(Skill, SkillAdmin)
admin.site.register(EmploymentHistory, EmploymentHistoryAdmin)
admin.site.register(Education, EducationAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Alert, AlertAdmin)
admin.site.register(NotificationPreference, NotificationPreferenceAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(SentNotification, SentNotificationAdmin)
admin.site.register(JobAlert, JobAlertAdmin)

# Post & related models
admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Rating, RatingAdmin)
admin.site.register(PostView, PostViewAdmin)

# Video & VideoComment (now fully enabled)
admin.site.register(Video, VideoAdmin)
admin.site.register(VideoComment, VideoCommentAdmin)

# Messaging
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(MessageRecipient)          # standalone registration
admin.site.register(UserStatus, UserStatusAdmin)

# Customize admin header
admin.site.site_header = "Hiring Portal Platform Administration"
admin.site.site_title = "System Admin"
admin.site.index_title = "Welcome to Hiring Portal Platform Administration"

@admin.register(HelpCenterPage)
class HelpCenterPageAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")
    search_fields = ("title", "description")
