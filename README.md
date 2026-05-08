# Onyx HR MCP

72 tool'lu Onyx MCP server: CV, Excel/CSV ve anket analizi. Tek Docker image — clone et, kendi data klasörünü bağla, Onyx'e bind et.

## Kurulum

```bash
git clone https://github.com/EmirhanCivil/onyx-mcp-hr.git
cd onyx-mcp-hr
cp .env.example .env
# .env içinde HR_DATA_DIR satırını kendi CV/Excel/anket klasörünün yoluna ayarla
docker compose up -d
```

Tek container ayağa kalkar (`onyx-mcp-hr`):

| Port | İş |
|---|---|
| **8005** | MCP server (Onyx buraya bağlanır) |
| **8007** | Üretilen chart/rapor dosyalarını servis eder |

Image: [`emirhancivil/onyx-mcp-hr:latest`](https://hub.docker.com/r/emirhancivil/onyx-mcp-hr) — `docker compose pull` ile güncellenir.

## Data klasörü yapısı

`HR_DATA_DIR` olarak verdiğin klasör şu yapıda olmalı:

```
<senin-data-klasörün>/
├── uploads/
│   ├── cv/        ← CV dosyaları (.pdf, .docx, .txt)
│   ├── excel/     ← Aday Excel'leri (.xlsx, .csv, .ods, …)
│   └── survey/    ← Anket Excel'leri
├── outputs/       ← Otomatik oluşur (chart, rapor, export)
└── processed/     ← Otomatik oluşur
```

Container açılışında `uploads/` altı otomatik taranır. Çalışırken yeni dosya eklenince Onyx'te `refresh_file_library` çağır.

## Onyx'e bağlama

1. **Admin → MCP Servers → Add**
   - URL: `http://host.docker.internal:8005/mcp`
   - Transport: **STREAMABLE_HTTP**
2. **Assistants → New Assistant**
   - Instructions kutusuna [`ONYX_UNIFIED_PROMPT.md`](ONYX_UNIFIED_PROMPT.md) içeriğini **olduğu gibi yapıştır** — uyarlama gerekmez. Agent ilk sohbette `list_file_library` + `profile_spreadsheet` ile dosyalarını ve kolonlarını otomatik öğrenir.
   - 72 tool'u etkinleştir.

## Sürüm notu

`0.2.0` — tek container (nginx + uvicorn supervisord ile), önceki iki-container yapı `0.1.0`'da.
