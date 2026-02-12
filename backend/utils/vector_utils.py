"""Shared utility functions for vector preparation."""

from datetime import datetime


def prepare_vectors(
    file_name: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    tags: list[str] = None
) -> list[dict]:
    """
    Prepare vectors for Pinecone upsert.

    Args:
        file_name: Source file name
        chunks: List of chunk dicts with 'text' and 'index'
        embeddings: List of embedding vectors
        tags: Optional list of tags

    Returns:
        List of vector dicts ready for Pinecone upsert
    """
    tags = tags or []
    vectors = []

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "id": f"{file_name}#chunk-{i}",
            "values": embedding,
            "metadata": {
                "source": file_name,
                "chunk_index": i,
                "text": chunk["text"],
                "tags": tags,
                "created_at": datetime.now(datetime.UTC).isoformat()
            }
        })

    return vectors
