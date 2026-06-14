#!/usr/bin/env node
/**
 * Enhanced generate_report.js — Professional PhD-Level DOCX Reports
 * Creates structured academic reports with:
 * - Cover page with metadata
 * - Executive summary section
 * - Detailed paper tables (per author and quartile)
 * - Citations and references
 * - Professional formatting with colors and borders
 */

const fs = require('fs');
const {
    Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
    WidthType, AlignmentType, BorderStyle, ShadingType, PageBreak, Header, Footer,
    PageNumber, convertInchesToTwip
} = require('docx');

const jsonPath = process.argv[2] || 'report_data.json';
const docxPath = process.argv[3] || 'research_report.docx';

if (!fs.existsSync(jsonPath)) {
    console.error(`Error: JSON report file not found: ${jsonPath}`);
    process.exit(1);
}

const data = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
const papers = data.papers || [];
const qDist = data.run_stats?.q_distribution || {};

// ── Color constants ──────────────────────────────────────────────────────────
const COLORS = {
    primary: "1F3864",
    secondary: "2E75B6",
    accent: "5B9BD5",
    q1: "70AD47",
    q2: "9DC3E6",
    q3: "FFC000",
    q4: "FF6B6B",
    white: "FFFFFF",
    lightGray: "F2F2F2",
    darkGray: "404040",
};

// ── Helper functions ──────────────────────────────────────────────────────────
function txt(text, opts = {}) {
    return new TextRun({ text: String(text || ''), ...opts });
}

function emptyPara(spacing = 80) {
    return new Paragraph({ children: [], spacing: { after: spacing } });
}

function heading(text, level = HeadingLevel.HEADING_1, color = COLORS.primary) {
    const sizes = { 1: 32, 2: 28, 3: 24, 4: 22 };
    return new Paragraph({
        heading: level,
        children: [txt(text, { bold: true, size: sizes[level] || 24, color: color })],
        spacing: { before: 300, after: 150 },
        border: level === 1 ? {
            bottom: { color: COLORS.accent, size: 12, space: 4, style: BorderStyle.SINGLE }
        } : undefined
    });
}

function para(children, opts = {}) {
    return new Paragraph({
        children,
        spacing: { after: opts.spacingAfter || 120, before: opts.spacingBefore || 0 },
        alignment: opts.alignment || AlignmentType.LEFT
    });
}

function coloredBox(text, bgColor = COLORS.primary) {
    return new Paragraph({
        children: [txt(text, { bold: true, color: COLORS.white, size: 20 })],
        shading: { type: ShadingType.CLEAR, fill: bgColor },
        spacing: { before: 100, after: 100 },
        alignment: AlignmentType.CENTER
    });
}

// ── Table creation helpers ───────────────────────────────────────────────────
function createHeaderCell(text, width = 2000, color = COLORS.primary) {
    return new TableCell({
        children: [new Paragraph({
            children: [txt(text, { bold: true, color: COLORS.white, size: 18 })],
            alignment: AlignmentType.CENTER,
            spacing: { after: 0 }
        })],
        shading: { type: ShadingType.CLEAR, fill: color },
        width: { size: width, type: WidthType.DXA },
        margins: { top: 100, bottom: 100, left: 100, right: 100 }
    });
}

function createDataCell(text, width = 2000, opts = {}) {
    const { bold = false, color = COLORS.darkGray, bgColor = null, alignment = AlignmentType.LEFT } = opts;
    return new TableCell({
        children: [new Paragraph({
            children: [txt(String(text || ''), { bold, color, size: 18 })],
            alignment,
            spacing: { after: 0 }
        })],
        shading: bgColor ? { type: ShadingType.CLEAR, fill: bgColor } : undefined,
        width: { size: width, type: WidthType.DXA },
        margins: { top: 60, bottom: 60, left: 100, right: 100 }
    });
}

// ── Build cover page ─────────────────────────────────────────────────────────
function buildCoverPage() {
    return [
        emptyPara(400),
        new Paragraph({
            children: [txt(data.title || 'Research Report', { bold: true, size: 48, color: COLORS.primary })],
            alignment: AlignmentType.CENTER,
            spacing: { after: 200 }
        }),
        emptyPara(200),
        new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
                new TableRow({ children: [createHeaderCell('REPORT METADATA', 9000, COLORS.primary)] }),
                new TableRow({ children: [createDataCell('Field:', 2000, { bold: true }), createDataCell(data.field || 'N/A', 7000)] }),
                new TableRow({ children: [createDataCell('Date Generated:', 2000, { bold: true }), createDataCell(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), 7000)] }),
                new TableRow({ children: [createDataCell('Total Papers:', 2000, { bold: true }), createDataCell(String(papers.length), 7000)] }),
                new TableRow({ children: [createDataCell('PDFs Downloaded:', 2000, { bold: true }), createDataCell(String(papers.filter(p => p.downloaded).length), 7000)] }),
                new TableRow({ children: [createDataCell('Search Mode:', 2000, { bold: true }), createDataCell(data.search_mode || 'N/A', 7000)] }),
                new TableRow({ children: [createDataCell('Language:', 2000, { bold: true }), createDataCell(data.search_language || 'English', 7000)] }),
            ]
        }),
        emptyPara(400),
        coloredBox('🔬 Generated by Research Hunter v6 — Academic Research Automation', COLORS.secondary),
        new Paragraph({ children: [new PageBreak()] })
    ];
}

// ── Build executive summary ─────────────────────────────────────────────────
function buildExecutiveSummary() {
    const summary = data.executive_summary || 'Comprehensive research summary not available.';
    return [
        heading('EXECUTIVE SUMMARY', HeadingLevel.HEADING_1),
        emptyPara(100),
        new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
                new TableRow({ children: [createHeaderCell('RESEARCH OVERVIEW', 9000, COLORS.secondary)] }),
                new TableRow({ children: [createDataCell('Topic:', 1500, { bold: true }), createDataCell(data.title || 'N/A', 7500)] }),
                new TableRow({ children: [createDataCell('Academic Field:', 1500, { bold: true }), createDataCell(data.field || 'N/A', 7500)] }),
                new TableRow({ children: [createDataCell('Year Range:', 1500, { bold: true }), createDataCell(String(data.year_range || 'All years'), 7500)] }),
                new TableRow({ children: [createDataCell('Country Context:', 1500, { bold: true }), createDataCell(data.country_context || 'International', 7500)] }),
            ]
        }),
        emptyPara(150),
        heading('Summary Content', HeadingLevel.HEADING_2),
        ...summary.split('\n').filter(l => l.trim()).map(line => para([txt(line.trim(), { size: 20 })])),
        emptyPara(200)
    ];
}

// ── Build Scopus quartile distribution ───────────────────────────────────────
function buildQuartileSection() {
    const quartileColors = { Q1: COLORS.q1, Q2: COLORS.q2, Q3: COLORS.q3, Q4: COLORS.q4 };
    const qualityMap = { Q1: 'Top-tier high impact', Q2: 'Good quality', Q3: 'Acceptable', Q4: 'Lower tier', 'Not Found': 'Not indexed' };
    
    return [
        heading('SCOPUS QUARTILE DISTRIBUTION', HeadingLevel.HEADING_1),
        emptyPara(100),
        new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
                new TableRow({ children: [
                    createHeaderCell('Quartile', 3000),
                    createHeaderCell('Count', 2000),
                    createHeaderCell('Percentage', 2000),
                    createHeaderCell('Quality', 4000)
                ]}),
                ...Object.entries(qDist).map(([q, count]) => {
                    const total = Object.values(qDist).reduce((a, b) => a + b, 0) || 1;
                    const pct = ((count / total) * 100).toFixed(1);
                    return new TableRow({ children: [
                        createDataCell(q, 3000, { bold: true, bgColor: quartileColors[q] || COLORS.lightGray }),
                        createDataCell(String(count), 2000, { alignment: AlignmentType.CENTER }),
                        createDataCell(`${pct}%`, 2000, { alignment: AlignmentType.CENTER }),
                        createDataCell(qualityMap[q] || 'N/A', 4000)
                    ]});
                })
            ]
        }),
        emptyPara(200)
    ];
}

// ── Build detailed papers table ──────────────────────────────────────────────
function buildPapersTable() {
    if (papers.length === 0) {
        return [para([txt('No papers available.', { italics: true, color: COLORS.darkGray })])];
    }

    const rows = [];
    const grouped = { Q1: [], Q2: [], Q3: [], Q4: [], 'Not Found': [] };
    papers.forEach(p => {
        const q = (p.scopus_quartile || {}).quartile || 'Not Found';
        (grouped[q] || grouped['Not Found']).push(p);
    });

    for (const [quartile, qPapers] of Object.entries(grouped)) {
        if (qPapers.length === 0) continue;
        
        rows.push(new TableRow({ children: [
            new TableCell({
                children: [new Paragraph({
                    children: [txt(`${quartile} Papers (${qPapers.length})`, { bold: true, color: COLORS.white, size: 20 })],
                    alignment: AlignmentType.CENTER
                })],
                shading: { type: ShadingType.CLEAR, fill: COLORS.primary },
                columnSpan: 5,
                margins: { top: 120, bottom: 120 }
            })
        ]}));

        rows.push(new TableRow({ children: [
            createHeaderCell('#', 400),
            createHeaderCell('Title & Authors', 5000),
            createHeaderCell('Year/Journal', 2500),
            createHeaderCell('Q', 400),
            createHeaderCell('DOI', 2000),
        ]}));

        qPapers.forEach((p, i) => {
            const q = (p.scopus_quartile || {}).quartile || '—';
            const authors = (p.authors || []).slice(0, 4).join('; ');
            const authorText = authors + ((p.authors || []).length > 4 ? ` +${p.authors.length - 4} more` : '');
            const qColor = { Q1: COLORS.q1, Q2: COLORS.q2, Q3: COLORS.q3, Q4: COLORS.q4 }[q] || COLORS.lightGray;
            
            rows.push(new TableRow({ children: [
                createDataCell(String(i + 1), 400, { alignment: AlignmentType.CENTER }),
                new TableCell({
                    children: [
                        new Paragraph({ children: [txt(p.title || 'Untitled', { bold: true, size: 18 })], spacing: { after: 40 } }),
                        new Paragraph({ children: [txt(authorText, { italics: true, size: 16, color: COLORS.darkGray })], spacing: { after: 0 } })
                    ],
                    width: { size: 5000, type: WidthType.DXA }
                }),
                new TableCell({
                    children: [
                        new Paragraph({ children: [txt(p.year || '—', { bold: true, size: 18 })], spacing: { after: 30 } }),
                        new Paragraph({ children: [txt(p.journal || '—', { italics: true, size: 16, color: COLORS.darkGray })], spacing: { after: 0 } })
                    ],
                    width: { size: 2500, type: WidthType.DXA }
                }),
                createDataCell(q, 400, { bold: true, alignment: AlignmentType.CENTER, bgColor: qColor }),
                createDataCell(p.doi ? `https://doi.org/${p.doi}` : '—', 2000, { color: '0563C1' })
            ]}));
        });
    }

    return [
        heading('DETAILED PAPERS', HeadingLevel.HEADING_1),
        emptyPara(100),
        new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows })
    ];
}

// ── Build author analysis ──────────────────────────────────────────────────────
function buildAuthorSection() {
    const authorCounts = {};
    papers.forEach(p => { (p.authors || []).forEach(a => { authorCounts[a] = (authorCounts[a] || 0) + 1; }); });
    
    const topAuthors = Object.entries(authorCounts).sort((a, b) => b[1] - a[1]).slice(0, 30);

    if (topAuthors.length === 0) {
        return [para([txt('No author data available.', { italics: true, color: COLORS.darkGray })])];
    }

    const authorRows = [
        new TableRow({ children: [
            createHeaderCell('Rank', 600),
            createHeaderCell('Author Name', 4000),
            createHeaderCell('Papers', 800),
            createHeaderCell('Papers Count Bar', 3000)
        ]})
    ];

    topAuthors.forEach(([author, count], i) => {
        const bar = '█'.repeat(Math.ceil(count / 3)) + '░'.repeat(Math.max(0, 10 - Math.ceil(count / 3)));
        authorRows.push(new TableRow({ children: [
            createDataCell(String(i + 1), 600, { alignment: AlignmentType.CENTER }),
            createDataCell(author, 4000),
            createDataCell(String(count), 800, { alignment: AlignmentType.CENTER, bold: true }),
            new TableCell({
                children: [new Paragraph({ children: [txt(bar, { color: COLORS.primary })], spacing: { after: 0 } })],
                width: { size: 3000, type: WidthType.DXA }
            })
        ]}));
    });

    return [
        emptyPara(200),
        heading('TOP AUTHORS ANALYSIS', HeadingLevel.HEADING_1),
        emptyPara(100),
        new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: authorRows })
    ];
}

// ── Build references section ──────────────────────────────────────────────────
function buildReferencesSection() {
    const sorted = [...papers].sort((a, b) => ((a.authors || [''])[0] || '').localeCompare((b.authors || [''])[0] || ''));

    const refRows = [
        new TableRow({ children: [
            createHeaderCell('#', 500),
            createHeaderCell('APA 7th Edition Reference', 8500)
        ]})
    ];

    sorted.forEach((p, i) => {
        const apa = p.apa || buildApa(p);
        refRows.push(new TableRow({ children: [
            createDataCell(String(i + 1), 500, { alignment: AlignmentType.CENTER }),
            createDataCell(apa, 8500)
        ]}));
    });

    return [
        emptyPara(300),
        new Paragraph({ children: [new PageBreak()] }),
        heading('REFERENCES (APA 7th Edition)', HeadingLevel.HEADING_1),
        emptyPara(100),
        new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: refRows })
    ];
}

function buildApa(p) {
    const auth = (p.authors || []).slice(0, 6).map(a => a || 'Unknown').join('; ') + ((p.authors || []).length > 6 ? ' et al.' : '');
    const year = p.year || 'n.d.';
    const title = p.title || 'Untitled';
    const journal = p.journal ? `, ${p.journal}` : '';
    const vol = p.volume ? `, ${p.volume}` : '';
    const iss = p.issue ? `(${p.issue})` : '';
    const pages = p.pages ? `, ${p.pages}` : '';
    const doi = p.doi ? `. https://doi.org/${p.doi}` : '.';
    return `${auth} (${year}). ${title}${journal}${vol}${iss}${pages}${doi}`;
}

// ── Main document builder ─────────────────────────────────────────────────────
const children = [
    ...buildCoverPage(),
    ...buildExecutiveSummary(),
    ...buildQuartileSection(),
    ...buildPapersTable(),
    ...buildAuthorSection(),
    ...buildReferencesSection()
];

const doc = new Document({
    styles: { default: { document: { run: { font: 'Calibri', size: 22 } } } },
    sections: [{
        properties: {
            page: { margin: { top: convertInchesToTwip(1), right: convertInchesToTwip(0.75), bottom: convertInchesToTwip(1), left: convertInchesToTwip(0.75) } }
        },
        headers: { default: new Header({ children: [new Paragraph({ children: [txt('Research Hunter v6 — Academic Report', { color: COLORS.accent, size: 16 })], alignment: AlignmentType.RIGHT })] }) },
        footers: { default: new Footer({ children: [new Paragraph({ children: [txt('Page ', { size: 16, color: COLORS.darkGray }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: COLORS.darkGray }), txt(` of `, { size: 16, color: COLORS.darkGray }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: COLORS.darkGray })], alignment: AlignmentType.CENTER })] }) },
        children
    }]
});

Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync(docxPath, buf);
    console.log(`✅ Professional DOCX report saved: ${docxPath} (${papers.length} papers)`);
}).catch(err => {
    console.error(`❌ DOCX generation failed: ${err.message}`);
    process.exit(1);
});