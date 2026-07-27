// Render the RA-facing coding documents: the protocol manual and the decision
// log template. Arial throughout, US Letter, per house style.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LineRuleType, PageNumber, Footer, PageBreak,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "data", "coding");
const FONT = "Arial";
const BODY = 22;                                  // 11 pt
const LETTER = { width: 12240, height: 15840 };
const BURGUNDY = "8A2B2B";

const SPACED = { line: 276, lineRule: LineRuleType.AUTO, after: 140 };
const TIGHT = { line: 252, lineRule: LineRuleType.AUTO, after: 60 };

function runs(text, opts = {}) {
  const { size = BODY, bold = false, italics = false, color } = opts;
  const out = [];
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  for (const p of parts) {
    if (!p) continue;
    if (p.startsWith("**") && p.endsWith("**")) {
      out.push(new TextRun({ text: p.slice(2, -2), bold: true, font: FONT, size, color }));
    } else if (p.startsWith("`") && p.endsWith("`")) {
      out.push(new TextRun({ text: p.slice(1, -1), font: "Courier New", size: size - 2 }));
    } else {
      out.push(new TextRun({ text: p, bold, italics, font: FONT, size, color }));
    }
  }
  return out.length ? out : [new TextRun({ text: "", font: FONT, size })];
}

const P = (t, o) => new Paragraph({ children: runs(t, o), spacing: SPACED });
const H1 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 },
  children: runs(t, { size: 28, bold: true, color: BURGUNDY }),
});
const H2 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 120 },
  children: runs(t, { size: 24, bold: true, color: BURGUNDY }),
});
const LI = (t) => new Paragraph({ children: runs(t), bullet: { level: 0 }, spacing: TIGHT });

function table(headers, rows, widths) {
  const total = 9360;
  const w = widths || headers.map(() => Math.floor(total / headers.length));
  const sum = w.reduce((a, b) => a + b, 0);
  w[w.length - 1] += total - sum;
  const cell = (text, isHead) => new TableCell({
    width: { size: w[0], type: WidthType.DXA },
    shading: isHead ? { type: ShadingType.CLEAR, fill: "EFE4E4", color: "auto" } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: [new Paragraph({ spacing: TIGHT, children: runs(String(text), { size: 20, bold: isHead }) })],
  });
  return new Table({
    columnWidths: w,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => new TableCell({
          width: { size: w[i], type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: "EFE4E4", color: "auto" },
          margins: { top: 70, bottom: 70, left: 110, right: 110 },
          children: [new Paragraph({ spacing: TIGHT, children: runs(String(h), { size: 20, bold: true }) })],
        })),
      }),
      ...rows.map(r => new TableRow({
        children: r.map((c, i) => new TableCell({
          width: { size: w[i], type: WidthType.DXA },
          margins: { top: 70, bottom: 70, left: 110, right: 110 },
          children: [new Paragraph({ spacing: TIGHT, children: runs(String(c), { size: 20 }) })],
        })),
      })),
    ],
  });
}

function doc(children, title) {
  return new Document({
    creator: "Yunyu Xiao",
    title,
    styles: { default: { document: { run: { font: FONT, size: BODY } } } },
    sections: [{
      properties: { page: { size: LETTER, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
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
}

// ---------------------------------------------------------------- protocol
const protocol = [
  new Paragraph({ spacing: { after: 60 }, children: runs("SRED human coding protocol", { size: 36, bold: true, color: BURGUNDY }) }),
  new Paragraph({ spacing: { after: 300 }, children: runs("Onboarding and operating manual for research assistants  ·  Suicide Research Evidence Database  ·  Weill Cornell Medicine", { size: 20, color: "666666" }) }),

  H1("1.  What this project is"),
  P("The Suicide Research Evidence Database (SRED) is a corpus of roughly 97,000 suicide research articles published between 1989 and 2025, assembled from PubMed, Europe PMC, OpenAlex, and NIH iCite. Every abstract in it has been classified automatically along three dimensions: what kind of communication it is, whether it reports data, and what research method it used. The database also carries suicide-specific fields no bibliographic database contains, such as where a study sits on the prevention continuum and whether it engages a social determinant of health."),
  P("A classifier did that labelling. Before the results can be published, someone has to check the classifier against trained human judgement. That is this job."),

  H1("2.  What you are being asked to do"),
  P("Code a stratified sample of **300 abstracts by hand**, blind to the classifier's answers, so we can measure agreement between machine and human coding. Two coders do this independently on the identical 300 records; a third person adjudicates where they differ."),
  P("Five questions per record. Three are primary and must be answered for every record: communication type, empirical status, and research methodology. Two are secondary and are answered only when the abstract makes the answer clear: prevention level and whether a social determinant is addressed."),
  P("**You will not see the classifier's answers, and you will not see the other coder's.** This is not a matter of trust; it is what makes the resulting statistic mean anything. A coder who can see a proposed answer anchors on it, and the agreement figure then measures compliance rather than judgement."),

  H1("3.  Why the design looks the way it does"),
  P("Two coders rather than one, because a single coder produces no reliability statistic at all. Two rather than three, because the marginal information from a third is small relative to the cost of calibrating three people to a common standard, and because a separate adjudicator serves the disagreement-resolution role more cleanly than a third coder would."),
  P("An adjudicator who is not one of the two coders, because someone who has already committed to an answer is the wrong person to arbitrate their own disagreement."),
  P("A calibration batch before the main batch, because every codebook contains ambiguities its author did not anticipate, and it is far better to discover them on 30 records than on 300."),

  H1("4.  Roles"),
  table(["Role", "Who", "Commitment"], [
    ["Coder A", "Research assistant", "~15 hours across two batches"],
    ["Coder B", "Research assistant", "~15 hours across two batches"],
    ["Adjudicator", "PI or senior postdoc", "~3 hours"],
    ["Project lead", "PI", "Calibration meeting, final sign-off"],
  ], [2200, 3400, 3760]),
  new Paragraph({ spacing: { before: 160, after: 140 }, children: runs("Coders should not be people who built the classifier or who know its tendencies. Familiarity with suicide research or health services research helps; familiarity with the pipeline hurts.") }),

  H1("5.  Schedule"),
  table(["Step", "What happens", "Time"], [
    ["1. Onboarding", "Read this document and both workbook tabs", "45 min"],
    ["2. Practice", "Code 10 records with the lead, out loud", "1 hour"],
    ["3. Batch 1", "Each coder independently codes 30 calibration records", "2 h each"],
    ["4. Calibration meeting", "Compare, resolve, record every decision in the log", "1.5 h, whole team"],
    ["5. Batch 2", "Each coder independently codes 270 records", "11 h each"],
    ["6. Re-code Batch 1", "Both coders redo the 30 under the settled rules", "1.5 h each"],
    ["7. Adjudication", "Adjudicator resolves disagreements and flags", "3 hours"],
    ["8. Scoring", "Final kappa computed and written into the manuscript", "automated"],
  ], [2000, 5200, 2160]),
  new Paragraph({ spacing: { before: 160, after: 140 }, children: runs("Batch 2 should be spread over at least four sittings. Coding accuracy degrades measurably after about ninety minutes of continuous work, and there is nothing to be gained by pushing through it.") }),

  new Paragraph({ children: [new PageBreak()] }),

  H1("6.  What good work looks like"),
  P("**Consistency beats correctness.** For most records there is a defensible answer and the question is whether you apply the same rule every time. If you decide that protocol papers are non-empirical, that decision must hold on record 7 and record 261 alike."),
  P("**Flag rather than guess.** The FLAG column exists so that uncertainty is recorded rather than hidden inside a confident-looking answer. A flagged record goes to adjudication regardless of whether the coders happened to agree. There is no quota and no penalty; an honest flag is more useful to the project than a coin-flip."),
  P("**Never leave a primary field blank.** A blank cannot be scored and is not the same as \"cannot_tell\". If you genuinely cannot decide, choose the closest answer and flag it."),
  P("**Abstract only.** Do not open the full text, do not search for the paper, do not look up the authors. The classifier sees only the title and abstract, so a fair comparison means you see only the title and abstract. This is the rule most often broken by conscientious coders trying to be helpful."),
  P("**Say so if you drift.** If you realise partway through that you have been applying a rule inconsistently, tell the lead. Re-coding a batch is cheap. Publishing a reliability figure nobody believes is not."),

  H1("7.  When the codebook does not cover your case"),
  new Paragraph({ children: runs("1.  Re-read the Codebook tab, including the Boundary note for that question."), spacing: TIGHT, indent: { left: 360 } }),
  new Paragraph({ children: runs("2.  Check the decision log for a ruling already made."), spacing: TIGHT, indent: { left: 360 } }),
  new Paragraph({ children: runs("3.  If neither settles it, code your best answer, set FLAG to yes, and describe the difficulty in NOTES."), spacing: TIGHT, indent: { left: 360 } }),
  new Paragraph({ children: runs("4.  Raise it at the next check-in. If it is a rule rather than a one-off, the lead records it in the decision log and both coders apply it from then on."), spacing: SPACED, indent: { left: 360 } }),
  P("**Do not message the other coder about a specific record.** Coordinating on a case destroys the independence the whole design rests on. Route everything through the lead."),

  H1("8.  The decision log"),
  P("Every clarification made after coding begins is written into the decision log, with the date, the record that prompted it, the rule adopted, and the reasoning. This exists for three reasons: so both coders apply the same rule, so a rule adopted in week one is still being applied in week three, and so the manuscript can describe how the codebook evolved rather than pretending it sprang fully formed."),
  P("If a decision changes how earlier records should have been coded, say so explicitly in the log. Those records get re-coded."),

  H1("9.  A note on the material"),
  P("You will be reading several hundred abstracts about suicide, including studies of method, of death, and of bereavement. Most are dry and clinical. Some are not."),
  P("This is worth naming up front rather than discovering at record 140. Take breaks. Do not code late at night. If the material is affecting you, say so to the lead, and know in advance that stepping back from the task carries no consequence for your position on the project. If you would find it useful, your institution's employee assistance or student counselling service is available to you, and using it is unremarkable."),
  P("If you have personal experience with suicide, that does not disqualify you from this work and may make you a better coder. It does mean it is worth thinking in advance about what pace and what schedule will work for you."),

  H1("10.  Confidentiality and data handling"),
  P("The abstracts are published, public material; there is nothing confidential in the corpus itself. Two handling rules still apply."),
  LI("**Do not share your workbook with the other coder** at any point before adjudication is complete."),
  LI("**Do not open the scoring key.** The file whose name contains DO_NOT_SHARE_WITH_CODERS holds the classifier's answers. It should never be sent to a coder, and if you receive it by accident, say so immediately rather than deleting it quietly, because we need to know whether the codes you produced afterwards are still usable."),

  H1("11.  Files"),
  table(["File", "Who holds it", "Purpose"], [
    ["SRED_coding_CoderA.xlsx", "Coder A only", "Instructions, codebook, 300 records"],
    ["SRED_coding_CoderB.xlsx", "Coder B only", "Identical, independent copy"],
    ["SRED_coding_decision_log.docx", "Shared; lead maintains", "Every rule clarified after coding began"],
    ["SRED_adjudication.xlsx", "Adjudicator", "Generated later; disagreements and flags only"],
    ["_scoring_key_...csv", "Project lead only", "Classifier predictions, withheld from coders"],
  ], [3200, 2400, 3760]),

  H1("12.  How the numbers are produced"),
  new Paragraph({ spacing: TIGHT, children: runs("`python scripts/08_score_coding.py --mode reliability`") }),
  new Paragraph({ spacing: TIGHT, children: runs("`python scripts/08_score_coding.py --mode adjudicate`") }),
  new Paragraph({ spacing: SPACED, children: runs("`python scripts/08_score_coding.py --mode confirm`") }),
  P("The output reports Cohen's kappa, percent agreement, the confusion matrix, and the marginal distribution for each field."),
  P("**Read kappa and percent agreement together.** On a field where one category holds 90% of the records, two coders can agree 92% of the time and still score a kappa near zero, because chance alone would have produced 90% agreement. That is a property of the statistic, not a failure of the coders, and the scoring output says so explicitly when it detects the condition. The manuscript reports both figures for exactly this reason."),
];

// ------------------------------------------------------------- decision log
const logRows = [
  ["2026-__-__", "e.g. row 14", "Q2", "Protocol papers describing a study not yet conducted are non_empirical.", "No data have been collected or analysed, so there is nothing empirical to report yet.", "No", "___"],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
  ["", "", "", "", "", "", ""],
];

const decisionLog = [
  new Paragraph({ spacing: { after: 60 }, children: runs("SRED coding decision log", { size: 36, bold: true, color: BURGUNDY }) }),
  new Paragraph({ spacing: { after: 300 }, children: runs("Every rule clarified after coding began  ·  maintained by the project lead", { size: 20, color: "666666" }) }),

  H1("How to use this"),
  P("The codebook in the workbook is the starting position. This log records every clarification made once real records started arriving, because no codebook survives contact with 300 abstracts unchanged."),
  P("The lead writes the entries, not the coders. A coder who hits an ambiguity flags the record and raises it; the lead decides, records it here, and tells both coders. That keeps one voice on the rules."),
  P("**Fill the last two columns honestly.** If a new rule means earlier records were coded under a different understanding, those records must be re-coded, and the log is where that obligation is recorded. A log that never says \"yes, re-code\" is usually a log nobody is really keeping."),
  P("Cite this log in the manuscript's coding section. Reviewers reasonably want to know whether a codebook was fixed in advance or evolved during coding; the honest answer is almost always that it evolved, and showing how is more credible than implying it did not."),

  H1("Entries"),
  table(
    ["Date", "Prompted by", "Q", "Rule adopted", "Reasoning", "Re-code earlier records?", "Told both coders"],
    logRows,
    [1000, 1100, 500, 2400, 2400, 1100, 860],
  ),

  new Paragraph({ children: [new PageBreak()] }),
  H1("Calibration meeting notes"),
  P("After Batch 1, record here what the comparison showed and what was agreed. Useful things to capture: which question produced the most disagreement, whether the disagreements were random or systematic, and whether either coder was applying a rule the other had not seen."),
  P("Systematic disagreement is good news. It means one rule needs stating more clearly, and once stated the problem disappears. Scattered disagreement across many categories is the harder case: it usually means the question itself is underspecified, and the fix is a sharper definition rather than more training."),
  ...Array.from({ length: 14 }, () => new Paragraph({
    spacing: { after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "D8D8D8", space: 4 } },
    children: runs(" "),
  })),
];

fs.mkdirSync(OUT, { recursive: true });
Promise.all([
  Packer.toBuffer(doc(protocol, "SRED human coding protocol")).then(b =>
    fs.writeFileSync(path.join(OUT, "SRED_coding_protocol.docx"), b)),
  Packer.toBuffer(doc(decisionLog, "SRED coding decision log")).then(b =>
    fs.writeFileSync(path.join(OUT, "SRED_coding_decision_log.docx"), b)),
]).then(() => console.log("wrote SRED_coding_protocol.docx and SRED_coding_decision_log.docx"));
