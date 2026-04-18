from django.urls import path
from .views import NotificationListView, MarkNotificationAsReadView, MarkAllAsReadView

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/<uuid:uuid>/mark-read/",
        MarkNotificationAsReadView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/mark-all-read/",
        MarkAllAsReadView.as_view(),
        name="notification-mark-all-read",
    ),
]
