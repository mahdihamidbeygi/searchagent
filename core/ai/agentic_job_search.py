import logging
import os
from typing import Any, Dict, List, Optional

from core.ai.agents.workflow import JobSearchWorkflow
from core.models import JobListing

logger = logging.getLogger(__name__)

class AgenticJobSearch:
    """
    Agentic job search system using multi-agent workflow
    
    This class integrates the LangGraph-based multi-agent job search workflow
    with the Django application, providing a standardized interface for
    searching and storing job listings.
    """
    
    def __init__(self):
        """Initialize the agentic job search system"""
        logger.info("Initializing AgenticJobSearchNew")
        self.workflow = JobSearchWorkflow()
    
    def process_query(self, query: str, industry: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a job search query using the multi-agent workflow
        
        Args:
            query: The job search query
            industry: Optional industry to target
            
        Returns:
            Dictionary with formatted job listings and errors (if any)
        """
        try:
            logger.info(f"Processing job search query: {query}")
            
            # Run the agent workflow
            result = self.workflow.run(query, industry)
            
            # Format the result for the API response
            formatted_result = self._format_result(result, query)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error in AgenticJobSearchNew.process_query: {str(e)}")
            return {
                "query": query,
                "structured_query": {"job_title": query, "industry": industry},
                "results": [],
                "answer": "An error occurred while processing your job search query.",
                "error": str(e)
            }
    
    def _format_result(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Format the workflow result for API response
        
        Args:
            result: Raw result from the workflow
            query: Original search query
            
        Returns:
            Formatted result for API response
        """
        # Extract standardized jobs from the result
        standardized_jobs = result.get("standardized_jobs", [])
        
        # Generate an answer based on the jobs found
        if not standardized_jobs:
            answer = "I couldn't find any job listings matching your search criteria."
        else:
            num_jobs = len(standardized_jobs)
            top_companies = ", ".join(set([job.company for job in standardized_jobs[:3]]))
            
            answer = (
                f"I found {num_jobs} job listings matching your search for '{query}'. "
                f"Top results include positions at {top_companies}. "
                "These listings have been processed and standardized for easy comparison."
            )
        
        # Format job listings for the API response
        formatted_results = []
        for job in standardized_jobs:
            formatted_results.append({
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "url": job.url,
                "source": job.source,
                "posted_date": job.posted_date,
                "salary": job.salary,
                "job_type": job.job_type,
                "requirements": job.requirements,
                "benefits": job.benefits,
                "skills": job.skills,
                "relevance_score": job.relevance_score,
                "metadata": {
                    "title": job.title,
                    "source": job.source,
                    "url": job.url
                }
            })
        
        # Return the formatted response
        return {
            "query": query,
            "structured_query": {"job_title": query, "industry": result.get("industry")},
            "results": formatted_results,
            "answer": answer,
            "errors": result.get("errors", [])
        }
    
    def save_job_listings(self, user_id: int, results: List[Dict[str, Any]]) -> List[JobListing]:
        """
        Save job listings to the database
        
        Args:
            user_id: ID of the user performing the search
            results: List of job listing results
            
        Returns:
            List of saved JobListing objects
        """
        saved_listings = []
        
        for result in results:
            try:
                # Create a new JobListing object
                job = JobListing(
                    user_id=user_id,
                    title=result.get("title", ""),
                    company=result.get("company", ""),
                    location=result.get("location", ""),
                    description=result.get("description", ""),
                    url=result.get("url", ""),
                    source=result.get("source", ""),
                    posted_date=result.get("posted_date") or None,
                    salary=result.get("salary", ""),
                    job_type=result.get("job_type", ""),
                    requirements=result.get("requirements", []),
                    benefits=result.get("benefits", []),
                    skills=result.get("skills", []),
                    relevance_score=result.get("relevance_score", 0.0)
                )
                
                # Save to the database
                job.save()
                saved_listings.append(job)
                
            except Exception as e:
                logger.error(f"Error saving job listing: {str(e)}")
                # Continue with other listings
        
        return saved_listings 