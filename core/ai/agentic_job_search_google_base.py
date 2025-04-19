import json
import logging
import os
from typing import Any, Dict, List

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import (ChatGoogleGenerativeAI,
                                    GoogleGenerativeAIEmbeddings)
from pydantic import BaseModel, ConfigDict, Field

from .job_search import JobListing
from .search_providers import SearchResult, get_search_provider

logger = logging.getLogger(__name__)

class JobSearchQuery(BaseModel):
    """Structure for job search queries"""
    job_title: str
    location: str = ""
    skills: List[str] = Field(default_factory=list)
    experience_level: str = ""
    job_type: str = ""
    salary_range: str = ""
    company: str = ""
    
    def to_search_query(self) -> str:
        """Convert structured query to search string"""
        parts = [self.job_title]
        
        if self.location:
            parts.append(f"in {self.location}")
        
        if self.skills:
            parts.append(f"skills: {', '.join(self.skills)}")
        
        if self.experience_level:
            parts.append(self.experience_level)
        
        if self.job_type:
            parts.append(self.job_type)
        
        if self.company:
            parts.append(f"at {self.company}")
        
        return " ".join(parts)

class AgenticJobSearch(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    embeddings: GoogleGenerativeAIEmbeddings = None
    llm: ChatGoogleGenerativeAI = None
    text_splitter: RecursiveCharacterTextSplitter = None
    vector_store: Chroma = None
    query_processor_prompt: str = None
    results_processor_prompt: str = None
    qa_chain: Any = None
    
    def __init__(self, **data):
        super().__init__(**data)
        try:
            # Initialize embeddings and LLM
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=os.getenv('GOOGLE_API_KEY')
            )
            
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=os.getenv('GOOGLE_API_KEY'),
                temperature=0.1,
                max_output_tokens=1024,
                convert_system_message_to_human=True
            )
            
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )
            
            # Initialize vector store
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory="./chroma_db/jobs"
            )
            
            # Define the prompt template for processing search results
            self.results_processor_prompt = """You are an AI job search assistant. Use the following job search results to answer the question at the end.
            If you don't know the answer, just say that you don't know, don't try to make up an answer.
            
            Job Search Results: {context}
            
            Original Query: {question}
            
            Provide a summary of the job opportunities found. Include key information such as job titles, companies, locations, and required skills.
            Also mention any common requirements or qualifications across these jobs.
            
            Answer:"""
            
            # Define the prompt template for processing user queries
            self.query_processor_prompt = """You are an AI job search assistant. Your task is to process the user's job search query
            and extract structured information.
            
            User Query: {query}
            
            Extract the following information in JSON format:
            - job_title: The position or role the user is looking for
            - location: The geographical location for the job (if specified)
            - skills: List of skills mentioned (if any)
            - experience_level: Experience level like entry, mid, senior (if specified)
            - job_type: Type of job like full-time, part-time, contract (if specified)
            - company: Specific company name (if specified)
            
            Return ONLY valid JSON without any additional text or explanation."""
            
            # Create document chain
            document_chain = create_stuff_documents_chain(
                llm=self.llm,
                prompt=PromptTemplate.from_template(self.results_processor_prompt)
            )
            
            # Create retrieval chain
            self.qa_chain = create_retrieval_chain(
                retriever=self.vector_store.as_retriever(),
                combine_docs_chain=document_chain
            )
            
            logger.info("AgenticJobSearch initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AgenticJobSearch: {str(e)}")
            raise
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a job search query using agentic search capabilities.
        """
        try:
            logger.info(f"Processing job search query: {query}")
            
            # 1. Extract structured information from the query
            structured_query = self._structure_query(query)
            
            # 2. Generate a search query from structured data
            search_query = structured_query.to_search_query()
            logger.info(f"Structured search query: {search_query}")
            
            # 3. Get search results from the configured provider
            search_provider = get_search_provider()
            search_results = search_provider.search(search_query, num_results=15)
            
            if not search_results:
                logger.warning("No search results found")
                return {
                    "query": query,
                    "structured_query": structured_query.dict(),
                    "results": [],
                    "answer": "I couldn't find any job listings matching your search criteria."
                }
            
            # 4. Process search results and add to vector store for retrieval
            docs = self._process_search_results(search_results)
            
            # 5. Generate response using the retrieval chain
            try:
                response = self.qa_chain.invoke({"input": query})
                logger.info("Generated job search response successfully")
                
                # 6. Format final results
                formatted_results = []
                for result in search_results:
                    formatted_results.append({
                        "title": result.title,
                        "description": result.description,
                        "url": result.url,
                        "source": result.source,
                        "metadata": result.metadata
                    })
                
                return {
                    "query": query,
                    "structured_query": structured_query.dict(),
                    "results": formatted_results,
                    "answer": response.get("answer", "I couldn't generate a specific answer for your job search query.")
                }
            except Exception as e:
                logger.error(f"Error in retrieval chain: {str(e)}")
                return {
                    "query": query,
                    "structured_query": structured_query.dict(),
                    "results": [],
                    "answer": "An error occurred while processing your job search query."
                }
            
        except Exception as e:
            logger.error(f"Error processing job search query: {str(e)}")
            return {
                "error": str(e),
                "query": query,
                "results": [],
                "answer": "An error occurred while processing your job search query."
            }
    
    def _structure_query(self, query: str) -> JobSearchQuery:
        """
        Process raw query into structured job search query using LLM
        """
        try:
            # Use LLM to extract structured information from the query
            response = self.llm.invoke(
                PromptTemplate.from_template(self.query_processor_prompt).format(query=query)
            )
            
            # Extract JSON from response
            json_str = response.content
            
            # Handle potential JSON parsing issues
            try:
                data = json.loads(json_str)
                return JobSearchQuery(**data)
            except json.JSONDecodeError:
                # If LLM didn't return proper JSON, create a basic query
                logger.warning(f"Failed to parse JSON from LLM response: {json_str}")
                return JobSearchQuery(job_title=query)
        except Exception as e:
            logger.error(f"Error structuring query: {str(e)}")
            return JobSearchQuery(job_title=query)
    
    def _process_search_results(self, results: List[SearchResult]) -> List[Document]:
        """
        Process search results into Documents for vector store
        """
        docs = []
        for result in results:
            content = f"Title: {result.title}\nDescription: {result.description}\nURL: {result.url}\nSource: {result.source}"
            doc = Document(
                page_content=content,
                metadata={
                    "url": result.url,
                    "title": result.title,
                    "source": result.source,
                    **result.metadata
                }
            )
            docs.append(doc)
        
        # Add to vector store
        try:
            self.vector_store.add_documents(docs)
            self.vector_store.persist()
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {str(e)}")
        
        return docs 