"""Professional paginated financial analysis report with vector charts and tables."""
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether, Image
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.lineplots import LinePlot
from core.config import DISCLAIMER, AVERAGE_POLICY, INCOME, BALANCE, CASH_FLOW, GUIDELINE
from core.ratio_engine import METRICS, BY_NAME
from core.scenario_engine import baseline, model, Scenario, ASSUMPTIONS

NAVY = colors.HexColor('#173859')
TEAL = colors.HexColor('#008C95')
MUTED = colors.HexColor('#587089')
ACTIVE_LOGO = Path(__file__).resolve().parents[1] / 'assets' / 'logo-active.png'


def pdf_report(a, meta: dict, scenario: dict | None = None,
               provenance: pd.DataFrame | None = None) -> bytes:
    """Build an A4 report; split long history into readable five-year table panels."""
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=42, leftMargin=42,
                            topMargin=48, bottomMargin=48, title='Falcon Finalysis - '+meta['company_name'],
                            author='Falcon Finalysis')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CoverTitle', fontName='Helvetica-Bold', fontSize=38, leading=43, textColor=NAVY, spaceAfter=22))
    styles.add(ParagraphStyle(name='SectionTitle', fontName='Helvetica-Bold', fontSize=23, leading=28, textColor=NAVY, spaceAfter=18))
    styles.add(ParagraphStyle(name='BodyFS', fontSize=9.5, leading=14, textColor=NAVY, spaceAfter=9))
    styles.add(ParagraphStyle(name='SmallFS', fontSize=8, leading=11, textColor=MUTED, spaceAfter=8))
    styles.add(ParagraphStyle(name='CellFS', fontSize=8, leading=10, textColor=NAVY))
    styles.add(ParagraphStyle(name='FormulaFS', fontSize=8, leading=10, textColor=MUTED, spaceAfter=4))
    story = []

    def p(text, style='BodyFS'):
        # PDF uses currency codes. Normalize typographic symbols to reliable base-font equivalents.
        text = str(text).replace('→', 'to').replace('×', 'x').replace('–', '-').replace('−', '-').replace('•', '-')
        return Paragraph(escape(text), styles[style])

    def section(title, subtitle=''):
        story.append(PageBreak())
        story.append(p(title, 'SectionTitle'))
        if subtitle:
            story.append(p(subtitle, 'SmallFS'))

    def report_table(df: pd.DataFrame, money=False, percentage=False, mixed=False):
        for offset in range(0, len(df.columns), 5):
            panel = df.iloc[:, offset:offset+5]
            rows = [[p('Metric', 'CellFS')] + [p(str(c), 'CellFS') for c in panel.columns]]
            for name, values in panel.iterrows():
                line = [p(name, 'CellFS')]
                for value in values:
                    if isinstance(value, (int, float)):
                        if pd.isna(value):
                            text = 'N/A'
                        elif percentage or mixed and name in BY_NAME and BY_NAME[name].unit == '%':
                            text = f'{value:.1%}'
                        elif money:
                            text = f'{value/1e6:,.2f}'
                        else:
                            text = f'{value:,.2f}'
                    else:
                        text = 'N/A' if pd.isna(value) else str(value)
                    line.append(p(text, 'CellFS'))
                rows.append(line)
            widths = [165] + [(511-165)/len(panel.columns)]*len(panel.columns)
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DCECEF')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F2F6FA'), colors.white]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5), ('LINEBELOW', (0, 0), (-1, 0), .8, TEAL),
            ]))
            story.extend([table, Spacer(1, 14)])

    def plot(df, columns, title, scale=1e6, suffix='millions'):
        d = Drawing(505, 195)
        d.add(String(5, 182, title, fontName='Helvetica-Bold', fontSize=11, fillColor=NAVY))
        chart = LinePlot()
        chart.x, chart.y, chart.width, chart.height = 48, 42, 430, 120
        series, labels = [], []
        for col in columns:
            # Omit incomplete series instead of joining across missing observations.
            if df[col].notna().all():
                series.append([(int(year), float(val)/scale) for year, val in df[col].items()])
                labels.append(col)
        if not series:
            return p('Chart unavailable: incomplete observations.', 'SmallFS')
        chart.data = series
        chart.xValueAxis.valueSteps = [int(v) for v in df.index]
        chart.xValueAxis.labelTextFormat = lambda v: str(int(v))
        chart.yValueAxis.labelTextFormat = lambda v: f'{v:,.1f}'
        chart.xValueAxis.labels.fontSize = 8
        chart.yValueAxis.labels.fontSize = 8
        for i, label in enumerate(labels):
            color = [TEAL, NAVY, colors.HexColor('#C3974A')][i % 3]
            chart.lines[i].strokeColor = color
            chart.lines[i].strokeWidth = 2
            d.add(String(48+i*155, 16, label, fontSize=8, fillColor=color))
        d.add(String(48, 166, suffix, fontSize=8, fillColor=MUTED))
        d.add(chart)
        return d

    logo = Image(str(ACTIVE_LOGO), width=330, height=188)
    logo.hAlign = 'LEFT'
    story += [logo, Spacer(1, 4), p('Financial Analytics & Decision Support', 'SectionTitle'),
              Spacer(1, 42), p(meta['company_name'], 'SectionTitle'),
              p(f'FY{a.statements.index.min()} - FY{a.statements.index.max()} | {meta["currency"]} | {meta.get("industry", "")}'),
              p('Financial analysis report', 'SectionTitle'),
              p('Generated '+datetime.now(timezone.utc).strftime('%d/%m/%Y, %H:%M UTC'), 'SmallFS'),
              Spacer(1, 36), p('From Financial Data to Financial Insight'),
              p('Local, deterministic analysis. This report is a snapshot of the supplied data and assumptions.', 'SmallFS'),
              p(DISCLAIMER, 'SmallFS')]
    section('Executive summary', 'All monetary statement tables use millions of '+meta['currency']+'. Ratios are labelled separately.')
    for heading in ['Financial Overview', 'Profitability', 'Liquidity', 'Solvency', 'Efficiency', 'Cash Flow', 'Growth']:
        story.append(KeepTogether([p(heading, 'Heading3'), p(a.summary[heading])]))
    section('Financial health & highlights')
    health = a.health[-1]
    story.append(p(f'Falcon Finalysis Financial Health Score: {health.score if health.score is not None else "N/A"} / 100 - {health.label}', 'Heading2'))
    story.append(p(f'Weighted data coverage: {health.coverage:.0%}. {GUIDELINE} This is not an industry-standard credit score.'))
    report_table(health.categories.set_index('Category')[['Weight', 'Score / 100', 'Coverage']])
    story.append(p('Coverage is shown as a decimal fraction in the table. Scores are normalized over available weights; overall scores need at least 75% coverage and evidence in every category.', 'SmallFS'))
    story.append(plot(a.combined, ['Revenue', 'Net Income', 'Operating Cash Flow'], 'Revenue, earnings and cash generation'))
    section('Income statement analysis', 'Reported amounts in millions of '+meta['currency'])
    report_table(a.statements[INCOME].T, money=True)
    story.append(plot(a.ratios, ['Gross Profit Margin', 'Operating Margin', 'Net Profit Margin'], 'Profitability margins', .01, 'percent'))
    section('Balance sheet analysis', 'Reported amounts in millions of '+meta['currency'])
    report_table(a.statements[BALANCE].T, money=True)
    story.append(plot(a.statements, ['Total Assets', 'Total Liabilities', 'Shareholders Equity'], 'Assets and funding'))
    section('Cash flow analysis', 'Reported amounts in millions of '+meta['currency'])
    report_table(a.combined[CASH_FLOW+['Free Cash Flow']].T, money=True)
    story.append(p(a.summary['Cash Flow']))
    story.append(plot(a.combined, ['Operating Cash Flow', 'Free Cash Flow'], 'Cash generation after investment'))
    section('Ratio analysis', AVERAGE_POLICY)
    for category in list(dict.fromkeys(m.category for m in METRICS)):
        if category == 'Solvency':
            section('Ratio analysis: funding & cash', 'Monetary metrics use full currency units; percentage ratios are formatted as percentages.')
        story.append(p(category, 'Heading3'))
        names = [m.name for m in METRICS if m.category == category]
        report_table(a.ratios[names].T, mixed=True)
    section('DuPont analysis', 'Net profit margin x asset turnover x equity multiplier = ROE. Returns and margins below are decimal ratios.')
    report_table(a.dupont.T)
    from core.dupont_engine import attribution
    effects = attribution(a.dupont)*100
    report_table(effects.to_frame('ROE change (pp)'))
    story.append(p('The attribution averages all six factor replacement orders. Contributions sum to the latest ROE change; they are arithmetic, not causal.', 'SmallFS'))
    section('Working capital analysis')
    report_table(a.ratios[['Inventory Days', 'Receivable Days', 'Payable Days', 'Cash Conversion Cycle', 'Current Ratio']].T)
    story.append(p('Cash conversion cycle = inventory days + receivable days - payable days. Days use average balances.'))
    story.append(plot(a.ratios, ['Inventory Days', 'Receivable Days', 'Cash Conversion Cycle'], 'Operating cash cycle', 1, 'days'))
    section('Growth analysis')
    report_table(a.growth.T, percentage=True)
    report_table(a.cagr.to_frame('CAGR'), percentage=True)
    section('Common-size analysis', 'Income statement / revenue; balance sheet / total assets.')
    story.append(p('Income statement common size', 'Heading3'))
    report_table(a.vertical[['COGS', 'Operating Expenses', 'EBIT', 'Net Income']].T, percentage=True)
    story.append(p('Balance sheet common size', 'Heading3'))
    report_table(a.vertical[BALANCE].T, percentage=True)
    section('Strengths, risks & monitoring', 'Evidence uses native metric units. Values marked as percentages in the ratio section are decimal ratios here.')
    for label, severities in [('Strengths', ['POSITIVE']), ('Risks', ['HIGH RISK', 'WARNING']), ('Areas to monitor', ['WATCH', 'INFO'])]:
        story.append(p(label, 'Heading2'))
        found = [f for f in a.flags if f.severity in severities]
        if not found:
            story.append(p('No available metric triggered a configured rule.'))
        for flag in found:
            story.append(KeepTogether([p(flag.severity+' - '+flag.title, 'Heading3'), p(flag.explanation),
                                       p(flag.metric+': '+flag.trend, 'SmallFS'), p('Investigate: '+flag.questions, 'SmallFS')]))
    section('Scenario analysis', 'Base case and active scenario are projected operating models, not historical cash flow.')
    story.append(p(ASSUMPTIONS, 'SmallFS'))
    try:
        base = baseline(a.statements.iloc[-1])
        case = Scenario(**scenario) if scenario else base
        result = pd.DataFrame({'Base case': model(a.statements.iloc[-1], base), 'Scenario': model(a.statements.iloc[-1], case)})
        story.append(p('Monetary outputs below are in full currency units; ROA, ROE and Net Margin are decimal ratios.', 'SmallFS'))
        report_table(result)
        section('Scenario assumptions', 'Rates below use decimals (0.15 = 15%); days are in days; monetary values use full currency units.')
        report_table(pd.DataFrame({'Base': base.to_dict(), 'Scenario': case.to_dict()}))
        story.append(p(ASSUMPTIONS))
    except ValueError as exc:
        story.append(p(str(exc)))
    if isinstance(provenance, pd.DataFrame) and not provenance.empty:
        section('Appendix: data sources', 'Recorded sources for imported or manually entered values.')
        source_summary = (provenance.groupby(['Source Type', 'Source Reference'], dropna=False)
                          .agg(Values=('Field', 'count'), First_Year=('Year', 'min'), Last_Year=('Year', 'max'))
                          .reset_index())
        source_summary['Source'] = source_summary['Source Type'] + ' - ' + source_summary['Source Reference']
        source_summary['First_Year'] = source_summary['First_Year'].astype(int).astype(str)
        source_summary['Last_Year'] = source_summary['Last_Year'].astype(int).astype(str)
        source_summary = source_summary.set_index('Source')[['Values', 'First_Year', 'Last_Year']]
        report_table(source_summary)
    section('Appendix: data quality & methodology')
    for issue in a.issues:
        story.append(p(f'{issue.severity} {issue.year}: {issue.message}'))
    if not a.issues:
        story.append(p('All available accounting reconciliation checks passed. This is not an audit.'))
    story += [p(AVERAGE_POLICY), p('No source values are altered. N/A denotes missing dependencies or nonpositive denominators. Preferred dividends must be explicitly supplied for EPS; ending shares and weighted-average shares are distinct.'),
              p('Growth uses positive prior bases; CAGR uses positive endpoints and elapsed years. Health score interpolation and risk thresholds are generic. Accounting conventions, seasonality and industry differences can limit comparisons.'),
              ]
    section('Formula reference', 'Every conventional ratio requires a positive denominator. Missing dependencies remain N/A.')
    for metric in METRICS:
        story.append(p(metric.name+': '+metric.formula, 'FormulaFS'))
    story.append(p(DISCLAIMER, 'SmallFS'))

    def footer(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(1)
        canvas.line(42, height-28, width-42, height-28)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(42, 25, 'Generated by Falcon Finalysis | Financial Analytics & Decision Support Platform')
        canvas.drawRightString(width-42, 25, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
