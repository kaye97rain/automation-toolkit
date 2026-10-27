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
│   ├── notify.py         email (SMTP) + Slack alerts
│   └── runner.py         wraps a job: timing, logging, failure alerts
├── projects/             one folder per automation
│   └── sales_report/     working example: CSV -> Excel summary report
├── templates/            starter used by new-project.ps1
├── data/input, output/   files going in and out
├── logs/                 one log file per project
├── tests/                pytest tests
├── .env.example          copy to .env and add your keys (never commit .env)
├── setup.ps1             one-time environment setup
└── new-project.ps1       create a new automation from the template
```

## Daily use

```powershell
cd C:\Users\Rain\automation-toolkit
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
$action = New-ScheduledTaskAction -Execute "C:\Users\Rain\automation-toolkit\.venv\Scripts\python.exe" `
  -Argument "-m projects.sales_report.main" -WorkingDirectory "C:\Users\Rain\automation-toolkit"
$trigger = New-ScheduledTaskTrigger -Daily -At 8am
Register-ScheduledTask -TaskName "Sales Report" -Action $action -Trigger $trigger
```

## Installed libraries

See `requirements.txt`. Each line has a comment explaining what the library is for.
