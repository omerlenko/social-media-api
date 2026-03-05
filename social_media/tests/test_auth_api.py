from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from social_media.models import Follow, Comment
from social_media.serializers import UserSerializer
from social_media.tests.utils import make_test_image, sample_post, sample_user


class UnauthenticatedUserApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_can_register_user(self):
        payload = {
            "email": "test@email.com",
            "username": "test_username",
            "password": "test_password",
        }
        res = self.client.post(reverse("social_media:create_user"), payload)
        user = get_user_model().objects.get(username=payload["username"])
        serializer = UserSerializer(user)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data, serializer.data)
        self.assertTrue(user.check_password(payload["password"]))

    def test_can_obtain_token(self):
        payload = {
            "email": "test@email.com",
            "password": "test_password",
        }
        get_user_model().objects.create_user(
            email=payload["email"],
            username="test_username",
            password=payload["password"],
        )

        res = self.client.post(reverse("social_media:token_obtain_pair"), payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_cant_access_users(self):
        res = self.client.get(reverse("social_media:user-list"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cant_access_posts(self):
        res = self.client.get(reverse("social_media:post-list"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedUserApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@email.com",
            username="test_username",
            password="test_password",
        )
        self.client.force_authenticate(self.user)

    def test_can_access_users(self):
        res = self.client.get(reverse("social_media:user-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_can_access_posts(self):
        res = self.client.get(reverse("social_media:post-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_can_update_own_post(self):
        post = sample_post(author=self.user)
        payload = {"text": "Updated post text."}
        url = reverse(f"social_media:post-detail", args=(post.id,))

        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["text"], payload["text"])

    def test_cant_update_other_users_post(self):
        other_user = sample_user()
        Follow.objects.create(follower=self.user, followee=other_user)
        post = sample_post(author=other_user)

        payload = {"text": "Updated post text."}
        url = reverse(f"social_media:post-detail", args=(post.id,))

        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_delete_own_comment(self):
        post = sample_post(author=self.user)
        comment = Comment.objects.create(
            author=self.user, text="Test comment.", post=post
        )

        url = reverse(f"social_media:comment-detail", args=(comment.id,))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_cant_delete_other_users_comment(self):
        other_user = sample_user()
        post = sample_post(author=self.user)
        comment = Comment.objects.create(
            author=other_user, text="Other user comment.", post=post
        )

        url = reverse(f"social_media:comment-detail", args=(comment.id,))
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_cant_upload_media_to_other_users_post(self):
        other_user = sample_user()
        post = sample_post(author=other_user)
        Follow.objects.create(follower=self.user, followee=other_user)

        image_1 = make_test_image()
        image_2 = make_test_image(name="test2.png")

        payload = {"file": [image_1, image_2]}

        url = reverse(f"social_media:post-detail", args=(post.id,)) + "media/"
        res = self.client.post(url, payload, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
