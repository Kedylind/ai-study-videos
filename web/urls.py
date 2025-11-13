from django.urls import path
from .views import home, health, upload_paper, pipeline_status, pipeline_result

urlpatterns = [
    path("", home, name="home"),
    path("health", health, name="health"),
    path("upload/", upload_paper, name="upload_paper"),
    path("status/<str:pmid>/", pipeline_status, name="pipeline_status"),
    path("result/<str:pmid>/", pipeline_result, name="pipeline_result"),
]
