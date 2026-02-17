from django.contrib.auth import get_user_model
from django.db.models.aggregates import Count
from rest_framework import viewsets, generics, status, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED
from rest_framework.views import APIView

from social_media.models import Profile, Follow, Post, PostMedia, Hashtag
from social_media.permissions import IsOwnerOrReadOnly
from social_media.serializers import (
    UserSerializer,
    ProfileSerializer,
    UserUpdateSerializer,
    LogoutSerializer,
    UserListSerializer,
    UserDetailSerializer,
    FollowDetailSerializer,
    EmptySerializer,
    PostSerializer,
    PostMediaSerializer,
    PostReadSerializer,
)


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)


class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = get_user_model().objects.select_related(
        "profile",
    )
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == "list":
            return UserListSerializer
        if self.action == "retrieve":
            return UserDetailSerializer
        if self.action == "follow":
            return EmptySerializer
        return UserListSerializer

    def get_queryset(self):
        queryset = self.queryset

        if self.action == "list":
            username = self.request.query_params.get("username")

            if username:
                queryset = queryset.filter(username__icontains=username)

        if self.action == "retrieve":
            queryset = queryset.annotate(
                followers_count=Count("followers", distinct=True)
            ).annotate(following_count=Count("following", distinct=True))

        return queryset.distinct()

    @action(detail=True, methods=["POST", "DELETE"])
    def follow(self, request, *args, **kwargs):
        user = self.get_object()

        if request.method == "POST":
            if request.user == user:
                raise ValidationError({"detail": "You can not follow yourself."})

            follow, created = Follow.objects.get_or_create(
                follower=request.user, followee=user
            )
            serializer = FollowDetailSerializer(follow, context={"request": request})

            return Response(
                serializer.data,
                status=HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        if request.method == "DELETE":
            Follow.objects.filter(follower=request.user, followee=user).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["GET"])
    def followers(self, request, *args, **kwargs):
        user = self.get_object()
        followers = (
            get_user_model()
            .objects.select_related("profile")
            .filter(following__followee=user)
            .distinct()
        )
        serializer = UserListSerializer(
            followers, many=True, context={"request": request}
        )
        return Response(serializer.data, status=HTTP_200_OK)

    @action(detail=True, methods=["GET"])
    def following(self, request, *args, **kwargs):
        user = self.get_object()
        following = (
            get_user_model()
            .objects.select_related("profile")
            .filter(followers__follower=user)
            .distinct()
        )
        serializer = UserListSerializer(
            following, many=True, context={"request": request}
        )
        return Response(serializer.data, status=HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class CreateProfileView(generics.CreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        qs = Profile.objects.filter(user=self.request.user)
        if qs.exists():
            raise ValidationError({"user": "Profile already exists for this user."})
        serializer.save(user=self.request.user)


class ManageProfileView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        try:
            profile = Profile.objects.get(user=self.request.user)
        except Profile.DoesNotExist:
            raise NotFound("The profile wasn't created for this user yet.")
        return profile


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.select_related("author").prefetch_related(
        "media", "hashtags"
    )
    serializer_class = PostSerializer
    permission_classes = (
        IsAuthenticated,
        IsOwnerOrReadOnly,
    )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        queryset = self.queryset

        user = self.request.user
        following = (
            get_user_model()
            .objects.filter(followers__follower=user)
            .values_list("id", flat=True)
        )
        authors_ids = [user.id] + list(following)
        queryset = queryset.filter(author__id__in=authors_ids)

        hashtags = self.request.query_params.get("hashtags")

        if hashtags:
            tags = [
                tag.strip().lower().lstrip("#").replace(" ", "")
                for tag in hashtags.split(",")
            ]
            queryset = queryset.filter(hashtags__text__in=tags).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PostReadSerializer

        return self.serializer_class

    @action(detail=True, methods=["POST"], serializer_class=PostMediaSerializer)
    def media(self, request, *args, **kwargs):
        post = self.get_object()

        files_list = request.FILES.getlist("file")
        if not files_list:
            raise ValidationError({"file": "No files were provided."})
        if len(files_list) > 10:
            raise ValidationError(
                {"detail": "You can only attach up to 10 files to a post."}
            )

        created_objects = []
        for file in files_list:
            obj = PostMedia.objects.create(post=post, file=file)
            created_objects.append(obj)

        serializer = PostMediaSerializer(
            created_objects, many=True, context={"request": request}
        )
        return Response(serializer.data, status=HTTP_201_CREATED)
