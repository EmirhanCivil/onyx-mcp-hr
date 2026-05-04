import os

import pandas as pd

from app.core.file_registry import file_registry
from app.services.semantic_compare_service import semantic_compare_service


def test_semantic_compare_only_target_field_binary_change(tmp_path):
    file_registry.clear()

    df_a = pd.DataFrame(
        {
            "E-posta": ["ada@example.com", "bora@example.com"],
            "Form Durumu": ["iletildi", "iletildi"],
            "Ad Soyad": ["Ada", "Bora"],
        }
    )
    df_b = pd.DataFrame(
        {
            "Email": ["ADA@EXAMPLE.COM", "bora@example.com"],
            "Form Iletim": ["iletilmedi", "iletildi"],
            "Candidate Name": ["Ada", "Bora"],
        }
    )

    meta_a = file_registry.register(str(tmp_path / "a.xlsx"), df_a, tags={"category": "excel"})
    meta_b = file_registry.register(str(tmp_path / "b.xlsx"), df_b, tags={"category": "excel"})

    result = semantic_compare_service.semantic_compare_excel_field(
        file_id_a=meta_a.file_id,
        file_id_b=meta_b.file_id,
        user_question="Form durumu fark var mi?",
        export=True,
        limit=20,
    )

    assert result["status"] == "success"
    data = result["data"]
    assert data["matched_rows"] == 2
    assert data["changed_count"] == 1
    assert data["only_in_a_count"] == 0
    assert data["only_in_b_count"] == 0
    assert data["value_type"] == "binary"
    assert data.get("export_path")
    assert os.path.exists(data["export_path"])


def test_semantic_compare_numeric_price_change_with_synonyms(tmp_path):
    file_registry.clear()

    df_a = pd.DataFrame(
        {
            "SKU": ["A1", "B2", "C3"],
            "Fiyat": ["₺1.200,50", "100", "200"],
            "Stok": [10, 5, 0],
        }
    )
    df_b = pd.DataFrame(
        {
            "Product Code": ["A1", "B2", "C3"],
            "Price": ["1200.50", "100", "250"],
            "Stock": [10, 5, 0],
        }
    )

    meta_a = file_registry.register(str(tmp_path / "price_a.xlsx"), df_a, tags={"category": "excel"})
    meta_b = file_registry.register(str(tmp_path / "price_b.xlsx"), df_b, tags={"category": "excel"})

    result = semantic_compare_service.semantic_compare_excel_field(
        file_id_a=meta_a.file_id,
        file_id_b=meta_b.file_id,
        user_question="Fiyatlar degismis mi?",
        export=False,
        limit=10,
    )
    assert result["status"] == "success"
    data = result["data"]
    assert data["matched_rows"] == 3
    assert data["changed_count"] == 1
    assert data["value_type"] in {"numeric", "text"}  # may refine to numeric
