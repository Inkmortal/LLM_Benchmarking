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

    def __post_init__(self):
        """Validate configuration after initialization."""
        if len(self.domain_name) > 28:
            raise ValueError(
                f"Domain name '{self.domain_name}' exceeds AWS limit of 28 characters"
            )

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
