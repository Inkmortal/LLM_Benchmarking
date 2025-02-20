"""Utility for generating embeddings using AWS Bedrock."""

import boto3
import json
from botocore.exceptions import ClientError

class EmbeddingsManager:
    """
    Handles embedding generation using a specified Bedrock model.
    """

    def __init__(self, model_id: str = "cohere.embed-english-v3", region_name: str = "us-west-2"):
        """
        Initializes the EmbeddingsManager with a specific Bedrock model.

        Args:
            model_id: The Bedrock model ID for embeddings.
            region_name: The AWS region.
        """
        self.model_id = model_id
        self.region_name = region_name
        self.bedrock = boto3.client('bedrock-runtime', region_name=self.region_name)


    def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for a given text using the configured Bedrock model.

        Args:
            text: The input text.

        Returns:
            The embedding vector as a list of floats.
        
        Raises:
            Exception: If the Bedrock call fails.
        """
        try:
            response = self.bedrock.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps({
                    "texts": [text],
                    "input_type": "search_query"  # Specify input type for Cohere models
                })
            )
            response_body = json.loads(response.get('body').read())
            return response_body.get('embeddings')[0]
        except ClientError as e:
            print(f"Error invoking Bedrock for embedding: {e}")
            raise
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Error processing Bedrock response: {e}")
            raise
