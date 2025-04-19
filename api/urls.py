from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AgenticJobSearchViewSet, SearchViewSet

router = DefaultRouter()
router.register(r'search', SearchViewSet, basename='search')
router.register(r'jobs', AgenticJobSearchViewSet, basename='jobs')


urlpatterns = [
    path('', include(router.urls)),
] 