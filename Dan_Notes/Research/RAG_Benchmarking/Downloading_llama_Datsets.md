# Downloading a LlamaDataset from LlamaHub

LlamaHub offers a variety of benchmark datasets that can be utilized for evaluating and testing Retrieval-Augmented Generation (RAG) systems. This guide provides a step-by-step approach to downloading a LlamaDataset and its associated source text documents.

## Prerequisites

Before proceeding, ensure you have the following:

- **Python Environment**: Make sure Python is installed on your system.
- **LlamaIndex Library**: Install the LlamaIndex library if you haven't already:

  ```bash
  pip install llama-index
  ```

## Steps to Download a LlamaDataset

1. **Browse Available Datasets**: Visit [LlamaHub](https://llamahub.ai) to explore the available benchmark datasets.

2. **Select a Dataset**: Choose the dataset that aligns with your evaluation needs. Note the dataset's class name, which is typically in the format `DatasetNameDataset`. For instance, for the Paul Graham essay dataset, the class name is `PaulGrahamEssayDataset`.

3. **Download the Dataset**: Utilize the `download_llama_dataset` function from the LlamaIndex library to download the selected dataset. Here's how:

   ```python
   from llama_index.core.llama_dataset import download_llama_dataset

   # Specify the dataset class name and the directory to download
   dataset_class = "PaulGrahamEssayDataset"  # Replace with your chosen dataset class
   download_directory = "./data"  # Directory where the dataset will be saved

   # Download the dataset and its source documents
   rag_dataset, documents = download_llama_dataset(dataset_class, download_directory)
   ```

   In this script:

   - `dataset_class` is the class name of the dataset you wish to download.
   - `download_directory` is the path where the dataset and its source documents will be stored.
   - The function returns two objects:
     - `rag_dataset`: The downloaded dataset.
     - `documents`: A list of source documents associated with the dataset.

4. **Verify the Download**: After executing the script, check the specified download directory to ensure that the dataset and its source documents have been successfully downloaded.

## Additional Information

- **Function Details**: The `download_llama_dataset` function retrieves the dataset from the LlamaHub repository and saves it locally. It also loads the source documents into a list for immediate use.

- **Loading Data**: Once downloaded, you can load and process the data as needed for your application. For more details on loading data, refer to the [Loading Data Guide](https://docs.llamaindex.ai/en/stable/understanding/loading/loading/).

By following these steps, you can efficiently download and utilize LlamaDatasets from LlamaHub for your RAG system evaluations.

