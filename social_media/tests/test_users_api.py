from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from social_media.models import Follow
from social_media.serializers import UserListSerializer, UserDetailSerializer
from social_media.tests.utils import sample_user


class UsersApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@email.com",
            username="test_username",
            password="test_password",
        )
        self.client.force_authenticate(self.user)

    def test_users_list(self):
        sample_user()

        url = reverse("social_media:user-list")
        res = self.client.get(url)

        users = get_user_model().objects.all()
        serializer = UserListSerializer(users, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_users_retrieve(self):
        user = sample_user()

        url = reverse("social_media:user-detail", args=(user.id,))
        res = self.client.get(url)

        queryset = (
            get_user_model()
            .objects.filter(pk=user.id)
            .annotate(followers_count=Count("followers", distinct=True))
            .annotate(following_count=Count("following", distinct=True))
            .first()
        )
        serializer = UserDetailSerializer(queryset)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_follow_user(self):
        other_user = sample_user()
        follow_exists_before = Follow.objects.filter(
            follower=self.user, followee=other_user
        ).exists()

        url = reverse("social_media:user-detail", args=(other_user.id,)) + "follow/"
        res = self.client.post(url)

        follow_exists_after = Follow.objects.filter(
            follower=self.user, followee=other_user
        ).exists()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(follow_exists_before)
        self.assertTrue(follow_exists_after)

    def test_follow_user_is_idempotent(self):
        other_user = sample_user()
        Follow.objects.create(follower=self.user, followee=other_user)
        follow_count_before = Follow.objects.count()

        url = reverse("social_media:user-detail", args=(other_user.id,)) + "follow/"
        res = self.client.post(url)

        follow_count_after = Follow.objects.count()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(follow_count_before, follow_count_after)

    def test_unfollow_user(self):
        other_user = sample_user()
        Follow.objects.create(follower=self.user, followee=other_user)
        follow_exists_before = Follow.objects.filter(
            follower=self.user, followee=other_user
        ).exists()

        url = reverse("social_media:user-detail", args=(other_user.id,)) + "follow/"
        res = self.client.delete(url)

        follow_exists_after = Follow.objects.filter(
            follower=self.user, followee=other_user
        ).exists()

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(follow_exists_before)
        self.assertFalse(follow_exists_after)

    def test_cant_follow_self(self):
        url = reverse("social_media:user-detail", args=(self.user.id,)) + "follow/"
        res = self.client.post(url)

        follow_exists = Follow.objects.filter(
            follower=self.user, followee=self.user
        ).exists()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(follow_exists)

    def test_list_following(self):
        other_user = sample_user()
        Follow.objects.create(follower=self.user, followee=other_user)

        url = reverse("social_media:user-detail", args=(self.user.id,)) + "following/"
        res = self.client.get(url)

        following = get_user_model().objects.filter(followers__follower=self.user)
        serializer = UserListSerializer(following, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)

    def test_list_followers(self):
        other_user = sample_user()
        Follow.objects.create(follower=other_user, followee=self.user)

        url = reverse("social_media:user-detail", args=(self.user.id,)) + "followers/"
        res = self.client.get(url)

        followers = get_user_model().objects.filter(following__followee=self.user)
        serializer = UserListSerializer(followers, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], serializer.data)
