# My Daily Jobs

Local app for Yusuf Hameed: business, systems, data, and QA analyst roles from **Indeed, Dice, Monster, and CareerBuilder**. Last 7 days, remote or within 30 miles of Columbia, Maryland, Easy Apply or 1-click.

## Run

```powershell
cd C:\Users\55024\.local\ai-governance-dashboard\maryiam-daily-jobs
& "C:\Users\55024\AppData\Local\Programs\Python\Python312\python.exe" server.py
```

Open **http://127.0.0.1:8791/**

First refresh runs a Playwright scrape of those five boards (`business analyst` + Remote + USA). Click **Refresh pool** to scrape again.

## Notes

- Apply opens the board listing; it does not auto-submit.
- Dead “no longer available” pages are dropped after link checks.
- LinkedIn may return fewer results when logged out (auth wall).
