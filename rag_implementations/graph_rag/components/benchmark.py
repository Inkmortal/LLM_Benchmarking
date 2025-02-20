"""Benchmarking utilities for GraphRAG."""

import json
from typing import List, Dict, Any
from tqdm.notebook import tqdm as tqdm_notebook
from utils.metrics.rag_metrics import RAGMetricsEvaluator
from rag_implementations.graph_rag.components.metrics import calculate_graph_metrics

def _generate_answers(rag, eval_examples):
    """Generates answers for evaluation examples."""
    questions = []
    contexts = []
    answers = []
    references = []
    graph_contexts = []
    graph_query_times = []

    total = len(eval_examples)
    with tqdm_notebook(total=total, desc="Generating Answers") as pbar:
        for i, example in enumerate(eval_examples):
            try:
                result = rag.query(example.query)

                questions.append(example.query)
                contexts.append([doc['content'] for doc in result['context']])
                answers.append(result['response'])
                references.append(example.reference_answer)
                graph_contexts.append(result['graph_context'])

                if 'graph_query_time' in result:
                    graph_query_times.append(result['graph_query_time'])

                pbar.update(1)
                pbar.set_postfix({
                    'Query': f"{i+1}/{total}",
                    'Status': 'Success'
                })
            except Exception as e:
                pbar.set_postfix({
                    'Query': f"{i+1}/{total}",
                    'Status': f'Error: {type(e).__name__}'
                })
                print(f"\nError processing query {i+1}: {str(e)}")
                continue  # Skip to the next example on error
    return questions, contexts, answers, references, graph_contexts, graph_query_times

def _evaluate_ragas_metrics(evaluator, questions, contexts, answers, references):
    """Evaluates RAGAs metrics."""
    return evaluator.evaluate_labeled(
        queries=questions,
        contexts=contexts,
        generated_answers=answers,
        reference_answers=references,
        plot_results=True
    )

def run_evaluation(rag, dataset, evaluator, eval_examples):
    """Runs the complete evaluation process."""

    questions, contexts, answers, references, graph_contexts, graph_query_times = _generate_answers(rag, eval_examples)

    # Calculate standard RAG metrics
    print("\nCalculating standard RAG metrics...")
    try:
        rag_results = _evaluate_ragas_metrics(evaluator, questions, contexts, answers, references)

        # Calculate graph-specific metrics
        print("\nCalculating graph metrics...")
        graph_metrics = calculate_graph_metrics(graph_contexts)

        # Add performance metrics
        if graph_query_times:
            graph_metrics['performance'] = {
                'avg_query_time': sum(graph_query_times) / len(graph_query_times),
                'min_query_time': min(graph_query_times),
                'max_query_time': max(graph_query_times)
            }
        
        # Convert results to pandas DataFrame
        df = rag_results.to_pandas()

        # Add graph metrics
        for metric, value in graph_metrics.items():
            if not isinstance(value, dict):
                df[f"graph_{metric}"] = value


        results = {
            'raw_results': rag_results,
            'metrics_df': df.to_dict(),
            'graph_metrics': graph_metrics,
            'evaluation_data': {
                'questions': questions,
                'contexts': contexts,
                'answers': answers,
                'references': references,
                'graph_contexts': graph_contexts
            }
        }
        return results

    except Exception as e:
        print(f"Error during evaluation: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        print("\nDataset contents:")
        for key, value in {
            'questions': questions,
            'contexts': contexts,
            'answers': answers,
            'references': references
        }.items():
            print(f"\n{key}:")
            print(f"Type: {type(value)}")
            print(f"Length: {len(value)}")
            if value:
                print(f"First item: {str(value[0])[:100]}...")
        raise

def save_results(results, dataset_name, results_dir):
    """Saves the evaluation results to a JSON file."""
    results_data = {
        'dataset': dataset_name,
        'num_examples': len(results['evaluation_data']['questions']),
        'num_documents': len(results['evaluation_data']['contexts']),
        'num_evaluated': len(results['evaluation_data']['questions']),
        'metrics': results['metrics_df'],
        'graph_metrics': results.get('graph_metrics', {}),
        'evaluation_data': results['evaluation_data']
    }

    results_file = results_dir / f'graph_rag_results_{dataset_name.lower()}.json'
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved to {results_file}")
