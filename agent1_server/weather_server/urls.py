from django.urls import include, path

urlpatterns = [path("", include("weather_server.weather.urls"))]
