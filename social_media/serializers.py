from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from social_media.models import Profile, Follow


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
