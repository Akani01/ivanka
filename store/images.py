"""Re-encode all uploads, strip metadata, normalize orientation and use one canvas."""

from io import BytesIO
import uuid, warnings
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework.exceptions import ValidationError


def normalize_product_image(upload):
    if upload.size > 10 * 1024 * 1024:
        raise ValidationError("Images must be 10 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(upload)
            if im.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Unsupported format")
            if im.width * im.height > 25000000:
                raise ValueError("Maximum 25 megapixels")
            im = ImageOps.exif_transpose(im).convert("RGBA")
            im.load()
        if settings.PRODUCT_REMOVE_BACKGROUND:
            try:
                from rembg import remove

                im = remove(im)
            except Exception as exc:
                raise ValidationError(
                    "Background removal failed. Check the installed rembg model."
                ) from exc
        elif im.getchannel("A").getextrema()[0] == 255:
            raise ValidationError(
                "Upload a transparent PNG/WebP product cutout for the uniform background. "
                "Ordinary photos require automatic background removal to be enabled."
            )
        im.thumbnail((1040, 1040), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (1200, 1200), "#f4f4f2")
        canvas.paste(im, ((1200 - im.width) // 2, (1200 - im.height) // 2), im)
        out = BytesIO()
        canvas.save(out, "WEBP", quality=88, method=4)
        result = ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.webp")
        result._ivanka_normalized = True
        return result
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "Upload a valid JPG, PNG or WebP image (maximum 25 megapixels)."
        ) from exc
