"""Executive summary helpers."""

from __future__ import annotations


def build_survey_executive_summary(overview: dict, group_analysis: dict | None = None, comment_analysis: dict | None = None) -> str:
    metrics = overview.get("overall_metrics", {})
    profile = overview.get("dataset_profile", {})
    executive = overview.get("executive_summary", {})
    lines = [
        "# Yönetici Özeti",
        "",
        f"Dosyada **{profile.get('row_count', metrics.get('response_count', 0))} kayıt** ve **{profile.get('column_count', 0)} kolon** bulunmaktadır.",
    ]
    if metrics.get("overall_score") is not None:
        lines.append(f"Genel skor ortalaması **{metrics['overall_score']}** seviyesindedir.")
    lines.extend(["", "## En Kritik Bulgular"])
    for finding in executive.get("critical_findings", [])[:4]:
        lines.append(f"- {finding}")
    if not executive.get("critical_findings"):
        lines.append("- Analiz için yeterli skor veya yorum kolonu tespit edilemedi.")

    lines.extend(["", "## Güçlü Alanlar"])
    highest = metrics.get("highest_score_columns", [])
    if highest:
        for item in highest[:4]:
            lines.append(f"- {item['column']}: ortalama {item['mean']}")
    else:
        lines.append("- Güçlü alan çıkarımı için skor kolonu bulunamadı.")

    lines.extend(["", "## Riskli / Gelişime Açık Alanlar"])
    lowest = metrics.get("lowest_score_columns", [])
    if lowest:
        for item in lowest[:4]:
            lines.append(f"- {item['column']}: ortalama {item['mean']}")
    else:
        lines.append("- Risk alanı çıkarımı için skor kolonu bulunamadı.")

    if group_analysis:
        lines.extend(["", "## Grup/Kategori Bazlı Analiz"])
        for item in group_analysis.get("lowest_groups", [])[:3]:
            lines.append(f"- Düşük skor: {item['group']} ({item.get('overall_score')})")
        for item in group_analysis.get("highest_groups", [])[:3]:
            lines.append(f"- Yüksek skor: {item['group']} ({item.get('overall_score')})")

    if comment_analysis:
        lines.extend(["", "## Yorum ve Tema Analizi"])
        for theme, count in list(comment_analysis.get("theme_counts", {}).items())[:6]:
            lines.append(f"- {theme}: {count} yorum")

    lines.extend([
        "",
        "## Önerilen Aksiyonlar",
        "",
        "### 0-30 Gün",
        "- En düşük skor alan başlıklarda ilgili grup/kategori kırılımı ile kök neden oturumu planla.",
        "- İlk 3 gelişim alanı için aksiyon sahibi ve hedef tarih belirle.",
        "",
        "### 30-60 Gün",
        "- Tema analizinde tekrar eden konular için süreç veya iletişim iyileştirmesi başlat.",
        "- Takip metriği belirleyip ara ölçüm planı oluştur.",
        "",
        "## Kısa Sonuç",
        "Sonuçlar, güçlü alanların korunması ve düşük skor/olumsuz tema üreten başlıklarda sahipli aksiyon alınması gerektiğini göstermektedir.",
    ])
    return "\n".join(lines)


def build_candidate_pool_summary(pool: dict) -> str:
    selected = pool.get("selected_file", {}) or {}
    name = selected.get("name") or selected.get("file", {}).get("name") or "Aday Havuzu"
    row_count = pool.get("row_count") or pool.get("dataset_profile", {}).get("rows") or 0
    resolved = pool.get("resolved_columns", {}) or {}
    dists = pool.get("distributions", {}) or {}
    missing_focus = pool.get("missing_focus", []) or []
    duplicates = pool.get("duplicates", {}) or {}

    lines = [
        "# Aday Havuzu Raporu",
        "",
        f"Dosya: **{name}**",
        f"Toplam kayit: **{row_count}**",
        "",
        "## Genel Ozet",
        "- Bu rapor aday havuzu dagilimlarini, eksik veri risklerini ve olasi duplicate kayitlari ozetler.",
    ]

    if resolved.get("status"):
        lines.extend(["", "## Surec / Durum Dagilimi"])
        for item in dists.get("status", [])[:10]:
            lines.append(f"- {item['value']}: {item['count']} (%{item['percent']})")

    lines.extend(["", "## Onemli Kirilimlar"])
    for key, title in (("university", "Okul / Universite"), ("major", "Bolum"), ("city", "Sehir / Lokasyon"), ("experience", "Deneyim"), ("military", "Askerlik")):
        if dists.get(key):
            lines.append(f"- **{title}**: ilk {min(8, len(dists[key]))} deger gorunur.")
            for item in dists[key][:8]:
                lines.append(f"  - {item['value']}: {item['count']} (%{item['percent']})")

    lines.extend(["", "## Eksik Veri Sinyalleri"])
    if missing_focus:
        for item in missing_focus[:10]:
            lines.append(f"- {item['field']} ({item['column']}): %{item['missing_rate_percent']} eksik")
    else:
        lines.append("- Odak alanlar icin eksik veri metrikleri cikartilamadi.")

    lines.extend(["", "## Duplicate Analizi"])
    lines.append(f"- Kullanilan anahtar(lar): {', '.join(pool.get('duplicate_keys_used') or []) or '(auto)'}")
    lines.append(f"- Duplicate satir sayisi: **{duplicates.get('duplicate_row_count', 0)}**")
    lines.append(f"- Duplicate grup sayisi: **{duplicates.get('duplicate_group_count', 0)}**")

    lines.extend(["", "## Aksiyon Onerileri"])
    if duplicates.get("duplicate_row_count", 0):
        lines.append("- Email/telefon/id gibi anahtarlarla duplicate kayitlari tekillestirip tek kaynak gercegi olusturun.")
    if missing_focus and missing_focus[0].get("missing_rate_percent", 0) and missing_focus[0]["missing_rate_percent"] >= 5:
        lines.append("- En cok eksik veri olan alanlar icin form/entegrasyon kaynaklarini kontrol edin (zorunlu alan/validation).")
    lines.append("- Surec durumlarini standart bir sozlukle normalize edin (pipeline raporlarinin tutarliligi icin).")

    if pool.get("export_path"):
        lines.extend(["", "## Uretilen Ciktilar", f"- Export: {pool['export_path']}"])

    return "\n".join(lines)


def build_shortlist_summary(shortlist: dict) -> str:
    role = shortlist.get("role") or "Role"
    criteria = shortlist.get("criteria", {}) or {}
    items = shortlist.get("shortlist", []) or []

    lines = [
        "# Shortlist Raporu",
        "",
        f"Rol: **{role}**",
        "",
        "## Kriterler",
        f"- Required: {', '.join(criteria.get('required_skills') or []) or '-'}",
        f"- Preferred: {', '.join(criteria.get('preferred_skills') or []) or '-'}",
        "",
        "## Sonuc",
        f"- Tarama yapilan aday/CV sayisi: **{shortlist.get('candidate_count', 0)}**",
        f"- Shortlist uzunlugu: **{len(items)}**",
        "",
        "## Shortlist (Ilk 10)",
    ]
    for item in items[:10]:
        lines.append(f"- #{item.get('rank')}: {item.get('candidate')} — skor {item.get('fit_score')}")
        miss = item.get("missing_required") or []
        if miss:
            lines.append(f"  - Eksik required: {', '.join(miss)}")
        pref = item.get("matched_preferred") or []
        if pref:
            lines.append(f"  - Matched preferred: {', '.join(pref[:6])}")
        if item.get("recommended_next_step"):
            lines.append(f"  - Next step: {item['recommended_next_step']}")

    lines.extend(["", "## Not", "- Bu skor otomatik is alim karari degildir; gorusme onceliklendirme destegidir."])
    return "\n".join(lines)


def build_data_quality_summary(audit: dict) -> str:
    # audit_spreadsheet_quality payload is tool-facing; we keep this summary generic.
    profile = (audit or {}).get("profile") or (audit or {}).get("dataset_profile") or {}
    detected = (audit or {}).get("detected_columns") or {}
    warnings = (audit or {}).get("warnings") or []
    rows = profile.get("rows") or profile.get("row_count") or 0
    cols = profile.get("column_count") or len(profile.get("columns") or []) or 0

    lines = [
        "# Veri Kalite Raporu",
        "",
        f"Kayit: **{rows}** | Kolon: **{cols}**",
        "",
        "## Tespitler",
    ]
    keys = detected.get("key_columns") or []
    if keys:
        lines.append(f"- Olası anahtar kolonlar: {', '.join(keys[:5])}")
    missing = profile.get("missing_rates_percent") or {}
    if missing:
        top_missing = sorted(missing.items(), key=lambda kv: kv[1], reverse=True)[:8]
        lines.append("- En cok eksik veri olan kolonlar:")
        for col, rate in top_missing:
            lines.append(f"  - {col}: %{rate}")
    if warnings:
        lines.extend(["", "## Uyarilar"])
        for w in warnings[:10]:
            lines.append(f"- {w}")
    lines.extend(["", "## Oneriler", "- Eksik veri/duplicate/anahtar kolon netligi icin audit + query + dedup akisini kullanin."])
    return "\n".join(lines)


def build_department_risk_summary(overview: dict, group_analysis: dict | None = None) -> str:
    metrics = overview.get("overall_metrics", {}) or {}
    profile = overview.get("dataset_profile", {}) or {}
    exec_sum = overview.get("executive_summary", {}) or {}

    lines = [
        "# Departman Risk Raporu",
        "",
        f"Kayit: **{profile.get('row_count', metrics.get('response_count', 0))}** | Grup sayisi: **{metrics.get('group_count', 0)}**",
        "",
        "## Genel Durum",
    ]
    if metrics.get("overall_score") is not None:
        lines.append(f"- Genel skor: **{metrics['overall_score']}**")
    for finding in exec_sum.get("critical_findings", [])[:4]:
        lines.append(f"- {finding}")

    if group_analysis:
        lines.extend(["", "## En Riskli Gruplar (Ilk 10)"])
        for item in (group_analysis.get("lowest_groups") or [])[:10]:
            lines.append(f"- {item['group']}: overall {item.get('overall_score')}, katilimci {item.get('participant_count')}")

        lines.extend(["", "## En Guclu Gruplar (Ilk 5)"])
        for item in (group_analysis.get("highest_groups") or [])[:5]:
            lines.append(f"- {item['group']}: overall {item.get('overall_score')}, katilimci {item.get('participant_count')}")

    lines.extend(["", "## Onerilen Aksiyonlar"])
    lines.append("- En riskli 3 grup icin liderlerle kok neden oturumu + aksiyon sahipligi belirleyin.")
    lines.append("- En dusuk 2-3 skor basligini grup bazinda hedefleyin; iletisim/yonetim/surec gibi temalarda somut aksiyon tanimlayin.")
    lines.append("- 60-90 gun icinde mini olcum ile etkiyi dogrulayin.")
    return "\n".join(lines)
