import logging
from typing import Any, Dict, List, Optional

from browser_use import Agent
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobSearchState, RawJobData
from search_agent.settings import GROK_API_KEY

logger = logging.getLogger(__name__)
load_dotenv()

class BrowserAgent(BaseAgent):
    """Agent for advanced job search and application using browser automation"""
    
    def __init__(self, task: str):
        super().__init__()
        self.llm = ChatOpenAI(model="grok-3-mini-beta", api_key=GROK_API_KEY, base_url="https://api.x.ai/v1/chat/completions", temperature=0.0, max_retries=3)
        self.browser_agent = None
        self._initialize_browser_agent(task)
    
    def _initialize_browser_agent(self, task: str):
        """Initialize the browser-use agent with Cloudflare bypass configuration"""
        try:
            # Configure browser with stealth settings to bypass Cloudflare
            browser_config = {
                # Enable stealth mode to avoid detection
                "stealth_mode": True,
                # Use a modern, common user agent
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                # Non-headless is less likely to be detected by Cloudflare
                "headless": False,
                # Disable automation flags that Cloudflare checks for
                "disable_automation_control": True,
                "disable_dev_shm_usage": True,
                # Ensure JavaScript execution for Cloudflare verification
                "enable_javascript": True,
                # Increase wait times for Cloudflare challenge completion
                "wait_for_navigation": 10,
                "wait_for_page_load": True,
                # Add random delays between actions to appear more human
                "action_delay": [1, 3],
            }
            
            self.browser_agent = Agent(
                task=task,
                llm=self.llm,
                browser_config=browser_config
            )
            logger.info("Successfully initialized browser-use agent with Cloudflare bypass configuration")
        except Exception as e:
            logger.error(f"Failed to initialize browser-use agent: {str(e)}")
            self.browser_agent = None
    
    # Method to handle Cloudflare challenges when encountered
    async def _handle_cloudflare_challenge(self):
        """Handle Cloudflare verification challenges when detected"""
        if not self.browser_agent:
            logger.warning("Browser agent not initialized, cannot handle Cloudflare challenge")
            return False
        
        try:
            # Create a task to wait for and solve Cloudflare challenges
            cloudflare_task = """
            A Cloudflare verification challenge has been detected. Please:
            1. Wait for the page to load completely
            2. If there's a CAPTCHA, solve it carefully
            3. If there's a "I am human" verification button, click it
            4. Wait for the verification to complete
            5. Once verification is complete, proceed with the original task
            """
            
            # Run the special Cloudflare handling task
            result = await self.browser_agent.run(cloudflare_task)
            logger.info("Cloudflare challenge handling completed")
            return True
            
        except Exception as e:
            logger.error(f"Error handling Cloudflare challenge: {str(e)}")
            return False
    
    async def _search_linkedin(self, query: str, location: str) -> List[RawJobData]:
        """Search for jobs on LinkedIn using browser automation"""
        if not self.browser_agent:
            logger.warning("Browser agent not initialized, skipping LinkedIn search")
            return []
        
        try:
            # Construct the search task
            task = f"""
            Search for {query} jobs in {location} on LinkedIn:
            1. Go to LinkedIn Jobs
            2. Enter search query: {query}
            3. Enter location: {location}
            4. Click search
            5. For each job listing:
               - Extract job title
               - Extract company name
               - Extract location
               - Extract job description
               - Extract application URL
               - Extract posted date
            6. Return results as JSON
            
            Important: If you encounter a Cloudflare verification challenge, please:
            - Wait for the challenge to appear fully
            - If there's a CAPTCHA, solve it carefully
            - If there's a "I am human" button, click it
            - Wait for verification to complete before continuing
            """
            
            # Run the browser agent
            result = await self.browser_agent.run(task)
            
            # Process the results
            jobs = []
            for job_data in result.get("jobs", []):
                jobs.append(RawJobData(
                    title=job_data.get("title", ""),
                    company=job_data.get("company", ""),
                    url=job_data.get("url", ""),
                    source="LinkedIn",
                    location=job_data.get("location", ""),
                    description=job_data.get("description", ""),
                    posted_date=job_data.get("posted_date", ""),
                    raw_data={
                        "origin": "linkedin",
                        "extraction_method": "browser_automation"
                    }
                ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {str(e)}")
            return []
    
    async def _search_indeed(self, query: str, location: str) -> List[RawJobData]:
        """Search for jobs on Indeed using browser automation"""
        if not self.browser_agent:
            logger.warning("Browser agent not initialized, skipping Indeed search")
            return []
        
        try:
            # Construct the search task with Cloudflare handling instructions
            task = f"""
            Search for {query} jobs in {location} on Indeed:
            1. Go to Indeed
            2. If you encounter a Cloudflare verification page:
               - Wait for the challenge to appear fully (at least 5 seconds)
               - If there's a CAPTCHA, solve it carefully
               - If there's a "I am human" verification button, click it
               - Wait for verification to complete (at least 10 seconds)
            3. Once you're on the main Indeed page, enter search query: {query}
            4. Enter location: {location}
            5. Click search
            6. For each job listing:
               - Extract job title
               - Extract company name
               - Extract location
               - Extract job description
               - Extract application URL
               - Extract posted date
               - Extract salary if available
            7. Return results as JSON
            """
            
            # Run the browser agent
            result = await self.browser_agent.run(task)
            
            # Check if we need to handle Cloudflare challenge
            if "cloudflare_challenge" in result and result["cloudflare_challenge"] == True:
                # Handle the Cloudflare challenge
                challenge_handled = await self._handle_cloudflare_challenge()
                if challenge_handled:
                    # Retry the search after handling the challenge
                    result = await self.browser_agent.run(task)
            
            # Process the results
            jobs = []
            for job_data in result.get("jobs", []):
                jobs.append(RawJobData(
                    title=job_data.get("title", ""),
                    company=job_data.get("company", ""),
                    url=job_data.get("url", ""),
                    source="Indeed",
                    location=job_data.get("location", ""),
                    description=job_data.get("description", ""),
                    posted_date=job_data.get("posted_date", ""),
                    salary=job_data.get("salary", ""),
                    raw_data={
                        "origin": "indeed",
                        "extraction_method": "browser_automation"
                    }
                ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error searching Indeed: {str(e)}")
            return []
    
    async def _apply_to_job(self, job: RawJobData, resume_path: str) -> Dict[str, Any]:
        """Apply to a job using browser automation"""
        if not self.browser_agent:
            logger.warning("Browser agent not initialized, skipping job application")
            return {"success": False, "error": "Browser agent not initialized"}
        
        try:
            # Construct the application task
            task = f"""
            Apply to the following job:
            Title: {job.title}
            Company: {job.company}
            URL: {job.url}
            
            Steps:
            1. Go to the job application page
            2. If you encounter a Cloudflare verification page:
               - Wait for the challenge to appear fully
               - If there's a CAPTCHA, solve it carefully
               - If there's a "I am human" verification button, click it
               - Wait for verification to complete
            3. Fill out the application form
            4. Upload resume from {resume_path}
            5. Submit the application
            6. Return application status
            """
            
            # Run the browser agent
            result = await self.browser_agent.run(task)
            
            return {
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "job": job.dict()
            }
            
        except Exception as e:
            logger.error(f"Error applying to job: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process job search and applications using browser automation
        
        Args:
            state: Current state with query and other information
            
        Returns:
            Updated state with job listings and application results
        """
        try:
            search_state = JobSearchState(**state)
            logger.info(f"Processing browser-based job search for query: {search_state.query}")
            
            # Search for jobs on different platforms
            linkedin_jobs = await self._search_linkedin(search_state.query, search_state.location)
            indeed_jobs = await self._search_indeed(search_state.query, search_state.location)
            
            # Combine results
            all_jobs = linkedin_jobs + indeed_jobs
            
            # Update state with results
            search_state.browser_jobs = all_jobs
            
            # If resume path is provided and auto_apply is True, apply to jobs
            if hasattr(search_state, 'resume_path') and hasattr(search_state, 'auto_apply'):
                if search_state.resume_path and search_state.auto_apply:
                    application_results = []
                    for job in all_jobs[:3]:  # Limit to first 3 jobs
                        result = await self._apply_to_job(job, search_state.resume_path)
                        application_results.append(result)
                    search_state.application_results = application_results
            
            logger.info(f"Found {len(all_jobs)} jobs using browser automation")
            return search_state.model_dump()
            
        except Exception as e:
            return self.handle_error(e, state) 