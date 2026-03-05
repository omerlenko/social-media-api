from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_media.models import Hashtag, Post, Follow, Like, Comment, PostMedia
from social_media.serializers import HashtagSerializer
from social_media.tests.utils import make_test_image, sample_post, sample_user


class PostsApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@email.com",
            username="test_username",
            password="test_password",
        )
        self.client.force_authenticate(self.user)

    def test_create_post_with_hashtags(self):
        payload = {
            "text": "Test text.",
            "hashtags": [
                {"text": "test"},
                {"text": "post"},
                {"text": "hashtag"},
            ],
        }

        url = reverse("social_media:post-list")
        res = self.client.post(url, payload, format="json")
        hashtags_serializer = HashtagSerializer(Hashtag.objects.all(), many=True)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["text"], payload["text"])
        self.assertEqual(res.data["hashtags"], hashtags_serializer.data)

    def test_created_hashtags_are_normalized(self):
        payload = {
            "text": "Test text.",
            "hashtags": [
                {"text": "#Django"},
                {"text": "django"},
                {"text": "Django"},
            ],
        }

        url = reverse("social_media:post-list")
        res = self.client.post(url, payload, format="json")
        hashtags_serializer = HashtagSerializer(Hashtag.objects.all(), many=True)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(hashtags_serializer.data), 1)
        self.assertEqual(hashtags_serializer.data[0]["text"], "django")

    def test_create_scheduled_post(self):
        payload = {
            "text": "Test text.",
            "scheduled_for": timezone.now() + timedelta(minutes=60),
        }

        url = reverse("social_media:post-list")
        res = self.client.post(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], Post.Status.SCHEDULED)
        self.assertEqual(res.data["published_at"], None)

    def test_create_non_scheduled_post(self):
        payload = {"text": "Test text.", "scheduled_for": None}

        url = reverse("social_media:post-list")
        res = self.client.post(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], Post.Status.PUBLISHED)
        self.assertTrue(res.data["published_at"])

    def test_feed_scoping(self):
        followed_user = sample_user()
        unfollowed_user = sample_user(
            email="sample_user_2@email.com",
            username="sample_user_2",
        )
        Follow.objects.create(follower=self.user, followee=followed_user)

        my_post = sample_post(author=self.user)
        scheduled_post = sample_post(
            author=self.user, scheduled_for=timezone.now() + timedelta(minutes=60)
        )
        followed_user_post = sample_post(author=followed_user)
        unfollowed_user_post = sample_post(author=unfollowed_user)

        url = reverse("social_media:post-list")
        res = self.client.get(url)

        returned_ids = {post["id"] for post in res.data["results"]}

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(my_post.id, returned_ids)
        self.assertIn(followed_user_post.id, returned_ids)
        self.assertNotIn(scheduled_post.id, returned_ids)
        self.assertNotIn(unfollowed_user_post.id, returned_ids)

    def test_posts_hashtags_filter(self):
        post_python_tag = sample_post(author=self.user)
        post_django_tag = sample_post(author=self.user)
        post_celery_tag = sample_post(author=self.user)

        python_tag = Hashtag.objects.create(text="python")
        django_tag = Hashtag.objects.create(text="django")
        celery_tag = Hashtag.objects.create(text="celery")

        post_python_tag.hashtags.add(python_tag)
        post_django_tag.hashtags.add(django_tag)
        post_celery_tag.hashtags.add(celery_tag)

        url = reverse("social_media:post-list")
        res = self.client.get(
            url, data={"hashtags": f"{python_tag.text}, {django_tag.text}"}
        )

        returned_ids = {post["id"] for post in res.data["results"]}

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(post_python_tag.id, returned_ids)
        self.assertIn(post_django_tag.id, returned_ids)
        self.assertNotIn(post_celery_tag.id, returned_ids)

    def test_like_post(self):
        post = sample_post(author=self.user)
        like_exists_before = Like.objects.filter(user=self.user, post=post).exists()

        url = reverse("social_media:post-detail", args=(post.id,)) + "like/"
        res = self.client.post(url)

        like_exists_after = Like.objects.filter(user=self.user, post=post).exists()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(like_exists_before)
        self.assertTrue(like_exists_after)

    def test_like_post_is_idempotent(self):
        post = sample_post(author=self.user)
        Like.objects.create(user=self.user, post=post)
        likes_count_before = Like.objects.count()

        url = reverse("social_media:post-detail", args=(post.id,)) + "like/"
        res = self.client.post(url)

        likes_count_after = Like.objects.count()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(likes_count_before, likes_count_after)

    def test_delete_like(self):
        post = sample_post(author=self.user)
        Like.objects.create(user=self.user, post=post)
        like_exists_before = Like.objects.filter(user=self.user, post=post).exists()

        url = reverse("social_media:post-detail", args=(post.id,)) + "like/"
        res = self.client.delete(url)

        like_exists_after = Like.objects.filter(user=self.user, post=post).exists()

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(like_exists_before)
        self.assertFalse(like_exists_after)

    def test_liked_returns_correct_posts(self):
        liked_post = sample_post(author=self.user)
        non_liked_post = sample_post(author=self.user)
        Like.objects.create(user=self.user, post=liked_post)

        url = reverse("social_media:post-list") + "liked/"
        res = self.client.get(url)

        returned_ids = {post["id"] for post in res.data["results"]}

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(liked_post.id, returned_ids)
        self.assertNotIn(non_liked_post.id, returned_ids)

    def test_likes_count(self):
        post = sample_post(author=self.user)
        likes_count_before = Like.objects.filter(post=post).count()

        url = reverse("social_media:post-detail", args=(post.id,)) + "like/"
        self.client.post(url)

        url = reverse("social_media:post-detail", args=(post.id,))
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(likes_count_before, 0)
        self.assertEqual(res.data["likes_count"], 1)

    def test_create_comment(self):
        post = sample_post(author=self.user)
        payload = {"text": "Test comment."}

        url = reverse("social_media:post-detail", args=(post.id,)) + "comments/"
        res = self.client.post(url, payload)

        comment_exists = Comment.objects.filter(id=res.data["id"]).exists()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["text"], payload["text"])
        self.assertTrue(comment_exists)

    def test_list_correct_comments(self):
        post = sample_post(author=self.user)
        other_post = sample_post(author=self.user)

        comment_1 = Comment.objects.create(
            author=self.user, post=post, text="Test comment 1"
        )
        comment_2 = Comment.objects.create(
            author=self.user, post=post, text="Test comment 2"
        )
        comment_3 = Comment.objects.create(
            author=self.user, post=other_post, text="Test comment 3"
        )

        url = reverse("social_media:post-detail", args=(post.id,)) + "comments/"
        res = self.client.get(url)

        returned_ids = {comment["id"] for comment in res.data["results"]}

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(comment_1.id, returned_ids)
        self.assertIn(comment_2.id, returned_ids)
        self.assertNotIn(comment_3.id, returned_ids)

    def test_update_own_comment(self):
        post = sample_post(author=self.user)
        comment = Comment.objects.create(
            author=self.user, post=post, text="Test comment"
        )

        payload = {"text": "Updated test comment"}

        url = reverse("social_media:comment-detail", args=(comment.id,))
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["text"], payload["text"])

    def test_cant_update_other_users_comment(self):
        post = sample_post(author=self.user)
        other_user = sample_user()

        comment = Comment.objects.create(
            author=other_user, post=post, text="Test comment"
        )

        payload = {"text": "Updated test comment"}

        url = reverse("social_media:comment-detail", args=(comment.id,))
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_cant_retrieve_comment_on_inaccessible_post(self):
        other_user = sample_user()
        post = sample_post(author=other_user)

        comment = Comment.objects.create(
            author=other_user, post=post, text="Test comment"
        )

        url = reverse("social_media:comment-detail", args=(comment.id,))
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_image_to_own_post(self):
        post = sample_post(author=self.user)
        image = make_test_image()

        payload = {"file": [image]}

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_upload_multiple_images_to_own_post(self):
        post = sample_post(author=self.user)
        image_1 = make_test_image()
        image_2 = make_test_image(name="test_image_2.png")

        payload = {"file": [image_1, image_2]}

        images_count_before = PostMedia.objects.count()

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        images_count_after = PostMedia.objects.count()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(images_count_before, 0)
        self.assertEqual(images_count_after, 2)

    def test_no_files_uploaded(self):
        post = sample_post(author=self.user)

        payload = {"file": []}

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_more_than_max_number_of_files(self):
        post = sample_post(author=self.user)

        image_list = []
        for i in range(11):
            image_list.append(make_test_image(name=f"test_image_{i}.png"))

        payload = {"file": image_list}

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cant_upload_image_to_other_users_post(self):
        other_user = sample_user()
        post = sample_post(author=other_user)
        Follow.objects.create(follower=self.user, followee=other_user)
        image = make_test_image()

        payload = {"file": [image]}

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
