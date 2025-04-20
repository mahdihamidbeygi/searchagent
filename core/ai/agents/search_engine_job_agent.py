import json
import logging
import requests
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData
from search_agent.settings import BRAVE_WEBSEARCH_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID
logger = logging.getLogger(__name__)

class SearchEngineJobAgent(BaseAgent):
    """Agent for extracting job listings from search engines like Google, Brave, and DuckDuckGo"""
    
    def __init__(self):
        super().__init__()
        self.search_engines = [
            {"name": "Google", "search_url": "https://www.googleapis.com/customsearch/v1"},
            {"name": "Brave", "search_url": "https://api.search.brave.com/res/v1/web/search"},
            {"name": "DuckDuckGo", "search_url": "https://api.duckduckgo.com/"}
        ]
        # API keys would normally be loaded from environment variables
        self.api_keys = {
            "Google": {"api_key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID},  # Google Custom Search API key and cx
            "Brave": {"api_key": BRAVE_WEBSEARCH_API_KEY},  # Brave Search API key
            "DuckDuckGo": {}  # DuckDuckGo doesn't require an API key for basic usage
        }
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for job listings using various search engines
        
        Args:
            state: Current state with query information
            
        Returns:
            Updated state with job listings from search engines
        """
        try:
            search_state = JobSearchState(**state)
            logger.info(f"Searching engines for job listings matching: {search_state.query}")
            
            # Collect jobs from each search engine
            collected_jobs = []
            for engine in self.search_engines:
                try:
                    logger.info(f"Searching {engine['name']} for jobs")
                    engine_jobs = self._search_engine(
                        engine=engine, 
                        query=search_state.query, 
                        industry=search_state.industry
                    )
                    collected_jobs.extend(engine_jobs)
                except Exception as e:
                    logger.error(f"Error searching {engine['name']}: {str(e)}")
                    # Add error to search_state's errors list
                    search_state.errors = search_state.errors + [{
                        'agent': self.__class__.__name__,
                        'engine': engine['name'],
                        'error': str(e)
                    }]
            
            # Update state with the collected jobs
            search_state.search_engine_jobs = collected_jobs
            
            logger.info(f"Found {len(collected_jobs)} jobs from search engines")
            return search_state.model_dump()
            
        except Exception as e:
            return self.handle_error(e, state)
    
    def _search_engine(self, engine: Dict[str, str], query: str, industry: Optional[str] = None) -> List[RawJobData]:
        """
        Search a specific engine for job listings
        
        Args:
            engine: Engine information including name and search URL
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data found via the search engine
        """
        engine_name = engine["name"]
        if engine_name == "Google":
            return self._search_google(engine, query, industry)
        elif engine_name == "Brave":
            return self._search_brave(engine, query, industry)
        elif engine_name == "DuckDuckGo":
            return self._search_duckduckgo(engine, query, industry)
        else:
            logger.warning(f"Unknown search engine: {engine_name}")
            return []
    
    def _search_google(self, engine: Dict[str, str], query: str, industry: Optional[str] = None) -> List[RawJobData]:
        """
        Search Google for job listings
        
        Args:
            engine: Engine information including name and search URL
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data from Google search
        """
        try:
            # Format the search query
            search_query = f"{query} jobs"
            if industry:
                search_query += f" {industry}"
            
            # Add specific job sites to the query to focus results
            search_query += " site:linkedin.com OR site:indeed.com OR site:glassdoor.com OR site:monster.com"
            
            api_key = self.api_keys["Google"]["api_key"]
            cx = self.api_keys["Google"]["cx"]
            
            # If API keys are not available, return mock data for demonstration
            if not api_key or not cx:
                logger.warning("Google API key or cx not configured, returning mock data")
                return self._generate_mock_search_results("Google", search_query, 5)
            
            # Make the API request
            params = {
                "key": api_key,
                "cx": cx,
                "q": search_query,
                "num": 10
            }
            
            response = requests.get(
                url=engine["search_url"],
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Google search failed with status code {response.status_code}")
                return []
            
            # Parse the results
            results = response.json()
            items = results.get("items", [])
            
            # Convert results to RawJobData format
            job_listings = []
            for item in items:
                job_listings.append(
                    RawJobData(
                        title=item.get("title", ""),
                        company=self._extract_company_from_title(item.get("title", "")),
                        url=item.get("link", ""),
                        source="Google",
                        description=item.get("snippet", ""),
                        raw_data={
                            "origin": "google_search",
                            "extraction_method": "api",
                            "raw_result": item
                        }
                    )
                )
            
            return job_listings
            
        except Exception as e:
            logger.error(f"Error searching Google: {str(e)}")
            return []
    
    def _search_brave(self, engine: Dict[str, str], query: str, industry: Optional[str] = None) -> List[RawJobData]:
        """
        Search Brave for job listings
        
        Args:
            engine: Engine information including name and search URL
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data from Brave search
        """
        try:
            # Format the search query
            search_query = f"{query} jobs"
            if industry:
                search_query += f" {industry}"
            
            api_key = self.api_keys["Brave"]["api_key"]
            
            # If API key is not available, return mock data for demonstration
            if not api_key:
                logger.warning("Brave API key not configured, returning mock data")
                return self._generate_mock_search_results("Brave", search_query, 5)
            
            # Make the API request
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            
            params = {
                "q": search_query,
                "count": 10
            }
            
            response = requests.get(
                url=engine["search_url"],
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Brave search failed with status code {response.status_code}")
                return []
            
            # Parse the results
            results = response.json()
            web_pages = results.get("web", {}).get("results", [])
            
            # Convert results to RawJobData format
            job_listings = []
            for page in web_pages:
                if any(site in page.get("url", "") for site in ["linkedin.com", "indeed.com", "glassdoor.com", "monster.com"]):
                    job_listings.append(
                        RawJobData(
                            title=page.get("title", ""),
                            company=self._extract_company_from_title(page.get("title", "")),
                            url=page.get("url", ""),
                            source="Brave",
                            description=page.get("description", ""),
                            raw_data={
                                "origin": "brave_search",
                                "extraction_method": "api",
                                "raw_result": page
                            }
                        )
                    )
            
            return job_listings
            
        except Exception as e:
            logger.error(f"Error searching Brave: {str(e)}")
            return []
    
    def _search_duckduckgo(self, engine: Dict[str, str], query: str, industry: Optional[str] = None) -> List[RawJobData]:
        """
        Search DuckDuckGo for job listings
        
        Args:
            engine: Engine information including name and search URL
            query: The job search query
            industry: Optional industry filter
            
        Returns:
            List of raw job data from DuckDuckGo search
        """
        try:
            # Format the search query
            search_query = f"{query} jobs"
            if industry:
                search_query += f" {industry}"
            
            # Add specific job sites to the query to focus results
            search_query += " site:linkedin.com OR site:indeed.com OR site:glassdoor.com OR site:monster.com"
            
            # Make the API request
            params = {
                "q": search_query,
                "format": "json",
                "no_html": 1,
                "no_redirect": 1
            }
            
            response = requests.get(
                url=engine["search_url"],
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"DuckDuckGo search failed with status code {response.status_code}")
                return []
            
            # Parse the results
            results = response.json()
            results_list = results.get("Results", [])
            
            # Convert results to RawJobData format
            job_listings = []
            for result in results_list:
                job_listings.append(
                    RawJobData(
                        title=result.get("Text", ""),
                        company=self._extract_company_from_title(result.get("Text", "")),
                        url=result.get("FirstURL", ""),
                        source="DuckDuckGo",
                        description=result.get("Abstract", ""),
                        raw_data={
                            "origin": "duckduckgo_search",
                            "extraction_method": "api",
                            "raw_result": result
                        }
                    )
                )
            
            # If no results found through the API, fall back to mock data
            if not job_listings:
                logger.warning("No results found through DuckDuckGo API, returning mock data")
                return self._generate_mock_search_results("DuckDuckGo", search_query, 5)
            
            return job_listings
            
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo: {str(e)}")
            return []
    
    def _extract_company_from_title(self, title: str) -> str:
        """
        Extract company name from job title when possible
        
        Args:
            title: Job title string
            
        Returns:
            Extracted company name or empty string
        """
        # Common patterns in job titles like "Software Engineer at Google"
        if " at " in title:
            return title.split(" at ")[1].split(" - ")[0].strip()
        
        # Another common pattern "Google - Software Engineer"
        if " - " in title:
            return title.split(" - ")[0].strip()
        
        # If no pattern found, return empty string
        return ""
    
    def _generate_mock_search_results(self, engine_name: str, query: str, count: int) -> List[RawJobData]:
        """
        Generate mock search results for demonstration purposes
        
        Args:
            engine_name: Name of the search engine
            query: Search query
            count: Number of mock results to generate
            
        Returns:
            List of mock job data
        """
        mock_companies = [
            "Amazon", "Google", "Microsoft", "Apple", "Meta", 
            "IBM", "Oracle", "Salesforce", "Adobe", "Netflix",
            "Uber", "Airbnb", "Twitter", "LinkedIn", "Spotify"
        ]
        
        mock_titles = [
            "Software Engineer", "Data Scientist", "Product Manager",
            "UX Designer", "DevOps Engineer", "Frontend Developer",
            "Backend Engineer", "Full Stack Developer", "AI Researcher",
            "Machine Learning Engineer", "Cloud Architect", "Data Analyst"
        ]
        
        mock_locations = [
            "Remote", "San Francisco, CA", "New York, NY", "Seattle, WA",
            "Austin, TX", "Boston, MA", "Los Angeles, CA", "Chicago, IL",
            "Denver, CO", "Atlanta, GA", "Portland, OR", "Dallas, TX"
        ]
        
        job_listings = []
        for i in range(count):
            company = mock_companies[i % len(mock_companies)]
            title = mock_titles[i % len(mock_titles)]
            location = mock_locations[i % len(mock_locations)]
            
            # Extract relevant terms from the query
            query_terms = query.lower().replace("jobs", "").strip().split()
            
            # If query has relevant terms, incorporate them into the title
            if query_terms:
                if "engineer" in query.lower() or "developer" in query.lower():
                    title = f"{query_terms[0].title()} Engineer"
                elif "manager" in query.lower():
                    title = f"{query_terms[0].title()} Manager"
                elif "scientist" in query.lower() or "analyst" in query.lower():
                    title = f"{query_terms[0].title()} Scientist"
            
            job_listings.append(
                RawJobData(
                    title=title,
                    company=company,
                    url=f"https://example.com/jobs/{company.lower()}/{i}",
                    source=engine_name,
                    location=location,
                    description=f"We are looking for a talented {title} to join our team at {company}. Ideal candidates have experience with relevant technologies and a passion for innovation.",
                    posted_date="2023-08-14",  # Mock date
                    salary="$120,000 - $180,000 per year",
                    job_type="Full-time",
                    raw_data={
                        "origin": f"{engine_name.lower()}_search",
                        "extraction_method": "mock",
                        "query": query
                    }
                )
            )
        
        return job_listings 