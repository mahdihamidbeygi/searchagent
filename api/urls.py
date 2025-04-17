from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AgenticJobSearchViewSet, JobSearchViewSet, SearchViewSet

router = DefaultRouter()
router.register(r'search', SearchViewSet, basename='search')
router.register(r'jobs', JobSearchViewSet, basename='jobs')
router.register(r'agentic-jobs', AgenticJobSearchViewSet, basename='agentic-jobs')

urlpatterns = [
    path('', include(router.urls)),
] 