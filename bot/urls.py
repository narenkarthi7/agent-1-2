from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_page),
    path("api/chat/", views.chat_api),
    path("api/upload/", views.upload_api),
    path("api/history/", views.history_api),
]
