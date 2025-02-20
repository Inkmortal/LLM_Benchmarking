"""Graph storage using Neptune for graph RAG."""

import boto3
from typing import Dict, Any, List, Optional
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError

class GraphStore:
    """Handles graph storage and retrieval using Amazon Neptune."""

    def __init__(
        self,
        cluster_name: str = "default-graph-rag"
    ):
        """Initialize graph store.

        Args:
            cluster_name: Name of Neptune cluster
        """
        self.cluster_name = cluster_name
        self._initialized = False
        self.neptune_manager = None  # Initialize to None
        self.graph = None
        self.endpoint = None
        if not self.check_configuration():
            self._delete_cluster()  # Delete if config doesn't match
        self._create_cluster() # Create on initialization


    def _get_aws_credentials(self):
        """Get AWS credentials."""
        session = boto3.Session()
        return session.get_credentials().get_frozen_credentials()

    def _create_cluster(self):
        """Create Neptune cluster and set up connection."""
        from utils.aws.neptune.cluster import NeptuneManager  # Import here

        print("Setting up Neptune cluster...")
        self.neptune_manager = NeptuneManager(
            cluster_name=self.cluster_name,
            cleanup_enabled=False,  # Never auto-cleanup during initialization
            verbose=True  # Enable logging
        )
        self.endpoint = self.neptune_manager.setup_cluster()
        self._initialized = True
        print(f"Neptune cluster endpoint: {self.endpoint}")

        # Get AWS credentials
        creds = self._get_aws_credentials()

        # Create database URL for Gremlin
        database_url = f"wss://{self.endpoint}:8182/gremlin"

        # Create and sign request
        request = AWSRequest(method="GET", url=database_url, data=None)
        SigV4Auth(creds, "neptune-db", "us-west-2").add_auth(request)

        # Create connection with signed headers
        self.graph = DriverRemoteConnection(
            database_url,
            'g',
            headers=request.headers.items()
        )
        print("Connected to Neptune")

    def _delete_cluster(self):
        """Delete existing Neptune cluster."""
        from utils.aws.neptune.cluster import NeptuneManager
        print("Deleting existing Neptune cluster...")
        temp_manager = NeptuneManager(
            cluster_name=self.cluster_name,
            cleanup_enabled=True  # Always cleanup when explicitly deleting
        )
        temp_manager.cleanup()
        print("Neptune cluster deleted.")


    def check_configuration(self) -> bool:
        """
        Checks if the existing Neptune cluster (if any) matches the
        expected configuration.
        Returns True if the config matches, False otherwise.
        """
        try:
            neptune = boto3.client('neptune')
            response = neptune.describe_db_clusters(
                DBClusterIdentifier=self.cluster_name
            )

            if response['DBClusters']:
                cluster_info = response['DBClusters'][0]
                # Just check if cluster exists and is available
                return cluster_info['Status'] == 'available'
            else:
                # Cluster doesn't exist
                return False
        except ClientError as e:
            if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
                # Cluster doesn't exist, so config "mismatches"
                return False
            else:
                # Some other error, raise it
                raise

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
