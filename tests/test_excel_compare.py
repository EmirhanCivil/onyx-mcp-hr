import pandas as pd

from app.analyzers.diff_analyzer import compare_by_key, compare_columns, row_set_difference
from app.core.file_registry import file_registry
from app.services.excel_compare_service import excel_compare_service


def test_compare_columns_reports_schema_differences():
    a = pd.DataFrame({"id": [1], "name": ["A"], "score": [4]})
    b = pd.DataFrame({"id": [1], "name": ["A"], "status": ["sent"]})

    result = compare_columns(a, b)

    assert result["columns_only_in_a"] == ["score"]
    assert result["columns_only_in_b"] == ["status"]
    assert result["common_columns"] == ["id", "name"]


def test_row_set_difference_uses_common_columns():
    a = pd.DataFrame({"id": [1, 2], "name": ["A", "B"]})
    b = pd.DataFrame({"id": [1, 3], "name": ["A", "C"]})

    result = row_set_difference(a, b)

    assert result["rows_only_in_a_count"] == 1
    assert result["rows_only_in_b_count"] == 1


def test_compare_by_key_detects_changed_rows():
    a = pd.DataFrame({"id": [1, 2], "status": ["İletildi", "Bekliyor"]})
    b = pd.DataFrame({"id": [1, 2], "status": ["İletildi", "İletildi"]})

    result = compare_by_key(a, b, ["id"], ["status"])

    assert result["matched_keys"] == 2
    assert result["changed_row_count"] == 1
    assert result["changed_rows_preview"][0]["changed_columns"]["status"]["a"] == "Bekliyor"


def test_auto_compare_handles_renamed_hr_columns_row_order_and_new_rows(tmp_path):
    file_registry.clear()
    old = pd.DataFrame({
        "Aday No": ["C001", "C002"],
        "Ad Soyad": ["Ada Yilmaz", "Bora Demir"],
        "Departman": ["Data", "IT"],
        "Aday Durumu": ["Bekliyor", "Olumlu"],
        "Puan": [70, 90],
    })
    new = pd.DataFrame({
        "Candidate ID": ["C002", "C003", "C001"],
        "Full Name": ["Bora Demir", "Cem Kaya", "Ada Yilmaz"],
        "Department": ["IT", "Sales", "Data"],
        "Status": ["Olumlu", "Yeni", "Gorusme"],
        "Score": [95, 60, 70],
    })
    meta_old = file_registry.register(str(tmp_path / "old.xlsx"), old, tags={"category": "candidate"})
    meta_new = file_registry.register(str(tmp_path / "new.xlsx"), new, tags={"category": "candidate"})

    result = excel_compare_service.compare_auto(meta_old.file_id, meta_new.file_id, key_query="aday no candidate id")

    mapped_pairs = {(item["a"], item["b"]) for item in result["mapped_columns"]}
    changed_columns = [row["changed_columns"] for row in result["changed_rows_preview"]]

    assert result["comparison_mode"] == "keyed"
    assert result["inferred_key_columns"] == ["Aday No"]
    assert ("Aday Durumu", "Status") in mapped_pairs
    assert ("Puan", "Score") in mapped_pairs
    assert result["matched_keys"] == 2
    assert result["only_in_b_count"] == 1
    assert result["changed_row_count"] == 2
    assert any("Aday Durumu" in row for row in changed_columns)
    assert any("Puan" in row for row in changed_columns)


def test_auto_compare_infers_name_key_when_ids_are_missing(tmp_path):
    file_registry.clear()
    old = pd.DataFrame({
        "Ad Soyad": ["Ada Yilmaz", "Bora Demir"],
        "Birim": ["Data", "IT"],
        "Durum": ["Bekliyor", "Olumlu"],
    })
    new = pd.DataFrame({
        "Full Name": ["Bora Demir", "Ada Yilmaz"],
        "Department": ["IT", "Data"],
        "Application Status": ["Olumlu", "Gorusme"],
    })
    meta_old = file_registry.register(str(tmp_path / "old_names.xlsx"), old, tags={"category": "candidate"})
    meta_new = file_registry.register(str(tmp_path / "new_names.xlsx"), new, tags={"category": "candidate"})

    result = excel_compare_service.compare_auto(meta_old.file_id, meta_new.file_id)

    assert result["comparison_mode"] == "keyed"
    assert result["inferred_key_columns"] == ["Ad Soyad"]
    assert result["matched_keys"] == 2
    assert result["changed_row_count"] == 1
    assert result["changed_rows_preview"][0]["changed_columns"]["Durum"]["b"] == "Gorusme"


def test_compare_by_key_normalizes_value_format_noise():
    a = pd.DataFrame({"Email": ["ADA@EXAMPLE.COM"], "Score": [85]})
    b = pd.DataFrame({"Email": ["ada@example.com"], "Score": ["85.0"]})

    result = compare_by_key(a, b, ["Email"], ["Score"])

    assert result["matched_keys"] == 1
    assert result["changed_row_count"] == 0


def test_auto_compare_handles_vehicle_inventory_without_hr_columns(tmp_path):
    file_registry.clear()
    old = pd.DataFrame({
        "Plaka": ["34 ABC 123", "06 XYZ 987"],
        "Marka": ["Toyota", "Ford"],
        "Model": ["Corolla", "Focus"],
        "Durum": ["Aktif", "Bakimda"],
        "KM": [1000, 24000],
    })
    new = pd.DataFrame({
        "License Plate": ["06 xyz 987", "35 NEW 001", "34 abc 123"],
        "Brand": ["Ford", "Renault", "Toyota"],
        "Vehicle Model": ["Focus", "Clio", "Corolla"],
        "Condition": ["Aktif", "Aktif", "Aktif"],
        "Mileage": ["25000", "120", "1000.0"],
    })
    meta_old = file_registry.register(str(tmp_path / "vehicles_old.xlsx"), old, tags={"category": "excel"})
    meta_new = file_registry.register(str(tmp_path / "vehicles_new.xlsx"), new, tags={"category": "excel"})

    result = excel_compare_service.compare_auto(meta_old.file_id, meta_new.file_id, key_query="plaka")

    mapped_pairs = {(item["a"], item["b"]) for item in result["mapped_columns"]}

    assert result["comparison_mode"] == "keyed"
    assert result["inferred_key_columns"] == ["Plaka"]
    assert ("Plaka", "License Plate") in mapped_pairs
    assert ("KM", "Mileage") in mapped_pairs
    assert result["matched_keys"] == 2
    assert result["only_in_b_count"] == 1
    assert result["changed_row_count"] == 1
    assert "KM" in result["changed_rows_preview"][0]["changed_columns"]


def test_auto_compare_handles_product_stock_with_generic_ids(tmp_path):
    file_registry.clear()
    old = pd.DataFrame({
        "Ürün Kodu": ["SKU-1", "SKU-2"],
        "Kategori": ["Laptop", "Monitor"],
        "Stok": [10, 5],
        "Birim Fiyat": [1000, 500],
    })
    new = pd.DataFrame({
        "SKU": ["SKU-2", "SKU-1", "SKU-3"],
        "Category": ["Monitor", "Laptop", "Mouse"],
        "Inventory": [4, "10.0", 20],
        "Unit Price": [500, "1000.0", 25],
    })
    meta_old = file_registry.register(str(tmp_path / "stock_old.xlsx"), old, tags={"category": "excel"})
    meta_new = file_registry.register(str(tmp_path / "stock_new.xlsx"), new, tags={"category": "excel"})

    result = excel_compare_service.compare_auto(meta_old.file_id, meta_new.file_id, key_query="urun kodu sku")

    assert result["comparison_mode"] == "keyed"
    assert result["inferred_key_columns"] == ["Ürün Kodu"]
    assert result["matched_keys"] == 2
    assert result["only_in_b_count"] == 1
    assert result["changed_row_count"] == 1
    assert result["changed_rows_preview"][0]["changed_columns"]["Stok"]["a"] == 5


def test_auto_compare_uses_fingerprint_when_no_reliable_key_exists(tmp_path):
    file_registry.clear()
    old = pd.DataFrame({
        "Renk": ["Kirmizi", "Mavi"],
        "Adet": [10, 20],
    })
    new = pd.DataFrame({
        "Colour": ["Mavi", "Kirmizi"],
        "Quantity": ["20.0", "10"],
    })
    meta_old = file_registry.register(str(tmp_path / "simple_old.xlsx"), old, tags={"category": "excel"})
    meta_new = file_registry.register(str(tmp_path / "simple_new.xlsx"), new, tags={"category": "excel"})

    result = excel_compare_service.compare_auto(meta_old.file_id, meta_new.file_id)

    assert result["comparison_mode"] == "row_set"
    assert result["key_quality"]["status"] == "fallback"
    assert result["fallback_strategy"] == "normalized_row_fingerprint"
    assert result["rows_only_in_a_count"] == 0
    assert result["rows_only_in_b_count"] == 0
