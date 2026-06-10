from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import yaml
from loguru import logger
from rapidfuzz import fuzz

try:
    import torch
    from sentence_transformers import SentenceTransformer, util
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    logger.warning("sentence-transformers or torch could not be imported. Semantic search is disabled.")
    HAS_SENTENCE_TRANSFORMERS = False

from app.config import settings
from app.constants import (
    DEFAULT_CANONICAL_SECTIONS,
    EMBEDDING_WEIGHT,
    FUZZY_WEIGHT,
    MATCH_STATUS_AUTO,
    MATCH_STATUS_REVIEW,
    MATCH_STATUS_UNMATCHED,
    SYNONYM_WEIGHT,
)
from app.segmentation.segmenter import DocumentSection


class SectionMatcher:
    """Matches document sections to canonical sections using synonyms, fuzzy matching, and embeddings."""

    def __init__(self) -> None:
        self.canonical_sections: list[str] = self._load_canonical_sections()
        self.synonyms: dict[str, list[str]] = self._load_synonyms()
        
        self.model: SentenceTransformer | None = None
        self.canonical_embeddings: dict[str, Any] = {}  # Maps canonical_name -> list of tensor embeddings

        if HAS_SENTENCE_TRANSFORMERS:
            try:
                logger.info(f"Loading embedding model: {settings.embedding_model}")
                self.model = SentenceTransformer(settings.embedding_model)
                self._precompute_embeddings()
            except Exception as e:
                logger.error(f"Failed to load sentence-transformers model: {e}. Semantic search disabled.")
                self.model = None

    def _load_canonical_sections(self) -> list[str]:
        """Loads canonical section names from schema file or falls back to constants."""
        schema_path = settings.section_schema_path
        if schema_path.exists():
            try:
                logger.info(f"Loading canonical schema from {schema_path}")
                with open(schema_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [s["name"] for s in data.get("sections", [])]
            except Exception as e:
                logger.error(f"Error reading section schema {schema_path}: {e}")
        
        logger.info("Using default canonical sections from constants.")
        return list(DEFAULT_CANONICAL_SECTIONS)

    def _load_synonyms(self) -> dict[str, list[str]]:
        """Loads synonyms from yaml file or returns empty dictionary."""
        syn_path = settings.section_synonyms_path
        if syn_path.exists():
            try:
                logger.info(f"Loading synonyms from {syn_path}")
                with open(syn_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        # Normalize keys and values to strings
                        return {str(k): [str(v) for v in val] for k, val in data.items()}
            except Exception as e:
                logger.error(f"Error reading synonyms file {syn_path}: {e}")
        
        logger.info("No synonyms file found or failed to load. Using empty synonyms.")
        return {}

    def _precompute_embeddings(self) -> None:
        """Precomputes embeddings for all canonical section names and their synonyms."""
        if not self.model:
            return
        
        logger.info("Precomputing embeddings for canonical sections and synonyms...")
        for canonical in self.canonical_sections:
            candidates = [canonical]
            if canonical in self.synonyms:
                candidates.extend(self.synonyms[canonical])
            
            # Encode all variations
            embeddings = self.model.encode(candidates, convert_to_tensor=True)
            self.canonical_embeddings[canonical] = embeddings

    def _normalize_text(self, text: str) -> str:
        """Helper to normalize text for simple matching comparison."""
        return " ".join(text.strip().lower().split())

    def match_section(self, section: DocumentSection) -> tuple[str | None, float, str]:
        """
        Matches a single document section to the best canonical section.
        Returns:
            canonical_name (str | None): The matched canonical section name, or None.
            score (float): The final match score [0.0, 1.0].
            status (str): Match status (auto_accepted, needs_review, unmatched).
        """
        heading = section.heading_text
        norm_heading = self._normalize_text(heading)
        
        best_canonical: str | None = None
        best_score = 0.0

        for canonical in self.canonical_sections:
            norm_canonical = self._normalize_text(canonical)
            candidates = [canonical]
            norm_candidates = [norm_canonical]
            if canonical in self.synonyms:
                candidates.extend(self.synonyms[canonical])
                norm_candidates.extend([self._normalize_text(syn) for syn in self.synonyms[canonical]])

            # 1. Synonym / Exact match score
            synonym_score = 0.0
            if norm_heading in norm_candidates:
                synonym_score = 1.0

            # 2. Fuzzy match score (using WRatio)
            max_fuzzy = 0.0
            for cand in candidates:
                fuz = fuzz.WRatio(heading, cand) / 100.0
                if fuz > max_fuzzy:
                    max_fuzzy = fuz
            fuzzy_score = max_fuzzy

            # 3. Semantic embedding score
            embedding_score = 0.0
            if self.model and canonical in self.canonical_embeddings:
                heading_emb = self.model.encode(heading, convert_to_tensor=True)
                cand_embs = self.canonical_embeddings[canonical]
                
                # Compute cosine similarities between heading and all candidates
                cos_sims = util.cos_sim(heading_emb, cand_embs)
                embedding_score = float(torch.max(cos_sims).item())

            # Calculate weighted score
            if self.model:
                score = (
                    synonym_score * SYNONYM_WEIGHT +
                    fuzzy_score * FUZZY_WEIGHT +
                    max(0.0, embedding_score) * EMBEDDING_WEIGHT
                )
            else:
                # Adjust weights to redistribute embedding weight if model is unavailable
                adj_sum = SYNONYM_WEIGHT + FUZZY_WEIGHT
                score = (
                    synonym_score * (SYNONYM_WEIGHT / adj_sum) +
                    fuzzy_score * (FUZZY_WEIGHT / adj_sum)
                )

            if score > best_score:
                best_score = score
                best_canonical = canonical

        # Determine status based on thresholds
        if best_score >= settings.auto_accept_threshold:
            status = MATCH_STATUS_AUTO
        elif best_score >= settings.review_threshold:
            status = MATCH_STATUS_REVIEW
        else:
            status = MATCH_STATUS_UNMATCHED
            best_canonical = None  # Clear match if below review threshold

        logger.debug(f"Matched '{heading}' -> '{best_canonical}' (score: {best_score:.4f}, status: {status})")
        return best_canonical, best_score, status

    def match_document(self, sections: list[DocumentSection]) -> dict[str, list[tuple[DocumentSection, float, str]]]:
        """
        Groups document sections under canonical sections.
        Returns a dictionary mapping: canonical_name -> list of (DocumentSection, score, status).
        Unmatched sections are mapped under MATCH_STATUS_UNMATCHED.
        """
        mappings: dict[str, list[tuple[DocumentSection, float, str]]] = {
            canonical: [] for canonical in self.canonical_sections
        }
        mappings[MATCH_STATUS_UNMATCHED] = []

        for section in sections:
            canonical, score, status = self.match_section(section)
            if canonical and status != MATCH_STATUS_UNMATCHED:
                mappings[canonical].append((section, score, status))
            else:
                mappings[MATCH_STATUS_UNMATCHED].append((section, score, status))

        return mappings
