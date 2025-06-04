import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData
from core.services.linkedin_scraper import LinkedInJobScraper

logger = logging.getLogger(__name__)

class JobListingWebsiteCollector(BaseAgent):
    """Agent for collecting job listings from job boards"""
    
    def __init__(self):
        super().__init__()
        self.job_platforms = [
            {"name": "LinkedIn", "url": "https://www.linkedin.com/jobs"},
            # {"name": "Indeed", "url": "https://www.indeed.com"},
            # {"name": "Monster", "url": "https://www.monster.com"},
            # {"name": "Glassdoor", "url": "https://www.glassdoor.com/Job"},
            # {"name": "ZipRecruiter", "url": "https://www.ziprecruiter.com"}
        ]
        self.linkedin_scraper = None
    
    def process(self, current_state: JobSearchState) -> Dict[str, Any]:
        """
        Search job listing websites for job postings based on the user's query
        
        Args:
            state: Current state with query information
            
        Returns:
            Updated state with job listings
        """
        try:
            search_state = current_state # current_state is already a JobSearchState instance
            logger.info(f"Processing job listing websites for query: {search_state.query}")
            
            # Search each job platform for job listings
            collected_jobs = []
            errors = search_state.errors if search_state.errors else []
            for platform in self.job_platforms:
                try:
                    logger.info(f"Searching {platform['name']} for jobs")
                    raw_jobs = self._search_job_platform(platform, search_state.query, search_state.industry)
                    collected_jobs.extend(raw_jobs)
                except Exception as e:
                    logger.error(f"Error searching {platform['name']}: {str(e)}")
                    # Add to errors but continue with other platforms
                    # search_state.errors is guaranteed to be a list
                    errors.append({
                        'agent': self.__class__.__name__,
                        'platform': platform['name'],
                        'error': str(e)
                    })
            
            
            logger.info(f"Found {len(collected_jobs)} jobs from job listing websites")
            return {"listing_jobs": collected_jobs, "errors": errors}
            
        except Exception as e:
            return super().handle_error(e, current_state)
        finally:
            # Clean up resources
            if self.linkedin_scraper:
                self.linkedin_scraper.close()
                self.linkedin_scraper = None
    
    def _search_job_platform(self, platform: Dict[str, str], query: str, industry: str = None) -> List[RawJobData]:
        """
        Search a specific job platform for job listings
        
        Args:
            platform: Platform information including name and URL
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data found on the job platform
        """
        if platform["name"] == "LinkedIn":
            return self._search_linkedin(query, industry)
        else:
            return
    
    def _search_linkedin(self, query: str, industry: str = None) -> List[RawJobData]:
        """
        Search LinkedIn for job listings using our specialized scraper
        
        Args:
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data from LinkedIn
        """
        try:
            logger.info(f"Searching LinkedIn for jobs matching '{query}' in industry '{industry}'")
            
            # Initialize the LinkedIn scraper if not already done
            if not self.linkedin_scraper:
                self.linkedin_scraper = LinkedInJobScraper(headless=True)
            
            # Prepare search parameters
            search_query = query
            location = ""
            max_pages = 2
            limit = 10
            
            # If industry is provided, include it in the search query
            if industry:
                search_query = f"{query} {industry}"
            
            # Apply filters based on configuration
            filters = {
                "time": "month",  # Look for jobs posted in the last month
                "experience": ["entry", "associate", "mid-senior"],  # Target mid-level positions
                "job_type": ["full_time", "contract"],  # Focus on full-time and contract roles
                "remote": ["remote", "hybrid"]  # Include remote and hybrid roles
            }
            
            # Execute the search
            job_results = self.linkedin_scraper.search_jobs(
                query=search_query,
                location=location,
                max_pages=max_pages,
                limit=limit,
                filters=filters
            )
            
            # Convert results to RawJobData
            raw_jobs = []
            for job_data in job_results:
                raw_job = self.linkedin_scraper.to_raw_job_data(job_data)
                raw_jobs.append(raw_job)
            
            logger.info(f"Found {len(raw_jobs)} LinkedIn jobs matching '{query}' in industry '{industry}'")
            return raw_jobs
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {str(e)}")
            # Return an empty list if we encounter an error
            return []
            