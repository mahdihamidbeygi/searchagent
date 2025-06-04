import asyncio
import json
import logging
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import aiohttp
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.ai.agents.state import RawJobData
from search_agent.settings import GOOGLE_API_KEY, MAIN_LLM_MODEL

logger = logging.getLogger(__name__)

class LinkedInJobScraper:
    """LinkedIn Job Scraper Service
    
    This service scrapes LinkedIn jobs using Selenium for browser automation.
    It's based on techniques from the linkedin-jobs-scraper package but
    adapted to work with our specific application needs.
    """
    
    def __init__(self, headless: bool = True, slow_mo: float = 0.5, page_load_timeout: int = 40):
        """Initialize the LinkedIn job scraper
        
        Args:
            headless: Whether to run the browser in headless mode (default: True)
            slow_mo: Seconds to wait between actions to avoid being blocked (default: 0.5)
            page_load_timeout: Page load timeout in seconds (default: 40)
        """
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }

        # Get API key from environment variable
        api_key = GOOGLE_API_KEY
        if not api_key:
            logger.error("GOOGLE_API_KEY environment variable not set. Using fallback behavior.")
            raise ValueError("GOOGLE_API_KEY environment variable not set. Using fallback behavior.")            
        
        # Configure the Generative AI library with the API key
        self.llm_client = genai.Client(api_key=api_key)
        
        logger.info("Successfully initialized Google Generative AI client")
        
        # Configure Gemini for extraction
        self.config = types.GenerateContentConfig(
            temperature=0.0,
            top_p=0.95,
            max_output_tokens=8192,
            response_mime_type="application/json",
        )
        
        self.driver = None
        self.headless = headless
        self.slow_mo = slow_mo
        self.page_load_timeout = page_load_timeout
        self.base_url = "https://www.linkedin.com/jobs/search/"
        
    def setup_driver(self) -> webdriver.Chrome:
        """Set up and return a Chrome WebDriver"""
        if self.driver is not None:
            return self.driver

        # Set up Chrome options
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Add common options to make the browser more stable
        chrome_options.add_argument("--enable-unsafe-webgl")
        chrome_options.add_argument("--enable-unsafe-swiftshader")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Initialize the Chrome WebDriver
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Set page load timeout
        self.driver.set_page_load_timeout(self.page_load_timeout)
        
        # Execute CDP command to not make navigator.webdriver visible
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return self.driver

    def _extract_job_details(self, job_url: str) -> Optional[Dict[str, str]]:
        """Extract detailed job information from a job page
        
        Args:
            job_url: URL of the job listing page
            
        Returns:
            Dictionary with job details or None if extraction failed
        """
        try:
            logger.info(f"Extracting job details from {job_url}")
            self.driver.get(job_url)
            time.sleep(self.slow_mo)  # Wait for initial page load
            
            # Wait for the job card to be present
            wait = WebDriverWait(self.driver, 10)
            
            # Extract job title
            try:
                job_title_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.top-card-layout__title"))
                )
                job_title = job_title_element.text.strip()
            except TimeoutException:
                logger.warning("Could not find job title element")
                return None
            
            # Extract company name
            try:
                company_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.topcard__org-name-link"))
                )
                company_name = company_element.text.strip()
                company_link = company_element.get_attribute("href")
            except TimeoutException:
                # Try alternative selector
                try:
                    company_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.topcard__org-name-text"))
                    )
                    company_name = company_element.text.strip()
                    company_link = None
                except TimeoutException:
                    logger.warning("Could not find company element")
                    company_name = "Unknown Company"
                    company_link = None
            
            # Extract location
            try:
                location_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.topcard__flavor--bullet"))
                )
                location = location_element.text.strip()
            except TimeoutException:
                logger.warning("Could not find location element")
                location = "Unknown Location"
            
            # Extract job posting date
            try:
                date_element = self.driver.find_element(By.CSS_SELECTOR, "span.posted-time-ago__text")
                date_text = date_element.text.strip()
                # Convert relative date to a proper date string
                posted_date = self._parse_date_text(date_text)
            except (NoSuchElementException, TimeoutException):
                logger.warning("Could not find date element")
                posted_date = datetime.now().strftime("%Y-%m-%d")
                date_text = "Recently"
            
            # Extract job type if available
            try:
                job_type_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.description__job-criteria-item")
                job_type = "Unknown"
                for element in job_type_elements:
                    header = element.find_element(By.CSS_SELECTOR, "h3.description__job-criteria-subheader").text.strip()
                    if header.lower() == "employment type":
                        job_type = element.find_element(By.CSS_SELECTOR, "span.description__job-criteria-text").text.strip()
                        break
            except (NoSuchElementException, TimeoutException):
                logger.warning("Could not find job type element")
                job_type = "Unknown"
            
            # Try to expand the job description if possible
            try:
                show_more_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.show-more-less-html__button"))
                )
                self.driver.execute_script("arguments[0].click();", show_more_button)
                time.sleep(self.slow_mo)
            except TimeoutException:
                logger.info("No 'Show more' button found or not clickable")
            
            # Extract job description
            try:
                description_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.description__text"))
                )
                job_description = description_element.get_attribute("innerHTML")
                job_description_text = description_element.text.strip()
            except TimeoutException:
                logger.warning("Could not find job description element")
                job_description = ""
                job_description_text = ""
            
            # Extract application link if available
            try:
                apply_button = self.driver.find_element(By.CSS_SELECTOR, "a.apply-button")
                apply_link = apply_button.get_attribute("href")
            except NoSuchElementException:
                apply_link = job_url
            
            # Extract insights if available (applicants, connections, etc.)
            try:
                insights_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.jobs-unified-top-card__job-insight")
                insights = [element.text.strip() for element in insights_elements]
            except NoSuchElementException:
                insights = []
            
            # Get company image if available
            try:
                company_img_element = self.driver.find_element(By.CSS_SELECTOR, "img.jobs-company__logo")
                company_img_link = company_img_element.get_attribute("src")
            except NoSuchElementException:
                company_img_link = None
            
            # Use AI to extract skills and requirements
            if job_description_text:
                skills, requirements = self._extract_skills_requirements(job_description_text)
            else:
                skills, requirements = [], []
            
            job_data = {
                "job_id": self._extract_job_id(job_url),
                "title": job_title,
                "company": company_name,
                "company_link": company_link,
                "company_img_link": company_img_link,
                "location": location,
                "description": job_description_text,
                "description_html": job_description,
                "source_url": job_url,
                "apply_link": apply_link,
                "date_text": date_text,
                "posted_date": posted_date,
                "job_type": job_type,
                "source": "linkedin",
                "insights": insights,
                "skills": skills,
                "requirements": requirements,
            }
            
            return job_data
        
        except Exception as e:
            logger.error(f"Error extracting job details: {str(e)}")
            return None

    def _extract_job_id(self, job_url: str) -> str:
        """Extract the job ID from the job URL"""
        try:
            # URLs typically look like: https://www.linkedin.com/jobs/view/12345678
            parts = job_url.split("/")
            job_id = parts[-1].split("?")[0]
            return job_id
        except Exception:
            # If we can't extract it, generate a unique ID
            return f"linkedin-{hash(job_url)}"

    def _parse_date_text(self, date_text: str) -> str:
        """Parse relative date text to a standard date format"""
        today = datetime.now()
        
        if "minute" in date_text.lower() or "hour" in date_text.lower():
            return today.strftime("%Y-%m-%d")
        
        if "day" in date_text.lower():
            try:
                days = int(date_text.split()[0])
                posted_date = today - timedelta(days=days)
                return posted_date.strftime("%Y-%m-%d")
            except:
                return today.strftime("%Y-%m-%d")
                
        if "week" in date_text.lower():
            try:
                weeks = int(date_text.split()[0])
                posted_date = today - timedelta(days=weeks*7)
                return posted_date.strftime("%Y-%m-%d")
            except:
                return today.strftime("%Y-%m-%d")
                
        if "month" in date_text.lower():
            try:
                months = int(date_text.split()[0])
                # Approximate, not exact
                posted_date = today - timedelta(days=months*30)
                return posted_date.strftime("%Y-%m-%d")
            except:
                return today.strftime("%Y-%m-%d")
        
        # Default to today
        return today.strftime("%Y-%m-%d")
    
    def _extract_skills_requirements(self, description: str) -> tuple[List[str], List[str]]:
        """Use AI to extract skills and requirements from job description"""
        try:
            prompt = f"""
            Extract skills and requirements from this job description.
            Format the response as a JSON with two arrays: 'skills' and 'requirements'.
            Keep it concise - only include clearly stated skills and requirements.
            
            Job Description:
            {description[:3000]}  # Limit length for token efficiency
            
            Example response format:
            {{
                "skills": ["Python", "SQL", "AWS", "Machine Learning"],
                "requirements": ["Bachelor's degree", "3+ years experience", "Strong communication skills"]
            }}
            """
            
            # Generate content with Gemini
            response = self.llm_client.models.generate_content(
                model=MAIN_LLM_MODEL,
                contents=prompt,
                config=self.config
            )            
            # Try to parse JSON response
            try:
                # Look for JSON in the response
                json_start = response.text.find('{')
                json_end = response.text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response.text[json_start:json_end]
                    parsed = json.loads(json_str)
                    skills = parsed.get("skills", [])
                    requirements = parsed.get("requirements", [])
                    return skills, requirements
            except Exception as e:
                logger.warning(f"Failed to parse AI-generated skills/requirements: {str(e)}")
            
            # Fallback: empty lists
            return [], []
        except Exception as e:
            logger.error(f"Error extracting skills: {str(e)}")
            return [], []

    def _scrape_job_listings(self, page_source: str) -> List[Dict[str, Any]]:
        """Scrape job listings from the search results page
        
        Args:
            page_source: HTML source of the search results page
            
        Returns:
            List of job listings with basic information
        """
        soup = BeautifulSoup(page_source, "html.parser")
        job_cards = soup.select("div.base-card")
        results = []
        
        for card in job_cards:
            try:
                # Extract the link first (most important item)
                link_element = card.select_one("a.base-card__full-link")
                if not link_element:
                    continue
                
                job_link = link_element.get("href", "").split("?")[0]  # Remove query parameters
                
                # Extract basic details from the card
                title_element = card.select_one("h3.base-search-card__title")
                title = title_element.get_text(strip=True) if title_element else "Unknown Title"
                
                company_element = card.select_one("h4.base-search-card__subtitle")
                company = company_element.get_text(strip=True) if company_element else "Unknown Company"
                
                location_element = card.select_one("span.job-search-card__location")
                location = location_element.get_text(strip=True) if location_element else "Unknown Location"
                
                date_element = card.select_one("time.job-search-card__listdate")
                date_text = date_element.get_text(strip=True) if date_element else "Unknown Date"
                datetime_attr = date_element.get("datetime") if date_element else None
                
                # Format the date
                if datetime_attr:
                    posted_date = datetime_attr.split("T")[0]  # Extract YYYY-MM-DD
                else:
                    posted_date = self._parse_date_text(date_text)
                
                job_listing = {
                    "title": title,
                    "company": company,
                    "location": location,
                    "date_text": date_text,
                    "posted_date": posted_date,
                    "link": job_link,
                    "source": "linkedin"
                }
                
                results.append(job_listing)
            
            except Exception as e:
                logger.warning(f"Error parsing job card: {str(e)}")
                continue
        
        return results

    def search_jobs(
        self, 
        query: str, 
        location: str = "", 
        max_pages: int = 3, 
        limit: int = None,
        filters: Dict[str, Any] = None,
        request=None
    ) -> List[Dict[str, Any]]:
        """Search for jobs on LinkedIn
        
        Args:
            query: Job title or keywords to search for
            location: Location to search in (default: "")
            max_pages: Maximum number of pages to scrape (default: 3)
            limit: Maximum number of jobs to return (default: None)
            filters: Dictionary of filters to apply (default: None)
            request: Web request object for session data (default: None)
            
        Returns:
            List of job listings with detailed information
        """
        jobs = []
        job_links = []
        urls_processed = set()
        
        try:
            self.setup_driver()
            
            # Build search URL with parameters
            params = {
                "keywords": query
            }
            
            if location:
                params["location"] = location
            
            # Add filters if provided
            if filters:
                # For date posted (f_TPR)
                if "time" in filters:
                    time_filter = filters["time"] 
                    if time_filter == "day":
                        params["f_TPR"] = "r86400"
                    elif time_filter == "week":
                        params["f_TPR"] = "r604800"
                    elif time_filter == "month":
                        params["f_TPR"] = "r2592000"
                
                # For experience level (f_E)
                if "experience" in filters:
                    experience_levels = filters["experience"]
                    exp_params = []
                    for level in experience_levels:
                        if level == "internship":
                            exp_params.append("1")
                        elif level == "entry":
                            exp_params.append("2")
                        elif level == "associate":
                            exp_params.append("3")
                        elif level == "mid-senior":
                            exp_params.append("4")
                        elif level == "director":
                            exp_params.append("5")
                        elif level == "executive":
                            exp_params.append("6")
                    
                    if exp_params:
                        params["f_E"] = ",".join(exp_params)
                
                # For job type (f_JT)
                if "job_type" in filters:
                    job_types = filters["job_type"]
                    jt_params = []
                    for jt in job_types:
                        if jt == "full_time":
                            jt_params.append("F")
                        elif jt == "part_time":
                            jt_params.append("P")
                        elif jt == "contract":
                            jt_params.append("C")
                        elif jt == "temporary":
                            jt_params.append("T")
                        elif jt == "internship":
                            jt_params.append("I")
                        elif jt == "volunteer":
                            jt_params.append("V")
                    
                    if jt_params:
                        params["f_JT"] = ",".join(jt_params)
                
                # For remote jobs (f_WT)
                if "remote" in filters:
                    remote_types = filters["remote"]
                    remote_params = []
                    for remote in remote_types:
                        if remote == "on_site":
                            remote_params.append("1")
                        elif remote == "remote":
                            remote_params.append("2")
                        elif remote == "hybrid":
                            remote_params.append("3")
                    
                    if remote_params:
                        params["f_WT"] = ",".join(remote_params)
            
            # Encode parameters
            query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
            search_url = f"{self.base_url}?{query_string}"
            
            logger.info(f"Searching for jobs at: {search_url}")
            self.driver.get(search_url)
            time.sleep(self.slow_mo * 2)  # Give time for the initial page to load
            
            # Get hidden jobs from session if request is provided
            hidden_jobs = []
            if request:
                hidden_jobs = request.session.get("hidden_jobs", [])
            
            page_counter = 0
            
            # Process search results pages
            while page_counter < max_pages:
                logger.info(f"Processing page {page_counter + 1}")
                
                # Extract job listings from the current page
                current_page_jobs = self._scrape_job_listings(self.driver.page_source)
                
                # Add unique job links to our list
                for job in current_page_jobs:
                    if job["link"] not in urls_processed:
                        job_links.append(job["link"])
                        urls_processed.add(job["link"])
                
                # Check if we've reached our limit
                if limit and len(job_links) >= limit:
                    job_links = job_links[:limit]
                    break
                
                # Try to click the "Next" button to load more results
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next']")
                    if next_button.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView();", next_button)
                        time.sleep(self.slow_mo)
                        next_button.click()
                        time.sleep(self.slow_mo * 2)  # Give extra time for page to load
                        page_counter += 1
                    else:
                        logger.info("Next button is disabled, no more pages")
                        break
                except Exception as e:
                    logger.info(f"Could not find or click Next button: {str(e)}")
                    break
                
                # Safety check to avoid infinite loops
                if page_counter >= max_pages:
                    break
            
            # Extract detailed information for each job
            for idx, link in enumerate(job_links):
                if limit and len(jobs) >= limit:
                    break
                    
                logger.info(f"Extracting details for job {idx + 1}/{len(job_links)}: {link}")
                job_details = self._extract_job_details(link)
                
                if job_details:
                    # Check if we have this job in the database already
                    # try:
                    #     existing_job = JobListing.objects.filter(
                    #         title=job_details["title"],
                    #         company=job_details["company"],
                    #         location=job_details["location"],
                    #         url=job_details["source_url"]
                    #     ).first()
                        
                    #     if existing_job:
                    #         # Skip if job is in hidden jobs list
                    #         if existing_job.id in hidden_jobs:
                    #             continue
                            
                    #         # Add id and tailored documents flag
                    #         job_details["id"] = existing_job.id
                    #         job_details["has_tailored_documents"] = hasattr(existing_job, "has_tailored_documents") and existing_job.has_tailored_documents
                    #     else:
                    #         job_details["id"] = None
                    #         job_details["has_tailored_documents"] = False
                    # except Exception as e:
                    #     logger.warning(f"Error checking existing job: {str(e)}")
                    #     job_details["id"] = None
                    #     job_details["has_tailored_documents"] = False
                    
                    jobs.append(job_details)
                
                # Add delay between job detail requests
                time.sleep(self.slow_mo * 2)
            
            return jobs
        
        except Exception as e:
            logger.error(f"Error during job search: {str(e)}")
            return jobs
        
        finally:
            self.close()
    
    def to_raw_job_data(self, job_details: Dict[str, Any]) -> RawJobData:
        """Convert job details to RawJobData format
        
        Args:
            job_details: Dictionary with job details
            
        Returns:
            RawJobData object
        """
        return RawJobData(
            title=job_details["title"],
            company=job_details["company"],
            url=job_details["source_url"],
            source="LinkedIn",
            location=job_details["location"],
            description=job_details["description"],
            posted_date=job_details["posted_date"],
            job_type=job_details.get("job_type", "Unknown"),
            salary=job_details.get("salary", "Not specified"),
            raw_data=job_details
        )
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

from datetime import timedelta
