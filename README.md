# Survey & Excel Intelligence MCP

Onyx uzerinden kullanilmak uzere tasarlanmis CV, Excel/CSV ve IK anket analiz MCP server'i.

Ana ilke: buyuk Excel/CSV dosyalari LLM context'ine tasinmaz. Hesaplama, filtreleme, karsilastirma, duplicate temizleme, anket analizi, grafik ve rapor uretimi Python/pandas tarafinda yapilir.

## Dosya Yerlesimi

Dosyalari bu klasorlere koyun:

- `data/uploads/cv`: CV dosyalari (`.pdf`, `.txt`, `.docx`, `.csv`, `.xlsx`, `.xls`)
- `data/uploads/excel`: Genel Excel/CSV/ODS dosyalari
- `data/uploads/survey`: Anket Excel/CSV/ODS dosyalari

Desteklenen tablo formatlari: `.xlsx`, `.xls`, `.xlsm`, `.xlsb`, `.ods`, `.csv`.

MCP acilista bu klasorleri ve alt klasorleri otomatik tarar. Calisirken yeni dosya eklenirse Onyx'te `refresh_file_library` demek yeterlidir.

## Onyx MCP URL

Onyx ile ayni Docker network icinde:

```text
http://survey-excel-mcp-onyx:8005/mcp
```

Host makineden test:

```text
http://localhost:8006/mcp
```

Sabit container IP kullanmayin; container yeniden olusturulunca IP degisebilir.

## Premium Kontrol Tool'lari

- `get_system_status`: Klasorleri, yuklenen dosya sayilarini, endpointleri ve eksik aksiyonlari tek cevapta ozetler.
- `refresh_file_library`: CV, Excel ve anket klasorlerini yeniden tarar.
- `list_file_library`: Tum dosya kutuphanesini kategorilere gore listeler.
- `hr_health_check_prompt`: Onyx'te standart baslangic kontrol akisi.

Onyx'te ilk mesaj olarak sunu yazmak iyi calisir:

```text
get_system_status calistir, sonra dosya kutuphanesini ozetle.
```

## Temel Tool'lar

- `create_candidate_shortlist`: CV havuzundan role/yetkinlige gore aday kisa listesi uretir; otomatik karar vermez.
- `analyze_candidate_pool`: Aday Excel'inden toplam aday, durum dagilimi, kirilimlar, eksik veri ve duplicate ozetini cikarir.
- `match_excel_candidates_to_cvs`: Excel aday kayitlarini CV dosyalariyla eslestirir; eslesmeyenleri raporlar ve export eder.
- `auto_select_hr_file`: Dosya adi vermeden uygun CV/aday Excel/anket dosyasini secer; alternatifleri dondurur.
- `normalize_hr_columns`: TR/EN kolonlari HR canonical alanlara eslestirir (email, telefon, durum, pozisyon vb.).
- `calculate_hr_data_quality_score`: Aday Excel'i icin 0-100 veri kalite skoru (eksik/duplicate/format/CV eslesme).
- `generate_hr_overview_dashboard`: Tek komutla aday havuzu dashboard ozeti.
- `analyze_candidate_stage_transitions`: Iki donem Excel arasinda aday surec gecislerini analiz eder ve export eder.
- `analyze_position_funnel`: Pozisyon bazli funnel analizi.
- `compare_candidate_segments`: Segment KPI karsilastirma (okul/sehir/pozisyon vb).
- `analyze_survey_root_causes`: Anket dusuk skor boyutlari icin tema+grup birlikte kok neden analizi.
- `suggest_hr_questions`: Yuklenen dosyalara gore ornek soru onerileri.
- `analyze_recruiting_pipeline`: Aday Excel'inden funnel, kaynak karmasi, darbogaz ve veri kalitesi ozeti cikarir.
- `create_survey_action_plan`: Anket sonuclarindan HRBP aksiyon plani, sahiplik ve takip metrikleri uretir.
- `find_spreadsheet`: Dosya adi, kolon veya kategoriye gore Excel/anket bulur.
- `inspect_workbook_sheets`: Coklu sheet workbook'larda sheet envanteri cikarir ve en dolu sheet'i onerir.
- `analyze_workbook_structure`: Coklu sheet workbook'larda tum sheet'leri profiller; veri sheet'lerini ayirir ve strateji onerir.
- `audit_spreadsheet_quality`: Her tip Excel/CSV/ODS icin eksik veri, duplicate, format/kalite problemleri ve onerilen tool taramasi yapar.
- `auto_compare_spreadsheets`: Iki dosyayi file_id veya birebir ayni kolon adi bilmeden otomatik kolon eslestirme ile karsilastirir.
- `auto_filter_excel_rows`: File id istemeden uygun Excel'i bulur ve dogal sorguyla satir filtreler.
- `auto_query_spreadsheet_rows`: File id istemeden full-scan sorgu yapar; kesin matched_count + preview/export.
- `filter_spreadsheet_rows`: Kolon/deger veya dogal sorguya gore satirlari filtreler.
- `summarize_spreadsheet_column`: Bir kolondaki deger dagilimini ozetler.
- `compare_spreadsheet_columns`: Iki Excel'in sutun farklarini bulur.
- `compare_spreadsheet_rows`: Iki Excel arasinda farkli satirlari bulur.
- `compare_spreadsheet_by_key`: Anahtar kolona gore degisen kayitlari bulur.
- `find_duplicate_rows`: Duplicate kayitlari bulur.
- `deduplicate_spreadsheet`: Duplicate kayitlari temizler ve gerekirse export uretir.
- `scan_cvs`, `list_cvs`, `search_cvs`, `analyze_cvs`: CV klasorunu tarar, listeler ve metin arar.
- `auto_analyze_survey`: File id istemeden anket overview, grup analizi ve yorum ozetini uretir.
- `analyze_survey_overview`, `analyze_survey_by_group`, `analyze_survey_comments`: Anket analizleri.
- `compare_survey_periods`: Iki anket donemini karsilastirir.
- `create_group_bar_chart`, `create_score_heatmap`, `create_survey_report`: Grafik ve rapor uretir.
- `create_candidate_pool_report`, `create_shortlist_report`, `create_data_quality_report`, `create_department_risk_report`: HTML/Markdown/DOCX raporlari uretir.

## HR Workflow Ornekleri

Aday shortlist:

```text
Python Data Analyst rolu icin create_candidate_shortlist calistir.
required_skills: Python, SQL, Excel
preferred_skills: Power BI, pandas, stakeholder management
```

Aday pipeline:

```text
analyze_recruiting_pipeline calistir, kaynak kanali ve aday durumu darbogazlarini ozetle.
```

Genel dosya kalite kontrolu:

```text
Yeni yukledigim dosyayi audit_spreadsheet_quality ile tara; dosya tipi, eksik veri, duplicate ve onerilen analizleri soyle.
```

Genel karsilastirma:

```text
Iki son Excel'i auto_compare_spreadsheets ile karsilastir; kolon adlari farkliysa otomatik eslestir.
```

Anket aksiyon plani:

```text
create_survey_action_plan calistir; 0-30 gun ve 30-60 gun aksiyonlarini yonetici ozeti olarak yaz.
```

Karar destegi notu: CV shortlist skoru nihai ise alim karari degildir. Yas, cinsiyet, askerlik, kimlik gibi korunmus veya hassas nitelikler karar kriteri yapilmamalidir.

## Local Calistirma

```powershell
.\venv\Scripts\python.exe server.py
```

Docker ile local build:

```powershell
docker compose up -d --build
```

## Sirket PC Kurulumu

Image Docker Hub'da:

```text
memobaba44/survey-excel-mcp:latest
```

Onyx zaten `onyx_default` network'u ile calisiyorsa:

```powershell
docker pull memobaba44/survey-excel-mcp:latest
docker compose -f docker-compose.company.yml up -d
```

Sonra Onyx MCP URL:

```text
http://survey-excel-mcp-onyx:8005/mcp
```

Hosttan kontrol:

```powershell
docker logs --tail 80 survey-excel-mcp-onyx
```

Beklenen satirlar:

```text
Auto-scan uploads: ... dosya yuklendi.
Auto-scan CVs: ... dosya yuklendi.
Uvicorn running on http://0.0.0.0:8005
```

## Onyx Instructions

Onyx agent instructions alani icin hazir prompt:

```text
ONYX_SURVEY_AGENT_PROMPT.md
```
