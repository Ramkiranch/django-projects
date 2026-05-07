import tempfile
from datetime import datetime, timedelta, timezone

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Post

# Tiny 1x1 PNG so ImageField validation passes without bundling a real file.
ONE_PIXEL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


def make_post(idx=0):
    return Post.objects.create(
        title=f'Post {idx}',
        pub_date=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=idx),
        image=SimpleUploadedFile(f'post-{idx}.png', ONE_PIXEL_PNG, content_type='image/png'),
        body=f'Body of post {idx}.',
    )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class HomeViewTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_home_uses_template(self):
        response = self.client.get(reverse('home'))
        self.assertTemplateUsed(response, 'posts/home.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_home_paginates_at_posts_per_page_limit(self):
        # Reference the constant directly so pagination size changes flow through
        from posts.views import POSTS_PER_PAGE

        # Create POSTS_PER_PAGE + 2 so we get exactly 2 pages with the
        # second page partially full.
        for i in range(POSTS_PER_PAGE + 2):
            make_post(i)

        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj.object_list), POSTS_PER_PAGE)
        self.assertEqual(page_obj.paginator.num_pages, 2)

    def test_home_second_page_returns_remaining_posts(self):
        from posts.views import POSTS_PER_PAGE

        for i in range(POSTS_PER_PAGE + 2):
            make_post(i)
        response = self.client.get(reverse('home') + '?page=2')
        self.assertEqual(response.status_code, 200)
        # Second page has the remainder (2 posts beyond the first POSTS_PER_PAGE)
        self.assertEqual(len(response.context['page_obj'].object_list), 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostDetailViewTests(TestCase):
    def test_detail_returns_200_for_existing_post(self):
        post = make_post(1)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, post.title)

    def test_detail_uses_template(self):
        post = make_post(1)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertTemplateUsed(response, 'posts/posts_detail.html')

    def test_detail_returns_404_for_missing_post(self):
        response = self.client.get(reverse('post_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_detail_renders_markdown_in_body(self):
        post = Post.objects.create(
            title='Markdown post',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('md.png', ONE_PIXEL_PNG, content_type='image/png'),
            body=(
                '## Subheading\n\n'
                'A paragraph with **bold** and *italic* text and `inline code`.\n\n'
                '1. First item\n'
                '2. Second item\n\n'
                '- Bullet one\n'
                '- Bullet two\n\n'
                '> A quoted line.\n'
            ),
        )
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # The post-detail view enables Markdown's `toc` extension which
        # injects id="..." on every heading, so allow either form.
        self.assertIn('>Subheading</h2>', body)
        self.assertIn('<strong>bold</strong>', body)
        self.assertIn('<em>italic</em>', body)
        self.assertIn('<code>inline code</code>', body)
        self.assertIn('<ol>', body)
        self.assertIn('<li>First item</li>', body)
        self.assertIn('<ul>', body)
        self.assertIn('<li>Bullet one</li>', body)
        self.assertIn('<blockquote>', body)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SitemapTests(TestCase):
    def test_sitemap_returns_200_with_xml_content_type(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('xml', response['Content-Type'].lower())

    def test_sitemap_includes_post_and_static_urls(self):
        post = make_post(0)
        response = self.client.get('/sitemap.xml')
        body = response.content.decode()
        # Static pages
        self.assertIn('<loc>', body)
        self.assertIn(reverse('home'), body)
        self.assertIn(reverse('about'), body)
        # Post URL
        self.assertIn(f'/posts/{post.id}/', body)


class RobotsTxtTests(TestCase):
    def test_robots_returns_200_text_plain(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_robots_disallows_admin_path(self):
        response = self.client.get('/robots.txt')
        body = response.content.decode()
        self.assertIn('User-agent: *', body)
        self.assertIn('Disallow:', body)
        self.assertIn('Sitemap:', body)
        self.assertIn('/sitemap.xml', body)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RSSFeedTests(TestCase):
    def test_feed_returns_200_with_rss_content_type(self):
        make_post(0)
        response = self.client.get('/feed/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('rss', response['Content-Type'].lower())

    def test_feed_lists_posts(self):
        post = make_post(0)
        response = self.client.get('/feed/')
        body = response.content.decode()
        self.assertIn("Ramkiran's Blog", body)
        self.assertIn(post.title, body)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OpenGraphTests(TestCase):
    def test_post_detail_has_og_article_type_and_image(self):
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        self.assertIn('property="og:type" content="article"', body)
        self.assertIn(f'property="og:title" content="{post.title}"', body)
        # og:image is per-post, should reference the uploaded image URL
        self.assertIn('property="og:image"', body)

    def test_post_detail_has_jsonld_blogposting(self):
        import json
        import re
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        match = re.search(
            r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
            body, re.DOTALL,
        )
        self.assertIsNotNone(match, 'JSON-LD script not found on post detail')
        data = json.loads(match.group(1))
        self.assertEqual(data['@type'], 'BlogPosting')
        self.assertEqual(data['headline'], post.title)
        self.assertIn('author', data)
        self.assertIn('datePublished', data)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    SITE_URL='http://localhost:8000',  # Misconfigured on purpose — request host should win
    ALLOWED_HOSTS=['ramkiransblog.com'],
)
class PostAdminShareUrlsTests(TestCase):
    """The Share URLs panel renders UTM-tagged links per platform.

    Critical: URLs must reflect the host the admin is being browsed
    on (e.g. ramkiransblog.com), NOT settings.SITE_URL — which may
    still be the localhost dev default if the operator forgot to set
    it on the VM.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pwd-not-used')
        self.client.force_login(self.admin)
        self.post = make_post(0)

    def test_change_form_uses_request_host_not_misconfigured_site_url(self):
        response = self.client.get(
            f'/rk-admin/posts/post/{self.post.id}/change/',
            HTTP_HOST='ramkiransblog.com',
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        # All platforms present
        for label in ('LinkedIn', 'Twitter/X', 'Instagram', 'Facebook', 'Newsletter'):
            self.assertIn(label, body)

        # URLs must use the request host, NOT the misconfigured localhost SITE_URL
        self.assertIn(
            f'http://ramkiransblog.com/posts/{self.post.id}/?utm_source=linkedin&amp;utm_medium=social',
            body,
        )
        self.assertIn(
            f'http://ramkiransblog.com/posts/{self.post.id}/?utm_source=newsletter&amp;utm_medium=email',
            body,
        )
        self.assertNotIn('localhost:8000', body)

    def test_change_form_uses_https_when_request_is_https(self):
        response = self.client.get(
            f'/rk-admin/posts/post/{self.post.id}/change/',
            HTTP_HOST='ramkiransblog.com',
            **{'wsgi.url_scheme': 'https'},
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(
            f'https://ramkiransblog.com/posts/{self.post.id}/?utm_source=linkedin&amp;utm_medium=social',
            body,
        )

    def test_panel_handles_unsaved_post_gracefully(self):
        response = self.client.get('/rk-admin/posts/post/add/', HTTP_HOST='ramkiransblog.com')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('save the post to see share URLs', body)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostSummaryTests(TestCase):
    """Post.summary() must skip the leading disclaimer (blockquote +
    horizontal rule) so home-page card previews show real content,
    not the same boilerplate on every card."""

    def _make_post_with_body(self, body: str) -> Post:
        return Post.objects.create(
            title='Summary test',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('s.png', ONE_PIXEL_PNG, content_type='image/png'),
            body=body,
        )

    def test_summary_skips_leading_blockquote_disclaimer(self):
        body = (
            "> _Views here are my own — not my employer's, past or present._\n\n"
            "---\n\n"
            "## Why I started this blog\n\n"
            "I want to write about web development and football."
        )
        post = self._make_post_with_body(body)
        summary = post.summary()
        self.assertNotIn('Views here are my own', summary)
        self.assertNotIn('employer', summary)
        self.assertIn('Why I started this blog', summary)

    def test_summary_skips_multi_line_blockquote(self):
        body = (
            "> _Multi-line disclaimer\n"
            "> spanning two blockquote lines._\n\n"
            "Real first paragraph here."
        )
        post = self._make_post_with_body(body)
        self.assertEqual(post.summary().strip(), 'Real first paragraph here.')

    def test_summary_handles_post_without_disclaimer(self):
        body = "Just a normal post. No disclaimer here."
        post = self._make_post_with_body(body)
        self.assertIn('Just a normal post', post.summary())

    def test_summary_truncates_to_160_chars(self):
        body = 'A' * 500
        post = self._make_post_with_body(body)
        self.assertEqual(len(post.summary()), 160)

    def test_summary_keeps_mid_post_blockquotes(self):
        # Mid-post blockquotes are real content (e.g. quoting someone) and
        # should NOT be skipped — only LEADING blockquotes are.
        body = (
            "First paragraph of real content here that fills enough chars "
            "to reach the blockquote.\n\n"
            "> A real quote inside the post.\n\n"
            "More content."
        )
        post = self._make_post_with_body(body)
        self.assertIn('First paragraph', post.summary())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostDetailSignupSlotsTests(TestCase):
    """The May 2026 redesign reintroduces a post-end signup — but as
    the new "author card" pattern (photo + bio + form), not the earlier
    plain "Liked this?" aside that was removed in PR #16. Both the
    author card and the footer form should render."""

    def test_post_end_uses_author_card_not_old_aside(self):
        post = Post.objects.create(
            title='Test',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('t.png', ONE_PIXEL_PNG, content_type='image/png'),
            body='Body.',
        )
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        # New author-card pattern present (with hidden source=post-end)
        self.assertIn('class="subs-author"', body)
        self.assertIn('value="post-end"', body)
        # Old "Liked this? Get notified" aside copy must NOT be back
        self.assertNotIn("Liked this? Get notified", body)
        # Footer signup (value="footer") still present — both forms render
        self.assertIn('value="footer"', body)


class ReadTimeTests(TestCase):
    """Post.read_time() rounds up at 225 wpm, never below 1 minute,
    and ignores Markdown syntax characters."""

    def _post(self, body: str) -> Post:
        return Post(
            title='rt',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            body=body,
        )

    def test_short_post_returns_one_minute(self):
        # 5 words → ceil(5/225) = 1
        self.assertEqual(self._post('one two three four five').read_time(), 1)

    def test_long_post_rounds_up(self):
        # 500 words → ceil(500/225) = 3
        body = ' '.join(['word'] * 500)
        self.assertEqual(self._post(body).read_time(), 3)

    def test_zero_words_returns_one_minute(self):
        self.assertEqual(self._post('').read_time(), 1)

    def test_strips_markdown_before_counting(self):
        # Visible words: 'bold italic heading body' = 4 words
        # Without stripping, we'd also count `**`, `_`, `##` as token noise.
        body = '**bold** _italic_\n\n## heading\n\nbody'
        self.assertEqual(self._post(body).read_time(), 1)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostDetailReadTimeTests(TestCase):
    def test_detail_page_shows_min_read(self):
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'min read')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostDetailTocTests(TestCase):
    def _post_with_body(self, body: str) -> Post:
        return Post.objects.create(
            title='TOC test',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('toc.png', ONE_PIXEL_PNG, content_type='image/png'),
            body=body,
        )

    def test_toc_sidebar_renders_when_two_or_more_h2s(self):
        post = self._post_with_body(
            '## First section\n\nfoo\n\n## Second section\n\nbar'
        )
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        self.assertIn('On this page', body)
        # Markdown's toc extension assigns ids to headings
        self.assertIn('id="first-section"', body)
        self.assertIn('id="second-section"', body)

    def test_toc_sidebar_omitted_when_only_one_h2(self):
        post = self._post_with_body('## Lonely\n\nbody only')
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertNotContains(response, 'On this page')

    def test_toc_sidebar_omitted_when_no_headings(self):
        post = self._post_with_body('Just a plain post with no headings.')
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertNotContains(response, 'On this page')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostDetailRecommendedPostsTests(TestCase):
    def test_recommendations_show_three_most_recent_other_posts(self):
        # Create 5 posts, view post 3 — recommendations should be 5/4/2 (newest first, excluding 3)
        posts = [make_post(i) for i in range(5)]
        target = posts[2]
        response = self.client.get(reverse('post_detail', args=[target.id]))
        body = response.content.decode()
        # Expected order: idx 4 (newest), idx 3, idx 1
        i4 = body.find('Post 4')
        i3 = body.find('Post 3')
        i1 = body.find('Post 1')
        self.assertGreater(i4, 0, 'Post 4 should appear in recommendations')
        self.assertGreater(i3, 0, 'Post 3 should appear in recommendations')
        self.assertGreater(i1, 0, 'Post 1 should appear in recommendations')
        # Newest first: Post 4 before Post 3 before Post 1 in the rendered HTML
        self.assertLess(i4, i3)
        self.assertLess(i3, i1)

    def test_recommendations_exclude_current_post(self):
        posts = [make_post(i) for i in range(3)]
        target = posts[1]
        response = self.client.get(reverse('post_detail', args=[target.id]))
        body = response.content.decode()
        # The current post's title appears in the H1 header — but should NOT
        # appear inside the "More from the blog" recommendations section.
        more_idx = body.find('More from the blog')
        self.assertGreater(more_idx, 0)
        recs_section = body[more_idx:]
        self.assertNotIn(f'>{target.title}<', recs_section)

    def test_recommendations_capped_at_three(self):
        posts = [make_post(i) for i in range(6)]
        target = posts[0]
        response = self.client.get(reverse('post_detail', args=[target.id]))
        body = response.content.decode()
        # Of 5 other posts, only 3 most recent should appear (5, 4, 3)
        for visible in ('Post 5', 'Post 4', 'Post 3'):
            self.assertIn(visible, body)
        # Older ones should NOT appear in recommendations
        more_idx = body.find('More from the blog')
        recs_section = body[more_idx:]
        self.assertNotIn('Post 2', recs_section)
        self.assertNotIn('Post 1', recs_section)

    def test_no_recommendations_section_when_only_one_post(self):
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertNotContains(response, 'More from the blog')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PostCardPartialTests(TestCase):
    def test_home_uses_card_partial(self):
        make_post(0)
        response = self.client.get(reverse('home'))
        self.assertTemplateUsed(response, 'posts/_post_card.html')

    def test_detail_uses_card_partial_for_recommendations(self):
        posts = [make_post(i) for i in range(3)]
        response = self.client.get(reverse('post_detail', args=[posts[0].id]))
        self.assertTemplateUsed(response, 'posts/_post_card.html')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RedesignSmokeTests(TestCase):
    """Smoke tests for the May 2026 visual refresh — assert the new
    design's distinctive class names and font loader appear in rendered
    HTML so a regression to the prior Bootstrap-only template gets caught."""

    def test_base_loads_google_fonts(self):
        response = self.client.get(reverse('home'))
        body = response.content.decode()
        self.assertIn('fonts.googleapis.com/css2?family=Lora', body)
        self.assertIn('Source+Sans+3', body)

    def test_home_uses_hero_safe(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="hero-safe"')

    def test_home_uses_new_post_card_class(self):
        make_post(0)
        response = self.client.get(reverse('home'))
        body = response.content.decode()
        self.assertIn('class="post-card"', body)
        self.assertIn('post-card-thumb', body)

    def test_post_detail_uses_post_layout_grid(self):
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertContains(response, 'class="post-layout"')

    def test_post_detail_includes_author_card(self):
        post = make_post(0)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        self.assertIn('class="subs-author"', body)
        # Form action still points at the existing subscribe view
        self.assertIn('/subscribe/', body)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MermaidDiagramTests(TestCase):
    """Mermaid client library is loaded only on posts that contain at
    least one ```mermaid block — otherwise we don't pay the ~600 KB
    download cost on every post-detail view."""

    MERMAID_CDN = 'cdn.jsdelivr.net/npm/mermaid'

    def _post_with_body(self, body: str) -> Post:
        return Post.objects.create(
            title='Diagram test',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('d.png', ONE_PIXEL_PNG, content_type='image/png'),
            body=body,
        )

    def test_post_with_mermaid_block_loads_mermaid_lib(self):
        body = (
            "Some intro text.\n\n"
            "```mermaid\n"
            "graph TD;\n"
            "  A-->B;\n"
            "  A-->C;\n"
            "```\n\n"
            "Closing paragraph."
        )
        post = self._post_with_body(body)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body_html = response.content.decode()
        self.assertIn(self.MERMAID_CDN, body_html)
        # The fenced_code marker that triggered the load
        self.assertIn('class="language-mermaid"', body_html)

    def test_post_without_mermaid_skips_mermaid_lib(self):
        post = self._post_with_body(
            "Just a normal post.\n\n```python\nprint('hi')\n```\n"
        )
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body_html = response.content.decode()
        self.assertNotIn(self.MERMAID_CDN, body_html)
        self.assertNotIn('class="language-mermaid"', body_html)

    def test_post_with_multiple_mermaid_blocks_loads_lib_once(self):
        body = (
            "```mermaid\nflowchart LR; A-->B\n```\n\n"
            "Some text.\n\n"
            "```mermaid\nsequenceDiagram; Alice->>Bob: Hi\n```\n"
        )
        post = self._post_with_body(body)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body_html = response.content.decode()
        # Exactly one CDN script tag, even with two diagrams in the body
        self.assertEqual(body_html.count(self.MERMAID_CDN), 1)
        # Both diagram source bodies appear in the rendered HTML (mermaid will
        # later swap each <pre> for an inline SVG client-side)
        self.assertIn('flowchart LR', body_html)
        self.assertIn('sequenceDiagram', body_html)


class MarkdownFilterTests(TestCase):
    def test_strip_markdown_removes_syntax(self):
        from posts.templatetags.markdown_filters import strip_markdown

        text = (
            '## Heading\n\n'
            'Para with **bold**, *italic*, and `code`.\n\n'
            '1. one\n2. two\n\n- a\n- b\n\n'
            '[link](https://x) and ![alt](https://x.png)\n\n'
            '> quoted\n'
        )
        cleaned = strip_markdown(text)
        for token in ('##', '**', '*', '`', '[', ']', '(', ')', '!', '>', '- ', '1.'):
            self.assertNotIn(token, cleaned)
        self.assertIn('Heading', cleaned)
        self.assertIn('bold', cleaned)
        self.assertIn('link', cleaned)
        self.assertIn('alt', cleaned)
        self.assertIn('quoted', cleaned)
