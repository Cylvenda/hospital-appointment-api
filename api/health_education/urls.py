from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContentCategoryViewSet, ContentTagViewSet, EducationalContentViewSet, BookmarkViewSet

router = DefaultRouter()
router.register(r'categories', ContentCategoryViewSet, basename='content-category')
router.register(r'tags', ContentTagViewSet, basename='content-tag')
router.register(r'contents', EducationalContentViewSet, basename='content')
router.register(r'bookmarks', BookmarkViewSet, basename='bookmark')

urlpatterns = [
    path('education/', include(router.urls)),
]