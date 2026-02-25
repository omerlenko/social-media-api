from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef
from django.db.models.aggregates import Count
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiRequest,
)
from rest_framework import viewsets, generics, status, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from social_media.models import Profile, Follow, Post, PostMedia, Like, Comment
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
    LikeSerializer,
    CommentSerializer,
    ProfileDetailSerializer,
)


@extend_schema_view(
    post=extend_schema(
        summary="Register user",
        request=UserSerializer,
        responses=UserSerializer,
        tags=["Auth"],
    ),
)
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)


@extend_schema_view(
    get=extend_schema(
        summary="Get own user details",
        description="Returns own user details.",
        responses=UserSerializer,
        tags=["Me"],
    ),
    patch=extend_schema(
        summary="Partially update your user details",
        request=UserUpdateSerializer,
        responses=UserUpdateSerializer,
        tags=["Me"],
    ),
    put=extend_schema(
        summary="Update your user details",
        request=UserUpdateSerializer,
        responses=UserUpdateSerializer,
        tags=["Me"],
    ),
)
class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


@extend_schema_view(
    list=extend_schema(
        summary="List users",
        description="Returns users with optional username search.",
        parameters=[
            OpenApiParameter(
                name="username",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Case-insensitive partial username search",
            ),
        ],
        responses=UserListSerializer(many=True),
        tags=["Users"],
    ),
    retrieve=extend_schema(
        summary="Get user details",
        description="Returns user profile and follow stats.",
        responses=UserDetailSerializer,
        tags=["Users"],
    ),
)
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

    @extend_schema(
        methods=["POST"],
        summary="Follow a user",
        description="Creates a follow relationship to the target user.",
        request=None,
        responses={
            201: OpenApiResponse(
                response=FollowDetailSerializer,
                examples=[
                    OpenApiExample(
                        "Follow user response (created)",
                        value={
                            "follower": "alice",
                            "followee": "bob",
                        },
                    )
                ],
            ),
            200: OpenApiResponse(
                response=FollowDetailSerializer,
                examples=[
                    OpenApiExample(
                        "Follow user response (already following)",
                        value={
                            "follower": "alice",
                            "followee": "bob",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Cannot follow yourself"),
        },
        tags=["Follows"],
    )
    @extend_schema(
        methods=["DELETE"],
        summary="Unfollow a user",
        description="Removes follow relationship to the target user.",
        request=None,
        responses={204: OpenApiResponse(description="Unfollowed")},
        tags=["Follows"],
    )
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

    @extend_schema(
        summary="List followers of a user",
        responses=UserListSerializer(many=True),
        tags=["Follows"],
    )
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

    @extend_schema(
        summary="List users followed by this user",
        responses=UserListSerializer(many=True),
        tags=["Follows"],
    )
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

    @extend_schema(
        summary="Log out current user",
        description="Blacklists the provided refresh token.",
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Invalid or expired token"),
            401: OpenApiResponse(
                description="Authentication credentials were not provided or invalid"
            ),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema_view(
    post=extend_schema(
        summary="Create own profile",
        request=ProfileSerializer,
        responses=ProfileSerializer,
        tags=["Profile"],
    ),
)
class CreateProfileView(generics.CreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        qs = Profile.objects.filter(user=self.request.user)
        if qs.exists():
            raise ValidationError({"user": "Profile already exists for this user."})
        serializer.save(user=self.request.user)


@extend_schema_view(
    get=extend_schema(
        summary="Get own profile details",
        description="Returns own profile details.",
        responses=ProfileDetailSerializer,
        tags=["Profile"],
    ),
    patch=extend_schema(
        summary="Partially update your profile details",
        request=ProfileSerializer,
        responses=ProfileSerializer,
        tags=["Profile"],
    ),
    put=extend_schema(
        summary="Update your profile details",
        request=ProfileSerializer,
        responses=ProfileSerializer,
        tags=["Profile"],
    ),
)
class ManageProfileView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProfileDetailSerializer
        return ProfileSerializer

    def get_object(self):
        try:
            profile = Profile.objects.get(user=self.request.user)
        except Profile.DoesNotExist:
            raise NotFound("The profile wasn't created for this user yet.")
        return profile


@extend_schema_view(
    list=extend_schema(
        summary="Feed posts",
        description=(
            "Returns published posts from the current user and users they follow. "
            "Can be filtered by comma-separated hashtags."
        ),
        parameters=[
            OpenApiParameter(
                name="hashtags",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Comma-separated hashtags, e.g. 'python,django'",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=PostReadSerializer(many=True),
                examples=[
                    OpenApiExample(
                        "Feed response",
                        value=[
                            {
                                "id": 105,
                                "author": "bob",
                                "text": "Today I added hashtag filtering to the posts feed.",
                                "media": [
                                    {
                                        "id": 14,
                                        "file": "http://127.0.0.1:8000/media/uploads/post_media/sample-feed-1.png",
                                    }
                                ],
                                "likes_count": 4,
                                "is_liked": True,
                                "comments_count": 2,
                                "hashtags": [
                                    {"id": 2, "text": "#django"},
                                    {"id": 4, "text": "#backend"},
                                ],
                                "published_at": "2026-02-25T11:40:00Z",
                            },
                            {
                                "id": 104,
                                "author": "alice",
                                "text": "Clean serializer validation beats debugging later.",
                                "media": [],
                                "likes_count": 1,
                                "is_liked": False,
                                "comments_count": 0,
                                "hashtags": [
                                    {"id": 1, "text": "#python"},
                                    {"id": 3, "text": "#api"},
                                ],
                                "published_at": "2026-02-25T10:15:00Z",
                            },
                        ],
                    )
                ],
            )
        },
        tags=["Posts"],
    ),
    retrieve=extend_schema(
        summary="Get post details",
        description="Returns post + media, likes and comments stats, hashtags.",
        responses=PostReadSerializer,
        tags=["Posts"],
    ),
    create=extend_schema(
        summary="Create a post",
        description="Creates a post immediately or schedules it if 'scheduled_for' is provided",
        request=OpenApiRequest(
            request=PostSerializer,
            examples=[
                OpenApiExample(
                    "Create post request (published immediately)",
                    summary="No scheduled_for provided",
                    value={
                        "text": "Just finished building my first DRF custom action. Feels great!",
                        "hashtags": [
                            {"text": "python"},
                            {"text": "#django"},
                            {"text": "api"},
                        ],
                    },
                ),
                OpenApiExample(
                    "Create post request (scheduled)",
                    summary="Scheduled post",
                    value={
                        "text": "Scheduled post example: this will be published later by Celery.",
                        "scheduled_for": "2026-03-01T10:30:00Z",
                        "hashtags": [
                            {"text": "backend"},
                            {"text": "webdev"},
                        ],
                    },
                ),
            ],
        ),
        responses={
            201: OpenApiResponse(
                response=PostSerializer,
                examples=[
                    OpenApiExample(
                        "Create post response (scheduled)",
                        value={
                            "id": 101,
                            "author": "alice",
                            "text": "Scheduled post example: this will be published later by Celery.",
                            "media": [],
                            "likes_count": 0,
                            "is_liked": False,
                            "comments_count": 0,
                            "hashtags": [
                                {"id": 4, "text": "backend"},
                                {"id": 5, "text": "webdev"},
                            ],
                            "status": "SCH",
                            "scheduled_for": "2026-03-01T10:30:00Z",
                            "created_at": "2026-02-25T12:00:00Z",
                            "published_at": None,
                        },
                    )
                ],
            )
        },
        tags=["Posts"],
    ),
    partial_update=extend_schema(
        summary="Partially update your post",
        tags=["Posts"],
    ),
    update=extend_schema(
        summary="Update your post",
        tags=["Posts"],
    ),
    destroy=extend_schema(
        summary="Delete your post",
        responses={204: OpenApiResponse(description="Deleted")},
        tags=["Posts"],
    ),
)
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

        # scoping
        user = self.request.user
        following = (
            get_user_model()
            .objects.filter(followers__follower=user)
            .values_list("id", flat=True)
        )
        authors_ids = [user.id] + list(following)
        queryset = queryset.filter(status=Post.Status.PUBLISHED).filter(
            author__id__in=authors_ids
        )

        # hashtag filtering
        hashtags = self.request.query_params.get("hashtags")

        if hashtags:
            tags = [
                tag.strip().lower().lstrip("#").replace(" ", "")
                for tag in hashtags.split(",")
            ]
            queryset = queryset.filter(hashtags__text__in=tags).distinct()

        # annotation
        if self.action in ("list", "retrieve", "liked"):
            like_exists = Like.objects.filter(user=user, post_id=OuterRef("pk"))

            queryset = (
                queryset.annotate(
                    likes_count=Count("likes", distinct=True),
                )
                .annotate(
                    comments_count=Count("comments", distinct=True),
                )
                .annotate(is_liked=Exists(like_exists))
            )

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PostReadSerializer
        if self.action == "like":
            return EmptySerializer

        return self.serializer_class

    @extend_schema(
        summary="Upload media to a post",
        description="Upload one or more image files to your own post.",
        request=PostMediaSerializer,
        responses={201: PostMediaSerializer(many=True)},
        tags=["Posts"],
    )
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

    @extend_schema(
        methods=["POST"],
        summary="Like a post",
        description="Creates a like relationship to the target post.",
        request=None,
        responses={
            201: LikeSerializer,
            200: LikeSerializer,  # already liked
        },
        tags=["Likes"],
    )
    @extend_schema(
        methods=["DELETE"],
        summary="Unlike a post",
        description="Removes like relationship to the target post.",
        request=None,
        responses={204: OpenApiResponse(description="Unliked")},
        tags=["Likes"],
    )
    @action(
        detail=True, methods=["POST", "DELETE"], permission_classes=(IsAuthenticated,)
    )
    def like(self, request, *args, **kwargs):
        post = self.get_object()

        if request.method == "POST":
            like, created = Like.objects.get_or_create(
                user=self.request.user, post=post
            )
            serializer = LikeSerializer(like)

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else HTTP_200_OK,
            )

        if request.method == "DELETE":
            Like.objects.filter(user=self.request.user, post=post).delete()
            return Response(status=HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="List posts liked by current user",
        description=(
            "Returns liked posts by this user. "
            "Can be filtered by comma-separated hashtags."
        ),
        parameters=[
            OpenApiParameter(
                name="hashtags",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Comma-separated hashtags, e.g. 'python,django'",
            ),
        ],
        responses=PostReadSerializer(many=True),
        tags=["Posts"],
    )
    @action(detail=False, methods=["GET"])
    def liked(self, request, *args, **kwargs):
        user = request.user

        liked_posts = self.get_queryset().filter(likes__user=user).distinct()
        serializer = PostReadSerializer(
            liked_posts, many=True, context={"request": request}
        )

        return Response(serializer.data, status=HTTP_200_OK)

    @extend_schema(
        methods=["GET"],
        summary="List comments for a post",
        responses=CommentSerializer(many=True),
        tags=["Comments"],
    )
    @extend_schema(
        methods=["POST"],
        summary="Create comment for a post",
        request=OpenApiRequest(
            request=CommentSerializer,
            examples=[
                OpenApiExample(
                    "Create comment request",
                    value={"text": "Nice post, the hashtag filtering works great."},
                )
            ],
        ),
        responses={
            201: OpenApiResponse(
                response=CommentSerializer,
                examples=[
                    OpenApiExample(
                        "Create comment response",
                        value={
                            "id": 12,
                            "author": 3,
                            "text": "Nice post, the hashtag filtering works great.",
                        },
                    )
                ],
            )
        },
        tags=["Comments"],
    )
    @action(
        detail=True,
        methods=["GET", "POST"],
        serializer_class=CommentSerializer,
        permission_classes=(IsAuthenticated,),
    )
    def comments(self, request, *args, **kwargs):
        post = self.get_object()
        if request.method == "GET":
            comments = (
                Comment.objects.select_related("author")
                .filter(post=post)
                .order_by("-created_at")
            )
            serializer = self.get_serializer(comments, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == "POST":
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(author=request.user, post=post)

            return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get comment details",
        responses=CommentSerializer,
        tags=["Comments"],
    ),
    partial_update=extend_schema(
        summary="Partially update your comment",
        request=CommentSerializer,
        responses=CommentSerializer,
        tags=["Comments"],
    ),
    update=extend_schema(
        summary="Update your comment",
        request=CommentSerializer,
        responses=CommentSerializer,
        tags=["Comments"],
    ),
    destroy=extend_schema(
        summary="Delete your comment",
        responses={204: OpenApiResponse(description="Deleted")},
        tags=["Comments"],
    ),
)
class CommentViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user

        following = (
            get_user_model()
            .objects.filter(followers__follower=user)
            .values_list("id", flat=True)
        )
        authors_ids = [user.id] + list(following)
        queryset = queryset.filter(post__author__id__in=authors_ids)

        return queryset
