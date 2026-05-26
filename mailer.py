"""
mailer.py — Send location-share emails via Gmail SMTP.

Required .env variables:
    GMAIL_USER         your-address@gmail.com
    GMAIL_APP_PASSWORD 16-char app password (not your normal Gmail password)
    BASE_URL           public base URL of this server, e.g. http://127.0.0.1:8000
                       (used to build the live-tracking link in the email)

How to get a Gmail App Password:
    1. Enable 2-Step Verification on your Google account.
    2. Go to: https://myaccount.google.com/apppasswords
    3. Create a new app password → copy the 16-character code into .env.
"""

import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Helpers ───────────────────────────────────────────────────────────────────

def _battery_color(level: float) -> str:
    pct = level * 100
    if pct <= 20:
        return "#dc2626"   # red
    if pct <= 50:
        return "#d97706"   # amber
    return "#16a34a"       # green


def _fmt_time(iso: str | None) -> str:
    if not iso:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso


# ── Main entry-point ──────────────────────────────────────────────────────────

def send_location_email(
    *,
    sender_name: str,
    recipient_email: str,
    latitude: float,
    longitude: float,
    battery_level: float,       # 0.0 – 1.0
    battery_charging: bool,
    last_seen: str | None,
    share_url: str,             # full URL to the live-tracking page
) -> None:
    """
    Send a location-share email.  Raises ValueError if env vars are missing,
    or smtplib.SMTPException on delivery failure.
    """
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    _PLACEHOLDER = "your_16_char_app_password_here"
    if not gmail_user or not gmail_pass or gmail_pass == _PLACEHOLDER:
        raise ValueError(
            "Gmail App Password not configured.\n\n"
            "Steps to fix:\n"
            "  1. Go to → https://myaccount.google.com/apppasswords\n"
            "     (You must have 2-Step Verification ON — check at\n"
            "      https://myaccount.google.com/signinoptions/two-step-verification)\n"
            "  2. Under 'App name' type: Mapiopidia  → click Create\n"
            "  3. Copy the 16-character password Google shows you\n"
            "  4. Open the .env file and replace the placeholder:\n"
            "       GMAIL_APP_PASSWORD=paste_the_16_chars_here\n"
            "  5. Restart the server"
        )

    pct          = int(round(battery_level * 100))
    bat_color    = _battery_color(battery_level)
    bat_icon     = "⚡" if battery_charging else "🔋"
    bat_status   = "Charging" if battery_charging else "On battery"
    maps_url     = f"https://www.google.com/maps?q={latitude},{longitude}&z=15"
    osm_url      = (
        f"https://www.openstreetmap.org/"
        f"?mlat={latitude}&mlon={longitude}#map=15/{latitude}/{longitude}"
    )
    shared_at    = _fmt_time(last_seen)

    subject = f"📍 {sender_name} is sharing their location with you"

    # ── HTML body ─────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f6f5f0;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f6f5f0;padding:30px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:16px;overflow:hidden;
                  box-shadow:0 8px 30px rgba(0,0,0,.09);">

      <!-- Header -->
      <tr>
        <td style="background:linear-gradient(120deg,#0f766e,#178f87);
                   padding:28px 32px;text-align:center;">
          <h1 style="margin:0;color:#fff;font-size:1.6rem;letter-spacing:-.5px;">
            📍 Mapiopidia
          </h1>
          <p style="margin:6px 0 0;color:#ccefec;font-size:.95rem;">
            Live Location Share
          </p>
        </td>
      </tr>

      <!-- Greeting -->
      <tr>
        <td style="padding:28px 32px 0;">
          <p style="margin:0;font-size:1.05rem;color:#1f2a1f;">
            <strong>{sender_name}</strong> is sharing their current location
            with you via <strong>Mapiopidia</strong>.
          </p>
        </td>
      </tr>

      <!-- Coordinates card -->
      <tr>
        <td style="padding:20px 32px 0;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f0f9f8;border:1px solid #a7d8d1;
                        border-radius:12px;padding:18px 20px;">
            <tr>
              <td>
                <p style="margin:0 0 4px;font-size:.8rem;color:#55635a;
                          text-transform:uppercase;letter-spacing:.06em;">
                  Current Location
                </p>
                <p style="margin:0;font-size:1.15rem;font-weight:700;
                          color:#0f766e;font-family:monospace;">
                  {latitude:.6f},&nbsp;{longitude:.6f}
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- Battery card -->
      <tr>
        <td style="padding:14px 32px 0;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#fffbf0;border:1px solid #fde68a;
                        border-radius:12px;padding:16px 20px;">
            <tr>
              <td style="width:50%;">
                <p style="margin:0 0 4px;font-size:.8rem;color:#55635a;
                          text-transform:uppercase;letter-spacing:.06em;">
                  Battery
                </p>
                <p style="margin:0;font-size:1.1rem;font-weight:700;
                          color:{bat_color};">
                  {bat_icon} {pct}% &mdash; {bat_status}
                </p>
              </td>
              <td style="width:50%;text-align:right;vertical-align:bottom;">
                <p style="margin:0;font-size:.8rem;color:#55635a;">
                  Last updated<br/>
                  <strong style="color:#1f2a1f;">{shared_at}</strong>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- CTA buttons -->
      <tr>
        <td style="padding:24px 32px 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding-right:8px;" width="50%">
                <a href="{share_url}"
                   style="display:block;text-align:center;background:linear-gradient(120deg,#0f766e,#178f87);
                          color:#fff;text-decoration:none;border-radius:10px;
                          padding:13px 10px;font-weight:700;font-size:.95rem;">
                  🗺️ View Live Location
                </a>
              </td>
              <td style="padding-left:8px;" width="50%">
                <a href="{maps_url}"
                   style="display:block;text-align:center;background:#fff;
                          color:#0f766e;text-decoration:none;border-radius:10px;
                          padding:13px 10px;font-weight:700;font-size:.95rem;
                          border:2px solid #0f766e;">
                  📌 Open in Google Maps
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- OpenStreetMap fallback -->
      <tr>
        <td style="padding:10px 32px 0;text-align:center;">
          <a href="{osm_url}"
             style="font-size:.82rem;color:#55635a;text-decoration:underline;">
            Open in OpenStreetMap instead
          </a>
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="padding:28px 32px 28px;border-top:1px solid #e5e7eb;margin-top:24px;">
          <p style="margin:0;font-size:.8rem;color:#9ca3af;text-align:center;">
            Sent via <strong>Mapiopidia</strong> &mdash; Shortest Route Finder &amp; Device Tracker<br/>
            If you didn&apos;t expect this email, you can safely ignore it.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

    # ── Plain-text fallback ───────────────────────────────────────────────────
    text = (
        f"{sender_name} is sharing their location with you via Mapiopidia.\n\n"
        f"Coordinates : {latitude:.6f}, {longitude:.6f}\n"
        f"Battery     : {bat_icon} {pct}% ({bat_status})\n"
        f"Last seen   : {shared_at}\n\n"
        f"View live location : {share_url}\n"
        f"Open in Google Maps: {maps_url}\n"
    )

    # ── Build message ─────────────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Mapiopidia <{gmail_user}>"
    msg["To"]      = recipient_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    # ── Send via Gmail SMTP (port 587 + STARTTLS) ─────────────────────────────
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient_email, msg.as_string())
    except smtplib.SMTPAuthenticationError:
        raise ValueError(
            "Gmail login failed. Your App Password is wrong or not set up yet.\n\n"
            "Follow these steps:\n"
            "  1. Enable 2-Step Verification → https://myaccount.google.com/security\n"
            "  2. Create an App Password     → https://myaccount.google.com/apppasswords\n"
            "  3. Paste the 16-char code into GMAIL_APP_PASSWORD in your .env file\n"
            "  4. Restart the server"
        )
    except smtplib.SMTPRecipientsRefused:
        raise ValueError(f"Recipient address '{recipient_email}' was rejected by Gmail.")
    except smtplib.SMTPException as exc:
        raise ValueError(f"SMTP error: {exc}") from exc
