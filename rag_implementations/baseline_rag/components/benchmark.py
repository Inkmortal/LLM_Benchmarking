"""Benchmarking utilities for BaselineRAG."""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from tqdm.notebook import tqdm as tqdm_notebook
from utils.metrics.rag_metrics import RAGMetricsEvaluator

def _generate_answers(rag, eval_examples):
    """Generates answers for evaluation examples."""
    questions = []
    contexts = []
    answers = []
    references = []
    query_times = []

    total = len(eval_examples)
    with tqdm_notebook(total=total, desc="Generating Answers") as pbar:
        for i, example in enumerate(eval_examples):
            try:
                result = rag.query(example.query)
                if not result or not result.get('response'):
                    pbar.set_postfix({
                        'Query': f"{i+1}/{total}",
                        'Status': 'Error: Empty response'
                    })
                    print(f"\nEmpty response for query {i+1}")
                    continue

                questions.append(example.query)
                contexts.append([doc['content'] for doc in result['context']])
                answers.append(result['response'])
                references.append(example.reference_answer)

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
    
    # Validate we have data to evaluate
    if not questions:
        raise ValueError("No valid responses generated for evaluation")
    
    return questions, contexts, answers, references, query_times

def _evaluate_ragas_metrics(evaluator, questions, contexts, answers, references):
    """Evaluates RAGAs metrics with error handling for empty arrays."""
    print("\nCalculating RAG metrics...")
    
    # Validate inputs
    if not questions or not contexts or not answers or not references:
        raise ValueError("Empty input arrays for evaluation")
    
    if len(questions) != len(contexts) or len(questions) != len(answers) or len(questions) != len(references):
        raise ValueError("Mismatched array lengths for evaluation inputs")
    
    # Filter out any empty entries
    valid_indices = []
    for i in range(len(questions)):
        if (questions[i] and contexts[i] and answers[i] and references[i] and 
            any(ctx.strip() for ctx in contexts[i])):  # Check for non-empty contexts
            valid_indices.append(i)
    
    if not valid_indices:
        raise ValueError("No valid examples for evaluation after filtering")
    
    # Use only valid entries
    filtered_questions = [questions[i] for i in valid_indices]
    filtered_contexts = [contexts[i] for i in valid_indices]
    filtered_answers = [answers[i] for i in valid_indices]
    filtered_references = [references[i] for i in valid_indices]
    
    print(f"Evaluating {len(filtered_questions)} valid examples")
    
    try:
        return evaluator.evaluate_labeled(
            queries=filtered_questions,
            contexts=filtered_contexts,
            generated_answers=filtered_answers,
            reference_answers=filtered_references,
            plot_results=True
        )
    except Exception as e:
        print(f"Error during metrics calculation: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        print("\nInput statistics:")
        print(f"Questions: {len(filtered_questions)}")
        print(f"Contexts: {len(filtered_contexts)}")
        print(f"Answers: {len(filtered_answers)}")
        print(f"References: {len(filtered_references)}")
        raise

def run_evaluation(rag, dataset, evaluator, eval_examples):
    """Runs the complete evaluation process."""
    questions, contexts, answers, references, query_times = _generate_answers(rag, eval_examples)

    try:
        # Calculate standard RAG metrics
        rag_results = _evaluate_ragas_metrics(evaluator, questions, contexts, answers, references)
        
        # Convert results to pandas DataFrame
        df = rag_results.to_pandas()

        results = {
            'raw_results': rag_results,
            'metrics_df': df.to_dict(),
            'evaluation_data': {
                'questions': questions,
                'contexts': contexts,
                'answers': answers,
                'references': references
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
        'evaluation_data': results['evaluation_data']
    }

    results_file = results_dir / f'baseline_rag_results_{dataset_name.lower()}.json'
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved to {results_file}")
