# skibidi_fixed_v3_full_embed_v2style.py
import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import sqlite3
from flask import Flask
from waitress import serve
from threading import Thread
import pathlib
import csv
import asyncio

# ===== Path DB =====
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "inactivity.db"

# ===== Config =====
TOKEN = os.getenv("TOKEN")
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"
INACTIVE_DAYS = 30

# ===== Intents =====
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Flask server (ổn định cho UptimeRobot) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "🟢 Bot đang chạy ổn định (Skibidi_v3)!"

@app.route("/healthz")
def healthz():
    # Route riêng cho Render health check (luôn trả 200 OK)
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    try:
        serve(app, host="0.0.0.0", port=port, _quiet=True)
    except Exception as e:
        print(f"⚠️ Flask lỗi: {e}")

# ===== Database =====
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
print(f"🟢 Database SQLite sẵn sàng: {DB_PATH}")

# ===== Helper =====
def make_embed(title: str, description: str = None, color=discord.Color.blue(), *, fields=None, footer=None):
    embed = discord.Embed(title=title, description=description or "", color=color, timestamp=datetime.now(timezone.utc))
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ===== Custom Help Embed (Phoebe style) =====
class FancyHelpCommand(commands.MinimalHelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📖 Hướng dẫn sử dụng Bot",
            description="Dưới đây là danh sách các lệnh khả dụng, chia theo nhóm:",
            color=discord.Color.from_rgb(125, 78, 255)
        )
        bot_avatar = self.context.bot.user.avatar.url if self.context.bot.user and self.context.bot.user.avatar else None
        embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
        embed.set_image(url="https://moewalls.com/wp-content/uploads/2025/03/phoebe-sleeping-wuthering-waves-thumb.jpg")

        for cog, commands_list in mapping.items():
            filtered = await self.filter_commands(commands_list, sort=True)
            if not filtered:
                continue
            embed.add_field(
                name=f"⚙️ {cog.qualified_name if cog else 'Lệnh chung'}",
                value="\n".join(f"**!{cmd.name}** — {cmd.help or 'Không có mô tả'}" for cmd in filtered),
                inline=False
            )

        embed.set_footer(text="💡 Dùng !help <tên lệnh> để xem chi tiết cụ thể.")
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"❔ Chi tiết lệnh: !{command.name}",
            color=discord.Color.green()
        )
        embed.add_field(name="📄 Mô tả", value=command.help or "Không có mô tả", inline=False)
        embed.add_field(name="📦 Cú pháp", value=f"`!{command.name} {command.signature}`", inline=False)
        await self.get_destination().send(embed=embed)

bot.remove_command("help")
bot.help_command = FancyHelpCommand()

# ===== Kiểm tra inactivity =====
async def check_inactivity_once(ctx=None, only_over_30=False):
    now = datetime.now(timezone.utc)
    print(f"🔍 [{now.isoformat()}] Bắt đầu kiểm tra inactivity...")
    total_checked = total_updated = total_role_added = 0
    try:
        conn = get_db_connection()
        c = conn.cursor()
        for guild in bot.guilds:
            role = discord.utils.get(guild.roles, name=ROLE_NAME)
            if not role:
                print(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong '{guild.name}'")
                continue
            for member in guild.members:
                if member.bot:
                    continue
                total_checked += 1
                try:
                    c.execute("SELECT last_seen, role_added FROM inactivity WHERE member_id=?", (str(member.id),))
                    row = c.fetchone()
                    last_seen, role_added = (row["last_seen"], row["role_added"]) if row else (None, 0)

                    if str(member.status) == "offline":
                        c.execute("""
                            INSERT INTO inactivity (member_id, guild_id, last_seen, role_added)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(member_id) DO UPDATE SET last_seen=excluded.last_seen
                        """, (str(member.id), str(guild.id), datetime.now(timezone.utc).isoformat(), role_added))
                        total_updated += 1

                    if last_seen:
                        last_seen_dt = datetime.fromisoformat(last_seen)
                        days_off = (now - last_seen_dt).days
                        if days_off >= INACTIVE_DAYS and role_added == 0:
                            if not only_over_30 or days_off >= INACTIVE_DAYS:
                                await member.add_roles(role)
                                c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                                total_role_added += 1
                                print(f"✅ Gán role '{ROLE_NAME}' cho {member.name} ({days_off} ngày)")
                except Exception as e:
                    print(f"⚠️ Lỗi xử lý {member.name}: {e}")
                if total_checked % 100 == 0:
                    await asyncio.sleep(0.1)
        conn.commit()
    except Exception as e:
        print(f"⚠️ Lỗi trong check_inactivity_once: {e}")
    finally:
        conn.close()
    print(f"✅ Hoàn tất. Checked={total_checked} Updated={total_updated} RoleAdded={total_role_added}")
    if ctx:
        embed = make_embed(
            title="✅ Hoàn tất kiểm tra Inactivity",
            color=discord.Color.green(),
            fields=[
                ("🧾 Tổng kiểm tra", str(total_checked), True),
                ("🔄 Cập nhật last_seen", str(total_updated), True),
                ("✅ Gán role", str(total_role_added), True)
            ],
            footer="Sử dụng !recheck30days để kiểm tra lại những người đã >=30 ngày."
        )
        await ctx.send(embed=embed)

# ===== Task định kỳ =====
@tasks.loop(hours=24)
async def check_inactivity():
    try:
        await check_inactivity_once()
    except Exception as e:
        print(f"⚠️ Lỗi trong task định kỳ: {e}")

# ===== Commands =====
@bot.command(help="Hiển thị thông tin cấu hình hiện tại của bot.")
async def config_info(ctx):
    embed = make_embed(
        title="⚙️ Cấu hình hiện tại",
        color=discord.Color.blurple(),
        fields=[
            ("💤 Tên Role Inactive", ROLE_NAME, True),
            ("📆 Số ngày inactive", str(INACTIVE_DAYS), True),
            ("🗂️ Database", str(DB_PATH.name), True),
            ("🌐 Flask Port", os.environ.get("PORT", "8080"), True),
        ],
        footer="Skibidi Bot v3 Full Embed (Phoebe Style)"
    )
    embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
    await ctx.send(embed=embed)

@bot.command(help="Liệt kê hoặc xuất CSV thành viên offline ≥ INACTIVE_DAYS (mặc định 30 ngày).")
@commands.has_permissions(administrator=True)
async def list_off_30days(ctx, export: str = None):
    guild = ctx.guild
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await ctx.send("✅ Database trống cho server này.")
        return

    now = datetime.now(timezone.utc)
    results = []
    for row in rows:
        member_id = int(row["member_id"])
        last_seen = row["last_seen"]
        if not last_seen:
            continue
        last_seen_dt = datetime.fromisoformat(last_seen)
        days_off = (now - last_seen_dt).days
        if days_off >= INACTIVE_DAYS:
            member = guild.get_member(member_id)
            results.append((member, days_off, last_seen, member_id))

    if not results:
        await ctx.send(f"✅ Không có thành viên nào offline ≥ {INACTIVE_DAYS} ngày.")
        return

    # Nếu xuất CSV
    if export and export.lower() in ("csv", "file"):
        csv_path = BASE_DIR / f"offline_{guild.id}_{INACTIVE_DAYS}d.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["member_id", "member_name", "days_offline", "last_seen"])
            for member, days_off, last_seen, member_id in results:
                name = f"{member.name}#{member.discriminator}" if member else "Không tìm thấy"
                writer.writerow([member_id, name, days_off, last_seen])
        with open(csv_path, "rb") as f:
            await ctx.send(f"📥 Danh sách thành viên offline ≥ {INACTIVE_DAYS} ngày:", file=discord.File(f, filename=csv_path.name))
        os.remove(csv_path)
        return

    # Nếu chỉ hiển thị embed
    per_page = 25
    chunks = [results[i:i+per_page] for i in range(0, len(results), per_page)]
    for i, chunk in enumerate(chunks, start=1):
        lines = []
        for member, days_off, last_seen, member_id in chunk:
            name = f"{member.mention}" if member else f"ID:{member_id}"
            lines.append(f"• {name} — 🕓 {days_off} ngày (last_seen: `{last_seen}`)")
        embed = make_embed(
            title=f"📋 Thành viên offline ≥ {INACTIVE_DAYS} ngày — Trang {i}/{len(chunks)}",
            description="\n".join(lines[:2000]),
            color=discord.Color.gold(),
            footer=f"Tổng: {len(results)} người"
        )
        await ctx.send(embed=embed)

@bot.command(help="Hiển thị danh sách thành viên offline ≥1 ngày.")
async def list_off(ctx):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server này.")
        return

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),))
    rows = c.fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    results = []

    for row in rows:
        member = guild.get_member(int(row["member_id"]))
        if not member or member.bot or str(member.status) != "offline":
            continue
        last_seen = row["last_seen"]
        if not last_seen:
            continue
        last_seen_dt = datetime.fromisoformat(last_seen)
        days_offline = (now - last_seen_dt).days
        if days_offline >= 1:
            results.append(f"• {member.name}#{member.discriminator} — 🕓 {days_offline} ngày offline")

    if results:
        msg = "📋 **Danh sách thành viên offline ≥1 ngày:**\n" + "\n".join(results)
    else:
        msg = "✅ Không có thành viên nào offline lâu."
    await ctx.send(msg)

@bot.command(help="Gỡ role ngủ đông khỏi một thành viên cụ thể.")
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server này.")
        return

    try:
        await member.remove_roles(role)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE inactivity SET role_added=0 WHERE member_id=?", (str(member.id),))
        conn.commit()
        conn.close()
        await ctx.send(f"✅ Đã gỡ role '{ROLE_NAME}' khỏi {member.name}.")
    except Exception as e:
        await ctx.send(f"⚠️ Lỗi khi gỡ role: {e}")

@bot.command(help="Xuất database inactivity thành file CSV có tên người dùng")
@commands.has_permissions(administrator=True)
async def exportcsv(ctx):
    csv_path = BASE_DIR / "inactivity_export.csv"
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen, role_added FROM inactivity")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await ctx.send("⚠️ Database trống.")
        return

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["member_id", "member_name", "guild_id", "last_seen", "role_added"])
        for row in rows:
            guild = bot.get_guild(int(row["guild_id"]))
            member = guild.get_member(int(row["member_id"])) if guild else None
            name = f"{member.name}#{member.discriminator}" if member else "Không tìm thấy"
            writer.writerow([row["member_id"], name, row["guild_id"], row["last_seen"], row["role_added"]])
    with open(csv_path, "rb") as f:
        await ctx.send(file=discord.File(f, filename="inactivity_export.csv"))
    os.remove(csv_path)

@bot.command(help="Chạy kiểm tra inactivity ngay lập tức")
@commands.has_permissions(administrator=True)
async def runcheck(ctx):
    await ctx.send(embed=make_embed(title="🔎 Đang kiểm tra...", color=discord.Color.blue()))
    await check_inactivity_once(ctx)
    await ctx.send(embed=make_embed(title="✅ Hoàn tất kiểm tra thủ công", color=discord.Color.green()))

@bot.command(help="Kiểm tra lại những người đã offline >= 30 ngày")
@commands.has_permissions(administrator=True)
async def recheck30days(ctx):
    await ctx.send(embed=make_embed(title="🔁 Đang kiểm tra lại những người đã offline ≥ 30 ngày...", color=discord.Color.blue()))
    await check_inactivity_once(ctx, only_over_30=True)
    await ctx.send(embed=make_embed(title="✅ Hoàn tất recheck", color=discord.Color.green()))

@bot.command(help="Gửi file database SQLite (.db)")
@commands.has_permissions(administrator=True)
async def exportdb(ctx):
    if os.path.exists(DB_PATH):
        await ctx.send(file=discord.File(DB_PATH))
    else:
        await ctx.send("❌ Không tìm thấy file database.")

@bot.command(help="Kiểm tra bot có hoạt động không")
async def test(ctx):
    embed = make_embed(
        title="🧪 Bot Test",
        description="✅ Bot hoạt động bình thường và tự kiểm tra inactivity mỗi 24 giờ.",
        color=discord.Color.green(),
        fields=[("🕓 Lịch kiểm tra", "24 giờ/lần", True)],
        footer="Dùng !runcheck để kiểm tra ngay."
    )
    embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
    await ctx.send(embed=embed)

# ===== Event =====
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    if not check_inactivity.is_running():
        check_inactivity.start()
        print("🟢 Task check_inactivity đã start")

# ===== Run App =====
if __name__ == "__main__":
    from threading import Thread
    import time

    print("🟢 Khởi động Flask server...")
    Thread(target=run_flask, daemon=True).start()
    time.sleep(3)  # Đợi Flask bind port

    print("🟢 Flask sẵn sàng, khởi chạy bot...")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Thiếu TOKEN trong biến môi trường!")
