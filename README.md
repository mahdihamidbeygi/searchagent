# Search Agent with Agentic RAG

A flexible job search agent built with Django, REST API, and configurable search providers (Brave, DuckDuckGo, Google).

## Features

- **Agentic Job Search**: Intelligent job search that understands natural language queries and returns structured results
- **Multiple Search Providers**: Configurable search providers to optimize for cost and quality
- **LLM-powered Query Processing**: Process natural language job queries into structured parameters
- **Vector Storage**: Store and retrieve job search results efficiently
- **REST API**: Easy integration with any frontend
- **Django Admin**: Manage users, search queries, and results
- **Configurable via Environment Variables**: Switch search providers without code changes

## Installation

1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on `.env.example` and add your API keys
5. Run database migrations:
   ```
   python manage.py migrate
   ```
6. Start the development server:
   ```
   python manage.py runserver
   ```

## Environment Variables

Configure your search providers by setting the following environment variables:

```
# Search Provider Configuration
SEARCH_PROVIDER=duckduckgo  # Options: duckduckgo, brave, google
BRAVE_API_KEY=your-brave-api-key  # Only needed if using Brave
GOOGLE_API_KEY=your-google-api-key  # Required for LLM and Google search
GOOGLE_CSE_ID=your-google-custom-search-engine-id  # Required for Google search
```

## API Endpoints

### Agentic Job Search

- **POST** `/api/agentic-jobs/search/`
  - Request:
    ```json
    {
      "query": "geophysics jobs in Canada"
    }
    ```
  - Response:
    ```json
    {
      "query": "geophysics jobs in Canada",
      "structured_query": {
        "job_title": "geophysics",
        "location": "Canada"
      },
      "answer": "I found several geophysics job opportunities in Canada...",
      "results": [
        {
          "id": 1,
          "title": "Geophysicist",
          "company": "ABC Energy",
          "location": "Calgary, AB",
          "description": "...",
          "url": "https://example.com/job1",
          "source": "brave"
        }
      ]
    }
    ```

- **GET** `/api/agentic-jobs/history/`
  - Returns the user's previously found job listings

### Traditional Job Search (Legacy)

- **POST** `/api/jobs/search/`
- **GET** `/api/jobs/history/`

### General Search

- **POST** `/api/search/search/`
- **GET** `/api/search/history/`
- **POST** `/api/search/{result_id}/feedback/`

## Usage Example

```python
import requests

# Configure API client
base_url = "http://localhost:8000/api"
headers = {
    "Authorization": "Token YOUR_AUTH_TOKEN",
    "Content-Type": "application/json"
}

# Perform job search
response = requests.post(
    f"{base_url}/agentic-jobs/search/",
    headers=headers,
    json={"query": "remote machine learning engineer with 5 years experience"}
)

# Process results
data = response.json()
print(f"Structured query: {data['structured_query']}")
print(f"Answer: {data['answer']}")
print(f"Found {len(data['results'])} job listings")

# Display job listings
for job in data['results']:
    print(f"- {job['title']} at {job['company']} ({job['location']})")
    print(f"  URL: {job['url']}")
```

## Architecture

The agentic job search implementation uses a flexible architecture:

1. **Query Processing**: User query is processed by LLM to extract structured job search parameters
2. **Search Provider Layer**: Abstract search provider interface allows switching between providers
3. **Result Processing**: Search results are processed, structured, and stored in vector database
4. **Response Generation**: LLM generates a comprehensive answer based on search results
5. **Storage**: Structured job listings are saved to database for future reference

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

# LinkedIn Job Scraper

A robust LinkedIn job scraper for extracting detailed job information based on search queries.

## Features

- Search for jobs based on keywords and location
- Filter by job type, experience level, date posted, and remote work options
- Extract detailed job information including title, company, location, description, and more
- Identify skills and requirements using AI analysis
- Handle pagination to scrape multiple pages of results
- Anti-detection measures to avoid being blocked

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure you have Chrome/Chromium installed on your system
4. Install the appropriate ChromeDriver for your Chrome version

## Usage

### As a standalone script

You can use the test script to run the scraper directly:

```bash
python tests/test_linkedin_scraper.py --query "Software Engineer" --location "New York" --max-pages 2 --limit 5
```

Arguments:
- `--query`: Job search keywords (required)
- `--location`: Location for job search (optional)
- `--max-pages`: Maximum number of pages to scrape (default: 2)
- `--limit`: Maximum number of jobs to return (default: 5)
- `--output`: Output JSON file path (default: linkedin_jobs.json)

### In your code

```python
from core.services.linkedin_scraper import LinkedInJobScraper

# Initialize the scraper
scraper = LinkedInJobScraper(headless=True, slow_mo=0.5, page_load_timeout=40)

try:
    # Define filters
    filters = {
        "time": "month",  # day, week, month
        "experience": ["entry", "associate", "mid-senior"],  # internship, entry, associate, mid-senior, director, executive
        "job_type": ["full_time", "contract"],  # full_time, part_time, contract, temporary, internship, volunteer
        "remote": ["remote", "hybrid"]  # on_site, remote, hybrid
    }
    
    # Search for jobs
    jobs = scraper.search_jobs(
        query="Software Engineer",
        location="San Francisco",
        max_pages=2,
        limit=10,
        filters=filters
    )
    
    # Process results
    for job in jobs:
        print(f"{job['title']} - {job['company']} ({job['location']})")
        print(f"URL: {job['source_url']}")
        print(f"Description: {job['description'][:100]}...")
        print()
        
finally:
    # Always close the scraper to release resources
    scraper.close()
```

## Integration with Job Search Agents

This scraper is designed to integrate with the SearchAgent framework. It's used by the `JobListingWebsiteCollector` agent to collect job listings from LinkedIn.

```python
from core.ai.agents.job_listing_collector import JobListingWebsiteCollector

# Create the collector agent
collector = JobListingWebsiteCollector()

# Run the agent with a query and industry
state = {
    "query": "Machine Learning Engineer",
    "industry": "Healthcare"
}

# Process the query
results = collector.process(state)

# Access the collected job listings
for job in results["listing_jobs"]:
    print(f"{job.title} - {job.company} ({job.location})")
```

## Avoiding Detection

The scraper includes several anti-detection measures:

1. User-agent rotation
2. Headless mode (can be disabled)
3. Slow page navigation with random delays
4. WebDriver signature masking
5. Throttling requests to avoid being rate-limited

## Notes

- This tool is for educational purposes only
- Use responsibly and respect LinkedIn's terms of service
- Consider using LinkedIn's official API for production applications

## Requirements

- Python 3.7+
- Selenium
- BeautifulSoup4
- Chrome/Chromium
- ChromeDriver compatible with your Chrome version

# Search Agent with Cloudflare Bypass Capabilities

This project includes a browser automation agent using the browser-use framework with enhanced capabilities to bypass Cloudflare verification challenges.

## Features

- Browser automation for job searches and web scraping
- Cloudflare verification bypass mechanisms
- Stealth browser configurations to avoid bot detection
- CAPTCHA handling instructions

## Installation

1. Clone the repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Required Dependencies

- browser-use
- selenium-stealth
- undetected-chromedriver
- fake-useragent
- langchain-openai
- python-dotenv

## Bypassing Cloudflare Verification

The agent uses several techniques to bypass Cloudflare's bot detection:

1. **Stealth Mode**: Prevents Cloudflare from detecting automation
2. **Custom User-Agent**: Uses a modern browser user-agent
3. **Non-Headless Mode**: Operating in visible browser mode reduces detection
4. **Automation Flag Removal**: Removes WebDriver flags that Cloudflare checks
5. **Human-like Delays**: Adds random delays between actions
6. **JavaScript Execution**: Ensures proper handling of Cloudflare's JavaScript challenges
7. **CAPTCHA Handling**: Includes instructions for handling CAPTCHAs when they appear

## Usage

Run the test browser agent to see the Cloudflare bypass in action:

```bash
python core/ai/agents/test_browser_agent.py
```

## Implementing in Your Code

You can integrate Cloudflare bypass capabilities in your own code:

```python
from browser_use import Agent
from langchain_openai import ChatOpenAI

agent = Agent(
    task="your task here",
    llm=ChatOpenAI(model="gpt-4o"),
    browser_config={
        "stealth_mode": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "headless": False,
        "disable_automation_control": True,
        "disable_dev_shm_usage": True,
        "enable_javascript": True,
        "wait_for_navigation": 10,
        "wait_for_page_load": True,
        "action_delay": [1, 3],
    }
)
```

## Troubleshooting

If you're still encountering Cloudflare challenges:

1. Ensure you're using the latest Chrome/Chromium version
2. Check that your chromedriver version matches your Chrome version
3. Try using a different IP address or proxy
4. Add additional stealth configurations
5. Consider using rotating user agents and headers

## Ethical Use

This tool is designed for legitimate testing and automation purposes. Always:

1. Respect website terms of service
2. Implement rate limiting
3. Only use for legitimate automation purposes
4. Do not use for scraping sites that explicitly prohibit it

## License

This project is for educational purposes only. Use responsibly. 