"""Public website routes."""
from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage

from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, url_for

from .. import db as dbmod
from .. import get_db
from ..security import check_spam, rate_limited
from .content import (ARTICLES, HOME_FAQS, INDUSTRIES, METHOD_STEPS, OBJECTIVES, PACKAGE_EXCLUSIONS, PACKAGES,
                      SEGMENTS, SERVICES)

bp = Blueprint("site", __name__)

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[+\d][\d\s\-()]{7,18}$")
URL_RE = re.compile(r"^(https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/\S*)?$")

STATIC_PAGES = ["site.home", "site.services", "site.about", "site.resources", "site.contact", "site.audit_request",
                "site.privacy", "site.terms"]


def _page(title, description, **extra):
    return {"title": title, "description": description, **extra}


def _crumbs(*items):
    return [("Home", url_for("site.home"))] + list(items)


@bp.app_context_processor
def _nav():
    return {"nav_services": SERVICES, "nav_industries": INDUSTRIES}


@bp.get("/")
def home():
    return render_template("site/home.html", faqs=HOME_FAQS, steps=METHOD_STEPS, industries=INDUSTRIES, services=SERVICES,
                           page=_page("Logistics AEO & AI Search Visibility Agency in India | RADYNTA",
                                      "RADYNTA helps transporters, freight forwarders, warehouse operators and 3PL providers improve AI search visibility, strengthen their online presence and generate more qualified enquiries.",
                                      home=True, faqs=HOME_FAQS))


@bp.get("/services/")
def services():
    return render_template("site/services.html", services=SERVICES, packages=PACKAGES, exclusions=PACKAGE_EXCLUSIONS,
                           page=_page("Services: Logistics AEO, Technical SEO & AI Visibility Monitoring | RADYNTA",
                                      "AEO, technical SEO and AI search visibility monitoring for logistics companies in India, with transparent indicative pricing.",
                                      crumbs=_crumbs(("Services", None))))


@bp.get("/services/<slug>/")
def service_detail(slug):
    svc = SERVICES.get(slug) or abort(404)
    return render_template("site/service_detail.html", svc=svc, slug=slug, industries=INDUSTRIES,
                           page=_page(f"{svc['title']} | RADYNTA", svc["description"],
                                      crumbs=_crumbs(("Services", url_for("site.services")), (svc["name"], None)),
                                      faqs=svc["faqs"]))


@bp.get("/industries/<slug>/")
def industry(slug):
    ind = INDUSTRIES.get(slug) or abort(404)
    others = {k: v for k, v in INDUSTRIES.items() if k != slug}
    return render_template("site/industry.html", ind=ind, slug=slug, others=others, services=SERVICES,
                           page=_page(f"{ind['title']} | RADYNTA", ind["description"],
                                      crumbs=_crumbs((ind["name"], None)), faqs=ind["faqs"]))


@bp.get("/about/")
def about():
    return render_template("site/about.html", page=_page("About RADYNTA | Logistics Visibility Specialists",
                                                         "RADYNTA is an India-based agency focused on search and AI visibility for logistics companies, combining logistics domain knowledge with software quality practices.",
                                                         crumbs=_crumbs(("About", None))))


@bp.get("/resources/")
def resources():
    return render_template("site/resources.html", articles=ARTICLES,
                           page=_page("Resources: Logistics SEO & AI Visibility Guides | RADYNTA",
                                      "Practical guides on technical SEO, AI search visibility and lead generation for logistics companies.",
                                      crumbs=_crumbs(("Resources", None))))


@bp.get("/resources/<slug>/")
def article(slug):
    art = ARTICLES.get(slug) or abort(404)
    return render_template(art["template"], art=art, slug=slug,
                           page=_page(f"{art['title']} | RADYNTA", art["description"], article=art,
                                      crumbs=_crumbs(("Resources", url_for("site.resources")), (art["title"], None))))


@bp.get("/privacy/")
def privacy():
    return render_template("site/privacy.html", page=_page("Privacy Policy | RADYNTA", "How RADYNTA collects, uses and protects personal data submitted through this website.",
                                                           crumbs=_crumbs(("Privacy Policy", None))))


@bp.get("/terms/")
def terms():
    return render_template("site/terms.html", page=_page("Terms of Service | RADYNTA", "Terms governing use of the RADYNTA website and services.",
                                                         crumbs=_crumbs(("Terms of Service", None))))


# ------------------------------------------------------------- forms ---

def _clean(form, key, limit):
    return (form.get(key) or "").strip()[:limit]


def validate_audit_form(form) -> tuple[dict, dict]:
    data = {
        "name": _clean(form, "name", 120), "email": _clean(form, "email", 200), "phone": _clean(form, "phone", 30),
        "company": _clean(form, "company", 200), "website": _clean(form, "website", 300),
        "segment": _clean(form, "segment", 40), "geography": _clean(form, "geography", 200),
        "objective": _clean(form, "objective", 40), "message": _clean(form, "message", 2000),
        "consent": 1 if form.get("consent") == "yes" else 0,
    }
    errors = {}
    if len(data["name"]) < 2:
        errors["name"] = "Please enter your name."
    if not data["email"] and not data["phone"]:
        errors["email"] = "Please give a business email or a phone number so we can reply."
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors["email"] = "That email address doesn’t look right."
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors["phone"] = "Please enter a valid phone number, e.g. +91 98765 43210."
    if len(data["company"]) < 2:
        errors["company"] = "Please enter your company name."
    if data["website"] and not URL_RE.match(data["website"]):
        errors["website"] = "Please enter a website address like yourcompany.com, or leave it blank."
    if data["segment"] not in dict(SEGMENTS):
        errors["segment"] = "Please choose your logistics segment."
    if data["objective"] and data["objective"] not in dict(OBJECTIVES):
        errors["objective"] = "Please choose an objective."
    if not data["consent"]:
        errors["consent"] = "We need your consent to contact you about this request."
    return data, errors


def validate_contact_form(form) -> tuple[dict, dict]:
    data = {"name": _clean(form, "name", 120), "email": _clean(form, "email", 200), "phone": _clean(form, "phone", 30),
            "company": _clean(form, "company", 200), "message": _clean(form, "message", 4000),
            "consent": 1 if form.get("consent") == "yes" else 0}
    errors = {}
    if len(data["name"]) < 2:
        errors["name"] = "Please enter your name."
    if not data["email"] and not data["phone"]:
        errors["email"] = "Please give an email or phone number so we can reply."
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors["email"] = "That email address doesn’t look right."
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors["phone"] = "Please enter a valid phone number."
    if len(data["message"]) < 10:
        errors["message"] = "Please tell us a little more (at least 10 characters)."
    if not data["consent"]:
        errors["consent"] = "We need your consent to reply to you."
    return data, errors


def _notify(kind: str, enquiry_id: int, data: dict) -> bool:
    """Send an internal notification if SMTP is configured. Returns True only if sent."""
    s = current_app.config["SETTINGS"]
    if not s.email_configured:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"[RADYNTA] New {kind} enquiry #{enquiry_id}: {data.get('company') or data.get('name')}"
    msg["From"] = s.smtp_from
    msg["To"] = s.enquiry_notify_to
    msg.set_content("\n".join(f"{k}: {v}" for k, v in data.items() if k != "consent") +
                    f"\n\nView: {s.site_url}/monitor/enquiries")
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        current_app.logger.warning("enquiry %s stored but notification email failed: %s", enquiry_id, type(exc).__name__)
        return False


def _handle(kind: str, validator, template: str, page: dict):
    errors, data = {}, {}
    if request.method == "POST":
        spam = check_spam(request.form)
        if spam:
            current_app.logger.info("rejected %s form submission: %s", kind, spam)
            if spam in ("expired", "bad-token"):
                errors["_form"] = "This form expired. Please submit it again."
            else:
                # Pretend success to bots, but store nothing.
                return redirect(url_for("site.thanks", kind=kind))
        if not errors and rate_limited(f"form:{kind}", limit=5, window=600):
            abort(429)
        data, errors = validator(request.form) if not errors else (dict(request.form), errors)
        if not errors:
            conn = get_db()
            eid = dbmod.insert(conn, "enquiries", {"kind": kind, **{k: v for k, v in data.items()}})
            conn.commit()
            if _notify(kind, eid, data):
                conn.execute("UPDATE enquiries SET notified=1 WHERE id=?", (eid,))
                conn.commit()
            return redirect(url_for("site.thanks", kind=kind))
    return render_template(template, page=page, errors=errors, data=data, segments=SEGMENTS, objectives=OBJECTIVES), \
        (400 if errors else 200)


@bp.route("/audit-request/", methods=["GET", "POST"])
def audit_request():
    return _handle("audit", validate_audit_form, "site/audit_request.html",
                   _page("Request a Logistics Visibility Audit | RADYNTA",
                         "Request an AI search visibility and website audit for your logistics business. Tell us your segment, target markets and goals.",
                         crumbs=_crumbs(("Request an audit", None))))


@bp.route("/contact/", methods=["GET", "POST"])
def contact():
    return _handle("contact", validate_contact_form, "site/contact.html",
                   _page("Contact RADYNTA", "Contact RADYNTA about AEO, technical SEO or AI visibility monitoring for your logistics business.",
                         crumbs=_crumbs(("Contact", None))))


@bp.get("/thanks/<kind>/")
def thanks(kind):
    if kind not in ("audit", "contact"):
        abort(404)
    return render_template("site/thanks.html", kind=kind, page=_page("Thank you | RADYNTA", "", noindex=True))


# ---------------------------------------------------------- SEO files ---

@bp.get("/robots.txt")
def robots_txt():
    s = current_app.config["SETTINGS"]
    body = f"User-agent: *\nDisallow: /monitor/\nDisallow: /thanks/\n\nSitemap: {s.site_url}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap_xml():
    s = current_app.config["SETTINGS"]
    urls = [url_for(e) for e in STATIC_PAGES]
    urls += [url_for("site.service_detail", slug=k) for k in SERVICES]
    urls += [url_for("site.industry", slug=k) for k in INDUSTRIES]
    urls += [url_for("site.article", slug=k) for k in ARTICLES]
    items = "".join(f"<url><loc>{s.site_url}{u}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
    return Response(xml, mimetype="application/xml")
