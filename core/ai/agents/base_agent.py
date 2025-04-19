import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents in the job search system"""
    
    def __init__(self):
        """Initialize the agent"""
        logger.info(f"Initializing {self.__class__.__name__}")
    
    @abstractmethod
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the current state and return an updated state
        
        Args:
            state: The current state object containing job search parameters and results
            
        Returns:
            Updated state object with new information from this agent
        """
        pass
    
    def handle_error(self, error: Exception, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle any errors that occur during processing
        
        Args:
            error: The exception that occurred
            state: The current state object
            
        Returns:
            Updated state object with error information
        """
        logger.error(f"Error in {self.__class__.__name__}: {str(error)}")
        if 'errors' not in state:
            state['errors'] = []
        
        state['errors'].append({
            'agent': self.__class__.__name__,
            'error': str(error)
        })
        
        return state 