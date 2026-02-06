from django.contrib.auth import get_user_model
from rest_framework import serializers

from social_media.models import Profile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "password")
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


class ProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(many=False, read_only=True)

    class Meta:
        model = Profile
        fields = ("id", "user", "first_name", "last_name", "bio", "profile_picture")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if self.instance is None and Profile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {"user": "Profile already exists for this user."}
            )

        return attrs
