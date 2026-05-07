"""Case 2 generator: 2 ilişkili Excel üretir
- Excel #1: dummy_basvuru_listesi.xlsx — 5500 aday, 21 kolon (full başvuru kaydı)
- Excel #2: dummy_anket_iletilenler.xlsx — Excel #1'deki onaylanmış adayların ~%60'ı (anket iletilenler)
                 Sadece 3 kolon: Ad Soyad, Aday-Email, Aday-Telefon
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

EXCEL_DIR = Path("/app/data/uploads/excel")
EXCEL_DIR.mkdir(parents=True, exist_ok=True)

FIRST_NAMES = [
    "Ali", "Ayşe", "Mehmet", "Fatma", "Mustafa", "Emine", "Ahmet", "Hatice", "Hüseyin", "Zeynep",
    "İbrahim", "Elif", "Hasan", "Sevgi", "Ömer", "Selin", "Yusuf", "Merve", "Murat", "Esra",
    "Burak", "Büşra", "Can", "Cansu", "Eren", "Damla", "Furkan", "Ece", "Kemal", "Gizem",
    "Tolga", "İrem", "Onur", "Melisa", "Serkan", "Nazlı", "Volkan", "Pelin", "Berk", "Sude",
    "Arda", "Defne", "Cem", "Yağmur", "Bora", "Naz", "Erdem", "Ceyda", "Hakan", "Beyza",
]

LAST_NAMES = [
    "Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Yıldırım", "Öztürk", "Aydın", "Özdemir",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek",
    "Aksoy", "Tekin", "Polat", "Erdoğan", "Akın", "Akar", "Bulut", "Korkmaz", "Güneş", "Yavuz",
    "Aktaş", "Türk", "Acar", "Sönmez", "Aydoğan", "Soylu", "Tunç", "Erdem", "Karaca", "Avcı",
]

CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Kocaeli", "Eskişehir", "Sakarya", "Antalya", "Adana", "Konya"]

UNIVERSITIES = [
    "Boğaziçi Üniversitesi", "İTÜ", "ODTÜ", "Hacettepe Üniversitesi", "Ankara Üniversitesi",
    "Marmara Üniversitesi", "Yıldız Teknik Üniversitesi", "Sabancı Üniversitesi", "Koç Üniversitesi",
    "Bilkent Üniversitesi", "Ege Üniversitesi", "Dokuz Eylül Üniversitesi", "Sakarya Üniversitesi",
    "Kocaeli Üniversitesi", "Anadolu Üniversitesi",
]

FACULTIES = [
    "Mühendislik Fakültesi", "Fen-Edebiyat Fakültesi", "İktisadi ve İdari Bilimler Fakültesi",
    "Hukuk Fakültesi", "Tıp Fakültesi", "İletişim Fakültesi", "Mimarlık Fakültesi",
    "Eğitim Fakültesi", "İşletme Fakültesi", "Bilgisayar ve Bilişim Bilimleri Fakültesi",
]

EDUCATION_LEVEL = ["Lisans", "Yüksek Lisans", "Lise", "Doktora"]
EDU_WEIGHTS = [70, 20, 7, 3]
GENDERS = ["Erkek", "Kadın"]
MILITARY_OPTIONS = ["Tecil", "Muaf", "Tamamlandı", "Belirtilmedi"]

DISTRICTS = {
    "İstanbul": ["Kadıköy", "Beşiktaş", "Şişli", "Üsküdar", "Maltepe", "Bakırköy"],
    "Ankara": ["Çankaya", "Yenimahalle", "Keçiören", "Mamak", "Etimesgut"],
    "İzmir": ["Bornova", "Konak", "Karşıyaka", "Buca", "Bayraklı"],
    "Bursa": ["Nilüfer", "Osmangazi", "Yıldırım"],
    "Kocaeli": ["İzmit", "Gebze", "Derince"],
    "Eskişehir": ["Tepebaşı", "Odunpazarı"],
    "Sakarya": ["Adapazarı", "Serdivan"],
    "Antalya": ["Muratpaşa", "Konyaaltı", "Kepez"],
    "Adana": ["Seyhan", "Yüreğir"],
    "Konya": ["Selçuklu", "Meram"],
}

STREETS = [
    "Atatürk Mh. Cumhuriyet Cd.", "İnönü Mh. Bağlar Sk.", "Yenişehir Mh. Çiçek Cd.",
    "Barbaros Mh. Lale Sk.", "Fatih Mh. Gül Cd.", "Kazım Karabekir Mh. Defne Sk.",
    "Mimar Sinan Mh. Çınar Cd.", "Hürriyet Mh. Akasya Sk.", "Orman Mh. Erguvan Cd.",
]


def random_date(start_year: int, end_year: int) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def gen_address(city: str) -> str:
    district = random.choice(DISTRICTS.get(city, ["Merkez"]))
    street = random.choice(STREETS)
    return f"{street} No:{random.randint(1, 280)} D:{random.randint(1, 25)}, {district} / {city}"


# Excel #1
rows = []
for i in range(1, 5501):
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    full = f"{fn} {ln}"
    suffix = random.randint(1, 9999)
    email = f"{fn.lower().replace('ı','i').replace('ö','o').replace('ü','u').replace('ş','s').replace('ç','c').replace('ğ','g')}." \
            f"{ln.lower().replace('ı','i').replace('ö','o').replace('ü','u').replace('ş','s').replace('ç','c').replace('ğ','g')}{suffix}@example.com"
    res_city = random.choice(CITIES)
    birth_city = random.choice(CITIES)
    uni = random.choice(UNIVERSITIES)
    fac = random.choice(FACULTIES)
    edu = random.choices(EDUCATION_LEVEL, weights=EDU_WEIGHTS)[0]
    gender = random.choice(GENDERS)

    cep = f"05{random.randint(30, 59)}{random.randint(1000000, 9999999):07d}"
    tel = f"0{random.choice([212, 216, 312, 232, 224])}{random.randint(1000000, 9999999):07d}"

    onay = random.random() < 0.62
    aciklama_onay = random.random() < 0.74

    staj_gun = random.choice([20, 30, 40, 45, 60, 90])
    zorunlu_staj = random.randint(1, 3)
    askerlik = random.choice(MILITARY_OPTIONS) if gender == "Erkek" else "—"

    bd = random_date(1995, 2005)
    create = random_date(2024, 2026)

    rows.append({
        "ID": f"AD-{i:05d}",
        "Ad Soyad": full,
        "Fotograf": f"/photos/AD-{i:05d}.jpg",
        "Adres": gen_address(res_city),
        "Doğum Tarihi": bd.strftime("%d/%m/%Y"),
        "Doğum Yeri": birth_city,
        "Onay Durum": onay,
        "Oluşturma Tarihi": create.strftime("%d/%m/%Y"),
        "CV": f"/data/cvs/AD-{i:05d}.pdf",
        "Açıklama Onay": aciklama_onay,
        "Email": email,
        "Cinsiyet": gender,
        "Fakülte": fac,
        "Staj Zamanı": staj_gun,
        "Zorunlu Staj Durumu": zorunlu_staj,
        "Askerlik Tecil Durumu": askerlik,
        "Cep Telefonu": cep,
        "Telefon": tel,
        "Uyruk": "Türkiye",
        "Eğitim Durumu": edu,
        "Üniversite": uni,
    })

df = pd.DataFrame(rows)
out1 = EXCEL_DIR / "dummy_basvuru_listesi.xlsx"
df.to_excel(out1, index=False)
print(f"Excel #1: {out1}  ({len(df)} satır, {len(df.columns)} kolon)")

# Excel #2 — Onay Durum=True olanların ~%60'ı (anket iletilmiş kabul)
approved = df[df["Onay Durum"] == True].copy()
delivered = approved.sample(frac=0.60, random_state=42)
delivered_subset = delivered[["Ad Soyad", "Email", "Cep Telefonu"]].rename(
    columns={"Email": "Aday-Email", "Cep Telefonu": "Aday-Telefon"}
).reset_index(drop=True)

out2 = EXCEL_DIR / "dummy_anket_iletilenler.xlsx"
delivered_subset.to_excel(out2, index=False)
print(f"Excel #2: {out2}  ({len(delivered_subset)} satır — onaylı havuzun %60'ı)")

print()
print("=== Veri haritası ===")
print(f"Toplam aday          : {len(df)}")
print(f"Onay Durum=True      : {len(approved)}")
print(f"Anket iletilenler    : {len(delivered_subset)}")
print(f"Onaylı ama iletilmemiş: {len(approved) - len(delivered_subset)}")
print()
print("Excel #1 kolonlar:", ', '.join(df.columns))
