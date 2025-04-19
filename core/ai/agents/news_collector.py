import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData

logger = logging.getLogger(__name__)

class NewsAndAdsCollector(BaseAgent):
    """Agent for collecting job opportunities from news articles and advertisements"""
    
    def __init__(self):
        super().__init__()
        self.news_sources = [
            {"name": "TechCrunch", "url": "https://techcrunch.com"},
            {"name": "Business Insider", "url": "https://www.businessinsider.com"},
            {"name": "Forbes", "url": "https://www.forbes.com"},
            {"name": "CNBC", "url": "https://www.cnbc.com"},
            {"name": "The Verge", "url": "https://www.theverge.com"}
        ]
    
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
        Search a specific news source for job mentions
        
        Args:
            source: News source information including name and URL
            query: The job search query
            
        Returns:
            List of raw job data found in news articles and ads
        """
        # In a real implementation, this would use RSS feeds, APIs, or web scraping
        # For demo purposes, we'll generate simulated results
        
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
            logger.error(f"Error in _search_news_source for {source['name']}: {str(e)}")
            return [] 