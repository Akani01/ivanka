# hiring/management/commands/create_static_pages.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from hiring.models import StaticPage

CustomUser = get_user_model()

class Command(BaseCommand):
    help = 'Create initial static pages'

    def handle(self, *args, **options):
        # Get or create a superuser to set as updated_by
        admin_user = CustomUser.objects.filter(is_superuser=True).first()
        
        pages = [
            {
                'page_type': 'privacy',
                'title': 'Privacy Policy',
                'content': '<h1>Privacy Policy</h1><p>Your privacy is important to us. OppoGlobe is committed to protecting your personal information.</p>',
                'meta_description': 'Learn how OppoGlobe protects your privacy and handles your personal information.',
                'meta_keywords': 'privacy, policy, data protection, oppoglobe',
                'sections': [
                    {'title': '1. Information We Collect', 'content': 'OppoGlobe collects information you provide directly, such as when you create an account, list a property, or contact us. This may include your name, email address, phone number, and property details.'},
                    {'title': '2. How We Use Your Information', 'content': 'We use your information to provide, maintain, and improve our services, to process transactions, to communicate with you, and to personalize your experience on OppoGlobe.'},
                    {'title': '3. Information Sharing', 'content': 'We do not sell your personal information. We may share your information with service providers who assist us in operating our platform, or as required by law.'},
                    {'title': '4. Your Rights', 'content': 'You have the right to access, correct, or delete your personal information. You may also opt out of marketing communications at any time.'},
                    {'title': '5. Contact Us', 'content': 'If you have questions about this Privacy Policy, please contact us at privacy@oppoglobe.com.'},
                ]
            },
            {
                'page_type': 'terms',
                'title': 'Terms of Service',
                'content': '<h1>Terms of Service</h1><p>Welcome to OppoGlobe. By using our platform, you agree to these terms.</p>',
                'meta_description': 'Read the terms and conditions for using OppoGlobe platform.',
                'meta_keywords': 'terms, conditions, legal, oppoglobe',
                'sections': [
                    {'title': '1. Acceptance of Terms', 'content': 'By using OppoGlobe, you agree to these Terms of Service. If you do not agree, please do not use our platform.'},
                    {'title': '2. User Accounts', 'content': 'You are responsible for maintaining the security of your account. You must provide accurate information when creating an account.'},
                    {'title': '3. Property Listings', 'content': 'Users who list properties must provide accurate information and have the right to list the property. OppoGlobe reserves the right to remove listings that violate our policies.'},
                    {'title': '4. Prohibited Conduct', 'content': 'You may not use OppoGlobe for illegal activities, to harass others, or to post false or misleading information.'},
                    {'title': '5. Disclaimer', 'content': 'OppoGlobe provides the platform "as is" without warranties of any kind. We are not responsible for the accuracy of property listings or transactions between users.'},
                    {'title': '6. Contact', 'content': 'For questions about these terms, please contact us at support@oppoglobe.com.'},
                ]
            },
            {
                'page_type': 'cookies',
                'title': 'Cookies Policy',
                'content': '<h1>Cookies Policy</h1><p>We use cookies to improve your experience on OppoGlobe.</p>',
                'meta_description': 'Learn how OppoGlobe uses cookies to improve your browsing experience.',
                'meta_keywords': 'cookies, policy, tracking, privacy',
                'sections': [
                    {'title': 'What Are Cookies?', 'content': 'Cookies are small text files that are stored on your device when you visit a website. They help us provide you with a better experience by remembering your preferences and understanding how you use our site.'},
                    {'title': 'How We Use Cookies', 'content': 'We use cookies to keep you signed in to your account, remember your preferences and settings, understand how you interact with our platform, and improve our services.'},
                    {'title': 'Types of Cookies We Use', 'content': '<strong>Essential Cookies:</strong> Required for the platform to function properly.<br><strong>Preference Cookies:</strong> Remember your settings and preferences.<br><strong>Analytics Cookies:</strong> Help us understand how users interact with OppoGlobe.'},
                    {'title': 'Managing Cookies', 'content': 'You can control and manage cookies in your browser settings. However, disabling certain cookies may affect your experience on OppoGlobe.'},
                    {'title': 'Contact Us', 'content': 'If you have questions about our use of cookies, please contact us at privacy@oppoglobe.com.'},
                ]
            },
            {
                'page_type': 'help',
                'title': 'Help Center',
                'content': '<h1>Help Center</h1><p>Welcome to the OppoGlobe Help Center. Find answers to common questions below.</p>',
                'meta_description': 'Find answers to common questions, guides, and support for OppoGlobe.',
                'meta_keywords': 'help, support, FAQ, guides',
                'sections': []
            },
            {
                'page_type': 'about',
                'title': 'About Us',
                'content': '<h1>About OppoGlobe</h1><p>Your trusted platform for finding dream properties, connecting with owners, and accessing educational resources.</p>',
                'meta_description': 'Learn about OppoGlobe - your trusted real estate platform.',
                'meta_keywords': 'about, oppoglobe, company, real estate',
                'sections': []
            },
            {
                'page_type': 'contact',
                'title': 'Contact Us',
                'content': '<h1>Contact Us</h1><p>Get in touch with our support team. We\'re here to help!</p>',
                'meta_description': 'Contact OppoGlobe support team for assistance.',
                'meta_keywords': 'contact, support, help',
                'sections': []
            },
        ]
        
        for page_data in pages:
            obj, created = StaticPage.objects.get_or_create(
                page_type=page_data['page_type'],
                defaults=page_data
            )
            if created:
                if admin_user:
                    obj.updated_by = admin_user
                    obj.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Created: {page_data["title"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Already exists: {page_data["title"]}'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 All static pages have been created!'))