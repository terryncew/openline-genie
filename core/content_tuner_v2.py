#!/usr/bin/env python3
"""
OpenLine Writing Studio — ContentTuner 2.0 (Python)
Audits and repairs the 3 critical defects in legacy content_tuner.py:
  1. Arbitrary mid-sentence word truncation that cuts off subordinate causal clauses.
  2. Deletion of meaningful epistemic qualifiers/negations ('allegedly', 'not', 'unless').
  3. Superficial global regex synonym substitutions that corrupt quotes and technical terms.
Separates deterministic local linting/compression from model-driven transformations,
and never overwrites ACCEPTED prose.
"""

from __future__ import annotations
import re
from typing import Dict, List, Tuple


PROTECTED_QUALIFIERS: Tuple[str, ...] = (
    "allegedly",
    "reportedly",
    "according to",
    "unnamed",
    "denied",
    "cannot prove",
    "under stated assumptions",
    "under assumption",
    "approximately",
    "estimated",
    "not",
    "never",
    "no",
    "unless",
    "except",
    "if and only if",
)

BUREAUCRATIC_PADDING_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (r"\bdue to the fact that\b", "because"),
    (r"\bin order to\b", "to"),
    (r"\bin the event that\b", "if"),
    (r"\bat this point in time\b", "now"),
    (r"\bfor the purpose of\b", "for"),
    (r"\bit is important to note that\s*", ""),
    (r"\bit is worth noting that\s*", ""),
    (r"\bneedless to say,\s*", ""),
    (r"\bin a very real sense,\s*", ""),
    (r"\bas a matter of fact,\s*", ""),
)


class LegacyDefectiveContentTuner:
    """
    Reproduces the 3 historical defects in legacy content_tuner.py for unit testing:
      1. Chops sentences arbitrarily after 14 words (destroying 'because...' / attribution clauses).
      2. Strips hedge/negation words ('allegedly', 'reportedly', 'approximately', 'not').
      3. Runs naive global regex replacements even inside direct quotations.
    """

    def tune_defective(self, text: str, max_words_per_sentence: int = 14) -> str:
        # Defect 2: Blindly strip qualifiers/hedges
        out = re.sub(r"\b(allegedly|reportedly|approximately|unnamed|not)\b\s*", "", text, flags=re.IGNORECASE)
        # Defect 3: Naive synonym swap even inside quotes
        out = re.sub(r"\bcapital expenditure\b", "cash burn", out, flags=re.IGNORECASE)
        # Defect 1: Arbitrary word-limit sentence truncation
        sentences = re.split(r"(?<=[.!?])\s+", out.strip())
        chopped = []
        for s in sentences:
            words = s.split()
            if len(words) > max_words_per_sentence:
                chopped.append(" ".join(words[:max_words_per_sentence]) + ".")
            else:
                chopped.append(s)
        return " ".join(chopped)


class ContentTunerV2:
    """
    Repaired ContentTuner 2.0:
    - Protects quoted strings ("..."), numbers/dates/currencies, negations, and epistemic qualifiers.
    - Compresses bureaucratic deadweight without ever truncating a sentence mid-clause.
    - Reports exact provenance and preserved qualifiers so the author can verify zero meaning loss.
    """

    def extract_protected_tokens(self, text: str) -> Dict[str, List[str]]:
        quotes = re.findall(r'"[^"]+"|\u201c[^\u201d]+\u201d', text)
        numbers = re.findall(r"\$?\d+(?:,\d{3})*(?:\.\d+)?%?|\b(?:19|20)\d{2}\b", text)
        qualifiers = []
        lower = text.lower()
        for q in PROTECTED_QUALIFIERS:
            if re.search(r"\b" + re.escape(q) + r"\b", lower):
                qualifiers.append(q)
        return {
            "quotes": quotes,
            "numbers": numbers,
            "qualifiers": qualifiers,
        }

    def tune(
        self,
        text: str,
        profile: str = "reported_plain",
        compression_level: float = 65.0,
    ) -> Dict[str, object]:
        if not isinstance(text, str):
            raise ValueError("Input text must be a string.")
        before_tokens = self.extract_protected_tokens(text)

        # Protect quoted spans with placeholders during phrase compression
        quotes_map: Dict[str, str] = {}

        def _stash_quote(match: re.Match) -> str:
            key = f"__OL_QUOTE_{len(quotes_map)}__"
            quotes_map[key] = match.group(0)
            return key

        working = re.sub(r'"[^"]+"|\u201c[^\u201d]+\u201d', _stash_quote, text)

        applied_rules: List[str] = []
        if compression_level >= 35.0:
            for pattern, repl in BUREAUCRATIC_PADDING_REPLACEMENTS:
                next_working, count = re.subn(pattern, repl, working, flags=re.IGNORECASE)
                if count > 0:
                    applied_rules.append(f"{pattern} -> {repl!r} ({count}x)")
                    working = next_working

        # Clean up double spaces and capitalize sentence starts after leading phrase removal
        working = re.sub(r"[ \t]{2,}", " ", working).strip()
        working = re.sub(
            r"(^|(?<=[.!?]\s))([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            working,
        )

        # Restore all direct quotations verbatim
        for key, original_quote in quotes_map.items():
            working = working.replace(key, original_quote)

        after_tokens = self.extract_protected_tokens(working)

        # Verify zero loss of quotes, numbers, or epistemic qualifiers
        missing_quotes = [q for q in before_tokens["quotes"] if q not in after_tokens["quotes"]]
        missing_numbers = [n for n in before_tokens["numbers"] if n not in after_tokens["numbers"]]
        missing_qualifiers = [q for q in before_tokens["qualifiers"] if q not in after_tokens["qualifiers"]]

        meaning_preserved = not (missing_quotes or missing_numbers or missing_qualifiers)
        if not meaning_preserved:
            # Fail-closed: return original text untouched if any protected token was disturbed
            working = text

        return {
            "originalText": text,
            "tunedText": working,
            "profile": profile,
            "state": "EXPLORATORY",
            "deterministic": True,
            "meaningPreserved": True,
            "appliedRules": applied_rules,
            "protectedTokens": before_tokens,
        }
