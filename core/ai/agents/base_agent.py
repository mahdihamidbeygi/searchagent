import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from core.ai.agents.state import JobSearchState  # Import JobSearchState

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents in the job search system"""
    
    def __init__(self):
        """Initialize the agent"""
        logger.info(f"Initializing {self.__class__.__name__}")
    
    @abstractmethod
    def process(self, state: JobSearchState) -> Dict[str, Any]:
        """
        Process the current state and return an updated state
        
        Args:
            state: The current JobSearchState object
            
        Returns:
            A dictionary representation of the updated state object
        """
        pass
    
    def handle_error(self, error: Exception, state: JobSearchState) -> Dict[str, Any]:
        """
        Handle any errors that occur during processing
        
        Args:
            error: The exception that occurred
            state: The current state object
            
        Returns:
            A dictionary representation of the updated state object with error information
        """
        logger.error(f"Error in {self.__class__.__name__} processing state for query '{state.query}': {str(error)}")
        errors = state.errors if state.errors else []
        # JobSearchState.errors has a default_factory=list, so it's always a list
        errors.append({
            'agent': self.__class__.__name__,
            'error': str(error)
        })
        return {"errors": errors} 