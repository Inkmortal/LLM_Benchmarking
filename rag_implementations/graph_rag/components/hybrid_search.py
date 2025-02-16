"""Hybrid search combining graph and vector retrieval for graph RAG."""

from typing import Dict, Any, List, Optional
from .graph_store import GraphStore
from .vector_store import VectorStore

class HybridSearch:
    """Combines graph and vector search results."""
    
    def __init__(
        self,
        graph_store: GraphStore,
        vector_store: VectorStore,
        k_graph: int = 5,
        k_vector: int = 3,
        alpha: float = 0.7
    ):
        """Initialize hybrid search.
        
        Args:
            graph_store: Graph storage component
            vector_store: Vector storage component
            k_graph: Number of graph-based results to retrieve
            k_vector: Number of vector-based results to retrieve
            alpha: Weight for combining graph and vector scores (0-1)
        """
        self.graph_store = graph_store
        self.vector_store = vector_store
        self.k_graph = k_graph
        self.k_vector = k_vector
        self.alpha = alpha
    
    def _calculate_graph_score(
        self,
        entity_matches: List[Dict],
        relation_matches: List[Dict],
        max_relation_distance: int = 10
    ) -> float:
        """Calculate graph relevance score based on entity and relation matches.
        
        Args:
            entity_matches: List of matching entities with frequencies
            relation_matches: List of matching relations with distances
            max_relation_distance: Maximum token distance for relationships
            
        Returns:
            Score between 0 and 1
        """
        # Entity score based on frequency and type
        entity_score = 0.0
        if entity_matches:
            frequencies = [e.get('frequency', 1) for e in entity_matches]
            # Normalize by max frequency
            max_freq = max(frequencies)
            entity_score = sum(f/max_freq for f in frequencies) / len(entity_matches)
        
        # Relation score based on distance
        relation_score = 0.0
        if relation_matches:
            distances = [r.get('distance', max_relation_distance) 
                       for r in relation_matches]
            # Inverse distance (closer = better)
            relation_score = sum((max_relation_distance - d)/max_relation_distance 
                               for d in distances) / len(relation_matches)
        
        # Combine scores with more weight on entities
        return 0.7 * entity_score + 0.3 * relation_score if entity_matches or relation_matches else 0.0
    
    def search(
        self,
        query_text: str,
        query_vector: List[float],
        query_entities: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining graph and vector results.
        
        Args:
            query_text: Original query text
            query_vector: Query embedding vector
            query_entities: Extracted entities from query
            
        Returns:
            Combined and re-ranked search results
        """
        # Get graph-based results
        graph_results = []
        for entity in query_entities:
            # Get documents containing entity
            docs = self.graph_store.get_entity_documents(
                entity_text=entity["text"],
                limit=self.k_graph
            )
            
            for doc in docs:
                # Get all entities and relations for scoring
                doc_entities = self.graph_store.get_document_entities(doc["id"])
                doc_relations = self.graph_store.get_document_relations(doc["id"])
                
                # Calculate graph score
                score = self._calculate_graph_score(doc_entities, doc_relations)
                
                graph_results.append({
                    "id": doc["id"],
                    "score": score,
                    "content": doc["content"],
                    "metadata": {k:v for k,v in doc.items() 
                               if k not in ["id", "content"]},
                    "source": "graph"
                })
        
        # Get vector-based results
        vector_results = self.vector_store.search(
            query_vector=query_vector,
            k=self.k_vector
        )
        for result in vector_results:
            result["source"] = "vector"
        
        # Combine results
        all_results = {}
        
        # Add graph results
        for result in graph_results:
            if result["id"] not in all_results:
                all_results[result["id"]] = {
                    "id": result["id"],
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "graph_score": result["score"],
                    "vector_score": 0.0
                }
        
        # Add vector results
        for result in vector_results:
            if result["id"] not in all_results:
                all_results[result["id"]] = {
                    "id": result["id"],
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "graph_score": 0.0,
                    "vector_score": result["score"]
                }
            else:
                all_results[result["id"]]["vector_score"] = result["score"]
        
        # Calculate combined scores
        results = []
        for doc_id, doc in all_results.items():
            combined_score = (
                self.alpha * doc["graph_score"] +
                (1 - self.alpha) * doc["vector_score"]
            )
            
            results.append({
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": combined_score,
                "graph_score": doc["graph_score"],
                "vector_score": doc["vector_score"]
            })
        
        # Sort by combined score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top k results
        k = max(self.k_graph, self.k_vector)
        return results[:k]
