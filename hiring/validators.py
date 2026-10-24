from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import os

def validate_file_size(value):
    """
    Validate that uploaded file size doesn't exceed 300MB
    """
    filesize = value.size
    if filesize > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(
            _('File size cannot exceed 300MB. Your file is %(size)sMB.'),
            params={'size': round(filesize / (1024*1024), 2)},
        )

def validate_video_file_extension(value):
    """
    Validate video file extensions
    """
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported file extension.'))

def validate_image_file_extension(value):
    """
    Validate image file extensions
    """
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported image format.'))