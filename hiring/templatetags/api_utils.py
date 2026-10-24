from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def api_js_functions():
    """Returns all API JavaScript functions as a single script tag."""
    js_code = """
    <script>
    // CSRF Cookie Helper
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Universal API request function
    async function apiRequest(endpoint, method = 'GET', data = null) {
        const csrfToken = getCookie('csrftoken');
        const url = '/api' + endpoint;
        
        const options = {
            method: method,
            credentials: 'include',
            headers: { 'X-CSRFToken': csrfToken }
        };
        
        if (data && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            return await response.text();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // All your API endpoints as easy-to-use functions
    window.api = {
        // Profile
        profile: {
            get: () => apiRequest('/profile/', 'GET'),
            update: (data) => apiRequest('/profile/', 'POST', data)
        },
        
        // Alerts
        alerts: {
            list: () => apiRequest('/alerts/', 'GET'),
            markRead: (id) => apiRequest(`/alerts/${id}/read/`, 'POST'),
            delete: (id) => apiRequest(`/alerts/${id}/delete/`, 'DELETE')
        },
        
        // Applications
        applications: {
            list: () => apiRequest('/applications/', 'GET'),
            apply: (jobId, data) => apiRequest(`/jobs/${jobId}/apply/`, 'POST', data)
        },
        
        // Jobs
        jobs: {
            list: () => apiRequest('/jobs/', 'GET'),
            detail: (jobId) => apiRequest(`/jobs/${jobId}/`, 'GET')
        },
        
        // Documents
        documents: {
            list: () => apiRequest('/profile/documents/', 'GET'),
            upload: (data) => apiRequest('/profile/documents/', 'POST', data)
        },
        
        // Skills, Employment, Education
        skills: {
            list: () => apiRequest('/profile/skills/', 'GET'),
            add: (data) => apiRequest('/profile/skills/', 'POST', data),
            delete: (id) => apiRequest(`/profile/skills/${id}/`, 'DELETE')
        },
        
        employment: {
            list: () => apiRequest('/profile/employment/', 'GET'),
            add: (data) => apiRequest('/profile/employment/', 'POST', data)
        },
        
        education: {
            list: () => apiRequest('/profile/education/', 'GET'),
            add: (data) => apiRequest('/profile/education/', 'POST', data)
        },
        
        // Messaging
        messaging: {
            conversations: () => apiRequest('/conversations/', 'GET'),
            sendMessage: (conversationId, data) => apiRequest(`/conversations/${conversationId}/messages/`, 'POST', data)
        },
        
        // Preferences
        preferences: {
            get: () => apiRequest('/preferences/', 'GET'),
            update: (data) => apiRequest('/preferences/', 'POST', data)
        },
        
        // Feed/Posts
        feed: {
            get: () => apiRequest('/feed/', 'GET'),
            like: (postId) => apiRequest(`/posts/${postId}/like-dislike/`, 'POST')
        }
    };
    
    // Also expose the raw apiRequest for custom calls
    window.apiRequest = apiRequest;
    </script>
    """
    return mark_safe(js_code)