"""Premium HR workflows built on top of the file, CV, and survey services."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pandas as pd

from app.analyzers.comment_analyzer import analyze_comments
from app.analyzers.department_analyzer import group_scores
from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.json_exporter import export_json
from app.exporters.markdown_exporter import export_markdown
from app.services.cv_service import cv_service
from app.services.excel_service import excel_service
from app.services.survey_analysis_service import survey_analysis_service
from app.utils.column_detector import detect_columns
from app.utils.dataframe_utils import normalize_column_name, safe_preview


POSITIVE_STATUS_TOKENS = {"olumlu", "advance", "advanced", "hired", "accepted", "teklif", "kabul", "ise alindi"}
NEGATIVE_STATUS_TOKENS = {"olumsuz", "reject", "rejected", "red", "ret", "declined"}
BLOCKED_STATUS_TOKENS = {"bekliyor", "bekleme", "eksik", "pending", "waiting", "missing", "hold"}


@dataclass
class CandidateScore:
    cv_id: str
    display_name: str
    score: float
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    evidence: str
    file_name: str
    path: str | None


class HRService:
    """Decision-support workflows for recruiting and employee engagement."""

    def candidate_shortlist(
        self,
        role: str,
        required_skills: str = "",
        preferred_skills: str = "",
        query: str = "",
        limit: int = 10,
        anonymize: bool = False,
        include_snippets: bool = False,
    ) -> dict:
        """Rank CVs against role criteria without making an automated hiring decision."""

        cv_service.scan_cvs()
        required = _parse_terms(required_skills)
        preferred = _parse_terms(preferred_skills)
        query_terms = _parse_terms(query)
        if not required and not preferred and query_terms:
            required = query_terms
        if not required and not preferred:
            raise InvalidInputError("En az bir required_skills, preferred_skills veya query girin.")

        scored = []
        for index, (meta, text) in enumerate(cv_service.iter_cvs(), start=1):
            candidate = self._score_candidate(meta.cv_id, meta.name, meta.path, text, required, preferred, anonymize, index, include_snippets)
            if candidate.score > 0 or not required:
                scored.append(candidate)

        ranked = sorted(scored, key=lambda item: item.score, reverse=True)[: max(1, min(limit, 50))]
        return {
            "role": role,
            "criteria": {
                "required_skills": required,
                "preferred_skills": preferred,
                "query": query,
            },
            "candidate_count": len(scored),
            "shortlist": [
                {
                    "rank": rank,
                    "cv_id": item.cv_id,
                    "candidate": item.display_name,
                    "fit_score": item.score,
                    "matched_required": item.matched_required,
                    "missing_required": item.missing_required,
                    "matched_preferred": item.matched_preferred,
                    "evidence": item.evidence,
                    "file_name": item.file_name if not anonymize else None,
                    "path": item.path if not anonymize else None,
                    "recommended_next_step": _candidate_next_step(item),
                }
                for rank, item in enumerate(ranked, start=1)
            ],
        }

    def recruiting_pipeline(
        self,
        file_query: str = "",
        stage_column: str = "",
        position_column: str = "",
        group_column: str = "",
        source_column: str = "",
        limit: int = 10,
    ) -> dict:
        """Summarize applicant funnel, bottlenecks, source mix, and data-quality risks."""

        excel_service.scan_uploads()
        selected = excel_service.select_file(file_query, "excel")
        if not selected:
            raise InvalidInputError("Aday Excel dosyasi bulunamadi. data/uploads/excel klasorunu kontrol edin.")

        df = file_registry.get_frame(selected["file_id"])
        stage_col = _pick_column(df, stage_column, ["aday durumu", "stage", "status", "durum", "form durumu"])
        position_col = _pick_column(df, position_column, ["basvurulan pozisyon", "pozisyon", "job", "role"], required=False)
        group_col = _pick_column(df, group_column, ["direktorluk", "departman", "department", "birim"], required=False)
        source_col = _pick_column(df, source_column, ["kaynak kanali", "source", "kanal"], required=False)

        stage_counts = _value_counts(df, stage_col, limit=25)
        stage_total = max(len(df), 1)
        stage_summary = [
            {
                **item,
                "percent": round(item["count"] / stage_total * 100, 2),
                "classification": _classify_stage(item["value"]),
            }
            for item in stage_counts
        ]
        classified = Counter(item["classification"] for item in stage_summary)
        bottlenecks = [
            item for item in stage_summary
            if item["classification"] in {"blocked", "negative"} or item["percent"] >= 35
        ][:limit]

        sensitive_columns: list[str] = []
        return {
            "selected_file": selected,
            "row_count": int(len(df)),
            "columns_used": {
                "stage_column": stage_col,
                "position_column": position_col,
                "group_column": group_col,
                "source_column": source_col,
            },
            "funnel": {
                "stage_counts": stage_summary,
                "positive_stage_count": int(classified.get("positive", 0)),
                "negative_stage_count": int(classified.get("negative", 0)),
                "blocked_stage_count": int(classified.get("blocked", 0)),
            },
            "segments": {
                "top_positions": _value_counts(df, position_col, limit) if position_col else [],
                "top_groups": _value_counts(df, group_col, limit) if group_col else [],
                "source_mix": _value_counts(df, source_col, limit) if source_col else [],
            },
            "bottlenecks": bottlenecks,
            "data_quality": self._pipeline_quality(df, selected["file_id"], sensitive_columns),
            "recommended_actions": _pipeline_actions(stage_summary, bottlenecks, sensitive_columns),
            "preview": safe_preview(df, min(limit, 10)),
        }

    def survey_action_plan(
        self,
        file_query: str = "",
        group_col: str = "",
        score_columns: str = "",
        comment_columns: str = "",
        min_group_size: int = 5,
        export: bool = True,
    ) -> dict:
        """Create an HRBP-style action plan from an engagement survey."""

        excel_service.scan_uploads()
        selected = excel_service.select_file(file_query, "survey")
        if not selected:
            raise InvalidInputError("Anket dosyasi bulunamadi. data/uploads/survey klasorunu kontrol edin.")

        df = file_registry.get_frame(selected["file_id"])
        detected = detect_columns(df)
        scores = _parse_explicit_columns(score_columns) or detected["likely_score_columns"][:8] or detected["numeric_columns"][:8]
        group = group_col if group_col in df.columns else (detected["group_columns"][0] if detected["group_columns"] else "")
        comments = _parse_explicit_columns(comment_columns) or detected["comment_columns"][:3]

        overview = survey_analysis_service.overview(selected["file_id"])
        group_result = group_scores(df, group, scores, min_group_size) if group and scores else None
        comment_result = analyze_comments(df, comments) if comments else None
        priority_col = _pick_column(df, "", ["aksiyon onceligi", "priority", "oncelik"], required=False)

        plan = self._build_action_plan(df, selected, scores, group_result, comment_result, priority_col)
        files: list[str] = []
        if export:
            markdown = _action_plan_markdown(plan)
            files.append(export_markdown(markdown, "hr_action_plan"))
            files.append(export_json(plan, "hr_action_plan"))

        return {
            "selected_file": selected,
            "overview": overview,
            "group_analysis": group_result,
            "comment_analysis": comment_result,
            "priority_column": priority_col,
            "action_plan": plan,
            "files": files,
        }

    def _score_candidate(
        self,
        cv_id: str,
        file_name: str,
        path: str,
        text: str,
        required: list[str],
        preferred: list[str],
        anonymize: bool,
        index: int,
        include_snippets: bool,
    ) -> CandidateScore:
        haystack = normalize_column_name(f"{file_name}\n{text}")
        matched_required = [term for term in required if normalize_column_name(term) in haystack]
        matched_preferred = [term for term in preferred if normalize_column_name(term) in haystack]
        missing_required = [term for term in required if term not in matched_required]

        required_ratio = len(matched_required) / max(len(required), 1)
        preferred_ratio = len(matched_preferred) / max(len(preferred), 1) if preferred else 0
        if required and preferred:
            score = round((required_ratio * 75) + (preferred_ratio * 25), 1)
        elif required:
            score = round(required_ratio * 100, 1)
        else:
            score = round(preferred_ratio * 100, 1)

        evidence = "Kisa metin kaniti include_snippets=true ile eklenebilir."
        if include_snippets:
            evidence = _excerpt(text, matched_required + matched_preferred) or "Eslesme dosya adindan veya kisa metinden geldi."
        display = f"Candidate {index:03d}" if anonymize else _candidate_name_from_file(file_name)
        return CandidateScore(cv_id, display, score, matched_required, missing_required, matched_preferred, evidence, file_name, str(Path(path).resolve()))

    def _pipeline_quality(self, df: pd.DataFrame, file_id: str, sensitive_columns: list[str]) -> dict:
        detected = detect_columns(df)
        duplicate_columns = [col for col in (detected.get("key_columns") or []) if col in df.columns][:2]
        duplicate_rows = 0
        if duplicate_columns:
            duplicate_rows = int(df.duplicated(subset=duplicate_columns, keep=False).sum())
        return {
            "file_id": file_id,
            "missing_rates_percent": {
                str(col): round(float(df[col].isna().mean() * 100), 2)
                for col in df.columns
                if df[col].isna().mean() > 0
            },
            "duplicate_rows_on_detected_keys": duplicate_rows,
            "detected_key_columns": duplicate_columns,
        }

    def _build_action_plan(
        self,
        df: pd.DataFrame,
        selected: dict,
        scores: list[str],
        group_result: dict | None,
        comment_result: dict | None,
        priority_col: str,
    ) -> dict:
        lowest_groups = (group_result or {}).get("lowest_groups", [])[:5]
        theme_counts = (comment_result or {}).get("theme_counts", {})
        priority_counts = _value_counts(df, priority_col, 10) if priority_col else []
        score_averages = {}
        for col in scores:
            values = pd.to_numeric(df[col], errors="coerce")
            if not values.dropna().empty:
                score_averages[col] = round(float(values.mean()), 3)

        actions = []
        for item in lowest_groups:
            actions.append({
                "priority": "High",
                "topic": f"{item['group']} dusuk skor takibi",
                "owner": "HRBP + ilgili direktorluk lideri",
                "timeframe": "0-30 gun",
                "recommended_action": "En dusuk 2 skor basligini liderle teyit et, ekip geri bildirim oturumu planla, sahipli aksiyon maddesi ac.",
                "success_metric": "30 gun icinde aksiyon sahibi ve hedef tarih atanmis olsun.",
            })
        for theme, count in list(theme_counts.items())[:5]:
            actions.append({
                "priority": "Medium" if count < 5 else "High",
                "topic": theme,
                "owner": "HRBP",
                "timeframe": "30-60 gun",
                "recommended_action": f"Yorumlarda {count} kez gecen temayi kok neden analiziyle incele.",
                "success_metric": "Tema icin en az 1 surec/iletisim iyilestirmesi tanimlansin.",
            })
        if actions:
            actions.append({
                "priority": "Medium",
                "topic": "Takip olcumu ve kalicilastirma",
                "owner": "HR + Liderlik ekibi",
                "timeframe": "60-90 gun",
                "recommended_action": "Uygulanan aksiyonlarin etkisini olcmek icin pulse/mini olcum yap, metrikleri (skor, tema yogunlugu, katilim) onceki donemle karsilastir.",
                "success_metric": "60-90 gun sonunda en riskli 1-2 baslikta iyilesme sinyali ve takip ritmi olussun.",
            })
        if not actions:
            actions.append({
                "priority": "Medium",
                "topic": "Genel takip",
                "owner": "HR",
                "timeframe": "0-30 gun",
                "recommended_action": "Anket sonuclarini liderlerle paylas, bir sonraki olcum icin takip metrikleri belirle.",
                "success_metric": "Aksiyon plani ve iletisim mesaji yayinlanmis olsun.",
            })

        return {
            "file_name": selected.get("name"),
            "respondent_count": int(len(df)),
            "score_averages": score_averages,
            "lowest_groups": lowest_groups,
            "priority_distribution": priority_counts,
            "top_comment_themes": theme_counts,
            "actions": actions[:10],
            "communication_note": "Sonuclari calisanlarla paylasirken 'geri bildiriminiz duyuldu' mesaji ve ilk aksiyon tarihini net verin.",
        }


def _parse_terms(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"[,;\n|]+", text) if part.strip()]
    if len(parts) == 1 and len(parts[0].split()) <= 6:
        return [part.strip() for part in parts[0].split() if len(part.strip()) > 1]
    return list(dict.fromkeys(parts))


def _parse_explicit_columns(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _pick_column(df: pd.DataFrame, explicit: str, hints: list[str], required: bool = True) -> str:
    if explicit and explicit in df.columns:
        return explicit
    scored = []
    for column in df.columns:
        normalized = normalize_column_name(column)
        score = 0
        for index, hint in enumerate(hints):
            hint_norm = normalize_column_name(hint)
            priority_bonus = (len(hints) - index) * 5
            if hint_norm == normalized:
                score += len(hint_norm) + 100 + priority_bonus
            elif hint_norm in normalized:
                score += len(hint_norm) + 20 + priority_bonus
            for token in hint_norm.split():
                if token in normalized:
                    score += len(token)
        scored.append((score, str(column)))
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    if required:
        raise InvalidInputError(f"Kolon bulunamadi. Ipuclari: {', '.join(hints)}")
    return ""


def _value_counts(df: pd.DataFrame, column: str, limit: int = 10) -> list[dict[str, Any]]:
    if not column or column not in df.columns:
        return []
    counts = (
        df[column]
        .map(lambda item: "(empty)" if pd.isna(item) or str(item).strip() == "" else str(item).strip())
        .value_counts()
        .head(limit)
    )
    return [{"value": str(index), "count": int(value)} for index, value in counts.items()]


def _classify_stage(value: str) -> str:
    normalized = normalize_column_name(value)
    if any(token in normalized for token in POSITIVE_STATUS_TOKENS):
        return "positive"
    if any(token in normalized for token in NEGATIVE_STATUS_TOKENS):
        return "negative"
    if any(token in normalized for token in BLOCKED_STATUS_TOKENS):
        return "blocked"
    return "neutral"


def _sensitive_columns(df: pd.DataFrame) -> list[str]:
    columns = []
    for column in df.columns:
        normalized = normalize_column_name(column)
        if any(hint in normalized for hint in PROTECTED_COLUMN_HINTS):
            columns.append(str(column))
    return columns


def _pipeline_actions(stage_summary: list[dict], bottlenecks: list[dict], sensitive_columns: list[str]) -> list[str]:
    actions = []
    if bottlenecks:
        top = bottlenecks[0]
        actions.append(f"En buyuk darbogaz '{top['value']}' asamasi; SLA ve sorumlu ekip kontrol edilmeli.")
    if not any(item["classification"] == "positive" for item in stage_summary):
        actions.append("Olumlu/ise alim asamasi net gorunmuyor; pipeline status sozlugunu standartlastirin.")
    actions.append("Kaynak kanali ve pozisyon bazli donusumleri haftalik HRBP ritmine alin.")
    return actions


def _candidate_next_step(candidate: CandidateScore) -> str:
    if candidate.missing_required:
        return "Eksik zorunlu yetkinlikleri insan incelemesiyle kontrol et."
    if candidate.score >= 75:
        return "On gorusme veya teknik tarama icin onceliklendir."
    return "Yedek havuzda tut veya farkli rol eslesmesi ara."


def _candidate_name_from_file(file_name: str) -> str:
    stem = Path(file_name).stem
    cleaned = re.sub(r"^\d+[_-]?", "", stem)
    cleaned = re.sub(r"ADY-\d+[_-]?", "", cleaned, flags=re.IGNORECASE)
    return cleaned.replace("_", " ").strip() or stem


def _excerpt(text: str, terms: list[str], window: int = 180) -> str:
    normalized = normalize_column_name(text)
    for term in terms:
        idx = normalized.find(normalize_column_name(term))
        if idx >= 0:
            start = max(idx - window // 2, 0)
            end = min(idx + window, len(text))
            return " ".join(text[start:end].split())
    return ""


def _action_plan_markdown(plan: dict) -> str:
    lines = [
        "# HR Action Plan",
        "",
        f"Dosya: {plan.get('file_name')}",
        f"Katilimci sayisi: {plan.get('respondent_count')}",
        "",
        "## Oncelikli Aksiyonlar",
    ]
    for index, action in enumerate(plan.get("actions", []), start=1):
        lines.extend([
            f"{index}. [{action['priority']}] {action['topic']}",
            f"   - Owner: {action['owner']}",
            f"   - Timeframe: {action['timeframe']}",
            f"   - Action: {action['recommended_action']}",
            f"   - Metric: {action['success_metric']}",
        ])
    lines.extend(["", "## Iletisim Notu", plan.get("communication_note", "")])
    return "\n".join(lines)


hr_service = HRService()
