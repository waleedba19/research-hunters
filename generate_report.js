#!/usr/bin/env node
// research_report.js — Generate a professional DOCX from JSON report data
// Used by research_hunter_v2-4.py  (called via generate_docx_report)

const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType } = require('docx');

const jsonPath = process.argv[2] || 'report_data.json';
const docxPath = process.argv[3] || 'research_report.docx';

if (!fs.existsSync(jsonPath)) {
    console.error(`Error: JSON report file not found: ${jsonPath}`);
    process.exit(1);
}

const data = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
const papers = data.papers || [];
const qDist = data.run_stats?.q_distribution || {};
const typeDist = data.run_stats?.type_distribution || {};

// ── Helper functions ────────────────────────────────────────────────────────
function txt(text, opts = {}) {
    return new TextRun({ text: String(text || ''), ...opts });
}

function heading(text, level = HeadingLevel.HEADING_1) {
    return new Paragraph({ heading: level, children: [txt(text, { bold: true, size: level === HeadingLevel.HEADING_1 ? 28 : 24 })] });
}

function para(children) {
    return new Paragraph({ children, spacing: { after: 120 } });
}

function boldPara(label, value) {
    return para([txt(label, { bold: true }), txt(` ${value}`)]);
}

// ── Build document ─────────────────────────────────────────────────────────
const children = [];

// Title page
children.push(heading(`Research Report: ${data.title || 'Untitled'}`));
children.push(para([txt(`Field: ${data.field || 'N/A'}`, { italics: true, color: '555555' })]));
children.push(para([txt(`Generated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`, { color: '777777' })]));
children.push(para([txt(`Papers Found: ${papers.length}  |  PDFs Downloaded: ${papers.filter(p => p.downloaded).length}`, { bold: true })]));
children.push(new Paragraph({ children: [], spacing: { after: 200 } }));

// Executive Summary
children.push(heading('Executive Summary', HeadingLevel.HEADING_2));
const summary = data.executive_summary || 'No summary available.';
summary.split('\n').forEach(line => {
    if (line.trim()) {
        children.push(para([txt(line.trim())]));
    }
});
children.push(new Paragraph({ children: [], spacing: { after: 200 } }));

// Scopus Quartile Distribution
children.push(heading('Scopus Quartile Distribution', HeadingLevel.HEADING_2));
const qRows = [
    ['Q1', qDist.Q1 || 0],
    ['Q2', qDist.Q2 || 0],
    ['Q3', qDist.Q3 || 0],
    ['Q4', qDist.Q4 || 0],
    ['Not Found', qDist['Not Found'] || 0],
];
qRows.forEach(([q, count]) => {
    children.push(para([txt(`  ${q}: `, { bold: true }), txt(`${count} papers`)]));
});
children.push(new Paragraph({ children: [], spacing: { after: 200 } }));

// All Papers table
children.push(heading(`All Papers (${papers.length})`, HeadingLevel.HEADING_2));
papers.forEach((p, i) => {
    const q = (p.scopus_quartile || {}).quartile || '—';
    const dl = p.downloaded ? '✅' : '—';
    const auth = (p.authors || []).slice(0, 3).join('; ');
    children.push(para([
        txt(`${i + 1}. `, { bold: true }),
        txt(`${p.title || 'Untitled'}`, { bold: true }),
    ]));
    children.push(para([
        txt(`   ${auth}`, { italics: true, size: 18, color: '555555' }),
        txt(` | ${p.year || '—'} | ${p.journal || '—'} | ${q} | PDF: ${dl}`, { size: 18, color: '777777' }),
    ]));
    if (p.doi) {
        children.push(para([txt(`   DOI: `, { size: 18, color: '777777' }), txt(`https://doi.org/${p.doi}`, { color: '2266cc' })]));
    }
    if (p.abstract) {
        children.push(para([txt(`   ${p.abstract.substring(0, 200)}...`, { size: 18, color: '999999' })]));
    }
    children.push(new Paragraph({ children: [], spacing: { after: 60 } }));
});

// APA References
children.push(new Paragraph({ children: [], spacing: { after: 200 } }));
children.push(heading('References (APA 7th Edition)', HeadingLevel.HEADING_2));
const sorted = [...papers].sort((a, b) => ((a.authors || [''])[0] || '').localeCompare((b.authors || [''])[0] || ''));
sorted.forEach(p => {
    const apa = p.apa || buildApa(p);
    children.push(para([txt(apa, { size: 20 })]));
});

function buildApa(p) {
    const auth = (p.authors || []).slice(0, 6).map(a => a || 'Unknown').join('; ') + ((p.authors || []).length > 6 ? ' et al.' : '');
    const year = p.year || 'n.d.';
    const title = p.title || 'Untitled';
    const journal = p.journal ? `, ${p.journal}` : '';
    const doi = p.doi ? `. https://doi.org/${p.doi}` : '.';
    return `${auth} (${year}). ${title}${journal}${doi}`;
}

// Build document
const doc = new Document({
    styles: {
        default: {
            document: {
                run: { font: 'Calibri', size: 22 },
            },
        },
    },
    sections: [{ children }],
});

Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync(docxPath, buf);
    console.log(`DOCX report saved: ${docxPath} (${papers.length} papers)`);
}).catch(err => {
    console.error(`DOCX generation failed: ${err.message}`);
    process.exit(1);
});