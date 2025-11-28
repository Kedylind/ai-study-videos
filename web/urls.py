from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from .views import (
    home, health, static_debug, debug_media_path, test_volume_write, upload_paper, pipeline_status, pipeline_result, register,
    api_start_generation, api_status, api_result, serve_video, my_videos
)

urlpatterns = [
    path("", home, name="home"),
    path("health", health, name="health"),
    path("static-debug/", static_debug, name="static_debug"),
    path("debug-media/", debug_media_path, name="debug_media"),
    path("test-volume-write/", test_volume_write, name="test_volume_write"),
    path("upload/", upload_paper, name="upload_paper"),
    path("my-videos/", my_videos, name="my_videos"),
    path("status/<str:pmid>/", pipeline_status, name="pipeline_status"),
    path("result/<str:pmid>/", pipeline_result, name="pipeline_result"),
    path("video/<str:pmid>/", serve_video, name="serve_video"),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", register, name="register"),
    # API endpoints
    path("api/generate/", api_start_generation, name="api_start_generation"),
    path("api/status/<str:paper_id>/", api_status, name="api_status"),
    path("api/result/<str:paper_id>/", api_result, name="api_result"),
]
