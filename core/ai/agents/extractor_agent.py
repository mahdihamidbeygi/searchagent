import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from core.ai.agents.base_agent import BaseAgent
from core.ai.agents.state import JobRecord, JobSearchState, RawJobData

logger = logging.getLogger(__name__)

class ExtractorAgent(BaseAgent):
    """Agent for processing raw job data into standardized records"""
    
    def __init__(self):
        super().__init__()
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw job data from collector agents into standardized job records
        
        Args:
            state: Current state with raw job data from collector agents
            
        Returns:
            Updated state with standardized job records
        """
        try:
            search_state = JobSearchState(**state)
            logger.info("Processing raw job data into standardized records")
            
            # Get all raw job data from collector agents
            raw_jobs = search_state.get_all_raw_jobs()
            
            # Process each raw job into a standardized record
            standardized_jobs = []
            for raw_job in raw_jobs:
                try:
                    # Convert the raw job data to a standardized record
                    standardized_job = self._process_job(raw_job)
                    standardized_jobs.append(standardized_job)
                except Exception as e:
                    logger.error(f"Error processing job {raw_job.title}: {str(e)}")
                    if 'errors' not in state:
                        state['errors'] = []
                    state['errors'].append({
                        'agent': self.__class__.__name__,
                        'job': raw_job.title,
                        'error': str(e)
                    })
            
            # Deduplicate job listings
            standardized_jobs = self._deduplicate_jobs(standardized_jobs)
            
            # Update the state with standardized job records
            search_state.standardized_jobs = standardized_jobs
            
            logger.info(f"Processed {len(standardized_jobs)} standardized job records")
            return search_state.dict()
            
        except Exception as e:
            return self.handle_error(e, state)
    
    def _process_job(self, raw_job: RawJobData) -> JobRecord:
        """
        Process a raw job into a standardized job record
        
        Args:
            raw_job: Raw job data from a collector agent
            
        Returns:
            Standardized job record
        """
        # Extract requirements and skills from the description
        requirements = self._extract_requirements(raw_job.description or "")
        skills = self._extract_skills(raw_job.description or "")
        benefits = self._extract_benefits(raw_job.description or "")
        
        # Calculate a relevance score (in a real implementation, this would be more sophisticated)
        relevance_score = self._calculate_relevance_score(raw_job)
        
        # Create the standardized job record
        return JobRecord(
            title=raw_job.title,
            company=raw_job.company,
            location=raw_job.location or "N/A",
            description=raw_job.description or "",
            url=raw_job.url,
            source=raw_job.source,
            posted_date=raw_job.posted_date,
            salary=raw_job.salary or "N/A",
            job_type=raw_job.job_type or "N/A",
            requirements=requirements,
            benefits=benefits,
            skills=skills,
            relevance_score=relevance_score
        )
    
    def _extract_requirements(self, description: str) -> List[str]:
        """Extract job requirements from the description"""
        # This is a simplified implementation
        # In a real system, this would use more sophisticated NLP techniques
        requirements = []
        
        # Look for common requirement patterns
        req_patterns = [
            r"Requirements?:(.+?)(?:\n\n|\n[A-Z]|\.$)",
            r"Qualifications?:(.+?)(?:\n\n|\n[A-Z]|\.$)",
            r"What you need:(.+?)(?:\n\n|\n[A-Z]|\.$)",
            r"You should have:(.+?)(?:\n\n|\n[A-Z]|\.$)"
        ]
        
        for pattern in req_patterns:
            matches = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if matches:
                req_text = matches.group(1).strip()
                # Split by bullet points or new lines
                items = re.split(r"•|\*|\n", req_text)
                for item in items:
                    item = item.strip()
                    if item and len(item) > 5:  # Arbitrary minimum length
                        requirements.append(item)
        
        # If no structured requirements found, make a simple guess
        if not requirements and len(description) > 50:
            # Add some generic requirements based on job title
            requirements = [
                "Previous experience in a similar role",
                "Strong communication skills",
                "Problem-solving abilities",
                "Team collaboration"
            ]
        
        return requirements
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract skills from the description"""
        # This is a simplified implementation
        # In a real system, this would use more sophisticated NLP techniques
        
        # Common technical skills to look for
        common_skills = [
            "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "SQL",
            "AWS", "Azure", "GCP", "Docker", "Kubernetes", "React", "Angular",
            "Vue.js", "Node.js", "Express", "Django", "Flask", "Spring",
            "Machine Learning", "AI", "Data Science", "DevOps", "CI/CD",
            "Agile", "Scrum", "Project Management", "Product Management"
        ]
        
        skills = []
        description_lower = description.lower()
        
        for skill in common_skills:
            skill_lower = skill.lower()
            # Check if the skill is mentioned in the description
            if skill_lower in description_lower:
                skills.append(skill)
        
        return skills
    
    def _extract_benefits(self, description: str) -> List[str]:
        """Extract benefits from the description"""
        # This is a simplified implementation
        
        # Common benefits to look for
        common_benefits = [
            "health insurance", "dental", "vision", "401k", "retirement",
            "remote work", "flexible hours", "paid time off", "pto",
            "parental leave", "professional development", "tuition reimbursement",
            "stock options", "equity", "bonus", "gym membership"
        ]
        
        benefits = []
        description_lower = description.lower()
        
        for benefit in common_benefits:
            if benefit in description_lower:
                benefits.append(benefit.title())  # Capitalize for readability
        
        # If we couldn't find any benefits, add some generic ones
        if not benefits:
            benefits = [
                "Competitive Salary",
                "Professional Development Opportunities",
                "Collaborative Work Environment"
            ]
        
        return benefits
    
    def _calculate_relevance_score(self, job: RawJobData) -> float:
        """
        Calculate a relevance score for the job
        
        In a real implementation, this would use more sophisticated techniques,
        possibly involving ML or embeddings to determine relevance.
        """
        # Simple scoring based on data completeness and source
        score = 0.5  # Base score
        
        # Add points for completeness
        if job.description:
            score += 0.1
        if job.location:
            score += 0.05
        if job.posted_date:
            # More recent jobs get higher scores
            try:
                date = datetime.strptime(job.posted_date, "%Y-%m-%d")
                days_old = (datetime.now() - date).days
                score += max(0, 0.1 - (days_old / 100))  # Decay with age
            except:
                # If date parsing fails, just add a small bonus
                score += 0.02
        if job.salary:
            score += 0.05
        if job.job_type:
            score += 0.05
        
        # Adjust score based on source
        source_weights = {
            "LinkedIn": 0.1,
            "Indeed": 0.1,
            "Monster": 0.08,
            "Glassdoor": 0.08,
            "ZipRecruiter": 0.07,
            # News sources get lower weights
            "TechCrunch": 0.05,
            "Business Insider": 0.05,
            "Forbes": 0.04,
            "CNBC": 0.04,
            "The Verge": 0.03
        }
        
        # Add source-specific weight
        score += source_weights.get(job.source, 0.02)
        
        # Ensure score is between 0 and 1
        return min(1.0, max(0.0, score))
    
    def _deduplicate_jobs(self, jobs: List[JobRecord]) -> List[JobRecord]:
        """
        Remove duplicate job listings
        
        Args:
            jobs: List of standardized job records
            
        Returns:
            Deduplicated list of job records
        """
        # Simple deduplication based on URL and title+company
        unique_jobs = {}
        
        for job in jobs:
            # Create a key based on URL or title+company if URL might vary
            key = job.url
            alt_key = f"{job.title.lower()}_{job.company.lower()}"
            
            # If we haven't seen this job before, or this one has a higher relevance score
            if (key not in unique_jobs and alt_key not in unique_jobs) or \
               (key in unique_jobs and job.relevance_score > unique_jobs[key].relevance_score) or \
               (alt_key in unique_jobs and job.relevance_score > unique_jobs[alt_key].relevance_score):
                
                # Store by both keys for efficient lookup
                unique_jobs[key] = job
                unique_jobs[alt_key] = job
        
        # Return the unique jobs, sorted by relevance score
        return sorted(
            list({job.url: job for job in unique_jobs.values()}.values()),
            key=lambda j: j.relevance_score,
            reverse=True
        ) 