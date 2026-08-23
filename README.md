# tracksolace notes

A small personal blog. Public reading, single-admin login to post, Markdown
posts stored in SQLite. Built with the skills in
[45-anti-slop-skills](https://github.com/hainesdrewh/45-anti-slop-skills)
(clean minimal direction).

## Local setup

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
python scripts/hash_password.py   # paste the output into .env as ADMIN_PASSWORD_HASH
python app.py                     # runs on http://127.0.0.1:8773
```

## Deployment

Runs behind nginx as a systemd-managed gunicorn service on the same Oracle
VPS as the existing trading journal, under its own subdomain
(`blog.tracksolace.xyz`) and its own low-privilege service user, so it can't
touch the journal's process, port, or data. All post content is backed up
nightly to a separate private repository; this repository holds only
application code, no post content and no secrets.
