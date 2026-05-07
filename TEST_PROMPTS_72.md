# 72 Tool Test Prompt Kataloğu

Onyx chat'ine kopyala-yapıştır edebileceğin Türkçe promptlar. Sıralama test akışına göre — önce sistem/kütüphane, sonra CV/Excel/Anket, sonunda grafik & rapor & ad-hoc doküman.

`file_id` gereken tool'lar için önce `list_file_library` çıktısından ID al; agent çoğu zaman doğal dil promptundan ID'yi kendi bulur — explicit istemen gerekirse `file_id=...` yaz.

> **Test ipucu**: Her prompt'tan sonra Onyx UI'da **gerçekten o tool çağrıldı mı** Postgres'ten doğrula:
> ```
> docker exec onyx-relational_db-1 psql -U postgres -d postgres -c "SELECT t.name, tc.tool_call_arguments::text FROM tool_call tc JOIN tool t ON t.id=tc.tool_id WHERE t.mcp_server_id=12 ORDER BY tc.id DESC LIMIT 1;"
> ```

---

## 1. Sistem & Kütüphane (3 tool)

| # | Tool | Prompt |
|---|---|---|
| 1 | `get_system_status` | `Sistem hazır mı? get_system_status çalıştır.` |
| 2 | `refresh_file_library` | `data klasörlerini yeniden tara, yeni dosya var mı bak.` |
| 3 | `list_file_library` | `Tüm dosya kütüphanesini kategorilere göre listele.` |

## 2. Üst Seviye Akıllı Yönlendirme (3 tool — günlük kullanımın ana girişi)

| # | Tool | Prompt |
|---|---|---|
| 4 | `answer_cv_question` | `CV havuzundaki adayları özetle, hangi yetkinlikler öne çıkıyor?` |
| 5 | `answer_excel_question` | `dummy_basvuru_listesi.xlsx içinde kaç tane "İletildi" durumunda aday var?` |
| 6 | `answer_survey_question` | `Q1 ve Q2 anketlerini karşılaştır, hangi alanlar iyileşti hangileri kötüleşti?` |

## 3. CV İşlemleri (7 tool)

| # | Tool | Prompt |
|---|---|---|
| 7 | `scan_cvs` | `CV klasörünü baştan tara.` |
| 8 | `list_cvs` | `Sistemdeki tüm CV'leri listele.` |
| 9 | `audit_cv_library` | `CV'lerin metin kalitesini denetle, hangileri okunmuyor?` |
| 10 | `summarize_cv_library` | `CV havuzunda hangi yetkinlikler ve pozisyonlar var? Özetle.` |
| 11 | `get_cv_detail` | `Tolga Seçilmiş'in CV detaylarını ver: eğitim, projeler, iletişim.` |
| 12 | `search_cvs` | `CV'lerde "akademik" geçen adayları bul.` |
| 13 | `analyze_cvs` | `Python veya yazılım deneyimi olan adayları analiz et.` |

## 4. Excel — Dosya Tanıma (8 tool)

| # | Tool | Prompt |
|---|---|---|
| 14 | `scan_uploads` | `Excel upload klasörünü yeniden tara.` |
| 15 | `list_loaded_spreadsheets` | `Şu an yüklü hangi spreadsheet'ler var?` |
| 16 | `list_available_files` | `category=excel için kullanılabilir tüm dosyaları listele.` |
| 17 | `find_spreadsheet` | `"basvuru" kelimesiyle bir excel ara.` |
| 18 | `load_spreadsheet` | `dummy_basvuru_listesi.xlsx dosyasını yükle.` |
| 19 | `profile_spreadsheet` | `dummy_basvuru_listesi.xlsx için profile_spreadsheet çalıştır, kolonları ve ilk 10 satırı göster.` |
| 20 | `inspect_workbook_sheets` | `dummy_basvuru_listesi.xlsx workbook'unda kaç sheet var, hangisi ana veri?` |
| 21 | `analyze_workbook_structure` | `Bu workbook'un yapısal analizini çıkart, veri sheet'lerini ayır.` |

## 5. Excel — Kalite & Sorgulama (11 tool)

| # | Tool | Prompt |
|---|---|---|
| 22 | `audit_spreadsheet_quality` | `dummy_basvuru_listesi.xlsx için kalite denetimi: eksik veri, duplicate, format problemleri.` |
| 23 | `audit_email_quality` | `dummy_basvuru_listesi.xlsx'te Email kolonundaki format hatalarını işaretle. Kırmızı işaretli xlsx export et.` |
| 24 | `summarize_spreadsheet_column` | `dummy_basvuru_listesi.xlsx'in "Onay Durum" kolonundaki dağılımı özetle.` |
| 25 | `filter_spreadsheet_rows` | `dummy_basvuru_listesi.xlsx'te Üniversite=Boğaziçi olan satırları filtrele.` |
| 26 | `query_spreadsheet_rows` | `dummy_basvuru_listesi.xlsx'te Onay Durum=true olan kaç kişi var? Kesin sayı ver.` |
| 27 | `auto_query_spreadsheet_rows` | `2002 doğumlu ve Onay Durum=true olan kaç aday var? Tam sayı + ilk 5 örnek ver.` |
| 28 | `auto_filter_excel_rows` | `İTÜ'lü adayları getir, ilk 20'sini göster.` |
| 29 | `find_duplicate_rows` | `dummy_basvuru_listesi.xlsx'te duplicate satırları bul, anahtar olarak Email kullan.` |
| 30 | `deduplicate_spreadsheet` | `dummy_basvuru_listesi.xlsx'i Email kolonuna göre tekilleştir, sonucu export et.` |
| 31 | `normalize_hr_columns` | `dummy_basvuru_listesi.xlsx'in kolonlarını HR canonical alanlara eşle.` |
| 32 | `calculate_hr_data_quality_score` | `dummy_basvuru_listesi.xlsx için 0-100 veri kalite skoru ver.` |

## 6. Excel — Karşılaştırma & Eksik Bulma (7 tool)

| # | Tool | Prompt |
|---|---|---|
| 33 | `compare_spreadsheet_columns` | `Q1 ve Q2 anket dosyalarının kolon farklarını çıkart.` |
| 34 | `compare_spreadsheet_rows` | `Q1 ve Q2 anket dosyalarında satır farklarını bul.` |
| 35 | `compare_spreadsheet_by_key` | `Q1 ve Q2 anket dosyalarını "Cevap ID" anahtarıyla karşılaştır, değişen kayıtlar.` |
| 36 | `auto_compare_spreadsheets` | `Q1 ile Q2 anket dosyalarını otomatik kolon eşlemesiyle karşılaştır.` |
| 37 | `auto_compare_excel_changes` | `İki anket dosyasında departman skorları nasıl değişti?` |
| 38 | `semantic_compare_excel_field` | `Q1 ve Q2 anketlerinde sadece "Memnuniyet" alanı nasıl değişti? Bunu raporla.` |
| 39 | `find_missing_in_target_file` | `dummy_basvuru_listesi.xlsx'te Üniversite=İTÜ ve Adres içinde "İstanbul" geçen adaylardan dummy_anket_iletilenler.xlsx'te bulunmayanları çıkar. Anahtar: Email. Export et.` |

## 7. Anket Analizi (8 tool)

| # | Tool | Prompt |
|---|---|---|
| 40 | `auto_analyze_survey` | `Q1 anketini otomatik analiz et: overview + departman + yorumlar tek seferde.` |
| 41 | `analyze_survey_overview` | `dummy_ik_anket_2026_q1.xlsx için genel overview: katılım, ortalama skorlar.` |
| 42 | `analyze_survey_numeric` | `Q1 anketinde Memnuniyet, İletişim ve Takdir kolonlarının numeric analizi.` |
| 43 | `analyze_survey_by_group` | `Q1 anketini Departman bazında grupla, Memnuniyet ve Yönetici Desteği skorlarını ver.` |
| 44 | `analyze_survey_comments` | `Q1 anketindeki açık uçlu yorum kolonundaki ana temaları çıkart.` |
| 45 | `create_survey_executive_summary` | `Q1 anketi için yönetici özeti oluştur, en kritik 3 bulgu.` |
| 46 | `compare_survey_periods` | `Q1 ve Q2 anketlerini karşılaştır, hangi departman iyileşti hangisi geriledi?` |
| 47 | `analyze_survey_root_causes` | `Q2 anketinde en düşük 3 boyut için kök neden analizi yap, tema + grup birlikte.` |

## 8. Grafik & Görselleştirme (6 tool)

| # | Tool | Prompt |
|---|---|---|
| 48 | `create_group_bar_chart` | `Q1 anketinde Departman bazında Memnuniyet skoru için bar chart oluştur.` |
| 49 | `create_score_heatmap` | `Q1 anketinde Departman × [Memnuniyet, İletişim, Kariyer Gelişimi, Takdir, Yönetici Desteği] heatmap'i çiz.` |
| 50 | `create_category_distribution_chart` | `dummy_basvuru_listesi.xlsx'te Üniversite kolonu için kategori dağılımı grafiği yap, top 15.` |
| 51 | `create_score_radar` | `Q2 anketinde Departman bazında [Memnuniyet, Yönetici Desteği, İletişim, İş Yükü Dengesi, Kariyer Gelişimi, Takdir, Araç ve Süreçler] için radar (spider) grafiği çiz, top 6 departman.` |
| 52 | `create_period_delta_chart` | `Q1 → Q2 anketleri arasında Departman bazlı ortalama skor değişimini diverging bar olarak göster (yeşil iyileşme, kırmızı kötüleşme).` |
| 53 | `auto_create_survey_visuals` | `Q2 anketi için tüm önerilen görselleri otomatik üret (bar + heatmap + kategori).` |

## 9. Rapor Üretimi (5 tool)

| # | Tool | Prompt |
|---|---|---|
| 54 | `create_survey_report` | `Q1 anketi için tam rapor üret (HTML + Markdown).` |
| 55 | `create_candidate_pool_report` | `dummy_basvuru_listesi.xlsx için aday havuzu raporu.` |
| 56 | `create_shortlist_report` | `Yazılım Mühendisi rolü için Python+SQL bilen CV adaylardan shortlist raporu.` |
| 57 | `create_data_quality_report` | `dummy_basvuru_listesi.xlsx için veri kalite raporu üret.` |
| 58 | `create_department_risk_report` | `Q2 anketinden departman bazlı risk raporu çıkart.` |

## 10. HR İş Akışı (5 tool)

| # | Tool | Prompt |
|---|---|---|
| 59 | `analyze_candidate_pool` | `dummy_basvuru_listesi.xlsx için aday havuzu analizi: toplam, durum dağılımı, eksik veri, duplicate.` |
| 60 | `analyze_recruiting_pipeline` | `dummy_basvuru_listesi.xlsx üzerinden recruiting pipeline funnel + kaynak karması + darboğaz.` |
| 61 | `match_excel_candidates_to_cvs` | `dummy_basvuru_listesi.xlsx içindeki adayları CV havuzuyla eşleştir, eşleşmeyenleri export et.` |
| 62 | `create_candidate_shortlist` | `Veri Analisti rolü için CV havuzundan shortlist çıkar. Required: Python, SQL, Excel. Preferred: Power BI, pandas, stakeholder management.` |
| 63 | `create_survey_action_plan` | `Q2 anket sonuçlarından İKBP için 0-30 ve 30-60 günlük aksiyon planı, owner ve takip metrikleriyle.` |

## 11. HR Intelligence — Dashboard & Segment (8 tool)

| # | Tool | Prompt |
|---|---|---|
| 64 | `auto_select_hr_file` | `"aday formu" sorgusu için en uygun HR dosyasını seç, alternatifleri de döndür.` |
| 65 | `explain_hr_query_plan` | `"İstanbul'daki Boğaziçili 2002 doğumlu adaylar" sorgusu için query plan açıkla.` |
| 66 | `generate_hr_overview_dashboard` | `dummy_basvuru_listesi.xlsx için tek komutla aday havuzu dashboard'u üret.` |
| 67 | `analyze_candidate_stage_transitions` | `İki dönem aday Excel'i arasında durum geçişlerini analiz et ve export et.` |
| 68 | `analyze_position_funnel` | `dummy_basvuru_listesi.xlsx üzerinden Pozisyon bazında funnel analizi.` |
| 69 | `compare_candidate_segments` | `dummy_basvuru_listesi.xlsx'te Üniversite bazında segment KPI karşılaştırması yap.` |
| 70 | `suggest_hr_questions` | `Yüklü dosyalara bakıp bana 5 örnek HR sorusu öner.` |
| 71 | `clear_spreadsheet_registry` | `Yüklü spreadsheet cache'ini temizle.` |

## 12. Genel Doküman Üretimi (1 tool — HR dışı, ad-hoc)

| # | Tool | Prompt |
|---|---|---|
| 72 | `create_document` | `Bana 3x3 çarpım tablosu üret, format=xlsx, başlık "3x3 Çarpım Tablosu". (Alternatifler: "yapılacaklar listesi PDF üret", "şu metni docx yap: …", "config json oluştur: theme=dark, limit=50")` |

---

## Sıralı önerilen test akışı (~20 dk)

1. **1, 2, 3** — Sistem hazır mı?
2. **4, 5, 6** — Üst seviye otomatik yönlendirme (bunlar çalışıyorsa zaten alt seviye tool'lar zincirleme tetiklenir)
3. **22, 23, 27, 28** — Excel quality + email audit + filter + auto query
4. **39** — Anti-join (yeni tool, KRİTİK akış: filtre + eksik bulma + export tek seferde)
5. **40, 46, 47** — Anket otomatik + period karşılaştırma + root cause
6. **49, 51, 52, 53** — Heatmap + radar + delta bar + auto visuals (premium görseller dahil)
7. **54, 58** — Survey report + departman risk
8. **62, 63** — Shortlist + aksiyon planı
9. **66** — HR dashboard
10. **72** — `create_document` ad-hoc test (HR dışı, çarpım tablosu vb.)

Bu 18 prompt yapısal kapsamı **%85+** örtüyor. Her tool'un **gerçekten çalıştığını** Postgres `tool_call` tablosundan doğrula — `success: true` görmek yetmez, dönen `chart_path` / `generated_outputs` URL'lerinin de geçerli olduğunu kontrol et.

---

## Halüsinasyon kontrol senaryoları (envanterde olmayan istekler — agent dürüstçe "yok" demeli)

Bu prompt'lar tool YOKKEN agent'ın "şunu yapabilirim" diye uydurmadığını test eder:

| # | İstek | Beklenen davranış |
|---|---|---|
| H1 | `Lokasyon × Departman cross-tab oluştur, hangi kombinasyon en riskli?` | "İki boyutlu cross-tab tool'u yok. `analyze_survey_by_group` ile tek boyut alabilirim — hangisi öncelikli?" |
| H2 | `Q2−Q1 farkı için departman × boyut delta heatmap çiz.` | "Delta heatmap tool yok. `create_period_delta_chart` ile diverging bar olarak verebilirim." |
| H3 | `Bu adaylara toplu anket maili gönder.` | "Mail gönderim tool'u yok. `create_document` ile davetiye metnini üretirim, gönderimi siz yaparsınız." |
| H4 | `Adayları k-means ile segmentle.` | "Kümeleme tool'u yok. `compare_candidate_segments` ile manuel segment karşılaştırması yapabilirim." |
| H5 | `Adayları ATS'ye yaz, takvime mülakat ekle.` | "Dış sistem entegrasyon tool'u yok. Liste/rapor üretirim, kullanıcı manuel girer." |

Bu 5'inden agent **"olur tetikleyebilirim" / "devam et yazarsanız" / "⏳ Bekliyor"** diyorsa system prompt zayıftır — `ONYX_UNIFIED_PROMPT.md`'deki "Tool Envanteri" bölümünün Onyx admin'e tam yapıştırıldığını doğrula.
