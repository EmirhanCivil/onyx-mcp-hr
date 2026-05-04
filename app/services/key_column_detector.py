"""Key column detection for semantic spreadsheet comparison.

We need a reliable join key to match rows across two files. This module aims to
find the best key column pair using only name/content heuristics (no domain
hardcoding, no embeddings, no external dependencies).
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from app.services.semantic_column_matcher import profile_columns
from app.services.value_normalizer import normalize_value
from app.utils.dataframe_utils import normalize_column_name


@dataclass(frozen=True)
class KeyPick:
    key_column_a: str
    key_column_b: str
    confidence: float
    reason: str
    alternatives: list[dict[str, Any]]


def detect_key_column(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key_hint: str | None = None,
    exclude_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Detect the best key column pair (A and B may have different names).

    Returns diagnostics to reduce ambiguity (duplicates, matched key count, only-in counts).
    """

    profiles_a = profile_columns(df_a)
    profiles_b = profile_columns(df_b)

    cols_a = [p["column_name"] for p in profiles_a]
    cols_b = [p["column_name"] for p in profiles_b]

    if not cols_a or not cols_b:
        return KeyPick("", "", 0.0, "empty dataframe(s)", []).__dict__

    if key_hint:
        # Strongly prefer key_hint if it matches reasonably in both files.
        pick_a = _best_match_by_name(profiles_a, key_hint)
        pick_b = _best_match_by_name(profiles_b, key_hint)
        conf = min(pick_a["confidence"], pick_b["confidence"])
        reason = f"key_hint matched: {pick_a['column']} / {pick_b['column']}"
        return KeyPick(pick_a["column"], pick_b["column"], round(conf, 4), reason, []).__dict__

    # Candidate selection: high uniqueness + low missing + looks like id/email.
    excludes = {normalize_column_name(c) for c in (exclude_columns or []) if c}
    cand_a = [c for c in _candidates(profiles_a) if normalize_column_name(c) not in excludes]
    cand_b = [c for c in _candidates(profiles_b) if normalize_column_name(c) not in excludes]
    if not cand_a:
        cand_a = cols_a[: min(5, len(cols_a))]
    if not cand_b:
        cand_b = cols_b[: min(5, len(cols_b))]

    best_pair = ("", "", -1.0, "")
    alternatives: list[tuple[str, str, float]] = []

    # Pre-normalize unique keys to estimate overlap cheaply.
    keys_a_cache: dict[str, set[str]] = {}
    keys_b_cache: dict[str, set[str]] = {}

    for a_col in cand_a:
        keys_a_cache[a_col] = _sample_unique_keys(df_a[a_col])
    for b_col in cand_b:
        keys_b_cache[b_col] = _sample_unique_keys(df_b[b_col])

    for a_col in cand_a:
        a_prof = next((p for p in profiles_a if p["column_name"] == a_col), None)
        if not a_prof:
            continue
        for b_col in cand_b:
            b_prof = next((p for p in profiles_b if p["column_name"] == b_col), None)
            if not b_prof:
                continue

            score = 0.0
            # Name similarity / hints.
            name_sim = _sim(normalize_column_name(a_col), normalize_column_name(b_col))
            if name_sim > 0:
                score += 30.0 * name_sim

            # Uniqueness / missingness.
            score += 40.0 * min(1.0, float(a_prof["unique_ratio"]))
            score += 40.0 * min(1.0, float(b_prof["unique_ratio"]))
            score += 20.0 * min(1.0, float(a_prof["non_null_ratio"]))
            score += 20.0 * min(1.0, float(b_prof["non_null_ratio"]))

            # Looks-like bonuses.
            score += 30.0 * max(float(a_prof["email_like_score"]), float(a_prof["id_like_score"]))
            score += 30.0 * max(float(b_prof["email_like_score"]), float(b_prof["id_like_score"]))

            # Cross-file overlap bonus (the key must link rows).
            a_keys = keys_a_cache.get(a_col) or set()
            b_keys = keys_b_cache.get(b_col) or set()
            overlap = _overlap_ratio(a_keys, b_keys)
            score += 40.0 * overlap

            alternatives.append((a_col, b_col, score))
            if score > best_pair[2]:
                best_pair = (a_col, b_col, score, f"overlap={overlap:.2f}, name_sim={name_sim:.2f}")

    a_best, b_best, raw_score, reason = best_pair
    conf = max(0.0, min(1.0, raw_score / 200.0))  # scores can exceed 100; map to 0-1

    # Top 3 alternatives excluding the best.
    alt_sorted = sorted(alternatives, key=lambda x: x[2], reverse=True)
    alt_payload: list[dict[str, Any]] = []
    for a_col, b_col, sc in alt_sorted[1:4]:
        alt_payload.append({"key_a": a_col, "key_b": b_col, "confidence": round(max(0.0, min(1.0, sc / 200.0)), 4)})

    diagnostics = _key_pair_diagnostics(df_a, df_b, a_best, b_best)
    payload = KeyPick(a_best, b_best, round(conf, 4), f"Best key pair: {reason}", alt_payload).__dict__
    payload.update(diagnostics)
    return payload


def _best_match_by_name(profiles: list[dict[str, Any]], hint: str) -> dict[str, Any]:
    hint_norm = normalize_column_name(hint)
    best = ("", -1.0)
    for p in profiles:
        col = p["column_name"]
        col_norm = normalize_column_name(col)
        sim = _sim(hint_norm, col_norm)
        sc = 100.0 * sim + 20.0 * max(float(p["email_like_score"]), float(p["id_like_score"])) + 10.0 * float(p["non_null_ratio"])
        if sc > best[1]:
            best = (col, sc)
    conf = max(0.0, min(1.0, best[1] / 130.0))
    return {"column": best[0], "confidence": conf}


def _candidates(profiles: list[dict[str, Any]]) -> list[str]:
    cands: list[tuple[str, float]] = []
    for p in profiles:
        col = p["column_name"]
        uniq = float(p["unique_ratio"])
        nn = float(p["non_null_ratio"])
        id_like = float(p["id_like_score"])
        email_like = float(p["email_like_score"])
        score = 0.0
        score += 40.0 * min(1.0, uniq)
        score += 20.0 * min(1.0, nn)
        score += 30.0 * max(id_like, email_like)
        if score >= 45.0:
            cands.append((col, score))
    return [c[0] for c in sorted(cands, key=lambda x: x[1], reverse=True)[:10]]


def _sample_unique_keys(series: pd.Series) -> set[str]:
    s = series.dropna()
    if len(s) == 0:
        return set()
    if len(s) > 20000:
        s = s.sample(n=20000, random_state=7)
    out: set[str] = set()
    for v in s.astype(str).tolist():
        nv = normalize_value(v, "id")
        if nv is None:
            continue
        nv2 = str(nv).strip()
        if not nv2:
            continue
        out.add(nv2)
        if len(out) >= 20000:
            break
    return out


def _key_pair_diagnostics(df_a: pd.DataFrame, df_b: pd.DataFrame, col_a: str, col_b: str) -> dict[str, Any]:
    if not col_a or col_a not in df_a.columns or not col_b or col_b not in df_b.columns:
        return {
            "duplicate_keys_a": 0,
            "duplicate_keys_b": 0,
            "matched_key_count": 0,
            "only_in_a_count": int(len(df_a)),
            "only_in_b_count": int(len(df_b)),
        }

    a_norm = df_a[col_a].map(lambda v: normalize_value(v, "id"))
    b_norm = df_b[col_b].map(lambda v: normalize_value(v, "id"))
    a_keys = a_norm.dropna().astype(str)
    b_keys = b_norm.dropna().astype(str)
    a_keys = a_keys[a_keys.str.len() > 0]
    b_keys = b_keys[b_keys.str.len() > 0]

    duplicate_a = int(a_keys.duplicated(keep=False).sum())
    duplicate_b = int(b_keys.duplicated(keep=False).sum())

    a_set = set(a_keys.tolist())
    b_set = set(b_keys.tolist())
    inter = len(a_set & b_set)
    only_a = len(a_set - b_set)
    only_b = len(b_set - a_set)

    return {
        "duplicate_keys_a": duplicate_a,
        "duplicate_keys_b": duplicate_b,
        "matched_key_count": inter,
        "only_in_a_count": only_a,
        "only_in_b_count": only_b,
    }


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    denom = max(1, min(len(a), len(b)))
    return float(inter / denom)


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return float(SequenceMatcher(a=a, b=b).ratio())
