from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobRecord(BaseModel):
    """Standardized job record format"""
    title: str
    company: str
    location: str = "N/A"
    description: str = ""
    url: str
    source: str
    posted_date: Optional[str] = None
    salary: str = "N/A"
    job_type: str = "N/A"
    requirements: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0

class RawJobData(BaseModel):
    """Raw job data format from collector agents"""
    title: str
    company: str
    url: str
    source: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    posted_date: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class JobSearchState(BaseModel):
    """State object for the job search workflow"""
    # Input parameters
    query: str
    industry: Optional[str] = None
    
    # Collector agent results
    company_jobs: List[RawJobData] = Field(default_factory=list)
    listing_jobs: List[RawJobData] = Field(default_factory=list)
    news_jobs: List[RawJobData] = Field(default_factory=list)
    
    # Extractor agent results
    standardized_jobs: List[JobRecord] = Field(default_factory=list)
    
    # Error tracking
    errors: List[Dict[str, str]] = Field(default_factory=list)
    
    def get_all_raw_jobs(self) -> List[RawJobData]:
        """Get all raw job data from all collector agents"""
        return self.company_jobs + self.listing_jobs + self.news_jobs 