"""Simple email service for transactional emails (receipts, dunning, trials)."""

import logging

from ..core.config import settings

logger = logging.getLogger("nexus.email")

try:
    import resend

    HAS_RESEND = bool(settings.RESEND_API_KEY)
    if HAS_RESEND:
        resend.api_key = settings.RESEND_API_KEY
except ImportError:
    HAS_RESEND = False

HAS_SMTP = bool(settings.SMTP_HOST and settings.SMTP_USER)


def send_email(to: str, subject: str, html: str) -> bool:
    """Send transactional email via configured provider (Resend > SMTP > mock)."""
    if HAS_RESEND:
        return _send_resend(to, subject, html)
    if HAS_SMTP:
        return _send_smtp(to, subject, html)
    logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}")
    return True


def send_receipt(to: str, tier: str, amount: int, invoice_url: str = "") -> bool:
    """Send payment receipt after successful billing."""
    html = f"""
    <h2>Payment Receipt — Nexus-UGC</h2>
    <p>Thank you for your {tier} subscription.</p>
    <p><b>Amount:</b> ${amount}/month</p>
    <p><b>Date:</b> {__import__("datetime").datetime.now().strftime("%B %d, %Y")}</p>
    """
    if invoice_url:
        html += f'<p><a href="{invoice_url}">View Invoice</a></p>'
    html += "<p>— Nexus-UGC Team</p>"
    return send_email(to, f"Your Nexus-UGC Receipt — ${amount}/mo", html)


def send_dunning_notice(to: str, attempts: int, max_attempts: int = 3) -> bool:
    """Notify user of failed payment — escalate urgency with each attempt."""
    urgency = "final notice" if attempts >= max_attempts else f"attempt {attempts} of {max_attempts}"
    html = f"""
    <h2>Payment {urgency}</h2>
    <p>Your last payment for Nexus-UGC failed.</p>
    <p>Please update your payment method to avoid service interruption.</p>
    <p><a href="{settings.PUBLIC_BASE_URL}/billing.html">Update Payment Method</a></p>
    """
    return send_email(to, f"[{urgency.upper()}] Payment Failed — Nexus-UGC", html)


def send_trial_ending(to: str, tier: str, days_left: int) -> bool:
    """Remind user their trial is ending."""
    html = f"""
    <h2>Trial Ending Soon</h2>
    <p>Your {tier} trial ends in {days_left} day{"s" if days_left != 1 else ""}.</p>
    <p>Subscribe now to keep your access: <a href="{settings.PUBLIC_BASE_URL}/billing.html">Choose a Plan</a></p>
    """
    return send_email(to, f"Trial Ending in {days_left} Days — Nexus-UGC", html)


def _send_resend(to: str, subject: str, html: str) -> bool:
    """Send via Resend API."""
    try:
        import resend

        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM or "noreply@nexusugc.com",
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        return True
    except Exception as e:
        logger.error("Resend send failed: %s", e)
        return False


def _send_smtp(to: str, subject: str, html: str) -> bool:
    """Send via SMTP."""
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(html, "html")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM or "noreply@nexusugc.com"
        msg["To"] = to
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587) as s:
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:
        logger.error("SMTP send failed: %s", e)
        return False


def _has_budget_for_email():
    """Check if email sending is possible."""
    return HAS_RESEND or HAS_SMTP
