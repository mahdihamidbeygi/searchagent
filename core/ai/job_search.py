import os
import re
from datetime import datetime
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
from serpapi.google_search import GoogleSearch


class JobListing(BaseModel):
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: datetime = Field(default_factory=datetime.now)
    salary: str = ""
    job_type: str = ""
    requirements: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0

class JobSearchAgent:
    def __init__(self):
        self.serpapi_key = os.getenv('SERPAPI_KEY')
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv('GOOGLE_API_KEY')
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

    def search_jobs(self, query: str, location: str = "", num_results: int = 10) -> List[JobListing]:
        """
        Search for jobs using both SerpAPI and DuckDuckGo
        """
        # Combine search results from both providers
        serp_results = self._search_serpapi(query, location, num_results)
        ddg_results = self._search_duckduckgo(query, location, num_results)
        
        # Process and clean the results
        processed_results = []
        for result in serp_results + ddg_results:
            try:
                job_listing = self._process_job_listing(result)
                if job_listing:
                    processed_results.append(job_listing)
            except Exception as e:
                print(f"Error processing job listing: {e}")
                continue
        
        # Remove duplicates and sort by relevance
        unique_jobs = self._remove_duplicates(processed_results)
        return sorted(unique_jobs, key=lambda x: x.relevance_score, reverse=True)

    def _search_serpapi(self, query: str, location: str, num_results: int) -> List[Dict]:
        """Search for jobs using SerpAPI"""
        params = {
            "engine": "google_jobs",
            "q": f"{query} {location}",
            "api_key": self.serpapi_key,
            "num": num_results
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        return results.get("jobs_results", [])

    def _search_duckduckgo(self, query: str, location: str, num_results: int) -> List[Dict]:
        """Search for jobs using DuckDuckGo"""
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f"{query} {location} job listing",
                region="wt-wt",
                safesearch="off",
                timelimit="y",
                max_results=num_results
            ))
        return results

    def _process_job_listing(self, raw_listing: Dict) -> JobListing:
        """Process and clean a job listing"""
        # Extract basic information
        title = raw_listing.get("title", "")
        company = raw_listing.get("company_name", "")
        location = raw_listing.get("location", "")
        description = raw_listing.get("description", "")
        url = raw_listing.get("job_link", "")

        # If description is not available, try to fetch it from the URL
        if not description and url:
            description = self._fetch_job_description(url)

        # Extract additional information using regex and NLP
        salary = self._extract_salary(description)
        job_type = self._extract_job_type(description)
        requirements = self._extract_requirements(description)
        benefits = self._extract_benefits(description)
        skills = self._extract_skills(description)

        # Calculate relevance score
        relevance_score = self._calculate_relevance(title, description)

        return JobListing(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source=raw_listing.get("source", "Unknown"),
            salary=salary,
            job_type=job_type,
            requirements=requirements,
            benefits=benefits,
            skills=skills,
            relevance_score=relevance_score
        )

    def _fetch_job_description(self, url: str) -> str:
        """Fetch job description from URL"""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            return soup.get_text()
        except Exception:
            return ""

    def _extract_salary(self, text: str) -> str:
        """Extract salary information using regex"""
        salary_patterns = [
            r'\$[\d,]+(?:\.\d{2})?(?:\s*-\s*\$[\d,]+(?:\.\d{2})?)?',
            r'\d{2,3}(?:,\d{3})*(?:\s*-\s*\d{2,3}(?:,\d{3})*)?\s*(?:k|K)',
            r'(?:salary|pay|compensation).*?\$[\d,]+'
        ]
        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return ""

    def _extract_job_type(self, text: str) -> str:
        """Extract job type (full-time, part-time, etc.)"""
        job_types = ["full-time", "part-time", "contract", "temporary", "internship"]
        for job_type in job_types:
            if job_type in text.lower():
                return job_type
        return ""

    def _extract_requirements(self, text: str) -> List[str]:
        """Extract job requirements"""
        requirements_section = re.search(r'(?:requirements|qualifications|must have)(.*?)(?:\n\n|\Z)', 
                                       text, re.IGNORECASE | re.DOTALL)
        if requirements_section:
            requirements = re.findall(r'•\s*(.*?)(?=\n|$)', requirements_section.group(1))
            return [req.strip() for req in requirements if req.strip()]
        return []

    def _extract_benefits(self, text: str) -> List[str]:
        """Extract job benefits"""
        benefits_section = re.search(r'(?:benefits|perks|what we offer)(.*?)(?:\n\n|\Z)', 
                                   text, re.IGNORECASE | re.DOTALL)
        if benefits_section:
            benefits = re.findall(r'•\s*(.*?)(?=\n|$)', benefits_section.group(1))
            return [benefit.strip() for benefit in benefits if benefit.strip()]
        return []

    def _extract_skills(self, text: str) -> List[str]:
        """Extract required skills"""
        skills_section = re.search(r'(?:skills|technologies|tools)(.*?)(?:\n\n|\Z)', 
                                 text, re.IGNORECASE | re.DOTALL)
        if skills_section:
            skills = re.findall(r'•\s*(.*?)(?=\n|$)', skills_section.group(1))
            return [skill.strip() for skill in skills if skill.strip()]
        return []

    def _calculate_relevance(self, title: str, description: str) -> float:
        """Calculate relevance score based on title and description"""
        # Simple implementation - can be enhanced with more sophisticated scoring
        title_words = set(title.lower().split())
        desc_words = set(description.lower().split())
        
        intersection = title_words.intersection(desc_words)
        return len(intersection) / len(title_words) if title_words else 0.0

    def _remove_duplicates(self, jobs: List[JobListing]) -> List[JobListing]:
        """Remove duplicate job listings based on title and company"""
        seen = set()
        unique_jobs = []
        for job in jobs:
            key = (job.title.lower(), job.company.lower())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        return unique_jobs 