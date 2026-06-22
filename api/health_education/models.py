import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone

class ContentCategory(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ContentTag(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class EducationalContent(models.Model):
    class ContentType(models.TextChoices):
        ARTICLE = "ARTICLE", "Article"
        VIDEO = "VIDEO", "Video"
        INFOGRAPHIC = "INFOGRAPHIC", "Infographic"
        FAQ = "FAQ", "FAQ"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    category = models.ForeignKey(ContentCategory, on_delete=models.SET_NULL, null=True, related_name="contents")
    tags = models.ManyToManyField(ContentTag, blank=True, related_name="contents")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="authored_contents")
    featured_image = models.ImageField(upload_to="health_education/images/", blank=True, null=True)
    content_type = models.CharField(max_length=20, choices=ContentType.choices, default=ContentType.ARTICLE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        # Make sure published content always has a publish timestamp.
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class ContentView(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey("accounts.PatientProfile", on_delete=models.CASCADE, related_name="content_views")
    content = models.ForeignKey(EducationalContent, on_delete=models.CASCADE, related_name="views")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "content")

    def __str__(self):
        return f"{self.patient} viewed {self.content}"

class ContentBookmark(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey("accounts.PatientProfile", on_delete=models.CASCADE, related_name="content_bookmarks")
    content = models.ForeignKey(EducationalContent, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "content")

    def __str__(self):
        return f"{self.patient} bookmarked {self.content}"

class ContentReaction(models.Model):
    class Reaction(models.TextChoices):
        LIKE = "LIKE", "Like"
        HELPFUL = "HELPFUL", "Helpful"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey("accounts.PatientProfile", on_delete=models.CASCADE, related_name="content_reactions")
    content = models.ForeignKey(EducationalContent, on_delete=models.CASCADE, related_name="reactions")
    reaction = models.CharField(max_length=20, choices=Reaction.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "content", "reaction")

    def __str__(self):
        return f"{self.patient} reacted {self.reaction} to {self.content}"
