import logging
from typing import Dict, List, Any

from core.services.linkedin_scraper import LinkedInJobScraper as ServiceScraper
from core.models import JobListing

logger = logging.getLogger(__name__)

class LinkedInJobScraper:
    """Legacy wrapper for the new LinkedIn job scraper service"""
    
    def __init__(self):
        self.service_scraper = ServiceScraper(headless=True)
        
    def setup_driver(self):
        """Set up the web driver in the service"""
        return self.service_scraper.setup_driver()
        
    def _extract_job_details(self, job_url: str) -> Dict[str, str]:
        """Wrapper for service's job details extraction method"""
        return self.service_scraper._extract_job_details(job_url)
        
    def scrape_job_links(self) -> List[str]:
        """Use service's page source scraping method"""
        page_source = self.service_scraper.driver.page_source if self.service_scraper.driver else ""
        jobs = self.service_scraper._scrape_job_listings(page_source)
        return [job["link"] for job in jobs if "link" in job]
        
    def scroll_down(self):
        """Scroll down the page to load more content"""
        if self.service_scraper.driver:
            self.service_scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            import time
            time.sleep(3)  # Wait for content to load
            self.service_scraper.driver.execute_script("window.scrollTo(0, 0);")  # scroll back to the top
            time.sleep(1)
    
    def search_jobs(self, role: str, location: str, max_pages: int = 3, request=None) -> List[Dict[str, Any]]:
        """Search LinkedIn for jobs, using our service implementation"""
        return self.service_scraper.search_jobs(
            query=role, 
            location=location, 
            max_pages=max_pages,
            request=request
        )
    
    def close(self):
        """Close the web driver"""
        self.service_scraper.close() 