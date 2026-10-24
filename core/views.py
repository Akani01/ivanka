# core/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .ai_service import ai_service
from realestate.models import Property
from hiring.models import JobListing, ApplicantProfile
from realestate.models import MaintenanceRequest
import logging

logger = logging.getLogger(__name__)

# ==========================================
# REAL ESTATE AI VIEWS
# ==========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_analyze_property(request, property_id):
    """AI analysis of a property"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_active=True)
        
        # Check permission
        if property_obj.owner != request.user and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
        
        analysis = ai_service.analyze_property(property_obj)
        
        return Response({
            'success': True,
            'property_id': str(property_obj.id),
            'property_title': property_obj.title,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"AI property analysis error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_search_properties(request):
    """AI-powered property search"""
    query = request.data.get('query', '').strip()
    
    if not query:
        return Response({
            'success': False,
            'error': 'Search query is required'
        }, status=400)
    
    # Get properties (filter by user's properties if business user)
    if request.user.user_type == 'admin':
        properties = Property.objects.filter(
            company__user=request.user,
            is_active=True
        )
    else:
        properties = Property.objects.filter(is_active=True)
    
    results = ai_service.search_properties_ai(query, properties)
    
    return Response({
        'success': True,
        'query': query,
        'results': results
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_compare_properties(request):
    """Compare multiple properties with AI"""
    property_ids = request.data.get('property_ids', [])
    
    if len(property_ids) < 2:
        return Response({
            'success': False,
            'error': 'Please provide at least 2 property IDs to compare'
        }, status=400)
    
    comparison = ai_service.compare_properties(property_ids)
    
    return Response({
        'success': True,
        'property_ids': property_ids,
        'comparison': comparison
    })

# ==========================================
# JOBS AI VIEWS
# ==========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_analyze_job(request, job_id):
    """AI analysis of a job listing"""
    try:
        job_obj = get_object_or_404(JobListing, id=job_id)
        
        analysis = ai_service.analyze_job(job_obj)
        
        return Response({
            'success': True,
            'job_id': str(job_obj.id),
            'job_title': job_obj.title,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"AI job analysis error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_match_candidate(request, job_id, applicant_id):
    """Match a candidate to a job with AI"""
    try:
        job_obj = get_object_or_404(JobListing, id=job_id)
        applicant = get_object_or_404(ApplicantProfile, id=applicant_id)
        
        match_result = ai_service.match_candidate_to_job(job_obj, applicant)
        
        return Response({
            'success': True,
            'job_id': str(job_obj.id),
            'job_title': job_obj.title,
            'applicant_id': str(applicant.id),
            'applicant_name': f"{applicant.first_name} {applicant.last_name}",
            'match': match_result
        })
        
    except Exception as e:
        logger.error(f"AI candidate matching error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_search_jobs(request):
    """AI-powered job search"""
    query = request.data.get('query', '').strip()
    
    if not query:
        return Response({
            'success': False,
            'error': 'Search query is required'
        }, status=400)
    
    jobs = JobListing.objects.filter(status='published')
    results = ai_service.search_jobs_ai(query, jobs)
    
    return Response({
        'success': True,
        'query': query,
        'results': results
    })

# ==========================================
# MAINTENANCE AI VIEWS
# ==========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_analyze_maintenance(request, maintenance_id):
    """AI analysis of a maintenance request"""
    try:
        maintenance_obj = get_object_or_404(MaintenanceRequest, id=maintenance_id)
        
        # Check permission
        if maintenance_obj.tenant != request.user and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
        
        analysis = ai_service.analyze_maintenance(maintenance_obj)
        
        return Response({
            'success': True,
            'maintenance_id': str(maintenance_obj.id),
            'title': maintenance_obj.title,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"AI maintenance analysis error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_maintenance_patterns(request, property_id):
    """AI analysis of maintenance patterns for a property"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_active=True)
        
        # Check permission
        if property_obj.owner != request.user and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
        
        patterns = ai_service.analyze_maintenance_patterns(property_obj)
        
        return Response({
            'success': True,
            'property_id': str(property_obj.id),
            'property_title': property_obj.title,
            'patterns': patterns
        })
        
    except Exception as e:
        logger.error(f"AI maintenance patterns error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# ==========================================
# GENERAL AI VIEWS
# ==========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat(request):
    """General AI chat assistant"""
    query = request.data.get('query', '').strip()
    
    if not query:
        return Response({
            'success': False,
            'error': 'Query is required'
        }, status=400)
    
    # Build context from user data
    context = {
        'user_type': request.user.user_type,
        'username': request.user.username,
    }
    
    response = ai_service.chat_assistant(query, context)
    
    return Response({
        'success': True,
        'query': query,
        'response': response
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_smart_search(request):
    """AI-powered smart search across all modules"""
    query = request.data.get('query', '').strip()
    search_type = request.data.get('search_type', 'all')
    
    if not query:
        return Response({
            'success': False,
            'error': 'Search query is required'
        }, status=400)
    
    # Pass request context for maintenance filtering
    context = request
    
    results = ai_service.smart_search(query, search_type, context)
    
    return Response({
        'success': True,
        'query': query,
        'search_type': search_type,
        'results': results
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_status(request):
    """Check AI service status"""
    return Response({
        'api_key_configured': bool(settings.DEEPSEEK_API_KEY),
        'api_key_preview': settings.DEEPSEEK_API_KEY[:10] + '...' if settings.DEEPSEEK_API_KEY else 'Not set',
        'model': settings.DEEPSEEK_MODEL,
        'timeout': settings.DEEPSEEK_TIMEOUT,
        'status': 'Ready' if settings.DEEPSEEK_API_KEY else 'Missing API Key'
    })