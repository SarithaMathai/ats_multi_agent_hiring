"""
Email sender — converts a CoordinatorResponse dict into a styled HTML email
and delivers it via SMTP using credentials from configs/settings.py (SMTP_* env vars).

Usage:
    from dashboard.components.email_sender import EmailSender
    sender = EmailSender()
    sender.send_html_report(
        to=["hr@company.com", "cto@company.com"],
        subject="ATS Hiring Analysis",
        response=response_dict,
    )
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self) -> None:
        from configs.settings import settings
        self._cfg = settings.smtp

    # ── Public API ────────────────────────────────────────────────────────────

    def send_html_report(
        self,
        to: list[str],
        subject: str,
        response: dict[str, Any],
        body_override: str | None = None,
    ) -> None:
        """Build and send an HTML email from a CoordinatorResponse dict.

        Args:
            to:            List of recipient email addresses.
            subject:       Email subject line.
            response:      CoordinatorResponse as a dict (from api_client).
            body_override: If provided, replaces the auto-generated HTML body
                           with caller-supplied plain text (wrapped in <pre>).
        Raises:
            RuntimeError: if SMTP credentials are not configured.
            smtplib.SMTPException: on delivery failure.
        """
        if not self._cfg.user or not self._cfg.password:
            raise RuntimeError(
                "SMTP credentials not configured. "
                "Set SMTP_USER and SMTP_PASSWORD in your .env file."
            )

        html = (
            f"<pre style='font-family:monospace'>{body_override}</pre>"
            if body_override
            else _render_html(response)
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self._cfg.from_address or self._cfg.user
        msg["To"]      = ", ".join(to)
        msg.attach(MIMEText(_render_plain(response), "plain"))
        msg.attach(MIMEText(html, "html"))

        self._deliver(msg, to)
        logger.info("Email sent to %s — subject: %s", to, subject)

    # ── SMTP delivery ─────────────────────────────────────────────────────────

    def _deliver(self, msg: MIMEMultipart, to: list[str]) -> None:
        with smtplib.SMTP(self._cfg.host, self._cfg.port, timeout=15) as server:
            if self._cfg.starttls:
                server.starttls()
            server.login(self._cfg.user, self._cfg.password)
            server.sendmail(msg["From"], to, msg.as_string())


# ── Rendering helpers ─────────────────────────────────────────────────────────

def _render_plain(response: dict[str, Any]) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    lines = [
        f"ATS Hiring Analysis Report",
        f"Run ID : {response.get('run_id', 'n/a')}",
        f"Status : {response.get('status', 'n/a')}",
        f"Tokens : {response.get('total_tokens', 0)}",
        "",
        "── Summary ──",
        response.get("summary", ""),
        "",
        "── Top Recommendations ──",
    ]
    for rec in response.get("all_recommendations", [])[:10]:
        lines.append(f"[{rec.get('priority','').upper()}] {rec.get('title','')} — {rec.get('description','')}")
    return "\n".join(lines)


def _render_html(response: dict[str, Any]) -> str:
    """Styled HTML email body."""
    run_id  = response.get("run_id", "n/a")
    status  = response.get("status", "n/a")
    tokens  = response.get("total_tokens", 0)
    latency = response.get("total_latency_ms", 0)
    summary = (response.get("summary", "") or "").replace("\n", "<br>")

    status_color = "#2ecc71" if status == "success" else "#e67e22" if status == "partial" else "#e74c3c"

    recs_html = ""
    priority_colors = {"high": "#e74c3c", "medium": "#e67e22", "low": "#3498db"}
    for rec in response.get("all_recommendations", [])[:10]:
        p     = rec.get("priority", "medium")
        color = priority_colors.get(p, "#888")
        recs_html += (
            f"<tr>"
            f"<td style='padding:6px 10px'>"
            f"<span style='background:{color};color:#fff;border-radius:3px;padding:2px 6px;"
            f"font-size:11px;text-transform:uppercase'>{p}</span></td>"
            f"<td style='padding:6px 10px'><strong>{rec.get('title','')}</strong><br>"
            f"<span style='color:#555;font-size:13px'>{rec.get('description','')}</span></td>"
            f"</tr>"
        )

    agents_html = ""
    skip = {"routing", "evaluation", "optimization"}
    for out in response.get("agent_outputs", []):
        if out.get("agent_name") in skip or out.get("status") == "skipped":
            continue
        conf  = out.get("confidence_score", 0)
        conf_color = "#2ecc71" if conf >= 0.75 else "#e67e22" if conf >= 0.5 else "#e74c3c"
        insights_html = "".join(
            f"<li style='margin:4px 0'>{i}</li>" for i in out.get("insights", [])[:5]
        )
        agents_html += f"""
        <div style='border:1px solid #ddd;border-radius:6px;padding:12px;margin:10px 0'>
          <h3 style='margin:0 0 8px'>{out.get('agent_name','').replace('_',' ').title()}
            <span style='float:right;font-size:13px;color:{conf_color}'>
              confidence {conf:.0%}
            </span>
          </h3>
          <ul style='margin:0;padding-left:18px'>{insights_html}</ul>
        </div>"""

    return f"""
    <html><body style='font-family:Arial,sans-serif;max-width:800px;margin:auto;color:#333'>
      <div style='background:#1a1a2e;color:#fff;padding:20px 30px;border-radius:8px 8px 0 0'>
        <h1 style='margin:0'>ATS Hiring Analysis Report</h1>
        <p style='margin:4px 0;opacity:.7'>Run ID: {run_id} &nbsp;|&nbsp;
           Status: <span style='color:{status_color}'>{status.upper()}</span> &nbsp;|&nbsp;
           {tokens:,} tokens &nbsp;|&nbsp; {latency:.0f} ms</p>
      </div>
      <div style='padding:20px 30px;background:#f9f9f9'>
        <h2>Summary</h2>
        <p style='line-height:1.6'>{summary}</p>
        <h2>Top Recommendations</h2>
        <table style='width:100%;border-collapse:collapse'>{recs_html}</table>
        <h2>Agent Insights</h2>
        {agents_html}
      </div>
      <div style='padding:12px 30px;background:#eee;font-size:12px;color:#888;border-radius:0 0 8px 8px'>
        Generated by ATS Multi-Agent Hiring System &nbsp;|&nbsp; Powered by GPT-4o-mini
      </div>
    </body></html>"""
