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
