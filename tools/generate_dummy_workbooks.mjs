import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "data", "uploads");
await fs.mkdir(outputDir, { recursive: true });

const schools = [
  "Boğaziçi Üniversitesi", "İTÜ", "ODTÜ", "Yıldız Teknik Üniversitesi", "Marmara Üniversitesi",
  "Hacettepe Üniversitesi", "Ege Üniversitesi", "Sakarya Üniversitesi", "Kocaeli Üniversitesi", "Anadolu Üniversitesi",
];
const departments = [
  "Bilgisayar Mühendisliği", "Endüstri Mühendisliği", "Elektrik Elektronik Mühendisliği",
  "Yazılım Mühendisliği", "İşletme", "İstatistik", "Matematik", "Psikoloji", "İnsan Kaynakları Yönetimi",
];
const cities = ["İstanbul", "Ankara", "İzmir", "Bursa", "Kocaeli", "Eskişehir", "Sakarya", "Antalya"];
const statuses = ["İletildi", "İletilmedi", "Beklemede", "Hatalı Email"];
const positions = ["Stajyer", "Uzun Dönem Stajyer", "Yeni Mezun", "Analist Adayı", "Mühendis Adayı"];
const yesNo = ["Evet", "Hayır"];

function pick(arr, i, salt = 0) {
  return arr[(i * 17 + salt * 31) % arr.length];
}

function score(i, salt) {
  return Math.max(1, Math.min(5, 1 + ((i * 7 + salt * 13) % 5)));
}

async function saveWorkbook(workbook, fileName) {
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  const out = path.join(outputDir, fileName);
  await xlsx.save(out);
  return out;
}

async function createStudentWorkbook() {
  const wb = Workbook.create();
  const sheet = wb.worksheets.add("Aday_Formlari");
  const headers = [
    "Aday ID", "Ad Soyad", "Email", "Telefon", "Okul", "Bölüm", "Şehir", "Doğum Yılı",
    "Başvurulan Pozisyon", "Form Durumu", "Form İletim Tarihi", "CV Onayı", "Zorunlu Staj",
    "Staj Dönemi", "Askerlik Durumu", "Uyruk", "Not Ortalaması", "İngilizce Seviyesi",
    "Kaynak", "Kayıt Tarihi",
  ];
  const rows = [headers];
  for (let i = 1; i <= 5500; i++) {
    const duplicateOffset = i % 137 === 0 ? -1 : 0;
    const idNum = i + duplicateOffset;
    const school = pick(schools, i);
    const department = pick(departments, i, 2);
    const city = pick(cities, i, 4);
    const status = pick(statuses, i, 6);
    rows.push([
      `STD-${String(idNum).padStart(5, "0")}`,
      `Aday ${String(idNum).padStart(5, "0")}`,
      `aday${idNum}@example.com`,
      `05${String(300000000 + idNum).slice(0, 9)}`,
      school,
      department,
      city,
      1998 + (i % 8),
      pick(positions, i, 8),
      status,
      status === "İletildi" ? new Date(2026, (i % 4), 1 + (i % 25)) : null,
      pick(yesNo, i, 1),
      pick(yesNo, i, 3),
      `${pick(["Haziran", "Temmuz", "Ağustos", "Eylül"], i)} 2026`,
      pick(["Tamamlandı", "Tecilli", "Muaf", "Belirtilmedi"], i, 5),
      pick(["Türkiye", "Azerbaycan", "KKTC", "Diğer"], i, 7),
      Number((2.2 + (i % 18) / 10).toFixed(2)),
      pick(["A1", "A2", "B1", "B2", "C1"], i, 9),
      pick(["Kariyer Portalı", "LinkedIn", "Üniversite Etkinliği", "Referans", "Web Form"], i, 10),
      new Date(2026, (i % 3), 1 + (i % 27)),
    ]);
  }
  sheet.getRangeByIndexes(0, 0, rows.length, headers.length).values = rows;
  sheet.getRange("A1:T1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF" } };
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:T${rows.length}`, true, "AdayFormlari");
  sheet.getRange("K2:K5501").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("T2:T5501").setNumberFormat("yyyy-mm-dd");
  return saveWorkbook(wb, "dummy_ogrenci_formlari_5500.xlsx");
}

function surveyRows(periodLabel, shift = 0) {
  const departments = ["İK", "Üretim", "Satış", "Finans", "IT", "Ar-Ge", "Lojistik", "Pazarlama", "Kalite", "Operasyon"];
  const locations = ["İstanbul", "Ankara", "İzmir", "Kocaeli"];
  const comments = [
    "Yönetim iletişimi daha düzenli olmalı.",
    "İş yükü dönem dönem çok yoğunlaşıyor.",
    "Kariyer gelişimi ve eğitim imkanları artırılmalı.",
    "Ekip içi destek ve çalışma ortamı güçlü.",
    "Süreç ve araçlar daha sade hale getirilmeli.",
    "Takdir mekanizması motivasyonu artırır.",
  ];
  const headers = [
    "Cevap ID", "Dönem", "Departman", "Lokasyon", "Unvan Seviyesi", "Memnuniyet",
    "Yönetici Desteği", "İletişim", "İş Yükü Dengesi", "Kariyer Gelişimi",
    "Takdir", "Araç ve Süreçler", "Açık Uçlu Yorum",
  ];
  const rows = [headers];
  for (let i = 1; i <= 1200; i++) {
    const dept = pick(departments, i, shift);
    const deptPenalty = dept === "Üretim" || dept === "Operasyon" ? -1 : 0;
    const improvement = periodLabel.includes("Q2") && (dept === "IT" || dept === "Ar-Ge") ? 1 : 0;
    rows.push([
      `${periodLabel}-${String(i).padStart(4, "0")}`,
      periodLabel,
      dept,
      pick(locations, i, 2),
      pick(["Uzman", "Kıdemli Uzman", "Yönetici", "Mavi Yaka", "Stajyer"], i, 4),
      score(i, 1 + shift) + deptPenalty + improvement,
      score(i, 2 + shift) + deptPenalty,
      score(i, 3 + shift),
      score(i, 4 + shift) + deptPenalty,
      score(i, 5 + shift) + improvement,
      score(i, 6 + shift),
      score(i, 7 + shift),
      pick(comments, i, shift),
    ].map((value, idx) => idx >= 5 && idx <= 11 ? Math.max(1, Math.min(5, value)) : value));
  }
  return rows;
}

async function createSurveyWorkbook(fileName, periodLabel, shift) {
  const wb = Workbook.create();
  const sheet = wb.worksheets.add("Anket");
  const rows = surveyRows(periodLabel, shift);
  sheet.getRangeByIndexes(0, 0, rows.length, rows[0].length).values = rows;
  sheet.getRange("A1:M1").format = { fill: "#1D4ED8", font: { bold: true, color: "#FFFFFF" } };
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:M${rows.length}`, true, "Anket");
  return saveWorkbook(wb, fileName);
}

const outputs = [];
outputs.push(await createStudentWorkbook());
outputs.push(await createSurveyWorkbook("dummy_ik_anket_2026_q1.xlsx", "2026-Q1", 0));
outputs.push(await createSurveyWorkbook("dummy_ik_anket_2026_q2.xlsx", "2026-Q2", 2));
console.log(outputs.join("\n"));
