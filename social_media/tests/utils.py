from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from social_media.models import Post, User


def make_test_image(name="test.png", size=(50, 50)):
    buf = BytesIO()
    Image.new("RGB", size).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def sample_post(author: User, **params):
    defaults = {
        "text": "Test text.",
        "author": author,
        "status": Post.Status.PUBLISHED,
        "published_at": timezone.now(),
    }

    if "scheduled_for" in params and "scheduled_for" is not None:
        defaults.update(status=Post.Status.SCHEDULED, published_at=None)
    defaults.update(params)

    return Post.objects.create(**defaults)


def sample_user(**params):
    defaults = {
        "email": "sample_user@email.com",
        "username": "sample_user",
        "password": "sample_password",
    }

    defaults.update(params)

    return get_user_model().objects.create_user(**defaults)
