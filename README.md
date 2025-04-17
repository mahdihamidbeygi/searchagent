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