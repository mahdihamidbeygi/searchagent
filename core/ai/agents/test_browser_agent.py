import unittest
from unittest.mock import Mock, patch
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ai.agents.browser_agent import BrowserAgent

from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

"""
To run this with Cloudflare bypass capabilities, ensure you have the following dependencies:
pip install browser-use selenium-stealth undetected-chromedriver fake-useragent

For optimal results with Cloudflare challenges:
1. Use a real browser (non-headless mode)
2. Install the latest version of Chrome/Chromium
3. Ensure your chromedriver version matches your Chrome version
"""

async def main():
    # Configure a more advanced agent with Cloudflare bypass capabilities
    agent = Agent(
        task="open indeed and search for 'software engineer' in 'new york'",
        llm=ChatOpenAI(model="gpt-4o"),
        browser_context={
            # Make browser appear more human-like to bypass Cloudflare
            "stealth_mode": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "headless": False,  # Non-headless is less likely to be detected
            "disable_automation_control": True,
            "disable_dev_shm_usage": True,
            "enable_javascript": True,
            "wait_for_navigation": 10,  # Increased wait time for Cloudflare verification to complete
            "wait_for_page_load": True,
            # Adding a delay between actions to appear more human-like
            "action_delay": [1, 3],
        }
    )
    await agent.run()

asyncio.run(main())