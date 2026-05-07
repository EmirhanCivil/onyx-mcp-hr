"""72 tool sanity test — direkt MCP üzerinden, LLM bypass.

Her tool'a minimum çalışır parametre ile call atar. Amaç: implementation'ın
çağrı + response cycle'ında hata atmadığını doğrulamak (success vs error).
"""

import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from urllib.error import HTTPError, URLError

URL = "http://localhost:8005/mcp"
TIMEOUT = 120


_RAW_PRINT = print  # bu satır builtin print'i koru — p() içinde recursion olmasın


def p(*args, **kwargs):
    """ASCII-safe print — Windows cp1252 console TR karakterlerle çakışıyor."""
    text = " ".join(str(a) for a in args)
    _RAW_PRINT(text.encode("ascii", "replace").decode("ascii"), **kwargs)


def _post(body: dict, sid: str | None = None) -> tuple[dict | str, str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            new_sid = resp.headers.get("mcp-session-id") or sid
        m = re.search(r"data:\s*(\{.*\})", raw, flags=re.S)
        payload = json.loads(m.group(1)) if m else {"raw": raw[:300]}
        return payload, new_sid
    except (HTTPError, URLError) as e:
        return {"transport_error": str(e)}, sid


def initialize() -> str:
    payload, sid = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "tester", "version": "0"}},
    })
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid=sid)
    return sid


def call(sid: str, name: str, args: dict) -> dict:
    payload, _ = _post({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }, sid=sid)
    return payload


def get_files(sid: str) -> dict[str, str]:
    """Returns {logical_name: file_id}. load_spreadsheet → file_path (zorunlu)."""
    out = {}
    paths = [
        ("basvuru",          "/app/data/uploads/excel/dummy_basvuru_listesi.xlsx"),
        ("anket_iletilenler","/app/data/uploads/excel/dummy_anket_iletilenler.xlsx"),
        ("q1",               "/app/data/uploads/survey/dummy_ik_anket_2026_q1.xlsx"),
        ("q2",               "/app/data/uploads/survey/dummy_ik_anket_2026_q2.xlsx"),
    ]
    for key, path in paths:
        resp = call(sid, "load_spreadsheet", {"file_path": path})
        try:
            text = resp["result"]["content"][0]["text"]
            data = json.loads(text)
            payload = data.get("data") if isinstance(data.get("data"), dict) else data
            fid = (payload.get("file_id")
                   or (payload.get("file") or {}).get("file_id")
                   or (payload.get("file") or {}).get("id"))
            if fid:
                out[key] = fid
            else:
                p(f"  [files] {key}: load OK but no file_id in payload keys={list(payload.keys())}")
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
            p(f"  [files] {key}: parse err {e}")
    return out


def summarize(resp: dict) -> tuple[str, str]:
    """Returns (status, short_msg). status ∈ {OK, PARAM, FAIL, ERR}.
    PARAM = schema/argument hatası (pydantic validation), tool-implementation problemi değil."""
    if "transport_error" in resp:
        return "ERR", resp["transport_error"][:80]
    if "error" in resp and resp["error"]:
        return "ERR", str(resp["error"])[:80]
    try:
        text = resp["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        return "ERR", f"shape: {e} | {str(resp)[:80]}"
    # Pydantic / arg validation hatası — JSON değil, plain text
    lo = text.lower()
    if "validation error" in lo or "missing_argument" in lo or "unexpected_keyword_argument" in lo:
        first = text.splitlines()[0][:100] if text else ""
        return "PARAM", first
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # JSON değil ama validation hatası da değil → plain text response
        return "OK", f"text | {text[:80].replace(chr(10),' ')}"
    success = data.get("success") or data.get("status") == "success"
    msg = data.get("message") or ""
    if success:
        extra = []
        d = data.get("data") if isinstance(data.get("data"), dict) else {}
        if d.get("chart") or data.get("charts"):
            extra.append("chart")
        if data.get("generated_outputs") or d.get("generated_outputs"):
            extra.append("export")
        for k in ("matched_count", "missing_count", "row_count", "duplicate_count"):
            if d.get(k) is not None:
                extra.append(f"{k}={d[k]}")
        tag = ",".join(extra) or "ok"
        return "OK", f"{tag} | {msg[:60]}"
    return "FAIL", str(data.get("error") or data.get("message") or "no success flag")[:100]


SCORE_COLS = "Memnuniyet,Yönetici Desteği,İletişim,İş Yükü Dengesi,Kariyer Gelişimi,Takdir,Araç ve Süreçler"


def build_test_plan(files: dict) -> list[tuple[str, dict]]:
    basv = files.get("basvuru", "")
    iletilen = files.get("anket_iletilenler", "")
    q1 = files.get("q1", "")
    q2 = files.get("q2", "")
    structured_itu = json.dumps({
        "logic": "AND",
        "conditions": [{"field": "Üniversite", "operator": "contains", "value": "İTÜ"}],
    }, ensure_ascii=False)
    return [
        # 1. Sistem & Kütüphane
        ("get_system_status", {}),
        ("refresh_file_library", {}),
        ("list_file_library", {}),
        # 2. Üst seviye akıllı yönlendirme
        ("answer_cv_question", {"question": "CV havuzunda kaç aday var?"}),
        ("answer_excel_question", {"question": "dummy_basvuru_listesi.xlsx içinde Onay Durum=true olan kaç kişi var?"}),
        ("answer_survey_question", {"question": "Q1 anketinde Memnuniyet ortalaması nedir?"}),
        # 3. CV
        ("scan_cvs", {}),
        ("list_cvs", {}),
        ("audit_cv_library", {}),
        ("summarize_cv_library", {}),
        ("get_cv_detail", {"query": "tolga"}),
        ("search_cvs", {"query": "akademik"}),
        ("analyze_cvs", {"query": "Python"}),
        # 4. Excel — dosya tanıma
        ("scan_uploads", {}),
        ("list_loaded_spreadsheets", {}),
        ("list_available_files", {"category": "excel"}),
        ("find_spreadsheet", {"query": "basvuru"}),
        ("load_spreadsheet", {"file_path": "/app/data/uploads/excel/dummy_basvuru_listesi.xlsx"}),
        ("profile_spreadsheet", {"file_id": basv, "preview_rows": 10}),
        ("inspect_workbook_sheets", {"file_query": "basvuru"}),
        ("analyze_workbook_structure", {"file_id": basv}),
        # 5. Excel kalite & sorgulama
        ("audit_spreadsheet_quality", {"file_id": basv}),
        ("audit_email_quality", {"file_id": basv, "email_column": "Email", "export": True}),
        ("summarize_spreadsheet_column", {"file_id": basv, "column": "Onay Durum"}),
        ("filter_spreadsheet_rows", {"file_id": basv, "column": "Üniversite", "value": "Boğaziçi"}),
        ("query_spreadsheet_rows", {"file_id": basv, "natural_query": "Onay Durum=true olanlar"}),
        ("auto_query_spreadsheet_rows", {"query": "İTÜ'lü adaylar", "file_query": "basvuru",
                                         "structured_query_json": structured_itu, "export": False}),
        ("auto_filter_excel_rows", {"query": "İTÜ'lü adaylar", "file_query": "basvuru"}),
        ("find_duplicate_rows", {"file_id": basv, "key_columns": "Email"}),
        ("deduplicate_spreadsheet", {"file_id": basv, "key_columns": "Email", "export": True}),
        ("normalize_hr_columns", {"file_id": basv}),
        ("calculate_hr_data_quality_score", {"file_id": basv}),
        # 6. Excel — karşılaştırma & eksik bulma
        ("compare_spreadsheet_columns", {"file_id_a": q1, "file_id_b": q2}),
        ("compare_spreadsheet_rows", {"file_id_a": q1, "file_id_b": q2}),
        ("compare_spreadsheet_by_key", {"file_id_a": q1, "file_id_b": q2, "key_columns": "Cevap ID"}),
        ("auto_compare_spreadsheets", {"file_query_a": "q1", "file_query_b": "q2"}),
        ("auto_compare_excel_changes", {"file_query_a": "q1", "file_query_b": "q2"}),
        ("semantic_compare_excel_field", {"file_id_a": q1, "file_id_b": q2,
                                          "user_question": "Memnuniyet alanı nasıl değişti?"}),
        ("find_missing_in_target_file", {
            "source_file_id": basv, "target_file_id": iletilen,
            "key_columns": "Email",
            "source_structured_query": structured_itu,
            "export": True,
        }),
        # 7. Anket
        ("auto_analyze_survey", {"file_query": "q1"}),
        ("analyze_survey_overview", {"file_id": q1}),
        ("analyze_survey_numeric", {"file_id": q1, "columns": "Memnuniyet,İletişim,Takdir"}),
        ("analyze_survey_by_group", {"file_id": q1, "group_col": "Departman", "score_columns": SCORE_COLS}),
        ("analyze_survey_comments", {"file_id": q1, "comment_columns": "Açık Uçlu Yorum"}),
        ("create_survey_executive_summary", {"file_id": q1}),
        ("compare_survey_periods", {"file_id_a": q1, "file_id_b": q2, "group_col": "Departman", "score_columns": SCORE_COLS}),
        ("analyze_survey_root_causes", {"file_id": q2}),
        # 8. Grafik
        ("create_group_bar_chart", {"file_id": q1, "group_col": "Departman", "value_col": "Memnuniyet"}),
        ("create_score_heatmap", {"file_id": q1, "group_col": "Departman", "score_columns": SCORE_COLS}),
        ("create_category_distribution_chart", {"file_id": basv, "category_col": "Üniversite", "top_n": 15}),
        ("create_score_radar", {"file_id": q2, "group_col": "Departman", "score_columns": SCORE_COLS, "top_n": 6}),
        ("create_period_delta_chart", {"file_id_a": q1, "file_id_b": q2, "group_col": "Departman", "score_columns": SCORE_COLS}),
        ("auto_create_survey_visuals", {"file_id": q2}),
        # 9. Rapor
        ("create_survey_report", {"file_id": q1}),
        ("create_candidate_pool_report", {"file_id": basv}),
        ("create_shortlist_report", {"role": "Yazılım Mühendisi", "required_skills": "Python,SQL"}),
        ("create_data_quality_report", {"file_id": basv}),
        ("create_department_risk_report", {"file_id": q2, "group_col": "Departman", "score_columns": SCORE_COLS}),
        # 10. HR iş akışı
        ("analyze_candidate_pool", {"file_id": basv}),
        ("analyze_recruiting_pipeline", {"file_query": "basvuru"}),
        ("match_excel_candidates_to_cvs", {"file_id": basv}),
        ("create_candidate_shortlist", {"role": "Veri Analisti", "required_skills": "Python,SQL,Excel", "preferred_skills": "Power BI,pandas"}),
        ("create_survey_action_plan", {"file_query": "q2", "group_col": "Departman", "score_columns": SCORE_COLS}),
        # 11. HR intelligence
        ("auto_select_hr_file", {"query": "aday formu"}),
        ("explain_hr_query_plan", {"file_id": basv, "natural_query": "İstanbul'daki Boğaziçili 2002 doğumlu adaylar"}),
        ("generate_hr_overview_dashboard", {"file_id": basv}),
        ("analyze_candidate_stage_transitions", {"file_id_a": q1, "file_id_b": q2}),
        ("analyze_position_funnel", {"file_id": basv}),
        ("compare_candidate_segments", {"file_id": basv, "segment_field": "Üniversite"}),
        ("suggest_hr_questions", {}),
        ("clear_spreadsheet_registry", {}),
        # 12. Doküman
        ("create_document", {"format": "xlsx", "filename": "carpim_3x3", "title": "3x3 Carpim",
                             "content": {"sheets": [{"name": "Carpim", "columns": ["x", "1", "2", "3"],
                                                       "rows": [[1, 1, 2, 3], [2, 2, 4, 6], [3, 3, 6, 9]]}]}}),
    ]


def main() -> int:
    p(f"[init] connecting {URL}")
    sid = initialize()
    p(f"[init] sid={sid[:8] if sid else '?'}")
    p(f"[files] looking up file_ids...")
    files = get_files(sid)
    p(f"[files] resolved: {list(files.keys())}")
    if not all(k in files for k in ("basvuru", "anket_iletilenler", "q1", "q2")):
        p(f"[files] WARN: missing some — partial test. Got: {files}")

    plan = build_test_plan(files)
    p(f"\n[run] {len(plan)} tools queued\n")

    results = []
    counts = defaultdict(int)
    t0 = time.time()
    for idx, (name, args) in enumerate(plan, 1):
        t1 = time.time()
        resp = call(sid, name, args)
        dt = time.time() - t1
        status, msg = summarize(resp)
        counts[status] += 1
        marker = {"OK": "+", "FAIL": "x", "ERR": "!", "PARAM": "?"}[status]
        p(f"{idx:2d}. {marker} [{status:4s}] {name:40s} {dt:5.2f}s  {msg}")
        results.append({"idx": idx, "name": name, "status": status, "dt": round(dt, 2), "msg": msg})

    elapsed = time.time() - t0
    p(f"\n[summary] {dict(counts)} | total {elapsed:.1f}s")

    out_path = "/tmp/test_72_results.json" if sys.platform != "win32" else "test_72_results.json"
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"summary": dict(counts), "elapsed_sec": round(elapsed, 1), "results": results},
                      fh, ensure_ascii=False, indent=2)
        p(f"[saved] {out_path}")
    except OSError as e:
        p(f"[save err] {e}")

    return 0 if counts.get("ERR", 0) == 0 and counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
