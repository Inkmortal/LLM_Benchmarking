"""Graph-specific metrics for evaluating graph RAG performance."""

import matplotlib.pyplot as plt
from typing import Dict, List, Any

def calculate_graph_metrics(graph_contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate graph-specific metrics.
    
    Args:
        graph_contexts: List of graph contexts from RAG results
        
    Returns:
        Dictionary containing graph metrics:
        - avg_entities_per_context: Average number of entities per context
        - avg_relations_per_context: Average number of relations per context
        - unique_entity_types: Number of unique entity types
        - unique_relation_types: Number of unique relation types
        - entity_type_distribution: Distribution of entity types
        - relation_type_distribution: Distribution of relation types
    """
    total_entities = 0
    total_relations = 0
    entity_types = {}
    relation_types = {}
    
    for ctx in graph_contexts:
        for doc_ctx in ctx:
            # Count entities
            doc_entities = doc_ctx['entities']
            total_entities += len(doc_entities)
            
            # Track entity types
            for entity in doc_entities:
                entity_type = entity['label']
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            
            # Count relations
            doc_relations = doc_ctx['relations']
            total_relations += len(doc_relations)
            
            # Track relation types
            for relation in doc_relations:
                relation_type = relation['label']
                relation_types[relation_type] = relation_types.get(relation_type, 0) + 1
    
    # Calculate averages
    num_contexts = len(graph_contexts)
    avg_entities = total_entities / num_contexts if num_contexts > 0 else 0
    avg_relations = total_relations / num_contexts if num_contexts > 0 else 0
    
    return {
        'avg_entities_per_context': avg_entities,
        'avg_relations_per_context': avg_relations,
        'unique_entity_types': len(entity_types),
        'unique_relation_types': len(relation_types),
        'entity_type_distribution': entity_types,
        'relation_type_distribution': relation_types,
        'total_entities': total_entities,
        'total_relations': total_relations
    }

def calculate_graph_coverage(
    query_entities: List[Dict[str, Any]],
    context_entities: List[Dict[str, Any]]
) -> float:
    """Calculate how well the retrieved graph context covers query entities.
    
    Args:
        query_entities: Entities extracted from query
        context_entities: Entities from retrieved context
        
    Returns:
        Coverage score between 0 and 1
    """
    if not query_entities:
        return 1.0
    
    # Get unique query entity texts
    query_texts = {e['text'].lower() for e in query_entities}
    
    # Get unique context entity texts
    context_texts = {e['text'].lower() for e in context_entities}
    
    # Calculate coverage
    covered = len(query_texts.intersection(context_texts))
    total = len(query_texts)
    
    return covered / total

def calculate_graph_relevance(
    query_entities: List[Dict[str, Any]],
    context_entities: List[Dict[str, Any]]
) -> float:
    """Calculate relevance of retrieved graph context to query.
    
    Args:
        query_entities: Entities extracted from query
        context_entities: Entities from retrieved context
        
    Returns:
        Relevance score between 0 and 1
    """
    if not context_entities:
        return 0.0
    
    # Get unique query entity texts
    query_texts = {e['text'].lower() for e in query_entities}
    
    # Get unique context entity texts
    context_texts = {e['text'].lower() for e in context_entities}
    
    # Calculate relevance (precision)
    relevant = len(query_texts.intersection(context_texts))
    total = len(context_texts)
    
    return relevant / total if total > 0 else 0.0

def plot_graph_metrics(metrics: Dict[str, Any], figsize: tuple = (15, 10)) -> None:
    """Plot graph-specific metrics.
    
    Args:
        metrics: Dictionary of graph metrics from calculate_graph_metrics()
        figsize: Figure size as (width, height) tuple
    """
    plt.figure(figsize=figsize)
    
    # Plot averages
    plt.subplot(2, 2, 1)
    averages = [metrics['avg_entities_per_context'], metrics['avg_relations_per_context']]
    plt.bar(['Entities', 'Relations'], averages)
    plt.title('Average Entities and Relations per Context')
    plt.ylabel('Count')
    
    # Plot unique types
    plt.subplot(2, 2, 2)
    unique_types = [metrics['unique_entity_types'], metrics['unique_relation_types']]
    plt.bar(['Entity Types', 'Relation Types'], unique_types)
    plt.title('Unique Entity and Relation Types')
    plt.ylabel('Count')
    
    # Plot entity type distribution
    plt.subplot(2, 2, 3)
    entity_types = metrics['entity_type_distribution']
    plt.bar(entity_types.keys(), entity_types.values())
    plt.title('Entity Type Distribution')
    plt.xticks(rotation=45)
    plt.ylabel('Count')
    
    # Plot relation type distribution
    plt.subplot(2, 2, 4)
    relation_types = metrics['relation_type_distribution']
    plt.bar(relation_types.keys(), relation_types.values())
    plt.title('Relation Type Distribution')
    plt.xticks(rotation=45)
    plt.ylabel('Count')
    
    plt.tight_layout()
    plt.show()
