from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

class MediaStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=os.path.join(settings.BASE_DIR, 'mediafiles'),
            base_url='/mediafiles/'
        )

class StaticStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=os.path.join(settings.BASE_DIR, 'staticfiles'),
            base_url='/static/'
        )