import asyncio
import logging

from asgiref.sync import async_to_sync, sync_to_async
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.ai.agentic_job_search import AgenticJobSearch
# from core.ai.agentic_job_search_google_base import AgenticJobSearch
from core.ai.job_search import JobSearchAgent
from core.ai.search import AISearch
from core.models import JobListing, SearchFeedback, SearchQuery, SearchResult

from .serializers import (SearchFeedbackSerializer, SearchQuerySerializer,
                          SearchRequestSerializer, SearchResultSerializer)

logger = logging.Logger(__name__)

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('job_search')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def job_search(request):
    return render(request, 'job_search.html')

# Create your views here.


# class JobSearchViewSet(viewsets.ViewSet):
#     permission_classes = [IsAuthenticated]
#     job_search = JobSearchAgent()
    
#     @action(detail=False, methods=['post'])
#     def search(self, request):
#         serializer = SearchRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         query = serializer.validated_data['query']
#         location = request.data.get('location', '')
#         num_results = int(request.data.get('num_results', 10))
        
#         try:
#             # Search for jobs
#             job_listings = self.job_search.search_jobs(query, location, num_results)
            
#             # Save results to database
#             saved_listings = []
#             for listing in job_listings:
#                 job = JobListing.objects.create(
#                     user=request.user,
#                     title=listing.title,
#                     company=listing.company,
#                     location=listing.location,
#                     description=listing.description,
#                     url=listing.url,
#                     source=listing.source,
#                     posted_date=listing.posted_date,
#                     salary=listing.salary,
#                     job_type=listing.job_type,
#                     requirements=listing.requirements,
#                     benefits=listing.benefits,
#                     skills=listing.skills,
#                     relevance_score=listing.relevance_score
#                 )
#                 saved_listings.append(job)
            
#             # Return the response
#             return Response({
#                 'query': query,
#                 'location': location,
#                 'results': [{
#                     'id': job.id,
#                     'title': job.title,
#                     'company': job.company,
#                     'location': job.location,
#                     'description': job.description,
#                     'url': job.url,
#                     'source': job.source,
#                     'posted_date': job.posted_date,
#                     'salary': job.salary,
#                     'job_type': job.job_type,
#                     'requirements': job.requirements,
#                     'benefits': job.benefits,
#                     'skills': job.skills,
#                     'relevance_score': job.relevance_score
#                 } for job in saved_listings]
#             })
            
#         except Exception as e:
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def history(self, request):
#         listings = JobListing.objects.filter(user=request.user)
#         return Response([{
#             'id': job.id,
#             'title': job.title,
#             'company': job.company,
#             'location': job.location,
#             'posted_date': job.posted_date,
#             'relevance_score': job.relevance_score
#         } for job in listings])

class AgenticJobSearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    agentic_job_search = AgenticJobSearch()
        
    @action(detail=False, methods=['post'])
    def search(self, request):
        """
        Synchronous wrapper around async job search
        """
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        industry = request.data.get('industry', None)
        
        try:
            # Create an async function to perform the job search
            async def perform_search():
                # Search for jobs using the new agentic job search system
                result = await self.agentic_job_search.process_query(query=query, industry=industry)
                
                # Save job listings to the database
                await sync_to_async(self.agentic_job_search.save_job_listings, thread_sensitive=True)(
                    request.user.id, 
                    result.get('results', [])
                )
                
                return result
            
            # Execute the async function synchronously with a timeout
            async def timed_search():
                try:
                    return await asyncio.wait_for(perform_search(), timeout=90.0)
                except asyncio.TimeoutError:
                    logger.error("Job search timed out after 90 seconds")
                    raise Exception("Job search operation timed out")
            
            result = async_to_sync(timed_search)()
            
            # Return the response
            return Response({
                'query': query,
                'industry': industry,
                'answer': result.get('answer', ''),
                'results': result.get('results', []),
                'errors': result.get('errors', [])
            })
            
        except Exception as e:
            logger.error(f"Error in search action: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        listings = JobListing.objects.filter(user=request.user)
        return Response([{
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'posted_date': job.posted_date,
            'relevance_score': job.relevance_score
        } for job in listings])
    
    @action(detail=True, methods=['get'])
    def detail(self, request, pk=None):
        job = get_object_or_404(JobListing, pk=pk, user=request.user)
        return Response({
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'description': job.description,
            'url': job.url,
            'source': job.source,
            'posted_date': job.posted_date,
            'salary': job.salary,
            'job_type': job.job_type,
            'requirements': job.requirements,
            'benefits': job.benefits,
            'skills': job.skills,
            'relevance_score': job.relevance_score
        })
