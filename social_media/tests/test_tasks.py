from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from social_media.models import Post
from social_media.tasks import publish_scheduled_posts
from social_media.tests.utils import sample_post


class ScheduledPostsTaskTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@email.com",
            username="test_username",
            password="test_password",
        )
        self.client.force_authenticate(self.user)

    def test_due_scheduled_post_becomes_published(self):
        scheduled_post = sample_post(
            author=self.user, scheduled_for=timezone.now() + timedelta(hours=1)
        )

        Post.objects.filter(id=scheduled_post.id).update(
            scheduled_for=timezone.now() - timedelta(seconds=1)
        )

        post_status_before = Post.objects.get(id=scheduled_post.id).status
        publish_scheduled_posts()
        post_status_after = Post.objects.get(id=scheduled_post.id).status

        self.assertEqual(post_status_before, Post.Status.SCHEDULED)
        self.assertEqual(post_status_after, Post.Status.PUBLISHED)

    def test_future_scheduled_post_stays_scheduled(self):
        scheduled_post = sample_post(
            author=self.user, scheduled_for=timezone.now() + timedelta(hours=1)
        )

        publish_scheduled_posts()
        post_status = Post.objects.get(id=scheduled_post.id).status

        self.assertEqual(post_status, Post.Status.SCHEDULED)

    def test_task_clears_scheduled_for_and_sets_published_at(self):
        scheduled_post = sample_post(
            author=self.user, scheduled_for=timezone.now() + timedelta(hours=1)
        )

        Post.objects.filter(id=scheduled_post.id).update(
            scheduled_for=timezone.now() - timedelta(seconds=1)
        )

        publish_scheduled_posts()

        post = Post.objects.get(id=scheduled_post.id)

        self.assertEqual(post.scheduled_for, None)
        self.assertTrue(post.published_at)
