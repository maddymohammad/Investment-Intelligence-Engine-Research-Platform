"""
Email sender: delivers the daily report via SMTP (Gmail) or SendGrid.

Primary:  SMTP with EMAIL_APP_PASSWORD (Gmail App Password)
Fallback: SendGrid API via SENDGRID_API_KEY

Both methods attach the HTML report as the email body and include
the research-only disclaimer in every message.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUBJECT = "Investment Intelligence Report — {date}"
_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


class EmailSender:

    def __init__(self, settings) -> None:
        self.settings = settings

    def send_report(
        self,
        recommendations: list,
        report_path: Optional[str],
        run_date: date,
    ) -> bool:
        """
        Render and send the daily report email.
        Returns True on success, False if skipped or failed.
        """
        if not self.settings.email_recipient:
            logger.info("Email skipped — EMAIL_RECIPIENT not set")
            return False

        html_body = self._render_email(recommendations, run_date)
        subject = _SUBJECT.format(date=run_date)

        if self.settings.email_app_password and self.settings.email_sender:
            return self._send_smtp(subject, html_body)

        if self.settings.sendgrid_api_key:
            return self._send_sendgrid(subject, html_body)

        logger.info("Email skipped — no credentials configured")
        return False

    # ─── Rendering ────────────────────────────────────────────────────────────

    def _render_email(self, recommendations: list, run_date: date) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader
            template_dir = Path(__file__).parent.parent.parent / "templates"
            env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = env.get_template("email.html.j2")
            return template.render(
                recommendations=recommendations,
                run_date=run_date,
                market={},  # market context not needed for email summary
            )
        except Exception as e:
            logger.error("Email template render failed: %s", e)
            return self._fallback_html(recommendations, run_date)

    def _render_email_with_market(
        self, recommendations: list, run_date: date, market_ctx: dict
    ) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader
            template_dir = Path(__file__).parent.parent.parent / "templates"
            env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = env.get_template("email.html.j2")
            return template.render(
                recommendations=recommendations,
                run_date=run_date,
                market=market_ctx,
            )
        except Exception as e:
            logger.error("Email template render failed: %s", e)
            return self._fallback_html(recommendations, run_date)

    def _fallback_html(self, recommendations: list, run_date: date) -> str:
        lines = [
            "<html><body>",
            "<p><strong>RESEARCH ONLY — NOT INVESTMENT ADVICE</strong></p>",
            f"<h2>Investment Intelligence Report — {run_date}</h2>",
        ]
        if not recommendations:
            lines.append("<p>No recommendations today.</p>")
        for rec in recommendations:
            lines += [
                f"<hr><h3>{rec.symbol} — {rec.name} ({rec.cap_category})</h3>",
                f"<p>Score: {rec.composite_score:.1f}/100 | Price: ₹{rec.entry_price:,.0f}</p>",
                f"<p>{rec.justification.why_selected}</p>",
            ]
        lines.append("</body></html>")
        return "\n".join(lines)

    # ─── SMTP ─────────────────────────────────────────────────────────────────

    def _send_smtp(self, subject: str, html_body: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.settings.email_sender
        msg["To"] = self.settings.email_recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(
                    self.settings.email_sender,
                    self.settings.email_app_password,
                )
                server.sendmail(
                    self.settings.email_sender,
                    self.settings.email_recipient,
                    msg.as_string(),
                )
            logger.info("Email sent via SMTP to %s", self.settings.email_recipient)
            return True
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False

    # ─── SendGrid ─────────────────────────────────────────────────────────────

    def _send_sendgrid(self, subject: str, html_body: str) -> bool:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            sg = sendgrid.SendGridAPIClient(api_key=self.settings.sendgrid_api_key)
            mail = Mail(
                from_email=self.settings.email_sender or "noreply@investment-intelligence.local",
                to_emails=self.settings.email_recipient,
                subject=subject,
                html_content=html_body,
            )
            resp = sg.send(mail)
            if resp.status_code in (200, 202):
                logger.info("Email sent via SendGrid (status %d)", resp.status_code)
                return True
            logger.warning("SendGrid returned status %d", resp.status_code)
            return False
        except Exception as e:
            logger.error("SendGrid send failed: %s", e)
            return False
