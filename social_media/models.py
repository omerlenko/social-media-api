import os
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.username} ({self.email})"


def create_custom_path(instance, filename: str) -> str:
    root, extension = os.path.splitext(filename)
    return os.path.join(
        "uploads/profile_pictures/",
        f"{slugify(instance.user.username)}-{uuid.uuid4()}{extension}",
    )


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    bio = models.TextField(blank=True, max_length=1000)
    profile_picture = models.ImageField(
        null=True, blank=True, upload_to=create_custom_path
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name
