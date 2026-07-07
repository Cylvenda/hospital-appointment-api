import shutil
import tempfile
from io import BytesIO

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from api.accounts.models import User
from .models import ContentCategory, EducationalContent


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class EducationalContentUploadTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(
            email="health-admin@example.com",
            password="testpass123",
            phone="255700000100",
            role="admin",
            is_active=True,
        )
        self.category = ContentCategory.objects.create(name="Wellness")
        self.client.force_authenticate(self.user)

    def test_create_content_uploads_featured_image(self):
        image_buffer = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(image_buffer, format="PNG")
        image = SimpleUploadedFile("cover.png", image_buffer.getvalue(), content_type="image/png")

        response = self.client.post(
            reverse("content-list"),
            {
                "title": "Image Upload Check",
                "summary": "Image upload summary",
                "content": "<p>Image content</p>",
                "category_uuid": str(self.category.uuid),
                "content_type": EducationalContent.ContentType.ARTICLE,
                "status": EducationalContent.Status.PUBLISHED,
                "featured_image": image,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        content = EducationalContent.objects.get(title="Image Upload Check")
        self.assertTrue(content.featured_image.name.startswith("health_education/images/"))
        self.assertTrue(response.data["featured_image"])

    def test_create_content_uploads_video_file(self):
        video = SimpleUploadedFile(
            "lesson.mp4",
            b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom",
            content_type="video/mp4",
        )

        response = self.client.post(
            reverse("content-list"),
            {
                "title": "Video Upload Check",
                "summary": "Video upload summary",
                "content": "<p>Video content</p>",
                "category_uuid": str(self.category.uuid),
                "content_type": EducationalContent.ContentType.VIDEO,
                "status": EducationalContent.Status.PUBLISHED,
                "video_file": video,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        content = EducationalContent.objects.get(title="Video Upload Check")
        self.assertTrue(content.video_file.name.startswith("health_education/videos/"))
        self.assertTrue(response.data["video_file"])
