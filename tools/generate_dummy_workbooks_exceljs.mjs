import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ExcelJS from "exceljs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const excelDir = path.join(root, "data", "uploads", "excel");
const surveyDir = path.join(root, "data", "uploads", "survey");
await fs.mkdir(excelDir, { recursive: true });
await fs.mkdir(surveyDir, { recursive: true });

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

// Mulberry32 PRNG — reproducible (seed=42) but independent draws across fields,
// so school × department × city × year are uncorrelated.
function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const _rng = mulberry32(42);
function pick(arr, _i, _salt = 0) {
  return arr[Math.floor(_rng() * arr.length)];
}
function score(_i, _salt) {
  return 1 + Math.floor(_rng() * 5);
}
function randInt(a, b) {
  return a + Math.floor(_rng() * (b - a + 1));
}

function styleHeader(row, fillColor) {
  row.eachCell((cell) => {
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: fillColor } };
    cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
    cell.alignment = { vertical: "middle", horizontal: "left" };
  });
}

async function createStudentWorkbook() {
  const wb = new ExcelJS.Workbook();
  const sheet = wb.addWorksheet("Aday_Formlari", { views: [{ state: "frozen", ySplit: 1 }] });
  const headers = [
    "Aday ID", "Ad Soyad", "Email", "Telefon", "Okul", "Bölüm", "Şehir", "Doğum Yılı",
    "Başvurulan Pozisyon", "Form Durumu", "Form İletim Tarihi", "CV Onayı", "Zorunlu Staj",
    "Staj Dönemi", "Askerlik Durumu", "Uyruk", "Not Ortalaması", "İngilizce Seviyesi",
    "Kaynak", "Kayıt Tarihi",
  ];
  sheet.addRow(headers);
  styleHeader(sheet.getRow(1), "FF0F766E");

  for (let i = 1; i <= 5500; i++) {
    const duplicateOffset = i % 137 === 0 ? -1 : 0;
    const idNum = i + duplicateOffset;
    const status = pick(statuses);
    sheet.addRow([
      `STD-${String(idNum).padStart(5, "0")}`,
      `Aday ${String(idNum).padStart(5, "0")}`,
      `aday${idNum}@example.com`,
      `05${String(300000000 + idNum).slice(0, 9)}`,
      pick(schools),
      pick(departments),
      pick(cities),
      randInt(1998, 2005),
      pick(positions),
      status,
      status === "İletildi" ? new Date(2026, randInt(0, 3), randInt(1, 28)) : null,
      pick(yesNo),
      pick(yesNo),
      `${pick(["Haziran", "Temmuz", "Ağustos", "Eylül"])} 2026`,
      pick(["Tamamlandı", "Tecilli", "Muaf", "Belirtilmedi"]),
      pick(["Türkiye", "Azerbaycan", "KKTC", "Diğer"]),
      Number((2.2 + _rng() * 1.8).toFixed(2)),
      pick(["A1", "A2", "B1", "B2", "C1"]),
      pick(["Kariyer Portalı", "LinkedIn", "Üniversite Etkinliği", "Referans", "Web Form"]),
      new Date(2026, randInt(0, 4), randInt(1, 28)),
    ]);
  }

  sheet.getColumn(11).numFmt = "yyyy-mm-dd";
  sheet.getColumn(20).numFmt = "yyyy-mm-dd";
  sheet.columns.forEach((col) => { col.width = 18; });

  const out = path.join(excelDir, "dummy_ogrenci_formlari_5500.xlsx");
  await wb.xlsx.writeFile(out);
  return out;
}

function surveyRows(periodLabel, shift = 0) {
  const surveyDepts = ["İK", "Üretim", "Satış", "Finans", "IT", "Ar-Ge", "Lojistik", "Pazarlama", "Kalite", "Operasyon"];
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
    const dept = pick(surveyDepts, i, shift);
    const deptPenalty = dept === "Üretim" || dept === "Operasyon" ? -1 : 0;
    const improvement = periodLabel.includes("Q2") && (dept === "IT" || dept === "Ar-Ge") ? 1 : 0;
    const raw = [
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
    ];
    rows.push(raw.map((v, idx) => (idx >= 5 && idx <= 11 ? Math.max(1, Math.min(5, v)) : v)));
  }
  return rows;
}

async function createSurveyWorkbook(fileName, periodLabel, shift) {
  const wb = new ExcelJS.Workbook();
  const sheet = wb.addWorksheet("Anket", { views: [{ state: "frozen", ySplit: 1 }] });
  const rows = surveyRows(periodLabel, shift);
  rows.forEach((r) => sheet.addRow(r));
  styleHeader(sheet.getRow(1), "FF1D4ED8");
  sheet.columns.forEach((col) => { col.width = 18; });

  const out = path.join(surveyDir, fileName);
  await wb.xlsx.writeFile(out);
  return out;
}

const outputs = [];
outputs.push(await createStudentWorkbook());
outputs.push(await createSurveyWorkbook("dummy_ik_anket_2026_q1.xlsx", "2026-Q1", 0));
outputs.push(await createSurveyWorkbook("dummy_ik_anket_2026_q2.xlsx", "2026-Q2", 2));
console.log(outputs.join("\n"));
