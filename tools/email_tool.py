"""
tools/email_tool.py
────────────────────────────────────────────────────────────────────────────
Sends a styled HTML email WITH a PDF attachment to the recipient.

Flow when user says "email me the itinerary to alice@example.com":
  1. send_email_with_pdf() is called by the agent
  2. Builds a beautiful HTML email body
  3. Generates a styled PDF using _build_pdf() from pdf_blob_tool
  4. Attaches the PDF to the email
  5. Sends via Gmail / Outlook SMTP or SendGrid
  6. Returns success + triggers generate_and_save_pdf() for blob archiving

Supported providers (set EMAIL_PROVIDER in .env):
  • gmail    — Gmail SMTP port 587. Needs an App Password.
  • outlook  — Outlook/Hotmail SMTP port 587.
  • sendgrid — SendGrid HTTP API, 100 emails/day free.
────────────────────────────────────────────────────────────────────────────
"""

import os
import io
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

import requests
from langchain_core.tools import tool


# ─────────────────────────────────────────────────────────────────────────────
# HTML email template
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(subject: str, body: str) -> str:
    """Styled HTML email body — travel themed, works in all email clients."""
    escaped = (
        body.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    now = datetime.now().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.10);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1565c0,#0d47a1);
                     padding:32px 40px;text-align:center;">
            <div style="font-size:2.5rem;margin-bottom:8px;">✈️</div>
            <h1 style="margin:0;color:#ffffff;font-size:1.6rem;font-weight:700;
                       letter-spacing:-0.02em;">Aria Travel Agent</h1>
            <p style="margin:6px 0 0;color:#90caf9;font-size:0.85rem;
                      letter-spacing:0.06em;text-transform:uppercase;">
              Your AI-Powered Travel Companion</p>
          </td>
        </tr>

        <!-- Subject bar -->
        <tr>
          <td style="background:#e3f2fd;padding:14px 40px;
                     border-bottom:1px solid #bbdefb;">
            <p style="margin:0;color:#1565c0;font-size:0.9rem;font-weight:600;">
              📋 {subject}</p>
            <p style="margin:4px 0 0;color:#90a4ae;font-size:0.78rem;">{now}</p>
          </td>
        </tr>

        <!-- PDF attachment notice -->
        <tr>
          <td style="background:#fff8e1;padding:10px 40px;
                     border-bottom:1px solid #ffe082;">
            <p style="margin:0;color:#f57f17;font-size:0.82rem;">
              📎 <strong>PDF attached</strong> — A beautifully formatted copy
              of this travel plan is attached to this email for offline use.
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 40px;">
            <pre style="margin:0;white-space:pre-wrap;word-wrap:break-word;
                        font-family:'Segoe UI',Arial,sans-serif;
                        font-size:0.92rem;line-height:1.75;
                        color:#263238;">{escaped}</pre>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f5f7fa;padding:20px 40px;text-align:center;
                     border-top:1px solid #e8ecf0;">
            <p style="margin:0;color:#90a4ae;font-size:0.78rem;">
              Sent by <strong>Aria AI Travel Agent</strong>
              &nbsp;·&nbsp; Powered by Azure OpenAI + LangGraph<br/>
              <span style="color:#bdbdbd;">
                This email was generated automatically from your travel query.
              </span>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Build MIME message with HTML body + PDF attachment
# ─────────────────────────────────────────────────────────────────────────────

def _build_mime_message(
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    plain_body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> MIMEMultipart:
    """
    Construct a MIME email with:
      - Plain text fallback
      - Rich HTML body
      - PDF attachment
    """
    # Outer container — 'mixed' allows both alternative body + attachment
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"Aria Travel Agent <{sender}>"
    msg["To"]      = recipient

    # Inner 'alternative' part for plain + HTML body
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(plain_body, "plain", "utf-8"))
    body_part.attach(MIMEText(html_body,  "html",  "utf-8"))
    msg.attach(body_part)

    # PDF attachment
    pdf_part = MIMEBase("application", "pdf")
    pdf_part.set_payload(pdf_bytes)
    encoders.encode_base64(pdf_part)
    pdf_part.add_header(
        "Content-Disposition",
        "attachment",
        filename=pdf_filename,
    )
    pdf_part.add_header("Content-Type", "application/pdf", name=pdf_filename)
    msg.attach(pdf_part)

    return msg


# ─────────────────────────────────────────────────────────────────────────────
# Provider senders
# ─────────────────────────────────────────────────────────────────────────────

def _smtp_send(
    host: str, port: int,
    sender: str, password: str,
    recipient: str, msg: MIMEMultipart,
) -> None:
    """Generic SMTP sender with TLS — works for Gmail and Outlook."""
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [recipient], msg.as_string())


def _send_gmail(
    recipient: str, subject: str,
    html: str, plain: str,
    pdf_bytes: bytes, pdf_filename: str,
) -> None:
    """
    Gmail SMTP (smtp.gmail.com:587).
    EMAIL_SENDER_PASSWORD must be a 16-char App Password — NOT your Gmail login.
    Get one: myaccount.google.com → Security → App passwords
    """
    sender   = os.environ["EMAIL_SENDER_ADDRESS"]
    password = os.environ["EMAIL_SENDER_PASSWORD"]
    msg      = _build_mime_message(sender, recipient, subject, html, plain, pdf_bytes, pdf_filename)
    _smtp_send("smtp.gmail.com", 587, sender, password, recipient, msg)


def _send_outlook(
    recipient: str, subject: str,
    html: str, plain: str,
    pdf_bytes: bytes, pdf_filename: str,
) -> None:
    """Outlook / Hotmail SMTP (smtp.office365.com:587)."""
    sender   = os.environ["EMAIL_SENDER_ADDRESS"]
    password = os.environ["EMAIL_SENDER_PASSWORD"]
    msg      = _build_mime_message(sender, recipient, subject, html, plain, pdf_bytes, pdf_filename)
    _smtp_send("smtp.office365.com", 587, sender, password, recipient, msg)


def _send_sendgrid(
    recipient: str, subject: str,
    html: str, plain: str,
    pdf_bytes: bytes, pdf_filename: str,
) -> None:
    """
    SendGrid HTTP API — 100 emails/day free, no credit card.
    Sign up: https://signup.sendgrid.com/
    EMAIL_SENDER_ADDRESS must be verified in your SendGrid account.
    """
    import base64
    api_key = os.environ["SENDGRID_API_KEY"]
    sender  = os.environ["EMAIL_SENDER_ADDRESS"]

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from"   : {"email": sender, "name": "Aria Travel Agent"},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": plain},
            {"type": "text/html",  "value": html},
        ],
        "attachments": [{
            "content"    : base64.b64encode(pdf_bytes).decode(),
            "type"       : "application/pdf",
            "filename"   : pdf_filename,
            "disposition": "attachment",
        }],
    }

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type" : "application/json",
        },
        json=payload,
        timeout=20,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.text}")


# ─────────────────────────────────────────────────────────────────────────────
# LangChain @tool
# ─────────────────────────────────────────────────────────────────────────────

@tool
def send_email(to_address: str, subject: str, body: str) -> str:
    """
    Send a styled HTML email WITH a PDF attachment to the recipient.

    Use this whenever the user asks to:
      - "email me the itinerary"
      - "send this to <email>"
      - "mail the details to alice@example.com"
      - "forward these results to my inbox"

    The email includes:
      • A beautifully styled HTML body with the travel content
      • A PDF attachment — the same content formatted as a travel document
        that the recipient can save, print, or share offline

    Args:
        to_address : Recipient email address (e.g. "alice@example.com")
        subject    : Email subject (e.g. "Your 5-Day Kyoto Itinerary")
        body       : Full plain-text content — all itinerary details,
                     weather, tips, country info, etc.

    Returns:
        Confirmation with sent status and PDF attachment details,
        or a specific error message if sending failed.
    """
    # ── Validate provider config ───────────────────────────────────────────
    provider = os.getenv("EMAIL_PROVIDER", "gmail").lower().strip()

    requirements = {
        "gmail"   : ["EMAIL_SENDER_ADDRESS", "EMAIL_SENDER_PASSWORD"],
        "outlook" : ["EMAIL_SENDER_ADDRESS", "EMAIL_SENDER_PASSWORD"],
        "sendgrid": ["SENDGRID_API_KEY", "EMAIL_SENDER_ADDRESS"],
    }

    if provider not in requirements:
        return (
            f"⚠️ Unknown EMAIL_PROVIDER '{provider}'.\n"
            "Set it to 'gmail', 'outlook', or 'sendgrid' in your .env file."
        )

    missing = [k for k in requirements[provider] if not os.getenv(k)]
    if missing:
        return (
            f"⚠️ Email not configured. Missing .env keys for {provider.title()}: "
            + ", ".join(missing)
            + "\nSee .env.example for setup instructions."
        )

    # ── Generate PDF ───────────────────────────────────────────────────────
    try:
        from tools.pdf_blob_tool import _build_pdf
        pdf_bytes = _build_pdf(subject, body, to_address)
    except ImportError:
        return (
            "⚠️ PDF generation requires reportlab.\n"
            "Run: pip install reportlab"
        )
    except Exception as e:
        return f"⚠️ PDF generation failed: {type(e).__name__}: {e}"

    # ── Build filename ─────────────────────────────────────────────────────
    import re
    date_str     = datetime.now().strftime("%Y-%m-%d")
    subject_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", subject.strip())[:50]
    pdf_filename = f"Aria_Travel_{subject_slug}_{date_str}.pdf"

    # ── Build email content ────────────────────────────────────────────────
    html_body  = _build_html(subject, body)
    plain_body = textwrap.dedent(body)

    # ── Send ───────────────────────────────────────────────────────────────
    dispatchers = {
        "gmail"   : _send_gmail,
        "outlook" : _send_outlook,
        "sendgrid": _send_sendgrid,
    }

    try:
        dispatchers[provider](to_address, subject, html_body, plain_body, pdf_bytes, pdf_filename)

        size_kb = round(len(pdf_bytes) / 1024, 1)
        return (
            f"✅ Email sent with PDF attachment!\n\n"
            f"  📧 To         : {to_address}\n"
            f"  📋 Subject    : {subject}\n"
            f"  📎 Attachment : {pdf_filename} ({size_kb} KB)\n"
            f"  🚀 Via        : {provider.title()}\n\n"
            f"The recipient will receive the travel details in the email body\n"
            f"AND as a formatted PDF they can save or print. 📬"
        )

    except smtplib.SMTPAuthenticationError:
        if provider == "gmail":
            return (
                "⚠️ Gmail authentication failed.\n"
                "You must use an App Password, not your regular Gmail password.\n"
                "Generate one: myaccount.google.com → Security → App passwords"
            )
        return "⚠️ Email authentication failed. Check EMAIL_SENDER_PASSWORD in .env."
    except smtplib.SMTPException as e:
        return f"⚠️ SMTP error: {e}"
    except RuntimeError as e:
        return f"⚠️ {e}"
    except Exception as e:
        return f"⚠️ Failed to send email: {type(e).__name__}: {e}"
