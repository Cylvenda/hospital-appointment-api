from rest_framework import serializers
from .models import ContentCategory, ContentTag, EducationalContent, ContentView, ContentBookmark, ContentReaction

class ContentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentCategory
        fields = ["uuid", "name", "slug", "description", "is_active"]
        read_only_fields = ["uuid", "slug"]

class ContentTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentTag
        fields = ["uuid", "name"]
        read_only_fields = ["uuid"]

class EducationalContentListSerializer(serializers.ModelSerializer):
    category = ContentCategorySerializer(read_only=True)
    author_name = serializers.SerializerMethodField()
    tags = ContentTagSerializer(many=True, read_only=True)

    def get_author_name(self, obj):
        if not obj.author:
            return "Unknown author"

        full_name = getattr(obj.author, "full_name", "") or ""
        if full_name.strip():
            return full_name.strip()

        if obj.author.first_name or obj.author.last_name:
            return f"{obj.author.first_name or ''} {obj.author.last_name or ''}".strip()

        return obj.author.email or "Unknown author"
    
    class Meta:
        model = EducationalContent
        fields = [
            "uuid", "title", "slug", "summary", "category", 
            "tags", "author_name", "featured_image", 
            "content_type", "status", "published_at", "created_at"
        ]

class EducationalContentDetailSerializer(serializers.ModelSerializer):
    category = ContentCategorySerializer(read_only=True)
    author_name = serializers.SerializerMethodField()
    tags = ContentTagSerializer(many=True, read_only=True)

    def get_author_name(self, obj):
        if not obj.author:
            return "Unknown author"

        full_name = getattr(obj.author, "full_name", "") or ""
        if full_name.strip():
            return full_name.strip()

        if obj.author.first_name or obj.author.last_name:
            return f"{obj.author.first_name or ''} {obj.author.last_name or ''}".strip()

        return obj.author.email or "Unknown author"

    class Meta:
        model = EducationalContent
        fields = [
            "uuid", "title", "slug", "summary", "content", "category", 
            "tags", "author_name", "featured_image", 
            "content_type", "status", "published_at", "created_at", "updated_at"
        ]

class EducationalContentCreateUpdateSerializer(serializers.ModelSerializer):
    category_uuid = serializers.SlugRelatedField(
        slug_field="uuid", queryset=ContentCategory.objects.all(), source="category", required=False, allow_null=True
    )
    tag_uuids = serializers.SlugRelatedField(
        many=True, slug_field="uuid", queryset=ContentTag.objects.all(), source="tags", required=False
    )

    class Meta:
        model = EducationalContent
        fields = [
            "title", "summary", "content", "category_uuid", 
            "tag_uuids", "featured_image", "content_type", "status", "published_at"
        ]

    def to_representation(self, instance):
        return EducationalContentDetailSerializer(instance, context=self.context).data

class ContentBookmarkSerializer(serializers.ModelSerializer):
    content = EducationalContentListSerializer(read_only=True)
    content_uuid = serializers.SlugRelatedField(
        slug_field="uuid", queryset=EducationalContent.objects.all(), source="content", write_only=True
    )

    class Meta:
        model = ContentBookmark
        fields = ["uuid", "content", "content_uuid", "created_at"]
        read_only_fields = ["uuid", "created_at"]
