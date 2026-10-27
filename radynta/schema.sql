-- RADYNTA schema (SQLite). Every client-owned table carries client_id so
-- queries can always be scoped to a single client.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Public website enquiries (audit requests + contact messages)
CREATE TABLE IF NOT EXISTS enquiries (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('audit', 'contact')),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,
    website TEXT,
    segment TEXT,
    geography TEXT,
    objective TEXT,
    message TEXT,
    consent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'qualified', 'closed', 'spam')),
    notified INTEGER NOT NULL DEFAULT 0,
    internal_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enquiries_created ON enquiries(created_at);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    brand_aliases TEXT NOT NULL DEFAULT '[]',   -- JSON list
    website_url TEXT NOT NULL,
    primary_domain TEXT NOT NULL,
    extra_domains TEXT NOT NULL DEFAULT '[]',   -- JSON list (e.g. .in domain)
    segment TEXT,
    services TEXT NOT NULL DEFAULT '[]',        -- JSON list of service terms
    geographies TEXT NOT NULL DEFAULT '[]',     -- JSON list of cities/states/routes
    is_sample INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    domain TEXT,
    UNIQUE (client_id, name)
);
CREATE INDEX IF NOT EXISTS idx_competitors_client ON competitors(client_id);

CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    geography TEXT,
    service_category TEXT,
    target_customer TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (client_id, text)
);
CREATE INDEX IF NOT EXISTS idx_prompts_client ON prompts(client_id);

-- A batch = one execution of the prompt set against one platform ("run")
CREATE TABLE IF NOT EXISTS visibility_batches (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('api', 'manual', 'sample')),
    model TEXT,
    market TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    notes TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_batches_client ON visibility_batches(client_id, started_at);

CREATE TABLE IF NOT EXISTS visibility_responses (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES visibility_batches(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    prompt_id INTEGER REFERENCES prompts(id) ON DELETE SET NULL,
    prompt_text TEXT NOT NULL,
    platform TEXT NOT NULL,
    model TEXT,
    market TEXT,
    collected_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    raw_response TEXT,
    raw_payload TEXT,
    error TEXT,
    brand_mentioned INTEGER,          -- NULL when status != ok
    mention_context TEXT,
    mention_ambiguous INTEGER NOT NULL DEFAULT 0,
    competitor_mentions TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_responses_batch ON visibility_responses(batch_id);
CREATE INDEX IF NOT EXISTS idx_responses_client ON visibility_responses(client_id);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY,
    response_id INTEGER NOT NULL REFERENCES visibility_responses(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('provider', 'text')),
    is_client_domain INTEGER NOT NULL DEFAULT 0,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_response ON citations(response_id);
CREATE INDEX IF NOT EXISTS idx_citations_client ON citations(client_id, domain);

CREATE TABLE IF NOT EXISTS site_audits (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    start_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    pages_crawled INTEGER NOT NULL DEFAULT 0,
    robots_status INTEGER,
    robots_txt TEXT,
    sitemap_url TEXT,
    sitemap_status INTEGER,
    sitemap_url_count INTEGER,
    score_json TEXT,
    crawl_notes TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    is_sample INTEGER NOT NULL DEFAULT 0,
    approved INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT,
    approved_at TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_audits_client ON site_audits(client_id, started_at);

CREATE TABLE IF NOT EXISTS page_checks (
    id INTEGER PRIMARY KEY,
    audit_id INTEGER NOT NULL REFERENCES site_audits(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    final_url TEXT,
    status_code INTEGER,
    redirect_chain TEXT NOT NULL DEFAULT '[]',
    data TEXT NOT NULL DEFAULT '{}',   -- JSON of parsed page facts
    error TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pages_audit ON page_checks(audit_id);

CREATE TABLE IF NOT EXISTS audit_findings (
    id INTEGER PRIMARY KEY,
    audit_id INTEGER NOT NULL REFERENCES site_audits(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low', 'info')),
    title TEXT NOT NULL,
    evidence TEXT NOT NULL,
    urls TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'wont_fix')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_findings_audit ON audit_findings(audit_id);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    audit_id INTEGER NOT NULL REFERENCES site_audits(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    finding_id INTEGER REFERENCES audit_findings(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    finding TEXT NOT NULL,
    evidence TEXT NOT NULL,
    business_relevance TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
    action TEXT NOT NULL,
    effort TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft', 'approved', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_recs_audit ON recommendations(audit_id);

CREATE TABLE IF NOT EXISTS tracked_metrics (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    batch_id INTEGER REFERENCES visibility_batches(id) ON DELETE CASCADE,
    audit_id INTEGER REFERENCES site_audits(id) ON DELETE CASCADE,
    metric TEXT NOT NULL,
    value REAL,
    denominator INTEGER,
    computed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_metrics_client ON tracked_metrics(client_id, metric, computed_at);

CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    audit_id INTEGER REFERENCES site_audits(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
