"""Test ragas imports to verify available metrics."""
try:
    from ragas import evaluate
    import ragas.metrics as metrics
    
    print("✅ Successfully imported ragas")
    print("\nAvailable metrics in ragas.metrics:")
    for item in dir(metrics):
        if not item.startswith('_'):  # Only show public attributes
            print(f"- {item}")
            
    # Try to get the actual metric objects
    print("\nTrying to access metric objects:")
    for metric_name in ['answer_relevancy', 'answer_relevance', 'answer_correctness']:
        try:
            metric = getattr(metrics, metric_name, None)
            if metric:
                print(f"✅ Successfully accessed {metric_name}")
            else:
                print(f"❌ {metric_name} not found")
        except Exception as e:
            print(f"❌ Error accessing {metric_name}: {str(e)}")
except Exception as e:
    print("❌ Error importing ragas:")
    print(str(e))
