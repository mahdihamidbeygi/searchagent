from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.ai.agentic_job_search import AgenticJobSearch
from core.ai.job_search import JobSearchAgent
from core.ai.search import AISearch
from core.models import JobListing, SearchFeedback, SearchQuery, SearchResult

from .serializers import (SearchFeedbackSerializer, SearchQuerySerializer,
                          SearchRequestSerializer, SearchResultSerializer)


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('test_search')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def test_search(request):
    return render(request, 'test_search.html')

# Create your views here.

class SearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    ai_search = AISearch()
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        
        # Process the query using AI
        ai_response = self.ai_search.process_query(query)
        
        if 'error' in ai_response:
            return Response(
                {'error': ai_response['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Save the search query
        search_query = SearchQuery.objects.create(
            user=request.user,
            query=query
        )
        
        # Save the results
        for result in ai_response['results']:
            SearchResult.objects.create(
                query=search_query,
                title=result['metadata'].get('title', 'Untitled'),
                content=result['content'],
                source=result['metadata'].get('source', ''),
                relevance_score=result['relevance_score']
            )
        
        # Return the response
        return Response({
            'query': search_query.query,
            'answer': ai_response['answer'],
            'results': SearchResultSerializer(
                search_query.results.all(),
                many=True
            ).data
        })
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        queries = SearchQuery.objects.filter(user=request.user)
        serializer = SearchQuerySerializer(queries, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        result = get_object_or_404(SearchResult, pk=pk)
        serializer = SearchFeedbackSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        feedback = SearchFeedback.objects.create(
            user=request.user,
            result=result,
            **serializer.validated_data
        )
        
        return Response(
            SearchFeedbackSerializer(feedback).data,
            status=status.HTTP_201_CREATED
        )

class JobSearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    job_search = JobSearchAgent()
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        location = request.data.get('location', '')
        num_results = int(request.data.get('num_results', 10))
        
        try:
            # Search for jobs
            job_listings = self.job_search.search_jobs(query, location, num_results)
            
            # Save results to database
            saved_listings = []
            for listing in job_listings:
                job = JobListing.objects.create(
                    user=request.user,
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    description=listing.description,
                    url=listing.url,
                    source=listing.source,
                    posted_date=listing.posted_date,
                    salary=listing.salary,
                    job_type=listing.job_type,
                    requirements=listing.requirements,
                    benefits=listing.benefits,
                    skills=listing.skills,
                    relevance_score=listing.relevance_score
                )
                saved_listings.append(job)
            
            # Return the response
            return Response({
                'query': query,
                'location': location,
                'results': [{
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
                } for job in saved_listings]
            })
            
        except Exception as e:
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

class AgenticJobSearchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    agentic_job_search = AgenticJobSearch()
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        
        try:
            # Process the query using agentic job search
            ai_response = self.agentic_job_search.process_query(query)
            
            if 'error' in ai_response:
                return Response(
                    {'error': ai_response['error']},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Save results to database
            saved_listings = []
            for result in ai_response['results']:
                # Extract job info from search result
                title = result.get('title', 'Unknown Position')
                description = result.get('description', '')
                url = result.get('url', '')
                source = result.get('source', 'Unknown')
                
                # Extract more specific job info when available
                company = ''
                location = ''
                job_type = ''
                
                # Try to parse company and location from title or description
                if ':' in title:
                    parts = title.split(':', 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                
                if '-' in title and not company:
                    parts = title.split('-', 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                
                # Create job listing in database
                job = JobListing.objects.create(
                    user=request.user,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=url,
                    source=source,
                    posted_date=timezone.now(),
                    job_type=job_type,
                    relevance_score=0.8  # Default score
                )
                saved_listings.append(job)
            
            # Return the response
            return Response({
                'query': query,
                'structured_query': ai_response.get('structured_query', {}),
                'answer': ai_response['answer'],
                'results': [{
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'location': job.location,
                    'description': job.description,
                    'url': job.url,
                    'source': job.source,
                    'posted_date': job.posted_date,
                    'job_type': job.job_type,
                    'relevance_score': job.relevance_score
                } for job in saved_listings]
            })
            
        except Exception as e:
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
