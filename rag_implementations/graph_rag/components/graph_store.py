"""Graph storage using Neptune for graph RAG."""

from typing import Dict, Any, List, Optional
from utils.aws.neptune import NeptuneManager

class GraphStore:
    """Handles graph storage and querying using Neptune."""
    
    def __init__(
        self,
        cluster_name: str,
        enable_audit: bool = True
    ):
        """Initialize graph store.
        
        Args:
            cluster_name: Name for the Neptune cluster
            enable_audit: Enable audit logging
        """
        self.cluster_name = cluster_name
        self.enable_audit = enable_audit
        
        # Track component state
        self._initialized = False
        self.neptune_manager = None
        self.graph = None
        
        # Initialize Neptune
        self._init_graph_store()
    
    def _init_graph_store(self):
        """Initialize Neptune graph store connection."""
        try:
            # Set up Neptune manager with cleanup disabled during init
            self.neptune_manager = NeptuneManager(
                cluster_name=self.cluster_name,
                cleanup_enabled=False,  # Never cleanup during init
                verbose=self.enable_audit,
                reuse_existing=True  # Try to reuse existing resources
            )
            
            # Get endpoint and graph connection
            endpoint = self.neptune_manager.setup_cluster()
            self.graph = self.neptune_manager.graph
            
            # Mark as initialized
            self._initialized = True
            
        except Exception as e:
            # Clean up any partial state without deleting resources
            if self.graph:
                try:
                    self.graph.close()
                except:
                    pass
                self.graph = None
                
            if self.neptune_manager:
                self.neptune_manager = None
                
            raise Exception(f"Failed to initialize graph store: {str(e)}") from e
    
    def ensure_initialized(self):
        """Ensure graph store is properly initialized."""
        if not self._initialized:
            raise RuntimeError("GraphStore not properly initialized")
        if not self.graph:
            raise RuntimeError("Graph connection not available")
    
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
        self.ensure_initialized()
        
        try:
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
                        
        except Exception as e:
            raise Exception(f"Failed to store document {doc_id}: {str(e)}") from e
    
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
        self.ensure_initialized()
        
        try:
            entities = self.graph.get_neighbors(
                vertex_id=doc_id,
                direction="out",
                edge_label="CONTAINS"
            )
            
            if label:
                entities = [e for e in entities if e["label"] == label]
                
            return entities
            
        except Exception as e:
            raise Exception(f"Failed to get entities for document {doc_id}: {str(e)}") from e
    
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
        self.ensure_initialized()
        
        try:
            return self.graph.get_edges(
                properties={"document": doc_id}
            )
        except Exception as e:
            raise Exception(f"Failed to get relations for document {doc_id}: {str(e)}") from e
    
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
        self.ensure_initialized()
        
        try:
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
            
        except Exception as e:
            raise Exception(f"Failed to get documents for entity {entity_text}: {str(e)}") from e
    
    def cleanup(self, delete_resources: bool = False):
        """Clean up all resources.
        
        Args:
            delete_resources: Whether to delete Neptune resources
        """
        if self.graph:
            try:
                self.graph.close()
            except:
                pass  # Best effort cleanup
            self.graph = None
            
        if self.neptune_manager:
            try:
                # Only delete resources if explicitly requested
                self.neptune_manager.cleanup_enabled = delete_resources
                self.neptune_manager.cleanup()
            except:
                pass  # Best effort cleanup
            self.neptune_manager = None
            
        self._initialized = False
