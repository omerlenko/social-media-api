from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from social_media.models import Profile, Follow, Post, Hashtag, Like, Comment, PostMedia

DEMO_USERS = [
    (
        "alice@example.com",
        "alice",
        "SecurePass123",
        "Alice",
        "Johnson",
        "Backend developer learning DRF.",
    ),
    (
        "bob@example.com",
        "bob",
        "SecurePass123",
        "Bob",
        "Lee",
        "I like building APIs and working with data.",
    ),
    (
        "charlie@example.com",
        "charlie",
        "SecurePass123",
        "Charlie",
        "Kim",
        "Interested in system design and Celery.",
    ),
]


class Command(BaseCommand):
    help = "Seed demo data: users, profiles, follows, posts, hashtags, likes, comments (and optional media)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data (only demo users with @example.com) before seeding.",
        )
        parser.add_argument(
            "--with-media",
            action="store_true",
            help="Generate a couple of tiny demo images for PostMedia (requires Pillow).",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        with_media = options["with_media"]

        user = get_user_model()

        if reset:
            self._reset_demo(user)

        with transaction.atomic():
            users = self._create_users_and_profiles(user)
            hashtags = self._create_hashtags()
            posts = self._create_posts(users, hashtags)
            self._create_follows(users)
            self._create_likes(users, posts)
            self._create_comments(users, posts)

            if with_media:
                self._create_media(posts)

        self.stdout.write(self.style.SUCCESS("✅ Demo data seeded successfully."))
        self.stdout.write(
            "Users created: "
            + ", ".join(
                [
                    u.username
                    for u in user.objects.filter(email__endswith="@example.com")
                ]
            )
        )

    def _reset_demo(self, user):
        demo_user_qs = user.objects.filter(email__endswith="@example.com")
        demo_user_ids = list(demo_user_qs.values_list("id", flat=True))

        Like.objects.filter(user_id__in=demo_user_ids).delete()
        Comment.objects.filter(author_id__in=demo_user_ids).delete()
        Follow.objects.filter(follower_id__in=demo_user_ids).delete()
        Follow.objects.filter(followee_id__in=demo_user_ids).delete()

        demo_posts = Post.objects.filter(author_id__in=demo_user_ids)
        PostMedia.objects.filter(post__in=demo_posts).delete()
        demo_posts.delete()

        Profile.objects.filter(user_id__in=demo_user_ids).delete()
        demo_user_qs.delete()

        Hashtag.objects.filter(posts__isnull=True).delete()

        self.stdout.write(self.style.WARNING("🧹 Demo data reset complete."))

    def _create_users_and_profiles(self, User):
        created_users = {}

        for email, username, password, first_name, last_name, bio in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"username": username},
            )
            if created:
                user.set_password(password)
                user.save()

            Profile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "bio": bio,
                },
            )

            created_users[username] = user

        return created_users

    def _create_hashtags(self):
        tags = ["python", "django", "backend", "api", "celery", "webdev"]
        created = {}
        for t in tags:
            obj, _ = Hashtag.objects.get_or_create(text=t)
            created[t] = obj
        return created

    def _create_posts(self, users, hashtags):
        """
        Creates:
        - a few published posts
        - one scheduled post (in the future)
        """
        now = timezone.now()

        def make_post(
            author, text, tag_keys: Iterable[str], published_minutes_ago: int | None
        ):
            if published_minutes_ago is None:
                # scheduled post
                post = Post.objects.create(
                    author=author,
                    text=text,
                    status=Post.Status.SCHEDULED,
                    scheduled_for=now + timedelta(minutes=1),
                    published_at=None,
                )
            else:
                post = Post.objects.create(
                    author=author,
                    text=text,
                    status=Post.Status.PUBLISHED,
                    scheduled_for=None,
                    published_at=now - timedelta(minutes=published_minutes_ago),
                )

            if tag_keys:
                post.hashtags.set([hashtags[k] for k in tag_keys])
            return post

        posts = []

        posts.append(
            make_post(
                users["alice"],
                "Just finished building a DRF custom action. Feels great!",
                ["python", "django", "api"],
                published_minutes_ago=55,
            )
        )
        posts.append(
            make_post(
                users["bob"],
                "Added hashtag filtering to the feed today.",
                ["django", "backend"],
                published_minutes_ago=35,
            )
        )
        posts.append(
            make_post(
                users["charlie"],
                "Next: scheduled posts with Celery Beat.",
                ["celery", "backend"],
                published_minutes_ago=15,
            )
        )
        posts.append(
            make_post(
                users["alice"],
                "Scheduled post example: this will appear later.",
                ["celery", "webdev"],
                published_minutes_ago=None,  # scheduled
            )
        )

        return posts

    def _create_follows(self, users):
        # alice follows bob and charlie
        Follow.objects.get_or_create(follower=users["alice"], followee=users["bob"])
        Follow.objects.get_or_create(follower=users["alice"], followee=users["charlie"])

        # bob follows alice
        Follow.objects.get_or_create(follower=users["bob"], followee=users["alice"])

    def _create_likes(self, users, posts):
        # Simple, deterministic likes
        Like.objects.get_or_create(
            user=users["alice"], post=posts[1]
        )  # alice likes bob post
        Like.objects.get_or_create(
            user=users["bob"], post=posts[0]
        )  # bob likes alice post
        Like.objects.get_or_create(
            user=users["charlie"], post=posts[0]
        )  # charlie likes alice post

    def _create_comments(self, users, posts):
        Comment.objects.get_or_create(
            author=users["bob"],
            post=posts[0],
            defaults={"text": "Nice work! Custom actions are super useful."},
        )
        Comment.objects.get_or_create(
            author=users["charlie"],
            post=posts[0],
            defaults={"text": "Clean implementation. Love the scoping logic."},
        )
        Comment.objects.get_or_create(
            author=users["alice"],
            post=posts[1],
            defaults={"text": "Hashtag filtering is such a great feature."},
        )

    def _create_media(self, posts):
        # Optional: create a couple tiny image files as PostMedia.
        try:
            from io import BytesIO
            from PIL import Image
            from django.core.files.base import ContentFile
        except Exception:
            self.stdout.write(
                self.style.WARNING("Pillow not installed; skipping --with-media.")
            )
            return

        def tiny_png_bytes() -> bytes:
            buf = BytesIO()
            Image.new("RGB", (50, 50)).save(buf, format="PNG")
            return buf.getvalue()

        img_bytes = tiny_png_bytes()
        for idx, post in enumerate(posts[:2], start=1):
            pm = PostMedia(post=post)
            pm.file.save(f"demo-{idx}.png", ContentFile(img_bytes), save=True)
