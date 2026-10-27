"""Website copy. Kept in one module so pages share layouts but not text.

Rules followed here: no guaranteed rankings or AI citations, no testimonials,
client logos, statistics or case studies until real evidence exists.
"""
from __future__ import annotations

SERVICES = {
    "logistics-aeo": {
        "name": "Logistics AEO",
        "short": "Make your services, lanes and credentials easy for AI assistants and search engines to understand and quote.",
        "title": "Answer Engine Optimization (AEO) for Logistics Companies",
        "description": "AEO for transporters, freight forwarders, 3PLs and courier companies in India: clear service, route and credibility content that AI assistants and search engines can understand.",
        "h1": "Answer Engine Optimization for logistics companies",
        "intro": "Buyers increasingly ask ChatGPT, Gemini, Perplexity and Google’s AI features questions like “who handles part-load transport from Pune to Bengaluru?” Those systems build answers from what they can find and verify about you. AEO is the work of making those facts explicit, consistent and easy to cite.",
        "points": [
            ("Service and lane clarity", "We rewrite or restructure service pages so each one states plainly what you move, where, in what vehicles or modes, and with what lead times — in the language your buyers actually use."),
            ("Question-led content", "We gather the real questions your sales team hears and turn them into direct answers on the right pages, instead of a generic FAQ nobody reads."),
            ("Entity consistency", "Your company name, address, phone, registrations and descriptions should match across your website, Google Business Profile, directories and associations. We list every inconsistency we find and help fix it."),
            ("Structured data that reflects reality", "Organization, LocalBusiness, Service and FAQ markup — only for facts that are visible on the page. We never add ratings, reviews or certifications that don’t exist."),
            ("Measurement", "We re-run the same buyer questions on the platforms we can access and track whether you are mentioned and whether your site is cited, separately."),
        ],
        "not_included": "AEO is not a trick or a file you upload. No technique — including llms.txt, FAQ schema or any other markup — guarantees that an AI system will mention or cite you.",
        "faqs": [
            ("What is the difference between AEO and SEO?", "SEO focuses on ranking pages in search results. AEO focuses on being understood and used as a source when a search engine or AI assistant composes a direct answer. In practice they overlap heavily: AEO builds on a technically sound, well-structured website."),
            ("Can you guarantee that ChatGPT will recommend us?", "No. Nobody can honestly guarantee that. AI answers vary by platform, model, location, wording and over time. We improve the facts and content those systems draw on, and we measure what changes."),
            ("Which platforms do you test?", "It depends on what we can access legitimately. We use official APIs where available (for example Perplexity’s API) and record answers manually from consumer apps where an API isn’t appropriate. Every report states exactly which method was used for each platform."),
        ],
    },
    "technical-seo": {
        "name": "Technical SEO",
        "short": "Fix the crawl, indexing and page-structure problems that stop your service pages being found.",
        "title": "Technical SEO Audits for Logistics Websites",
        "description": "Technical SEO for logistics websites in India: crawlability, indexing, page titles, canonical URLs, sitemaps, structured data and broken pages, with a prioritised fix list.",
        "h1": "Technical SEO for logistics websites",
        "intro": "Many logistics websites were built once and left alone. Pages get blocked from indexing by accident, sitemaps go missing, every page shares the same title, and old service pages return errors. None of that is visible to the business owner, but all of it affects whether buyers can find you.",
        "points": [
            ("Crawl and indexing", "HTTP status of every crawled page, redirect chains, robots.txt rules, noindex directives and XML sitemap availability."),
            ("Page metadata", "Missing, duplicated or badly sized titles and meta descriptions, multiple or missing H1s, canonical URLs and Open Graph tags."),
            ("Structure and links", "Heading hierarchy, internal links between service, industry and route pages, and broken internal URLs."),
            ("Structured data", "Detection and validation of existing JSON-LD, and recommendations based strictly on the content on each page."),
            ("Mobile and contact basics", "Viewport configuration, tap-to-call links, WhatsApp links and enquiry forms — the technical details that decide whether a mobile visitor can contact you."),
        ],
        "not_included": "We crawl only public pages, with rate limits, and never log in, submit forms or test private areas of your site.",
        "faqs": [
            ("Do you need access to our website or hosting?", "Not for the audit. We crawl the public site the way a search engine would. To implement fixes we either work with your developer or, with your permission, make the changes ourselves."),
            ("How many pages do you check?", "The Launch Audit reviews your most important pages in depth and crawls a bounded sample of the rest. Larger sites are scoped individually."),
            ("Will this slow down our website?", "No. Our crawler waits between requests and checks a limited number of pages."),
        ],
    },
    "ai-search-visibility-monitoring": {
        "name": "AI Search Visibility Monitoring",
        "short": "Track whether you and your competitors appear in AI answers to your buyers’ questions, and which sources get cited.",
        "title": "AI Search Visibility Monitoring for Logistics Brands",
        "description": "Monthly monitoring of how AI assistants answer logistics buyer questions: brand mentions, cited sources and competitor visibility, with clear methodology and limitations.",
        "h1": "AI search visibility monitoring",
        "intro": "You can’t improve what you don’t measure. We maintain a library of the questions your buyers ask — by service, location and customer type — and record how AI platforms answer them over time.",
        "points": [
            ("Your buyer question library", "Questions configured for your services, routes, target customers and geography, reviewed with you before monitoring starts."),
            ("Mentions and citations, tracked separately", "Being named in an answer and having your website cited as a source are different outcomes. We report both."),
            ("Competitor and source analysis", "Which competitors are mentioned, and which domains — directories, marketplaces, news, competitor sites — are being cited instead of yours."),
            ("Honest denominators", "Rates are calculated from valid responses only. Failed or blocked collections are reported as failures, never counted as ‘not mentioned’."),
            ("Raw evidence", "Every answer is stored verbatim with its timestamp, platform and method, so any number in a report can be traced back to the response behind it."),
        ],
        "not_included": "Results are a sample, not a census: AI answers change between runs, users and locations. We show sample sizes and limitations alongside every metric.",
        "faqs": [
            ("Is this an official ranking from Google or ChatGPT?", "No. These are RADYNTA’s own measurements of answers we collected. No AI platform publishes an official visibility ranking."),
            ("How often do you re-test?", "Monthly on the Visibility Growth and Visibility Intelligence plans, using the same questions so changes are comparable."),
            ("Do you scrape ChatGPT or Gemini?", "No. We use official APIs where they exist and are appropriate, and record consumer-app answers manually. We respect each platform’s terms and rate limits."),
        ],
    },
}

INDUSTRIES = {
    "road-transport": {
        "name": "Road Transport",
        "nav": "Road transport & fleet operators",
        "title": "AI Search Visibility for Road Transport & Fleet Operators",
        "description": "Help shippers find your FTL, part-load and fleet services in search and AI answers. Route-specific visibility audits for Indian transporters and fleet operators.",
        "h1": "Visibility for transporters and fleet operators",
        "intro": "Shippers looking for a truck rarely search for a company name. They search for a lane, a load type and a vehicle: “32 ft container Mumbai to Ahmedabad”, “part load transport Pune to Hyderabad”, “open body truck for machinery”. If your website doesn’t state those lanes and vehicles, you are invisible for exactly the searches that bring work.",
        "buyer_questions": [
            "Which transporters provide full truckload services between Mumbai and Pune?",
            "Who offers part-load (PTL) transport from Delhi to Jaipur?",
            "Which transport companies have 32 ft multi-axle containers in Gujarat?",
            "Reliable transporter for industrial goods from Chakan MIDC?",
        ],
        "gaps": [
            "A single ‘Services’ page listing FTL, PTL and ODC in one paragraph, with no detail on any of them.",
            "Lanes served only in a PDF rate card or brochure, or not at all.",
            "Fleet details (vehicle types, capacities, GPS tracking) missing, so buyers can’t tell if you can carry their load.",
            "Phone number shown as an image, with no tap-to-call or WhatsApp link for mobile visitors.",
            "Google Business Profile address and phone different from the website.",
        ],
        "audit_focus": [
            "Coverage of your real lanes and hubs in titles, headings and page copy",
            "Vehicle-type and load-type pages (FTL, PTL, ODC, containerised, open body)",
            "Mobile contact paths: tap-to-call, WhatsApp, short quote form",
            "Consistency of name, address and phone across website and listings",
        ],
        "content_ideas": [
            "One page per lane you run regularly, with transit times, vehicle options and what to have ready for a quote — only for lanes you genuinely operate.",
            "A fleet page with vehicle types, dimensions and payloads.",
            "A clear explanation of how part-load consolidation works and how pricing is quoted.",
        ],
        "faqs": [
            ("Should we create a page for every city?", "No. Thin pages that swap one city name for another rarely help and can hurt. Create route pages only for lanes you run regularly, and give each one real detail: transit time, vehicles, pickup areas, documentation."),
            ("We get most business through brokers and calls. Does the website matter?", "Increasingly, yes. Shippers often check your website — or ask an AI assistant — before they call, especially for a new lane. The audit shows what they find today."),
        ],
    },
    "freight-forwarding": {
        "name": "Freight Forwarding",
        "nav": "Freight forwarders & shipping",
        "title": "AEO & Search Visibility for Freight Forwarders in India",
        "description": "Search and AI visibility audits for freight forwarders and shipping companies: trade lanes, modes, customs and compliance content that importers and exporters search for.",
        "h1": "Visibility for freight forwarders and shipping companies",
        "intro": "Importers and exporters compare forwarders by trade lane, mode and capability: sea freight to Jebel Ali, LCL consolidation from Nhava Sheva, air freight for pharma, customs clearance at Chennai. These are high-value enquiries, and buyers increasingly shortlist using AI assistants before requesting quotes.",
        "buyer_questions": [
            "Which freight forwarders handle sea freight exports from India to the UAE?",
            "Who offers LCL consolidation from Nhava Sheva to Europe?",
            "Customs broker for import clearance at Chennai port?",
            "Freight forwarder experienced with DG cargo by air from Mumbai?",
        ],
        "gaps": [
            "Trade lanes and destination countries not listed anywhere on the site.",
            "Generic ‘sea, air, road’ copy that doesn’t distinguish FCL, LCL, project cargo or DG handling.",
            "Licences, registrations and memberships mentioned without details a buyer can verify.",
            "No content explaining Incoterms, documentation or clearance steps — the questions buyers actually ask.",
            "Separate .com and .in websites with conflicting information.",
        ],
        "audit_focus": [
            "Coverage of trade lanes, ports and airports you actually serve",
            "Distinct, substantive pages for each mode and special capability",
            "Verifiable credibility signals (registrations, memberships) stated accurately",
            "Which directories and marketplaces are cited instead of you in AI answers",
        ],
        "content_ideas": [
            "Trade-lane pages for your strongest corridors, with ports, typical transit times, frequency and documentation.",
            "A plain-language guide to the export or import documents your clients need, based on how your team actually handles them.",
            "Capability pages for specialised cargo you are genuinely equipped for (temperature-controlled, DG, ODC/project).",
        ],
        "faqs": [
            ("We have a .com and a .in website. Is that a problem?", "Not necessarily, but they should not compete or contradict each other. Usually one should be canonical and the other should redirect page-by-page. We map this in the audit."),
            ("Can you mention our memberships and licences?", "Yes — accurately, and only the ones you hold. We recommend stating them in a way buyers can verify, never implying memberships or certifications you don’t have."),
        ],
    },
    "warehousing-3pl": {
        "name": "Warehousing and 3PL",
        "nav": "Warehousing & 3PL",
        "title": "Search & AI Visibility for Warehousing and 3PL Providers",
        "description": "Visibility audits for warehousing and third-party logistics providers: locations, capacity, services and integrations that brands and manufacturers search for.",
        "h1": "Visibility for warehousing and 3PL providers",
        "intro": "Brands and manufacturers choosing a 3PL want specifics: warehouse location, square footage, racking, temperature control, WMS integrations, value-added services and contract flexibility. If those facts aren’t clearly on your website, AI answers and search results will point buyers to providers whose facts are.",
        "buyer_questions": [
            "Which 3PL providers offer warehousing and distribution in Maharashtra?",
            "Shared warehousing near Bhiwandi for an FMCG brand?",
            "3PL with WMS integration for Shopify and marketplaces in Bengaluru?",
            "Bonded warehouse providers near Chennai port?",
        ],
        "gaps": [
            "Warehouse locations listed by city only, without area, capacity or facility details.",
            "Value-added services (kitting, labelling, returns, cross-docking) buried in one long paragraph.",
            "No explanation of onboarding, minimum commitments or how pricing works.",
            "Technology and integrations claimed vaguely (‘advanced WMS’) without saying what it does.",
            "No page per facility, so facility-specific searches have nothing to match.",
        ],
        "audit_focus": [
            "Facility and location coverage (one clear page per facility you operate)",
            "Service-by-service pages for storage, fulfilment and value-added services",
            "Clarity on integrations, onboarding and commercial model",
            "Trust signals: address details, registrations, and consistent listings",
        ],
        "content_ideas": [
            "Facility pages with location, area, storage types, operating hours and compliance details.",
            "An onboarding page explaining how a new client moves inventory in, step by step.",
            "A comparison of shared versus dedicated warehousing, written for the buyer deciding between them.",
        ],
        "faqs": [
            ("We operate several warehouses. Should each have its own page?", "Usually yes, if each facility is a real, distinct option for buyers. A facility page with specific details is far more useful than a list of city names."),
            ("Do you write the content for us?", "Our plans include content briefs and a set number of substantial page updates. We base content on facts you confirm, and nothing is published without your approval."),
        ],
    },
    "courier-ecommerce-logistics": {
        "name": "Courier and E-commerce Logistics",
        "nav": "Courier & e-commerce logistics",
        "title": "AI Search Visibility for Courier & E-commerce Logistics Companies",
        "description": "Visibility audits for courier, last-mile and e-commerce fulfilment companies: serviceable areas, delivery SLAs, COD, returns and integrations buyers compare.",
        "h1": "Visibility for courier and e-commerce logistics companies",
        "intro": "D2C brands and online sellers compare courier and fulfilment partners on practical details: pin-code coverage, delivery speed, COD remittance cycles, returns handling, weight slabs and platform integrations. AI assistants answer these comparison questions by drawing on whatever detail they can find.",
        "buyer_questions": [
            "Which logistics companies provide e-commerce fulfilment in India?",
            "Courier partner with same-day delivery in Mumbai for a D2C brand?",
            "Which courier companies offer fast COD remittance for small sellers?",
            "Fulfilment provider that integrates with Shopify and handles returns?",
        ],
        "gaps": [
            "Serviceability described as ‘pan-India’ with no way to check a pin code or region.",
            "Delivery timelines, COD terms and returns process not documented.",
            "Integration claims without listing which platforms are actually supported.",
            "Tracking page indexed as the main result instead of service pages.",
            "Seller onboarding requirements hidden behind a sign-up form.",
        ],
        "audit_focus": [
            "Clarity of coverage, delivery timelines and service tiers",
            "Seller-facing pages for COD, returns, weight slabs and onboarding",
            "Accurate integration and platform pages",
            "Separation of tracking and account pages from public service content",
        ],
        "content_ideas": [
            "A seller onboarding guide: documents, KYC, pickup setup and first-shipment steps.",
            "A clear returns and RTO process page.",
            "Integration pages for each platform you genuinely support, with setup steps.",
        ],
        "faqs": [
            ("Will your crawler touch our tracking or seller dashboard?", "No. We skip login, account, dashboard and checkout areas by default and only review public pages."),
            ("We compete with very large courier brands. Is AEO worth it?", "You won’t out-shout national brands on generic queries. The opportunity is usually specific: a region, a niche (B2B parcels, heavy shipments, hyperlocal), or a buyer type where you are genuinely strong. The audit identifies where that is."),
        ],
    },
    "cold-chain-specialized-logistics": {
        "name": "Cold Chain and Specialized Logistics",
        "nav": "Cold chain & specialized logistics",
        "title": "Search Visibility for Cold Chain & Specialized Logistics Providers",
        "description": "Visibility audits for cold-chain, pharma, temperature-controlled, project cargo and specialised logistics providers: capability, compliance and coverage content.",
        "h1": "Visibility for cold-chain and specialized logistics",
        "intro": "Buyers of temperature-controlled, pharma, hazardous or over-dimensional logistics are risk-averse. They look for evidence: temperature ranges, monitoring, equipment, handling procedures, compliance and experience with similar cargo. Clear, verifiable capability content matters more here than in any other segment.",
        "buyer_questions": [
            "Which logistics companies specialise in temperature-controlled transport?",
            "Reefer trucks for frozen food from Nashik to Mumbai?",
            "Pharma cold-chain logistics provider with temperature monitoring in Hyderabad?",
            "Who handles over-dimensional project cargo transport in Gujarat?",
        ],
        "gaps": [
            "Temperature ranges, equipment and monitoring not stated precisely.",
            "Compliance and quality processes mentioned vaguely, without what they cover.",
            "No content explaining handling procedures or what happens if an excursion occurs.",
            "Project cargo capability shown only through photos with no written detail.",
            "Industry-specific pages (pharma, dairy, frozen food, chemicals) missing.",
        ],
        "audit_focus": [
            "Precision of capability claims (ranges, equipment, monitoring)",
            "Industry and cargo-type pages for the sectors you serve",
            "Accurate, verifiable compliance and certification statements",
            "Contact paths suited to urgent and high-value enquiries",
        ],
        "content_ideas": [
            "Capability pages per temperature band or cargo type, with equipment and monitoring details.",
            "A plain-language explanation of your handling and escalation process.",
            "Sector pages (pharma, dairy, frozen food, chemicals, project cargo) for sectors you genuinely serve.",
        ],
        "faqs": [
            ("We hold several certifications. How should we show them?", "State each one accurately — issuing body, scope and validity — and only those currently held. We never recommend displaying certifications or badges that don’t apply."),
            ("Our project cargo work is under NDA. Can we still build visibility?", "Yes. You can describe capabilities, equipment and the kinds of moves you handle without naming clients. We don’t publish case studies without written permission."),
        ],
    },
}

HOME_FAQS = [
    ("What is AI search visibility?", "It describes whether your company is mentioned, and whether your website is cited as a source, when people ask AI assistants and AI-powered search features questions about the services you offer. It is related to SEO, but it is measured differently."),
    ("Can you guarantee rankings or AI recommendations?", "No, and you should be cautious of anyone who does. Search rankings and AI answers depend on many factors outside any agency’s control. We improve the things that are in your control — your website, content and listings — and measure what happens."),
    ("What do I get from a Logistics Visibility Audit?", "A written report covering how AI platforms currently answer your buyers’ questions, which competitors and sources appear, technical problems on your website, gaps in service and route coverage, and a prioritised 30-day action plan. We walk you through it on a call."),
    ("How is the audit score calculated?", "We use RADYNTA’s internal 100-point diagnostic across six areas: AI answer visibility, technical SEO, service and route relevance, trust signals, content quality and conversion readiness. It is our own framework for prioritising work, not an official Google or ChatGPT score. Anything we couldn’t measure is reported as ‘not measured’ rather than scored as zero."),
    ("Do you work with small transporters?", "Yes. Small and mid-sized logistics businesses are exactly who we built the Launch Audit for. If you don’t have a website yet, we’ll tell you honestly whether an audit is useful or whether you need a basic website first."),
    ("Which areas do you serve?", "We are based in India and work with logistics businesses across the country, remotely. Our test questions can be configured for any Indian city, state or trade lane."),
]

PACKAGES = [
    {
        "name": "Launch Audit",
        "price": "₹7,500–₹9,999",
        "cadence": "one-time",
        "for": "For businesses that want a clear picture of where they stand.",
        "items": ["Up to 20 buyer questions", "Two AI/search platforms (where accessible)", "Up to three competitors",
                  "In-depth review of five key pages", "Written report with prioritised recommendations", "One walkthrough call"],
    },
    {
        "name": "Visibility Growth",
        "price": "₹24,999",
        "cadence": "per month",
        "for": "For businesses ready to fix gaps and track progress monthly.",
        "items": ["Up to 30 monitored buyer questions", "Monthly visibility and citation analysis", "Four existing pages reviewed or improved",
                  "Two content briefs or substantial content updates", "Technical SEO recommendations", "Monthly report"],
    },
    {
        "name": "Visibility Intelligence",
        "price": "₹39,999",
        "cadence": "per month",
        "for": "For multi-service or multi-location operators in competitive markets.",
        "items": ["Up to 60 monitored buyer questions", "Expanded competitor analysis", "Six page improvements",
                  "Four content briefs or substantial updates", "Automated reporting where supported", "Technical issue tracking"],
    },
]
PACKAGE_EXCLUSIONS = ("Not included unless agreed in writing: paid advertising, large-scale content production, custom website "
                      "development, and third-party listing or placement fees. Prices exclude GST. Final scope is confirmed "
                      "after an initial call.")

METHOD_STEPS = [
    ("Define the questions", "We agree the buyer questions that matter to you — by service, lane, location and customer type — before anything is measured."),
    ("Collect answers", "We put those questions to selected AI and search platforms through official APIs or documented manual capture, and store every answer verbatim."),
    ("Check your website", "Our crawler reviews your public pages for crawlability, structure, content depth, trust signals and contact paths."),
    ("Score and prioritise", "Findings are scored on our internal six-part diagnostic and turned into actions ranked by impact and effort."),
    ("Review with a human", "Every recommendation is reviewed by RADYNTA before it reaches you. Nothing in the report is auto-published."),
]

SEGMENTS = [
    ("transport", "Road transport / fleet operator"),
    ("freight_forwarding", "Freight forwarding / shipping"),
    ("warehousing_3pl", "Warehousing / 3PL"),
    ("courier_ecommerce", "Courier / e-commerce logistics"),
    ("cold_chain", "Cold chain / specialized logistics"),
    ("project_cargo", "Industrial logistics / project cargo"),
    ("other", "Other"),
]
OBJECTIVES = [
    ("more_enquiries", "More qualified enquiries"),
    ("ai_visibility", "Appear in AI answers"),
    ("website_issues", "Fix website / SEO problems"),
    ("new_market", "Enter a new route or market"),
    ("understand", "Just understand where we stand"),
]

ARTICLES = {
    "how-we-measure-ai-visibility": {
        "title": "How we measure AI visibility for logistics companies",
        "description": "The method behind RADYNTA’s AI visibility measurements: buyer questions, mentions versus citations, valid-run denominators and the limitations we report.",
        "published": "2026-10-27",
        "template": "site/articles/how-we-measure-ai-visibility.html",
    },
    "logistics-website-technical-checklist": {
        "title": "A technical checklist for logistics websites",
        "description": "Fifteen technical and content checks every transporter, forwarder and 3PL website should pass before investing in SEO or AI visibility work.",
        "published": "2026-10-27",
        "template": "site/articles/logistics-website-technical-checklist.html",
    },
}
