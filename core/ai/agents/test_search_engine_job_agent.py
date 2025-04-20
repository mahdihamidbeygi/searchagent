import json
import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ai.agents.search_engine_job_agent import SearchEngineJobAgent
from core.ai.agents.state import JobSearchState, RawJobData
from search_agent.settings import BRAVE_WEBSEARCH_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID

class TestSearchEngineJobAgent(unittest.TestCase):
    """Test cases for the SearchEngineJobAgent"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.agent = SearchEngineJobAgent()
        
        # Create a basic test state
        self.test_state = {
            "query": "software engineer",
            "industry": "tech"
        }
    
    @patch('requests.get')
    def test_search_google(self, mock_get):
        """Test Google search functionality"""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Software Engineer at Google",
                    "link": "https://example.com/job/1",
                    "snippet": "We are looking for a talented Software Engineer"
                },
                {
                    "title": "Amazon - Software Developer",
                    "link": "https://example.com/job/2",
                    "snippet": "Join our team as a Software Developer"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Set API keys for testing
        self.agent.api_keys["Google"]["api_key"] = GOOGLE_API_KEY
        self.agent.api_keys["Google"]["cx"] = GOOGLE_CSE_ID
        
        # Test the search
        engine = {"name": "Google", "search_url": "https://www.googleapis.com/customsearch/v1"}
        results = self.agent._search_google(engine, "software engineer", "tech")
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Software Engineer at Google")
        self.assertEqual(results[0].company, "Google")
        self.assertEqual(results[0].url, "https://example.com/job/1")
        self.assertEqual(results[0].source, "Google")
        
        self.assertEqual(results[1].title, "Amazon - Software Developer")
        self.assertEqual(results[1].company, "Amazon")
        self.assertEqual(results[1].url, "https://example.com/job/2")
        
        # Verify the API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        self.assertEqual(call_args["url"], "https://www.googleapis.com/customsearch/v1")
        self.assertEqual(call_args["params"]["key"], GOOGLE_API_KEY)
        self.assertEqual(call_args["params"]["cx"], GOOGLE_CSE_ID)
        self.assertIn("software engineer", call_args["params"]["q"])
        self.assertIn("tech", call_args["params"]["q"])
    
    @patch('requests.get')
    def test_search_brave(self, mock_get):
        """Test Brave search functionality"""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Senior Developer Position at LinkedIn",
                        "url": "https://linkedin.com/jobs/view/123",
                        "description": "LinkedIn is hiring a Senior Developer"
                    },
                    {
                        "title": "Indeed - Junior Engineer",
                        "url": "https://indeed.com/jobs/456",
                        "description": "Entry-level engineering position"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # Set API key for testing
        self.agent.api_keys["Brave"]["api_key"] = BRAVE_WEBSEARCH_API_KEY
        
        # Test the search
        engine = {"name": "Brave", "search_url": "https://api.search.brave.com/res/v1/web/search"}
        results = self.agent._search_brave(engine, "developer", "software")
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Senior Developer Position at LinkedIn")
        self.assertEqual(results[0].company, "LinkedIn")
        self.assertEqual(results[0].url, "https://linkedin.com/jobs/view/123")
        self.assertEqual(results[0].source, "Brave")
        
        # Verify the API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        self.assertEqual(call_args["url"], "https://api.search.brave.com/res/v1/web/search")
        self.assertEqual(call_args["headers"]["X-Subscription-Token"], BRAVE_WEBSEARCH_API_KEY)
        self.assertIn("developer", call_args["params"]["q"])
        self.assertIn("jobs", call_args["params"]["q"])
    
    @patch('requests.get')
    def test_search_duckduckgo(self, mock_get):
        """Test DuckDuckGo search functionality"""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Results": [
                {
                    "Text": "Data Scientist at Netflix",
                    "FirstURL": "https://netflix.com/jobs/123",
                    "Abstract": "Join our data science team"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test the search
        engine = {"name": "DuckDuckGo", "search_url": "https://api.duckduckgo.com/"}
        results = self.agent._search_duckduckgo(engine, "data scientist", None)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Data Scientist at Netflix")
        self.assertEqual(results[0].company, "Netflix")
        self.assertEqual(results[0].url, "https://netflix.com/jobs/123")
        self.assertEqual(results[0].source, "DuckDuckGo")
        
        # Verify the API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        self.assertEqual(call_args["url"], "https://api.duckduckgo.com/")
        self.assertIn("data scientist", call_args["params"]["q"])
        self.assertEqual(call_args["params"]["format"], "json")
    
    def test_extract_company_from_title(self):
        """Test company name extraction from job titles"""
        # Test "at" pattern
        title1 = "Software Engineer at Google"
        self.assertEqual(self.agent._extract_company_from_title(title1), "Google")
        
        # Test "-" pattern
        title2 = "Amazon - Senior Developer"
        self.assertEqual(self.agent._extract_company_from_title(title2), "Amazon")
        
        # Test complex title with both patterns
        title3 = "Frontend Developer at Twitter - Remote"
        self.assertEqual(self.agent._extract_company_from_title(title3), "Twitter")
        
        # Test title with no company pattern
        title4 = "DevOps Engineer Required"
        self.assertEqual(self.agent._extract_company_from_title(title4), "")
    
    def test_generate_mock_search_results(self):
        """Test mock search results generation"""
        results = self.agent._generate_mock_search_results("TestEngine", "python developer", 3)
        
        # Verify correct number of results
        self.assertEqual(len(results), 3)
        
        # Verify result structure
        for result in results:
            self.assertIsInstance(result, RawJobData)
            self.assertIn("Python", result.title)  # Title should include query term
            self.assertIsNotNone(result.company)
            self.assertIsNotNone(result.url)
            self.assertEqual(result.source, "TestEngine")
            self.assertIsNotNone(result.description)
            self.assertEqual(result.raw_data["origin"], "testengine_search")
            self.assertEqual(result.raw_data["extraction_method"], "mock")
    
    @patch.object(SearchEngineJobAgent, '_search_engine')
    def test_process(self, mock_search_engine):
        """Test the main process method"""
        # Mock the search engine results
        mock_job1 = RawJobData(
            title="Software Engineer",
            company="Google",
            url="https://example.com/job/1",
            source="Google"
        )
        mock_job2 = RawJobData(
            title="Data Scientist",
            company="Netflix",
            url="https://example.com/job/2",
            source="Brave"
        )
        
        # Configure the mock to return different results for each engine
        def mock_search_side_effect(engine, query, industry):
            if engine["name"] == "Google":
                return [mock_job1]
            elif engine["name"] == "Brave":
                return [mock_job2]
            else:
                return []
                
        mock_search_engine.side_effect = mock_search_side_effect
        
        # Process the test state
        result = self.agent.process(self.test_state)
        
        # Verify the search engine was called for each engine
        self.assertEqual(mock_search_engine.call_count, 3)  # Three search engines
        
        # Verify the state was updated correctly
        result_state = JobSearchState(**result)
        self.assertEqual(len(result_state.search_engine_jobs), 2)
        self.assertEqual(result_state.search_engine_jobs[0].company, "Google")
        self.assertEqual(result_state.search_engine_jobs[1].company, "Netflix")
        
        # Verify query and industry were passed correctly
        for call_args in mock_search_engine.call_args_list:
            self.assertEqual(call_args[1]["query"], "software engineer")
            self.assertEqual(call_args[1]["industry"], "tech")
            
    def test_api_failure_handling(self):
        """Test handling of API failures"""
        # Create a state with mock search engines that will fail
        self.agent.search_engines = [
            {"name": "Google", "search_url": "https://failing-url.example"}
        ]
        
        # Patch the _search_google method to raise an exception
        with patch.object(SearchEngineJobAgent, '_search_google', side_effect=Exception("API connection failed")):
            # Process should handle the error and return a valid state
            result = self.agent.process(self.test_state)
            
            # Verify error was added to the state
            result_state = JobSearchState(**result)
            self.assertGreaterEqual(len(result_state.errors), 1)
            self.assertEqual(result_state.errors[0]["agent"], "SearchEngineJobAgent")
            self.assertEqual(result_state.errors[0]["engine"], "Google")

    def test_real_job_query_with_mocks(self):
        """Test with a realistic job query and industry"""
        # Setup more realistic test data
        real_query = "machine learning engineer"
        real_industry = "healthcare"
        
        test_state = {
            "query": real_query,
            "industry": real_industry
        }
        
        # Mock the search engine methods to prevent actual API calls
        with patch.object(self.agent, '_search_google', return_value=[
            RawJobData(
                title="Senior Machine Learning Engineer at Mayo Clinic",
                company="Mayo Clinic",
                url="https://example.com/job/mayo-ml",
                source="Google",
                description="Using ML to improve healthcare outcomes",
                location="Rochester, MN",
                job_type="Full-time"
            )
        ]), \
        patch.object(self.agent, '_search_brave', return_value=[
            RawJobData(
                title="Cleveland Clinic - Machine Learning Researcher",
                company="Cleveland Clinic",
                url="https://example.com/job/cc-ml",
                source="Brave",
                description="Develop ML models for clinical applications",
                location="Cleveland, OH",
                job_type="Full-time"
            )
        ]), \
        patch.object(self.agent, '_search_duckduckgo', return_value=[
            RawJobData(
                title="AI/ML Engineer at Johns Hopkins Medicine",
                company="Johns Hopkins Medicine",
                url="https://example.com/job/jh-ml",
                source="DuckDuckGo",
                description="Applying ML to medical imaging",
                location="Baltimore, MD",
                job_type="Full-time"
            )
        ]):
            # Process the test state
            result = self.agent.process(test_state)
            
            # Verify the state was updated correctly
            result_state = JobSearchState(**result)
            
            # Should have 3 jobs, one from each engine
            self.assertEqual(len(result_state.search_engine_jobs), 3)
            
            # Verify jobs match the expected companies
            companies = [job.company for job in result_state.search_engine_jobs]
            self.assertIn("Mayo Clinic", companies)
            self.assertIn("Cleveland Clinic", companies)
            self.assertIn("Johns Hopkins Medicine", companies)
            
            # Verify all jobs are related to healthcare
            for job in result_state.search_engine_jobs:
                self.assertIsNotNone(job.description)
                self.assertIsNotNone(job.location)
                
            # Verify no errors occurred
            self.assertEqual(len(result_state.errors), 0)
            
    @unittest.skip("This test makes real API calls and should only be run manually")
    def test_live_api_call(self):
        """Test with real API calls - SKIPPED BY DEFAULT
        
        This test makes actual API calls and should only be run manually when needed.
        To run: 
        python -m unittest core.ai.agents.test_search_engine_job_agent.TestSearchEngineJobAgent.test_live_api_call
        """
        # Only run the test if we have valid API keys
        if not all([
            self.agent.api_keys["Google"]["api_key"], 
            self.agent.api_keys["Google"]["cx"],
            self.agent.api_keys["Brave"]["api_key"]
        ]):
            self.skipTest("API keys not configured for live testing")
        
        # Use a real query that should return job results
        live_test_state = {
            "query": "python developer",
            "industry": "technology"
        }
        
        # Process using actual API calls
        result = self.agent.process(live_test_state)
        result_state = JobSearchState(**result)
        
        # Print some information about the results for manual inspection
        print(f"\nLive API test results:")
        print(f"Found {len(result_state.search_engine_jobs)} jobs")
        
        # Group jobs by source
        jobs_by_source = {}
        for job in result_state.search_engine_jobs:
            if job.source not in jobs_by_source:
                jobs_by_source[job.source] = []
            jobs_by_source[job.source].append(job)
        
        for source, jobs in jobs_by_source.items():
            print(f"\n{source} results ({len(jobs)}):")
            for i, job in enumerate(jobs[:3], 1):  # Show up to 3 jobs per source
                print(f"  {i}. {job.title} - {job.company}")
                print(f"     URL: {job.url}")
        
        # Basic assertions to verify functionality
        self.assertGreaterEqual(len(result_state.search_engine_jobs), 1, 
                               "Should find at least one job")
        
        # Check if we have results from multiple engines
        sources = set(job.source for job in result_state.search_engine_jobs)
        self.assertGreaterEqual(len(sources), 1, 
                               "Should have results from at least one search engine")

if __name__ == "__main__":
    unittest.main() 