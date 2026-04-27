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

    def test_home_paginates_when_more_than_ten_posts(self):
        for i in range(12):
            make_post(i)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj.object_list), 10)
        self.assertEqual(page_obj.paginator.num_pages, 2)

    def test_home_second_page_returns_remaining_posts(self):
        for i in range(12):
            make_post(i)
        response = self.client.get(reverse('home') + '?page=2')
        self.assertEqual(response.status_code, 200)
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
        self.assertIn('<h2>Subheading</h2>', body)
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
class PostDetailNoDuplicateSignupTests(TestCase):
    """The post-end signup CTA was removed in favor of the single footer
    form — verify it doesn't render on post detail anymore."""

    def test_no_post_end_signup_section_on_detail(self):
        post = Post.objects.create(
            title='Test',
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            image=SimpleUploadedFile('t.png', ONE_PIXEL_PNG, content_type='image/png'),
            body='Body.',
        )
        response = self.client.get(reverse('post_detail', args=[post.id]))
        body = response.content.decode()
        # The post-end signup used <input name="source" value="post-end"> — verify gone
        self.assertNotIn('value="post-end"', body)
        self.assertNotIn("Liked this? Get notified", body)
        # Footer signup (value="footer") still present — single CTA per page
        self.assertIn('value="footer"', body)


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
