import os
import json
import logging
import traceback
import argparse
from pathlib import Path
from core.ai.agents.news_collector import NewsAndAdsCollector
from core.ai.agents.state import JobSearchState, RawJobData

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Test the NewsAndAdsCollector agent with a sample search query"""
    
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Test the NewsAndAdsCollector agent')
        parser.add_argument('--query', type=str, default='software engineer',
                            help='Job search query (default: "software engineer")')
        parser.add_argument('--industry', type=str, default='artificial intelligence',
                            help='Industry for the job search (default: "artificial intelligence")')
        parser.add_argument('--config', type=str, default=None,
                            help='Path to config file with API keys')
        args = parser.parse_args()
        
        # Check for API key
        api_key = os.environ.get("NEWS_API_KEY", "")
        config_path = args.config
        
        if not api_key and not config_path:
            # Check for default config file
            default_paths = [
                Path("api_keys.json"),
                Path("config/api_keys.json"),
                Path(os.path.expanduser("~/.searchagent/api_keys.json"))
            ]
            
            for path in default_paths:
                if path.exists():
                    config_path = str(path)
                    print(f"Found config file at: {config_path}")
                    break
        
        if not api_key and not config_path:
            print("WARNING: No NEWS_API_KEY found in environment or config files. Will use simulated data.")
        
        # Initialize the news collector agent
        collector = NewsAndAdsCollector(config_path=config_path)
        
        # Create initial state
        initial_state = {
            "query": args.query,
            "industry": args.industry
        }
        
        # Process the search query
        print(f"Searching for '{args.query}' jobs in '{args.industry}' industry in news articles...")
        results = collector.process(initial_state)
        
        # Debug: print full results structure
        print("\nResult structure:")
        for key, value in results.items():
            print(f"  {key}: {type(value)} with {len(value) if hasattr(value, '__len__') else 'N/A'} items")
        
        # Get the news jobs from results
        news_jobs = results.get("news_jobs", [])
        print(f"\nRaw news_jobs type: {type(news_jobs)}")
        
        if not news_jobs:
            print("No job opportunities found in news articles.")
            return
        
        # Display results
        print(f"\nFound {len(news_jobs)} job opportunities in news articles:")
        
        for i, job in enumerate(news_jobs, 1):
            try:
                # Convert dict to RawJobData if needed
                if isinstance(job, dict):
                    job = RawJobData(**job)
                
                print(f"\nJob {i}:")
                print(f"  Title: {job.title}")
                print(f"  Company: {job.company}")
                print(f"  Source: {job.source}")
                print(f"  Posted: {job.posted_date}")
                print(f"  URL: {job.url}")
                
                # Truncate description if too long
                description = job.description
                if description and len(description) > 100:
                    description = description[:97] + "..."
                print(f"  Description: {description}")
            except Exception as e:
                print(f"Error processing job {i}: {str(e)}")
                print(f"Job data: {job}")
    
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 