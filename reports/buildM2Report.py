"""Build the Milestone 2 report (four pages, AI Strategy canvas style) and print it to PDF.

Every number comes from m2ReportData.gather(), which queries the live
databases read-only. Usage: uv run reports/buildM2Report.py
"""

import subprocess
from pathlib import Path

from m2ReportData import gather

HERE = Path(__file__).resolve().parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
OUT_HTML = HERE / "team8Milestone2Report.html"
OUT_PDF = HERE / "team8Milestone2Report.pdf"
MEETING_NOTES = "https://docs.google.com/document/d/1lXb8wGagvXWI6eDV1wB0E36veDIipPSqC3Tmnh4Q4KQ/edit?tab=t.0"
VIDEO_LINK = None  # Set to the shared video URL before submitting.

CSS = """
@page { size: Letter; margin: 0.5in 0.62in; }
* { box-sizing: border-box; }
html, body { background: #fff; }
body { font-family: "Times New Roman", Times, serif; font-size: 10.5pt; line-height: 1.3; color: #000; margin: 0; }
p { margin: 0 0 4pt; text-align: justify; }
ul { margin: 0 0 5pt; padding-left: 15pt; } li { margin: 0 0 2pt; text-align: justify; }
.eyebrow { font-size: 10.5pt; font-weight: bold; text-align: center; letter-spacing: 0.03em; margin: 0 0 6pt; }
.title { font-size: 12.5pt; font-weight: bold; text-align: center; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 3pt; }
.subtitle { font-size: 10.5pt; font-style: italic; text-align: center; margin: 0 0 7pt; }
table { width: 100%; border-collapse: collapse; margin: 3pt 0 6pt; }
th, td { border: 0.75pt solid #000; padding: 2.4pt 4.5pt; font-size: 9.5pt; line-height: 1.2; text-align: left; vertical-align: top; }
th { font-weight: bold; background: #f2f2f2; }
tr:nth-child(even) td { background: #fafafa; }
.meta th, .meta td { font-size: 9.5pt; }
.banner { border: 0.75pt solid #000; padding: 5pt 8pt; margin: 5pt 0 6pt; }
.banner p, .banner ul { margin: 0 0 2pt; }
.sectionhead { border-top: 1.25pt solid #000; padding-top: 5pt; margin-top: 2pt; }
.page { page-break-before: always; }
.sectiontitle { font-size: 11.5pt; font-weight: bold; letter-spacing: 0.03em; margin: 0 0 3pt; }
.fhead { font-size: 10.5pt; font-weight: bold; margin: 6pt 0 2pt; }
.cap { font-size: 9.5pt; font-style: italic; margin: 6pt 0 1pt; }
figure { margin: 4pt 0 4pt; text-align: center; }
figcaption { font-size: 9.5pt; font-style: italic; text-align: left; margin-top: 2pt; }
svg { width: 100%; height: auto; max-width: 4.8in; }
.bx { fill: #fff; stroke: #000; stroke-width: 1.1; } .fl { fill: #f2f2f2; stroke: #000; stroke-width: 1.1; }
.pl { fill: #fff; stroke: #000; stroke-width: 1.2; stroke-dasharray: 6 4; }
.ar { stroke: #000; stroke-width: 1.2; fill: none; } .dash { stroke-dasharray: 5 4; }
.t { font-family: "Times New Roman", Times, serif; font-size: 14px; fill: #000; }
.tb { font-family: "Times New Roman", Times, serif; font-size: 14px; font-weight: bold; fill: #000; }
.ti { font-family: "Times New Roman", Times, serif; font-size: 13px; font-style: italic; fill: #000; }
.todo { background: #fff2a8; font-weight: bold; }
a { color: #000; }
"""


def n(value) -> str:
    return f"{value:,}"


def mb(value) -> str:
    return f"{value:,.0f} MB" if value >= 10 else f"{value:,.1f} MB"


def billions(value) -> str:
    return f"${value / 1e9:,.3f} billion"


def svg_box(x, y, w, h, lines, cls="bx", bold_first=True):
    out = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>']
    top = y + (h - 17 * len(lines)) / 2 + 13
    for i, line in enumerate(lines):
        style = "tb" if (i == 0 and bold_first) else "t"
        out.append(f'<text class="{style}" x="{x + w / 2}" y="{top + 17 * i}" text-anchor="middle">{line}</text>')
    return "".join(out)


def arrow(x1, y1, x2, y2, dashed=False):
    return f'<line class="ar{" dash" if dashed else ""}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#ah)"/>'


def architecture_svg() -> str:
    parts = ['<svg viewBox="0 0 960 330" xmlns="http://www.w3.org/2000/svg" role="img">',
             '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
             '<path d="M0,0 L10,5 L0,10 z"/></marker></defs>']
    for x, label in ((95, "SOURCES"), (305, "RAW (AS RECEIVED)"), (520, "PROCESSED (dev)"), (720, "SERVING (final)"), (885, "USE")):
        parts.append(f'<text class="tb" x="{x}" y="16" text-anchor="middle">{label}</text>')
    sources = [("SEC Company Facts", "XBRL JSON API"), ("SEC earnings releases", "8-K Exhibit 99.1 HTML"),
               ("Yahoo Finance prices", "daily chart JSON"), ("SEC Form 13F", "quarterly TSV in ZIP")]
    for i, (a, b) in enumerate(sources):
        parts.append(svg_box(10, 30 + 75 * i, 170, 58, [a, b], "fl"))
    parts.append(svg_box(215, 30, 180, 133, ["MongoDB Atlas", "companyfacts_concepts", "companyfacts_snapshots", "earnings_releases"]))
    parts.append(svg_box(215, 180, 180, 133, ["PostgreSQL dev (raw)", "stock_price_downloads", "raw_stock_prices", "f13_downloads, f13_*"]))
    parts.append(svg_box(430, 30, 180, 133, ["Python loaders", "quarterly_revenue", "quarterly_capex", "operating_income", "cash_flow, valuation", "product_kpis"]))
    parts.append(svg_box(430, 180, 180, 133, ["SQL views", "stock_prices_daily", "f13_filing_review", "f13_quarterly_changes"]))
    parts.append(svg_box(645, 30, 150, 283, ["final schema", "financial_metrics", "capital_expenditure", "company_financials", "valuation_quarterly", "valuation_annual", "product_kpis"], "fl"))
    parts.append(svg_box(830, 60, 120, 90, ["Dashboard", "(planned)"], "pl"))
    parts.append(svg_box(830, 180, 120, 110, ["Vector search", "on release", "text in", "MongoDB", "(planned)"], "pl"))
    parts += [arrow(180, 59, 215, 80), arrow(180, 134, 215, 120), arrow(180, 209, 215, 230), arrow(180, 284, 215, 270),
              arrow(395, 96, 430, 96), arrow(395, 246, 430, 246), arrow(610, 96, 645, 96), arrow(610, 246, 645, 246),
              arrow(795, 105, 830, 105, True)]
    parts.append("</svg>")
    return "".join(parts)


def page_one(d) -> str:
    video = (f'<a href="{VIDEO_LINK}">{VIDEO_LINK}</a>' if VIDEO_LINK
             else '<span class="todo">VIDEO LINK TO BE ADDED BEFORE SUBMISSION</span>')
    return f"""
<p class="eyebrow">95-815 DATA ENGINEERING · FINAL PROJECT · MILESTONE 2 · SECTION B2</p>
<p class="title">Stock Intelligence Dashboard for AI Infrastructure</p>
<p class="subtitle">How can retail investors easily compare AI infrastructure companies on their finances,
valuation, products and institutional investment?</p>
<div class="meta"><table>
<tr><th>Team</th><th>Members</th><th>Project manager</th><th>Meeting notes</th></tr>
<tr><td>Team 8</td><td>Mohd Danish Multani, Anav Batra, Akshay Iyer, Alan Zhou</td><td>Anav Batra</td>
<td><a href="{MEETING_NOTES}">Team Google Doc</a></td></tr>
<tr><th>Video demo</th><td colspan="3">{video}</td></tr></table></div>

<p class="fhead">The project in brief</p>
<p>We are building a dashboard that compares {d['companies']} AI infrastructure companies: Microsoft, Alphabet, Amazon, Meta and
NVIDIA. It tracks 13 KPIs (key performance indicators) in three groups: 7 financial, 3 valuation and 3 product metrics. It also
shows how big investment funds change their holdings. All data is public, from the SEC (the U.S. regulator that holds company
filings) and Yahoo Finance. It covers fiscal years {d['first_fy']} to {d['last_fy']}, which is {n(d['quarters'])} company quarters.</p>

<p class="fhead">The problem</p>
<p>Company results are spread across filings, press releases and price data. Each source uses its own format, and the companies
end their fiscal years in different months. An investor has to collect and line up these numbers by hand. Our pipeline does this
once, and every number links back to the filing it came from.</p>

<p class="fhead">Research questions</p>
<table>
<tr><th style="width:44%">Question</th><th style="width:24%">Source</th><th>Tables and views used</th></tr>
<tr><td><b>Q1.</b> How have revenue growth, operating margin and free cash flow changed over five years, and is rising capital
spending (CapEx) paying off?</td><td>SEC Company Facts (10-Q and 10-K filings)</td>
<td>final.company_financials_quarterly, built from dev.quarterly_revenue, quarterly_capex, quarterly_operating_income,
quarterly_operating_cash_flow</td></tr>
<tr><td><b>Q2.</b> How do valuations (P/E, EV/Revenue, FCF yield) compare with performance, and are funds buying the companies
that are improving?</td><td>SEC Company Facts, Yahoo Finance prices, SEC Form 13F</td>
<td>final.valuation_quarterly, final.valuation_annual (from dev.quarterly_valuation_inputs, dev.stock_prices_daily);
dev.f13_quarterly_changes</td></tr>
<tr><td><b>Q3.</b> How do product lines (Azure, AWS, Google Cloud, Data Center) grow compared with the whole company, and does
management commentary match the numbers?</td><td>SEC earnings releases (8-K, Exhibit 99.1), SEC Company Facts</td>
<td>MongoDB earnings_releases; final.product_kpis_quarterly (from dev.quarterly_product_kpis);
final.company_financials_quarterly</td></tr>
</table>

<div class="banner"><p><b>What changed since Milestone 1</b></p><ul>
<li>We now cover AI infrastructure only. Banking and its sources were dropped so that every data source is used.</li>
<li>We dropped the S3 data lake and the staging layer because of time. Raw data is kept unchanged inside the databases instead.</li>
<li>We use earnings releases instead of call transcripts. They are official SEC filings and contain the product numbers.</li>
</ul></div>

<p class="fhead">Who benefits</p>
<p>Retail investors, students, investment clubs and journalists get one free place to compare these companies, with every
number traceable to its source. We chose this topic because we share an interest in financial markets, and it uses every
stage of the course on real data.</p>
"""


def page_two(d) -> str:
    return f"""
<div class="page sectionhead"><p class="sectiontitle">1. DATA SOURCES, STORAGE AND KPIS</p></div>
<p class="cap">Table 1. Our four data sources (sizes measured in our databases).</p>
<table>
<tr><th style="width:15%">Source</th><th style="width:31%">What it contains</th><th style="width:12%">Format</th>
<th style="width:14%">Size</th><th style="width:19%">Stored in, and why</th><th>Answers</th></tr>
<tr><td><b>SEC Company Facts</b><br><a href="https://www.sec.gov/edgar/sec-api-documentation">SEC API</a></td>
<td><b>Standard numbers</b> each company tags in its 10-Q and 10-K filings: revenue, CapEx, profit, cash flow, EPS, shares, debt,
cash. Whole-company totals only, with no product breakdown.</td>
<td>Nested JSON (semi-structured)</td><td>{d['snapshots']} files, {mb(d['facts_mb'])}, {n(d['concepts'])} documents</td>
<td><b>MongoDB.</b> Nested, differs by company; loaders read only what they need.</td><td>Q1, Q2, Q3</td></tr>
<tr><td><b>SEC earnings releases</b><br><a href="https://www.sec.gov/edgar/search/">EDGAR</a></td>
<td><b>Press release text</b> filed each quarter (8-K, Exhibit 99.1). It has the product numbers that Company Facts lacks (AWS,
Azure, Google Cloud, Data Center) and management comments.</td>
<td>HTML text (unstructured)</td><td>{n(d['releases'])} documents, {mb(d['releases_mb'])}</td>
<td><b>MongoDB.</b> Whole documents; read for product numbers, later searched.</td><td>Q3</td></tr>
<tr><td><b>Yahoo Finance prices</b><br><a href="https://finance.yahoo.com">Yahoo chart API</a></td>
<td><b>Daily stock prices:</b> open, high, low, close and volume for each company.</td>
<td>JSON, one row per day (structured)</td><td>{n(d['price_raw'])} rows, {mb(d['price_mb'])}</td>
<td><b>PostgreSQL.</b> Rows and columns; joined to quarters in SQL.</td><td>Q2</td></tr>
<tr><td><b>SEC Form 13F</b><br><a href="https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets">SEC data sets</a></td>
<td><b>Fund holdings:</b> the stocks each large investment fund reports holding every quarter.</td>
<td>Tab-separated tables in ZIP files (structured)</td><td>{d['f13_windows']} files, {mb(d['f13_mb'])}, {n(d['f13_scanned'])} rows scanned</td>
<td><b>PostgreSQL.</b> Related tables joined by filing ID in SQL.</td><td>Q2</td></tr>
</table>

<p class="fhead">Where the data lives, and how raw and clean are kept apart</p>
<ul>
<li><b>Shared cloud:</b> PostgreSQL on AWS RDS and MongoDB Atlas, used by the whole team. The data is real and large
({n(d['f13_scanned'])} 13F rows scanned), and its messiness is kept, not cleaned before loading.</li>
<li><b>Raw:</b> stored exactly as received, with no keys or type rules that could reject a row. MongoDB keeps the original
documents. PostgreSQL keeps raw text rows (<i>dev.raw_stock_prices</i>, <i>dev.f13_infotable</i>) and the original ZIP files.
Bad rows are flagged, never deleted.</li>
<li><b>Clean:</b> tables in the <i>dev</i> schema with proper types, keys and checks (for example <i>dev.quarterly_revenue</i>).</li>
<li><b>Final:</b> views in the <i>final</i> schema. The dashboard reads only these.</li>
</ul>

<p class="cap">Table 2. Where each KPI comes from and where it is stored.</p>
<table>
<tr><th style="width:34%">KPI</th><th style="width:22%">Source</th><th style="width:22%">Clean table (dev)</th><th>Final view</th></tr>
<tr><td>1 Revenue, 2 Revenue growth, 3 CapEx, 4 CapEx growth, 5 CapEx as % of revenue, 6 Operating margin, 7 Free cash flow</td><td>SEC Company Facts</td><td>quarterly_revenue, quarterly_capex, quarterly_operating_income, quarterly_operating_cash_flow</td><td>company_financials_quarterly</td></tr>
<tr><td>8 P/E, 9 EV/Revenue, 10 FCF yield</td><td>SEC Company Facts + Yahoo Finance prices</td><td>quarterly_valuation_inputs</td><td>valuation_quarterly, valuation_annual</td></tr>
<tr><td>11 to 13 Product KPIs (AWS, Google Cloud, Azure, Meta apps, NVIDIA Data Center)</td><td>SEC earnings releases</td>
<td>quarterly_product_kpis</td><td>product_kpis_quarterly</td></tr>
<tr><td>Fund holdings (for Q2)</td><td>SEC Form 13F</td><td>f13 tables</td><td>f13_quarterly_changes</td></tr>
</table>
<figure>{architecture_svg()}
<figcaption><b>Figure 1.</b> How data moves: source, raw storage, clean tables, final views. Dashed boxes are planned.</figcaption></figure>
"""


def page_three(d) -> str:
    dec = d["f13_decisions"]
    s = d["val_status"]
    full_pairs = [p for p in d["f13_pairs"] if p[1] > 10000]
    revenue, capex, margin, ocf, fcf = d["msft"]
    return f"""
<div class="page sectionhead"><p class="sectiontitle">2. HOW WE TRANSFORM THE DATA, AND WHAT WAS HARD</p></div>
<p class="fhead">Transformation steps</p>
<ul>
<li><b>Find the quarters.</b> We use each company's real quarter dates, because Microsoft's year ends in June and NVIDIA's in late January.</li>
<li><b>Turn year-to-date totals into quarters.</b> Cash flow is reported year to date, so each quarter = this total minus the last one.</li>
<li><b>Adjust for stock splits.</b> Per-share numbers are restated for splits (NVIDIA 4:1 and 10:1, Amazon and Alphabet 20:1).</li>
<li><b>Read product numbers</b> from each press release, and keep the exact sentence or table row each number came from.</li>
<li><b>Calculate the KPIs in SQL views:</b> growth, margins, free cash flow, P/E, EV/Revenue and FCF yield.</li>
</ul>
<p>Each load runs as one transaction. Running the cash flow and product loads a second time changed nothing.</p>

<p class="cap">Table 3. Data quality log. Critical issues stop the load. Recoverable issues are fixed and recorded.</p>
<table>
<tr><th style="width:24%">Issue</th><th style="width:33%">What we found</th><th style="width:12%">Type</th><th>What we did</th></tr>
<tr><td>Same number in several filings</td><td>Each value is repeated in next year's filing</td><td>Recoverable</td>
<td>Use the filing for that period only.</td></tr>
<tr><td>Quarters must add up to the year</td><td>{d['ocf_mismatch']} mismatches in {d['company_years']} company-years</td><td>Critical</td>
<td>Load stops if a number is missing.</td></tr>
<tr><td>Rounding in Q4 figures</td><td>{d['release_q4']} values taken from press releases; largest gap ${n(d['revenue_max_recon'])}</td>
<td>Recoverable</td><td>Keep the published number and record the gap.</td></tr>
<tr><td>Stock splits</td><td>{n(d['split_pairs'])} EPS pairs checked against later filings</td><td>Critical</td>
<td>Load stops on a split-sized gap.</td></tr>
<tr><td>Missing shares or debt</td><td>{d['implied_shares']} Alphabet quarters with no share count; {d['meta_no_debt']} Meta quarters with no debt line</td>
<td>Recoverable</td><td>Shares = net income / EPS. No debt line = 0, labelled.</td></tr>
<tr><td>Bad or duplicate prices</td><td>{n(d['price_flagged'])} of {n(d['price_raw'])} rows flagged; {n(d['price_dup_rows'])} repeated rows</td>
<td>Recoverable</td><td>Flag, never delete. Keep one row per stock per day.</td></tr>
<tr><td>Fund filing amendments (13F)</td><td>{n(d['f13_filings'])} filings; {n(dec.get('superseded', 0))} replaced by later ones</td><td>Recoverable</td>
<td>Use only the latest valid filing.</td></tr>
<tr><td>Product number not in release</td><td>{n(d['prod_rows'] - d['prod_values'])} of {n(d['prod_rows'])} slots empty</td><td>Recoverable</td>
<td>Store as empty with a reason. Never guess.</td></tr>
</table>

<p class="fhead">Types, missing values and duplicates</p>
<ul>
<li><b>Types:</b> raw values stay as text so no row is lost; clean tables store dates, whole dollars and exact decimals so math is exact.</li>
<li><b>Missing values:</b> stored as empty (NULL) with a reason, not as zero, because zero would distort averages. The one exception: a filing with no debt line is stored as 0 and labelled.</li>
<li><b>Duplicates:</b> removed using keys (company and exact dates) and file fingerprints, so each quarter is counted once.</li>
</ul>
<p><b>Check:</b> Microsoft FY{d['last_fy']} Q4 from its filings gives revenue {billions(revenue)}, CapEx {billions(capex)} and free cash
flow {billions(fcf)}. Our final view shows the same numbers.</p>

<p class="fhead">Challenges</p>
<ul>
<li>Different fiscal year ends, so quarters are matched on exact dates.</li>
<li>Companies label the same number differently, and Alphabet and Meta have several share classes.</li>
<li>Product definitions change over time, so growth is only computed when the definition is the same.</li>
<li>13F files mix quarters; we now have {len(full_pairs)} full quarter-to-quarter comparisons for 2025.</li>
</ul>
"""


def page_four(d) -> str:
    c = d["prod_cover"]
    return f"""
<div class="page sectionhead"><p class="sectiontitle">3. PLAN FROM NOW TO DELIVERY</p></div>
<p class="cap">Table 4. Timeline.</p>
<table>
<tr><th style="width:30%">Step</th><th style="width:20%">Date</th><th>Status</th></tr>
<tr><td>M1 Proposal</td><td>Nov 9</td><td>Done</td></tr>
<tr><td>M2 Data, ingestion, cleaning</td><td>Nov 23</td><td>Done: 4 data sources loaded, all 13 KPIs built</td></tr>
<tr><td>Dashboard and answers to Q1 to Q3</td><td>Nov 24 to Dec 4</td><td>Next</td></tr>
<tr><td>Final presentation (15 minutes)</td><td>Dec 7, 1:00 to 4:00 pm</td><td>Every member presents</td></tr>
<tr><td>Final report and peer evaluation</td><td>After Dec 7</td><td>Planned</td></tr>
</table>

<p class="fhead">Next build 1: the dashboard</p>
<ul>
<li><b>Industry overview:</b> all 10 financial and valuation KPIs for the five companies, quarterly or yearly. Answers Q1 and Q2.</li>
<li><b>Company deep dive:</b> one company's trends from FY{d['first_fy']} to FY{d['last_fy']}.</li>
<li><b>Product performance:</b> AWS, Google Cloud, Azure, Meta apps and NVIDIA Data Center growth. Answers Q3.</li>
<li><b>Fund activity:</b> which companies funds bought or sold most in 2025. Answers Q2.</li>
</ul>

<p class="fhead">Next build 2: a vector database on SEC text</p>
<ul>
<li>Split the {n(d['releases'])} stored press releases into short passages.</li>
<li>Turn each passage into a vector (a list of numbers that captures its meaning) and index it with MongoDB Atlas Vector Search.</li>
<li>Then a question like "what did management say about AI demand?" finds the right passages, with links. This answers the
second part of Q3. Later, an assistant can answer questions using both the numbers and the text.</li>
</ul>

<p class="fhead">Other work</p>
<ul>
<li>Fill two product gaps from other SEC documents: Microsoft Cloud gross margin ({c.get(('MSFT', 'microsoft_cloud_gross_margin_pct'), 0)} of 28
quarters found) and Meta revenue per person ({c.get(('META', 'average_revenue_per_person_usd'), 0)} of 28).</li>
<li>Run the loaders on a schedule so the data stays up to date.</li>
<li>State limits clearly: our free cash flow can differ from a company's own figure, and 13F covers only large funds.</li>
</ul>

<p class="fhead">What the video shows</p>
<ul>
<li>Where the data comes from, with examples of each data source.</li>
<li>The loaders running, and the tables and collections they fill.</li>
<li>The quality issues we found, and the data after cleaning.</li>
</ul>
"""


def build() -> None:
    d = gather()
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>Team 8 Milestone 2</title><style>{CSS}</style></head><body>"
            f"{page_one(d)}{page_two(d)}{page_three(d)}{page_four(d)}</body></html>")
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_PDF.unlink(missing_ok=True)
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()], check=True, capture_output=True)
    print("wrote", OUT_HTML)
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    build()
