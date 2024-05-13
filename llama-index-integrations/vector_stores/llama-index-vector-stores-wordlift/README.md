# LlamaIndex Vector_Stores Integration: Wordlift

Wordlift is an AI-powered SEO platform. With our AI we build your own knowledge graph for your business with entities marked up by the different topics, categories and regions. Using this graph, search engines will be able to understand the structure of your content faster and more precisely. To access a Wordlift key and unlock our AI-powered SEO tools, visit [Wordlift](https://wordlift.io/).

This integration enables the use of Wordlift as a vector store for LlamaIndex, allowing you to work with your knowledge graph directly from your codebase.

## Features

- Perform retrieval-augmented generation (RAG) using your knowledge graph data directly in your codebase.
- Add new nodes and search within your knowledge graph effortlessly.

## Usage

Please refer to the [notebook](./examples/wordlift_vector_store_demo.ipynb) for usage of Wordlift as vector store in LlamaIndex.

Wordlift Knowledge Graphs are built on the principles of fully Linked Data, where each entity is assigned a permanent dereferentiable URI.\
When adding nodes to an existing Knowledge Graph, it's essential to include an "entity_id" in the metadata of each loaded document.\
For further insights into Fully Linked Data, explore these resources:
[W3C Linked Data](https://www.w3.org/DesignIssues/LinkedData.html),
[5 Star Data](https://5stardata.info/en/).
