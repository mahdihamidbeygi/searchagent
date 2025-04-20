#!/usr/bin/env python
"""
Script to run the news collector test.
Usage: python run_news_collector.py [--query QUERY] [--industry INDUSTRY] [--config CONFIG_PATH]

Examples:
  python run_news_collector.py
  python run_news_collector.py --query "data scientist" --industry "fintech"
  python run_news_collector.py --config path/to/api_keys.json
"""

import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import and run the test function
from tests.test_news_collector import main

if __name__ == "__main__":
    main() 