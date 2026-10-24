from django import template

register = template.Library()

@register.filter
def has_admin_access(user):
    if not user.is_authenticated:
        return False
    return user.user_type == 'admin' or user.is_superuser

@register.filter
def has_business_access(user):
    return user.is_authenticated and user.user_type == 'admin'