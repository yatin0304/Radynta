# RADYNTA Logistics Visibility Diagnostic v0.1

This is an internal framework for prioritising work. It is **not** an official Google, ChatGPT, Gemini or Perplexity score.
The score is `awarded ÷ measured points × 100`. Checks that couldn't be measured are excluded from both sides and reported as "not measured". They are never scored as zero.

Source of truth: `radynta/audit/scoring.py`. Recommendation text: `radynta/audit/recommendations.py`.

| Dim (pts) | Code | Check | Rule | Limitation |
|---|---|---|---|---|
| AI visibility (25) | A1 | Brand mentioned | 15 × mention rate over valid responses | Small samples; answers vary |
|  | A2 | Client site cited | 10 × client-domain citation rate | API may differ from consumer apps |
| Technical (20) | T1 | Homepage over HTTPS | 3 if 200 + HTTPS, 1 if 200 only | |
|  | T2 | robots.txt | 2 if 200 and allows `/`; 1 if 404; 0 if blocking or error | |
|  | T3 | XML sitemap | 2 if it lists URLs; 1 if empty | Checks robots.txt sitemap lines, else `/sitemap.xml` |
|  | T4 | Indexable | 3 × share without noindex; 0 if homepage is noindex | Meta tags only (no X-Robots-Tag header yet) |
|  | T5 | Titles | 3 × share 10–65 chars and unique | |
|  | T6 | Meta descriptions | 2 × share 50–170 chars and unique | |
|  | T7 | One H1 | 2 × share with exactly one H1 | |
|  | T8 | Self-canonical | 1 × share whose canonical is on-site and points to itself | May be intentional for duplicates |
|  | T9 | No broken pages | 2, scaled down; 0 if >10 % of crawled URLs fail | Only crawled URLs checked |
| Relevance (20) | S1 | Services in title/H1 | 8 × coverage (title/H1 = 1, body = 0.5) | Needs services configured |
|  | S2 | Dedicated service pages | 4 × share with a page (slug or H1) | |
|  | S3 | Geography/route coverage | 6 × coverage (title/H1 = 1, body = 0.5) | Needs geographies configured |
|  | S4 | Homepage states what you do | 2 if title/H1 has a service term | |
| Trust (15) | R1 | Phone visible | 3 | Phone numbers shown as images aren't detected |
|  | R2 | Email visible | 2 | |
|  | R3 | Address with PIN | 3 | Heuristic; confirm by hand |
|  | R4 | About page | 2 | |
|  | R5 | Organization JSON-LD | 2 | Flags JSON-LD that fails to parse |
|  | R6 | GSTIN (2) + privacy policy (1) | 3 | |
| Content (10) | C1 | 250+ words | 4 × share | A proxy, not a quality measure |
|  | C2 | Heading structure | 3 × share with 2+ H2 and no skipped levels | |
|  | C3 | Q&A content | 3 if any page has 3+ question headings or FAQPage | |
| Conversion (10) | V1 | tel: links | 3 | |
|  | V2 | WhatsApp link | 2 | |
|  | V3 | Enquiry form | 3 (search forms excluded) | JS-injected forms aren't seen |
|  | V4 | Homepage CTA text | 2 | |

Severity of a failed check: **high** if it is ≥75 % short and worth ≥3 pts, **medium** if ≥40 % short, otherwise **low**. Priority: high = P1, medium = P2, low = P3.

## AI visibility metrics

- **Valid run** = a response that was collected successfully and has text. Failures (timeouts, auth errors, empty answers) are stored with their error and excluded from denominators.
- **Brand mention rate** = valid responses naming the brand or an alias (word-bounded, case-insensitive) ÷ valid responses.
- **Client citation rate** = valid responses citing the client domain or a subdomain (from provider citations or URLs in the text) ÷ valid responses.
- **Ambiguous** = matched alias is under 4 characters or made only of generic logistics words. These need a human to confirm.
- Competitor mention frequency and cited-domain frequency are counted once per response.
- Change over time is the percentage-point difference against the previous completed batch on the same platform.

## Crawl safety

- Only http/https, ports 80/443, no credentials in URLs.
- Every hop must resolve only to public IPs (blocks localhost, RFC1918, CGNAT, link-local and metadata IPs, IPv6 ULA, mapped addresses).
- Redirects are followed manually and re-validated at each hop.
- Body limit of 2 MB, a timeout, and a delay between requests.
- Respects robots.txt. Skips `/admin`, `/login`, `/account`, `/cart`, `/checkout`, `/dashboard`, `/portal` and similar paths.
- Stays on the same site; off-site redirects are recorded, not followed.
