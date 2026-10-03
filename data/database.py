"""Transactional SQLite repository. Financial information never leaves the device."""
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parent / 'finsight.db'


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def audit(con: sqlite3.Connection, event: str, object_type: str,
          object_id: int | None, details: str = '') -> None:
    con.execute('INSERT INTO AuditEvents(event,object_type,object_id,details,created_at) VALUES(?,?,?,?,?)',
                (event, object_type, object_id, details, stamp()))


def connect(path: Path = DEFAULT_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS Companies(id INTEGER PRIMARY KEY, company_name TEXT NOT NULL,
      industry TEXT, currency TEXT, country TEXT, description TEXT);
    CREATE TABLE IF NOT EXISTS Projects(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL
      REFERENCES Companies(id), name TEXT NOT NULL, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS FinancialPeriods(id INTEGER PRIMARY KEY, project_id INTEGER
      REFERENCES Projects(id) ON DELETE CASCADE, year INTEGER, UNIQUE(project_id, year));
    CREATE TABLE IF NOT EXISTS FinancialStatements(period_id INTEGER PRIMARY KEY
      REFERENCES FinancialPeriods(id) ON DELETE CASCADE, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS CalculatedMetrics(project_id INTEGER REFERENCES Projects(id)
      ON DELETE CASCADE, year INTEGER, payload TEXT, PRIMARY KEY(project_id, year));
    CREATE TABLE IF NOT EXISTS ScenarioModels(id INTEGER PRIMARY KEY, project_id INTEGER
      REFERENCES Projects(id) ON DELETE CASCADE, name TEXT, assumptions TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS ReportHistory(id INTEGER PRIMARY KEY, project_id INTEGER
      REFERENCES Projects(id) ON DELETE CASCADE, format TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS DataProvenance(project_id INTEGER REFERENCES Projects(id)
      ON DELETE CASCADE, year INTEGER, field TEXT, source_type TEXT, source_reference TEXT,
      recorded_at TEXT, PRIMARY KEY(project_id, year, field));
    CREATE TABLE IF NOT EXISTS PortfolioProjects(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
      payload TEXT NOT NULL, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS CreditCases(id INTEGER PRIMARY KEY, business_name TEXT NOT NULL,
      payload TEXT NOT NULL, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS CreditDecisions(id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL
      REFERENCES CreditCases(id) ON DELETE CASCADE, decision TEXT NOT NULL, reviewer TEXT NOT NULL,
      rationale TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT);
    CREATE TABLE IF NOT EXISTS ImportMappings(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
      payload TEXT NOT NULL, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS AppSettings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS AuditEvents(id INTEGER PRIMARY KEY, event TEXT NOT NULL,
      object_type TEXT NOT NULL, object_id INTEGER, details TEXT, created_at TEXT NOT NULL);
    ''')
    return con


class Repository:
    """CRUD for local analyses with isolated project ownership."""
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        connect(path).close()

    def backup_bytes(self) -> bytes:
        """Take a consistent SQLite snapshot, including committed journal contents."""
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'backup.db'
            source = sqlite3.connect(self.path)
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            return target.read_bytes()

    def list_projects(self) -> list[dict]:
        with connect(self.path) as con:
            return [dict(r) for r in con.execute('SELECT p.*, c.company_name FROM Projects p '
                                                 'JOIN Companies c ON p.company_id=c.id ORDER BY updated_at DESC')]

    def save(self, meta: dict, frame: pd.DataFrame, name: str, project_id: int | None = None,
             metrics: pd.DataFrame | None = None, provenance: pd.DataFrame | None = None) -> int:
        from core.validation import validate
        errors = [i.message for i in validate(frame) if i.severity == 'ERROR']
        if errors:
            raise ValueError(' '.join(errors))
        if not name.strip() or not meta.get('company_name', '').strip():
            raise ValueError('Company and project names are required.')
        with connect(self.path) as con:
            values = [meta.get(k, '') for k in ['company_name', 'industry', 'currency', 'country', 'description']]
            if project_id is None:
                company = con.execute('INSERT INTO Companies(company_name,industry,currency,country,description) '
                                      'VALUES(?,?,?,?,?)', values).lastrowid
                project_id = con.execute('INSERT INTO Projects(company_id,name,created_at,updated_at) VALUES(?,?,?,?)',
                                         (company, name, stamp(), stamp())).lastrowid
            else:
                record = con.execute('SELECT company_id FROM Projects WHERE id=?', (project_id,)).fetchone()
                if not record:
                    raise ValueError('This project no longer exists. Save it as a new project.')
                con.execute('UPDATE Companies SET company_name=?,industry=?,currency=?,country=?,description=? WHERE id=?',
                            values + [record[0]])
                con.execute('UPDATE Projects SET name=?,updated_at=? WHERE id=?', (name, stamp(), project_id))
                con.execute('DELETE FROM FinancialPeriods WHERE project_id=?', (project_id,))
                con.execute('DELETE FROM CalculatedMetrics WHERE project_id=?', (project_id,))
                con.execute('DELETE FROM DataProvenance WHERE project_id=?', (project_id,))
            for row in json.loads(frame.to_json(orient='records')):
                year = int(row.pop('Year'))
                period = con.execute('INSERT INTO FinancialPeriods(project_id,year) VALUES(?,?)', (project_id, year)).lastrowid
                con.execute('INSERT INTO FinancialStatements VALUES(?,?)', (period, json.dumps(row, allow_nan=False)))
            if metrics is not None:
                for year, row in metrics.iterrows():
                    con.execute('INSERT INTO CalculatedMetrics VALUES(?,?,?)', (project_id, int(year), row.to_json()))
            if provenance is not None and not provenance.empty:
                for row in provenance.to_dict(orient='records'):
                    con.execute('INSERT OR REPLACE INTO DataProvenance VALUES(?,?,?,?,?,?)',
                                (project_id, int(row['Year']), str(row['Field']),
                                 str(row['Source Type']), str(row['Source Reference']), str(row['Recorded At'])))
            audit(con, 'SAVE', 'Financial project', int(project_id), name.strip())
            return int(project_id)

    def open(self, project_id: int) -> tuple[dict, pd.DataFrame]:
        with connect(self.path) as con:
            row = con.execute('SELECT c.*, p.name,p.updated_at,p.created_at FROM Companies c JOIN Projects p '
                              'ON c.id=p.company_id WHERE p.id=?', (project_id,)).fetchone()
            if row is None:
                raise ValueError('Project not found.')
            rows = con.execute('SELECT year,payload FROM FinancialPeriods p JOIN FinancialStatements s '
                               'ON p.id=s.period_id WHERE project_id=? ORDER BY year', (project_id,)).fetchall()
            return dict(row), pd.DataFrame([{'Year': r['year'], **json.loads(r['payload'])} for r in rows])

    def duplicate(self, project_id: int) -> int:
        meta, frame = self.open(project_id)
        return self.save(meta, frame, meta['name'] + ' (copy)', provenance=self.provenance(project_id))

    def provenance(self, project_id: int) -> pd.DataFrame:
        with connect(self.path) as con:
            rows = con.execute('SELECT year AS Year, field AS Field, source_type AS "Source Type", '
                               'source_reference AS "Source Reference", recorded_at AS "Recorded At" '
                               'FROM DataProvenance WHERE project_id=? ORDER BY year,field',
                               (project_id,)).fetchall()
            return pd.DataFrame([dict(row) for row in rows],
                                columns=['Year', 'Field', 'Source Type', 'Source Reference', 'Recorded At'])

    def rename(self, project_id: int, name: str) -> None:
        if not name.strip():
            raise ValueError('Enter a project name.')
        with connect(self.path) as con:
            con.execute('UPDATE Projects SET name=?,updated_at=? WHERE id=?', (name.strip(), stamp(), project_id))

    def delete(self, project_id: int) -> None:
        with connect(self.path) as con:
            row = con.execute('SELECT company_id FROM Projects WHERE id=?', (project_id,)).fetchone()
            con.execute('DELETE FROM Projects WHERE id=?', (project_id,))
            if row:
                con.execute('DELETE FROM Companies WHERE id=?', (row[0],))

    def save_scenario(self, project_id: int, name: str, assumptions: dict) -> None:
        with connect(self.path) as con:
            con.execute('INSERT INTO ScenarioModels(project_id,name,assumptions,created_at) VALUES(?,?,?,?)',
                        (project_id, name, json.dumps(assumptions, allow_nan=False), stamp()))

    def scenarios(self, project_id: int) -> list[dict]:
        with connect(self.path) as con:
            return [dict(r) for r in con.execute('SELECT * FROM ScenarioModels WHERE project_id=? ORDER BY id DESC', (project_id,))]

    def log_report(self, project_id: int, format_name: str) -> None:
        with connect(self.path) as con:
            con.execute('INSERT INTO ReportHistory(project_id,format,created_at) VALUES(?,?,?)', (project_id, format_name, stamp()))

    def list_portfolios(self) -> list[dict]:
        with connect(self.path) as con:
            return [dict(row) for row in con.execute(
                'SELECT id,name,created_at,updated_at FROM PortfolioProjects ORDER BY updated_at DESC')]

    def save_portfolio(self, name: str, payload: dict, portfolio_id: int | None = None) -> int:
        if not name.strip():
            raise ValueError('Enter a portfolio name.')
        encoded = json.dumps(payload, allow_nan=False)
        with connect(self.path) as con:
            if portfolio_id is None:
                portfolio_id = con.execute(
                    'INSERT INTO PortfolioProjects(name,payload,created_at,updated_at) VALUES(?,?,?,?)',
                    (name.strip(), encoded, stamp(), stamp())).lastrowid
            else:
                exists = con.execute('SELECT id FROM PortfolioProjects WHERE id=?',
                                     (portfolio_id,)).fetchone()
                if not exists:
                    raise ValueError('This saved portfolio no longer exists.')
                con.execute('UPDATE PortfolioProjects SET name=?,payload=?,updated_at=? WHERE id=?',
                            (name.strip(), encoded, stamp(), portfolio_id))
            audit(con, 'SAVE', 'Portfolio', int(portfolio_id), name.strip())
            return int(portfolio_id)

    def open_portfolio(self, portfolio_id: int) -> tuple[dict, dict]:
        with connect(self.path) as con:
            row = con.execute('SELECT * FROM PortfolioProjects WHERE id=?',
                              (portfolio_id,)).fetchone()
            if row is None:
                raise ValueError('Saved portfolio not found.')
            meta = {key: row[key] for key in ['id', 'name', 'created_at', 'updated_at']}
            return meta, json.loads(row['payload'])

    def rename_portfolio(self, portfolio_id: int, name: str) -> None:
        if not name.strip():
            raise ValueError('Enter a portfolio name.')
        with connect(self.path) as con:
            con.execute('UPDATE PortfolioProjects SET name=?,updated_at=? WHERE id=?',
                        (name.strip(), stamp(), portfolio_id))

    def duplicate_portfolio(self, portfolio_id: int) -> int:
        meta, payload = self.open_portfolio(portfolio_id)
        return self.save_portfolio(meta['name'] + ' (copy)', payload)

    def delete_portfolio(self, portfolio_id: int) -> None:
        with connect(self.path) as con:
            con.execute('DELETE FROM PortfolioProjects WHERE id=?', (portfolio_id,))

    def list_credit_cases(self) -> list[dict]:
        with connect(self.path) as con:
            return [dict(row) for row in con.execute(
                'SELECT id,business_name,created_at,updated_at FROM CreditCases ORDER BY updated_at DESC')]

    def save_credit_case(self, business_name: str, payload: dict,
                         case_id: int | None = None) -> int:
        if not business_name.strip():
            raise ValueError('Enter the business name.')
        encoded = json.dumps(payload, allow_nan=False)
        with connect(self.path) as con:
            if case_id is None:
                case_id = con.execute(
                    'INSERT INTO CreditCases(business_name,payload,created_at,updated_at) VALUES(?,?,?,?)',
                    (business_name.strip(), encoded, stamp(), stamp())).lastrowid
            else:
                exists = con.execute('SELECT id FROM CreditCases WHERE id=?', (case_id,)).fetchone()
                if not exists:
                    raise ValueError('This credit case no longer exists.')
                con.execute('UPDATE CreditCases SET business_name=?,payload=?,updated_at=? WHERE id=?',
                            (business_name.strip(), encoded, stamp(), case_id))
            audit(con, 'SAVE', 'Credit case', int(case_id), business_name.strip())
            return int(case_id)

    def open_credit_case(self, case_id: int) -> tuple[dict, dict]:
        with connect(self.path) as con:
            row = con.execute('SELECT * FROM CreditCases WHERE id=?', (case_id,)).fetchone()
            if row is None:
                raise ValueError('Credit case not found.')
            meta = {key: row[key] for key in ['id', 'business_name', 'created_at', 'updated_at']}
            return meta, json.loads(row['payload'])

    def save_credit_decision(self, case_id: int, decision: str, reviewer: str,
                             rationale: str, payload: dict) -> int:
        if decision not in {'Approve', 'Modify', 'Decline'}:
            raise ValueError('Choose Approve, Modify or Decline.')
        if not reviewer.strip() or not rationale.strip():
            raise ValueError('Reviewer and rationale are required.')
        with connect(self.path) as con:
            if not con.execute('SELECT id FROM CreditCases WHERE id=?', (case_id,)).fetchone():
                raise ValueError('Save the credit case before recording a decision.')
            decision_id = con.execute(
                'INSERT INTO CreditDecisions(case_id,decision,reviewer,rationale,payload,created_at) '
                'VALUES(?,?,?,?,?,?)',
                (case_id, decision, reviewer.strip(), rationale.strip(),
                 json.dumps(payload, allow_nan=False), stamp())).lastrowid
            audit(con, 'HUMAN_DECISION', 'Credit case', case_id,
                  f'{decision} · reviewer {reviewer.strip()} · decision #{decision_id}')
            return int(decision_id)

    def credit_decisions(self, case_id: int) -> list[dict]:
        with connect(self.path) as con:
            return [dict(row) for row in con.execute(
                'SELECT * FROM CreditDecisions WHERE case_id=? ORDER BY id DESC', (case_id,))]

    def list_import_mappings(self) -> list[dict]:
        with connect(self.path) as con:
            return [dict(row) for row in con.execute(
                'SELECT id,name,created_at,updated_at FROM ImportMappings ORDER BY name')]

    def save_import_mapping(self, name: str, mapping: dict[str, str]) -> int:
        if not name.strip() or not mapping:
            raise ValueError('Enter a mapping name and map at least one column.')
        encoded = json.dumps(mapping, sort_keys=True)
        with connect(self.path) as con:
            existing = con.execute('SELECT id FROM ImportMappings WHERE name=?',
                                   (name.strip(),)).fetchone()
            if existing:
                con.execute('UPDATE ImportMappings SET payload=?,updated_at=? WHERE id=?',
                            (encoded, stamp(), existing['id']))
                return int(existing['id'])
            return int(con.execute(
                'INSERT INTO ImportMappings(name,payload,created_at,updated_at) VALUES(?,?,?,?)',
                (name.strip(), encoded, stamp(), stamp())).lastrowid)

    def open_import_mapping(self, mapping_id: int) -> dict[str, str]:
        with connect(self.path) as con:
            row = con.execute('SELECT payload FROM ImportMappings WHERE id=?',
                              (mapping_id,)).fetchone()
            if row is None:
                raise ValueError('Import mapping not found.')
            return json.loads(row['payload'])

    def settings(self) -> dict[str, str]:
        with connect(self.path) as con:
            return {row['key']: row['value'] for row in con.execute(
                'SELECT key,value FROM AppSettings')}

    def save_settings(self, values: dict[str, str]) -> None:
        with connect(self.path) as con:
            for key, value in values.items():
                con.execute('INSERT INTO AppSettings(key,value,updated_at) VALUES(?,?,?) '
                            'ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
                            (str(key), str(value), stamp()))
            audit(con, 'UPDATE', 'Local settings', None, ', '.join(sorted(values)))

    def audit_events(self, limit: int = 250) -> list[dict]:
        with connect(self.path) as con:
            return [dict(row) for row in con.execute(
                'SELECT * FROM AuditEvents ORDER BY id DESC LIMIT ?', (max(1, int(limit)),))]
