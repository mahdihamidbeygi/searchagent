import logging
import os
from typing import Any, Dict, List, Optional

from core.ai.agents.state import JobSearchState
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
        logger.info("Initializing AgenticJobSearch")
        self.workflow = JobSearchWorkflow()
    
    async def process_query(self, **kwargs) -> Dict[str, Any]:
        """
        Process a job search query using the multi-agent workflow
        
        Args:
            query: The job search query
            industry: Optional industry to target
            
        Returns:
            Dictionary with formatted job listings and errors (if any)
        """
        try:
            logger.info(f"Processing job search query: {kwargs}")
            
            # Prepare JobSearchState object for the workflow
            query_val = kwargs.get('query', '')
            # 'industry' kwarg is the primary source for JobSearchState.industry
            # 'location' kwarg might be used by some parts of the query formation,
            # but JobSearchState itself uses 'industry'.
            industry_val = kwargs.get('industry', None) 
            
            # Create the initial JobSearchState object
            # Other fields like company_jobs, listing_jobs, standardized_jobs, errors
            # will use their default_factory from the JobSearchState model.
            initial_job_search_state = JobSearchState(
                query=query_val,
                industry=industry_val,
            )
            
            # Run the workflow with the JobSearchState object
            # The workflow.run method expects a JobSearchState object.
            final_job_search_state: JobSearchState = await self.workflow.run(initial_job_search_state)
           
            # Format the result for the API response
            formatted_result = self._format_result(final_job_search_state, query_val)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error in AgenticJobSearch.process_query: {str(e)}")
            # Include more detailed error information
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            return {
                "query": query_val,
                "structured_query": {"job_title": query_val, "industry": industry_val},
                "results": [],
                "answer": "An error occurred while processing your job search query. Please try again.",
                "errors": [f"Processing error: {str(e)}"]
            }
    
    def _format_result(self, result_state: Any, query: str) -> Dict[str, Any]:
        """
        Format the workflow result for API response
        
        Args:
            result_state: JobSearchState object from the workflow
            query: Original search query
            
        Returns:
            Formatted result for API response
        """
        # Handle case where result_state might be a dictionary or a JobSearchState object
        if hasattr(result_state, 'standardized_jobs'):
            standardized_jobs = result_state.standardized_jobs or []
            industry = getattr(result_state, 'industry', None)
            errors = result_state.errors or []
        elif isinstance(result_state, dict):
            standardized_jobs = result_state.get('standardized_jobs', [])
            industry = result_state.get('industry')
            errors = result_state.get('errors', [])
        else:
            logger.warning(f"Unexpected result_state type: {type(result_state)}")
            standardized_jobs = []
            industry = None
            errors = ["Unexpected result format"]
        
        # Generate an answer based on the jobs found
        if not standardized_jobs:
            answer = "I couldn't find any job listings matching your search criteria."
        else:
            num_jobs = len(standardized_jobs)
            companies = []
            for job in standardized_jobs[:3]:
                if hasattr(job, 'company'):
                    companies.append(job.company)
                elif isinstance(job, dict):
                    companies.append(job.get('company', 'Unknown'))
            top_companies = ", ".join(set(companies))
            
            answer = (
                f"I found {num_jobs} job listings matching your search for '{query}'. "
                f"Top results include positions at {top_companies}. "
                "These listings have been processed and standardized for easy comparison."
            )
        
        # Format job listings for the API response
        formatted_results = []
        for job in standardized_jobs:
            try:
                if hasattr(job, '__dict__'):
                    # Handle object-style job
                    formatted_job = {
                        "title": getattr(job, 'title', ''),
                        "company": getattr(job, 'company', ''),
                        "location": getattr(job, 'location', ''),
                        "description": getattr(job, 'description', ''),
                        "url": getattr(job, 'url', ''),
                        "source": getattr(job, 'source', ''),
                        "posted_date": getattr(job, 'posted_date', None),
                        "salary": getattr(job, 'salary', ''),
                        "job_type": getattr(job, 'job_type', ''),
                        "requirements": getattr(job, 'requirements', []),
                        "benefits": getattr(job, 'benefits', []),
                        "skills": getattr(job, 'skills', []),
                        "relevance_score": getattr(job, 'relevance_score', 0.0),
                        "metadata": {
                            "title": getattr(job, 'title', ''),
                            "source": getattr(job, 'source', ''),
                            "url": getattr(job, 'url', '')
                        }
                    }
                else:
                    # Handle dictionary-style job
                    formatted_job = {
                        "title": job.get('title', ''),
                        "company": job.get('company', ''),
                        "location": job.get('location', ''),
                        "description": job.get('description', ''),
                        "url": job.get('url', ''),
                        "source": job.get('source', ''),
                        "posted_date": job.get('posted_date', None),
                        "salary": job.get('salary', ''),
                        "job_type": job.get('job_type', ''),
                        "requirements": job.get('requirements', []),
                        "benefits": job.get('benefits', []),
                        "skills": job.get('skills', []),
                        "relevance_score": job.get('relevance_score', 0.0),
                        "metadata": {
                            "title": job.get('title', ''),
                            "source": job.get('source', ''),
                            "url": job.get('url', '')
                        }
                    }
                formatted_results.append(formatted_job)
            except Exception as e:
                logger.error(f"Error formatting job: {str(e)}")
                continue
        
        # Return the formatted response
        return {
            "query": query,
            "structured_query": {"job_title": query, "industry": industry},
            "results": formatted_results,
            "answer": answer,
            "errors": errors if isinstance(errors, list) else []
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
                    relevance_score=float(result.get("relevance_score", 0.0))
                )
                
                # Save to the database
                job.save()
                saved_listings.append(job)
                logger.info(f"Successfully saved job listing: {job.title} at {job.company}")
                
            except Exception as e:
                logger.error(f"Error saving job listing: {str(e)}")
                logger.error(f"Problematic result: {result}")
                # Continue with other listings
        
        logger.info(f"Successfully saved {len(saved_listings)} out of {len(results)} job listings")
        return saved_listings