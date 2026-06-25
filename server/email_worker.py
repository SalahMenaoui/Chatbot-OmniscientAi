import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from server import models

log = logging.getLogger(__name__)

try:
    import anthropic as _anthropic
    import resend as _resend
    _claude    = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    _resend.api_key = os.environ.get("RESEND_API_KEY", "")
    _ready = bool(os.environ.get("ANTHROPIC_API_KEY")) and bool(os.environ.get("RESEND_API_KEY"))
except Exception:
    _ready = False


def _generate_email(visitor_name: str, messages: list, tone: str, client_name: str):
    tone_labels = {
        "professional": "professionnel et formel",
        "friendly":     "chaleureux et amical",
        "urgent":       "urgent et incitatif à l'action",
    }
    tone_label = tone_labels.get(tone, "professionnel")
    conv_lines = "\n".join(
        f"{'Visiteur' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    )
    prompt = (
        f"Tu es un assistant marketing pour {client_name}. "
        f"Un visiteur nommé {visitor_name} a chatté avec notre assistant virtuel "
        f"mais n'a pas encore pris contact directement.\n\n"
        f"Conversation :\n{conv_lines}\n\n"
        f"Génère un email de suivi en français avec un ton {tone_label}, "
        f"personnalisé selon la conversation. L'email doit :\n"
        f"- Rappeler brièvement le sujet de la conversation\n"
        f"- Offrir de l'aide ou inviter à prendre contact\n"
        f"- Être court (3 paragraphes max)\n\n"
        f"Format EXACT :\nOBJET: <sujet en une ligne>\n---\n<corps de l'email>"
    )
    resp = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if "---" in text:
        parts   = text.split("---", 1)
        subject = parts[0].replace("OBJET:", "").strip()
        body    = parts[1].strip()
    else:
        subject = f"Suite à votre conversation avec {client_name}"
        body    = text
    return subject, body


def _send_followup_emails():
    if not _ready:
        return
    pending = models.get_conversations_pending_email()
    for conv in pending:
        try:
            messages = models.get_messages(conv["conv_id"])
            if not messages:
                continue
            subject, body = _generate_email(
                conv["visitor_name"], messages, conv["tone"], conv["client_name"]
            )
            _resend.Emails.send({
                "from":    f"{conv['from_name']} <{conv['from_email']}>",
                "to":      [conv["visitor_email"]],
                "subject": subject,
                "text":    body,
            })
            with models.get_conn() as db:
                db.execute(
                    """INSERT INTO email_logs
                           (visitor_id, conversation_id, status, subject, body_preview)
                       VALUES (?, ?, 'sent', ?, ?)""",
                    (conv["visitor_id"], conv["conv_id"], subject, body[:200]),
                )
            log.info("Email sent to %s (conv %d)", conv["visitor_email"], conv["conv_id"])
        except Exception as e:
            log.error("Failed email for conv %d: %s", conv["conv_id"], e)
            try:
                with models.get_conn() as db:
                    db.execute(
                        """INSERT INTO email_logs
                               (visitor_id, conversation_id, status, subject, body_preview)
                           VALUES (?, ?, 'failed', '', ?)""",
                        (conv["visitor_id"], conv["conv_id"], str(e)[:200]),
                    )
            except Exception:
                pass


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(_send_followup_emails, "interval", hours=1, id="email_followup")
    scheduler.start()
    log.info("Email scheduler started.")
    return scheduler
