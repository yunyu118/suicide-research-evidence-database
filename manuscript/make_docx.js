// Build the submission-ready .docx from manuscript_built.md.
//
// Written with docx-js rather than pandoc because the target journals want
// specific mechanics that a generic converter does not produce: Arial
// throughout, US Letter, double-spaced body, continuous line numbers, and
// figures placed with captions. Pandoc gets the text across; it does not get
// the manuscript through a submission portal.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  PageBreak, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  BorderStyle, LineRuleType, PageNumber, Header, Footer,
} = require("docx");

const DIR = __dirname;
const ROOT = path.resolve(DIR, "..");
const SRC = path.join(DIR, "manuscript_built.md");
const OUT = path.join(DIR, "SRED_manuscript.docx");

const FONT = "Arial";          // Yunyu's standing preference for all documents
const BODY_SIZE = 22;          // half-points => 11 pt
const LETTER = { width: 12240, height: 15840 };   // DXA, US Letter

const FIGURES = [
  ["fig1_growth", "Figure 1. Growth in suicide research output and publishing venues, 1989-2023."],
  ["fig2_empiricism", "Figure 2. Evolution of empirical and non-empirical suicide scholarship, 1989-2023."],
  ["fig3_methodology", "Figure 3. Distribution of research methodologies in empirical suicide research, 1989-2023."],
  ["fig4_collaboration", "Figure 4. Trends in collaborative authorship in suicide research, 1989-2023."],
  ["fig5_uncited", "Figure 5. Percentage of suicide research articles never cited, by publication year."],
  ["fig6_dispersion", "Figure 6. Dispersion of suicide research beyond its specialty journals, 1989-2023."],
  ["fig7_sdoh", "Figure 7. Social determinants of health addressed in suicide research, by decade."],
  ["fig8_prevention", "Figure 8. Position of suicide research on the prevention continuum, by decade."],
];

// --- inline markdown -> TextRun[] -------------------------------------------
function runs(text, { bold = false, italics = false, size = BODY_SIZE } = {}) {
  const out = [];
  // Split on **bold**, *italic*, and `code`, keeping the delimiters.
  const parts = text.split(/(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|`[^`]+`)/g);
  for (const part of parts) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) {
      out.push(new TextRun({ text: part.slice(2, -2), bold: true, font: FONT, size }));
    } else if (part.startsWith("`") && part.endsWith("`")) {
      out.push(new TextRun({ text: part.slice(1, -1), font: "Courier New", size: size - 2 }));
    } else if (part.startsWith("*") && part.endsWith("*")) {
      out.push(new TextRun({ text: part.slice(1, -1), italics: true, font: FONT, size }));
    } else {
      out.push(new TextRun({ text: part, bold, italics, font: FONT, size }));
    }
  }
  return out.length ? out : [new TextRun({ text: "", font: FONT, size })];
}

const DOUBLE = { line: 480, lineRule: LineRuleType.AUTO, after: 0 };
const SINGLE = { line: 240, lineRule: LineRuleType.AUTO, after: 120 };

function body(text, spacing = DOUBLE) {
  return new Paragraph({ children: runs(text), spacing, alignment: AlignmentType.LEFT });
}

function heading(text, level) {
  const size = level === 1 ? 28 : level === 2 ? 26 : 24;
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1
      : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    spacing: { before: 300, after: 160 },
    children: runs(text.replace(/^#+\s*/, ""), { bold: true, size }),
  });
}

// --- markdown table -> docx Table -------------------------------------------
function mdTable(rows) {
  const cols = rows[0].length;
  const total = 9360;                                    // 6.5 in at 1440 DXA
  const w = Math.floor(total / cols);
  const widths = Array(cols).fill(w);
  widths[cols - 1] = total - w * (cols - 1);             // absorb rounding

  return new Table({
    columnWidths: widths,
    rows: rows.map((cells, ri) => new TableRow({
      tableHeader: ri === 0,
      children: cells.map((c, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.DXA },
        shading: ri === 0
          ? { type: ShadingType.CLEAR, fill: "E8E8E8", color: "auto" }
          : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({
          spacing: SINGLE,
          children: runs(c, { bold: ri === 0, size: 20 }),
        })],
      })),
    })),
  });
}

// --- parse ------------------------------------------------------------------
const md = fs.readFileSync(SRC, "utf8");
const lines = md.split("\n");
const children = [];
let tableBuf = [];

function flushTable() {
  if (!tableBuf.length) return;
  const rows = tableBuf
    .filter(r => !/^\|[\s:|-]+\|$/.test(r.trim()))
    .map(r => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
  if (rows.length) {
    children.push(mdTable(rows));
    children.push(new Paragraph({ text: "", spacing: { after: 160 } }));
  }
  tableBuf = [];
}

for (let i = 0; i < lines.length; i++) {
  const raw = lines[i];
  const line = raw.trimEnd();

  if (line.trim().startsWith("|")) { tableBuf.push(line); continue; }
  flushTable();

  if (!line.trim()) { continue; }

  if (/^---+$/.test(line.trim())) {
    children.push(new Paragraph({
      children: [new TextRun({ text: "", font: FONT, size: BODY_SIZE })],
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "BBBBBB", space: 6 } },
      spacing: { before: 160, after: 200 },
    }));
    continue;
  }

  const h = line.match(/^(#{1,4})\s+(.*)$/);
  if (h) { children.push(heading(h[2], h[1].length)); continue; }

  const li = line.match(/^\s*[-*]\s+(.*)$/);
  if (li) {
    children.push(new Paragraph({
      children: runs(li[1]),
      bullet: { level: 0 },
      spacing: SINGLE,
    }));
    continue;
  }

  const nli = line.match(/^\s*(\d+)\.\s+(.*)$/);
  if (nli) {
    children.push(new Paragraph({
      children: runs(`${nli[1]}. ${nli[2]}`),
      spacing: SINGLE,
      indent: { left: 360, hanging: 360 },
    }));
    continue;
  }

  // Reference list entries: hanging indent, single spaced.
  const isRef = /^[A-Z][A-Za-z'’\-]+,\s[A-Z]\.|^de Solla|^\*\[Additional/.test(line.trim());
  children.push(new Paragraph({
    children: runs(line.trim()),
    spacing: isRef ? SINGLE : DOUBLE,
    indent: isRef ? { left: 720, hanging: 720 } : undefined,
  }));
}
flushTable();

// --- figures ----------------------------------------------------------------
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("Figures", 2));
for (const [name, caption] of FIGURES) {
  const p = path.join(ROOT, "figures", `${name}.png`);
  if (!fs.existsSync(p)) continue;
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 80 },
    children: [new ImageRun({
      type: "png",
      data: fs.readFileSync(p),
      transformation: { width: 600, height: 340 },
    })],
  }));
  children.push(new Paragraph({
    spacing: SINGLE,
    children: runs(caption, { size: 20 }),
  }));
  children.push(new Paragraph({ children: [new PageBreak()] }));
}

// --- document ---------------------------------------------------------------
const doc = new Document({
  creator: "Yunyu Xiao",
  title: "The Suicide Research Evidence Database",
  description: "AI-enabled analysis of knowledge production in suicide research and prevention, 1989-2025",
  styles: {
    default: {
      document: { run: { font: FONT, size: BODY_SIZE } },
      heading1: { run: { font: FONT, size: 28, bold: true, color: "000000" } },
      heading2: { run: { font: FONT, size: 26, bold: true, color: "000000" } },
      heading3: { run: { font: FONT, size: 24, bold: true, color: "000000" } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: LETTER,
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
      lineNumbers: { countBy: 1, restart: "continuous" },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: runs("Suicide Research Evidence Database", { size: 18 }),
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT} (${(buf.length / 1024).toFixed(0)} KB, ${children.length} blocks)`);
});
