import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from core.ai.agents.browser_agent import BrowserAgent
from core.ai.agents.company_collector import CompanyWebsiteCollector
from core.ai.agents.extractor_agent import ExtractorAgent
from core.ai.agents.job_listing_collector import JobListingWebsiteCollector
from core.ai.agents.news_collector import NewsAndAdsCollector
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
        self.browser_agent = BrowserAgent()
        self.extractor_agent = ExtractorAgent()
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
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
        # graph.add_node("browser_agent", self.browser_agent.process)
        graph.add_node("extractor", self.extractor_agent.process)
        
        # Define the edges (parallel execution for collectors)
        # Start -> All collectors
        graph.add_edge("__start__", "company_collector")
        graph.add_edge("__start__", "job_listing_collector")
        graph.add_edge("__start__", "news_collector")
        # graph.add_edge("__start__", "browser_agent")
        
        # All collectors -> Extractor (using conditional routing to wait for all collectors)
        graph.add_conditional_edges(
            "company_collector",
            self._check_all_collectors_done,
            {
                True: "extractor",
                False: "company_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("company_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "job_listing_collector",
            self._check_all_collectors_done,
            {
                True: "extractor",
                False: "job_listing_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("job_listing_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "news_collector",
            self._check_all_collectors_done,
            {
                True: "extractor",
                False: "news_collector_wait"  # Wait for other collectors
            }
        )
        graph.add_node("news_collector_wait", lambda x: x)
        
        graph.add_conditional_edges(
            "browser_agent",
            self._check_all_collectors_done,
            {
                True: "extractor",
                False: "browser_agent_wait"  # Wait for other collectors
            }
        )
        graph.add_node("browser_agent_wait", lambda x: x)
        
        # Extractor -> End
        graph.add_edge("extractor", END)
        
        return graph
    
    def _check_all_collectors_done(self, state: JobSearchState) -> bool:
        """
        Check if all collectors have completed their work
        
        Args:
            state: Current state of the workflow
            
        Returns:
            bool: True if all collectors are done, False otherwise
        """
        # Check if all collectors have completed
        collectors_done = (
            hasattr(state, 'company_jobs') and
            hasattr(state, 'job_listing_jobs') and
            hasattr(state, 'news_jobs') and
            hasattr(state, 'browser_jobs')
        )
        
        return collectors_done
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the job search workflow
        
        Args:
            initial_state: Initial state for the workflow
            
        Returns:
            Final state after workflow completion
        """
        try:
            # Convert initial state to JobSearchState
            search_state = JobSearchState(**initial_state)
            
            # Run the workflow
            final_state = await self.workflow.invoke(search_state)
            
            return final_state
            
        except Exception as e:
            logger.error(f"Error running job search workflow: {str(e)}")
            return {"error": str(e)} 