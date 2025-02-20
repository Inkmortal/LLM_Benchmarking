"""Type definitions for OpenSearch utilities."""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass

@dataclass
class OpenSearchConfig:
    """Configuration for OpenSearch operations."""
    domain_name: str
    cleanup_enabled: bool = False
    verbose: bool = True
    region: str = "us-west-2"

@dataclass
class VectorSearchConfig:
    """Configuration for vector search operations."""
    search_type: Literal['script', 'knn'] = 'script'
    similarity_threshold: Optional[float] = None
    index_settings: Optional[Dict[str, Any]] = None
    knn_params: Optional[Dict[str, Any]] = None
    max_retries: int = 5
    min_delay: float = 1.0
    max_delay: float = 60.0
