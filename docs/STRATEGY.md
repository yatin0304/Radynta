# Go-to-market notes (first 90 days)

These are working assumptions to validate, not proven facts.

## First segment to target

**Recommendation: freight forwarders and customs brokers in Mumbai / Nhava Sheva, with mid-size 3PLs in Maharashtra second.**

Why:
- Almost all of them already have a website, so there is something to audit. Many small transporters don't have one yet.
- Each enquiry is worth a lot (trade-lane contracts), so a ₹7,500–₹9,999 audit is easy to justify.
- Their buyers (importers, exporters, procurement teams) research online and increasingly ask AI assistants for shortlists.
- The gaps are concrete and easy to show: trade lanes not named, modes lumped together, .com/.in duplication.

Small road transporters remain a good **second wave** once there is a cheaper, faster "basic website + listing" offer. Many of them need a website before an audit is useful.

## Pricing (proposed, to validate)

| Package | Price | Scope |
|---|---|---|
| Launch Audit | ₹7,500–₹9,999 one-time | 20 questions, 2 platforms, 3 competitors, 5 pages in depth, report, walkthrough |
| Visibility Growth | ₹24,999/month | 30 questions monthly, 4 page improvements, 2 content briefs, monthly report |
| Visibility Intelligence | ₹39,999/month | 60 questions, expanded competitors, 6 page improvements, 4 briefs, issue tracking |

Excluded unless agreed in writing: ads, large-scale content production, custom development, third-party listing fees. Prices are shown excluding GST.

To validate: after five sales calls, record which price was accepted, which was rejected and the objection given. Don't discount the first audit below ₹7,500 without a referral or case-study agreement in writing.

**Effort tracking:** log hours per audit from the first one. The audit engine should cut a Launch Audit to roughly half a day of analyst time. Check this against the actual numbers.

## 90-day plan, mapped to this codebase

| Days | Business | Software (status) |
|---|---|---|
| 1–30 | Launch site; research 30–50 forwarders/3PLs; run **free internal** audits on 5 public sites to calibrate (don't publish them); close the first paid audit | Site ✅, audit engine ✅, sample report ✅, enquiry capture ✅ |
| 31–60 | Deliver first audit; offer the retainer; approach 2–3 web agencies for white-label partnerships | Historical storage ✅, API collection (needs keys and a live test) ⚠️, regression tests ✅ |
| 61–90 | Standardise onboarding; aim for 2–3 paying clients; decide whether SaaS is justified | Dashboard is basic and enough; build more only for needs clients actually repeat |

## Prospect research workflow (no CRM yet)

Use the monitor's enquiry list for inbound leads. For outbound, keep a simple sheet with these columns: company, website, segment, contact, prospect score (1–5), last contact, next action, status, notes. Build a tracker into the app only after you have 20+ live prospects.

## Content plan (publish one substantial piece every 2–3 weeks)

1. ✅ How we measure AI visibility for logistics companies
2. ✅ A technical checklist for logistics websites
3. Freight forwarding SEO: how importers and exporters actually search for forwarders
4. Route pages that work, and when they backfire (with good and bad structure examples)
5. Warehousing and 3PL lead generation: what facility pages should contain
6. Mentions vs citations: reading an AI visibility report
7. Turning freight enquiries into qualified ones: form design for logistics websites

Each article needs a real point of view and real examples. If there's nothing new to say, don't publish.

## Before launch checklist

- [ ] Set `CONTACT_EMAIL` and make sure that inbox is monitored (hello@ or sales@radynta.com once the mailbox exists)
- [ ] Lawyer review of the privacy policy and terms
- [ ] Decide whether to show a phone/WhatsApp number (`CONTACT_PHONE`)
- [ ] Get a Perplexity API key and run `check-provider perplexity --live`
- [ ] Run a real audit on a friendly business's site and compare the findings with a manual review
