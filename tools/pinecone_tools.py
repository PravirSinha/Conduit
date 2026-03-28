"""
CONDUIT — Pinecone Tools
Semantic search utilities for the Intake Agent RAG pipeline.
"""

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


def get_pinecone_index():
    """
    Returns a connected Pinecone index instance.
    Called once per agent invocation.
    """
    api_key    = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")

    if not api_key:
        raise ValueError(
            "PINECONE_API_KEY is not set. "
            "Add it to the GitHub Actions secrets and redeploy."
        )
    if not index_name:
        raise ValueError(
            "PINECONE_INDEX_NAME is not set. "
            "Add it to the GitHub Actions secrets and redeploy."
        )

    from pinecone import Pinecone

    pc = Pinecone(
        api_key=api_key,
        pool_threads=1,
    )

    # Validate index exists before trying to connect
    # A wrong index name causes index.query() to hang indefinitely
    available = [i.name for i in pc.list_indexes()]
    if index_name not in available:
        raise ValueError(
            f"Pinecone index '{index_name}' not found. "
            f"Available indexes: {available}. "
            f"Update the PINECONE_INDEX_NAME GitHub secret."
        )

    index = pc.Index(
        index_name,
        pool_threads=1,
    )
    return index


def get_openai_client():
    from openai import OpenAI
    import httpx

    raw_client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=httpx.Timeout(30.0, connect=10.0),
    )

    # Best-effort LangSmith tracing for embedding calls.
    # IMPORTANT: tracing must never break the pipeline.
    try:
        tracing_enabled = (
            os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true" or
            os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        )
        has_langsmith_key = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
        if tracing_enabled and has_langsmith_key:
            from langsmith.wrappers import wrap_openai
            return wrap_openai(raw_client)
    except Exception:
        pass

    return raw_client


def embed_text(text: str) -> List[float]:
    """
    Converts a text string into a vector embedding.
    Uses text-embedding-3-small — same model used during seeding.
    Consistency is critical — query and index must use same model.
    """
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        timeout=15,   # fail fast if OpenAI is slow
    )
    return response.data[0].embedding


def search_parts_catalog(
    complaint_text: str,
    top_k: int = 5,
    filter_make: Optional[str] = None,
    filter_fuel_type: Optional[str] = None,
) -> List[Dict]:
    """
    Semantic search on Pinecone parts catalog.
    Returns top_k most relevant parts for a given complaint.

    Args:
        complaint_text: Raw complaint from service advisor
                       e.g. "grinding noise from front when braking"
        top_k:         Number of results to return (default 5)
        filter_make:   Optional — filter by vehicle make
                       e.g. "Honda" returns only Honda-compatible parts
        filter_fuel_type: Optional — filter by fuel type
                          e.g. "Electric" returns EV parts

    Returns:
        List of dicts with part details + similarity score
    """
    # Build query vector from complaint text
    query_vector = embed_text(complaint_text)

    # Build optional metadata filter
    # Pinecone filter syntax uses $in for list membership
    pinecone_filter = {}

    if filter_make:
        pinecone_filter["compatible_makes"] = {"$in": [filter_make]}

    if filter_fuel_type:
        pinecone_filter["fuel_types"] = {"$in": [filter_fuel_type]}

    # Execute search
    index = get_pinecone_index()

    query_kwargs = {
        "vector":          query_vector,
        "top_k":           top_k,
        "include_metadata": True,
    }

    if pinecone_filter:
        query_kwargs["filter"] = pinecone_filter

    results = index.query(**query_kwargs, timeout=20)

    # Format results into clean dicts
    parts = []
    for match in results.matches:
        part = {
            "part_number":      match.metadata.get("part_number"),
            "description":      match.metadata.get("description"),
            "category":         match.metadata.get("category"),
            "subcategory":      match.metadata.get("subcategory"),
            "brand":            match.metadata.get("brand"),
            "unit_cost":        match.metadata.get("unit_cost"),
            "sell_price":       match.metadata.get("sell_price"),
            "bin_location":     match.metadata.get("bin_location"),
            "qty_on_hand":      match.metadata.get("qty_on_hand"),
            "stock_status":     match.metadata.get("stock_status"),
            "compatible_makes": match.metadata.get("compatible_makes", []),
            "compatible_models": match.metadata.get("compatible_models", []),
            "is_ev_part":       match.metadata.get("is_ev_part", False),
            "oem_part_number":  match.metadata.get("oem_part_number"),
            "similarity_score": round(match.score, 4),
        }
        parts.append(part)

    return parts