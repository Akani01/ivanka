# utils/helpers.py
from rest_framework.response import Response
from rest_framework import status
from connections.models import Connection
import re
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Constants
ALLOWED_POST_TYPES = ['all', 'general', 'job', 'update', 'news', 'question']
ALLOWED_SORT_OPTIONS = ['newest', 'popular', 'top']
ALLOWED_VISIBILITY = ['public', 'connections', 'group', 'private']

def error_response(message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """Standardized error response"""
    response_data = {
        'success': False,
        'error': message
    }
    if details:
        response_data['details'] = details
    return Response(response_data, status=status_code)

def success_response(message, data=None, status_code=status.HTTP_200_OK):
    """Standardized success response"""
    response_data = {
        'success': True,
        'message': message
    }
    if data:
        response_data.update(data)
    return Response(response_data, status_code=status_code)

def get_paginated_data(queryset, page, page_size, serializer_class, context=None):
    """Helper for pagination"""
    total_count = queryset.count()
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
    
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    paginated_items = queryset[start_index:end_index]
    
    if context:
        serializer = serializer_class(paginated_items, many=True, context=context)
    else:
        serializer = serializer_class(paginated_items, many=True)
    
    return {
        'data': serializer.data,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_items': total_count,
            'page_size': page_size,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
    }

def get_user_visibility_filters(user):
    """Get filters for posts based on user visibility settings"""
    filters = Q(is_published=True)
    
    if user.is_authenticated:
        try:
            # Get user's connections based on your models
            from connections.models import Connection
            connections = Connection.objects.filter(
                Q(from_user=user, status='accepted') |
                Q(to_user=user, status='accepted')
            )
            
            connection_ids = set()
            for conn in connections:
                if conn.from_user != user:
                    connection_ids.add(conn.from_user.id)
                if conn.to_user != user:
                    connection_ids.add(conn.to_user.id)
            
            # Get user's groups
            user_groups = user.groups.values_list('id', flat=True)
            
            # Complex Q object for visibility
            visibility_filter = (
                Q(visibility='public') |
                Q(visibility='connections', author_id__in=connection_ids) |
                Q(visibility='group', author__groups__id__in=user_groups) |
                Q(visibility='private', author=user) |
                Q(author=user)  # User can always see their own posts
            )
            
            filters &= visibility_filter
        except ImportError:
            # If connections app doesn't exist, use simpler filters
            filters &= (Q(visibility='public') | Q(author=user))
    else:
        # Anonymous users can only see public posts
        filters &= Q(visibility='public')
    
    return filters

def generate_safe_title(content, max_length=60):
    """Generate a safe title from content"""
    if not content:
        return "Untitled Post"
    
    # Remove HTML tags and extra whitespace
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = ' '.join(clean_content.split())
    
    # Take first few words (limit by max_length)
    if len(clean_content) <= max_length:
        return clean_content
    
    # Find a good breaking point
    truncated = clean_content[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        return truncated[:last_space] + '...'
    return truncated + '...'

def can_user_view_post(post, user):
    """Check if user can view a specific post"""
    if not post.is_published:
        return False
    
    if user.is_authenticated and user == post.author:
        return True
    
    if post.visibility == 'public':
        return True
    
    if not user.is_authenticated:
        return False
    
    if post.visibility == 'private':
        return user == post.author
    
    if post.visibility == 'connections':
        try:
            from connections.models import Connection
            return Connection.objects.filter(
                Q(from_user=user, to_user=post.author, status='accepted') |
                Q(from_user=post.author, to_user=user, status='accepted')
            ).exists()
        except ImportError:
            return False
    
    if post.visibility == 'group':
        user_groups = user.groups.values_list('id', flat=True)
        author_groups = post.author.groups.values_list('id', flat=True)
        return bool(set(user_groups) & set(author_groups))
    
    return False  