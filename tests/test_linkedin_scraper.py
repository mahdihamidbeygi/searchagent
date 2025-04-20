import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.linkedin_scraper import LinkedInJobScraper

def main():
    """
    Test script for the LinkedIn job scraper.
    
    Usage:
        python test_linkedin_scraper.py --query "Software Engineer" --location "New York" --max-pages 2 --limit 5
    """
    parser = argparse.ArgumentParser(description='Test LinkedIn Job Scraper')
    parser.add_argument('--query', type=str, required=True, help='Job search query')
    parser.add_argument('--location', type=str, default='', help='Location for job search')
    parser.add_argument('--max-pages', type=int, default=2, help='Maximum number of pages to scrape')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of jobs to return')
    parser.add_argument('--output', type=str, default='linkedin_jobs.json', help='Output file for results')
    
    args = parser.parse_args()
    
    # Apply filters based on configuration
    filters = {
        "time": "month",  # Look for jobs posted in the last month
        "experience": ["entry", "associate", "mid-senior"],  # Target mid-level positions
        "job_type": ["full_time", "contract"],  # Focus on full-time and contract roles
        "remote": ["remote", "hybrid"]  # Include remote and hybrid roles
    }
    
    print(f"Searching for '{args.query}' jobs in '{args.location}'...")
    print(f"Max pages: {args.max_pages}, Limit: {args.limit}")
    print(f"Filters: {filters}")
    
    # Initialize scraper
    scraper = LinkedInJobScraper(headless=True)
    
    try:
        # Execute search
        jobs = scraper.search_jobs(
            query=args.query,
            location=args.location,
            max_pages=args.max_pages,
            limit=args.limit,
            filters=filters
        )
        
        # Display results summary
        print(f"\nFound {len(jobs)} jobs matching '{args.query}' in '{args.location or 'any location'}'")
        
        if jobs:
            # Save to JSON file
            with open(args.output, 'w', encoding='utf-8') as f:
                # We need to convert to a serializable format
                serializable_jobs = []
                for job in jobs:
                    # Convert any non-serializable fields (like sets) to lists
                    serializable_job = {}
                    for key, value in job.items():
                        if isinstance(value, set):
                            serializable_job[key] = list(value)
                        else:
                            serializable_job[key] = value
                    serializable_jobs.append(serializable_job)
                
                json.dump(serializable_jobs, f, indent=2)
            
            print(f"Results saved to {args.output}")
            
            # Print job titles
            print("\nJobs found:")
            for i, job in enumerate(jobs, 1):
                print(f"{i}. {job['title']} - {job['company']} ({job['location']})")
                print(f"   Posted: {job['date_text']}")
                print(f"   URL: {job['source_url']}")
                print()
        
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    finally:
        # Always close the scraper to release resources
        scraper.close()

if __name__ == "__main__":
    main() 