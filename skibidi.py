import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import sqlite3
from flask import Flask
from threading import Thread
import pathlib
import csv


# ===== Path cho DB nằm trong repo =====
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "inactivity.db"

# ===== Flask server cho Render =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot đang chạy!"

Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
print("🟢 Flask server đã chạy trên thread riêng")

# ===== Hàm tạo kết nối DB thread-safe =====
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ===== Tạo bảng nếu chưa tồn tại =====
conn = get_db_connection()
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS inactivity (
    member_id TEXT PRIMARY KEY,
    guild_id TEXT,
    last_seen TIMESTAMP,
    role_added BOOLEAN DEFAULT 0
)
""")
conn.commit()
conn.close()
print(f"🟢 Database SQLite đã sẵn sàng: {DB_PATH}")

# ===== Cấu hình bot =====
TOKEN = os.getenv("TOKEN")
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"
INACTIVE_DAYS = 30

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================================================
# 💤 HÀM CHÍNH: Kiểm tra 1 lần duy nhất (dùng cho task & lệnh !runcheck)
# =====================================================
async def check_inactivity_once(ctx=None, only_over_30=False):
    now = datetime.now(timezone.utc)
    print(f"🔍 [{now.isoformat()}] Bắt đầu kiểm tra thành viên không hoạt động...")
    total_checked = 0
    total_updated = 0
    total_role_added = 0

    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if not role:
            print(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server '{guild.name}'")
            continue

        for member in guild.members:
            if member.bot:
                continue

            conn = get_db_connection()
            c = conn.cursor()

            try:
                c.execute("SELECT last_seen, role_added FROM inactivity WHERE member_id=?", (str(member.id),))
                row = c.fetchone()
                last_seen, role_added = (row["last_seen"], row["role_added"]) if row else (None, 0)
                total_checked += 1

                # Cập nhật nếu offline
                if str(member.status) == "offline":
                    c.execute("""
                        INSERT INTO inactivity (member_id, guild_id, last_seen, role_added)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(member_id) DO UPDATE SET last_seen=excluded.last_seen
                    """, (str(member.id), str(guild.id), now, role_added))
                    conn.commit()
                    total_updated += 1
                    print(f"🟡 Cập nhật last_seen cho {member.name}")

                # Gán role nếu đủ 30 ngày offline
                if last_seen:
                    last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
                    days_offline = (now - last_seen_dt).days
                    if days_offline >= INACTIVE_DAYS and role_added == 0:
                        if only_over_30 and days_offline < INACTIVE_DAYS:
                            continue
                        try:
                            await member.add_roles(role)
                            c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                            conn.commit()
                            total_role_added += 1
                            print(f"✅ Gán role '{ROLE_NAME}' cho {member.name} ({days_offline} ngày offline)")
                        except discord.Forbidden:
                            print(f"🚫 Không đủ quyền để gán role cho {member.name}")
                        except Exception as e:
                            print(f"⚠️ Lỗi khi gán role cho {member.name}: {e}")

            except Exception as e:
                print(f"⚠️ Lỗi SQLite với {member.name}: {e}")
            finally:
                conn.close()

    print(f"✅ [{datetime.now(timezone.utc).isoformat()}] Hoàn tất kiểm tra!")
    summary = (
        f"🧾 **Tổng kết:**\n"
        f"• Kiểm tra: {total_checked} thành viên\n"
        f"• Cập nhật: {total_updated}\n"
        f"• Gán role: {total_role_added}"
    )
    if ctx:
        await ctx.send(summary)
    else:
        print(summary)


# ===== Task định kỳ =====
@tasks.loop(hours=24)
async def check_inactivity():
    await check_inactivity_once()

# =====================================================
# ⚙️ CÁC LỆNH
# =====================================================

# ===== Custom Help Command Đẹp Mắt =====
class FancyHelpCommand(commands.MinimalHelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📘 Hướng dẫn sử dụng Bot",
            description="Dưới đây là danh sách các lệnh khả dụng, chia theo nhóm:",
            color=discord.Color.blue()
        )

        # Thumbnail (logo góc phải)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1424075941268951070/1428267008973340774/wallpae.png?ex=68f1e0ce&is=68f08f4e&hm=e0fe822bd5dace59aa272fe3756d7de08fa756db20fa6da6690658ec393fba0e&")

        # Banner hoặc GIF nền (ở dưới cùng embed)
        embed.set_image(url="https://moewalls.com/wp-content/uploads/2025/03/phoebe-sleeping-wuthering-waves-thumb.jpg")

        for cog, commands_list in mapping.items():
            filtered = await self.filter_commands(commands_list, sort=True)
            if not filtered:
                continue

            command_descriptions = [
                f"**!{cmd.name}** — {cmd.help or 'Không có mô tả'}"
                for cmd in filtered
            ]
            embed.add_field(
                name=f"⚙️ {cog.qualified_name if cog else 'Lệnh chung'}",
                value="\n".join(command_descriptions),
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

# 🚫 Xóa help mặc định, tránh trùng lặp
bot.remove_command("help")

# ✅ Gán help mới
bot.help_command = FancyHelpCommand()

@bot.command()
async def test(ctx):
    await ctx.send("✅ Bot đang hoạt động và kiểm tra mỗi 24h 🕓")

@bot.command()
@commands.has_permissions(administrator=True)
async def runcheck(ctx):
    """Chạy kiểm tra inactivity ngay lập tức"""
    await ctx.send("🔎 Bắt đầu kiểm tra thủ công...")
    await check_inactivity_once(ctx)
    await ctx.send("✅ Đã hoàn tất kiểm tra thủ công!")

@bot.command()
@commands.has_permissions(administrator=True)
async def recheck30days(ctx):
    """Kiểm tra lại những người đã offline đủ 30 ngày trở lên"""
    await ctx.send("🔁 Đang kiểm tra lại những member đã offline đủ 30 ngày...")
    await check_inactivity_once(ctx, only_over_30=True)
    await ctx.send("✅ Hoàn tất kiểm tra lại thành viên offline 30 ngày!")

@bot.command()
@commands.has_permissions(administrator=True)
async def exportdb(ctx):
    """Gửi file inactivity.db lên kênh Discord"""
    if os.path.exists(DB_PATH):
        await ctx.send(file=discord.File(DB_PATH))
    else:
        await ctx.send("❌ Không tìm thấy file database.")

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

    await ctx.send("✅ Đã xuất file CSV có tên người dùng:", file=discord.File(csv_path))
    os.remove(csv_path)  # Xóa file sau khi gửi (nếu muốn)

# ===== Command: list offline members (CÓ hiển thị số ngày offline) =====
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




