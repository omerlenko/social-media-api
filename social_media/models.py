import os
import uuid
from django.utils import timezone

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, F
from rest_framework.exceptions import ValidationError


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.username} ({self.email})"


def upload_profile_pictures(instance, filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return f"uploads/profile_pictures/{uuid.uuid4()}{ext.lower()}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    bio = models.TextField(blank=True, max_length=1000)
    profile_picture = models.ImageField(
        null=True, blank=True, upload_to=upload_profile_pictures
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "followee"], name="unique_follow"
            ),
            models.CheckConstraint(
                condition=~Q(follower=F("followee")), name="no_self_follow"
            ),
        ]

    def __str__(self):
        return f"Follower: {self.follower}, Followee: {self.followee}"


class Hashtag(models.Model):
    text = models.CharField(unique=True, max_length=50)

    def __str__(self):
        return "#" + self.text


class Post(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCH", "Scheduled"
        PUBLISHED = "PUB", "Published"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    text = models.TextField(max_length=1000)
    hashtags = models.ManyToManyField(Hashtag, related_name="posts", blank=True)
    status = models.CharField(
        max_length=3, choices=Status.choices, default=Status.PUBLISHED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.status == self.Status.SCHEDULED:
            if self.scheduled_for is None:
                raise ValidationError("Post must have scheduled_for to be scheduled.")
            if self.scheduled_for <= timezone.now():
                raise ValidationError("Scheduled time must be in the future.")
            if self.published_at is not None:
                raise ValidationError(
                    "Post can't have published_at when it's scheduled."
                )

        elif self.status == self.Status.PUBLISHED:
            if self.published_at is None:
                raise ValidationError("Post must have published_at to be published.")
            if self.scheduled_for is not None:
                raise ValidationError(
                    "Post can't have scheduled_for when it's published."
                )
            if self.published_at > timezone.now():
                raise ValidationError("The published_at field cannot be in the future.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


def upload_post_media(instance, filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return f"uploads/post_media/{uuid.uuid4()}{ext.lower()}"


class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    file = models.ImageField(upload_to=upload_post_media)


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_like")
        ]

    def __str__(self):
        return f"{self.post.id} liked by {self.user.username}"


class Comment(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"comment: {self.text}"
