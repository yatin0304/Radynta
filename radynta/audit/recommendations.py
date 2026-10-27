"""Turn failed checks into findings and draft recommendations.

Recommendations are DRAFTS until a RADYNTA reviewer approves them in the
monitor UI. Expected outcomes are phrased as hypotheses, never guarantees.
"""
from __future__ import annotations

from .scoring import severity_for

PRIORITY = {"high": "P1", "medium": "P2", "low": "P3"}

# code -> (title, business relevance, suggested action, effort, hypothesis)
PLAYBOOK: dict[str, tuple[str, str, str, str, str]] = {
    "T1": ("Serve the homepage reliably over HTTPS",
           "Buyers and search engines treat an insecure or failing homepage as a red flag; every other page depends on it.",
           "Install a valid TLS certificate, 301-redirect all http:// URLs to https://, and fix any server errors on the homepage.",
           "Low (hosting setting, 1–2 hours)",
           "If the homepage loads securely, crawlers can index the site consistently and fewer visitors abandon at the browser warning."),
    "T2": ("Publish a permissive robots.txt",
           "A blocking or missing robots.txt can stop search engines and AI crawlers from reading service pages.",
           "Publish /robots.txt that allows crawling of public pages and lists the sitemap URL. Remove any site-wide Disallow: / rules.",
           "Low (under 1 hour)",
           "If crawlers are explicitly allowed and pointed at the sitemap, new and updated pages may be discovered faster."),
    "T3": ("Publish an XML sitemap",
           "A sitemap helps search engines find every service, route and location page, not only those linked from the homepage.",
           "Generate /sitemap.xml listing all canonical public pages, reference it in robots.txt and submit it in Google Search Console and Bing Webmaster Tools.",
           "Low (1–2 hours; most CMSs have a plugin)",
           "If a sitemap is submitted, deeper pages such as route pages may be indexed more completely."),
    "T4": ("Remove unintended noindex directives",
           "Pages marked noindex are excluded from search results and are unlikely to be used as sources by search-grounded AI answers.",
           "Review every listed page; remove the noindex meta tag (or X-Robots-Tag header) from pages that should be found by buyers.",
           "Low (under 1 hour per template)",
           "If important pages become indexable, they can begin to appear for relevant service searches."),
    "T5": ("Write a unique, descriptive title for every page",
           "Titles are the first thing a buyer sees in search results; duplicated or vague titles make service pages indistinguishable.",
           "Give each page a 10–65 character title naming the service and location, e.g. “FTL Truck Transport Mumbai to Pune | Company”.",
           "Low–Medium (15 minutes per page)",
           "If titles match how buyers search, click-through from search results may improve."),
    "T6": ("Write unique meta descriptions",
           "Meta descriptions shape the search snippet and help a buyer decide whether to enquire.",
           "Write a 50–170 character description for each page summarising the service, coverage and the next step (call / quote).",
           "Low (10 minutes per page)",
           "If snippets are specific, more qualified searchers may click through."),
    "T7": ("Use exactly one H1 per page",
           "A single clear H1 tells search engines and AI systems what the page is about.",
           "Make the main page heading the only H1 and convert other large headings to H2/H3.",
           "Low (template change)",
           "If page topics are unambiguous, the right page is more likely to be matched to the right query."),
    "T8": ("Make every page’s canonical URL point to itself",
           "A missing or wrong canonical can split ranking signals across URL variants — or, if inner pages point to the homepage, tell search engines to ignore those pages entirely.",
           "On each page, set <link rel=\"canonical\"> to that page’s own preferred https URL. Only point elsewhere for genuine duplicates.",
           "Low (template change)",
           "If duplicates consolidate, the preferred URL may accumulate signals more consistently."),
    "T9": ("Fix broken internal pages",
           "Broken pages waste crawl effort and lose buyers who click from navigation or search.",
           "Restore or 301-redirect each failing URL to the most relevant live page, then update internal links.",
           "Low–Medium (depends on count)",
           "If dead ends are removed, fewer visitors drop off before enquiring."),
    "S1": ("Name each core service in page titles and headings",
           "Buyers search by service (“part load transport”, “customs clearance”). If the service is only mentioned in passing, the site is unlikely to match those searches or AI answers.",
           "For every service marked ‘not found’ or ‘body text only’, add it to the title and H1 of the most relevant page.",
           "Medium (half a day)",
           "If services are stated explicitly, the site may become eligible to appear for more service-specific queries."),
    "S2": ("Create a dedicated page for each core service",
           "A single generic ‘Services’ page cannot answer specific buyer questions about each service.",
           "Create one substantive page per missing service: what it covers, vehicle/equipment types, coverage, typical lead times, documents needed, and a quote CTA.",
           "Medium–High (1 page per day including review)",
           "If each service has a focused page, those pages may be cited or ranked for service-specific questions."),
    "S3": ("Cover the cities, states and routes you actually serve",
           "Logistics buyers almost always search with a location or lane. Missing geography means missing the question entirely.",
           "Add genuine coverage details (branches, lanes, transit times) for each target geography. Create route pages only where you operate regularly — avoid thin, copy-paste location pages.",
           "Medium (depends on number of lanes)",
           "If target locations and lanes are covered with real detail, the site may appear for more location-specific queries."),
    "S4": ("State clearly on the homepage what you do and where",
           "Visitors and AI systems summarise a company from its homepage; a vague headline leads to vague or missing mentions.",
           "Rewrite the homepage title and H1 to include the primary service and region, e.g. “Full Truckload & Part Load Transport across Maharashtra”.",
           "Low (1 hour)",
           "If the homepage is explicit, summaries of the business may become more accurate."),
    "R1": ("Show a phone number on every page",
           "Logistics buyers often want to call before sharing shipment details; a missing number reduces trust.",
           "Add the main business number as text in the header and footer, matching the Google Business Profile.",
           "Low (template change)",
           "If contact details are visible, more visitors may make direct enquiries."),
    "R2": ("Show a business email address",
           "Corporate buyers and procurement teams expect a company email, not only a form.",
           "Display a domain-based email (e.g. sales@yourdomain.com) in the footer and on the contact page.",
           "Low",
           "If a professional email is visible, the business may appear more established to B2B buyers."),
    "R3": ("Publish a complete physical address",
           "An address with PIN code shows that the business is real and helps local search and map listings stay consistent.",
           "Add the registered/branch address(es) with PIN code to the footer and contact page; keep it identical to the Google Business Profile.",
           "Low",
           "If name, address and phone are consistent across the web, local listings may be trusted more."),
    "R4": ("Add an About page",
           "Buyers want to know who they are trusting with their cargo: history, fleet or facilities, team and certifications.",
           "Create an About page with verifiable facts only: years operating, fleet/warehouse details, registrations, key people.",
           "Medium (half a day)",
           "If the company story is documented, buyers and AI summaries have accurate facts to draw on."),
    "R5": ("Add Organization structured data that matches the page",
           "Structured data gives search engines an unambiguous record of the business name, URL, logo and contact points.",
           "Add Organization (or LocalBusiness) JSON-LD with genuine name, URL, logo, phone and address. Never add ratings or reviews that are not shown on the page. Fix any JSON-LD that fails to parse.",
           "Low (1–2 hours)",
           "If the entity is described consistently, search engines may associate the brand with its website more reliably. Structured data does not guarantee rich results or AI citations."),
    "R6": ("Show business registration details and a privacy policy",
           "GSTIN and a privacy policy are basic credibility signals for Indian B2B buyers and are expected under India’s data protection rules when collecting enquiries.",
           "Display the GSTIN in the footer (if the business is comfortable doing so) and publish a privacy policy describing how enquiry data is used.",
           "Low",
           "If identity signals are visible, cautious buyers may be more willing to submit an enquiry."),
    "C1": ("Expand thin pages with useful, specific information",
           "Short pages rarely answer a buyer’s real questions about capacity, coverage, timelines or documentation.",
           "Expand each listed page to cover: who the service is for, what is included, coverage, typical transit/lead times, documentation, and FAQs. Use real operational detail.",
           "Medium–High",
           "If pages answer buyer questions directly, they are more likely to be used as a source for those questions."),
    "C2": ("Structure pages with clear sections",
           "Clear H2 sections make pages easier for buyers to scan and for search systems to extract answers from.",
           "Break pages into H2 sections (e.g. Coverage, Vehicle types, Process, Documents, FAQs) and do not skip heading levels.",
           "Low–Medium",
           "If content is well structured, specific passages may be easier to surface for specific questions."),
    "C3": ("Add a genuine FAQ section to key service pages",
           "Buyers ask questions in natural language — the same way they ask AI assistants. Direct answers on your own pages give those systems something accurate to quote.",
           "Collect the real questions your sales team hears and answer them on the relevant service pages. Mark up with FAQPage schema only if the Q&A is visible on the page.",
           "Medium",
           "If the site answers common buyer questions directly, it may be more likely to be cited for them. FAQ markup alone does not guarantee visibility."),
    "V1": ("Add click-to-call links",
           "Most logistics enquiries from mobile end in a phone call; without a tap-to-call link, some of those calls never happen.",
           "Wrap every displayed phone number in a tel: link and add a call button in the mobile header.",
           "Low",
           "If calling is one tap away, mobile visitors may call more often."),
    "V2": ("Add a WhatsApp contact option",
           "Many Indian transport and freight buyers prefer WhatsApp for quick rate requests.",
           "Add a wa.me link to a monitored business WhatsApp number with a pre-filled message, e.g. “Hi, I need a quote for…”.",
           "Low",
           "If buyers can message in their preferred channel, enquiry volume from mobile may increase."),
    "V3": ("Add a short quote/enquiry form",
           "Buyers outside business hours need a way to request a rate without calling.",
           "Add a short form (name, phone, origin, destination, cargo type, date) on the homepage and every service page, and route submissions to a monitored inbox.",
           "Medium (half a day including testing)",
           "If enquiries can be submitted at any time, fewer out-of-hours prospects may be lost."),
    "V4": ("Add a clear call-to-action on the homepage",
           "Visitors who don’t see an obvious next step leave.",
           "Place a primary ‘Get a quote’ button above the fold and repeat it after each major section.",
           "Low",
           "If the next step is obvious, more homepage visitors may start an enquiry."),
    "A1": ("Strengthen the facts AI systems can find about the brand",
           "When buyers ask AI assistants for logistics providers, brands that are not mentioned are not considered.",
           "Make service, coverage and credibility facts explicit on the website; keep business listings consistent; earn mentions on relevant industry directories and associations. Re-test the same questions monthly.",
           "Ongoing",
           "If the brand’s facts are explicit and consistent across sources, mention rates may improve over subsequent test runs. No outcome is guaranteed."),
    "A2": ("Make the website a citable source for buyer questions",
           "Even when an AI answer mentions a brand, it may cite a directory or competitor instead of the brand’s own site.",
           "Publish pages that directly answer the tested buyer questions (service + location + specifics). Review which domains are cited today and close the content gaps they reveal.",
           "Medium–High",
           "If the website directly answers the tested questions, the client domain may be cited more often. No outcome is guaranteed."),
}


def findings_from_scorecard(scorecard: dict) -> list[dict]:
    out = []
    for dim_key, dim in scorecard["dimensions"].items():
        for check in dim["checks"]:
            if not check["measured"]:
                out.append({
                    "dimension": dim_key, "code": check["code"], "severity": "info",
                    "title": f"Not measured: {check['label']}", "evidence": check["evidence"], "urls": [],
                })
                continue
            sev = severity_for(check)
            if sev is None:
                continue
            if check["code"] == "T4" and "HOMEPAGE is noindex" in check["evidence"]:
                sev = "high"
            out.append({
                "dimension": dim_key, "code": check["code"], "severity": sev,
                "title": check["label"], "evidence": check["evidence"]
                + (f" (Limitation: {check['limitation']})" if check.get("limitation") else ""),
                "urls": check["urls"],
            })
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    return sorted(out, key=lambda f: (order[f["severity"]], f["code"]))


def recommendation_for(finding: dict) -> dict | None:
    if finding["severity"] == "info":
        return None
    title, relevance, action, effort, hypothesis = PLAYBOOK[finding["code"]]
    return {
        "title": title,
        "finding": finding["title"],
        "evidence": finding["evidence"],
        "business_relevance": relevance,
        "priority": PRIORITY[finding["severity"]],
        "action": action,
        "effort": effort,
        "hypothesis": hypothesis,
    }
