from django.contrib import admin
from .models import ContentCategory, ContentTag, EducationalContent, ContentView, ContentBookmark, ContentReaction

@admin.register(ContentCategory)
class ContentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(ContentTag)
class ContentTagAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(EducationalContent)
class EducationalContentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "content_type", "status", "published_at")
    list_filter = ("status", "content_type", "category")
    search_fields = ("title", "summary")
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(ContentView)
admin.site.register(ContentBookmark)
admin.site.register(ContentReaction)
