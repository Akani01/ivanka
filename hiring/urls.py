from django.urls import path, include
from django.views.generic import TemplateView

from . import views, message_views

# ============================================================
# MESSAGING API (mounted under /api/conversations/)
# ============================================================
message_urlpatterns = [
    path('', message_views.ConversationViewSet.as_view({'get': 'list'}),
         name='conversation-list'),
    path('unread-count/',
         message_views.ConversationViewSet.as_view({'get': 'unread_count'}),
         name='conversation-unread-count'),
    path('start/<str:user_id>/',
         message_views.ConversationViewSet.as_view({'post': 'start_conversation'}),
         name='start-conversation'),
    path('<uuid:conversation_id>/messages/',
         message_views.MessageViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='conversation-messages'),
    path('<uuid:conversation_id>/messages/send-file/',
         message_views.MessageViewSet.as_view({'post': 'send_file'}),
         name='send-file'),
    path('users/', message_views.UserViewSet.as_view({'get': 'list'}),
         name='user-list'),
    path('users/search/', message_views.UserViewSet.as_view({'get': 'search'}),
         name='user-search'),
    path('user-status/update/', message_views.update_user_status,
         name='update-user-status'),
    path('user-status/<str:user_id>/', message_views.get_user_status,
         name='get-user-status'),
]


urlpatterns = [
    # ===================== MAIN PAGES =====================
    path('dashboard/', views.dashboard_page, name='home'),
    path('profile/', views.profile_page, name='profile_page'),
    path('applications/', views.applications_page, name='applications_page'),
    path('dashboard/', views.dashboard_page, name='dashboard_page'),
    path('profile/documents/', views.documents_page, name='documents_page'),
    path('profile/skills/', views.skills_page, name='skills_page'),
    path('profile/employment/', views.employment_page, name='employment_page'),
    path('profile/education/', views.education_page, name='education_page'),
    path('alerts/', views.alerts_page, name='alerts_page'),
    path('preferences/', views.preferences_page, name='preferences_page'),
    path('logout/', views.custom_logout, name='logout_page'),
    path('analytics/', views.analytics_page, name='analytics'),
    path('settings/', views.settings_page, name='settings'),
    path('notifications/', views.notifications_page, name='notifications'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('security/', views.security_page, name='security'),
    path('account/', views.account_page, name='account'),

    # ===================== FEED & POSTS =====================
    path('feed/', views.feed_page, name='feed_page'),
    path('posts/', views.posts_page, name='posts_page'),

    # ===================== MESSAGING PAGES =====================
    path('messaging/', views.messaging_page, name='messaging_page'),
    path('connections/', views.connections_page, name='connections_page'),

    # ===================== JOBS (page) =====================
    path('jobs/<str:job_id>/', views.job_detail_page, name='job_detail_page'),

    # ===================== PWA + PUSH =====================
    path('black-theme/', views.black_theme_settings, name='black_theme'),
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.pwa_sw, name='pwa_sw'),
    path('offline/', views.offline_page, name='offline_page'),
    path('api/push/subscribe/', views.save_push_subscription,
         name='save_push_subscription'),
    path('api/push/test/', views.send_test_notification,
         name='send_test_notification'),

    # ===================== MESSAGING API =====================
    path('api/conversations/', include(message_urlpatterns)),

    # ===================== PROFILE API =====================
    path('api/profile/', views.api_profile, name='api_profile'),
    path('api/profile/edit/', views.api_edit_profile, name='edit-profile'),

    # Skills
    path('api/profile/skills/', views.api_skills, name='api_skills'),
    path('api/profile/skills/<int:skill_id>/', views.api_skills,
         name='api_skills_delete'),

    # Employment
    path('api/profile/employment/', views.api_employment, name='api_employment'),
    path('api/profile/employment/<int:employment_id>/',
         views.api_employment, name='api_employment_delete'),
    path('api/profile/employment/<int:employment_id>/update/',
         views.update_employment, name='update_employment'),

    # Education
    path('api/profile/education/', views.api_education, name='api_education'),
    path('api/profile/education/<int:education_id>/',
         views.api_education, name='api_education_delete'),
    path('api/profile/education/<int:education_id>/update/',
         views.update_education, name='update_education'),

    # Documents
    path('api/profile/documents/', views.api_documents, name='api_documents'),
    path('api/profile/documents/add/', views.api_add_document,
         name='api_add_document'),
    path('api/profile/documents/<int:document_id>/',
         views.api_documents, name='api_documents_delete'),
    path('api/profile/documents/<int:document_id>/detail/',
         views.api_document_detail, name='document-detail'),
    path('api/profile/documents/<int:document_id>/edit/',
         views.api_edit_document, name='edit-document'),

    # Business document access
    path('api/business/applications/documents/',
         views.api_business_applications_with_documents,
         name='business_applications_documents'),
    path('api/business/applications/<uuid:application_id>/documents/',
         views.api_business_applicant_documents,
         name='business_applicant_documents'),

    # ===================== AUTH API =====================
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/signup/', views.api_signup, name='api_signup'),
    path('api/auth/business-signup/', views.api_business_signup,
         name='business_signup'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),

    # ===================== PASSWORD RESET =====================
    path('forgot-password/',
         TemplateView.as_view(template_name='forgot_password.html'),
         name='forgot_password'),
    path('reset-password/',
         TemplateView.as_view(template_name='reset_password.html'),
         name='reset_password'),
    path('api/auth/password-reset/',
         views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('api/auth/password-reset-confirm/',
         views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),

    # ===================== JOBS & APPLICATIONS API =====================
    path('api/applications/', views.api_applications, name='api_applications'),
    path('api/jobs/', views.api_job_listings, name='api_job_listings'),
    path('api/jobs/<str:job_id>/', views.api_job_detail, name='api_job_detail'),
    path('api/jobs/<str:job_id>/apply/', views.api_apply_job,
         name='api_apply_job'),
    path('api/jobs/<int:job_id>/like-dislike/',
         views.api_job_like_dislike, name='api_job_like_dislike'),
    path('api/jobs/<int:job_id>/comments/',
         views.api_job_comments, name='api_job_comments'),

    # ===================== USER STATS =====================
    path('api/stats/users/', views.user_stats, name='user_stats'),

    # ===================== ADMIN PAGES =====================
    path('admin-portal/', views.admin_portal, name='admin_portal'),
    path('admin-portal/export/', views.export_data_page,
         name='export_data_page'),
    path('admin-portal/jobs/', views.admin_jobs_page, name='admin_jobs_page'),
    path('admin-portal/jobs/edit/', views.admin_job_edit_page,
         name='admin_job_edit_page'),
    path('admin-portal/users/', views.admin_users_page, name='admin_users_page'),
    path('admin-portal/applications/', views.admin_applications_page,
         name='admin_applications_page'),
    path('admin-portal/analytics/', views.admin_analytics_page,
         name='admin_analytics_page'),

    # ===================== ADMIN API =====================
    path('api/admin/stats/', views.api_admin_stats, name='api_admin_stats'),
    path('api/admin/activity/', views.api_recent_activity,
         name='api_recent_activity'),
    path('api/admin/dashboard-stats/', views.api_admin_dashboard_stats,
         name='api_admin_dashboard_stats'),
    path('api/admin/quick-stats/', views.api_admin_quick_stats,
         name='api_admin_quick_stats'),
    path('api/admin/system-health/', views.api_system_health,
         name='api_system_health'),
    path('api/admin/health-check/', views.api_simple_health_check,
         name='api_simple_health_check'),
    path('api/admin/database-stats/', views.api_database_stats,
         name='api_database_stats'),
    path('api/admin/generate-report/', views.api_generate_report,
         name='api_generate_report'),
    path('api/admin/quick-action/', views.api_admin_quick_action,
         name='api_admin_quick_action'),
    path('api/admin/export-simple/', views.api_export_simple,
         name='api_export_simple'),
    path('api/admin/test-export/', views.api_test_export,
         name='api_test_export'),

    # ===================== ADMIN JOB MANAGEMENT =====================
    path('api/admin/jobs/', views.api_admin_jobs, name='api_admin_jobs'),
    path('api/admin/jobs/save/', views.save_job, name='save_job'),
    path('api/admin/jobs/simple-list/', views.api_admin_jobs_simple_list,
         name='api_admin_jobs_simple_list'),
    path('api/admin/jobs/<uuid:job_id>/', views.api_admin_job_detail,
         name='api_admin_job_detail'),
    path('api/admin/jobs/<uuid:job_id>/status/', views.api_admin_job_status,
         name='api_admin_job_status'),
    path('api/admin/jobs/<uuid:job_id>/applications/',
         views.api_admin_job_applications,
         name='api_admin_job_applications'),
    path('api/admin/jobs/<uuid:job_id>/edit/', views.api_edit_job,
         name='api_edit_job'),
    path('api/admin/jobs/<int:job_id>/get/', views.get_job_data,
         name='get_job_data'),

    # ===================== ADMIN APPLICATIONS =====================
    path('api/admin/applications/list/', views.api_admin_applications_list,
         name='api_admin_applications_list'),
    path('api/admin/applications/stats/', views.api_admin_application_stats,
         name='api_admin_application_stats'),
    path('api/admin/applications/<uuid:application_id>/',
         views.api_admin_application_detail,
         name='api_admin_application_detail'),
    path('api/admin/applications/<uuid:application_id>/status/',
         views.api_admin_application_status,
         name='api_admin_application_status'),
    path('api/admin/applications/<uuid:application_id>/update-status/',
         views.api_admin_update_application_status,
         name='api_admin_update_application_status'),

    # ===================== ADMIN USERS =====================
    path('api/admin/users/list/', views.api_admin_users_list,
         name='api_admin_users_list'),
    path('api/admin/users/<int:user_id>/', views.api_admin_user_detail,
         name='api_admin_user_detail'),
    path('api/admin/users/<int:user_id>/update/', views.api_admin_update_user,
         name='api_admin_update_user'),
    path('api/admin/users/<int:user_id>/delete/', views.api_admin_delete_user,
         name='api_admin_delete_user'),

    # ===================== ADMIN ANALYTICS =====================
    path('api/admin/analytics/', views.api_admin_analytics,
         name='api_admin_analytics'),

    # ===================== ALERTS & NOTIFICATIONS =====================
    path('api/alerts/', views.api_alerts, name='api_user_alerts'),
    path('api/alerts/<str:alert_id>/read/', views.api_mark_alert_read,
         name='api_mark_alert_read'),
    path('api/alerts/<str:alert_id>/delete/', views.api_delete_alert,
         name='api_delete_alert'),
    path('api/preferences/', views.api_notification_preferences,
         name='api_preferences'),
    path('api/notifications/preferences/',
         views.api_notification_preferences,
         name='api_notification_preferences'),
    path('api/notifications/sent/', views.api_sent_notifications,
         name='api_sent_notifications'),

    # ===================== BUSINESS API =====================
    path('api/business-stats/', views.api_business_stats,
         name='api_business_stats'),
    path('api/business/dashboard-stats/', views.api_business_dashboard_stats,
         name='api_business_dashboard_stats'),
    path('api/business/jobs/', views.api_business_jobs, name='api_business_jobs'),
    path('api/business/applications/', views.api_business_applications,
         name='api_business_applications'),
    path('api/business-profile/', views.api_business_profile,
         name='business_profile'),
    path('api/business/profile/view/<int:business_id>/',
         views.api_record_business_profile_view,
         name='api_record_business_profile_view'),

    # ===================== LOOKUPS =====================
    path('api/industries/', views.api_industries, name='api_industries'),
    path('api/company-sizes/', views.api_company_sizes, name='api_company_sizes'),
    path('api/job-categories/', views.api_job_categories,
         name='api_job_categories'),

    # ===================== POSTS / FEED API =====================
    path('api/feed/', views.api_home_feed, name='api_home_feed'),
    path('api/posts/', views.api_posts, name='api_posts'),
    path('api/posts/feed/', views.api_feed_posts, name='api_feed_posts'),
    path('api/posts/stats/', views.api_post_stats, name='api_post_stats'),
    path('api/posts/user-stats/', views.api_user_post_stats,
         name='api_user_post_stats'),
    path('api/posts/<uuid:post_id>/', views.api_post_detail,
         name='api_post_detail'),
    path('api/posts/<int:post_id>/like-dislike/',
         views.api_post_like_dislike, name='api_post_like_dislike'),
    path('api/posts/<uuid:post_id>/share/', views.api_post_share,
         name='api_post_share'),
    path('api/posts/<uuid:post_id>/rate/', views.api_post_rating,
         name='api_post_rating'),
    path('api/post-comments/<int:post_id>/', views.api_post_comments,
         name='api_post_comments'),

    # ===================== USER MISC API =====================
    path('api/user/status/update/', views.update_user_status,
         name='update_user_status'),
    path('api/notifications/sound/preferences/get/',
         views.get_notification_sound_preferences,
         name='get_notification_sound_preferences'),
    path('api/sync-pending/', views.sync_pending_data, name='sync_pending_data'),
    path('api/test/', views.api_test, name='api_test'),

    # ===================== STATIC PAGES =====================
    path('about/', views.about_view, name='about'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('cookies/', views.cookies_view, name='cookies'),
    path('terms/', views.terms_view, name='terms'),
    path('help/', views.help_view, name='help'),
    path('help-center/', views.help_center, name='help_center'),

    # ===================== BLOG =====================
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('api/blog/create/', views.blog_create_api, name='blog_create_api'),
    path('api/blog/update/<int:post_id>/', views.blog_update_api,
         name='blog_update_api'),
    path('api/blog/delete/<int:post_id>/', views.blog_delete_api,
         name='blog_delete_api'),

    # ===================== CAREERS =====================
    path('careers/', views.career_list, name='careers'),
    path('api/career/create/', views.career_create_api,
         name='career_create_api'),
    path('api/career/update/<int:career_id>/', views.career_update_api,
         name='career_update_api'),
    path('api/career/delete/<int:career_id>/', views.career_delete_api,
         name='career_delete_api'),

    # ===================== FAQ =====================
    path('faq/', views.faq_list, name='faq'),
    path('api/faq/create/', views.faq_create_api, name='faq_create_api'),
    path('api/faq/update/<int:faq_id>/', views.faq_update_api,
         name='faq_update_api'),
    path('api/faq/delete/<int:faq_id>/', views.faq_delete_api,
         name='faq_delete_api'),

    # ===================== CONTACT =====================
    path('contact/', views.contact_view, name='contact'),
    path('contact/messages/', views.contact_messages_view,
         name='contact_messages'),
    path('api/contact/messages/<int:message_id>/read/',
         views.contact_message_mark_read_api,
         name='contact_message_mark_read'),

    # ===================== NEWSLETTER =====================
    path('api/newsletter/subscribe/', views.subscribe_newsletter,
         name='subscribe_newsletter'),
]