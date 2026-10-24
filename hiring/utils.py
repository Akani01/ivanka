from .models import ApplicantProfile

def calculate_profile_completeness(profile):
    """
    Calculate profile completeness percentage
    """
    total_fields = 0
    completed_fields = 0
    
    # Basic info fields
    basic_fields = ['title', 'gender', 'first_name', 'last_name', 'ethnicity', 
                   'is_citizen', 'birth_date', 'current_home_location']
    
    for field in basic_fields:
        total_fields += 1
        value = getattr(profile, field)
        if value and str(value).strip():
            completed_fields += 1
    
    # Boolean fields
    bool_fields = ['has_drivers_license', 'has_own_transport', 'willing_to_relocate']
    for field in bool_fields:
        total_fields += 1
        if getattr(profile, field) is not None:
            completed_fields += 1
    
    # Job preference fields
    job_fields = ['preferred_job_title', 'availability', 'current_salary', 'desired_salary']
    for field in job_fields:
        total_fields += 1
        value = getattr(profile, field)
        if value and str(value).strip():
            completed_fields += 1
    
    # Introduction field
    total_fields += 1
    if profile.introduction and profile.introduction.strip():
        completed_fields += 1
    
    # Calculate percentage
    if total_fields == 0:
        return 0
    
    return int((completed_fields / total_fields) * 100)


def validate_file_size(file, max_size_mb=5):
    """
    Validate file size
    """
    max_size = max_size_mb * 1024 * 1024  # Convert to bytes
    if file.size > max_size:
        return False
    return True

def get_file_extension(filename):
    """
    Get file extension from filename
    """
    return filename.split('.')[-1].lower() if '.' in filename else ''

def generate_application_reference(application):
    """
    Generate a human-readable application reference
    """
    return f"APP-{application.id.hex[:8].upper()}"