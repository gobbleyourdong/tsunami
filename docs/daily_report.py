#!/usr/bin/env python3
"""Generate a one-page daily highlight reel PDF for tsunami.

Scans git log for 24h, extracts highlights (new scaffolds, tool additions,
bug fixes, QA findings from SCRATCHPAD), renders a readable single-page PDF
in the tsunami color palette.

Usage:
  python ~/ComfyUI/CelebV-HQ/ark/daily_report.py
  # Output: ~/ComfyUI/CelebV-HQ/ark/DAILY_REPORT.pdf (always overwritten)
"""

import subprocess
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

REPO = os.path.expanduser("~/ComfyUI/CelebV-HQ/ark")
OUTPUT_PDF = os.path.join(REPO, "DAILY_REPORT.pdf")
SCRATCHPAD = os.path.join(REPO, "SCRATCHPAD.md")
DELIVERABLES = os.path.join(REPO, "workspace", "deliverables")


def git_log_24h():
    since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    result = subprocess.run(
        ["git", "-C", REPO, "log", f"--since={since}",
         "--format=%H|%ai|%s", "--no-merges"],
        capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0][:8],
                    "date": parts[1].strip(),
                    "msg": parts[2].strip()
                })
    return commits


def git_files_24h():
    since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    result = subprocess.run(
        ["git", "-C", REPO, "log", f"--since={since}",
         "--format=", "--name-only", "--diff-filter=A", "--no-merges"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f.strip()]


def git_lines_changed_24h():
    since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    result = subprocess.run(
        ["git", "-C", REPO, "log", f"--since={since}",
         "--numstat", "--format=", "--no-merges"],
        capture_output=True, text=True
    )
    added, removed = 0, 0
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                added += int(parts[0])
                removed += int(parts[1])
            except ValueError:
                pass
    return added, removed


def parse_scratchpad():
    """Extract bug counts + eval results from SCRATCHPAD.md."""
    stats = {
        "active_bugs": 0,
        "fixed_bugs": 0,
        "evals_pass": 0,
        "evals_fail": 0,
        "active_bug_titles": [],
        "fixed_bug_titles": [],
        "eval_titles": [],
    }
    if not os.path.exists(SCRATCHPAD):
        return stats

    with open(SCRATCHPAD) as f:
        content = f.read()

    def section_between(text, start_heading, end_headings):
        """Return text between a start heading and the next of end_headings, or EOF."""
        start_re = re.compile(rf"^## {re.escape(start_heading)}.*$", re.MULTILINE)
        m = start_re.search(text)
        if not m:
            return ""
        start = m.end()
        end = len(text)
        for eh in end_headings:
            end_re = re.compile(rf"^## {re.escape(eh)}.*$", re.MULTILINE)
            em = end_re.search(text, pos=start)
            if em and em.start() < end:
                end = em.start()
        return text[start:end]

    active_section = section_between(content, "ACTIVE BUGS",
                                     ["FIXED BUGS", "RECENT EVALS"])
    fixed_section = section_between(content, "FIXED BUGS",
                                    ["RECENT EVALS", "ACTIVE BUGS"])
    evals_section = section_between(content, "RECENT EVALS",
                                    ["FIXED BUGS", "ACTIVE BUGS"])

    bug_re = re.compile(r"^## \[(QA-[0-9]|Programmer[- ]?discovered)\] Bug:\s*(.+)$",
                       re.MULTILINE)

    active_bugs = bug_re.findall(active_section)
    stats["active_bugs"] = len(active_bugs)
    stats["active_bug_titles"] = [b[1][:75] for b in active_bugs[:4]]

    fixed_bugs = bug_re.findall(fixed_section)
    stats["fixed_bugs"] = len(fixed_bugs)
    stats["fixed_bug_titles"] = [b[1][:75] for b in fixed_bugs[:4]]

    eval_re = re.compile(
        r"^## \[(QA-[0-9])\] (Eval|Probe):\s*(.+?)$(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL
    )
    for _, _, title, body in eval_re.findall(evals_section):
        result_m = re.search(r"Result:\s*(PASS|FAIL)", body)
        result = result_m.group(1) if result_m else None
        if result == "PASS":
            stats["evals_pass"] += 1
        elif result == "FAIL":
            stats["evals_fail"] += 1
        if result:
            stats["eval_titles"].append(f"{result[:4]}: {title.strip()[:65]}")
    stats["eval_titles"] = stats["eval_titles"][:4]

    return stats


def count_deliverables_24h():
    """Count deliverable dirs created in last 24h."""
    if not os.path.isdir(DELIVERABLES):
        return 0, []
    cutoff = (datetime.now() - timedelta(hours=24)).timestamp()
    recent = []
    try:
        for name in os.listdir(DELIVERABLES):
            path = os.path.join(DELIVERABLES, name)
            if os.path.isdir(path) and os.path.getctime(path) >= cutoff:
                recent.append(name)
    except OSError:
        pass
    return len(recent), recent[:6]


def count_scaffolds():
    """Count scaffold templates available."""
    scaffolds_dir = os.path.join(REPO, "scaffolds")
    if not os.path.isdir(scaffolds_dir):
        return 0
    try:
        return sum(1 for n in os.listdir(scaffolds_dir)
                   if os.path.isdir(os.path.join(scaffolds_dir, n)))
    except OSError:
        return 0


def extract_highlights(commits, new_files):
    """Extract highlight items from commits and new files."""
    highlights = {
        "fixes": [],       # bug-fix commits
        "features": [],    # new features / tool additions
        "scaffolds": [],   # scaffold changes
        "tools": [],       # engine/tool files
        "docs": [],        # docs/readme updates
    }

    for c in commits:
        msg = c["msg"]
        low = msg.lower()
        if any(k in low for k in ["fix", "refuse", "block", "gate", "bug", "eliminate"]):
            highlights["fixes"].append(msg[:80])
        elif any(k in low for k in ["add", "enable", "nudge", "support", "implement"]):
            highlights["features"].append(msg[:80])
        elif "readme" in low or "doc" in low:
            highlights["docs"].append(msg[:80])

    for f in new_files:
        base = os.path.basename(f)
        if f.startswith("scaffolds/"):
            parts = f.split("/")
            if len(parts) > 1:
                highlights["scaffolds"].append(parts[1])
        elif f.startswith("engine/") or f.startswith("tsunami/tools/") or f.startswith("cli/"):
            highlights["tools"].append(f)
        elif f.endswith(".md") and not f.startswith("workspace/"):
            highlights["docs"].append(base)

    # Deduplicate
    for k in highlights:
        highlights[k] = list(dict.fromkeys(highlights[k]))[:6]

    return highlights


def categorize_files(files):
    cats = defaultdict(int)
    for f in files:
        if "/" in f:
            domain = f.split("/")[0]
        else:
            domain = "root"
        cats[domain] += 1
    return dict(cats)


def _ocean_bg(canvas, doc):
    """Draw dark ocean background with subtle horizontal lines."""
    canvas.saveState()
    # Deep dark background (tsunami --bg: #08090d)
    canvas.setFillColor(colors.HexColor('#08090d'))
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    # Subtle horizontal scan lines (wave suggestion)
    canvas.setStrokeColor(colors.HexColor('#111318'))
    canvas.setLineWidth(0.3)
    for y in range(0, int(doc.pagesize[1]), 4):
        canvas.line(0, y, doc.pagesize[0], y)
    # Ocean-blue border (tsunami --accent: #4a9eff)
    canvas.setStrokeColor(colors.HexColor('#4a9eff'))
    canvas.setLineWidth(1.5)
    canvas.rect(8, 8, doc.pagesize[0]-16, doc.pagesize[1]-16, fill=0, stroke=1)
    canvas.restoreState()


def generate_pdf(commits, new_files, highlights, lines_added, lines_removed,
                 scratchpad, deliverables_count, deliverables_list, scaffold_count):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cats = categorize_files(new_files)

    doc = SimpleDocTemplate(OUTPUT_PDF, pagesize=letter,
                            topMargin=0.4*inch, bottomMargin=0.3*inch,
                            leftMargin=0.6*inch, rightMargin=0.6*inch)

    styles = getSampleStyleSheet()
    # Tsunami palette
    light = colors.HexColor('#d0d2d8')      # --text
    dim = colors.HexColor('#505568')         # --muted
    accent = colors.HexColor('#4a9eff')      # --accent (ocean blue)
    accent_bright = colors.HexColor('#6ab4ff')  # --accent-bright
    green = colors.HexColor('#34d4b0')       # --green (teal)
    yellow = colors.HexColor('#d4a834')      # --yellow
    red = colors.HexColor('#d44848')         # --red
    blue = colors.HexColor('#5090d4')        # --blue
    purple = colors.HexColor('#8060c4')      # --purple
    orange = colors.HexColor('#d47834')      # --orange

    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=15, spaceAfter=1,
                                  textColor=colors.white, fontName='Helvetica-Bold')
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=8,
                               textColor=dim, alignment=TA_CENTER, spaceAfter=4)
    section_style = ParagraphStyle('Sec', parent=styles['Heading3'], fontSize=9,
                                   textColor=accent, spaceBefore=5, spaceAfter=2,
                                   fontName='Helvetica-Bold')
    item_style = ParagraphStyle('Item', parent=styles['Normal'], fontSize=7, leading=9,
                                leftIndent=8, spaceBefore=0, textColor=light)
    footer_style = ParagraphStyle('Foot', parent=styles['Normal'], fontSize=6,
                                  textColor=dim, alignment=TA_CENTER)

    story = []

    # Header
    story.append(Paragraph("TSUNAMI — TIDE REPORT", title_style))
    story.append(Paragraph(
        f"{now} | {len(commits)} commits | {len(set(new_files))} new files | "
        f"+{lines_added} / -{lines_removed} lines | "
        f"{scratchpad['active_bugs']} active bugs | {scratchpad['fixed_bugs']} fixed",
        sub_style))

    # Metrics — single row
    active_color = red if scratchpad["active_bugs"] > 5 else (yellow if scratchpad["active_bugs"] > 0 else green)
    active_hex = '#%02x%02x%02x' % (int(active_color.red*255), int(active_color.green*255), int(active_color.blue*255))
    metrics_style = ParagraphStyle('Metrics', parent=styles['Normal'], fontSize=11,
                                    alignment=TA_CENTER, textColor=light, leading=16)
    story.append(Paragraph(
        f'<font color="#4a9eff">ACTIVE</font> <font color="{active_hex}"><b>{scratchpad["active_bugs"]}</b></font>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;'
        f'<font color="#4a9eff">FIXED</font> <font color="#34d4b0"><b>{scratchpad["fixed_bugs"]}</b></font>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;'
        f'<font color="#4a9eff">BUILDS</font> <font color="#6ab4ff"><b>{deliverables_count}</b></font>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;'
        f'<font color="#4a9eff">COMMITS</font> <font color="#6ab4ff"><b>{len(commits)}</b></font>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;'
        f'<font color="#4a9eff">SCAFFOLDS</font> <font color="#6ab4ff"><b>{scaffold_count}</b></font>',
        metrics_style))
    story.append(Spacer(1, 4))

    # Eval pass/fail summary
    if scratchpad["evals_pass"] + scratchpad["evals_fail"] > 0:
        total_evals = scratchpad["evals_pass"] + scratchpad["evals_fail"]
        pass_pct = 100 * scratchpad["evals_pass"] / total_evals
        pass_color = "#34d4b0" if pass_pct >= 70 else ("#d4a834" if pass_pct >= 40 else "#d44848")
        story.append(Paragraph(
            f'<font color="#4a9eff" size="8">UNDERTOW (QA EVALS)</font> '
            f'<font color="{pass_color}" size="9"><b>{scratchpad["evals_pass"]}P / {scratchpad["evals_fail"]}F</b></font> '
            f'<font color="#505568" size="7">({pass_pct:.0f}% pass)</font>',
            ParagraphStyle('M2', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=light)
        ))
        story.append(Spacer(1, 4))

    # Domain bars — compact
    if cats:
        story.append(Paragraph("DOMAINS", section_style))
        for domain in sorted(cats.keys()):
            pct = min(cats[domain] / max(max(cats.values()), 1), 1.0)
            bar_len = int(pct * 35)
            bar = chr(9608) * bar_len
            story.append(Paragraph(
                f'<font color="#505568" size="7">{domain:<14}</font> '
                f'<font color="#4a9eff" size="7">{bar}</font> '
                f'<font color="#6ab4ff" size="7">{cats[domain]}</font>',
                item_style))

    # Highlight sections
    sec_map = [
        ("SWELL — FIXES",       highlights["fixes"],      green),
        ("WAVE — FEATURES",     highlights["features"],   accent_bright),
        ("EDDIES — TOOLS",      highlights["tools"],      orange),
        ("SCAFFOLDS",           highlights["scaffolds"],  purple),
        ("BREAK — DOCS",        highlights["docs"],       blue),
    ]

    for sec_title, items, sec_color in sec_map:
        if not items:
            continue
        hex_c = '#%02x%02x%02x' % (int(sec_color.red*255), int(sec_color.green*255), int(sec_color.blue*255))
        story.append(Paragraph(f'<font color="{hex_c}">{chr(9632)} {sec_title}</font>', section_style))
        for item in items[:4]:
            safe = item.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f'<font color="#505568">{chr(8226)}</font> {safe}', item_style))

    # Active bugs section
    if scratchpad["active_bug_titles"]:
        story.append(Paragraph(f'<font color="#d44848">{chr(9632)} UNDERTOW — ACTIVE BUGS</font>', section_style))
        for title in scratchpad["active_bug_titles"]:
            safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f'<font color="#505568">{chr(8226)}</font> {safe}', item_style))

    # Evals section (sample)
    if scratchpad["eval_titles"]:
        story.append(Paragraph(f'<font color="#d4a834">{chr(9632)} UNDERTOW — RECENT EVALS</font>', section_style))
        for title in scratchpad["eval_titles"]:
            safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f'<font color="#505568">{chr(8226)}</font> {safe}', item_style))

    # Deliverables built
    if deliverables_list:
        story.append(Paragraph(f'<font color="#6ab4ff">{chr(9632)} BUILDS — DELIVERABLES (24h)</font>', section_style))
        for name in deliverables_list:
            safe = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f'<font color="#505568">{chr(8226)}</font> {safe}', item_style))

    # Recent commits — very compact
    story.append(Spacer(1, 3))
    story.append(Paragraph(f'<font color="#4a9eff">{chr(9632)} RECENT COMMITS</font>', section_style))
    for c in commits[:8]:
        time_short = c["date"].split(" ")[1][:5] if " " in c["date"] else ""
        msg = c["msg"][:70]
        safe_msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(
            f'<font color="#3d4250" size="6">{c["hash"]} {time_short}</font> '
            f'<font color="#a0a0b0" size="6.5">{safe_msg}</font>',
            item_style))
    if len(commits) > 8:
        story.append(Paragraph(f'<font color="#3d4250" size="6">+{len(commits)-8} more</font>', item_style))

    # Footer
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"gobbleyourdong/tsunami | {chr(127754)} | {now}", footer_style))

    doc.build(story, onFirstPage=_ocean_bg, onLaterPages=_ocean_bg)
    return OUTPUT_PDF


def main():
    commits = git_log_24h()
    new_files = git_files_24h()
    lines_added, lines_removed = git_lines_changed_24h()
    scratchpad = parse_scratchpad()
    deliverables_count, deliverables_list = count_deliverables_24h()
    scaffold_count = count_scaffolds()
    highlights = extract_highlights(commits, new_files)

    pdf_path = generate_pdf(
        commits, new_files, highlights,
        lines_added, lines_removed,
        scratchpad, deliverables_count, deliverables_list,
        scaffold_count
    )
    print(f"PDF: {pdf_path}")

    total_highlights = sum(len(v) for v in highlights.values())
    print(f"  {len(commits)} commits, {len(set(new_files))} new files, "
          f"+{lines_added}/-{lines_removed} lines, "
          f"{scratchpad['active_bugs']} active bugs, {scratchpad['fixed_bugs']} fixed, "
          f"{scratchpad['evals_pass']}P/{scratchpad['evals_fail']}F evals, "
          f"{deliverables_count} builds, {total_highlights} highlights")


if __name__ == "__main__":
    main()
