from django.core.management.base import BaseCommand
from hiring.models import Industry, CompanySize, JobCategory

class Command(BaseCommand):
    help = 'Load default industries, company sizes, and job categories for business accounts'
    
    def handle(self, *args, **options):
        # Default Industries - EXPANDED
        industries_data = [
            ('Technology', 'Technology and IT services'),
            ('Healthcare', 'Healthcare and medical services'),
            ('Finance', 'Banking, finance, and insurance'),
            ('Education', 'Education and training'),
            ('Manufacturing', 'Manufacturing and production'),
            ('Retail', 'Retail and consumer goods'),
            ('Hospitality', 'Hospitality and tourism'),
            ('Construction', 'Construction and engineering'),
            ('Transportation', 'Transportation and logistics'),
            ('Marketing', 'Marketing and advertising'),
            ('Real Estate', 'Real estate and property'),
            ('Energy', 'Energy and utilities'),
            ('Agriculture', 'Agriculture and farming'),
            ('Entertainment', 'Entertainment and media'),
            ('Non-Profit', 'Non-profit and social services'),
            ('Security', 'Security and protection services'),
            ('Cleaning', 'Cleaning and sanitation services'),
            ('Group of Companies', 'Conglomerate and holding companies'),
            ('Legal', 'Legal services and law firms'),
            ('Consulting', 'Business consulting and advisory'),
            ('Government', 'Government and public sector'),
            ('Telecommunications', 'Telecom and communication services'),
            ('Automotive', 'Automotive industry and services'),
            ('Pharmaceutical', 'Pharmaceutical and medical research'),
            ('Beauty & Wellness', 'Beauty, spa, and wellness services'),
            ('Sports & Fitness', 'Sports, fitness, and recreation'),
            ('Art & Design', 'Creative arts and design services'),
            ('Science & Research', 'Scientific research and development'),
            ('Environmental', 'Environmental services and sustainability'),
            ('Food & Beverage', 'Food production and beverage services'),
        ]
        
        industries_dict = {}
        for name, description in industries_data:
            industry, created = Industry.objects.get_or_create(
                name=name, 
                defaults={'description': description}
            )
            industries_dict[name] = industry
            if created:
                self.stdout.write(f"Created industry: {name}")
        
        # Default Company Sizes
        company_sizes_data = [
            ('1-10', '1-10 employees', 1, 10),
            ('11-50', '11-50 employees', 11, 50),
            ('51-200', '51-200 employees', 51, 200),
            ('201-500', '201-500 employees', 201, 500),
            ('501-1000', '501-1000 employees', 501, 1000),
            ('1000+', '1000+ employees', 1001, None),
        ]
        
        for size_range, description, min_emp, max_emp in company_sizes_data:
            size, created = CompanySize.objects.get_or_create(
                size_range=size_range, 
                defaults={
                    'description': description,
                    'min_employees': min_emp,
                    'max_employees': max_emp
                }
            )
            if created:
                self.stdout.write(f"Created company size: {size_range}")
        
        # COMPREHENSIVE Job Categories - EXPANDED
        job_categories_data = {
            'Technology': [
                'Software Development', 'Web Development', 'Mobile Development', 'Data Science',
                'DevOps', 'IT Support', 'Cybersecurity', 'Network Administration',
                'Database Administration', 'UI/UX Design', 'Cloud Computing', 'AI/Machine Learning',
                'Blockchain Development', 'Game Development', 'QA Testing', 'System Administration',
                'Technical Support', 'IT Project Management', 'Software Architecture', 'ERP Implementation'
            ],
            'Healthcare': [
                'Nursing', 'Medical Doctor', 'Pharmacist', 'Medical Technician',
                'Healthcare Administration', 'Physical Therapy', 'Mental Health',
                'Dental Care', 'Emergency Services', 'Medical Research', 'Phlebotomy',
                'Radiology', 'Surgery', 'Pediatrics', 'Geriatrics', 'Oncology',
                'Cardiology', 'Neurology', 'Medical Coding', 'Healthcare IT'
            ],
            'Finance': [
                'Accounting', 'Financial Analysis', 'Investment Banking', 'Auditing',
                'Tax Services', 'Risk Management', 'Financial Planning', 'Insurance',
                'Wealth Management', 'Corporate Finance', 'Treasury', 'Compliance',
                'Fintech', 'Payroll', 'Bookkeeping', 'Financial Consulting', 'Actuarial',
                'Credit Analysis', 'Mergers & Acquisitions', 'Hedge Fund Management'
            ],
            'Education': [
                'Teaching', 'Academic Administration', 'Curriculum Development',
                'Student Services', 'Educational Technology', 'Research', 'Tutoring',
                'School Counseling', 'Special Education', 'Early Childhood Education',
                'Higher Education', 'Vocational Training', 'Education Policy',
                'Librarian', 'Instructional Design', 'Test Preparation', 'Education Consulting'
            ],
            'Manufacturing': [
                'Production Management', 'Quality Control', 'Supply Chain',
                'Industrial Engineering', 'Maintenance', 'Assembly', 'Logistics',
                'Process Engineering', 'Manufacturing Engineering', 'Plant Management',
                'Safety Management', 'Inventory Control', 'Lean Manufacturing',
                'CNC Operation', 'Welding', 'Fabrication', 'Packaging', 'Materials Management'
            ],
            'Retail': [
                'Store Management', 'Sales Associate', 'Customer Service',
                'Merchandising', 'Inventory Management', 'Retail Marketing',
                'Visual Merchandising', 'Buying', 'Loss Prevention', 'E-commerce',
                'Retail Operations', 'Category Management', 'Store Design',
                'Retail Analytics', 'Brand Management', 'Retail Training'
            ],
            'Hospitality': [
                'Hotel Management', 'Food Service', 'Event Planning',
                'Tourism', 'Customer Service', 'Culinary Arts',
                'Restaurant Management', 'Catering', 'Front Desk', 'Housekeeping',
                'Concierge', 'Spa Services', 'Travel Agency', 'Tour Guide',
                'Resort Management', 'Banquet Management', 'Hospitality Marketing'
            ],
            'Construction': [
                'Civil Engineering', 'Architecture', 'Project Management',
                'Skilled Trades', 'Construction Management', 'Safety Officer',
                'Site Supervision', 'Quantity Surveying', 'Structural Engineering',
                'Electrical Installation', 'Plumbing', 'Carpentry', 'Masonry',
                'HVAC', 'Landscaping', 'Urban Planning', 'Building Inspection'
            ],
            'Marketing': [
                'Digital Marketing', 'Content Creation', 'Social Media',
                'Brand Management', 'Market Research', 'Advertising',
                'SEO/SEM', 'Email Marketing', 'Public Relations', 'Product Marketing',
                'Marketing Analytics', 'Influencer Marketing', 'Event Marketing',
                'Content Strategy', 'Marketing Automation', 'Growth Hacking'
            ],
            'Security': [
                'Security Guard', 'Security Management', 'Cybersecurity',
                'Surveillance', 'Access Control', 'Security Consulting',
                'Loss Prevention', 'Executive Protection', 'Security Systems',
                'Risk Assessment', 'Security Training', 'Alarm Monitoring',
                'Corporate Security', 'Physical Security', 'Information Security',
                'Security Analysis', 'CCTV Operation', 'Security Patrol'
            ],
            'Cleaning': [
                'Commercial Cleaning', 'Residential Cleaning', 'Janitorial Services',
                'Carpet Cleaning', 'Window Cleaning', 'Sanitation Services',
                'Disinfection Services', 'Housekeeping', 'Industrial Cleaning',
                'Office Cleaning', 'Post-Construction Cleaning', 'Specialized Cleaning',
                'Cleaning Supervision', 'Waste Management', 'Environmental Cleaning',
                'Cleaning Equipment Operation', 'Cleaning Training'
            ],
            'Group of Companies': [
                'Group CEO', 'Group Director', 'Corporate Strategy',
                'Portfolio Management', 'Group Finance', 'Corporate Development',
                'Shared Services', 'Group HR', 'Group Marketing', 'Group Operations',
                'Business Unit Management', 'Corporate Governance', 'Group IT',
                'Group Legal', 'Group Procurement', 'Group Risk Management',
                'Group Compliance', 'Corporate Communications', 'Group Tax'
            ],
            'Legal': [
                'Corporate Law', 'Litigation', 'Intellectual Property',
                'Real Estate Law', 'Family Law', 'Criminal Law',
                'Immigration Law', 'Employment Law', 'Contract Law',
                'Legal Research', 'Paralegal', 'Legal Secretary',
                'Compliance Officer', 'Notary Public', 'Mediation',
                'Legal Consulting', 'Law Clerk', 'Legal Administration'
            ],
            'Consulting': [
                'Management Consulting', 'IT Consulting', 'Strategy Consulting',
                'HR Consulting', 'Financial Consulting', 'Marketing Consulting',
                'Operations Consulting', 'Change Management', 'Business Analysis',
                'Process Improvement', 'Organizational Development',
                'Project Management Consulting', 'Risk Consulting', 'Sustainability Consulting'
            ],
            'Government': [
                'Public Administration', 'Policy Analysis', 'Urban Planning',
                'Social Services', 'Law Enforcement', 'Diplomatic Services',
                'Public Health', 'Education Administration', 'Transportation Planning',
                'Environmental Protection', 'Tax Administration', 'Customs & Border',
                'Legislative Affairs', 'Public Works', 'Community Development'
            ],
            'Telecommunications': [
                'Network Engineering', 'Telecom Sales', 'Customer Support',
                'Fiber Optics', 'Wireless Technology', 'Telecom Infrastructure',
                'VoIP Services', 'Mobile Networks', 'Satellite Communications',
                'Telecom Project Management', 'Network Operations', 'Telecom Regulation'
            ],
            'Automotive': [
                'Automotive Engineering', 'Mechanic', 'Auto Sales',
                'Parts Management', 'Service Advisor', 'Auto Body Repair',
                'Quality Control', 'Manufacturing', 'Automotive Design',
                'Fleet Management', 'Automotive Electronics', 'Aftermarket Sales'
            ],
            'Pharmaceutical': [
                'Pharmaceutical Research', 'Clinical Trials', 'Regulatory Affairs',
                'Drug Development', 'Quality Assurance', 'Medical Writing',
                'Pharmacovigilance', 'Manufacturing', 'Sales Representative',
                'Medical Science Liaison', 'Formulation Development', 'Biotechnology'
            ],
            'Beauty & Wellness': [
                'Hair Stylist', 'Esthetician', 'Massage Therapist',
                'Spa Manager', 'Makeup Artist', 'Nail Technician',
                'Wellness Coach', 'Beauty Advisor', 'Salon Manager',
                'Cosmetology', 'Skin Care Specialist', 'Beauty Product Development'
            ],
            'Sports & Fitness': [
                'Personal Trainer', 'Fitness Instructor', 'Sports Coach',
                'Gym Manager', 'Athletic Director', 'Sports Marketing',
                'Physical Education', 'Sports Medicine', 'Recreation Coordinator',
                'Team Management', 'Fitness Nutrition', 'Sports Analytics'
            ],
            'Art & Design': [
                'Graphic Design', 'Interior Design', 'Fashion Design',
                'Industrial Design', 'Animation', 'Photography',
                'Video Production', 'Architectural Design', 'Web Design',
                'Creative Direction', 'Art Direction', 'User Experience Design'
            ],
            'Science & Research': [
                'Research Scientist', 'Laboratory Technician', 'Data Analyst',
                'Clinical Research', 'Biotechnology', 'Environmental Science',
                'Materials Science', 'Physics Research', 'Chemistry Research',
                'Biology Research', 'Scientific Writing', 'Research Management'
            ],
            'Environmental': [
                'Environmental Engineering', 'Sustainability Management',
                'Conservation', 'Waste Management', 'Renewable Energy',
                'Environmental Consulting', 'Climate Change Analysis',
                'Water Resources', 'Environmental Health', 'Ecology',
                'Environmental Policy', 'Green Building'
            ],
            'Food & Beverage': [
                'Chef', 'Restaurant Management', 'Food Production',
                'Beverage Management', 'Food Safety', 'Culinary Arts',
                'Nutrition', 'Food Science', 'Bakery', 'Butchery',
                'Food Quality Control', 'Menu Development'
            ],
            'Real Estate': [
                'Real Estate Agent', 'Property Management', 'Real Estate Development',
                'Commercial Real Estate', 'Residential Sales', 'Real Estate Appraisal',
                'Mortgage Broker', 'Real Estate Marketing', 'Property Valuation',
                'Facilities Management', 'Real Estate Investment', 'Leasing Agent'
            ],
            'Energy': [
                'Electrical Engineering', 'Renewable Energy', 'Oil & Gas',
                'Power Plant Operations', 'Energy Management', 'Solar Installation',
                'Wind Energy', 'Energy Consulting', 'Utility Management',
                'Energy Efficiency', 'Petroleum Engineering', 'Nuclear Energy'
            ],
            'Agriculture': [
                'Farm Management', 'Agricultural Engineering', 'Crop Science',
                'Livestock Management', 'Agricultural Economics', 'Horticulture',
                'Agribusiness', 'Soil Science', 'Irrigation Management',
                'Agricultural Research', 'Food Processing', 'Supply Chain Management'
            ],
            'Entertainment': [
                'Film Production', 'Music Production', 'Event Management',
                'Talent Management', 'Broadcasting', 'Content Creation',
                'Stage Management', 'Lighting Design', 'Sound Engineering',
                'Script Writing', 'Film Direction', 'Entertainment Marketing'
            ],
            'Non-Profit': [
                'Program Management', 'Fundraising', 'Grant Writing',
                'Volunteer Coordination', 'Community Outreach', 'Advocacy',
                'Non-Profit Management', 'Social Work', 'Development Director',
                'Campaign Management', 'Donor Relations', 'Social Impact'
            ]
        }
        
        categories_created = 0
        for industry_name, categories in job_categories_data.items():
            industry = industries_dict.get(industry_name)
            if industry:
                for category_name in categories:
                    try:
                        # Try to get existing category
                        category = JobCategory.objects.get(name=category_name, industry=industry)
                        self.stdout.write(f"Job category already exists: {category_name} in {industry_name}")
                    except JobCategory.DoesNotExist:
                        # Create new category if it doesn't exist
                        category = JobCategory.objects.create(
                            name=category_name,
                            industry=industry,
                            description=f'{category_name} in {industry_name}'
                        )
                        categories_created += 1
                        self.stdout.write(f"Created job category: {category_name} in {industry_name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully loaded: {len(industries_data)} industries, '
                f'{len(company_sizes_data)} company sizes, '
                f'{categories_created} job categories'
            )
        )