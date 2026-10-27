# Automation Toolkit

A reusable starting point for business automations in Python.

## Layout

```
automation-toolkit/
├── core/                 shared helpers every project reuses
│   ├── config.py         paths + settings from .env
│   ├── logger.py         console + rotating log files in logs/
│   ├── http.py           API session with retries, pagination helper
│   ├── excel.py          DataFrames -> formatted Excel workbooks
│   ├── db.py             database connection (SQLite by default)
│   ├── formatting.py     $ amounts, dates and numbers for people
│   ├── html_email.py     tables, bullets and layout for report emails
│   ├── notify.py         email (SMTP) + Slack alerts
│   └── runner.py         wraps a job: timing, logging, failure alerts
├── projects/             one folder per automation
│   ├── sales_report/       working example: CSV -> Excel summary report
│   ├── weekly_sales_email/ emails the sales report with a KPI summary
│   ├── report_summarizer/  summarizes ANY Excel/CSV in data/input and emails it
│   │                       (business rules per report in reports.yaml)
│   └── invoice_processor/  PDF invoices -> extracted, validated, saved to a database,
│                           filed to processed/ or needs_review/, register + email
├── templates/            starter used by new-project.ps1
├── data/input, output/   files going in and out
├── logs/                 one log file per project
├── tests/                pytest tests
├── .env.example          copy to .env and add your keys (never commit .env)
├── setup.ps1             one-time environment setup
├── new-project.ps1       create a new automation from the template
└── schedule-project.ps1  run a project weekly via Task Scheduler
```

## Daily use

```powershell
cd automation-toolkit                        # wherever you cloned it
.\setup.ps1                                  # first time only
.\.venv\Scripts\Activate.ps1                 # activate the environment

python -m projects.sales_report.main         # run the example
.\new-project.ps1 invoice_processor          # start a new automation
python -m projects.invoice_processor.main    # run it
pytest                                       # run tests
```

If PowerShell blocks scripts, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Every project follows the same pattern

`extract()` get data → `transform()` apply business rules → `load()` act / report,
wrapped in `run_job()` so every run is logged and failures can alert you on Slack.

## Scheduling a job (Windows Task Scheduler)

```powershell
.\schedule-project.ps1 report_summarizer -Day Monday -At 8am     # schedule weekly
Start-ScheduledTask "Automation - report_summarizer"             # test it now
Unregister-ScheduledTask "Automation - report_summarizer"        # remove it
```

The task runs hidden in the background; if the PC is off at the scheduled time it runs at next startup.
Check `logs\<project>.log` to see what happened.

## Installed libraries

See `requirements.txt`. Each line has a comment explaining what the library is for.
