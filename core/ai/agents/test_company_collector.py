import json
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import google.generativeai as genai

from core.ai.agents.company_collector import CompanyWebsiteCollector
from core.ai.agents.state import JobSearchState, RawJobData


class TestCompanyWebsiteCollector(unittest.TestCase):
    """Tests for the CompanyWebsiteCollector class"""

    def __init__(self):
        """Set up test fixtures"""
        self.collector = CompanyWebsiteCollector()
        self.test_state = {
            "query": "python developer",
            "industry": "technology",
            "location": "remote",
            "company_jobs": []
        }
        self.company = {"name": "Microsoft Corporation careers page", "url": "https://careers.microsoft.com/us/en/job-search"}

    # @patch('google.generativeai.GenerativeModel')
    # def test_search_companies_by_llm_success(self, mock_genai_model):
    #     """Test successful company search using LLM with structured output"""
    #     # Mock response data
    #     mock_companies = [
    #         {"name": "Test Company 1", "url": "https://testcompany1.com/careers"},
    #         {"name": "Test Company 2", "url": "https://testcompany2.com/jobs"}
    #     ]
        
    #     # Create a mock response object that mimics the structure from Gemini
    #     mock_response = MagicMock()
    #     mock_response.candidates = [MagicMock()]
    #     mock_content = MagicMock()
    #     mock_part = MagicMock()
    #     mock_part.text = json.dumps({"companies": mock_companies})
    #     mock_content.parts = [mock_part]
    #     mock_response.candidates[0].content = mock_content
        
    #     # Set up the mock
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.return_value = mock_response
    #     mock_genai_model.return_value = mock_model_instance
        
    #     # Test with an industry not in the predefined list
    #     self.collector.genai_client = mock_model_instance
    #     result = self.collector._search_companies_by_llm("gaming", "game developer")
        
    #     # Verify results
    #     self.assertEqual(len(result), 2)
    #     self.assertEqual(result[0]["name"], "Test Company 1")
    #     self.assertEqual(result[1]["url"], "https://testcompany2.com/jobs")
        
    #     # Verify the model was called with correct parameters
    #     mock_model_instance.generate_content.assert_called_once()
    #     args, kwargs = mock_model_instance.generate_content.call_args
    #     self.assertIn("gaming industry", args[0])
    #     self.assertIn("game developer", args[0])
    #     self.assertIn("response_mime_type", kwargs["generation_config"])
    #     self.assertEqual(kwargs["generation_config"]["response_mime_type"], "application/json")

    # @patch('google.generativeai.GenerativeModel')
    # def test_search_companies_by_llm_fallback(self, mock_genai_model):
    #     """Test fallback to default companies when LLM returns invalid data"""
    #     # Create a mock response object with invalid data
    #     mock_response = MagicMock()
    #     mock_response.candidates = [MagicMock()]
    #     mock_content = MagicMock()
    #     mock_part = MagicMock()
    #     mock_part.text = "Invalid JSON data"
    #     mock_content.parts = [mock_part]
    #     mock_response.candidates[0].content = mock_content
        
    #     # Set up the mock
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.return_value = mock_response
    #     mock_genai_model.return_value = mock_model_instance
        
    #     # Test with an industry not in the predefined list
    #     self.collector.genai_client = mock_model_instance
    #     result = self.collector._search_companies_by_llm("unknown", "job")
        
    #     # Verify fallback to default industry
    #     self.assertEqual(len(result), 5)  # Default tech industry has 5 companies
    #     self.assertEqual(result[0]["name"], "Microsoft")

    # @patch('google.generativeai.GenerativeModel')
    # def test_search_companies_by_llm_empty_response(self, mock_genai_model):
    #     """Test handling of empty company list from LLM"""
    #     # Mock response with empty companies list
    #     mock_response = MagicMock()
    #     mock_response.candidates = [MagicMock()]
    #     mock_content = MagicMock()
    #     mock_part = MagicMock()
    #     mock_part.text = json.dumps({"companies": []})
    #     mock_content.parts = [mock_part]
    #     mock_response.candidates[0].content = mock_content
        
    #     # Set up the mock
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.return_value = mock_response
    #     mock_genai_model.return_value = mock_model_instance
        
    #     # Set the test industry to technology explicitly
    #     self.collector.genai_client = mock_model_instance
    #     result = self.collector._search_companies_by_llm("technology", "cashier")
        
    #     # Verify fallback to default industry
    #     self.assertEqual(len(result), 5)
    #     self.assertEqual(result[0]["name"], "Microsoft")

    # @patch('google.generativeai.GenerativeModel')
    # def test_process_with_successful_search(self, mock_genai_model):
    #     """Test the full process method with successful company search"""
    #     # Mock LLM response
    #     mock_companies = [
    #         {"name": "Tech Corp", "url": "https://techcorp.com/careers"},
    #         {"name": "Dev Solutions", "url": "https://devsolutions.com/jobs"}
    #     ]
        
    #     mock_response = MagicMock()
    #     mock_response.candidates = [MagicMock()]
    #     mock_content = MagicMock()
    #     mock_part = MagicMock()
    #     mock_part.text = json.dumps({"companies": mock_companies})
    #     mock_content.parts = [mock_part]
    #     mock_response.candidates[0].content = mock_content
        
    #     # Set up the mock
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.return_value = mock_response
    #     mock_genai_model.return_value = mock_model_instance
        
    #     # Override the _search_companies_by_llm method to return our mock companies
    #     with patch.object(self.collector, '_search_companies_by_llm', return_value=mock_companies):
    #         # And also mock the _search_company_website method
    #         with patch.object(self.collector, '_search_company_website') as mock_search_website:
    #             # Return some mock job data
    #             mock_search_website.side_effect = lambda company, query: [
    #                 RawJobData(
    #                     title=f"Senior {query} at {company['name']}",
    #                     company=company["name"],
    #                     url=f"{company['url']}/job/1",
    #                     source=company["name"],
    #                     location="Remote",
    #                     description=f"Test job at {company['name']}",
    #                     posted_date="2023-04-15",
    #                     raw_data={"origin": "test"}
    #                 )
    #             ]
                
    #             # Run the process method
    #             self.collector.genai_client = mock_model_instance
    #             result = self.collector.process(self.test_state)
                
    #             # Verify results
    #             self.assertIn("company_jobs", result)
    #             self.assertEqual(len(result["company_jobs"]), 2)  # One job per company
    #             self.assertEqual(result["company_jobs"][0]["company"], "Tech Corp")
    #             self.assertEqual(result["company_jobs"][1]["company"], "Dev Solutions")
                
    #             # Verify the search website method was called for each company
    #             self.assertEqual(mock_search_website.call_count, 2)

    # @patch('google.generativeai.GenerativeModel')
    # def test_process_with_empty_companies(self, mock_genai_model):
    #     """Test the process method when the LLM returns an empty company list"""
    #     # Mock response with empty companies list
    #     mock_response = MagicMock()
    #     mock_response.candidates = [MagicMock()]
    #     mock_content = MagicMock()
    #     mock_part = MagicMock()
    #     mock_part.text = json.dumps({"companies": []})
    #     mock_content.parts = [mock_part]
    #     mock_response.candidates[0].content = mock_content
        
    #     # Set up the mock
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.return_value = mock_response
    #     mock_genai_model.return_value = mock_model_instance
        
    #     # Override the _search_companies_by_llm method to return an empty list
    #     with patch.object(self.collector, '_search_companies_by_llm', return_value=[]):
    #         # And also mock the _search_company_website method
    #         with patch.object(self.collector, '_search_company_website') as mock_search_website:
    #             # Set up the mock to return job data for any company
    #             mock_search_website.side_effect = lambda company, query: [
    #                 RawJobData(
    #                     title=f"Senior {query} at {company['name']}",
    #                     company=company["name"],
    #                     url=f"{company['url']}/job/1",
    #                     source=company["name"],
    #                     location="Remote",
    #                     description=f"Test job at {company['name']}",
    #                     posted_date="2023-04-15",
    #                     raw_data={"origin": "test"}
    #                 )
    #             ]
                
    #             # Run the process method
    #             self.collector.genai_client = mock_model_instance
    #             result = self.collector.process(self.test_state)
                
    #             # Verify that default companies were used
    #             self.assertIn("company_jobs", result)
    #             self.assertEqual(len(result["company_jobs"]), 5)  # 5 default companies
    #             self.assertEqual(result["company_jobs"][0]["company"], "Microsoft")
                
    #             # Verify the search website method was called for each default company
    #             self.assertEqual(mock_search_website.call_count, 5)

    # def test_predefined_industry_companies(self):
    #     """Test using predefined companies for known industries"""
    #     # Test with a known industry
    #     result = self.collector._search_companies_by_llm("finance", "accountant")
        
    #     self.assertEqual(len(result), 5)
    #     self.assertEqual(result[0]["name"], "JPMorgan Chase")
        
    #     # Test with a different known industry
    #     result = self.collector._search_companies_by_llm("healthcare", "nurse")
        
    #     self.assertEqual(len(result), 5)
    #     self.assertEqual(result[0]["name"], "Johnson & Johnson")

    # @patch('google.generativeai.GenerativeModel')
    # def test_exception_handling(self, mock_genai_model):
    #     """Test exception handling during company search"""
    #     # Make the mock throw an exception
    #     mock_model_instance = MagicMock()
    #     mock_model_instance.generate_content.side_effect = Exception("API Error")
    #     mock_genai_model.return_value = mock_model_instance
        
    #     self.collector.genai_client = mock_model_instance
        
    #     # Should fall back to default companies
    #     result = self.collector._search_companies_by_llm("unknown", "job")
        
    #     self.assertEqual(len(result), 5)
    #     self.assertEqual(result[0]["name"], "Microsoft")

    # def test_process_with_real_query(self):
    #     """Test the process method with a real query"""
    #     self.test_state["query"] = "python developer"
    #     self.test_state["industry"] = "technology"
    #     self.test_state["location"] = "remote"
    #     result = self.collector.process(self.test_state)
    #     self.assertIn("company_jobs", result)
    #     self.assertGreater(len(result["company_jobs"]), 0)
    #     # Print first job for debugging
    #     if result["company_jobs"]:
    #         print(f"First job: {result['company_jobs'][0]['title']} at {result['company_jobs'][0]['company']}")

    def test_search_company_website_with_real_query(self):
        """Test the search_company_website method with a real query"""
        result = self.collector._search_company_website(self.company, self.test_state["query"])
        print("result", result)


if __name__ == "__main__":
    # unittest.main() 
    TestCompanyWebsiteCollector().test_search_company_website_with_real_query()