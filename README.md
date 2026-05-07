# Onyx HR MCP

72 tool'lu Onyx MCP server: CV, Excel/CSV ve anket analizi. Image Docker Hub'da hazır — clone et, `docker compose up` de, Onyx'e bağla.

## Kurulum

```bash
git clone https://github.com/EmirhanCivil/onyx-mcp-hr.git
cd onyx-mcp-hr
cp .env.example .env
docker compose up -d
```

İki container ayağa kalkar:

| Container | Port | İş |
|---|---|---|
| `survey-excel-mcp-onyx` | 8005 | MCP server |
| `survey-excel-mcp-files` | 8007 | Üretilen chart/rapor dosyalarını servis eder |

Image: [`emirhancivil/onyx-mcp-hr:latest`](https://hub.docker.com/r/emirhancivil/onyx-mcp-hr) — `docker compose pull` ile güncellenir.

## Onyx'e bağlama

1. **Admin → MCP Servers → Add**
   - URL: `http://host.docker.internal:8005/mcp`
   - Transport: **STREAMABLE_HTTP**
2. **Assistants → New Assistant**
   - Instructions kutusuna [`ONYX_UNIFIED_PROMPT.md`](ONYX_UNIFIED_PROMPT.md) içeriğini komple yapıştır
   - 72 tool'u etkinleştir

## Dummy data

`data/uploads/` altında repo ile gelir:

| Dosya | Yer | İçerik |
|---|---|---|
| `dummy_basvuru_listesi.xlsx` | `excel/` | 5500 satır, 22 kolon (ID, Ad Soyad, Email, Cinsiyet, Fakülte, Üniversite, Doğum Tarihi, Adres, Onay Durum, …) |
| `dummy_anket_iletilenler.xlsx` | `excel/` | Ana havuzun anket iletilen alt kümesi |
| `dummy_ik_anket_2026_q1.xlsx` | `survey/` | 1200 yanıt, 7 skor boyutu (Memnuniyet, Yönetici Desteği, İletişim, İş Yükü Dengesi, Kariyer Gelişimi, Takdir, Araç ve Süreçler) |
| `dummy_ik_anket_2026_q2.xlsx` | `survey/` | Aynı yapı, Q2 dönemi |
| 3 PDF CV | `cv/` | Akademik / modern / örnek |

Kendi datanla denemek için: `data/uploads/{cv,excel,survey}/` altına kopyala, Onyx'te `refresh_file_library` çağır.
