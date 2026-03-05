from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from social_media.views import (
    ManageUserView,
    ManageProfileView,
    CreateUserView,
    CreateProfileView,
    LogoutView,
    UserViewSet,
    PostViewSet,
    CommentViewSet,
)

router = routers.DefaultRouter()
router.register("users", UserViewSet)
router.register("posts", PostViewSet)
router.register("comments", CommentViewSet)
urlpatterns = [
    path("auth/register/", CreateUserView.as_view(), name="create_user"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="token_logout"),
    path("users/me/", ManageUserView.as_view(), name="manage_user"),
    path("profiles/create/", CreateProfileView.as_view(), name="create_profile"),
    path("profiles/me/", ManageProfileView.as_view(), name="manage_profile"),
    path("", include(router.urls)),
]

app_name = "social_media"
