import os, smtplib, calendar
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import feedparser

FEED_URL = "https://feeds.bbci.co.uk/news/rss.xml"

def now_se():
    return datetime.now(ZoneInfo("Europe/Stockholm"))

def time_window():
    """Från igår 18:00 lokal tid till nu (lokal tid)."""
    end_local = now_se()
    start_local = (end_local - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    return start_local, end_local

def parse_pubdate_local(entry):
    # BBC pubDate är GMT/UTC; feedparser ger published_parsed (UTC struct_time)
    pp = entry.get("published_parsed")
    if not pp:
        return None
    dt_utc = datetime.fromtimestamp(calendar.timegm(pp), tz=timezone.utc)
    return dt_utc.astimezone(ZoneInfo("Europe/Stockholm"))

def collect_items():
    d = feedparser.parse(FEED_URL)
    start_local, end_local = time_window()
    items = []
    for e in d.entries:
        dt_local = parse_pubdate_local(e)
        if not dt_local:
            continue
        if start_local <= dt_local <= end_local:
            items.append({"title": e.title, "link": e.link, "t_local": dt_local})
    items.sort(key=lambda x: x["t_local"], reverse=True)
    return items, start_local, end_local

def build_email(items, start_local, end_local):
    subj = f"BBC – nyheter sedan {start_local.strftime('%Y-%m-%d kl %H:%M')} (antal {len(items)})"

    lines = [
        f"Period: {start_local.strftime('%Y-%m-%d %H:%M')} → {end_local.strftime('%Y-%m-%d %H:%M')} (Europe/Stockholm)",
        f"Källa: {FEED_URL}",
        f"Antal: {len(items)}",
        ""
    ]
    if items:
        for it in items:
            lines.append(f"- {it['t_local'].strftime('%Y-%m-%d %H:%M')} — {it['title']}\n  {it['link']}")
    else:
        lines.append("Inga nya poster i perioden.")
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content(body)
    return msg

def send_email(msg):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USERNAME"]
    pwd  = os.environ["SMTP_PASSWORD"]
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)

def main():
    # Körs av Render Cron 05:00 och 06:00 UTC. Skicka endast när lokal tid faktiskt är 07.
    if now_se().hour != 7:
        return
    items, start_local, end_local = collect_items()
    msg = build_email(items, start_local, end_local)
    send_email(msg)

if __name__ == "__main__":
    main()
