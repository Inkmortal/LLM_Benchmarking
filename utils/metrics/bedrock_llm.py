"""
Bedrock LLM wrapper for RAGAs evaluation.
"""

import json
from typing import Any, Dict, List, Optional
from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import Generation, LLMResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
import boto3

class BedrockLLM(BaseLLM):
    """Wrapper around AWS Bedrock for RAGAs evaluation."""
    
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_tokens: int = 1000,
        temperature: float = 0.0,
        **kwargs: Any,
    ):
        """Initialize Bedrock LLM.
        
        Args:
            model_id: Bedrock model ID
            max_tokens: Maximum tokens to generate
            temperature: Temperature for sampling
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = boto3.client('bedrock-runtime')
        
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Execute the LLM call."""
        # Format prompt based on model
        if self.model_id.startswith("anthropic.claude"):
            messages = [{"role": "user", "content": prompt}]
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "messages": messages,
                "temperature": self.temperature
            }
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")
            
        # Call Bedrock
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "bedrock"
        
    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate LLM result for multiple prompts."""
        generations = []
        for prompt in prompts:
            text = self._call(prompt, stop=stop, run_manager=run_manager, **kwargs)
            generations.append([Generation(text=text)])
        return LLMResult(generations=generations)
    
    def set_run_config(self, run_config: Any) -> None:
        """Set run configuration."""
        pass  # Not needed for Bedrock
