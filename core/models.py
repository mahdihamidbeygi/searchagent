from django.contrib.auth.models import User
from django.db import models

# Create your models here.

class SearchQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_queries')
    query = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Search Queries'

    def __str__(self):
        return f"{self.user.username if hasattr(self.user, 'username') else 'Unknown'} - {self.query[:50] if self.query else ''}"

class SearchResult(models.Model):
    query = models.ForeignKey(SearchQuery, on_delete=models.CASCADE, related_name='results')
    title = models.CharField(max_length=255)
    content = models.TextField()
    source = models.URLField(max_length=500)
    relevance_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-relevance_score']
        verbose_name_plural = 'Search Results'

    def __str__(self):
        return f"{self.title} - {self.relevance_score}"

class SearchFeedback(models.Model):
    FEEDBACK_CHOICES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_feedback')
    result = models.ForeignKey(SearchResult, on_delete=models.CASCADE, related_name='feedback')
    feedback_type = models.CharField(max_length=10, choices=FEEDBACK_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Search Feedback'

    def __str__(self):
        return f"{self.user.username if hasattr(self.user, 'username') else 'Unknown'} - {self.feedback_type} - {self.result.title[:50] if hasattr(self.result, 'title') else ''}"

class JobListing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_listings')
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=500)
    source = models.CharField(max_length=100)
    posted_date = models.DateTimeField()
    salary = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(max_length=50, blank=True)
    requirements = models.JSONField(default=list)
    benefits = models.JSONField(default=list)
    skills = models.JSONField(default=list)
    relevance_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-relevance_score', '-posted_date']
        verbose_name_plural = 'Job Listings'

    def __str__(self):
        return f"{self.title} at {self.company}"
