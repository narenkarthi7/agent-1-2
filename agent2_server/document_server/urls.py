from django.urls import include, path

urlpatterns = [path("", include("document_server.document.urls"))]
