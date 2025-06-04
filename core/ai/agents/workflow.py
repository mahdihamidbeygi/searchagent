import logging
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from core.ai.agents.company_collector import CompanyWebsiteCollector
from core.ai.agents.extractor_agent import ExtractorAgent
from core.ai.agents.job_listing_collector import JobListingWebsiteCollector
from core.ai.agents.news_collector import NewsAndAdsCollector
from core.ai.agents.search_engine_job_agent import SearchEngineJobAgent
from core.ai.agents.state import JobSearchState

logger = logging.getLogger(__name__)

class JobSearchWorkflow:
    """
    Manages the workflow of job search agents using LangGraph
    
    This class creates a LangGraph workflow that coordinates the execution
    of multiple agents for collecting and processing job listings.
    """
    
    def __init__(self):
        """Initialize the job search workflow"""
        logger.info("Initializing JobSearchWorkflow")
        
        # Initialize the agents
        self.company_collector = CompanyWebsiteCollector()
        self.job_listing_collector = JobListingWebsiteCollector()
        self.news_collector = NewsAndAdsCollector()
        self.search_engine_agent = SearchEngineJobAgent()
        self.extractor_agent = ExtractorAgent()
        
        # Build the workflow graph
        self.workflow = self._build_workflow()

        # Compile the graph with the custom checkpointer
        self.app = self.workflow.compile()

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow
        
        Returns:
            StateGraph: The configured workflow graph
        """
        # Define the graph
        graph = StateGraph(JobSearchState)
        
        # Add nodes for each agent
        graph.add_node("company_collector", self.company_collector.process)
        graph.add_node("job_listing_collector", self.job_listing_collector.process)
        graph.add_node("news_collector", self.news_collector.process)
        graph.add_node("search_engine_agent", self.search_engine_agent.process)
        graph.add_node("extractor", self.extractor_agent.process)
        
        # Define the edges (parallel execution for collectors)
        # Start -> All collectors
        graph.add_edge("__start__", "company_collector")
        graph.add_edge("__start__", "job_listing_collector")
        graph.add_edge("__start__", "news_collector")
        graph.add_edge("__start__", "search_engine_agent")
        
        # All collectors -> Extractor (using conditional routing to wait for all collectors)
        graph.add_conditional_edges(
            "company_collector",
            self._check_all_collectors_done,
            {
                "end": "extractor",
                "continue": "company_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("company_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "job_listing_collector",
            self._check_all_collectors_done,
            {
                "end": "extractor",
                "continue": "job_listing_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("job_listing_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "news_collector",
            self._check_all_collectors_done,
            {
                "end": "extractor",
                "continue": "news_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("news_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "search_engine_agent",
            self._check_all_collectors_done,
            {
                "end": "extractor",
                "continue": "search_engine_agent_wait"  # Wait for other collectors
            }
        )
        graph.add_node("search_engine_agent_wait", lambda x: x)

        # # LangGraph will implicitly wait for all these predecessors to complete
        # # before running the 'extractor' node.
        # graph.add_edge("company_collector", "extractor")
        # graph.add_edge("job_listing_collector", "extractor")
        # graph.add_edge("news_collector", "extractor")
        # graph.add_edge("search_engine_agent", "extractor")        
        # Extractor -> End
        graph.add_edge("extractor", END)
        
        return graph
    
    def _check_all_collectors_done(self, search_state: JobSearchState) -> str:
        """
        Check if all job collectors have completed their tasks.
        
        Args:
            search_state: The current job search state.
            
        Returns:
            "continue" if any collectors still need to run, "end" otherwise.
        """
        # Check if search engine jobs have been collected
        if not search_state.search_engine_jobs:
            return "continue"
            
        # Check if company jobs need to be collected and have been
        if not search_state.company_jobs:
            return "continue"
            
        # Check if news jobs have been collected
        if not search_state.news_jobs:
            return "continue"
            
        # All collectors have run
        return "end"
    
    async def run(self, search_state:JobSearchState) -> JobSearchState:
        """
        Run the job search workflow.
        
        Args:
            search_state (JobSearchState): The initial state for the workflow.
        )
        Returns:
            The final state after the workflow completes.
        """

        final_state = await self.app.ainvoke(search_state)
        return final_state 