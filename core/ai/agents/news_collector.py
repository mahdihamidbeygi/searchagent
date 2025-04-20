import logging
import random
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
import os
import requests
from pathlib import Path

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData

logger = logging.getLogger(__name__)

class NewsAndAdsCollector(BaseAgent):
    """Agent for collecting job opportunities from news articles and advertisements"""
    
    def __init__(self, config_path: str = None):
        super().__init__()
        self.news_sources = [
            {"name": "TechCrunch", "url": "https://techcrunch.com"},
            {"name": "Business Insider", "url": "https://www.businessinsider.com"},
            {"name": "Forbes", "url": "https://www.forbes.com"},
            {"name": "CNBC", "url": "https://www.cnbc.com"},
            {"name": "The Verge", "url": "https://www.theverge.com"}
        ]
        # Get API key from environment variable, config file, or use a default for development
        self.news_api_key = self._get_api_key(config_path)
        self.news_api_endpoint = "https://newsapi.org/v2/everything"
    
    def _get_api_key(self, config_path: str = None) -> str:
        """
        Get the NewsAPI key from environment variables or config file
        
        Args:
            config_path: Optional path to a JSON config file containing the API key
            
        Returns:
            The API key as a string, or an empty string if not found
        """
        # First try environment variable
        api_key = os.environ.get("NEWS_API_KEY", "")
        
        if api_key:
            logger.info("Using NEWS_API_KEY from environment variables")
            return api_key
        
        # Then try config file if provided
        if config_path:
            try:
                config_file = Path(config_path)
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                        api_key = config.get("news_api_key", "")
                        if api_key:
                            logger.info(f"Using NEWS_API_KEY from config file: {config_path}")
                            return api_key
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
        
        # Try default locations for config file
        default_paths = [
            Path("config/api_keys.json"),
            Path("api_keys.json"),
            Path(os.path.expanduser("~/.searchagent/api_keys.json"))
        ]
        
        for path in default_paths:
            try:
                if path.exists():
                    with open(path, 'r') as f:
                        config = json.load(f)
                        api_key = config.get("news_api_key", "")
                        if api_key:
                            logger.info(f"Using NEWS_API_KEY from config file: {path}")
                            return api_key
            except Exception as e:
                logger.error(f"Error loading config file {path}: {str(e)}")
        
        logger.warning("No NEWS_API_KEY found in environment variables or config files")
        return ""
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract job opportunities from news articles and advertisements
        
        Args:
            state: Current state with query information
            
        Returns:
            Updated state with job listings from news sources
        """
        try:
            search_state = JobSearchState(**state)
            logger.info(f"Processing news sources for query: {search_state.query}")
            
            # Search each news source for job mentions
            collected_jobs = []
            for source in self.news_sources:
                try:
                    logger.info(f"Searching {source['name']} for job mentions")
                    raw_jobs = self._search_news_source(source, search_state.query)
                    collected_jobs.extend(raw_jobs)
                except Exception as e:
                    logger.error(f"Error searching {source['name']}: {str(e)}")
                    # Add to errors but continue with other sources
                    if 'errors' not in state:
                        state['errors'] = []
                    state['errors'].append({
                        'agent': self.__class__.__name__,
                        'source': source['name'],
                        'error': str(e)
                    })
            
            # Set the news_jobs field directly
            search_state.news_jobs = collected_jobs
            
            logger.info(f"Found {len(search_state.news_jobs)} jobs from news sources")
            return search_state.dict()
            
        except Exception as e:
            return self.handle_error(e, state)
    
    def _search_news_source(self, source: Dict[str, str], query: str) -> List[RawJobData]:
        """
        Search a specific news source for job mentions using NewsAPI
        
        Args:
            source: News source information including name and URL
            query: The job search query
            
        Returns:
            List of raw job data found in news articles and ads
        """
        # If no API key is available, fallback to simulated data
        if not self.news_api_key:
            logger.warning("No NEWS_API_KEY found. Using simulated news data.")
            return self._generate_simulated_news_data(source, query)
        
        try:
            logger.info(f"Fetching real news data for {query} from {source['name']}")
            
            # Extract domain from URL
            domain = source['url'].replace('https://', '').replace('http://', '').split('/')[0]
            
            # Calculate date range (last 30 days)
            today = datetime.now()
            one_month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Create search terms for job-related news
            search_terms = f"{query} hiring OR jobs OR careers OR positions OR opportunities"
            
            # Make API request to NewsAPI
            params = {
                'q': search_terms,
                'domains': domain,
                'from': one_month_ago,
                'language': 'en',
                'sortBy': 'relevancy',
                'apiKey': self.news_api_key
            }
            
            response = requests.get(self.news_api_endpoint, params=params)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            news_data = response.json()
            
            # Process the results
            jobs = []
            articles = news_data.get('articles', [])
            
            logger.info(f"Found {len(articles)} articles from {source['name']} related to {query} jobs")
            
            for article in articles:
                # Only process articles that likely mention job opportunities
                if self._is_job_related(article, query):
                    title = article.get('title', '')
                    description = article.get('description', '')
                    url = article.get('url', '')
                    published_at = article.get('publishedAt', '')
                    
                    # Convert date format
                    try:
                        published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    except:
                        published_date = datetime.now().strftime('%Y-%m-%d')
                    
                    # Extract company from title or use a generic approach
                    company = self._extract_company_from_article(article, query)
                    
                    # Create the job record
                    jobs.append(RawJobData(
                        title=f"{query} opportunity at {company}",
                        company=company,
                        url=url,
                        source=source["name"],
                        description=description,
                        posted_date=published_date,
                        raw_data={
                            "origin": "news_article",
                            "news_source": source["name"],
                            "article_title": title
                        }
                    ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error fetching news from {source['name']}: {str(e)}")
            # Fallback to simulated data if API fails
            logger.info(f"Falling back to simulated data for {source['name']}")
            return self._generate_simulated_news_data(source, query)
    
    def _is_job_related(self, article: Dict[str, Any], query: str) -> bool:
        """Determine if an article is related to job opportunities"""
        job_keywords = ['hiring', 'job', 'career', 'position', 'opportunity', 
                        'recruit', 'employment', 'opening', 'vacancy']
        
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        content = article.get('content', '').lower()
        
        # Check if the article contains job-related keywords
        for keyword in job_keywords:
            if keyword in title or keyword in description or keyword in content:
                return True
        
        return False
    
    def _extract_company_from_article(self, article: Dict[str, Any], query: str) -> str:
        """Extract company name from news article"""
        title = article.get('title', '')
        description = article.get('description', '')
        content = article.get('content', '')
        
        # Common patterns in news headlines about hiring
        patterns = [
            f"(.*?) is hiring {query}",
            f"(.*?) announces {query} positions",
            f"(.*?) to hire {query}",
            f"(.*?) seeks {query}"
        ]
        
        # Try to extract company name using patterns
        for text in [title, description, content]:
            for pattern in patterns:
                if pattern.replace('{query}', '').lower() in text.lower():
                    # Very basic extraction - in a real implementation, 
                    # this would use more sophisticated NLP
                    parts = text.split(' is hiring ')
                    if len(parts) > 1:
                        return parts[0]
        
        # If no company found, use source publisher as a fallback
        return article.get('source', {}).get('name', 'Company')
    
    def _generate_simulated_news_data(self, source: Dict[str, str], query: str) -> List[RawJobData]:
        """Generate simulated news data as a fallback when API is unavailable"""
        logger.info(f"Generating simulated news data for {query} from {source['name']}")
        
        try:
            # The chance of finding a job mention in news is lower than on job boards
            if random.random() > 0.6:  # 40% chance of finding job mentions
                return []
            
            # Generate some job announcements from news
            jobs = []
            num_jobs = random.randint(1, 3)  # Fewer jobs from news sources
            
            for i in range(num_jobs):
                # Generate some sample tech companies that might be in news
                companies = [
                    "Startup XYZ", "NewTech Inc.", "InnovateCorp", 
                    "TechGrowth", "Disrupt AI", "NextWave Systems"
                ]
                
                company = random.choice(companies)
                
                # Create different types of news stories about jobs
                story_types = [
                    f"{company} Announces New {query} Positions as Part of Expansion",
                    f"{company} Hiring {query} Professionals After Securing $10M Funding",
                    f"Tech Talent Shortage: {company} Struggling to Fill {query} Roles",
                    f"{company} Opens New Office, Creates 50 New {query} Jobs"
                ]
                
                title = random.choice(story_types)
                
                # Generate a random date within the last 14 days (news is more recent)
                days_ago = random.randint(0, 14)
                posted_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                
                # Create the news article URL
                article_slug = title.lower().replace(" ", "-").replace(":", "")
                article_url = f"{source['url']}/news/{article_slug}-{i}"
                
                # Create a sample news excerpt
                description = f"According to a recent article on {source['name']}, {company} " \
                              f"is hiring for multiple {query} positions. " \
                              f"The company is looking for candidates with experience in " \
                              f"{query} and related technologies. Visit their careers page for more information."
                
                # Create the job record
                jobs.append(RawJobData(
                    title=f"{query} at {company}",
                    company=company,
                    url=article_url,
                    source=source["name"],
                    description=description,
                    posted_date=posted_date,
                    raw_data={
                        "origin": "news_article",
                        "news_source": source["name"],
                        "article_title": title
                    }
                ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error in _generate_simulated_news_data for {source['name']}: {str(e)}")
            return [] 