"""
HR CV Analyzer MCP - Text Cleaner
CV metinlerini normalize eder, gereksiz boşlukları temizler.
"""

import re
import unicodedata


def clean_text(text: str) -> str:
    """CV metnini temizler ve normalize eder."""
    if not text:
        return ""

    # Unicode normalizasyonu (Türkçe karakterler korunsun)
    text = unicodedata.normalize("NFKD", text)
    # Kontrol karakterlerini kaldır (newline ve tab hariç)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t\r")
    # Çoklu boşlukları tek boşluk yap
    text = re.sub(r"[ \t]+", " ", text)
    # Çoklu satır sonu — en fazla 2 ardışık
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Satır başı/sonu boşlukları
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


def normalize_for_search(text: str) -> str:
    """Arama/eşleştirme için metni normalize eder."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s\+\#\./]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_sections(text: str) -> dict[str, str]:
    """CV metnini bölümlere ayırır (Eğitim, Deneyim, Yetenekler vb.)."""

    section_headers: dict[str, list[str]] = {
        "summary": [
            "summary", "özet", "objective", "profile", "profil", "about",
            "hakkımda", "kişisel bilgiler", "personal information", "personal details",
        ],
        "education": [
            "education", "eğitim", "öğrenim", "akademik", "academic",
            "educational background", "eğitim bilgileri",
        ],
        "experience": [
            "experience", "deneyim", "iş deneyimi", "work experience",
            "professional experience", "çalışma deneyimi", "iş tecrübesi",
            "employment history", "career",
        ],
        "skills": [
            "skills", "yetkinlikler", "beceriler", "teknik beceriler",
            "technical skills", "yetenekler", "competencies", "technologies",
            "teknolojiler", "araçlar", "tools",
        ],
        "projects": [
            "projects", "projeler", "proje deneyimleri", "project experience",
        ],
        "certifications": [
            "certifications", "sertifikalar", "certificates", "sertifika",
            "lisanslar", "licenses",
        ],
        "languages": [
            "languages", "diller", "yabancı dil", "language skills",
        ],
        "references": [
            "references", "referanslar",
        ],
    }

    lines = text.split("\n")
    sections: dict[str, str] = {}
    current_section = "header"
    section_lines: dict[str, list[str]] = {"header": []}

    for line in lines:
        line_clean = line.strip()
        line_lower = line_clean.lower().strip(":").strip("-").strip("–").strip()

        matched_section = None
        for section_key, headers in section_headers.items():
            if line_lower in headers or any(line_lower.startswith(h) for h in headers):
                # Gerçek başlık mı yoksa uzun cümle mi kontrol et
                if len(line_clean.split()) <= 5:
                    matched_section = section_key
                    break

        if matched_section:
            current_section = matched_section
            if current_section not in section_lines:
                section_lines[current_section] = []
        else:
            if current_section not in section_lines:
                section_lines[current_section] = []
            section_lines[current_section].append(line)

    for key, content_lines in section_lines.items():
        sections[key] = "\n".join(content_lines).strip()

    return sections
