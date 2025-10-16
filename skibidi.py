# skibidi_fixed.py
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

# ===== Flask server cho Render (keep-alive) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot đang chạy!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    serve(app, host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()
print("🟢 Flask server đã chạy qua waitress (daemon thread).")

# ===== Hàm tạo kết nối DB thread-safe =====
def get_db_connection():
    # check_same_thread=False để có thể dùng conn từ nhiều thread (cẩn thận khi dùng)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ===== Tạo bảng nếu chưa tồn tại =====
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

# ===== Cấu hình bot (có thể lấy ROLE_NAME, INACTIVE_DAYS từ env nếu muốn) =====
TOKEN = os.getenv("TOKEN")
ROLE_NAME = os.getenv("ROLE_NAME", "💤 Tín Đồ Ngủ Đông")
INACTIVE_DAYS = int(os.getenv("INACTIVE_DAYS", "30"))

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Helper tạo embed chuẩn =====
def make_embed(title: str, description: str = None, color: discord.Color = discord.Color.blue(), *, fields=None, footer=None):
    embed = discord.Embed(title=title, description=description or "", color=color, timestamp=datetime.now(timezone.utc))
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ===== FancyHelpCommand (giữ nguyên phong cách nhưng ổn hơn chút) =====
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
                    f"**!{cmd.name}** — {cmd.help or 'Không có mô tả'}"
                    for cmd in filtered
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

# gán lại help command
bot.remove_command("help")
bot.help_command = FancyHelpCommand()

# =====================================================
# 💤 HÀM CHÍNH: Kiểm tra 1 lần duy nhất (dùng cho task & lệnh !runcheck)
# - Mở 1 connection DB cho toàn bộ lượt kiểm tra (không mở/đóng từng member)
# - Bọc try/except để không làm dừng task
# =====================================================
async def check_inactivity_once(ctx=None, only_over_30=False):
    now = datetime.now(timezone.utc)
    print(f"🔍 [{now.isoformat()}] Bắt đầu kiểm tra thành viên không hoạt động...")
    total_checked = 0
    total_updated = 0
    total_role_added = 0

    try:
        # Mở 1 connection cho toàn bộ check
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
                    # Lấy dữ liệu hiện tại
                    c.execute("SELECT last_seen, role_added FROM inactivity WHERE member_id=?", (str(member.id),))
                    row = c.fetchone()
                    last_seen, role_added = (row["last_seen"], row["role_added"]) if row else (None, 0)

                    # Cập nhật nếu offline (ghi thời điểm hiện tại)
                    if str(member.status) == "offline":
                        c.execute("""
                            INSERT INTO inactivity (member_id, guild_id, last_seen, role_added)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(member_id) DO UPDATE SET last_seen=excluded.last_seen
                        """, (str(member.id), str(guild.id), datetime.now(timezone.utc).isoformat(), role_added))
                        total_updated += 1

                    # Gán role nếu đủ ngưỡng
                    if last_seen:
                        try:
                            last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
                        except Exception:
                            # fallback nếu format khác
                            last_seen_dt = datetime.now(timezone.utc)
                        days_offline = (now - last_seen_dt).days
                        if days_offline >= INACTIVE_DAYS and role_added == 0:
                            if only_over_30 and days_offline < INACTIVE_DAYS:
                                pass
                            else:
                                try:
                                    await member.add_roles(role)
                                    c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                                    total_role_added += 1
                                    print(f"✅ Gán role '{ROLE_NAME}' cho {member.name} ({days_offline} ngày offline)")
                                except discord.Forbidden:
                                    print(f"🚫 Không đủ quyền để gán role cho {member.name}")
                                except Exception as e:
                                    print(f"⚠️ Lỗi khi gán role cho {member.name}: {e}")

                except Exception as e:
                    print(f"⚠️ Lỗi với member {getattr(member, 'name', 'unknown')}: {e}")

                # Giải phóng event loop nhẹ để tránh block lâu (khi guild rất lớn)
                if total_checked % 100 == 0:
                    await asyncio.sleep(0.1)

        # commit 1 lần sau khi xong
        conn.commit()
    except Exception as e:
        print(f"⚠️ Lỗi trong check_inactivity_once: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    finished_ts = datetime.now(timezone.utc).isoformat()
    print(f"✅ [{finished_ts}] Hoàn tất kiểm tra! Checked={total_checked} Updated={total_updated} RolesAdded={total_role_added}")

    # nếu có ctx (lệnh), gửi embed tóm tắt
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

# ===== Task định kỳ (24h) - bọc try/except để không dừng =====
@tasks.loop(hours=24)
async def check_inactivity():
    try:
        await check_inactivity_once()
    except Exception as e:
        print(f"⚠️ Lỗi trong task check_inactivity: {e}")

# =====================================================
# ⚙️ CÁC LỆNH - dùng embed cho phản hồi
# =====================================================
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
    pre = make_embed(
        title="🔎 Bắt đầu kiểm tra thủ công...",
        description="Bot đang quét các thành viên. Vui lòng chờ...",
        color=discord.Color.blue()
    )
    await ctx.send(embed=pre)
    await check_inactivity_once(ctx)
    done = make_embed(
        title="✅ Hoàn tất kiểm tra thủ công",
        description="Kết quả đã gửi ở trên.",
        color=discord.Color.green()
    )
    await ctx.send(embed=done)

@bot.command()
@commands.has_permissions(administrator=True)
async def recheck30days(ctx):
    """Kiểm tra lại những người đã offline đủ INACTIVE_DAYS"""
    pre = make_embed(
        title="🔁 Kiểm tra những member đã offline >= INACTIVE_DAYS",
        description=f"Ngưỡng: {INACTIVE_DAYS} ngày",
        color=discord.Color.blue()
    )
    await ctx.send(embed=pre)
    await check_inactivity_once(ctx, only_over_30=True)
    done = make_embed(
        title="✅ Hoàn tất kiểm tra lại",
        description="Đã hoàn tất kiểm tra những người đã offline đủ ngưỡng.",
        color=discord.Color.green()
    )
    await ctx.send(embed=done)

@bot.command()
@commands.has_permissions(administrator=True)
async def exportdb(ctx):
    """Gửi file inactivity.db lên kênh Discord"""
    if os.path.exists(DB_PATH):
        embed = make_embed(title="📁 Export Database", description="Đang gửi file inactivity.db", color=discord.Color.green())
        await ctx.send(embed=embed)
        await ctx.send(file=discord.File(DB_PATH))
    else:
        await ctx.send(embed=make_embed(title="❌ Lỗi", description="Không tìm thấy file database.", color=discord.Color.red()))

@bot.command()
@commands.has_permissions(administrator=True)
async def exportcsv(ctx):
    """Xuất database inactivity thành file CSV có tên người dùng"""
    csv_path = BASE_DIR / "inactivity_export.csv"

    if not os.path.exists(DB_PATH):
        await ctx.send(embed=make_embed(title="❌ Lỗi", description="Không tìm thấy file database.", color=discord.Color.red()))
        return

    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT member_id, guild_id, last_seen, role_added FROM inactivity").fetchall()
        conn.close()

        if not rows:
            await ctx.send(embed=make_embed(title="⚠️ Database trống", description="Không có dữ liệu để xuất.", color=discord.Color.orange()))
            return

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["member_id", "member_name", "guild_id", "last_seen", "role_added"])
            for row in rows:
                guild = bot.get_guild(int(row["guild_id"])) if row["guild_id"] else None
                member = guild.get_member(int(row["member_id"])) if guild else None
                member_name = f"{member.name}#{member.discriminator}" if member else "Không tìm thấy"
                writer.writerow([row["member_id"], member_name, row["guild_id"], row["last_seen"], row["role_added"]])

        embed = make_embed(title="✅ Đã xuất CSV", description="Gửi file CSV kèm tên người dùng.", color=discord.Color.green())
        await ctx.send(embed=embed, file=discord.File(csv_path))
    except Exception as e:
        await ctx.send(embed=make_embed(title="⚠️ Lỗi khi xuất CSV", description=str(e), color=discord.Color.red()))
    finally:
        try:
            if os.path.exists(csv_path):
                os.remove(csv_path)
        except Exception:
            pass

# ===== Command: list offline members (hiển thị số ngày offline) =====
@bot.command()
async def list_off(ctx):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(embed=make_embed(title="⚠️ Không tìm thấy role", description=f"Role '{ROLE_NAME}' không tồn tại.", color=discord.Color.orange()))
        return

    conn = get_db_connection()
    rows = conn.execute("SELECT member_id, last_seen FROM inactivity WHERE guild_id=?", (str(guild.id),)).fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    results = []
    for row in rows:
        try:
            member = guild.get_member(int(row["member_id"]))
            if not member or member.bot or str(member.status) != "offline":
                continue
            last_seen = row["last_seen"]
            if not last_seen:
                continue
            last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
            days_offline = (now - last_seen_dt).days
            if days_offline >= 1:
                results.append(f"• {member.name}#{member.discriminator} — 🕓 {days_offline} ngày")
        except Exception:
            continue

    if results:
        # nếu dài quá, chia trang (giữ đơn giản: gửi tất cả)
        embed = make_embed(title="📋 Danh sách member offline", description="\n".join(results[:25]), color=discord.Color.gold())
        embed.set_footer(text=f"Tổng: {len(results)} người. Hiển thị tối đa 25.")
        await ctx.send(embed=embed)
    else:
        await ctx.send(embed=make_embed(title="✅ Không có member offline lâu", description="Không có member nào đang offline >= 1 ngày.", color=discord.Color.green()))

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(embed=make_embed(title="⚠️ Không tìm thấy role", description=f"Role '{ROLE_NAME}' không tồn tại.", color=discord.Color.orange()))
        return
    try:
        await member.remove_roles(role)
        conn = get_db_connection()
        conn.execute("UPDATE inactivity SET role_added=0 WHERE member_id=?", (str(member.id),))
        conn.commit()
        conn.close()
        await ctx.send(embed=make_embed(title="✅ Gỡ role", description=f"Đã gỡ role '{ROLE_NAME}' cho {member.name}#{member.discriminator}", color=discord.Color.green()))
    except Exception as e:
        await ctx.send(embed=make_embed(title="⚠️ Lỗi khi gỡ role", description=str(e), color=discord.Color.red()))

# ===== Event: bot ready =====
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    if not check_inactivity.is_running():
        check_inactivity.start()
        print("🟢 Task check_inactivity đã được start")

# ===== Run bot =====
if TOKEN:
    print("🟢 Bắt đầu chạy bot...")
    bot.run(TOKEN)
else:
    print("❌ Không tìm thấy TOKEN trong biến môi trường!")
