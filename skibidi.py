# skibidi_fixed_v2.py
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

# ===== Path cho DB nằm trong repo =====
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "inactivity.db"

# ===== Cấu hình =====
TOKEN = os.getenv("TOKEN")
ROLE_NAME = os.getenv("ROLE_NAME", "💤 Tín Đồ Ngủ Đông")
INACTIVE_DAYS = int(os.getenv("INACTIVE_DAYS", "30"))

# ===== Khởi tạo bot 1 lần với tất cả intents cần thiết =====
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== FLASK SERVER =====
app = Flask(__name__)

@app.route("/")
def home():
    return "🟢 Bot đang chạy!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    serve(app, host="0.0.0.0", port=port, _quiet=True)

# ===== Database thread-safe =====
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ===== Tạo bảng nếu chưa có =====
with get_db_connection() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inactivity (
        member_id TEXT PRIMARY KEY,
        guild_id TEXT,
        last_seen TEXT,
        role_added INTEGER DEFAULT 0
    )
    """)
print(f"🟢 Database SQLite đã sẵn sàng: {DB_PATH}")

# ===== Helper embed =====
def make_embed(title: str, description: str = None, color: discord.Color = discord.Color.blue(), *, fields=None, footer=None):
    embed = discord.Embed(title=title, description=description or "", color=color, timestamp=datetime.now(timezone.utc))
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ===== Fancy Help Command =====
class FancyHelpCommand(commands.MinimalHelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📘 Hướng dẫn sử dụng Bot",
            description="Dưới đây là danh sách các lệnh khả dụng, chia theo nhóm:",
            color=discord.Color.blue()
        )
        bot_avatar = self.context.bot.user.avatar.url if self.context.bot.user and self.context.bot.user.avatar else None
        embed.set_thumbnail(url=bot_avatar or "https://files.catbox.moe/rvvejl.png")
        embed.set_image(url="https://moewalls.com/wp-content/uploads/2025/03/phoebe-sleeping-wuthering-waves-thumb.jpg")

        for cog, commands_list in mapping.items():
            filtered = await self.filter_commands(commands_list, sort=True)
            if not filtered:
                continue
            embed.add_field(
                name=f"⚙️ {cog.qualified_name if cog else 'Lệnh chung'}",
                value="\n".join(
                    f"**!{cmd.name}** — {cmd.help or 'Không có mô tả'}" for cmd in filtered
                ),
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

# Gán help command
bot.remove_command("help")
bot.help_command = FancyHelpCommand()

# ===== Hàm kiểm tra inactivity =====
async def check_inactivity_once(ctx=None, only_over_30=False):
    now = datetime.now(timezone.utc)
    print(f"🔍 [{now.isoformat()}] Bắt đầu kiểm tra thành viên không hoạt động...")
    total_checked = total_updated = total_role_added = 0
    try:
        conn = get_db_connection()
        c = conn.cursor()
        for guild in bot.guilds:
            role = discord.utils.get(guild.roles, name=ROLE_NAME)
            if not role:
                print(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server '{guild.name}'")
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
                        last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
                        days_offline = (now - last_seen_dt).days
                        if days_offline >= INACTIVE_DAYS and role_added == 0:
                            if not only_over_30 or days_offline >= INACTIVE_DAYS:
                                try:
                                    await member.add_roles(role)
                                    c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                                    total_role_added += 1
                                    print(f"✅ Gán role '{ROLE_NAME}' cho {member.name} ({days_offline} ngày offline)")
                                except Exception as e:
                                    print(f"⚠️ Lỗi khi gán role cho {member.name}: {e}")
                except Exception as e:
                    print(f"⚠️ Lỗi với member {getattr(member, 'name', 'unknown')}: {e}")
                if total_checked % 100 == 0:
                    await asyncio.sleep(0.1)
        conn.commit()
    except Exception as e:
        print(f"⚠️ Lỗi trong check_inactivity_once: {e}")
    finally:
        try: conn.close()
        except: pass
    finished_ts = datetime.now(timezone.utc).isoformat()
    print(f"✅ [{finished_ts}] Checked={total_checked} Updated={total_updated} RolesAdded={total_role_added}")
    if ctx:
        embed = make_embed(
            title="✅ Hoàn tất kiểm tra Inactivity",
            description=f"Thời gian: `{finished_ts}`",
            color=discord.Color.green(),
            fields=[
                ("🧾 Tổng kiểm tra", str(total_checked), True),
                ("🔄 Cập nhật last_seen", str(total_updated), True),
                ("✅ Gán role", str(total_role_added), True)
            ],
            footer="Sử dụng !recheck30days để chỉ kiểm tra những người đã >= INACTIVE_DAYS"
        )
        await ctx.send(embed=embed)

# ===== Task định kỳ =====
@tasks.loop(hours=24)
async def check_inactivity():
    try:
        await check_inactivity_once()
    except Exception as e:
        print(f"⚠️ Lỗi trong task check_inactivity: {e}")

# ===== Commands =====
@bot.command()
@commands.has_permissions(administrator=True)
async def exportcsv(ctx):
    """Xuất database inactivity thành file CSV có tên người dùng"""
    csv_path = BASE_DIR / "inactivity_export.csv"

    if not os.path.exists(DB_PATH):
        await ctx.send("❌ Không tìm thấy file database.")
        return

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen, role_added FROM inactivity")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await ctx.send("⚠️ Database trống, không có dữ liệu để xuất.")
        return

    # Ghi file CSV kèm tên user
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["member_id", "member_name", "guild_id", "last_seen", "role_added"])
        for row in rows:
            guild = bot.get_guild(int(row["guild_id"]))
            member = guild.get_member(int(row["member_id"])) if guild else None
            member_name = f"{member.name}#{member.discriminator}" if member else "Không tìm thấy"
            writer.writerow([row["member_id"], member_name, row["guild_id"], row["last_seen"], row["role_added"]])

    # Gửi file mà không cần sleep
    with open(csv_path, "rb") as f:
        await ctx.send("✅ Đã xuất file CSV có tên người dùng:", file=discord.File(f, filename="inactivity_export.csv"))

    # Xóa file sau khi gửi
    os.remove(csv_path)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}'")
        return
    try:
        await member.remove_roles(role)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE inactivity SET role_added=0 WHERE member_id=?", (str(member.id),))
        conn.commit()
        conn.close()
        await ctx.send(f"✅ Gỡ role '{ROLE_NAME}' cho {member.name}")
    except Exception as e:
        await ctx.send(f"⚠️ Lỗi: {e}")

@bot.command()
async def list_off(ctx):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}'")
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
        last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
        days_offline = (now - last_seen_dt).days
        if days_offline >= 1:
            results.append(f"• {member.name}#{member.discriminator} — 🕓 {days_offline} ngày offline")

    if results:
        message = "📋 **Danh sách member offline:**\n" + "\n".join(results)
    else:
        message = "✅ Không có member nào đang offline lâu."
    await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def exportdb(ctx):
    """Gửi file inactivity.db lên kênh Discord"""
    if os.path.exists(DB_PATH):
        await ctx.send(file=discord.File(DB_PATH))
    else:
        await ctx.send("❌ Không tìm thấy file database.")

@bot.command()
async def test(ctx):
    embed = make_embed(
        title="🧪 Bot Test",
        description="✅ Bot đang hoạt động và sẽ kiểm tra inactivities mỗi 24 giờ.",
        color=discord.Color.green(),
        fields=[("🕓 Lịch kiểm tra", "24 giờ/lần", True)],
        footer="Nếu muốn chạy ngay, dùng !runcheck"
    )
    embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def runcheck(ctx):
    """Chạy kiểm tra inactivity ngay lập tức"""
    await ctx.send(embed=make_embed(title="🔎 Bắt đầu kiểm tra thủ công...", color=discord.Color.blue()))
    await check_inactivity_once(ctx)
    await ctx.send(embed=make_embed(title="✅ Hoàn tất kiểm tra thủ công", color=discord.Color.green()))

@bot.command()
@commands.has_permissions(administrator=True)
async def recheck30days(ctx):
    """Kiểm tra lại những người đã offline đủ INACTIVE_DAYS"""
    await ctx.send(embed=make_embed(title="🔁 Kiểm tra những member đã offline >= INACTIVE_DAYS", color=discord.Color.blue()))
    await check_inactivity_once(ctx, only_over_30=True)
    await ctx.send(embed=make_embed(title="✅ Hoàn tất kiểm tra lại", color=discord.Color.green()))

@bot.command()
@commands.has_permissions(administrator=True)
async def list_off_30days(ctx, export: str = None):
    """
    Liệt kê member offline >= INACTIVE_DAYS (mặc định 30).
    Usage:
      !list_off_30days        -> gửi embed (phân trang nếu >25)
      !list_off_30days csv    -> xuất file CSV và gửi
    """
    guild = ctx.guild
    if not guild:
        await ctx.send("❌ Lệnh chỉ dùng trong server.")
        return

    # lấy dữ liệu từ DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await ctx.send("✅ Database trống cho server này.")
        return

    now = datetime.now(timezone.utc)
    threshold = INACTIVE_DAYS  # mặc định từ config
    results = []

    for row in rows:
        try:
            member_id = int(row["member_id"])
        except Exception:
            continue
        last_seen = row["last_seen"]
        if not last_seen:
            continue
        try:
            last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
        except Exception:
            continue
        days_offline = (now - last_seen_dt).days
        if days_offline >= threshold:
            member = guild.get_member(member_id)
            results.append((member, days_offline, last_seen, member_id))

    if not results:
        await ctx.send(f"✅ Không có member nào offline ≥ {threshold} ngày.")
        return

    # Nếu user yêu cầu xuất CSV
    if export and export.lower() in ("csv", "file"):
        csv_path = BASE_DIR / f"offline_{guild.id}_{threshold}d.csv"
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["member_id", "member_name", "days_offline", "last_seen"])
                for member, days_offline, last_seen, member_id in results:
                    member_name = f"{member.name}#{member.discriminator}" if member else "Không tìm thấy"
                    writer.writerow([member_id, member_name, days_offline, last_seen])
            # gửi file
            with open(csv_path, "rb") as f:
                await ctx.send(f"📥 Danh sách member offline ≥ {threshold} ngày (CSV):", file=discord.File(f, filename=csv_path.name))
        except Exception as e:
            await ctx.send(f"⚠️ Lỗi khi xuất CSV: {e}")
        finally:
            try:
                if os.path.exists(csv_path):
                    os.remove(csv_path)
            except:
                pass
        return

    # Chuẩn bị message embed phân trang (25 mục/ embed)
    per_page = 25
    chunks = [results[i:i+per_page] for i in range(0, len(results), per_page)]
    for page_idx, chunk in enumerate(chunks, start=1):
        lines = []
        for member, days_offline, last_seen, member_id in chunk:
            if member:
                name = f"{member.mention} ({member.name}#{member.discriminator})"
            else:
                name = f"ID:{member_id} — Không tìm thấy"
            lines.append(f"• {name} — 🕓 {days_offline} ngày (last_seen: `{last_seen}`)")
        embed = make_embed(
            title=f"📋 Danh sách offline ≥ {threshold} ngày — Trang {page_idx}/{len(chunks)}",
            description="\n".join(lines[:2000]),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Tổng: {len(results)} member")
        await ctx.send(embed=embed)

# ===== Event on_ready =====
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    if not check_inactivity.is_running():
        check_inactivity.start()
        print("🟢 Task check_inactivity đã start")

# ===== Chạy Flask và Bot =====
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    print("🟢 Flask server đã chạy qua waitress (daemon thread).")
    if TOKEN:
        print("🟢 Bắt đầu chạy bot...")
        bot.run(TOKEN)
    else:
        print("❌ Không tìm thấy TOKEN trong biến môi trường!")

