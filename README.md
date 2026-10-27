# RADYNTA

Logistics AEO agency website + internal AI Visibility Monitor, in one small Flask app.

- **Public website** (`/`): home, services + pricing, 3 service pages, 5 industry pages, about, resources (2 articles), contact, audit request, privacy, terms, `sitemap.xml`, `robots.txt`. Enquiry forms save to the database, with CSRF protection, a honeypot, a minimum time to submit and rate limiting.
- **Audit engine** (`radynta/audit/`): an SSRF-safe, polite crawler, technical/content/trust/conversion checks, scoring on the internal 100-point diagnostic, findings, and draft recommendations.
- **AI visibility** (`radynta/visibility/`): buyer-question library, provider adapters (Perplexity API, OpenAI web search API) and manual CSV import for answers copied from consumer apps. Mentions and citations are tracked separately, and rates use **valid runs only**.
- **Monitor** (`/monitor`, login required): clients, enquiries, audits, recommendation review/approval, AI batches, HTML report, CSV exports.

Stack: Python 3.11+ · Flask · SQLite · requests · BeautifulSoup · pytest. There's no JavaScript build step and no paid services.

## Run locally (Windows PowerShell)

```powershell
cd RADYNTA
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then edit .env
flask --app radynta init-db
flask --app radynta create-user you@radynta.com
flask --app radynta seed-sample # optional: labelled SYNTHETIC demo client + report
flask --app radynta run --debug
```

Open http://127.0.0.1:5000/ for the site and http://127.0.0.1:5000/monitor/ for the monitor.
On macOS or Linux, use `source venv/bin/activate` and `cp`.

## Run the tests

```
pytest
```

There are 96 tests covering: SSRF blocking (private IPs, cloud metadata, redirects to private hosts, ports, credentials), crawl limits, robots.txt, page parsing, scoring including unmeasured dimensions, mention vs citation, ambiguous aliases, metric denominators, provider parsing and failures, missing-credential errors, forms (validation, CSRF, honeypot, rate limit), canonical redirects, SEO tags, login, client separation, report sections and approval rules.

## Delivering an audit for a real prospect

```powershell
# 1. Describe the client (copy data/sample_client.json, fill in real values, delete the _comment line)
flask --app radynta add-client data\clients\acme.json
flask --app radynta import-prompts acme data\clients\acme-prompts.csv

# 2. Crawl their public website (25 pages by default, 1 s between requests)
flask --app radynta run-audit acme

# 3a. AI answers via API (needs a key in .env)
flask --app radynta check-provider perplexity --live
flask --app radynta run-visibility acme --provider perplexity --market India
# 3b. ...and/or answers copied by hand from ChatGPT / Gemini / Google AI Overviews
#     (fill data/manual_responses_template.csv; platform e.g. chatgpt-web)
flask --app radynta import-responses acme captures.csv

# 4. Fold the AI data into the score
flask --app radynta rescore-audit acme

# 5. In /monitor: review every recommendation (approve/reject), then "Approve report"
# 6. Export (refuses unapproved reports unless --allow-draft, which watermarks DRAFT)
flask --app radynta export-report acme
```

The output goes to `reports/`: one self-contained HTML report plus `findings`, `recommendations`, `pages` and `visibility` CSVs. To make a PDF, open the HTML in Chrome and use **Print → Save as PDF**. The A4 print styles are built in.

## Configuration

Everything is set through environment variables or `.env` (see `.env.example`). Key points:

| Variable | Purpose |
|---|---|
| `RADYNTA_ENV=production` | Enables secure cookies, HSTS and proxy headers; **requires** `RADYNTA_SECRET_KEY` (32+ chars) |
| `CONTACT_EMAIL`, `CONTACT_PHONE` | Shown on the site only when set. Use real, monitored details |
| `SMTP_*`, `ENQUIRY_NOTIFY_TO` | Optional enquiry alert emails. Without them, enquiries are only stored (and the thank-you page says no email is sent) |
| `PERPLEXITY_API_KEY` | Enables `--provider perplexity` |
| `OPENAI_API_KEY` + `OPENAI_MODEL` | Enables `--provider openai` (choose a model with web-search support on your account) |

## Known limitations (honest list)

- **The provider adapters have not been run against a live API yet.** They follow the documented request and response formats and are tested with mocked responses. Run `check-provider <name> --live` with a real key before relying on them.
- API answers can differ from what users see in the ChatGPT or Gemini apps. Reports label the collection method for each platform. Manual capture is the ToS-safe way to measure consumer apps.
- The crawler doesn't run JavaScript. Content that only appears after client-side rendering isn't seen.
- Heuristic checks (address, phone, forms, CTAs) can miss things or flag false positives. Every recommendation needs human approval before delivery.
- Rate limiting is in-memory per process. That's fine for one small server; use a shared store if you scale out.
- DNS-rebinding TOCTOU risk in the crawler is documented in `safe_fetch.py`. In production, run on a host whose egress firewall blocks private ranges.
- The audit button in the monitor runs the crawl in a background thread. That's fine for one operator. Move to a job queue only if usage grows.
- The privacy policy and terms are drafts. **Have a lawyer review them before launch.**

## Layout

```
radynta/            app package
  audit/            safe_fetch, website_audit (crawler + parser), scoring, recommendations, pipeline
  visibility/       providers/, response_parser, metrics, runner
  reports/          report_builder (HTML context + CSV)
  site/             public routes + content.py (all website copy)
  monitor/          internal routes
  templates/        site/, monitor/, reports/, partials/
  static/           css (design tokens), img
data/               prompt library, client template, manual-capture template, synthetic sample answers
docs/               deployment, methodology, strategy, sample report
tests/              pytest suite
```

See `docs/DEPLOYMENT.md`, `docs/AUDIT_METHODOLOGY.md` and `docs/STRATEGY.md`.
