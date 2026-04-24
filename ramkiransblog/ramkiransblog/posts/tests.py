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
