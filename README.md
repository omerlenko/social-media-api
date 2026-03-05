# Social Media API

A RESTful API for a social media platform built as a student project using **Django 6** and **Django REST Framework**. It covers the full lifecycle of a social platform, from user registration to posting, following, liking, commenting, and scheduling future posts.

---

## Features

### Authentication
- Register with **email and password**, no username-based login.
- Log in to receive a **JWT access token** and refresh token.
- Securely **log out** by blacklisting the refresh token so it can't be reused.

### Profiles
- After registering, create a profile with your **first name, last name, bio, and profile picture**.
- Update your profile at any time. Profile pictures are stored and served locally.
- View any user's public profile, which also shows their **follower and following counts**, and whether you follow each other.
- **Search users** by username, partial, case-insensitive matching supported.

### Follow / Unfollow
- Follow or unfollow any other user with a single API call.
- The system **prevents self-following and duplicate follows**.
- Browse the **list of followers** and **following** for any user.

### Posts & Feed
- Create a post with text content and optional **hashtags** (the `#` prefix is optional, the API normalises them automatically).
- After posting, **upload up to 10 images** as media attachments (separate upload endpoint).
- The main **feed is scoped**: it returns only your own posts and posts from users you follow, so it works like a real social feed.
- Filter the feed by **one or more hashtags** using a query parameter (e.g. `?hashtags=python,django`).

### Scheduled Posts
- Set a `scheduled_for` datetime when creating a post to schedule it for the future.
- A **Celery Beat** worker runs every 30 seconds in the background and automatically publishes any scheduled posts that are due.
- Scheduled posts have status `SCH` until published, at which point they switch to `PUB` automatically.

### Likes
- Like or unlike any post in your feed. **Duplicate likes are prevented** by a unique constraint.
- Each post shows a `likes_count` and an `is_liked` flag so you know your own like status at a glance.
- Retrieve a dedicated **feed of all posts you've liked**.

### Comments
- Add a comment to any post in your feed.
- Retrieve all comments for a specific post.
- Edit or delete **only your own comments**.

### Permissions
- All write actions require authentication, no anonymous posting, liking, or commenting.
- A custom `IsOwnerOrReadOnly` permission ensures you can only **modify or delete content you created**.

---

## Technology Stack

| Layer            | Technology                                 |
|------------------|--------------------------------------------|
| Framework        | Django 6.0, Django REST Framework          |
| Database         | PostgreSQL 16                              |
| Authentication   | JWT via `djangorestframework-simplejwt`    |
| Task Queue       | Celery 5 with Redis as the message broker  |
| API Docs         | `drf-spectacular` (Swagger UI & ReDoc)     |
| Containerisation | Docker & Docker Compose                    |

---

## Database Model Overview

```
User ──── Profile         (one-to-one)
User ──── Follow ──── User (self-referential many-to-many)
User ──── Post            (one-to-many)
Post ──── Hashtag         (many-to-many)
Post ──── PostMedia       (one-to-many, up to 10 images)
User ──── Like ──── Post  (unique per user+post pair)
User ──── Comment ── Post (many-to-many via comments)
```

---

## Getting Started

### Prerequisites
- **Docker** and **Docker Compose** installed.

### Setup

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/social_media_api.git
cd social_media_api
```

**2. Create a `.env` file** in the project root with the following keys:
```env
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

SECRET_KEY=your_django_secret_key

CELERY_BROKER_URL="redis://redis:6379"
CELERY_RESULT_BACKEND="redis://redis:6379"
```

**3. Start all services**
```bash
docker-compose up -d --build
```

This brings up the Django app, PostgreSQL, Redis, Celery Worker, and Celery Beat, all wired together automatically.

The API is now available at `http://localhost:8000/`

**4. Seed demo data _(highly recommended)_**

> The posts feed is **scoped to your own posts and posts from users you follow**, so an empty database gives you an empty feed.
> Running the demo seed is the easiest way to see the API working as intended.

```bash
docker-compose exec social_media python manage.py seed_demo
```

This creates 3 demo users with profiles, mutual follows, published posts, a scheduled post, likes, and comments, all ready to explore.

**Demo credentials** (password `SecurePass123` for all):

| Email | Username |
|---|---|
| `alice@example.com` | alice |
| `bob@example.com` | bob |
| `charlie@example.com` | charlie |

Log in as **alice** to see a feed that includes her own posts plus posts from bob and charlie (whom she follows).

> To reset and re-seed: `python manage.py seed_demo --reset`

**5. Create an admin superuser** _(optional)_
```bash
docker-compose exec social_media python manage.py createsuperuser
```

---

## API Documentation

Interactive documentation is available once the server is running:

- **Swagger UI** → [http://localhost:8000/api/docs/swagger/](http://localhost:8000/api/docs/swagger/)
- **ReDoc** → [http://localhost:8000/api/docs/redoc/](http://localhost:8000/api/docs/redoc/)

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/social_media/auth/register/` | Create a new account |
| `POST` | `/api/social_media/auth/token/` | Log in, returns JWT tokens |
| `POST` | `/api/social_media/auth/token/refresh/` | Refresh an access token |
| `POST` | `/api/social_media/auth/logout/` | Blacklist refresh token (log out) |
| `GET/PUT` | `/api/social_media/users/me/` | View or update your account details |
| `POST` | `/api/social_media/profiles/create/` | Create your profile |
| `GET/PUT` | `/api/social_media/profiles/me/` | View or update your profile |
| `GET` | `/api/social_media/users/` | List users (supports `?username=` search) |
| `GET` | `/api/social_media/users/{id}/` | View a user's profile and follow stats |
| `POST/DELETE` | `/api/social_media/users/{id}/follow/` | Follow or unfollow a user |
| `GET` | `/api/social_media/users/{id}/followers/` | List a user's followers |
| `GET` | `/api/social_media/users/{id}/following/` | List who a user is following |
| `GET` | `/api/social_media/posts/` | Your scoped feed (optional `?hashtags=` filter) |
| `POST` | `/api/social_media/posts/` | Create a post (add `scheduled_for` to schedule it) |
| `POST` | `/api/social_media/posts/{id}/media/` | Upload image attachments to a post |
| `POST/DELETE` | `/api/social_media/posts/{id}/like/` | Like or unlike a post |
| `GET` | `/api/social_media/posts/liked/` | All posts you've liked |
| `GET/POST` | `/api/social_media/posts/{id}/comments/` | View or add comments on a post |
| `PUT/DELETE` | `/api/social_media/comments/{id}/` | Edit or delete your own comment |
