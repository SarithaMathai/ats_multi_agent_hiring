"""
Page 4 — Email Stakeholders

Reads the last analysis result from st.session_state["last_response"]
(populated by the Analysis page), lets the user customise subject and
recipients, previews the formatted report, then sends via SMTP.
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

from dashboard.components.email_sender import EmailSender, _render_plain

st.set_page_config(page_title="Email Stakeholders | ATS Insights", layout="wide", page_icon="📧")
st.title("📧 Email Stakeholders")
st.caption("Send the latest analysis report to HR leadership or hiring managers.")

# ── Guard: need a completed analysis first ────────────────────────────────────

if "last_response" not in st.session_state:
    st.warning("No analysis result yet. Go to the **Analysis** page, run a query, then come back.")
    st.stop()

response: dict = st.session_state["last_response"]
run_id  = response.get("run_id", "n/a")
status  = response.get("status", "n/a")
tokens  = response.get("total_tokens", 0)

st.success(f"Analysis loaded — run_id: `{run_id}` · status: `{status}` · {tokens:,} tokens")

# ── Email compose form ────────────────────────────────────────────────────────

col_form, col_preview = st.columns([1, 2])

with col_form:
    st.subheader("Compose")

    subject = st.text_input(
        "Subject",
        value=f"ATS Hiring Analysis Report — run {run_id}",
    )
    recipients_raw = st.text_input(
        "Recipients (comma-separated)",
        placeholder="hr@company.com, cto@company.com",
    )
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    # SMTP config status
    try:
        from configs.settings import settings
        cfg = settings.smtp
        smtp_configured = bool(cfg.user and cfg.password)
    except Exception:
        smtp_configured = False

    if not smtp_configured:
        st.warning(
            "SMTP not configured. Add `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` "
            "to your `.env` file to enable email sending."
        )

    send_btn = st.button(
        "Send Email",
        type="primary",
        disabled=(not recipients or not smtp_configured),
    )

    # Quick SMTP settings display
    with st.expander("SMTP Settings"):
        if smtp_configured:
            st.caption(f"Host: {cfg.host}:{cfg.port}")
            st.caption(f"From: {cfg.from_address or cfg.user}")
            st.caption(f"STARTTLS: {cfg.starttls}")
        else:
            st.code(
                "SMTP_HOST=smtp.gmail.com\n"
                "SMTP_PORT=587\n"
                "SMTP_USER=your-email@gmail.com\n"
                "SMTP_PASSWORD=your-app-password\n"
                "SMTP_FROM=ats-system@yourdomain.com\n"
                "SMTP_STARTTLS=true",
                language="ini",
            )

with col_preview:
    st.subheader("Report Preview (editable)")
    default_preview = _render_plain(response)
    preview_text = st.text_area(
        "Edit before sending",
        value=default_preview,
        height=420,
    )

# ── Send ──────────────────────────────────────────────────────────────────────

if send_btn and recipients:
    with st.spinner(f"Sending to {', '.join(recipients)}…"):
        try:
            sender = EmailSender()
            sender.send_html_report(
                to=recipients,
                subject=subject,
                response=response,
                body_override=preview_text if preview_text != default_preview else None,
            )
            st.success(f"Email sent to: {', '.join(recipients)}")
            st.balloons()
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Failed to send email: {exc}")
            st.caption("Check your SMTP credentials and that your Gmail account has App Passwords enabled.")
