from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateImportStorage(FileSystemStorage):
    """Keep uploaded source workbooks outside public media/static directories."""

    def __init__(self):
        super().__init__(location=settings.BASE_DIR / 'private_imports', base_url=None)

    def url(self, name):
        raise ValueError('Import source files are private and do not have public URLs.')
