from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class JobListing:
    """A standalone version of the JobListing model for use without Django"""
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: str
    salary: str = ""
    job_type: str = ""
    requirements: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list) 
    skills: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "posted_date": self.posted_date,
            "salary": self.salary,
            "job_type": self.job_type,
            "requirements": self.requirements,
            "benefits": self.benefits,
            "skills": self.skills,
            "relevance_score": self.relevance_score
        } 