import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from google import genai
from google.api_core import exceptions, retry
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData
from search_agent.settings import GOOGLE_API_KEY, MAIN_LLM_MODEL

logger = logging.getLogger(__name__)

class CompanyCache:
    """Cache for storing and retrieving company information by industry and query"""

    def __init__(self, db_path=None):
        """Initialize the company cache"""
        if db_path is None:
            # Use a default path in the user's home directory
            db_path = os.path.join(os.path.expanduser("~"), ".company_cache.db")
        
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self):
        """Create the database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for storing company data by industry and query
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_cache (
            id INTEGER PRIMARY KEY,
            cache_key TEXT UNIQUE,
            industry TEXT,
            query TEXT,
            companies_json TEXT,
            timestamp INTEGER
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Initialized company cache database at {self.db_path}")
    
    def _generate_cache_key(self, industry, query):
        """Generate a unique cache key for the industry and query"""
        # Normalize the inputs
        industry_norm = industry.lower().strip()
        query_norm = query.lower().strip()
        
        # Generate a hash
        key_string = f"{industry_norm}:{query_norm}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_companies(self, industry, query, max_age_hours=24):
        """
        Get companies from cache for the given industry and query
        
        Args:
            industry: The industry to search for
            query: The job query
            max_age_hours: Maximum age of cached data in hours (default: 24 hours)
            
        Returns:
            List of company information including name and URL, or None if not in cache
        """
        cache_key = self._generate_cache_key(industry, query)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate the timestamp threshold
        current_time = int(time.time())
        max_age_seconds = max_age_hours * 3600
        threshold_time = current_time - max_age_seconds
        
        # Query the database for cached data that isn't too old
        cursor.execute(
            "SELECT companies_json FROM company_cache WHERE cache_key = ? AND timestamp > ?",
            (cache_key, threshold_time)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                companies = json.loads(result[0])
                logger.info(f"Retrieved {len(companies)} companies from cache for {industry}, {query}")
                return companies
            except json.JSONDecodeError:
                logger.error("Failed to decode cached companies JSON")
                return None
        
        return None
    
    def save_companies(self, industry, query, companies):
        """
        Save companies to cache for the given industry and query
        
        Args:
            industry: The industry to search for
            query: The job query
            companies: List of company information including name and URL
        """
        if not companies:
            logger.warning("No companies to cache")
            return
        
        cache_key = self._generate_cache_key(industry, query)
        companies_json = json.dumps(companies)
        current_time = int(time.time())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert or replace the cached data
        cursor.execute(
            "INSERT OR REPLACE INTO company_cache (cache_key, industry, query, companies_json, timestamp) VALUES (?, ?, ?, ?, ?)",
            (cache_key, industry.lower(), query.lower(), companies_json, current_time)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cached {len(companies)} companies for {industry}, {query}")

class CompanyWebsiteCollector(BaseAgent):
    """Agent for collecting job listings from company websites"""
    
    def __init__(self):
        super().__init__()
        self.industry_companies = {
            "technology": [
            ],
            "finance": [
            ],
            "healthcare": [
            ],
            "retail": [
            ]
        }
        
        # Default industry if none specified
        self.default_industry = "technology"
        
        # Initialize Google Generative AI API with proper configuration
        self._initialize_genai_client()
        
        # Initialize the company cache
        self.company_cache = CompanyCache()
    
    def _initialize_genai_client(self):
        """Initialize the Google Generative AI client with proper configuration"""
        # Get API key from environment variable
        api_key = GOOGLE_API_KEY
        if not api_key:
            logger.error("GOOGLE_API_KEY environment variable not set. Using fallback behavior.")
            raise ValueError("GOOGLE_API_KEY environment variable not set. Using fallback behavior.")            
        
        # Configure the Generative AI library with the API key
        self.genai_client = genai.Client(api_key=api_key)
        
        logger.info("Successfully initialized Google Generative AI client")
            
    
    def _search_companies_by_llm(self, industry: str, query: str) -> List[Dict[str, str]]:
        """
        Use Google's Generative AI with search grounding to find companies related to the industry and query
        
        Args:
            industry: The industry to search for
            query: The job query
            
        Returns:
            List of company information including name and career URL
        """
        # First check if we have cached results
        cached_companies = self.company_cache.get_companies(industry, query)
        
        try:
            # Prepare the cached companies string if we have cached data
            cached_companies_str = ""
            if cached_companies:
                # Format cached companies for inclusion in the prompt
                cached_names = [comp["name"] for comp in cached_companies]
                cached_companies_str = f"\nCompanies we already have: {', '.join(cached_names[:10])}"
                if len(cached_names) > 10:
                    cached_companies_str += f" and {len(cached_names) - 10} more."
                cached_companies_str += "\nPlease focus on finding additional companies that are not in this list."
            
            # Use Gemini with search grounding to find companies
            prompt = f"""I need a comprehensive and thorough list of ALL companies in the {industry} industry that are related to {query}.{cached_companies_str}

            For each company, please provide:
            1. The FULL and COMPLETE company name (including Inc., LLC, Ltd., etc. when applicable)
            2. The EXACT URL to the company's career page (not just the company's homepage)
            
            Be exhaustive in your search. Include both well-known companies and lesser-known companies. Use search to find as many relevant companies as possible in the {industry} industry that are connected to {query}.
            
            Format the response as a clean JSON object with this exact structure:
            {{
                "companies": [
                    {{"name": "Complete Company Name, Inc.", "url": "https://company-careers-url.com/careers"}},
                    {{"name": "Another Full Company Name, LLC", "url": "https://another-company.com/jobs"}}
                ]
            }}
            
            IMPORTANT: Ensure ALL company names are complete and thorough. Do not abbreviate company names.
            Return ONLY the JSON object with no additional text.
            """
            
            logger.warning(f"Querying LLM with search grounding for companies in {industry} industry related to {query}")
            
            # Define system instruction for better company research
            system_instruction = """You are a specialized company research assistant. Your task is to:
                1. Search thoroughly for companies in specified industries
                2. Always provide complete, formal company names with proper suffixes (Inc., LLC, Ltd., etc.)
                3. Find exact career page URLs for each company
                4. Return data in clean, properly formatted JSON
                5. Focus on accuracy and completeness of information
                6. Verify that career page URLs are direct links to job listings
                7. Include both major and smaller companies in the results
                8. Ensure all URLs are valid and accessible
                9. Return only factual, verifiable information
                10. Maintain consistent JSON formatting throughout the response"""
            
            # Create config with search tools
            config_with_search = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
                top_p=0.95,
                max_output_tokens=8192,
                system_instruction=system_instruction,
                request_options={"timeout": 10.0}
            )
            
            # Generate content with search grounding
            response = self.genai_client.models.generate_content(
                model=MAIN_LLM_MODEL,
                contents=prompt,
                config=config_with_search,
            )
            
            if hasattr(response, 'text'):
                # Get response text
                raw_text = response.text
                logger.warning(f"Raw response length: {len(raw_text)}")

                # Extract JSON from the response text
                # First check if there's a JSON code block
                json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw_text)
                
                if json_match:
                    # Extract JSON from code block
                    json_str = json_match.group(1)
                    logger.warning("Found JSON in code block")
                else:
                    # Try to find JSON object directly
                    json_pattern = r'(\{\s*"companies"\s*:\s*\[[\s\S]*?\]\s*\})'
                    direct_match = re.search(json_pattern, raw_text)
                    
                    if direct_match:
                        json_str = direct_match.group(1)
                        logger.warning("Found JSON directly in response")
                    else:
                        # Use the entire response as potential JSON
                        json_str = raw_text
                
                # Parse the extracted JSON
                try:
                    data = json.loads(json_str)
                    if "companies" in data and isinstance(data["companies"], list):
                        new_companies = data["companies"]
                        logger.warning(f"Found {len(new_companies)} companies through JSON parsing")
                        
                        # Merge with cached companies if we have them
                        if cached_companies:
                            # Create a set of existing company names for deduplication
                            existing_names = {company["name"].lower() for company in cached_companies}
                            
                            # Add only new companies
                            merged_companies = cached_companies.copy()
                            for company in new_companies:
                                if company["name"].lower() not in existing_names:
                                    merged_companies.append(company)
                                    existing_names.add(company["name"].lower())
                            
                            logger.info(f"Merged {len(merged_companies)} companies ({len(cached_companies)} cached, {len(merged_companies) - len(cached_companies)} new)")
                            
                            # Cache the updated merged list
                            self.company_cache.save_companies(industry, query, merged_companies)
                            return merged_companies
                        else:
                            # No cached companies, just save the new ones
                            self.company_cache.save_companies(industry, query, new_companies)
                            return new_companies
                except json.JSONDecodeError:
                    logger.warning("Failed to parse extracted JSON")
                    
                # Fallback to regex extraction if JSON parsing failed
                logger.warning("Trying regex extraction")
                pattern = r'"name":\s*"([^"]+)"[^}]*"url":\s*"(https?://[^"]+)"'
                matches = re.findall(pattern, raw_text)
                
                if matches:
                    new_companies = []
                    for name, url in matches:
                        new_companies.append({"name": name, "url": url})
                    logger.warning(f"Found {len(new_companies)} companies through regex parsing")
                    
                    # Merge with cached companies if we have them
                    if cached_companies:
                        # Create a set of existing company names for deduplication
                        existing_names = {company["name"].lower() for company in cached_companies}
                        
                        # Add only new companies
                        merged_companies = cached_companies.copy()
                        for company in new_companies:
                            if company["name"].lower() not in existing_names:
                                merged_companies.append(company)
                                existing_names.add(company["name"].lower())
                        
                        logger.info(f"Merged {len(merged_companies)} companies ({len(cached_companies)} cached, {len(merged_companies) - len(cached_companies)} new)")
                        
                        # Cache the updated merged list
                        self.company_cache.save_companies(industry, query, merged_companies)
                        return merged_companies
                    else:
                        # No cached companies, just save the new ones
                        self.company_cache.save_companies(industry, query, new_companies)
                        return new_companies
            
            # If we couldn't find any new companies but have cached ones, return those
            if cached_companies:
                logger.warning("No new companies found, using cached companies")
                return cached_companies
                
            # Ultimate fallback to default industry companies
            logger.warning("Could not extract company data from LLM, using default companies")
            return self.industry_companies[self.default_industry]
        
        except Exception as e:
            logger.error(f"Error searching for companies with LLM: {str(e)}")
            # If we have cached companies, return those on error
            if cached_companies:
                logger.warning("Using cached companies due to error")
                return cached_companies
            return self.industry_companies[self.default_industry]
    def process(self, current_state: JobSearchState) -> Dict[str, Any]:
        """
        Search company websites for job listings based on the user's query and industry
        
        Args:
            state: Current state with query and industry information
            
        Returns:
            Updated state with company job listings
        """
        try:
            search_state = current_state # current_state is already a JobSearchState instance
            logger.info(f"Processing company websites for query: {search_state.query}")
            
            # # Determine which industry to use
            # industry = search_state.industry.lower() if search_state.industry else self.default_industry
            
            # # Get companies related to the industry and query using LLM with search grounding
            # companies_to_search = self._search_companies_by_llm(industry, search_state.query)
            
            # if not companies_to_search:
            #     logger.warning("No companies found, using default industry companies")
            #     companies_to_search = self.industry_companies[self.default_industry]
            
            # # Search each company website for job listings
            collected_jobs = []
            errors = search_state.errors if search_state.errors else []
            # logger.info(f"Companies: {companies_to_search}")
            # for company in companies_to_search[:10]:
            #     try:
            #         logger.info(f"Searching {company['name']} website for jobs")
            #         raw_jobs = self._search_company_website(company, search_state.query)
            #         collected_jobs.extend(raw_jobs)
            #     except Exception as e:
            #         logger.error(f"Error searching {company['name']} website: {str(e)}")
            #         # Add to errors but continue with other companies
            #         # search_state.errors is guaranteed to be a list
            #         errors.append({
            #             'agent': self.__class__.__name__,
            #             'company': company['name'],
            #             'error': str(e)
            #         })
                        
            logger.info(f"Found {len(collected_jobs)} jobs from company websites")
            return {"company_jobs":collected_jobs, "errors": errors}
            
        except Exception as e:
            return super().handle_error(e, current_state) # Call parent's handle_error
    
    def _extract_text_from_containers(self, soup: BeautifulSoup) -> str:
        """
        Extract text from relevant containers while excluding navigation, headers, footers etc.
        """
        # Initialize list to store extracted text
        content_text = []
        
        try:
            # Extract text from main content sections
            main_content_selectors = [
                'section', # Main sections
                '[data-slice-type="info_display_cards"]', # Info display cards
                '[data-slice-type="testimonial_carousel"]', # Testimonials
                '[data-slice-type="faq"]', # FAQs
                '.richtext', # Rich text content
                '[data-testid="faq_item"]' # FAQ items
            ]

            # Elements to exclude
            exclude_selectors = [
                'nav',
                'footer', 
                'header',
                '.ChipList_root',
                '[data-testid="schemaScript"]',
                'style',
                'script'
            ]

            # First remove unwanted elements
            for selector in exclude_selectors:
                for element in soup.select(selector):
                    element.decompose()

            # Extract text from main content areas
            for selector in main_content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # Get text while preserving some structure
                    text = ' '.join(line.strip() for line in element.stripped_strings)
                    if text:
                        content_text.append(text)

            # Extract headings
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                text = heading.get_text(strip=True)
                if text:
                    content_text.append(text)

            # Extract paragraphs
            for para in soup.find_all('p'):
                text = para.get_text(strip=True)
                if text:
                    content_text.append(text)

            # Join all found content with newlines
            return '\n'.join(filter(None, content_text))

        except Exception as e:
            logger.error(f"Error extracting text from containers: {str(e)}")
            # Return raw text as fallback
            return ' '.join(line.strip() for line in soup.stripped_strings)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common noise patterns
        noise_patterns = [
            r'cookie[s]? policy',
            r'accept( all)? cookies?',
            r'privacy policy',
            r'terms of( use| service)',
            r'all rights reserved',
            r'copyright ©?\s*\d{4}',
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()    


    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract and normalize all relevant links from the page.
        Returns a list of unique, absolute URLs.
        """
        links = set()  # Use set to avoid duplicates

        try:
            # Try to get base URL from base tag
            base_tag = soup.find('base', href=True)
            if base_tag:
                base_url = base_tag['href']

            # Find all anchor tags with href
            for anchor in soup.find_all('a', href=True):
                url = anchor['href']
                
                # Skip empty, javascript, and mailto links
                if not url or url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    continue

                try:
                    # Handle relative URLs
                    if not url.startswith(('http://', 'https://')):
                        url = urljoin(base_url, url)

                    # Normalize the URL
                    parsed = urlparse(url)
                    normalized_url = urlunparse(parsed._replace(fragment=''))  # Remove fragments
                    
                    # Additional URL cleaning
                    normalized_url = normalized_url.rstrip('/')  # Remove trailing slash
                    
                    # Only add URLs that match our criteria
                    if self._is_valid_job_url(normalized_url):
                        links.add(normalized_url)

                except Exception as e:
                    logger.debug(f"Error processing URL {url}: {str(e)}")
                    continue

            return list(links)

        except Exception as e:
            logger.error(f"Error extracting links: {str(e)}")
            return []

    def _is_valid_job_url(self, url: str) -> bool:
        """
        Check if URL is likely to be a job listing page based on common patterns.
        """
        # Common job-related URL patterns
        job_patterns = [
            r'/jobs?/',
            r'/careers?/',
            r'/positions?/',
            r'/opportunities?/',
            r'/openings?/',
            r'/apply/',
            r'/job-?listing',
            r'/work-?with-?us',
            r'/join-?our-?team',
            r'/vacancy/',
            r'/employment/',
        ]

        # Convert URL to lowercase for case-insensitive matching
        url_lower = url.lower()

        # Check if URL contains any job-related patterns
        return any(re.search(pattern, url_lower) for pattern in job_patterns)

    def _normalize_url(self, url: str, base_url: str) -> str:
        """
        Normalize a URL by handling relative paths and cleaning the URL.
        """
        try:
            # Handle relative URLs
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)

            # Parse and normalize
            parsed = urlparse(url)
            
            # Clean the path
            path = parsed.path.rstrip('/')
            
            # Reconstruct without fragments and specific query parameters if needed
            cleaned = urlunparse((
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))

            return cleaned

        except Exception as e:
            logger.debug(f"Error normalizing URL {url}: {str(e)}")
            return url

    def _extract_job_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract links specifically from job-related containers.
        """
        job_links = set()

        # Common job container selectors
        job_containers = [
            '.jobs-list',
            '.careers-list',
            '.positions-list',
            '[data-testid="jobs-container"]',
            '.job-listings',
            '#careers-section',
            '.opportunities'
        ]

        try:
            # Look for links in specific job-related containers first
            for container_selector in job_containers:
                container = soup.select_one(container_selector)
                if container:
                    for anchor in container.find_all('a', href=True):
                        url = self._normalize_url(anchor['href'], base_url)
                        if url and self._is_valid_job_url(url):
                            job_links.add(url)

            # If no links found in specific containers, try general approach
            if not job_links:
                all_links = self._extract_links(soup, base_url  )
                job_links.update(url for url in all_links if self._is_valid_job_url(url))

            return list(job_links)

        except Exception as e:
            logger.error(f"Error extracting job links: {str(e)}")
            return []
    
    def _search_company_website(self, company: Dict[str, str], query: str) -> List[RawJobData]:
        """
        Search a specific company website for job listings using Gemini for extraction
        
        Args:
            company: Company information including name and URL
            query: The job search query
            
        Returns:
            List of raw job data found on the company website
            
        **TODO**:
        check if there are any jobs on the company website
        if not, look for a jobs page on the given url (sometimes there's a button on career page to go to jobs page)
        **NOTE**:
        this whole function and class can be replaced by Langchain/Langgraph based AI
        """
        logger.info(f"Searching {company['name']} careers page at {company['url']}")
        
        try:
            # Make request to the company careers page
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(company["url"], headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {company['name']} careers page: HTTP {response.status_code}")
                return []
            
            # Parse the HTML content
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract all links
            all_links = self._extract_links(soup, company["url"])
            
            # Extract job-specific links
            job_links = self._extract_job_links(soup, company["url"])
            
            # Combine and deduplicate links
            unique_links = list(set(all_links + job_links))
            
            # Extract relevant text content
            content_text = self._extract_text_from_containers(soup)
            content_text = self._clean_text(content_text)        
            
            # Normalize query for matching
            query_terms = set(query.lower().split())
            
            # Use Gemini to extract job listings
            prompt = f"""Extract job listings from {company['name']}'s careers page.
            Focus on jobs related to: {query_terms}
            
            I've extracted the following information:
            
            Job-related links found:
            {unique_links}
            
            Main content text:
            {content_text}
            
            For each job listing, extract:
            1. Job title (should be concise, 3-50 characters)
            2. Job URL (must be one of the links provided above)
            3. Location (if mentioned)
            4. Job type (full-time, part-time, contract, etc.)
            5. Description (concise, 10-200 characters)
            6. Posted date (if available)
            
            Format the response as a JSON array with this structure:
            [
                {{
                    "title": "Job Title",
                    "url": "https://company.com/job-url",
                    "location": "Location",
                    "job_type": "Job Type",
                    "description": "Job Description",
                    "posted_date": "Posted Date"
                }}
            ]
            
            Important rules:
            1. Only include jobs that match the query: {query_terms}
            2. URLs must be from the provided links list
            3. Keep titles and descriptions concise
            4. Return ONLY the JSON array with no additional text.
            """
            
            # Configure Gemini for extraction
            config = types.GenerateContentConfig(
                temperature=0.0,
                top_p=0.95,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
            
            # Generate content with Gemini
            response = self.genai_client.models.generate_content(
                model=MAIN_LLM_MODEL,
                contents=prompt,
                config=config
            )
            

            # Extract JSON from response
            try:
                if hasattr(response, 'text'):
                    # Get response text
                    raw_text = response.text
                    
                    # Extract JSON from the response text
                    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', raw_text)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        # Try to find JSON array directly
                        json_pattern = r'(\[\s*\{[\s\S]*?\}\s*\])'
                        direct_match = re.search(json_pattern, raw_text)
                        if direct_match:
                            json_str = direct_match.group(1)
                        else:
                            # Use the entire response as potential JSON
                            json_str = raw_text
                    
                    # Parse the extracted JSON
                    extracted_jobs = json.loads(json_str)
                    logger.warning(f"Gemini extracted {len(extracted_jobs)} jobs from {company['name']}")
                    
                    # Process extracted jobs
                    jobs = []
                    for job_data in extracted_jobs:
                        try:
                            # Make URL absolute if it's relative
                            job_url = job_data.get("url", "")
                            if job_url and not job_url.startswith("http"):
                                continue
                                                
                            jobs.append(RawJobData(
                                title=job_data.get("title", ""),
                                company=company["name"],
                                url=job_url,
                                source=company["name"],
                                location=job_data.get("location", "Unknown"),
                                job_type=job_data.get("job_type", ""),
                                description=job_data.get("description", f"Job listing for {job_data.get('title', '')} at {company['name']}."),
                                posted_date=job_data.get("posted_date", "Unknown"),
                                raw_data={
                                    "origin": "company_website",
                                    "company_url": company["url"],
                                    "extraction_method": "gemini"
                                }
                            ))
                        except Exception as e:
                            logger.warning(f"Error processing extracted job: {str(e)}")
                            continue
                    
                        if jobs:
                            logger.info(f"Found {len(jobs)} matching jobs using Gemini at {company['name']}")
                            return jobs
                        else:
                            logger.warning(f"No jobs found via Gemini, trying traditional scraping for {company['name']}")
                else:
                    logger.warning("No text in Gemini response, falling back to traditional scraping")
            except Exception as e:
                logger.warning(f"Gemini extraction failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error in _search_company_website for {company['name']}: {str(e)}")
            return [] 