### 🧠 **Sleep Bot — Internal Maintenance Handbook (Private)**

> **Version:** `v6_full_embed_configsystem`
> **Dev:** Kiyaaaa
> **Goal:** Stability • Easy maintenance • Dynamic configuration via slash commands
> **Stack:** Flask + Discord.py + SQLite

---

## 🚀 Quick Start

If the bot stops or the Render service just redeployed, run:

```bash
python3 skibidi_v6.py
```

The bot will automatically:

1. Launch a Flask server on port `8080`
2. Create routes `/` (for UptimeRobot) and `/healthz` (for Render)
3. Delay 3 seconds to allow Flask to bind the port
4. Start the Discord bot (slash commands auto-sync)

---

## 🧩 Required Environment Variables

Set these in Render Secrets or a `.env` file:

```
TOKEN=discord_bot_token
ROLE_NAME=💤 Hibernate Follower
PORT=8080
```

> ⚙️ **No need to define INACTIVE_DAYS or AUTO_DELETE_ENABLED anymore**
> as the bot reads/writes them automatically from `config.json`.

---

## ⚙️ Dynamic Configuration

The `config.json` stores runtime settings, for example:

```json
{
  "INACTIVE_DAYS": 30,
  "AUTO_DELETE_ENABLED": true
}
```

If the file does not exist, the bot will **automatically create it** with default values.

---

## 🔧 Slash Commands (v6)

| Command               | Description                                                       | Notes                        |
| --------------------- | ----------------------------------------------------------------- | ---------------------------- |
| `/runcheck`           | Manually check inactivity, add “hibernate” role to inactive users | Result shown via embed       |
| `/config_info`        | Display current configuration info                                | Includes role, days, DB      |
| `/setinactive <days>` | Change the required inactive days to add role                     | Saves to `config.json`       |
| `/toggle_autodelete`  | Enable/disable auto-deletion of embeds (after 3s)                 | Saves to `config.json`       |
| `/status`             | Show the number of users currently with the hibernate role        | Visual embed                 |
| `/exportdb`           | Export the `.db` file for backup                                  | Sends SQLite file            |
| `/exportcsv`          | Export a readable CSV                                             | Sends CSV file               |
| `/help`               | Paginated list of commands with icon and thumbnail                | Includes image, fully intact |
| `/list_off`           | List members with the hibernate role                              | Auto-paginated if long       |

> 🔁 All commands retain v5 embed style, with v6 configuration logic added.

---

## 💾 Database: `inactivity.db`

* Auto-created if missing.
* Columns: `member_id`, `guild_id`, `last_seen`, `role_added`.
* Can be exported or reset easily.

### 📤 Manual Backup

```bash
/exportdb
```

### 📊 CSV Export

```bash
/exportcsv
```

---

## 🔁 Scheduled Task

The bot automatically runs inactivity checks every **24 hours**:

* If a user is **offline ≥ INACTIVE_DAYS** → add hibernate role
* If a user is online → update `last_seen`

> Can also run manually via `/runcheck`.

---

## 🧰 Quick Debug

| Issue              | Cause                   | Solution                                  |
| ------------------ | ----------------------- | ----------------------------------------- |
| Bot does not start | Flask not bound yet     | Check `time.sleep(3)`                     |
| Role not added     | Bot lacks permissions   | Grant `Manage Roles`                      |
| Flask logs 503     | Render pinged too early | Ping again after 5s                       |
| Config not saved   | Bot cannot write file   | Check write permissions for `config.json` |
| Embed not deleted  | AUTO_DELETE = false     | Enable via `/toggle_autodelete`           |

---

## ⚙️ Quick Deployment on Render

### 1️⃣ Fork or upload the repo to GitHub

Ensure the repo includes:

```
skibidi_v6.py
requirements.txt
runtime.txt
```

### 2️⃣ Go to [Render.com](https://render.com) → **New + Web Service**

* **Environment:** Python
* **Build Command:** *(leave blank)*
* **Start Command:**

```bash
python3 skibidi_v6.py
```

### 3️⃣ Add Environment Variables:

```
TOKEN=...
ROLE_NAME=💤 Hibernate Follower
PORT=8080
```

### 4️⃣ Keep the bot online with UptimeRobot

* URL: `https://your-service-name.onrender.com/`
* Ping every 5 minutes is sufficient.

---

## 🧹 Light Reset

Delete the database and config, then restart:

```bash
rm inactivity.db config.json
python3 skibidi_v6.py
```

---

## 🧠 Notes

* Flask always starts **before the bot**
* `/healthz` prevents Render from killing the process
* SQLite + JSON config → lightweight and easy to backup
* No need to redeploy after adjusting configuration

---

## 🧩 Suggested Repo Structure

```
/ (root)
├── skibidi_v6.py
├── config.json
├── inactivity.db
├── requirements.txt
├── runtime.txt
├── README_INTERNAL_v6.md
└── .gitignore
```

---

> “The bot doesn’t need power — just enough logic to survive on its own.”
> — Kiyaaaa, 2025

---

If you want, I can also **translate all the internal comments in your Python script into English** so the code + README is fully English-ready for documentation. Do you want me to do that next?
