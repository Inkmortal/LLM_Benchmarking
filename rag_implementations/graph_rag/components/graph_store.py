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
    
    def _create_entity_id(self, text: str, label: str) -> str:
        """Create consistent entity ID.
        
        Args:
            text: Entity text
            label: Entity label
            
        Returns:
            Entity vertex ID
        """
        # Clean text for ID (remove spaces, special chars)
        clean_text = text.replace(" ", "_").replace("'", "").replace('"', "")
        return f"{clean_text}_{label}"
    
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
            
            # Track created entity vertices
            entity_vertices = {}
            
            # Add entities
            for entity in graph_data["entities"]:
                # Create unique ID for entity
                entity_id = self._create_entity_id(entity["text"], entity["label"])
                
                # Add entity vertex if it doesn't exist
                if entity_id not in entity_vertices:
                    entity_vertices[entity_id] = self.graph.add_vertex(
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
                    to_id=entity_vertices[entity_id],
                    label="CONTAINS",
                    properties={
                        "start": entity["start"],
                        "end": entity["end"]
                    }
                )
            
            # Add relations
            for relation in graph_data["relations"]:
                if relation["object"] and relation["subject"]:
                    # Get entity IDs
                    subject_id = self._create_entity_id(
                        relation["subject"],
                        relation["subject_label"]
                    )
                    object_id = self._create_entity_id(
                        relation["object"],
                        relation["object_label"]
                    )
                    
                    # Only create relation if both entities exist
                    if subject_id in entity_vertices and object_id in entity_vertices:
                        self.graph.add_edge(
                            from_id=entity_vertices[subject_id],
                            to_id=entity_vertices[object_id],
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
            # Start with document vertex
            query = self.graph.g.V(doc_id)
            
            # Get outgoing CONTAINS edges to entities
            query = query.out("CONTAINS")
            
            # Filter by label if specified
            if label:
                query = query.hasLabel(label)
            
            # Get entity properties
            results = query.valueMap(True).toList()
            return results
            
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
            # Get edges with document property
            query = self.graph.g.E().has("document", doc_id)
            
            # Get edge properties
            results = query.valueMap(True).toList()
            return results
            
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
            # Start with vertices having matching text
            query = self.graph.g.V().has("text", entity_text)
            
            # Get incoming CONTAINS edges from documents
            query = query.in_("CONTAINS")
            
            # Limit results if specified
            if limit:
                query = query.limit(limit)
            
            # Get document properties
            results = query.valueMap(True).toList()
            return results
            
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
