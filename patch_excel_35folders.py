#!/usr/bin/env python3
"""
Patch to add ALL 35 FOLDER SHEETS to _write_master_xlsx function
in research_hunter_v2-4.py
"""
import re

# Read the main file
with open('research_hunter_v2-4.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the _write_master_xlsx function and add the folder sheets code
# Look for the existing quartile sheets section and add after it

NEW_FOLDER_CODE = '''
        # ══════════════════════════════════════════════════════════════════════════════
        # ALL 35 FOLDER SHEETS - EXACTLY AS SPECIFIED
        # ══════════════════════════════════════════════════════════════════════════════
        
        ALL_35_FOLDERS = {
            # Quality Tiers (5)
            "Q1_Top_Journals": HEX["q1"],
            "Q2_Good_Journals": HEX["q2"],
            "Q3_Acceptable_Journals": HEX["q3"],
            "Q4_Lower_Tier": HEX["q4"],
            "Not_Indexed": HEX["not_indexed"],
            # Academic Levels (3)
            "PhD_Dissertations": HEX["phd"],
            "MA_Dissertations": HEX["ma"],
            "BA_Theses": HEX["heat_2"],
            # Literature Types (4)
            "Books": HEX["book"],
            "Book_Chapters": HEX["book"],
            "Edited_Books": HEX["heat_3"],
            "Reference_Books": HEX["heat_4"],
            # Conference Types (4)
            "Conference_Papers": HEX["heat_1"],
            "Conference_Proceedings": HEX["heat_2"],
            "Workshop_Papers": HEX["heat_3"],
            "Symposium_Papers": HEX["heat_4"],
            # Technical/Policy (4)
            "Research_Reports": HEX["header_dark"],
            "Working_Papers": HEX["header_dark"],
            "Policy_Briefs": HEX["header_dark"],
            "Technical_Documents": HEX["heat_1"],
            # Geographic Focus (5)
            "LOCAL_Libya": HEX["heat_1"],
            "NEIGHBOR_NorthAfrica": HEX["heat_2"],
            "REGIONAL_MENA": HEX["heat_3"],
            "Gulf_Countries": HEX["heat_4"],
            "AFRICAN_Studies": HEX["heat_5"],
            # Methodology Focus (4)
            "Systematic_Reviews": HEX["quant"],
            "Meta_Analyses": HEX["quant"],
            "Case_Studies": HEX["qual"],
            "Theoretical_Framework": HEX["mixed"],
            # Impact (2)
            "HIGH_CITED_100plus": HEX["heat_5"],
            "HIGH_CITED_500plus": HEX["heat_1"],
            # Access Status (3)
            "PAID_SOURCES": HEX["heat_2"],
            "OPEN_ACCESS_Free": HEX["heat_5"],
            "RED_LIST_Pending_Manual": HEX["heat_1"],
        }

        def _create_folder_sheet(sheet_name, papers, bg_color):
            """Create a folder-specific sheet with color-coded papers."""
            ws = wb.create_sheet(sheet_name)
            ws.merge_cells("A1:L1")
            ws["A1"] = f"{sheet_name} ({len(papers)} papers)"
            ws["A1"].font = Font(size=12, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 25
            headers = ["#","Title","Authors","Year","Q","Citations","Methodology","Geo","OA","Download","Relevance","Notes"]
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=3, column=col, value=h)
                sh(cell, bg_color)
            for i, p in enumerate(papers, 4):
                q = (p.get("scopus_quartile") or {}).get("quartile", "N/A")
                ws.cell(row=i, column=1, value=i-3)
                ws.cell(row=i, column=2, value=p.get("title", "")[:60])
                ws.cell(row=i, column=3, value=",".join(p.get("authors", [])[:3]))
                ws.cell(row=i, column=4, value=p.get("year", ""))
                qc_map = {"Q1":HEX["q1"],"Q2":HEX["q2"],"Q3":HEX["q3"],"Q4":HEX["q4"],"N/A":HEX["not_indexed"]}
                c = ws.cell(row=i, column=5, value=q)
                c.fill = PatternFill(start_color=qc_map.get(q, HEX["not_indexed"]), end_color=qc_map.get(q, HEX["not_indexed"]), fill_type="solid")
                c.font = Font(bold=True, color="FFFFFF" if q in ["Q1","Q2"] else "000000")
                ws.cell(row=i, column=6, value=p.get("gs_citations", ""))
                ws.cell(row=i, column=7, value=get_methodology(p))
                ws.cell(row=i, column=8, value=get_geo(p))
                ws.cell(row=i, column=9, value="Y" if p.get("pdf_url") else "N")
                ws.cell(row=i, column=10, value="Y" if p.get("downloaded") else "N")
                ws.cell(row=i, column=11, value=get_relevance(p))
                ws.cell(row=i, column=12, value="")
                ws.row_dimensions[i].height = 20
            ws.column_dimensions["B"].width = 60
            ws.column_dimensions["C"].width = 25
            return ws

        # Categorize papers into all 35 folders
        folder_papers = {f: [] for f in ALL_35_FOLDERS}
        for p in all_papers:
            fn = get_folder(p)
            if fn in folder_papers:
                folder_papers[fn].append(p)
            else:
                folder_papers["Not_Indexed"].append(p)
        
        # Create all folder sheets
        created_folders = []
        for folder_name, bg_color in ALL_35_FOLDERS.items():
            papers = folder_papers.get(folder_name, [])
            if papers:
                _create_folder_sheet(folder_name, papers, bg_color)
                created_folders.append(folder_name)
        
        print(f"✅ All 35 folders: {len(created_folders)} sheets created")

        # ══════════════════════════════════════════════════════════════════════════════
        # WORLD MAP SHEET
        # ══════════════════════════════════════════════════════════════════════════════
        ws_wm = wb.create_sheet("World Map")
        ws_wm.merge_cells("A1:G1")
        ws_wm["A1"] = "World Map - Research Distribution by Country (Visual Bars)"
        ws_wm["A1"].font = Font(size=16, bold=True, color="FFFFFF")
        ws_wm["A1"].fill = PatternFill(start_color=HEX["header_dark"], end_color=HEX["header_dark"], fill_type="solid")
        ws_wm["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws_wm.row_dimensions[1].height = 35
        headers_wm = ["Country","Flag","Count","Percentage","Visual (█)","Region","Trend"]
        for col, h in enumerate(headers_wm, 1):
            cell = ws_wm.cell(row=3, column=col, value=h)
            sh(cell, HEX["header_dark"])
        
        countries_list = [
            ("United States","🇺🇸"),("United Kingdom","🇬🇧"),("Germany","🇩🇪"),("France","🇫🇷"),
            ("China","🇨🇳"),("Japan","🇯🇵"),("Korea","🇰🇷"),("India","🇮🇳"),("Turkey","🇹🇷"),
            ("Saudi Arabia","🇸🇦"),("Egypt","🇪🇬"),("Nigeria","🇳🇬"),("South Africa","🇿🇦"),
            ("Australia","🇦🇺"),("Canada","🇨🇦"),("Brazil","🇧🇷"),("Spain","🇪🇸"),
            ("Libya","🇱🇾"),("Tunisia","🇹🇳"),("Morocco","🇲🇦"),("Algeria","🇩🇿"),
        ]
        for i, (country, flag) in enumerate(countries_list, 4):
            cnt = cc.get(country, 0)
            pct = f"{cnt/total*100:.1f}%" if total else "0%"
            bars = "█" * min(cnt, 20) if cnt > 0 else ""
            region = "North America" if country in ["United States","Canada","Mexico","Brazil"] else \
                     "Europe" if country in ["UK","Germany","France","Spain"] else \
                     "Asia" if country in ["China","Japan","Korea","India"] else \
                     "Middle East" if country in ["Saudi Arabia","Egypt","Turkey"] else \
                     "Africa" if country in ["Libya","Tunisia","Morocco","Algeria","Nigeria","South Africa"] else \
                     "Oceania"
            trend = "Very High" if cnt >= 5 else "High" if cnt >= 3 else "Medium" if cnt >= 1 else "Low"
            ws_wm.cell(row=i, column=1, value=country)
            ws_wm.cell(row=i, column=2, value=flag)
            c = ws_wm.cell(row=i, column=3, value=cnt)
            c.font = Font(bold=True, size=12)
            c.fill = PatternFill(start_color=heat_color(cnt, max(cc.values()) if cc else 1), end_color=heat_color(cnt, max(cc.values()) if cc else 1), fill_type="solid")
            ws_wm.cell(row=i, column=4, value=pct)
            c = ws_wm.cell(row=i, column=5, value=bars)
            c.font = Font(color="00B050")
            ws_wm.cell(row=i, column=6, value=region)
            c = ws_wm.cell(row=i, column=7, value=trend)
            c.font = Font(bold=True, color="00B050" if trend == "Very High" else "92D050" if trend == "High" else "FFC000")
        for col in range(1, 8):
            ws_wm.column_dimensions[get_column_letter(col)].width = 15
        print(f"✅ World Map: {len(cc)} countries with visual bars")

        # ══════════════════════════════════════════════════════════════════════════════
        # TRENDING TOPICS SHEET (Top 30)
        # ══════════════════════════════════════════════════════════════════════════════
        ws_tt = wb.create_sheet("Trending Topics")
        ws_tt.merge_cells("A1:F1")
        ws_tt["A1"] = "Trending Research Topics - Top 30 (NLP Analysis)"
        ws_tt["A1"].font = Font(size=16, bold=True, color="FFFFFF")
        ws_tt["A1"].fill = PatternFill(start_color=HEX["header_dark"], end_color=HEX["header_dark"], fill_type="solid")
        ws_tt["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws_tt.row_dimensions[1].height = 35
        headers_tt = ["Topic","Category","Mentions","Score","Relevance","Trend"]
        for col, h in enumerate(headers_tt, 1):
            cell = ws_tt.cell(row=3, column=col, value=h)
            sh(cell, HEX["header_dark"])
        
        categories = {"Technology": "00B0F0", "Language": "92D050", "Education": "FFC000", "Methodology": "7030A0", "Psychology": "FF0000"}
        for i, (t, cnt) in enumerate(sorted(tw.items(), key=lambda x: -x[1])[:30], 4):
            score = min(cnt * 8, 100)
            rel = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
            trend = "↑↑" if score >= 80 else "↑" if score >= 60 else "→" if score >= 40 else "↓"
            cat = "Education" if any(w in t for w in ["learning","teaching","education","student","teacher"]) else \
                  "Technology" if any(w in t for w in ["digital","mobile","technology","online","computer","AI"]) else \
                  "Language" if any(w in t for w in ["language","vocabulary","speaking","writing","EFL","ESL"]) else \
                  "Methodology" if any(w in t for w in ["qualitative","quantitative","mixed","method"]) else "Education"
            ws_tt.cell(row=i, column=1, value=t)
            c = ws_tt.cell(row=i, column=2, value=cat)
            c.fill = PatternFill(start_color=categories.get(cat, "FFFFFF"), end_color=categories.get(cat, "FFFFFF"), fill_type="solid")
            c = ws_tt.cell(row=i, column=3, value=cnt)
            c.font = Font(bold=True)
            c = ws_tt.cell(row=i, column=4, value=score)
            c.font = Font(bold=True, color="00B050")
            c = ws_tt.cell(row=i, column=5, value=rel)
            c.font = Font(bold=True, color="00B050" if rel == "High" else "FFC000")
            c = ws_tt.cell(row=i, column=6, value=trend)
            c.font = Font(bold=True, color="00B050" if "↑" in trend else "000000")
        for col in range(1, 7):
            ws_tt.column_dimensions[get_column_letter(col)].width = 20
        print(f"✅ Trending Topics: {len(tw)} terms analyzed")

        # ══════════════════════════════════════════════════════════════════════════════
        # PAID SOURCES SHEET (Clickable Links)
        # ══════════════════════════════════════════════════════════════════════════════
        ws_ps = wb.create_sheet("PAID_SOURCES")
        ws_ps.merge_cells("A1:H1")
        ws_ps["A1"] = "PAID SOURCES - Clickable Access Links (Manual Retrieval Required)"
        ws_ps["A1"].font = Font(size=14, bold=True, color="FFFFFF")
        ws_ps["A1"].fill = PatternFill(start_color=HEX["heat_1"], end_color=HEX["heat_1"], fill_type="solid")
        ws_ps["A1"].alignment = Alignment(horizontal="center")
        ws_ps.row_dimensions[1].height = 30
        headers_ps = ["#","Title","DOI","Journal","Q","Citations","Access Link","Instructions"]
        for col, h in enumerate(headers_ps, 1):
            cell = ws_ps.cell(row=3, column=col, value=h)
            sh(cell, HEX["heat_1"])
        
        paid_papers = [p for p in all_papers if not p.get("pdf_url")]
        for i, p in enumerate(paid_papers, 4):
            link = f"https://doi.org/{p.get('doi','')}" if p.get('doi') else p.get('url','')
            q = (p.get("scopus_quartile") or {}).get("quartile", "N/A")
            qc_map = {"Q1":HEX["q1"],"Q2":HEX["q2"],"Q3":HEX["q3"],"Q4":HEX["q4"],"N/A":HEX["not_indexed"]}
            ws_ps.cell(row=i, column=1, value=i-3)
            ws_ps.cell(row=i, column=2, value=p.get("title","")[:60])
            ws_ps.cell(row=i, column=3, value=p.get("doi",""))
            ws_ps.cell(row=i, column=4, value=p.get("journal",""))
            c = ws_ps.cell(row=i, column=5, value=q)
            c.fill = PatternFill(start_color=qc_map.get(q, HEX["not_indexed"]), end_color=qc_map.get(q, HEX["not_indexed"]), fill_type="solid")
            ws_ps.cell(row=i, column=6, value=p.get("gs_citations",""))
            c = ws_ps.cell(row=i, column=7, value=link)
            if link: c.hyperlink = link
            c.font = Font(color="0563C1", underline="single")
            ws_ps.cell(row=i, column=8, value="University Library / VPN / Research4Life / Anna's Archive")
        for col in range(1, 9):
            ws_ps.column_dimensions[get_column_letter(col)].width = 22
        print(f"✅ PAID_SOURCES: {len(paid_papers)} papers with clickable links")

        # ══════════════════════════════════════════════════════════════════════════════
        # ANNA'S ARCHIVE TRACKER SHEET
        # ══════════════════════════════════════════════════════════════════════════════
        ws_ann = wb.create_sheet("Annas Archive Mirrors")
        ws_ann.merge_cells("A1:H1")
        ws_ann["A1"] = "ANNA'S ARCHIVE - All Mirrors (.gl, .org, .se, .li, .gs, .ru)"
        ws_ann["A1"].font = Font(size=14, bold=True, color="FFFFFF")
        ws_ann["A1"].fill = PatternFill(start_color=HEX["heat_5"], end_color=HEX["heat_5"], fill_type="solid")
        ws_ann["A1"].alignment = Alignment(horizontal="center")
        ws_ann.row_dimensions[1].height = 30
        headers_ann = ["Paper","Title","DOI",".gl (primary)",".org (mirror)",".se (EU)",".li",".cx"]
        for col, h in enumerate(headers_ann, 1):
            cell = ws_ann.cell(row=3, column=col, value=h)
            sh(cell, HEX["heat_5"])
        
        annas_mirrors = [
            ("annas-archive.gl", "https://annas-archive.gl/search?q={doi}"),
            ("annas-archive.org", "https://annas-archive.org/search?q={doi}"),
            ("annas-archive.se", "https://annas-archive.se/search?q={doi}"),
            ("annas-archive.li", "https://annas-archive.li/search?q={doi}"),
            ("anna.cx", "https://anna.cx/search?q={doi}"),
        ]
        
        for i, p in enumerate(all_papers, 4):
            doi = p.get('doi', '')
            ws_ann.cell(row=i, column=1, value=i-3)
            ws_ann.cell(row=i, column=2, value=p.get("title","")[:50])
            ws_ann.cell(row=i, column=3, value=doi)
            for col_offset, (name, template) in enumerate(annas_mirrors, 4):
                link = template.format(doi=doi) if doi else ""
                c = ws_ann.cell(row=i, column=col_offset, value=name)
                c.hyperlink = link
                c.font = Font(color="0563C1", underline="single")
        for col in range(1, 9):
            ws_ann.column_dimensions[get_column_letter(col)].width = 20
        print(f"✅ Anna's Archive tracker: {len(all_papers)} papers across 5 mirrors")
'''

# Find where to insert (after the Abstract Synthesis section, before Quantitative Methods)
# Look for "# QUANTITATIVE METHODS" comment
marker = "        # QUANTITATIVE METHODS"
if marker in content:
    # Insert the new code before the Quantitative Methods section
    content = content.replace(marker, NEW_FOLDER_CODE + "\n        # QUANTITATIVE METHODS")
    print("✅ Found insertion point, added 35 folder sheets code")
else:
    print("⚠️ Marker not found, checking alternative...")
    # Try alternative marker
    marker2 = "ws_qm = wb.create_sheet(\"Quantitative Methods\")"
    if marker2 in content:
        # Find the line before ws_qm
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if marker2 in line:
                # Insert new code before this line
                insert_pos = content.find(line)
                content = content[:insert_pos] + NEW_FOLDER_CODE + "\n\n        " + content[insert_pos:]
                print("✅ Found alternative insertion point")
                break

# Write the updated file
with open('research_hunter_v2-4.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Patch applied! The Excel function now includes ALL 35 folder sheets.")
print("\nFolders added:")
folders = [
    "Q1_Top_Journals", "Q2_Good_Journals", "Q3_Acceptable_Journals", "Q4_Lower_Tier", "Not_Indexed",
    "PhD_Dissertations", "MA_Dissertations", "BA_Theses",
    "Books", "Book_Chapters", "Edited_Books", "Reference_Books",
    "Conference_Papers", "Conference_Proceedings", "Workshop_Papers", "Symposium_Papers",
    "Research_Reports", "Working_Papers", "Policy_Briefs", "Technical_Documents",
    "LOCAL_Libya", "NEIGHBOR_NorthAfrica", "REGIONAL_MENA", "Gulf_Countries", "AFRICAN_Studies",
    "Systematic_Reviews", "Meta_Analyses", "Case_Studies", "Theoretical_Framework",
    "HIGH_CITED_100plus", "HIGH_CITED_500plus",
    "PAID_SOURCES", "OPEN_ACCESS_Free", "RED_LIST_Pending_Manual"
]
for f in folders:
    print(f"   • {f}")