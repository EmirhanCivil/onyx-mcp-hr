# 69 Tool Kataloğu — Survey & Excel Intelligence MCP

Toplam **69 tool**, 10 kategori. Default kullanım için **3 üst-seviye yönlendirme tool'u** (`answer_*`) yeter; alt seviyeler özel ihtiyaçta veya zincirleme akışta devreye giriyor.

---

## 1. 🛠️ Sistem & Kütüphane (3)

Her sohbetin başında veya yeni dosya atılınca koşturulur.

| # | Tool | Ne işe yarar |
|---|---|---|
| 1 | `get_system_status` | Klasör durumu, dosya sayıları, endpoint'ler ve eksik aksiyonları **tek cevapta** raporlar — sistem sağlık kontrolü. |
| 2 | `refresh_file_library` | CV/Excel/Anket klasörlerini yeniden tarar, registry'i tazeler. |
| 3 | `list_file_library` | Yüklü tüm dosyaları kategoriye göre listeler. |

---

## 2. 🚪 Üst Seviye Yönlendirme (3) — **Default başlangıç**

Doğal dilde gelen sorular için **ilk tercih edilecek** tool'lar. Dosya seçimi, kalite audit'i, alt-seviye tool zincirini kendileri yönetir.

| # | Tool | Ne işe yarar |
|---|---|---|
| 4 | `answer_cv_question` | CV/aday hakkındaki her doğal dil sorusu — arama mı detay mı kendi karar verir. |
| 5 | `answer_excel_question` | Excel/CSV filtreleme, arama, kalite, karşılaştırma — tüm akışı tek seferde yürütür. |
| 6 | `answer_survey_question` | Anket overview + grup analizi + yorum + aksiyon planı pakedi. |

---

## 3. 📄 CV (7)

| # | Tool | Ne işe yarar |
|---|---|---|
| 7 | `scan_cvs` | CV klasörünü baştan tarar, yeni eklenenleri registry'e alır. |
| 8 | `list_cvs` | Sistemdeki tüm CV'leri listeler (dosya adı, ad, kısa özet). |
| 9 | `audit_cv_library` | Her CV'nin metin kalitesini ölçer ("PDF okunmuyor", "OCR gerek" gibi). |
| 10 | `summarize_cv_library` | Havuzdaki yetkinlik/pozisyon dağılımı, aday sayısı. |
| 11 | `get_cv_detail` | Tek aday detayı — eğitim, deneyim, projeler, iletişim, form durumu. |
| 12 | `search_cvs` | CV metinlerinde **basit** anahtar kelime araması. |
| 13 | `analyze_cvs` | Yetkinlik/dil/deneyim bazlı **yapılandırılmış** filtre. |

---

## 4. 📊 Excel — Dosya Tanıma & Yükleme (8)

| # | Tool | Ne işe yarar |
|---|---|---|
| 14 | `scan_uploads` | Excel klasörünü yeniden tarar. |
| 15 | `list_loaded_spreadsheets` | Şu an pandas registry'de yüklü dosyaları listeler. |
| 16 | `list_available_files` | Belirli kategorideki (excel/cv/survey) dosyaları listeler. |
| 17 | `find_spreadsheet` | Dosya adı, kolon adı veya kategoriye göre dosya bul. |
| 18 | `load_spreadsheet` | Dosya path'i verilen Excel/CSV'i registry'e yükle. |
| 19 | `profile_spreadsheet` | Dosyanın profilini çıkar — satır/kolon, dtypes, ilk N satır preview. |
| 20 | `inspect_workbook_sheets` | Çoklu sheet workbook'ta sheet envanteri — en dolu sheet'i öner. |
| 21 | `analyze_workbook_structure` | Tüm sheet'leri profilleyip veri sheet'lerini ayırır, strateji önerir. |

---

## 5. 🔍 Excel — Kalite & Sorgulama (10)

| # | Tool | Ne işe yarar |
|---|---|---|
| 22 | `audit_spreadsheet_quality` | Eksik veri, duplicate, format problemi, önerilen tool taraması. |
| 23 | `summarize_spreadsheet_column` | Tek kolon için değer dağılımı (top N + frekans). |
| 24 | `filter_spreadsheet_rows` | Kolon/değer çiftiyle satır filtreler — preview döner. |
| 25 | `query_spreadsheet_rows` | **Full scan** sorgu — kesin matched_count + preview/export. |
| 26 | `auto_query_spreadsheet_rows` | File_id istemeden uygun dosyayı seçer, full scan yapar. |
| 27 | `auto_filter_excel_rows` | File_id istemeden doğal dil filtre — kullanıcının ifadesi `query`'e geçer. |
| 28 | `find_duplicate_rows` | Anahtar kolona göre duplicate kayıtları bulur (silmez). |
| 29 | `deduplicate_spreadsheet` | Duplicate temizler ve gerekirse yeni dosya export eder. |
| 30 | `normalize_hr_columns` | TR/EN kolonları HR canonical alanlara eşler (email, telefon, durum...). |
| 31 | `calculate_hr_data_quality_score` | Aday Excel'i için **0–100 veri kalite skoru**. |

---

## 6. ⚖️ Excel — Karşılaştırma (6)

| # | Tool | Ne işe yarar |
|---|---|---|
| 32 | `compare_spreadsheet_columns` | İki dosyanın kolon adları/varlıklarını kıyaslar. |
| 33 | `compare_spreadsheet_rows` | İki dosya arasında farklı satırları bulur. |
| 34 | `compare_spreadsheet_by_key` | Anahtar kolona göre değişen kayıtları bulur. |
| 35 | `auto_compare_spreadsheets` | Otomatik kolon eşleme ile iki dosyayı kıyaslar (kolon adları farklı olsa bile). |
| 36 | `auto_compare_excel_changes` | İş kolonlarındaki değişimi otomatik bulur (form durumu, fiyat...). |
| 37 | `semantic_compare_excel_field` | Sadece tek bir alan/kavram için değişimi raporla ("fiyat değişti mi"). |

---

## 7. 📈 Anket Analizi (7)

| # | Tool | Ne işe yarar |
|---|---|---|
| 38 | `auto_analyze_survey` | Otomatik dosya seçimi + overview + grup + yorum + grafik + rapor — **tek komut**. |
| 39 | `analyze_survey_overview` | Genel özet: katılım, ortalamalar, önerilen analizler. |
| 40 | `analyze_survey_numeric` | Seçilen kolonlar için ortalama, medyan, min, max, std. |
| 41 | `analyze_survey_by_group` | Skorları departman/lokasyon/birim kırılımında gösterir. |
| 42 | `analyze_survey_comments` | Açık uçlu yorumlardan tema + duygu kırılımı. |
| 43 | `create_survey_executive_summary` | Yönetici özeti, güçlü/riskli alanlar, aksiyon paketi. |
| 44 | `compare_survey_periods` | İki dönemi (Q1 vs Q2) departman bazlı skor değişimi açısından karşılaştırır. |

---

## 8. 🖼️ Grafik (5)

Default 3 grafik + **2 opt-in premium** (kullanıcıya sorulup üretilir).

| # | Tool | Ne işe yarar |
|---|---|---|
| 45 | `create_group_bar_chart` | Grup bazında ortalama skor bar grafiği. |
| 46 | `create_score_heatmap` | Grup × skor boyutu ısı haritası (kırmızı→sarı→yeşil brand cmap). |
| 47 | `create_category_distribution_chart` | Kategori dağılımı için yatay count bar. |
| 48 | `auto_create_survey_visuals` | Algılanan kolonlara göre otomatik grafik paketi (3 default chart). |
| 49 | `create_score_radar` | **🕸️ [OPT-IN]** Top N grup × ≥3 boyut polar radar — yönetici klasiği. |
| 50 | `create_period_delta_chart` | **⚖️ [OPT-IN]** İki dönem skoru için yeşil/kırmızı diverging bar. |

> Premium iki tool agent **otomatik çağırmaz** — kullanıcıya "ister misiniz?" diye sorduktan sonra tetiklenir.

---

## 9. 📑 Rapor (5)

Hepsi Markdown + HTML çıktısı verir; istenirse DOCX/JSON da. HTML brand kit'li (gradient hero, Inter font, table hover, dark mode).

| # | Tool | Ne işe yarar |
|---|---|---|
| 51 | `create_survey_report` | Anket için yönetici raporu (HTML + MD ± DOCX/JSON, grafiklerle entegre). |
| 52 | `create_candidate_pool_report` | Aday havuzu raporu (toplam, durum dağılımı, eksik veri, duplicate). |
| 53 | `create_shortlist_report` | Shortlist raporu — skor + dosya adı + kanıta dayalı parça. |
| 54 | `create_data_quality_report` | Veri kalite raporu — eksik/duplicate/format problemleri. |
| 55 | `create_department_risk_report` | Departman bazlı risk raporu (anket + havuz birleşik). |

---

## 10. 👥 HR İş Akışı (5)

| # | Tool | Ne işe yarar |
|---|---|---|
| 56 | `analyze_candidate_pool` | Toplam aday, durum dağılımı, kırılımlar, eksik veri, duplicate — pool sağlığı. |
| 57 | `match_excel_candidates_to_cvs` | Excel adayları CV dosyalarıyla eşleştir; eşleşmeyenleri raporla/export. |
| 58 | `create_candidate_shortlist` | Role + gerekli yetkinliklere göre CV havuzundan shortlist (puanlı). |
| 59 | `analyze_recruiting_pipeline` | Funnel + kaynak karması + darboğaz + veri kalitesi riski. |
| 60 | `create_survey_action_plan` | Anket sonuçlarından 0–30 ve 30–60 günlük aksiyon planı (owner + takip metriği). |

---

## 11. 🧠 HR Intelligence — Dashboard & Segment (9)

| # | Tool | Ne işe yarar |
|---|---|---|
| 61 | `auto_select_hr_file` | Doğal dil sorgusuna göre en uygun HR dosyasını seç. |
| 62 | `explain_hr_query_plan` | Sorgu için query plan açıklar (debug/şeffaflık için). |
| 63 | `generate_hr_overview_dashboard` | Tek komutla aday havuzu dashboard özeti. |
| 64 | `analyze_candidate_stage_transitions` | İki dönem aday Excel'i arasında durum geçişleri. |
| 65 | `analyze_position_funnel` | Pozisyon bazlı funnel (kaç başvuru → mülakat → teklif). |
| 66 | `compare_candidate_segments` | Okul/şehir/pozisyon vb segment KPI karşılaştırma. |
| 67 | `analyze_survey_root_causes` | Anket düşük skor boyutları için tema + grup birlikte kök neden. |
| 68 | `suggest_hr_questions` | Yüklü dosyalara bakıp örnek HR sorusu önerir. |
| 69 | `clear_spreadsheet_registry` | Yüklü spreadsheet cache'ini temizler. |

---

## Sayım Doğrulaması

3 + 3 + 7 + 8 + 10 + 6 + 7 + 6 + 5 + 5 + 9 = **69** ✓

## Kullanım Önerisi

| Senaryo | Önerilen tool akışı |
|---|---|
| Sohbete giriş | `get_system_status` → `list_file_library` |
| Anket — tek seferlik analiz | `answer_survey_question` (kendisi alt seviyeyi zincirler) |
| Anket — manuel kontrol | `auto_analyze_survey` → premium görsel teklifi |
| Excel havuz raporu | `analyze_candidate_pool` → `create_candidate_pool_report` |
| Aday + role match | `create_candidate_shortlist` → `create_shortlist_report` |
| İki dönem karşılaştırma | `compare_survey_periods` → premium delta grafik teklifi |
