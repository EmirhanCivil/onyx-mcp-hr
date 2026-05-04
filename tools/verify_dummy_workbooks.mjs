import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.cwd();
const files = [
  "dummy_ogrenci_formlari_5500.xlsx",
  "dummy_ik_anket_2026_q1.xlsx",
  "dummy_ik_anket_2026_q2.xlsx",
];

for (const file of files) {
  const fullPath = path.join(root, "data", "uploads", file);
  const blob = await FileBlob.load(fullPath);
  const workbook = await SpreadsheetFile.importXlsx(blob);
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table",
    tableMaxRows: 3,
    tableMaxCols: 6,
    maxChars: 2000,
  });
  const sheetName = workbook.worksheets.getItemAt(0).name;
  const renderRange = file.includes("5500") ? "A1:T30" : "A1:M30";
  const rendered = await workbook.render({ sheetName, range: renderRange, scale: 1, format: "png" });
  const bytes = new Uint8Array(await rendered.arrayBuffer());
  await fs.writeFile(path.join(root, "data", "outputs", "charts", `${file}.preview.png`), bytes);
  console.log(`VERIFIED ${file}`);
  console.log(summary.ndjson.split("\n").slice(0, 4).join("\n"));
}
