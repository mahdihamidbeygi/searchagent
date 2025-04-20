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
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search job listing websites for job postings based on the user's query
        
        Args:
            state: Current state with query information
            
        Returns:
            Updated state with job listings
        """
        try:
            search_state = JobSearchState(**state)
            logger.info(f"Processing job listing websites for query: {search_state.query}")
            
            # Search each job platform for job listings
            collected_jobs = []
            for platform in self.job_platforms:
                try:
                    logger.info(f"Searching {platform['name']} for jobs")
                    raw_jobs = self._search_job_platform(platform, search_state.query, search_state.industry)
                    collected_jobs.extend(raw_jobs)
                except Exception as e:
                    logger.error(f"Error searching {platform['name']}: {str(e)}")
                    # Add to errors but continue with other platforms
                    if 'errors' not in state:
                        state['errors'] = []
                    state['errors'].append({
                        'agent': self.__class__.__name__,
                        'platform': platform['name'],
                        'error': str(e)
                    })
            
            # Set the listing_jobs field directly
            search_state.listing_jobs = collected_jobs
            
            logger.info(f"Found {len(search_state.listing_jobs)} jobs from job listing websites")
            return search_state.dict()
            
        except Exception as e:
            return self.handle_error(e, state)
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
            return self._generate_mock_jobs(platform, query)
    
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
            
    def _generate_mock_jobs(self, platform: Dict[str, str], query: str) -> List[RawJobData]:
        """
        Generate mock job listings for platforms we don't yet have scrapers for
        
        Args:
            platform: Platform information including name and URL
            query: The job search query
            
        Returns:
            List of mock job data
        """
        try:
            # Generate some realistic company names
            companies = [
                "Acme Corporation", "Tech Innovations", "Global Systems",
                "NextGen Solutions", "Data Dynamics", "Future Technologies",
                "Pinnacle Software", "Quantum Enterprises", "Apex Industries",
                "Synergy Solutions"
            ]
            
            # Generate some realistic locations
            locations = [
                "New York, NY", "San Francisco, CA", "Chicago, IL", 
                "Austin, TX", "Seattle, WA", "Boston, MA", "Remote",
                "Denver, CO", "Atlanta, GA", "Los Angeles, CA"
            ]
            
            # Generate some realistic job types
            job_types = ["Full-time", "Part-time", "Contract", "Remote", "Temporary"]
            
            # Generate some sample postings
            jobs = []
            num_jobs = random.randint(3, 7)  # Random number of jobs per platform
            
            for i in range(num_jobs):
                # Generate a random date within the last 30 days
                days_ago = random.randint(0, 30)
                posted_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                
                company = random.choice(companies)
                location = random.choice(locations)
                job_type = random.choice(job_types)
                
                # Create job titles based on the query
                if i % 2 == 0:
                    title = f"{query} {random.choice(['Specialist', 'Lead', 'Expert'])}"
                else:
                    title = f"{random.choice(['Senior', 'Junior', 'Principal'])} {query}"
                
                # Create a sample description
                description = f"We are looking for a {title} to join our team at {company}. " \
                              f"This is a {job_type} position based in {location}. " \
                              f"The ideal candidate will have experience in {query} and related technologies."
                
                # Create the job record
                jobs.append(RawJobData(
                    title=title,
                    company=company,
                    url=f"{platform['url']}/viewjob?jk={i}",
                    source=platform["name"],
                    location=location,
                    description=description,
                    posted_date=posted_date,
                    job_type=job_type,
                    salary=f"${random.randint(50, 150)}K - ${random.randint(150, 200)}K",
                    raw_data={
                        "origin": "job_platform",
                        "platform": platform["name"]
                    }
                ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error in _generate_mock_jobs for {platform['name']}: {str(e)}")
            return [] 