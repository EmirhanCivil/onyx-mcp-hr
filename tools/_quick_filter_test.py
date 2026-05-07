import pandas as pd

df1 = pd.read_excel('/app/data/uploads/excel/dummy_basvuru_listesi.xlsx')
df2 = pd.read_excel('/app/data/uploads/excel/dummy_anket_iletilenler.xlsx')

# Ceyda Karaca'nın Excel #1'de kaç kaydı var?
ceyda1 = df1[df1['Ad Soyad'] == 'Ceyda Karaca'][['ID', 'Ad Soyad', 'Email', 'Üniversite', 'Adres', 'Onay Durum']]
print("=== Excel #1'deki tüm 'Ceyda Karaca' kayıtları ===")
print(ceyda1.to_string(index=False))
print()

# Excel #2'de Ceyda Karaca var mı, hangi email ile?
ceyda2 = df2[df2['Ad Soyad'] == 'Ceyda Karaca']
print("=== Excel #2'deki 'Ceyda Karaca' kayıtları ===")
print(ceyda2.to_string(index=False))
print()

# Sabancı + İstanbul filtresine giren ama email'i Excel #2'de OLMAYAN Ceyda
filtered = df1[(df1['Üniversite'].str.contains('Sabancı', na=False)) &
               (df1['Adres'].str.contains('İstanbul', na=False))]
ceyda_filtered = filtered[filtered['Ad Soyad'] == 'Ceyda Karaca']
print("=== Filtre kümesindeki Ceyda Karaca'lar (Sabancı + İstanbul) ===")
print(ceyda_filtered[['ID', 'Ad Soyad', 'Email', 'Üniversite', 'Adres']].to_string(index=False))
print()

# Bu Ceyda'ların email'leri Excel #2'de geçiyor mu?
target_emails = set(df2['Aday-Email'])
print("=== Bu Ceyda'ların email'i Excel #2'de var mı? ===")
for _, row in ceyda_filtered.iterrows():
    in_target = row['Email'] in target_emails
    status = '✓ İLETİLDİ (Email Excel #2\'de var)' if in_target else '✗ İLETİLMEMİŞ (Email Excel #2\'de yok)'
    print(f"  {row['ID']}  {row['Email']:<40}  {status}")
