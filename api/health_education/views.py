from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import ContentCategory, ContentTag, EducationalContent, ContentView, ContentBookmark, ContentReaction
from .serializers import (
    ContentCategorySerializer, ContentTagSerializer, EducationalContentListSerializer,
    EducationalContentDetailSerializer, EducationalContentCreateUpdateSerializer,
    ContentBookmarkSerializer
)

class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role in ["admin", "receptionist", "doctor"]

class ContentCategoryViewSet(viewsets.ModelViewSet):
    queryset = ContentCategory.objects.all()
    serializer_class = ContentCategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"

class ContentTagViewSet(viewsets.ModelViewSet):
    queryset = ContentTag.objects.all()
    serializer_class = ContentTagSerializer
    permission_classes = [IsAdminOrReadOnly]

class EducationalContentViewSet(viewsets.ModelViewSet):
    queryset = EducationalContent.objects.all().order_by("-published_at")
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EducationalContentCreateUpdateSerializer
        if self.action == "retrieve":
            return EducationalContentDetailSerializer
        return EducationalContentListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or user.role == "patient":
            # Patients only see published content
            queryset = queryset.filter(status=EducationalContent.Status.PUBLISHED)
        
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
            
        return queryset

    def perform_create(self, serializer):
        kwargs = {"author": self.request.user}
        if serializer.validated_data.get("status") == EducationalContent.Status.PUBLISHED:
            kwargs["published_at"] = timezone.now()
        serializer.save(**kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Track views for patients
        if request.user.is_authenticated and request.user.role == "patient":
            ContentView.objects.get_or_create(patient=request.user.patient_profile, content=instance)
            
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def bookmark(self, request, slug=None):
        content = self.get_object()
        if request.user.role != "patient":
            return Response({"detail": "Only patients can bookmark content."}, status=status.HTTP_403_FORBIDDEN)
            
        bookmark, created = ContentBookmark.objects.get_or_create(patient=request.user.patient_profile, content=content)
        if not created:
            bookmark.delete()
            return Response({"status": "unbookmarked"})
        return Response({"status": "bookmarked"})
        
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def react(self, request, slug=None):
        content = self.get_object()
        if request.user.role != "patient":
            return Response({"detail": "Only patients can react to content."}, status=status.HTTP_403_FORBIDDEN)
            
        reaction_type = request.data.get("reaction")
        if reaction_type not in [choice[0] for choice in ContentReaction.Reaction.choices]:
            return Response({"detail": "Invalid reaction type."}, status=status.HTTP_400_BAD_REQUEST)
            
        reaction, created = ContentReaction.objects.get_or_create(
            patient=request.user.patient_profile, 
            content=content,
            defaults={"reaction": reaction_type}
        )
        if not created:
            if reaction.reaction == reaction_type:
                reaction.delete()
                return Response({"status": "reaction removed"})
            else:
                reaction.reaction = reaction_type
                reaction.save()
        return Response({"status": "reaction updated", "reaction": reaction_type})

class BookmarkViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContentBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == "patient":
            return ContentBookmark.objects.filter(patient=self.request.user.patient_profile).order_by("-created_at")
        return ContentBookmark.objects.none()
