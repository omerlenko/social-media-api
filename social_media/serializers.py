from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from social_media.models import Profile, Follow, Post, PostMedia, Hashtag, Like, Comment


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "email", "username", "password")
        extra_kwargs = {
            "password": {
                "write_only": True,
                "min_length": 5,
                "style": {"input_type": "password"},
                "label": "Password",
            }
        }

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()
        return user


class UserUpdateSerializer(UserSerializer):
    email = serializers.EmailField(read_only=True)


class EmptySerializer(serializers.Serializer):
    pass


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError("Request context is required.")
        return attrs

    def save(self, **kwargs):
        refresh_token = self.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)

            request = self.context["request"]
            if int(token.get("user_id")) != request.user.id:
                raise serializers.ValidationError(
                    {"refresh": "Token does not belong to this user."}
                )

            token.blacklist()

        except TokenError:
            raise serializers.ValidationError({"refresh": "Invalid or expired token."})


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("id", "user", "first_name", "last_name", "bio", "profile_picture")
        read_only_fields = ("user",)


class ProfileDetailSerializer(ProfileSerializer):
    class Meta:
        model = Profile
        fields = ("id", "first_name", "last_name", "bio", "profile_picture")


class UserListSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "profile_picture")

    def get_profile_picture(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile:
            return None

        profile_picture = profile.profile_picture
        if not profile_picture:
            return None

        request = self.context.get("request")
        url = profile_picture.url
        return request.build_absolute_uri(url) if request else url


class UserDetailSerializer(serializers.ModelSerializer):
    profile = ProfileDetailSerializer(many=False, read_only=True)
    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    is_following = serializers.SerializerMethodField(read_only=True)
    is_followed_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "profile",
            "followers_count",
            "following_count",
            "is_following",
            "is_followed_by",
        )

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request is None:
            return False

        return Follow.objects.filter(follower=request.user, followee=obj).exists()

    def get_is_followed_by(self, obj):
        request = self.context.get("request")
        if request is None:
            return False

        return Follow.objects.filter(follower=obj, followee=request.user).exists()


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ("follower", "followee")
        read_only_fields = ("follower", "followee")


class FollowDetailSerializer(FollowSerializer):
    follower = serializers.SlugRelatedField(
        read_only=True, many=False, slug_field="username"
    )
    followee = serializers.SlugRelatedField(
        read_only=True, many=False, slug_field="username"
    )


class PostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostMedia
        fields = ("id", "file")


class HashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ("id", "text")
        extra_kwargs = {"text": {"validators": []}}

    def validate_text(self, text):
        text = text.strip().lower().lstrip("#").replace(" ", "")
        if text == "":
            raise serializers.ValidationError("Hashtag text cannot be empty.")
        return text


class HashtagListSerializer(HashtagSerializer):
    text = serializers.SerializerMethodField(read_only=True)

    def get_text(self, obj):
        return "#" + obj.text


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        read_only=True, many=False, slug_field="username"
    )

    class Meta:
        model = Comment
        fields = ("id", "author", "post", "text", "created_at")
        read_only_fields = ("author", "post", "created_at")


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        read_only=True, many=False, slug_field="username"
    )
    media = PostMediaSerializer(many=True, read_only=True)
    hashtags = HashtagSerializer(many=True, required=False)
    likes_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "text",
            "created_at",
            "media",
            "likes_count",
            "is_liked",
            "comments_count",
            "hashtags",
        )
        read_only_fields = (
            "author",
            "created_at",
            "likes_count",
            "is_liked",
            "comments_count",
        )

    def _resolve_tags(self, hashtags_data):
        seen = set()
        tags = []

        for hashtag in hashtags_data:
            text = hashtag["text"]
            if text in seen:
                continue
            seen.add(text)

            tag, _ = Hashtag.objects.get_or_create(text=text)
            tags.append(tag)

        return tags

    def create(self, validated_data):
        with transaction.atomic():
            hashtags_data = validated_data.pop("hashtags", [])
            post = Post.objects.create(**validated_data)

            tags = self._resolve_tags(hashtags_data)
            post.hashtags.set(tags)

            return post

    def update(self, instance, validated_data):
        hashtags_data = validated_data.pop("hashtags", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if hashtags_data is not None:
                tags = self._resolve_tags(hashtags_data)
                instance.hashtags.set(tags)

        return instance


class PostReadSerializer(PostSerializer):
    hashtags = HashtagListSerializer(many=True, read_only=True)


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ("id", "user", "post")
        read_only_fields = ("user", "post")
