"""
skibidi_v5_slash_autodelete.py
Phiên bản Slash Commands + Flask uptime + Auto-delete embed khi có người nhắn.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
from waitress import serve
from datetime import datetime, timezone
import sqlite3
import pathlib
import asyncio
import csv

# ===== Path & Config =====
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "inactivity.db"
TOKEN = os.getenv("TOKEN")
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"
INACTIVE_DAYS = 30

# ===== Intents =====
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.guilds = True
intents.message_content = True  # cần để nhận messageCreate event

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== Flask (Render / UptimeRobot) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "🟢 Skibidi v5 slash đang chạy!"

@app.route("/healthz")
def healthz():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    serve(app, host="0.0.0.0", port=port, _quiet=True)

# ===== Database setup =====
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inactivity (
        member_id TEXT PRIMARY KEY,
        guild_id TEXT,
        last_seen TEXT,
        role_added INTEGER DEFAULT 0
    )
    """)

# ===== Helper =====
def make_embed(title: str, description: str = None, color=discord.Color.blurple(), *, fields=None, footer=None):
    embed = discord.Embed(title=title, description=description or "", color=color, timestamp=datetime.now(timezone.utc))
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ===== Lưu ID embed cuối mỗi channel =====
last_command_msg_id = {}

# ===== Auto-delete embed (có delay để tránh spam Render) =====
delete_timers = {}

@bot.event
async def on_message(message: discord.Message):
    """Tự động xóa embed sau 3 giây nếu có người gửi tin nhắn mới."""
    if message.author.bot:
        return

    if message.channel.id in last_command_msg_id:
        # Nếu đã có timer trước -> hủy (debounce)
        if message.channel.id in delete_timers:
            delete_timers[message.channel.id].cancel()

        async def delayed_delete(channel_id):
            await asyncio.sleep(3)  # Đợi 3 giây để giảm tải Render & tránh rate limit
            try:
                old_msg_id = last_command_msg_id.pop(channel_id, None)
                if old_msg_id:
                    old_msg = await message.channel.fetch_message(old_msg_id)
                    await old_msg.delete()
                    print(f"🗑️ Đã xóa embed cũ ở #{message.channel.name}")
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"⚠️ Lỗi khi xóa embed trễ: {e}")

        # Tạo task bất đồng bộ và lưu lại
        task = asyncio.create_task(delayed_delete(message.channel.id))
        delete_timers[message.channel.id] = task

# ===== Inactivity logic (cập nhật full trạng thái) =====
async def check_inactivity_once(interaction: discord.Interaction = None, only_over_30=False):
    now = datetime.now(timezone.utc)
    total_checked = total_updated = total_role_added = 0
    conn = get_db_connection()
    c = conn.cursor()

    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if not role:
            continue
        for member in guild.members:
            if member.bot:
                continue
            total_checked += 1

            # Lấy dữ liệu từ DB
            c.execute("SELECT last_seen, role_added FROM inactivity WHERE member_id=?", (str(member.id),))
            row = c.fetchone()
            last_seen, role_added = (row["last_seen"], row["role_added"]) if row else (None, 0)

            # Cập nhật last_seen mọi trạng thái
            c.execute("""
                INSERT INTO inactivity (member_id, guild_id, last_seen, role_added)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(member_id) DO UPDATE SET last_seen=excluded.last_seen
            """, (str(member.id), str(guild.id), now.isoformat(), role_added))
            total_updated += 1

            # Nếu offline và đã đủ INACTIVE_DAYS thì gán role
            if last_seen:
                days = (now - datetime.fromisoformat(last_seen)).days
                if days >= INACTIVE_DAYS and role_added == 0:
                    if not only_over_30 or days >= INACTIVE_DAYS:
                        try:
                            await member.add_roles(role)
                            c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                            total_role_added += 1
                        except Exception as e:
                            print(f"⚠️ Lỗi gán role cho {member}: {e}")

            # Sleep nhẹ để tránh block event loop
            if total_checked % 100 == 0:
                await asyncio.sleep(0.1)

    conn.commit()
    conn.close()

    # Gửi embed báo cáo nếu có interaction
    if interaction:
        embed = make_embed(
            "✅ Hoàn tất kiểm tra Inactivity",
            color=discord.Color.green(),
            fields=[
                ("🧾 Tổng kiểm tra", str(total_checked), True),
                ("🔄 Cập nhật last_seen", str(total_updated), True),
                ("✅ Gán role", str(total_role_added), True)
            ],
            footer="Dùng /recheck30days để kiểm tra lại."
        )
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id

# ===== Task định kỳ =====
@tasks.loop(hours=24)
async def check_inactivity_task():
    try:
        await check_inactivity_once()
    except Exception as e:
        print(f"⚠️ Lỗi trong task định kỳ: {e}")

# ===== Slash commands =====
@tree.command(name="test", description="Kiểm tra bot có hoạt động không.")
async def slash_test(interaction: discord.Interaction):
    embed = make_embed("🧪 Bot Test", "✅ Bot hoạt động bình thường.", color=discord.Color.green())
    await interaction.response.defer()
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="ping", description="Xem độ trễ của bot.")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = make_embed("🏓 Pong!", f"Độ trễ: **{latency}ms**")
    await interaction.response.defer()
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="config_info", description="Hiển thị thông tin cấu hình hiện tại của bot.")
async def slash_config_info(interaction: discord.Interaction):
    embed = make_embed(
        title="⚙️ Cấu hình hiện tại",
        fields=[
            ("💤 Role Inactive", ROLE_NAME, True),
            ("📆 Số ngày inactive", str(INACTIVE_DAYS), True),
            ("🗂️ Database", str(DB_PATH.name), True)
        ],
        footer="Skibidi Bot v5 - Phoebe style"
    )
    embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
    await interaction.response.defer()
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="runcheck", description="Chạy kiểm tra inactivity ngay (admin only).")
@app_commands.checks.has_permissions(administrator=True)
async def slash_runcheck(interaction: discord.Interaction):
    await interaction.response.defer()
    await check_inactivity_once(interaction)

@tree.command(name="recheck30days", description="Kiểm tra lại người offline >= 30 ngày (admin only).")
@app_commands.checks.has_permissions(administrator=True)
async def slash_recheck30days(interaction: discord.Interaction):
    await interaction.response.defer()
    await check_inactivity_once(interaction, only_over_30=True)

@tree.command(name="list_off", description="Liệt kê các thành viên offline ≥1 ngày.")
async def slash_list_off(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc)
    lines = []

    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        c.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),))
        for member_id, last_seen in c.fetchall():
            member = guild.get_member(int(member_id))
            if not member:
                continue
            days = (now - datetime.fromisoformat(last_seen)).days
            if days >= 1:
                lines.append(f"{member.display_name} – offline {days} ngày")

    conn.close()
    desc = "\n".join(lines) if lines else "Không có thành viên offline ≥1 ngày."
    embed = make_embed("📋 Danh sách Offline ≥1 ngày", desc)
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="list_off_30days", description="Liệt kê các thành viên offline ≥30 ngày.")
async def slash_list_off_30days(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc)
    lines = []

    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        c.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),))
        for member_id, last_seen in c.fetchall():
            member = guild.get_member(int(member_id))
            if not member:
                continue
            days = (now - datetime.fromisoformat(last_seen)).days
            if days >= 30:
                lines.append(f"{member.display_name} – offline {days} ngày")

    conn.close()
    desc = "\n".join(lines) if lines else "Không có thành viên offline ≥30 ngày."
    embed = make_embed("📋 Danh sách Offline ≥30 ngày", desc, color=discord.Color.orange())
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="exportdb", description="Xuất file database SQLite (.db)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_exportdb(interaction: discord.Interaction):
    await interaction.response.defer()
    if os.path.exists(DB_PATH):
        await interaction.followup.send(file=discord.File(DB_PATH))
    else:
        embed = make_embed("❌ Lỗi", "Không tìm thấy file database.")
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id

@tree.command(name="exportcsv", description="Xuất dữ liệu inactivity thành file CSV.")
@app_commands.checks.has_permissions(administrator=True)
async def slash_exportcsv(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen, role_added FROM inactivity")
    rows = c.fetchall()
    conn.close()

    if not rows:
        embed = make_embed("❌ Xuất CSV", "Database rỗng, không có dữ liệu để xuất.")
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id
        return

    # Tạo file CSV tạm thời
    csv_file_path = BASE_DIR / f"inactivity_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(["Guild_ID", "Member_ID", "Member_Name", "Last_Seen", "Role_Added"])
        # Dữ liệu
        for member_id, guild_id, last_seen, role_added in rows:
            guild = bot.get_guild(int(guild_id))
            member_name = "Unknown"
            if guild:
                member = guild.get_member(int(member_id))
                if member:
                    member_name = member.display_name
            writer.writerow([guild_id, member_id, member_name, last_seen, role_added])

    # Gửi file lên Discord
    try:
        await interaction.followup.send(file=discord.File(csv_file_path))
    except Exception as e:
        embed = make_embed("❌ Lỗi", f"Không thể gửi file CSV: {e}")
        await interaction.followup.send(embed=embed)

    # Lưu ID message để auto-delete
    last_command_msg_id[interaction.channel_id] = (await interaction.original_response()).id

    # Xóa file CSV tạm thời sau khi gửi
    try:
        os.remove(csv_file_path)
    except Exception as e:
        print(f"⚠️ Không thể xóa file CSV tạm: {e}")

@tree.command(name="help", description="Hiển thị danh sách lệnh của Skibidi Bot.")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = make_embed(
        title="📖 Danh sách lệnh Skibidi Bot",
        desc="Các lệnh hiện có:\n"
             "• `/test` – Kiểm tra bot hoạt động.\n"
             "• `/ping` – Xem độ trễ.\n"
             "• `/config_info` – Thông tin cấu hình.\n"
             "• `/runcheck` – Kiểm tra inactivity thủ công.\n"
             "• `/recheck30days` – Kiểm tra lại người offline ≥30 ngày.\n"
             "• `/list_off` – Danh sách offline ≥1 ngày.\n"
             "• `/list_off_30days` – Danh sách offline ≥30 ngày.\n"
             "• `/exportdb` – Xuất database.\n"
             "• `/exportcsv` – Xuất file CSV.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Skibidi Bot v6 • Phoebe Style 💜")
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id

# ===== Bot Events =====
@bot.event
async def on_ready():
    try:
        await tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"⚠️ Sync lỗi: {e}")
    print(f"🤖 Bot {bot.user} online.")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    if not check_inactivity_task.is_running():
        check_inactivity_task.start()

# ===== Run App =====
async def main():
    from threading import Thread
    import time
    print("🟢 Khởi động Flask...")
    Thread(target=run_flask, daemon=True).start()
    time.sleep(1)
    if TOKEN:
        await bot.start(TOKEN)
    else:
        print("❌ Thiếu TOKEN!")

if __name__ == "__main__":
    asyncio.run(main())
