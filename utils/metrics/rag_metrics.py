"""
RAG evaluation metrics using RAGAs framework and custom implementations.
Provides a unified interface for evaluating RAG systems with both labeled and unlabeled datasets.
"""

from typing import List, Dict, Any, Optional, Union
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    ContextPrecision,
    AnswerRelevancy,
    ContextRecall,
    ContextEntityRecall,
    NoiseSensitivity
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_aws import ChatBedrockConverse, BedrockEmbeddings

class RAGMetricsEvaluator:
    """
    Unified interface for evaluating RAG systems using both labeled and unlabeled datasets.
    Integrates RAGAs metrics with custom evaluation capabilities.
    """
    
    def __init__(
        self,
        region_name: str = "us-west-2",
        llm_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        embedding_model_id: str = "cohere.embed-english-v3",
        temperature: float = 0.0
    ):
        """
        Initialize the evaluator with AWS Bedrock models.
        
        Args:
            region_name: AWS region name
            llm_model_id: Bedrock LLM model ID
            embedding_model_id: Bedrock embeddings model ID
            temperature: Temperature for LLM sampling
        """
        # Initialize Bedrock models
        evaluator_llm = LangchainLLMWrapper(ChatBedrockConverse(
            region_name=region_name,
            base_url=f"https://bedrock-runtime.{region_name}.amazonaws.com",
            model=llm_model_id,
            temperature=temperature,
        ))
        
        evaluator_embeddings = LangchainEmbeddingsWrapper(BedrockEmbeddings(
            region_name=region_name,
            model_id=embedding_model_id,
        ))
        
        # Initialize metrics with wrapped models
        self.metrics = [
            # Context retrieval metrics
            ContextPrecision(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
            ContextEntityRecall(llm=evaluator_llm),
            NoiseSensitivity(llm=evaluator_llm),
            
            # Answer generation metrics
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
        ]
        
    def evaluate_labeled(
        self,
        queries: List[str],
        contexts: List[List[str]],
        generated_answers: List[str],
        reference_answers: List[str],
        plot_results: bool = True
    ) -> Dict[str, float]:
        """
        Evaluate RAG system using labeled dataset with reference answers.
        
        Args:
            queries: List of input queries
            contexts: List of retrieved contexts for each query
            generated_answers: List of generated answers
            reference_answers: List of ground truth answers
            plot_results: Whether to plot evaluation results
            
        Returns:
            Dictionary of metric names and scores
        """
        # Create evaluation dataset
        data = {
            "question": queries,
            "answer": generated_answers,
            "contexts": contexts,
            "reference": reference_answers
        }
        eval_dataset = Dataset.from_dict(data)
        
        # Evaluate using RAGAs
        results = evaluate(
            dataset=eval_dataset,
            metrics=self.metrics
        )
        
        # Convert to DataFrame
        df = results.to_pandas()
        
        # Plot results if requested
        if plot_results:
            self.plot_results(df)
        
        return results
    
    def evaluate_unlabeled(
        self,
        queries: List[str],
        contexts: List[List[str]],
        generated_answers: List[str],
        plot_results: bool = True
    ) -> Dict[str, float]:
        """
        Evaluate RAG system using unlabeled dataset (no reference answers).
        
        Args:
            queries: List of input queries
            contexts: List of retrieved contexts for each query
            generated_answers: List of generated answers
            plot_results: Whether to plot evaluation results
            
        Returns:
            Dictionary of metric names and scores
        """
        # Create evaluation dataset
        data = {
            "question": queries,
            "answer": generated_answers,
            "contexts": contexts
        }
        eval_dataset = Dataset.from_dict(data)
        
        # Select metrics that don't require ground truth
        unlabeled_metrics = [
            metric for metric in self.metrics
            if not metric.__class__.__name__ in ['ContextRecall', 'ContextEntityRecall']
        ]
        
        # Evaluate using RAGAs
        results = evaluate(
            dataset=eval_dataset,
            metrics=unlabeled_metrics
        )
        
        # Convert to DataFrame
        df = results.to_pandas()
        
        # Plot results if requested
        if plot_results:
            self.plot_results(df)
        
        return results
    
    def plot_results(
        self,
        results: Union[Dict[str, float], pd.DataFrame],
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> None:
        """
        Plot evaluation results using different visualizations.
        
        Args:
            results: Evaluation results as dictionary or DataFrame
            title: Optional plot title
            save_path: Optional path to save plots
        """
        # Convert dictionary to DataFrame if needed
        df = pd.DataFrame(results) if isinstance(results, dict) else results
        
        # Group metrics with fallbacks for different naming conventions
        retrieval_metrics = {
            'context_precision': ['context_precision'],
            'context_recall': ['context_recall'],
            'context_entity_recall': ['context_entity_recall'],
            'noise_sensitivity': ['noise_sensitivity', 'noise_sensitivity_relevant']  # Handle both naming variants
        }
        generation_metrics = {
            'faithfulness': ['faithfulness'],
            'answer_relevancy': ['answer_relevancy']
        }
        
        # Helper function to get metric value with fallbacks
        def get_metric_value(metrics_dict, metric_name):
            for possible_name in metrics_dict[metric_name]:
                if possible_name in df.columns:
                    return df[possible_name].mean()
            return 0.0  # Return 0 if metric not found
        
        # Calculate mean scores
        retrieval_scores = pd.Series({
            metric: get_metric_value(retrieval_metrics, metric)
            for metric in retrieval_metrics.keys()
        })
        
        generation_scores = pd.Series({
            metric: get_metric_value(generation_metrics, metric)
            for metric in generation_metrics.keys()
        })
        
        # Create comparison plots
        plt.figure(figsize=(12, 6))
        
        # Plot retrieval metrics
        plt.subplot(1, 2, 1)
        sns.barplot(x=retrieval_scores.index, y=retrieval_scores.values)
        plt.title('Context Retrieval Metrics')
        plt.xticks(rotation=45)
        plt.ylim(0, 1)
        
        # Plot generation metrics
        plt.subplot(1, 2, 2)
        sns.barplot(x=generation_scores.index, y=generation_scores.values)
        plt.title('Answer Generation Metrics')
        plt.xticks(rotation=45)
        plt.ylim(0, 1)
        
        plt.tight_layout()
        
        # Save plot if path provided
        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
        
        plt.show()
        
        # Print analysis
        print("\nAnalysis:")
        print("Context Retrieval:")
        print(f"- Precision: {retrieval_scores.get('context_precision', 0):.2f} - How many retrieved documents are relevant")
        print(f"- Recall: {retrieval_scores.get('context_recall', 0):.2f} - How many relevant documents were retrieved")
        print(f"- Entity Recall: {retrieval_scores.get('context_entity_recall', 0):.2f} - How well important entities are preserved")
        print(f"- Noise Sensitivity: {retrieval_scores.get('noise_sensitivity', 0):.2f} - Robustness against irrelevant data")
        
        print("\nAnswer Generation:")
        print(f"- Faithfulness: {generation_scores.get('faithfulness', 0):.2f} - How factual the answers are")
        print(f"- Relevancy: {generation_scores.get('answer_relevancy', 0):.2f} - How relevant the answers are to questions")
    
    def compare_implementations(
        self,
        implementation_results: Dict[str, Dict[str, float]],
        output_format: str = 'dataframe'
    ) -> Any:
        """
        Compare metrics across different RAG implementations.
        
        Args:
            implementation_results: Dictionary mapping implementation names to their metric results
            output_format: 'dataframe' or 'dict'
            
        Returns:
            Comparison results in specified format
        """
        if output_format == 'dataframe':
            return pd.DataFrame(implementation_results).round(4)
        return implementation_results
    
    @staticmethod
    def aggregate_metrics(results: Dict[str, float]) -> float:
        """
        Calculate an aggregate score from multiple metrics.
        
        Args:
            results: Dictionary of metric names and scores
            
        Returns:
            Aggregate score between 0 and 1
        """
        # Simple average of all metrics
        return sum(results.values()) / len(results)


def load_llama_dataset(dataset_path: str) -> tuple:
    """
    Load a dataset in LlamaIndex format.
    
    Args:
        dataset_path: Path to the dataset file
        
    Returns:
        Tuple of (queries, contexts, reference_answers)
    """
    from llama_index.core.llama_dataset import download_llama_dataset
    
    # Load dataset using LlamaIndex
    rag_dataset, documents = download_llama_dataset(dataset_path)
    
    # Extract components
    queries = rag_dataset.queries
    contexts = rag_dataset.contexts
    reference_answers = rag_dataset.reference_answers
    
    return queries, contexts, reference_answers


# Example usage:
"""
# Initialize evaluator
evaluator = RAGMetricsEvaluator()

# Evaluate labeled dataset
labeled_results = evaluator.evaluate_labeled(
    queries=queries,
    contexts=contexts,
    generated_answers=answers,
    reference_answers=ground_truths
)

# Evaluate unlabeled dataset
unlabeled_results = evaluator.evaluate_unlabeled(
    queries=queries,
    contexts=contexts,
    generated_answers=answers
)

# Compare implementations
comparison = evaluator.compare_implementations({
    'baseline': baseline_results,
    'graph_rag': graph_results
})
print(comparison)
"""
