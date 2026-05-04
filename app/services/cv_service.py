"""CV document discovery, extraction, search, and structured profiling."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
import pandas as pd
from pypdf import PdfReader

from app.config import settings
from app.core.exceptions import InvalidInputError
from app.utils.dataframe_utils import normalize_column_name


@dataclass
class RegisteredCv:
    cv_id: str
    path: str
    name: str
    extension: str
    loaded_at: str
    char_count: int
    word_count: int
    preview: str


class CvService:
    """Scans CV upload folders and exposes answer-ready candidate profiles."""

    def __init__(self) -> None:
        self._texts: dict[str, str] = {}
        self._meta: dict[str, RegisteredCv] = {}

    def scan_cvs(self) -> dict:
        loaded = []
        failed = []
        current_ids = set()
        if not settings.CV_UPLOAD_DIR.exists():
            pruned_count = len(self._meta)
            self._meta.clear()
            self._texts.clear()
            return {
                "cv_dir": str(settings.CV_UPLOAD_DIR),
                "loaded_count": 0,
                "failed_count": 1,
                "pruned_count": pruned_count,
                "cvs": [],
                "failed": [{"path": str(settings.CV_UPLOAD_DIR), "error": "CV klasoru bulunamadi."}],
                "supported_extensions": sorted(settings.SUPPORTED_CV_EXTENSIONS),
            }

        for path in sorted(settings.CV_UPLOAD_DIR.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in settings.SUPPORTED_CV_EXTENSIONS:
                continue
            try:
                meta = self.load_cv(str(path))
                current_ids.add(meta["cv_id"])
                loaded.append(meta)
            except Exception as exc:
                failed.append({"path": str(path), "error": str(exc)})

        pruned_count = 0
        for cv_id in list(self._meta.keys()):
            if cv_id not in current_ids:
                self._meta.pop(cv_id, None)
                self._texts.pop(cv_id, None)
                pruned_count += 1

        return {
            "cv_dir": str(settings.CV_UPLOAD_DIR),
            "loaded_count": len(loaded),
            "failed_count": len(failed),
            "pruned_count": pruned_count,
            "cvs": loaded,
            "failed": failed,
            "supported_extensions": sorted(settings.SUPPORTED_CV_EXTENSIONS),
        }

    def load_cv(self, file_path: str) -> dict:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in settings.SUPPORTED_CV_EXTENSIONS:
            raise InvalidInputError(f"Desteklenmeyen CV formati: {ext}")

        text = self._extract_text(path)
        cv_id = self._stable_id(path)
        meta = RegisteredCv(
            cv_id=cv_id,
            path=str(path.resolve()),
            name=path.name,
            extension=ext,
            loaded_at=datetime.now(timezone.utc).isoformat(),
            char_count=len(text),
            word_count=len(text.split()),
            preview=text[:600],
        )
        self._texts[cv_id] = text
        self._meta[cv_id] = meta
        return meta.__dict__

    def list_cvs(self) -> list[dict]:
        return [meta.__dict__ for meta in self._meta.values()]

    def iter_cvs(self) -> list[tuple[RegisteredCv, str]]:
        return [(meta, self._texts.get(cv_id, "")) for cv_id, meta in self._meta.items()]

    def get_text(self, cv_id: str) -> str:
        return self._texts.get(cv_id, "")

    def search_cvs(self, query: str, limit: int = 10) -> dict:
        needle = normalize_column_name(query)
        scored = []
        for cv_id, text in self._texts.items():
            normalized_text = normalize_column_name(text)
            score = self._match_score(needle, normalized_text)
            if needle and score < self._min_score(needle):
                continue
            index = normalized_text.find(needle) if needle else 0
            if index < 0:
                token_positions = [normalized_text.find(token) for token in needle.split() if token and normalized_text.find(token) >= 0]
                index = min(token_positions) if token_positions else 0
            start = max(index - 180, 0)
            end = min(index + len(needle) + 360, len(text))
            scored.append((score, {
                "cv": self._meta[cv_id].__dict__,
                "profile": self._profile_from_text(self._meta[cv_id], text, include_full_text=False),
                "snippet": text[start:end],
                "score": score,
            }))
        matches = [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:limit]]
        return {"query": query, "match_count": len(matches), "matches": matches}

    def answer_question(self, question: str, limit: int = 5) -> dict:
        """Return an answer-ready retrieval packet for Onyx CV questions."""

        self.scan_cvs()
        detail_intent = _looks_like_detail_question(question)
        if detail_intent:
            matches = self.search_cvs(question, limit=max(limit, 3))["matches"]
            if matches:
                profiles = [
                    self.get_cv_detail(cv_id=match["cv"]["cv_id"], include_full_text=False)
                    for match in matches[:limit]
                ]
                return {
                    "question": question,
                    "mode": "detail",
                    "matched_count": len(matches),
                    "profiles": profiles,
                    "answer_guidance": "Bu profillerden kullanicinin sordugu alanlari yanitla; ham full_text basma.",
                }
        result = self.search_cvs(question, limit=limit)
        return {
            "question": question,
            "mode": "search",
            "matched_count": result["match_count"],
            "matches": result["matches"],
            "library_summary": self.summarize_library() if result["match_count"] == 0 else {},
            "answer_guidance": "Eslesen CV profillerindeki structured alanlara dayanarak cevap ver; emin degilsen get_cv_detail oner.",
        }

    def analyze_cvs(self, query: str = "", limit: int = 10) -> dict:
        result = self.search_cvs(query, limit)
        return {
            **result,
            "total_cvs": len(self._meta),
            "guidance": "Use matches for shortlist-style answers; do not paste full CV text into chat.",
        }

    def get_cv_detail(self, cv_id: str = "", query: str = "", include_full_text: bool = False) -> dict:
        target_id = cv_id
        if not target_id and query:
            result = self.search_cvs(query, limit=1)
            if result["matches"]:
                target_id = result["matches"][0]["cv"]["cv_id"]
        if not target_id or target_id not in self._meta:
            raise InvalidInputError("CV bulunamadi. cv_id veya aday adi/yetkinlik sorgusu verin.")
        meta = self._meta[target_id]
        text = self._texts.get(target_id, "")
        return self._profile_from_text(meta, text, include_full_text)

    def summarize_library(self) -> dict:
        profiles = [self._profile_from_text(meta, text, include_full_text=False) for meta, text in self.iter_cvs()]
        skill_counter: Counter[str] = Counter()
        position_counter: Counter[str] = Counter()
        city_counter: Counter[str] = Counter()
        education_counter: Counter[str] = Counter()
        form_counter: Counter[str] = Counter()
        for profile in profiles:
            skill_counter.update(profile.get("skills", []))
            if profile.get("position"):
                position_counter[profile["position"]] += 1
            if profile.get("city"):
                city_counter[profile["city"]] += 1
            if profile.get("education"):
                education_counter[profile["education"]] += 1
            if profile.get("form_status"):
                form_counter[profile["form_status"]] += 1
        return {
            "cv_count": len(profiles),
            "top_skills": _counter_items(skill_counter, 20),
            "positions": _counter_items(position_counter, 20),
            "cities": _counter_items(city_counter, 20),
            "education": _counter_items(education_counter, 20),
            "form_status": _counter_items(form_counter, 20),
            "profiles": profiles,
        }

    def audit_library(self) -> dict:
        self.scan_cvs()
        profiles = [self._profile_from_text(meta, text, include_full_text=False) for meta, text in self.iter_cvs()]
        weak = [
            {
                "cv_id": profile["cv_id"],
                "name": profile["name"],
                "file_name": profile["file_name"],
                "char_count": profile["text_quality"]["char_count"],
                "missing_fields": profile["text_quality"]["missing_fields"],
            }
            for profile in profiles
            if profile["text_quality"]["quality"] != "good"
        ]
        return {
            "cv_count": len(profiles),
            "good_count": len(profiles) - len(weak),
            "needs_attention_count": len(weak),
            "needs_attention": weak,
            "guidance": "needs_attention varsa PDF tarama/OCR kaynakli olabilir; dosyayi text-selectable PDF, DOCX veya TXT olarak yeniden yukleyin.",
        }

    @staticmethod
    def _extract_text(path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        if ext == ".docx":
            document = Document(str(path))
            paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
            return "\n".join(paragraphs)
        if ext == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        try:
            if ext == ".csv":
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
            return "\n".join(
                " | ".join("" if pd.isna(value) else str(value) for value in row)
                for row in df.head(200).to_numpy()
            )
        except Exception:
            return path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _stable_id(path: Path) -> str:
        resolved = str(path.resolve()).encode("utf-8")
        return hashlib.sha256(resolved).hexdigest()[:16]

    @staticmethod
    def _match_score(query: str, text: str) -> int:
        if not query:
            return 1
        score = 0
        if query in text:
            score += len(query) + 50
        for token in _important_tokens(query):
            if token and token in text:
                score += len(token) * 3
        return score

    @staticmethod
    def _min_score(query: str) -> int:
        tokens = _important_tokens(query)
        if not tokens:
            return 1
        if len(tokens) == 1:
            return max(3, len(tokens[0]) * 2)
        if any(any(char.isdigit() for char in token) for token in tokens):
            numeric_tokens = [token for token in tokens if any(char.isdigit() for char in token)]
            return max(12, max(len(token) for token in numeric_tokens) * 3)
        return max(8, sum(len(token) for token in tokens) // 2)

    @staticmethod
    def _profile_from_text(meta: RegisteredCv, text: str, include_full_text: bool = False) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header = lines[0] if lines else Path(meta.name).stem
        second = lines[1] if len(lines) > 1 else ""
        header_parts = [part.strip() for part in second.split("|")]
        position = header_parts[0] if header_parts else ""
        city = header_parts[1] if len(header_parts) > 1 else ""
        email = _first_match(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        phone = _first_match(r"0\d{3}\s?\d{3}\s?\d{2}\s?\d{2}", text)
        field_map = _field_map(lines)
        skills = _split_skills(field_map.get("Teknik Yetkinlikler", ""))
        projects = _section_bullets(lines, "Projeler")
        experience = _section_bullets(lines, "Deneyim")
        certifications = _extract_after_label(text, "Sertifikalar:")
        languages = _extract_after_label(text, "Dil:")
        missing_fields = [
            field for field, value in {
                "name": header,
                "position": position,
                "email": email,
                "candidate_id": field_map.get("Aday ID", ""),
                "skills": ", ".join(skills),
                "education": field_map.get("Egitim", ""),
            }.items()
            if not value
        ]
        quality = "good"
        if len(text.strip()) < 250 or len(missing_fields) >= 3:
            quality = "needs_attention"
        profile = {
            "cv_id": meta.cv_id,
            "file_name": meta.name,
            "path": meta.path,
            "name": header,
            "position": position,
            "city": city,
            "email": email,
            "phone": phone,
            "candidate_id": field_map.get("Aday ID", ""),
            "birth_date": field_map.get("Dogum Tarihi", ""),
            "military_status": field_map.get("Askerlik", ""),
            "form_status": field_map.get("Form Durumu", ""),
            "directorate": field_map.get("Direktorluk", ""),
            "source": field_map.get("Kaynak", ""),
            "education": field_map.get("Egitim", ""),
            "skills": skills,
            "experience": experience,
            "projects": projects,
            "certifications": certifications,
            "languages": languages,
            "summary": _section_text(lines, "Ozet Profil", stop_labels={"Kisisel ve Basvuru Bilgileri"}),
            "text_quality": {
                "quality": quality,
                "char_count": len(text),
                "word_count": len(text.split()),
                "missing_fields": missing_fields,
            },
        }
        if include_full_text:
            profile["full_text"] = text
        return profile


cv_service = CvService()


def _important_tokens(query: str) -> list[str]:
    stop = {"ve", "ile", "icin", "için", "olan", "kim", "kimler", "aday", "adaylar", "cv", "var", "mi", "mı"}
    return [token for token in normalize_column_name(query).split() if len(token) > 1 and token not in stop]


def _looks_like_detail_question(question: str) -> bool:
    normalized = normalize_column_name(question)
    return any(token in normalized for token in (
        "detay", "detail", "egitim", "education", "school", "university",
        "yetkin", "skill", "competenc", "deneyim", "experience", "work",
        "proje", "project", "form", "status", "stage", "direktorluk",
        "department", "source", "kaynak", "iletisim", "contact", "mail",
        "email", "telefon", "phone", "ady", "candidate id",
    ))


def _field_map(lines: list[str]) -> dict[str, str]:
    labels = {
        "aday id": "Aday ID",
        "candidate id": "Aday ID",
        "applicant id": "Aday ID",
        "application id": "Aday ID",
        "dogum tarihi": "Dogum Tarihi",
        "askerlik": "Askerlik",
        "form durumu": "Form Durumu",
        "status": "Form Durumu",
        "application status": "Form Durumu",
        "candidate status": "Form Durumu",
        "stage": "Form Durumu",
        "direktorluk": "Direktorluk",
        "department": "Direktorluk",
        "division": "Direktorluk",
        "business unit": "Direktorluk",
        "kaynak": "Kaynak",
        "source": "Kaynak",
        "channel": "Kaynak",
        "egitim": "Egitim",
        "education": "Egitim",
        "academic background": "Egitim",
        "university": "Egitim",
        "teknik yetkinlikler": "Teknik Yetkinlikler",
        "skills": "Teknik Yetkinlikler",
        "technical skills": "Teknik Yetkinlikler",
        "core skills": "Teknik Yetkinlikler",
        "competencies": "Teknik Yetkinlikler",
        "technologies": "Teknik Yetkinlikler",
    }
    result = {}
    for index, line in enumerate(lines[:-1]):
        canonical = labels.get(normalize_column_name(line))
        if canonical:
            result[canonical] = lines[index + 1]
    return result


def _split_skills(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;|]", value or "") if part.strip()]


def _section_bullets(lines: list[str], label: str) -> list[str]:
    items = []
    in_section = False
    stop = {
        "projeler", "projects", "project experience",
        "sertifikalar ve diller", "certifications and languages", "certifications", "languages",
        "kisisel ve basvuru bilgileri", "personal and application information", "personal information",
        "teknik yetkinlikler", "skills", "technical skills", "education", "egitim",
        "deneyim", "experience", "work experience", "professional experience",
    }
    targets = _section_aliases(label)
    for line in lines:
        normalized = normalize_column_name(line)
        if normalized in targets:
            in_section = True
            continue
        if in_section and normalized in stop and normalized not in targets:
            break
        if in_section and (line.startswith("•") or line.startswith("-")):
            items.append(line.lstrip("•- ").strip())
    return items


def _section_text(lines: list[str], label: str, stop_labels: set[str]) -> str:
    values = []
    in_section = False
    targets = _section_aliases(label)
    stops = {normalize_column_name(item) for item in stop_labels}
    if "Kisisel ve Basvuru Bilgileri" in stop_labels:
        stops.update({"personal information", "personal and application information", "application information"})
    for line in lines:
        normalized = normalize_column_name(line)
        if normalized in targets:
            in_section = True
            continue
        if in_section and normalized in stops:
            break
        if in_section:
            values.append(line)
    return " ".join(values)


def _extract_after_label(text: str, label: str) -> str:
    label_aliases = {
        "Sertifikalar:": ["Sertifikalar:", "Certifications:", "Certificates:"],
        "Dil:": ["Dil:", "Languages:", "Language:"],
    }.get(label, [label])
    for line in text.splitlines():
        stripped = line.strip()
        for alias in label_aliases:
            if stripped.lower().startswith(alias.lower()):
                return stripped.split(alias, 1)[1].strip()
    return ""


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _counter_items(counter: Counter[str], limit: int) -> list[dict]:
    return [{"value": key, "count": int(value)} for key, value in counter.most_common(limit)]


def _section_aliases(label: str) -> set[str]:
    normalized = normalize_column_name(label)
    aliases = {
        "ozet profil": {"ozet profil", "summary", "profile summary", "professional summary", "about"},
        "projeler": {"projeler", "projects", "project experience", "selected projects"},
        "deneyim": {"deneyim", "experience", "work experience", "professional experience", "employment history"},
    }
    return aliases.get(normalized, {normalized})
