import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData

logger = logging.getLogger(__name__)

class JobListingWebsiteCollector(BaseAgent):
    """Agent for collecting job listings from job boards"""
    
    def __init__(self):
        super().__init__()
        self.job_platforms = [
            {"name": "LinkedIn", "url": "https://www.linkedin.com/jobs"},
            {"name": "Indeed", "url": "https://www.indeed.com"},
            {"name": "Monster", "url": "https://www.monster.com"},
            {"name": "Glassdoor", "url": "https://www.glassdoor.com/Job"},
            {"name": "ZipRecruiter", "url": "https://www.ziprecruiter.com"}
        ]
    
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
                    raw_jobs = self._search_job_platform(platform, search_state.query)
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
    
    def _search_job_platform(self, platform: Dict[str, str], query: str) -> List[RawJobData]:
        """
        Search a specific job platform for job listings
        
        Args:
            platform: Platform information including name and URL
            query: The job search query
            
        Returns:
            List of raw job data found on the job platform
        """
        # In a real implementation, this would use APIs or web scraping
        # For demo purposes, we'll generate simulated results
        
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
            logger.error(f"Error in _search_job_platform for {platform['name']}: {str(e)}")
            return [] 