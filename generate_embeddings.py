#!/usr/bin/env python3
"""
Embedding Generation Script for Wesley Corpus

This script generates embeddings for all passages in the Wesley corpus using either
OpenAI's text-embedding-3-small model or a local sentence-transformers model.

USAGE:
    # Generate embeddings using OpenAI (default)
    python3 generate_embeddings.py

    # Generate embeddings using local sentence-transformers
    python3 generate_embeddings.py --backend local

    # Generate with dry-run to see what would be processed
    python3 generate_embeddings.py --dry-run

    # Search for similar passages
    python3 generate_embeddings.py search "what is perfect love"
    python3 generate_embeddings.py search --backend local "what is perfect love"

REQUIREMENTS:

    For OpenAI backend:
        - pip install openai
        - Set OPENAI_API_KEY environment variable

    For local backend:
        - pip install sentence-transformers torch
        - No API key needed

OUTPUT:
    - chunked/embeddings.npz: Compressed numpy file containing:
        - 'embeddings': (n_passages, embedding_dim) array
        - 'ids': array of passage IDs in corresponding order

    - chunked/embedding_metadata.json: Metadata about the embedding generation
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np


def check_dependencies(backend: str) -> bool:
    """Check if required dependencies are installed for the specified backend."""
    try:
        if backend == "openai":
            import openai
            return True
        elif backend == "local":
            import sentence_transformers
            import torch
            return True
    except ImportError:
        return False


def get_dependency_instructions(backend: str) -> str:
    """Return installation instructions for the specified backend."""
    if backend == "openai":
        return (
            "OpenAI backend requires:\n"
            "  pip install openai\n"
            "  export OPENAI_API_KEY='your-api-key'\n"
        )
    elif backend == "local":
        return (
            "Local backend requires:\n"
            "  pip install sentence-transformers torch\n"
        )
    return ""


def load_passages(passages_file: str) -> Tuple[List[str], List[str]]:
    """Load passages from the JSONL file."""
    passages = []
    passage_ids = []

    if not os.path.exists(passages_file):
        raise FileNotFoundError(f"Passages file not found: {passages_file}")

    with open(passages_file, 'r') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                passage_ids.append(data['id'])
                passages.append(data['text'])

    return passages, passage_ids


def generate_embeddings_openai(
    passages: List[str],
    passage_ids: List[str],
    dry_run: bool = False,
    batch_size: int = 100,
) -> Tuple[np.ndarray, List[str]]:
    """Generate embeddings using OpenAI API."""
    try:
        from openai import OpenAI, RateLimitError
    except ImportError:
        print("Error: OpenAI library not installed.")
        print(get_dependency_instructions("openai"))
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print(get_dependency_instructions("openai"))
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    model = "text-embedding-3-small"
    embeddings = []

    print(f"Generating embeddings for {len(passages)} passages using OpenAI...")
    print(f"Model: {model}")
    print(f"Batch size: {batch_size}")

    if dry_run:
        print("[DRY RUN] Would process the following batches:")
        for i in range(0, len(passages), batch_size):
            batch_end = min(i + batch_size, len(passages))
            print(f"  Batch {i // batch_size + 1}: passages {i}-{batch_end-1}")
        return np.array(embeddings), passage_ids

    # Process in batches
    for i in range(0, len(passages), batch_size):
        batch_passages = passages[i : i + batch_size]
        batch_end = min(i + batch_size, len(passages))

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                print(f"Processing batch {i // batch_size + 1}/{(len(passages) + batch_size - 1) // batch_size}...")

                response = client.embeddings.create(
                    input=batch_passages,
                    model=model,
                )

                # Extract embeddings and maintain order
                for item in sorted(response.data, key=lambda x: x.index):
                    embeddings.append(item.embedding)

                break
            except RateLimitError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Error: Rate limit exceeded after {max_retries} retries")
                    raise
                wait_time = min(2 ** retry_count, 60)
                print(f"Rate limited. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"Error generating embeddings for batch {i // batch_size + 1}: {e}")
                raise

    print(f"Generated {len(embeddings)} embeddings")
    return np.array(embeddings), passage_ids


def generate_embeddings_local(
    passages: List[str],
    passage_ids: List[str],
    dry_run: bool = False,
    batch_size: int = 32,
) -> Tuple[np.ndarray, List[str]]:
    """Generate embeddings using local sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Error: sentence-transformers library not installed.")
        print(get_dependency_instructions("local"))
        sys.exit(1)

    model_name = "all-MiniLM-L6-v2"
    print(f"Generating embeddings for {len(passages)} passages using local model...")
    print(f"Model: {model_name}")
    print(f"Batch size: {batch_size}")

    if dry_run:
        print("[DRY RUN] Would process the following batches:")
        for i in range(0, len(passages), batch_size):
            batch_end = min(i + batch_size, len(passages))
            print(f"  Batch {i // batch_size + 1}: passages {i}-{batch_end-1}")
        return np.array([]), passage_ids

    print(f"Loading model {model_name} (this may take a minute on first run)...")
    model = SentenceTransformer(model_name)

    # Generate embeddings with batching
    embeddings = model.encode(
        passages,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    print(f"Generated {len(embeddings)} embeddings")
    return embeddings, passage_ids


def save_embeddings(
    embeddings: np.ndarray,
    passage_ids: List[str],
    output_file: str,
) -> None:
    """Save embeddings to a compressed numpy file."""
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    np.savez_compressed(
        output_file,
        embeddings=embeddings,
        ids=np.array(passage_ids, dtype=object),
    )

    print(f"Embeddings saved to {output_file}")
    print(f"  Shape: {embeddings.shape}")
    print(f"  Passage count: {len(passage_ids)}")


def save_metadata(
    output_file: str,
    backend: str,
    passage_count: int,
    embedding_dim: int,
) -> None:
    """Save metadata about the embedding generation."""
    metadata = {
        "backend": backend,
        "passage_count": passage_count,
        "embedding_dimension": embedding_dim,
        "model": "text-embedding-3-small" if backend == "openai" else "all-MiniLM-L6-v2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    metadata_file = output_file.replace(".npz", "_metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to {metadata_file}")


def semantic_search(
    query: str,
    embeddings_file: str,
    passages_file: str,
    backend: str,
    top_k: int = 5,
) -> None:
    """Search for passages similar to the query."""
    if not os.path.exists(embeddings_file):
        print(f"Error: Embeddings file not found: {embeddings_file}")
        print("Please run the embedding generation first.")
        sys.exit(1)

    print(f"Loading embeddings from {embeddings_file}...")
    data = np.load(embeddings_file, allow_pickle=True)
    embeddings = data['embeddings']
    passage_ids = data['ids']

    print(f"Loaded {len(passage_ids)} passage embeddings")

    # Generate embedding for query
    if backend == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            print("Error: OpenAI library not installed.")
            print(get_dependency_instructions("openai"))
            sys.exit(1)

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set.")
            sys.exit(1)

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            input=[query],
            model="text-embedding-3-small",
        )
        query_embedding = np.array(response.data[0].embedding)
    else:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("Error: sentence-transformers library not installed.")
            print(get_dependency_instructions("local"))
            sys.exit(1)

        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_embedding = model.encode([query], convert_to_numpy=True)[0]

    # Compute similarity scores
    similarities = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    # Get top-k results
    top_indices = np.argsort(similarities)[::-1][:top_k]

    # Load passages for results
    passages, all_ids = load_passages(passages_file)
    id_to_passage = {pid: text for pid, text in zip(all_ids, passages)}

    print(f"\nTop {top_k} results for: '{query}'")
    print("-" * 80)

    for rank, idx in enumerate(top_indices, 1):
        passage_id = passage_ids[idx]
        similarity = similarities[idx]
        passage_text = id_to_passage.get(passage_id, "[Passage not found]")

        # Truncate long passages
        display_text = passage_text[:200] + "..." if len(passage_text) > 200 else passage_text

        print(f"\n{rank}. Score: {similarity:.4f}")
        print(f"   ID: {passage_id}")
        print(f"   Text: {display_text}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for Wesley corpus passages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Main generation command
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate embeddings (default)",
    )
    generate_parser.add_argument(
        "--backend",
        choices=["openai", "local"],
        default="openai",
        help="Embedding backend to use (default: openai)",
    )
    generate_parser.add_argument(
        "--passages",
        default="chunked/passages.jsonl",
        help="Path to passages JSONL file (default: chunked/passages.jsonl)",
    )
    generate_parser.add_argument(
        "--output",
        default="chunked/embeddings.npz",
        help="Path to save embeddings (default: chunked/embeddings.npz)",
    )
    generate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually generating embeddings",
    )

    # Search command
    search_parser = subparsers.add_parser(
        "search",
        help="Search for passages similar to a query",
    )
    search_parser.add_argument(
        "query",
        help="Query text to search for",
    )
    search_parser.add_argument(
        "--backend",
        choices=["openai", "local"],
        default="openai",
        help="Embedding backend to use (default: openai)",
    )
    search_parser.add_argument(
        "--embeddings",
        default="chunked/embeddings.npz",
        help="Path to embeddings file (default: chunked/embeddings.npz)",
    )
    search_parser.add_argument(
        "--passages",
        default="chunked/passages.jsonl",
        help="Path to passages JSONL file (default: chunked/passages.jsonl)",
    )
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )

    args = parser.parse_args()

    # Default to generate command if no subcommand specified
    if not args.command:
        args.command = "generate"

    if args.command == "generate":
        backend = args.backend
        passages_file = args.passages
        output_file = args.output
        dry_run = args.dry_run

        # Check dependencies
        if not check_dependencies(backend):
            print(f"Error: Required dependencies for '{backend}' backend not installed.")
            print(get_dependency_instructions(backend))
            sys.exit(1)

        # Load passages
        try:
            passages, passage_ids = load_passages(passages_file)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

        print(f"Loaded {len(passages)} passages from {passages_file}")

        # Generate embeddings
        if backend == "openai":
            embeddings, ids = generate_embeddings_openai(
                passages,
                passage_ids,
                dry_run=dry_run,
                batch_size=100,
            )
        else:
            embeddings, ids = generate_embeddings_local(
                passages,
                passage_ids,
                dry_run=dry_run,
                batch_size=32,
            )

        if not dry_run and len(embeddings) > 0:
            save_embeddings(embeddings, ids, output_file)
            save_metadata(output_file, backend, len(passage_ids), embeddings.shape[1])
            print("\nEmbedding generation complete!")
        elif dry_run:
            print("\n[DRY RUN] No embeddings were actually generated.")

    elif args.command == "search":
        query = args.query
        embeddings_file = args.embeddings
        passages_file = args.passages
        backend = args.backend
        top_k = args.top_k

        # Check dependencies
        if not check_dependencies(backend):
            print(f"Error: Required dependencies for '{backend}' backend not installed.")
            print(get_dependency_instructions(backend))
            sys.exit(1)

        semantic_search(
            query,
            embeddings_file,
            passages_file,
            backend,
            top_k=top_k,
        )


if __name__ == "__main__":
    main()
