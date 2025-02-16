"""Graph storage using Neptune for graph RAG."""

from typing import Dict, Any, List, Optional
from utils.aws.neptune_utils import NeptuneManager, NeptuneGraph

class GraphStore:
    """Handles graph storage and querying using Neptune."""
    
    def __init__(
        self,
        cluster_name: str,
        instance_type: str = "db.r6g.xlarge",
        enable_audit: bool = True
    ):
        """Initialize graph store.
        
        Args:
            cluster_name: Name for the Neptune cluster
            instance_type: Neptune instance type
            enable_audit: Enable audit logging
        """
        self.cluster_name = cluster_name
        self.instance_type = instance_type
        self.enable_audit = enable_audit
        
        # Initialize Neptune
        self._init_graph_store()
    
    def _init_graph_store(self):
        """Initialize Neptune graph store connection."""
        # Set up Neptune cluster
        self.neptune_manager = NeptuneManager(
            cluster_name=self.cluster_name,
            instance_type=self.instance_type,
            cleanup_enabled=True
        )
        endpoint = self.neptune_manager.setup_cluster()
        
        # Initialize graph interface
        self.graph = NeptuneGraph(endpoint)
    
    def store_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        graph_data: Dict[str, Any]
    ) -> None:
        """Store document and its graph data in Neptune.
        
        Args:
            doc_id: Document identifier
            content: Document content
            metadata: Document metadata
            graph_data: Extracted entities and relations
        """
        # Create document vertex
        doc_vertex_id = self.graph.add_vertex(
            label="Document",
            properties={
                "id": doc_id,
                "content": content,
                **metadata
            },
            id=doc_id
        )
        
        # Add entities
        entity_ids = {}
        for entity in graph_data["entities"]:
            # Create unique ID for entity
            entity_id = f"{entity['text']}_{entity['label']}"
            
            # Add entity vertex if it doesn't exist
            if entity_id not in entity_ids:
                entity_ids[entity_id] = self.graph.add_vertex(
                    label=entity["label"],
                    properties={
                        "text": entity["text"],
                        "label": entity["label"],
                        "frequency": entity["frequency"]
                    },
                    id=entity_id
                )
            
            # Link entity to document
            self.graph.add_edge(
                from_id=doc_vertex_id,
                to_id=entity_ids[entity_id],
                label="CONTAINS",
                properties={
                    "start": entity["start"],
                    "end": entity["end"]
                }
            )
        
        # Add relations
        for relation in graph_data["relations"]:
            if relation["object"]:
                # Create relation edge between entities
                subject_matches = self.graph.get_vertices(
                    properties={"text": relation["subject"]}
                )
                object_matches = self.graph.get_vertices(
                    properties={"text": relation["object"]}
                )
                
                if subject_matches and object_matches:
                    self.graph.add_edge(
                        from_id=subject_matches[0]["id"],
                        to_id=object_matches[0]["id"],
                        label=relation["predicate"].upper(),
                        properties={
                            "document": doc_id,
                            "distance": relation["distance"]
                        }
                    )
    
    def get_document_entities(
        self,
        doc_id: str,
        label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get entities connected to a document.
        
        Args:
            doc_id: Document identifier
            label: Optional entity label to filter by
            
        Returns:
            List of entity data
        """
        entities = self.graph.get_neighbors(
            vertex_id=doc_id,
            direction="out",
            edge_label="CONTAINS"
        )
        
        if label:
            entities = [e for e in entities if e["label"] == label]
            
        return entities
    
    def get_document_relations(
        self,
        doc_id: str
    ) -> List[Dict[str, Any]]:
        """Get relations associated with a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of relation data
        """
        return self.graph.get_edges(
            properties={"document": doc_id}
        )
    
    def get_entity_documents(
        self,
        entity_text: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get documents containing an entity.
        
        Args:
            entity_text: Entity text to search for
            limit: Maximum number of documents to return
            
        Returns:
            List of document data
        """
        # Find matching entity vertices
        matches = self.graph.get_vertices(
            properties={"text": entity_text}
        )
        
        documents = []
        for match in matches:
            # Get connected documents
            docs = self.graph.get_neighbors(
                vertex_id=match["id"],
                direction="in",
                edge_label="CONTAINS",
                limit=limit
            )
            documents.extend(docs)
        
        return documents[:limit] if limit else documents
    
    def cleanup(self):
        """Clean up Neptune resources."""
        if self.neptune_manager:
            self.neptune_manager.cleanup()
