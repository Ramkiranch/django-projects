# bookishbailee

A Django blog at `bookishbailee.com`, built to the **Modern Botanical** design hand-off.
Same deployment shape as `ramkiransblog` (Django + Postgres + Gunicorn + Caddy + Docker), fresh codebase.

## Stack

- **Django 5.2** + PostgreSQL 16
- **Gunicorn** behind **Caddy** (auto Let's Encrypt TLS)
- **WhiteNoise** for static assets, **django-imagekit** for image variants
- **Markdown** for post bodies (drop cap, pull quote, TOC custom extensions)
- Hand-rolled CSS using design tokens — no Bootstrap, no Tailwind
- Self-hosted Fraunces / Inter / Caveat (WOFF2)

## First-time setup

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY (50+ random chars) and POSTGRES_PASSWORD.
# For local dev set DEBUG=True.

# Pull the fonts (skips files that already exist).
./scripts/fetch-fonts.sh

# Local dev: Postgres + gunicorn, no Caddy.
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build

# Create the admin user.
docker compose exec web python manage.py createsuperuser
```

Open http://localhost:8000 — and the admin at http://localhost:8000/bb-admin/
(adjust if you changed `DJANGO_ADMIN_URL`).

## Authoring

1. Sign in at `/bb-admin/`.
2. Create at least one **Category** (slug autopopulates from name).
3. Optionally create **Tags**.
4. Create a **Post**: title, slug auto-fills, pick a category, attach an image,
   write a markdown body, set `is_featured` on at most one post.

### Markdown extras

| Want | Syntax |
|---|---|
| Drop cap on the first paragraph | (automatic) |
| Pull quote | A line starting with `> [!quote]` then the quoted paragraph |
| TOC | Use `## Section` headings — anchors and a right-rail mini-TOC are generated |
| Code block | Triple backtick fence |

## Deploying

The production compose stack adds Caddy with automatic TLS. Before the
first prod deploy, point `bookishbailee.com` and `www.bookishbailee.com`
A records at the server so the ACME HTTP challenge succeeds.

```bash
# On the server:
git pull
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

`entrypoint.sh` runs `migrate` + `collectstatic` automatically on every
container start, so there's nothing else to do at deploy time.

## Project layout

```
bookishbailee/                Django project package (settings, urls, wsgi, asgi)
posts/                        Blog app (Post, Category, Tag, views, admin, urls)
sitepages/                    About page app
templates/                    Project-level templates (base + partials + page templates)
static/css/                   tokens.css, base.css, layout.css, components.css
static/fonts/                 self-hosted WOFF2 (gitignored — run scripts/fetch-fonts.sh)
caddy/Caddyfile               TLS + reverse proxy + media file server
scripts/entrypoint.sh         migrate + collectstatic + exec gunicorn
scripts/fetch-fonts.sh        download Fraunces/Inter/Caveat into static/fonts/
docker-compose.yml            db + web + caddy
docker-compose.local.yml      dev override: web exposed on :8000, no Caddy
```

## Out of scope (v2)

- Newsletter form (band is visual-only; subscriber model + Buttondown wiring later)
- Bookshelf model — sidebar shelf is hardcoded HTML
- RSS, sitemap, search, comments
