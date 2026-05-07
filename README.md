# Survey & Excel Intelligence MCP

72 tool'lu Onyx MCP server: CV, Excel/CSV ve anket analizi. Büyük tablolar LLM context'ine taşınmaz; hesaplama ve görselleştirme Python/pandas tarafında yapılır, agent sonuçları yorumlar.

## Çalıştırma

```bash
git clone https://github.com/EmirhanCivil/onyx-mcp-hr.git
cd onyx-mcp-hr
cp .env.example .env
docker compose up -d --build
```

İki container ayağa kalkar:

| Container | Port | İş |
|---|---|---|
| `survey-excel-mcp-onyx` | 8005 | MCP server (FastAPI + mcp Python SDK) |
| `survey-excel-mcp-files` | 8007 | nginx file-serving — Onyx'in chart/rapor link'leri için |

Lokal Python (Docker olmadan):

```bash
python -m venv venv && source venv/bin/activate   # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Onyx'e bağlama

1. **Admin → MCP Servers → Add**
   - URL: `http://host.docker.internal:8005/mcp`
   - Transport: **STREAMABLE_HTTP**
2. **Assistants → New Assistant**
   - Instructions kutusuna [`ONYX_UNIFIED_PROMPT.md`](ONYX_UNIFIED_PROMPT.md) içeriğini komple yapıştır
   - 72 tool'u etkinleştir
3. Test: [`TEST_PROMPTS_72.md`](TEST_PROMPTS_72.md)

## Dosya yerleşimi

Kullanıcı dosyaları:

- `data/uploads/cv` — `.pdf`, `.docx`, `.txt`
- `data/uploads/excel` — `.xlsx`, `.xls`, `.xlsm`, `.xlsb`, `.ods`, `.csv`
- `data/uploads/survey` — aynı tablo formatları

Container açılışında otomatik taranır. Çalışırken yeni dosya eklenince Onyx'te `refresh_file_library` çağır.

Üretilen çıktılar:

- `data/outputs/charts` — PNG grafikler
- `data/outputs/reports` — HTML / Markdown / DOCX raporlar
- `data/outputs/exports` — XLSX export'lar

Hepsi nginx üzerinden `http://localhost:8007/...` URL'leriyle servis edilir.

## Repo'da gelen dummy data

`data/uploads/` altında out-of-the-box test verisi var:

| Dosya | Yer | İçerik |
|---|---|---|
| `dummy_basvuru_listesi.xlsx` | `excel/` | 5500 satır, 22 kolon (ID, Ad Soyad, Email, Cinsiyet, Fakülte, Üniversite, Doğum Tarihi, Adres, Onay Durum, …) |
| `dummy_anket_iletilenler.xlsx` | `excel/` | Ana havuzun anket iletilen alt kümesi |
| `dummy_ik_anket_2026_q1.xlsx` | `survey/` | 1200 yanıt, 7 skor boyutu (Memnuniyet, Yönetici Desteği, İletişim, İş Yükü Dengesi, Kariyer Gelişimi, Takdir, Araç ve Süreçler) |
| `dummy_ik_anket_2026_q2.xlsx` | `survey/` | Aynı yapı, Q2 dönemi |
| 3 PDF CV | `cv/` | Akademik / modern / örnek |

Kendi datanla denemek istiyorsan: `data/uploads/` altındaki dosyaları silip kendi dosyalarını koy, container'ı restart et veya `refresh_file_library` çağır.

## Dosya rehberi

| Dosya | İçerik |
|---|---|
| [`ONYX_UNIFIED_PROMPT.md`](ONYX_UNIFIED_PROMPT.md) | Onyx Assistant Instructions — komple yapıştırılır. 72 tool envanteri + halüsinasyon kuralları dahil. |
| [`TOOL_CATALOG.md`](TOOL_CATALOG.md) | 72 tool listesi, kategorize. |
| [`TEST_PROMPTS_72.md`](TEST_PROMPTS_72.md) | Her tool için bir prompt + sıralı 18-prompt test akışı + halüsinasyon kontrol senaryoları. |
| `tools/test_all_72_tools.py` | MCP üzerinden otomatik integration test — `python tools/test_all_72_tools.py`. |

## Lisans

MIT
