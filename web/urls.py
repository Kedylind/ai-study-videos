from django.urls import path
from .views import home, health

urlpatterns = [
    path("", home, name="home"),
    path("health", health, name="health"),
]
