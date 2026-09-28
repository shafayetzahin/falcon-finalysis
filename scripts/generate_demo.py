"""Regenerate fictional input files and example reports from the shared application engines."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.demo import demo_company, DEMO_META
from core.financial_engine import analyze
from reports.excel_report import input_template, excel_report
from reports.pdf_report import pdf_report
from data.provenance import provenance_for_frame


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    frame = demo_company()
    a = analyze(frame)
    provenance = provenance_for_frame(frame, 'Fictional demo', 'Bundled Apex demonstration dataset')
    (root/'examples').mkdir(exist_ok=True)
    (root/'data/sample_company.xlsx').write_bytes(input_template(frame))
    frame.to_csv(root/'data/sample_company.csv', index=False)
    (root/'data/input_template.xlsx').write_bytes(input_template())
    (root/'examples/Apex_Falcon_Finalysis_Report.pdf').write_bytes(pdf_report(a, DEMO_META, provenance=provenance))
    (root/'examples/Apex_Falcon_Finalysis_Analysis.xlsx').write_bytes(excel_report(a, DEMO_META, provenance=provenance))
    print(f'Demo and reports generated. Health score: {a.health[-1].score}.')


if __name__ == '__main__':
    main()
