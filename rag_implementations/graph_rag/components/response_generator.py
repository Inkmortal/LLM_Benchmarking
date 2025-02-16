"""Response generation using Bedrock for graph RAG."""

import json
import time
import random
from typing import Dict, Any, List
from botocore.exceptions import ClientError
from utils.metrics.bedrock_llm import BedrockLLM

class ResponseGenerator:
    """Handles response generation using Bedrock."""
    
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_retries: int = 5,
        min_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        """Initialize response generator.
        
        Args:
            model_id: Bedrock model ID
            max_retries: Maximum retry attempts
            min_delay: Minimum retry delay in seconds
            max_delay: Maximum retry delay in seconds
        """
        self.model_id = model_id
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        
        # Initialize LLM
        self.llm = BedrockLLM()
    
    def _invoke_with_retry(self, body: Dict) -> Dict:
        """Invoke Bedrock model with exponential backoff retry.
        
        Args:
            body: Request body
            
        Returns:
            Model response
            
        Raises:
            Exception: If max retries exceeded
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = self.llm.bedrock.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body)
                )
                return json.loads(response['body'].read())
                
            except ClientError as e:
                last_exception = e
                if e.response['Error']['Code'] == 'ThrottlingException':
                    if attempt == self.max_retries - 1:
                        raise
                    # Exponential backoff with jitter
                    delay = min(
                        self.max_delay,
                        self.min_delay * (2 ** attempt) + random.uniform(0, 1)
                    )
                    time.sleep(delay)
                else:
                    raise
                    
        raise last_exception
    
    def _format_prompt(
        self,
        query: str,
        results: List[Dict[str, Any]],
        graph_context: List[Dict[str, Any]]
    ) -> str:
        """Format prompt with retrieved context and graph information.
        
        Args:
            query: Original query
            results: Retrieved documents
            graph_context: Graph relationships
            
        Returns:
            Formatted prompt string
        """
        # Format document context
        doc_context = "\n\n".join(r["content"] for r in results)
        
        # Format graph context
        graph_sections = []
        for ctx in graph_context:
            # Format entities
            entities = [f"{e['text']} ({e['label']})" for e in ctx["entities"]]
            
            # Format relations
            relations = [
                f"{r['subject']} {r['predicate']} {r['object']}"
                for r in ctx["relations"]
            ]
            
            section = f"Document {ctx['doc_id']}:\n"
            section += "Entities: " + ", ".join(entities) + "\n"
            section += "Relations: " + ", ".join(relations)
            graph_sections.append(section)
        
        graph_text = "\n\n".join(graph_sections)
        
        prompt = f"""Use the following information to answer the question.

Document Context:
{doc_context}

Graph Context:
{graph_text}

Question: {query}

Answer:"""
        
        return prompt
    
    def generate(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        graph_context: List[Dict[str, Any]]
    ) -> str:
        """Generate response using retrieved context.
        
        Args:
            query: Original query
            search_results: Retrieved documents with scores
            graph_context: Graph relationships
            
        Returns:
            Generated response
        """
        # Format prompt
        prompt = self._format_prompt(query, search_results, graph_context)
        
        # Generate response
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response_body = self._invoke_with_retry(request_body)
        
        return response_body['content'][0]['text']
