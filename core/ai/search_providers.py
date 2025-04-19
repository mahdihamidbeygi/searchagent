import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests
from duckduckgo_search import DDGS
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    """Base model for search results from any provider"""
    title: str
    description: str
    url: str
    source: str
    metadata: Dict = {}

class SearchProvider(ABC):
    """Abstract base class for search providers"""
    
    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Search for content using the provider's API"""
        pass

class BraveSearchProvider(SearchProvider):
    """Search provider using Brave Search API"""
    
    def __init__(self):
        self.api_key = os.getenv("BRAVE_WEBSEARCH_API_KEY")
        if not self.api_key:
            logger.warning("BRAVE_API_KEY not found in environment. Some features may be limited.")
        
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Search using Brave Search API"""
        logger.info(f"Searching Brave for: {query}")
        
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            }
            
            params = {
                "q": query,
                "count": min(num_results, 20),  # Brave API limit
                "search_lang": "en"
            }
            
            response = requests.get(
                self.base_url,
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Brave search error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            results = []
            
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    source="brave",
                    metadata={"rank": item.get("rank", 0)}
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Brave: {str(e)}")
            return []

class DuckDuckGoSearchProvider(SearchProvider):
    """Search provider using DuckDuckGo Search"""
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Search using DuckDuckGo"""
        logger.info(f"Searching DuckDuckGo for: {query}")
        
        try:
            results = []
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(
                    query,
                    region="wt-wt",
                    safesearch="off",
                    timelimit="y",
                    max_results=num_results
                ))
                
                for item in ddg_results:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        description=item.get("body", ""),
                        url=item.get("href", ""),
                        source="duckduckgo",
                        metadata={}
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo: {str(e)}")
            return []

class GoogleSearchAPIProvider(SearchProvider):
    """Search provider using Google Custom Search API"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_CSE_ID")
        
        if not self.api_key or not self.search_engine_id:
            logger.warning("GOOGLE_API_KEY or GOOGLE_CSE_ID not found. Google search will be limited.")
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Search using Google Custom Search API"""
        logger.info(f"Searching Google for: {query}")
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": min(num_results, 10)  # Google API limit for free tier
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Google search error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            results = []
            
            for item in data.get("items", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    description=item.get("snippet", ""),
                    url=item.get("link", ""),
                    source="google",
                    metadata={"rank": item.get("rank", 0)}
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Google: {str(e)}")
            return []

def get_search_provider() -> SearchProvider:
    """Factory function to get the configured search provider"""
    provider_name = os.getenv("SEARCH_PROVIDER", "duckduckgo").lower()
    
    if provider_name == "brave":
        return BraveSearchProvider()
    elif provider_name == "google":
        return GoogleSearchAPIProvider()
    else:
        # Default to DuckDuckGo as it doesn't require an API key
        return DuckDuckGoSearchProvider() 