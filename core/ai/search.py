import logging
import os
from typing import Any, Dict, List

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import (ChatGoogleGenerativeAI,
                                    GoogleGenerativeAIEmbeddings)
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

class AISearch(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings: GoogleGenerativeAIEmbeddings = None
    llm: ChatGoogleGenerativeAI = None
    text_splitter: RecursiveCharacterTextSplitter = None
    vector_store: Chroma = None
    prompt_template: str = None
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
                persist_directory="./chroma_db"
            )
            
            # Define the prompt template
            self.prompt_template = """You are an AI search assistant. Use the following pieces of context to answer the question at the end.
            If you don't know the answer, just say that you don't know, don't try to make up an answer.
            
            Context: {context}
            
            Question: {question}
            
            Answer:"""
            
            # Create document chain
            document_chain = create_stuff_documents_chain(
                llm=self.llm,
                prompt=PromptTemplate.from_template(self.prompt_template)
            )
            
            # Create retrieval chain
            self.qa_chain = create_retrieval_chain(
                retriever=self.vector_store.as_retriever(),
                combine_docs_chain=document_chain
            )
            
            logger.info("AISearch initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AISearch: {str(e)}")
            raise
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a search query using Google's Gemini model.
        """
        try:
            logger.info(f"Processing query: {query}")
            
            # Check if vector store is empty
            try:
                # Initialize with sample documents if vector store is empty or not initialized
                sample_docs = [
                    "This is a sample document about job searching.",
                    "Job search tips and best practices.",
                    "How to write a great resume and cover letter.",
                    "Interview preparation and techniques.",
                    "Networking strategies for job seekers."
                ]
                
                # Try to get documents from vector store
                try:
                    docs = self.vector_store.similarity_search("test", k=1)
                    if not docs:
                        raise Exception("No documents found")
                except Exception:
                    logger.info("Vector store is empty or not initialized, adding sample documents")
                    self.add_documents(sample_docs)
                
            except Exception as e:
                logger.error(f"Error initializing vector store: {str(e)}")
                # If initialization fails, try to add documents anyway
                try:
                    self.add_documents(sample_docs)
                except Exception as init_error:
                    logger.error(f"Failed to initialize with sample documents: {str(init_error)}")
                    raise
            
            # Get relevant documents from vector store
            try:
                docs = self.vector_store.similarity_search(query, k=5)
                logger.info(f"Found {len(docs)} relevant documents")
            except Exception as e:
                logger.error(f"Error in similarity search: {str(e)}")
                docs = []
            
            if not docs:
                logger.warning("No relevant documents found")
                return {
                    "query": query,
                    "results": [],
                    "answer": "I couldn't find any relevant information for your query."
                }
            
            # Generate response using the retrieval chain
            try:
                response = self.qa_chain.invoke({"input": query})
                logger.info("Generated response successfully")
                
                # Format results
                results = []
                for doc in docs:
                    try:
                        results.append({
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "relevance_score": self._calculate_relevance(query, doc.page_content)
                        })
                    except Exception as e:
                        logger.error(f"Error formatting document result: {str(e)}")
                        continue
                
                return {
                    "query": query,
                    "results": results,
                    "answer": response.get("answer", "I couldn't generate a specific answer for your query.")
                }
            except Exception as e:
                logger.error(f"Error in retrieval chain: {str(e)}")
                return {
                    "query": query,
                    "results": [],
                    "answer": "An error occurred while processing your query."
                }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "error": str(e),
                "query": query,
                "results": [],
                "answer": "An error occurred while processing your query."
            }
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """
        Calculate relevance score between query and content.
        """
        # Simple implementation - can be enhanced with more sophisticated scoring
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        intersection = query_words.intersection(content_words)
        return len(intersection) / len(query_words) if query_words else 0.0
    
    def add_documents(self, documents: List[str], metadata: List[Dict] = None):
        """
        Add documents to the vector store for future searches.
        """
        if metadata is None:
            metadata = [{} for _ in documents]
        
        # Split documents into chunks
        texts = self.text_splitter.split_text("\n".join(documents))
        
        # Add to vector store
        self.vector_store.add_texts(texts, metadata)
        self.vector_store.persist() 