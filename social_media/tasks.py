from celery import shared_task
from django.utils import timezone
from social_media.models import Post


@shared_task
def add(x, y):
    return x + y


@shared_task
def publish_scheduled_posts():
    now = timezone.now()

    updated = Post.objects.filter(
        status=Post.Status.SCHEDULED, scheduled_for__lte=now
    ).update(status=Post.Status.PUBLISHED, published_at=now, scheduled_for=None)

    return updated
