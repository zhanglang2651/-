"""账号体系：注册 / 登录 / 会话 / 邮箱验证码。

安全要点：
- 密码用 PBKDF2-HMAC-SHA256 加盐 20 万轮，数据库里不存明文
- 验证码 5 分钟过期、一次性消费、同邮箱 60 秒内不可重复发送
- 未配置 SMTP 时进入「开发模式」：不真发信，把验证码回传给前端，保证本地可用
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from app.config import settings
from app.services import db

CODE_TTL_SECONDS = 300
CODE_RESEND_SECONDS = 60
TOKEN_TTL_DAYS = settings.session_days


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _hash(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return salt, digest.hex()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    """只允许指定域名（默认 163.com），返回错误信息，空串表示通过。"""
    email = normalize_email(email)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{4,31}@[a-z0-9.-]+\.[a-z]{2,}", email):
        return "邮箱格式不正确"
    domain = email.split("@")[-1]
    if domain != settings.allowed_email_domain:
        return f"目前仅支持 @{settings.allowed_email_domain} 邮箱注册"
    return ""


def validate_password(pwd: str) -> str:
    if len(pwd or "") < 8:
        return "密码至少 8 位"
    if len(pwd) > 64:
        return "密码过长"
    if not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        return "密码需同时包含字母和数字"
    return ""


# ---------------------------------------------------------------- 邮件
def _send_mail_sync(to: str, subject: str, html: str) -> None:
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("云游文旅助手", settings.smtp_user))
    msg["To"] = to
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as s:
        s.login(settings.smtp_user, settings.smtp_auth_code)
        s.sendmail(settings.smtp_user, [to], msg.as_string())


async def issue_code(email: str, purpose: str = "register") -> dict[str, Any]:
    """发送验证码。返回 {sent, dev_mode, code?}"""
    email = normalize_email(email)
    err = validate_email(email)
    if err:
        return {"ok": False, "message": err}

    recent = db.query_one(
        "SELECT created_at FROM verify_codes WHERE email=? ORDER BY id DESC LIMIT 1", (email,)
    )
    if recent:
        elapsed = (_now() - _parse(recent["created_at"])).total_seconds()
        if elapsed < CODE_RESEND_SECONDS:
            return {"ok": False, "message": f"发送太频繁，请 {int(CODE_RESEND_SECONDS - elapsed)} 秒后重试"}

    code = f"{random.randint(0, 999999):06d}"
    db.execute(
        "INSERT INTO verify_codes (email, code, purpose, expires_at, created_at) VALUES (?,?,?,?,?)",
        (email, code, purpose, _iso(_now() + timedelta(seconds=CODE_TTL_SECONDS)), _iso(_now())),
    )

    if not settings.mail_ready:
        # 开发模式：不发信，验证码随响应返回，便于本地跑通
        return {"ok": True, "sent": False, "dev_mode": True, "code": code,
                "message": "未配置 SMTP，已进入开发模式（验证码直接返回）"}

    html = f"""<div style="font-family:system-ui;padding:24px;background:#f6f8fb">
      <div style="max-width:420px;margin:auto;background:#fff;border-radius:14px;padding:28px">
        <h2 style="margin:0 0 6px;color:#0f172a">云游 · 文旅助手</h2>
        <p style="color:#64748b;font-size:13px;margin:0 0 20px">你正在注册/登录账号，验证码 5 分钟内有效</p>
        <div style="font-size:32px;letter-spacing:10px;font-weight:700;color:#0d9488;
             background:#f0fdfa;border-radius:10px;padding:16px;text-align:center">{code}</div>
        <p style="color:#94a3b8;font-size:12px;margin-top:20px">如果不是你本人操作，请忽略这封邮件。</p>
      </div></div>"""
    try:
        await asyncio.to_thread(_send_mail_sync, email, "云游 · 注册验证码", html)
        return {"ok": True, "sent": True, "dev_mode": False, "message": "验证码已发送，请查收邮箱"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"邮件发送失败：{exc}。请检查 SMTP_USER / SMTP_AUTH_CODE 配置"}


def consume_code(email: str, code: str, purpose: str = "register") -> bool:
    email = normalize_email(email)
    row = db.query_one(
        "SELECT * FROM verify_codes WHERE email=? AND code=? AND purpose=? AND used=0 "
        "ORDER BY id DESC LIMIT 1", (email, (code or "").strip(), purpose))
    if not row:
        return False
    if _parse(row["expires_at"]) < _now():
        return False
    db.execute("UPDATE verify_codes SET used=1 WHERE id=?", (row["id"],))
    return True


# ---------------------------------------------------------------- 账号
def register(email: str, password: str, code: str,
             city_id: str = "", city_name: str = "", nickname: str = "") -> dict[str, Any]:
    email = normalize_email(email)
    for err in (validate_email(email), validate_password(password)):
        if err:
            return {"ok": False, "message": err}

    if db.query_one("SELECT id FROM users WHERE email=?", (email,)):
        return {"ok": False, "message": "该邮箱已注册，请直接登录"}

    if not consume_code(email, code, "register"):
        return {"ok": False, "message": "验证码错误或已过期"}

    salt, pwd_hash = _hash(password)
    uid = db.execute(
        "INSERT INTO users (email, pwd_hash, pwd_salt, nickname, city_id, city_name, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (email, pwd_hash, salt, nickname or email.split("@")[0], city_id, city_name, _iso(_now())),
    )
    return {"ok": True, "token": _new_session(uid), "user": _public(uid)}


def login(email: str, password: str) -> dict[str, Any]:
    email = normalize_email(email)
    row = db.query_one("SELECT * FROM users WHERE email=?", (email,))
    if not row:
        return {"ok": False, "message": "邮箱或密码错误"}
    _, digest = _hash(password, row["pwd_salt"])
    if not secrets.compare_digest(digest, row["pwd_hash"]):
        return {"ok": False, "message": "邮箱或密码错误"}
    db.execute("UPDATE users SET last_login=? WHERE id=?", (_iso(_now()), row["id"]))
    return {"ok": True, "token": _new_session(row["id"]), "user": _public(row["id"])}


def _new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?,?,?,?)",
        (token, user_id, _iso(_now() + timedelta(days=TOKEN_TTL_DAYS)), _iso(_now())),
    )
    return token


def _public(user_id: int) -> dict[str, Any]:
    u = db.query_one("SELECT id,email,nickname,city_id,city_name,created_at FROM users WHERE id=?",
                     (user_id,))
    return u or {}


def user_from_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    row = db.query_one("SELECT * FROM sessions WHERE token=?", (token,))
    if not row:
        return None
    if _parse(row["expires_at"]) < _now():
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return _public(row["user_id"])


def logout(token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token=?", (token,))


def update_city(user_id: int, city_id: str, city_name: str) -> dict[str, Any]:
    db.execute("UPDATE users SET city_id=?, city_name=? WHERE id=?", (city_id, city_name, user_id))
    return _public(user_id)


# ---------------------------------------------------------------- 行程收藏
def save_plan(user_id: int, payload: dict[str, Any]) -> str:
    import json
    import uuid

    plan = payload.get("plan") or {}
    pid = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO plans (id,user_id,title,city,days,summary,payload,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (pid, user_id, plan.get("theme") or "未命名行程", plan.get("city") or "",
         int(plan.get("days") or 0), (plan.get("summary") or "")[:200],
         json.dumps(payload, ensure_ascii=False), _iso(_now())),
    )
    return pid


def list_plans(user_id: int) -> list[dict[str, Any]]:
    import json

    rows = db.query_all(
        "SELECT id,title,city,days,summary,created_at,share_token,is_public FROM plans "
        "WHERE user_id=? ORDER BY created_at DESC",
        (user_id,))
    return rows


def get_plan(user_id: int, plan_id: str) -> dict[str, Any] | None:
    import json

    row = db.query_one("SELECT * FROM plans WHERE id=? AND user_id=?", (plan_id, user_id))
    if not row:
        return None
    row["payload"] = json.loads(row["payload"])
    return row


def delete_plan(user_id: int, plan_id: str) -> bool:
    row = db.query_one("SELECT id FROM plans WHERE id=? AND user_id=?", (plan_id, user_id))
    if not row:
        return False
    db.execute("DELETE FROM plans WHERE id=?", (plan_id,))
    return True


# ---------------------------------------------------------------- 分享
def share_plan(user_id: int, plan_id: str) -> str | None:
    """生成（或复用）分享 token，并把行程标记为公开只读。"""
    row = db.query_one("SELECT id, share_token FROM plans WHERE id=? AND user_id=?",
                       (plan_id, user_id))
    if not row:
        return None
    token = row.get("share_token") or secrets.token_urlsafe(9)
    db.execute("UPDATE plans SET share_token=?, is_public=1 WHERE id=?", (token, plan_id))
    return token


def unshare_plan(user_id: int, plan_id: str) -> bool:
    row = db.query_one("SELECT id FROM plans WHERE id=? AND user_id=?", (plan_id, user_id))
    if not row:
        return False
    db.execute("UPDATE plans SET is_public=0 WHERE id=?", (plan_id,))
    return True


def get_shared(token: str) -> dict[str, Any] | None:
    import json

    row = db.query_one(
        "SELECT p.*, u.nickname FROM plans p JOIN users u ON u.id=p.user_id "
        "WHERE p.share_token=? AND p.is_public=1", (token,))
    if not row:
        return None
    row["payload"] = json.loads(row["payload"])
    row.pop("user_id", None)
    return row


def plan_meta(user_id: int, plan_id: str) -> dict[str, Any] | None:
    return db.query_one(
        "SELECT id,share_token,is_public,title,city,days FROM plans WHERE id=? AND user_id=?",
        (plan_id, user_id))


# ---------------------------------------------------------------- 重置密码
def reset_password(email: str, code: str, new_password: str) -> dict[str, Any]:
    email = normalize_email(email)
    err = validate_email(email) or validate_password(new_password)
    if err:
        return {"ok": False, "message": err}
    row = db.query_one("SELECT id FROM users WHERE email=?", (email,))
    if not row:
        return {"ok": False, "message": "该邮箱尚未注册"}
    if not consume_code(email, code, "reset"):
        return {"ok": False, "message": "验证码错误或已过期"}
    salt, pwd_hash = _hash(new_password)
    db.execute("UPDATE users SET pwd_hash=?, pwd_salt=? WHERE id=?", (pwd_hash, salt, row["id"]))
    # 旧会话全部失效
    db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    return {"ok": True, "message": "密码已重置，请用新密码登录"}
