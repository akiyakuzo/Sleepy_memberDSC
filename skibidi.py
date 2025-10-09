import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import sqlite3
from flask import Flask
from threading import Thread
import pathlib

# ===== Path cho DB nằm trong repo =====
BASE_DIR = pathlib.Path(__file__).parent  # thư mục chứa script
DB_PATH = BASE_DIR / "inactivity.db"      # file DB trong repo

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

# ===== Bot Discord =====
TOKEN = os.getenv("TOKEN")
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"
INACTIVE_DAYS = 30

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Task: check inactivity & gán role =====
@tasks.loop(hours=24)
async def check_inactivity():
    now = datetime.now(timezone.utc)
    print(f"🔍 [{now.isoformat()}] Bắt đầu kiểm tra thành viên không hoạt động...")

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

                # Cập nhật last_seen nếu offline
                if member.activity is None and str(member.status) == "offline":
                    c.execute("""
                        INSERT INTO inactivity (member_id, guild_id, last_seen, role_added)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(member_id) DO UPDATE SET last_seen=excluded.last_seen
                    """, (str(member.id), str(guild.id), now, role_added))
                    conn.commit()
                    last_seen = now
                    print(f"🟡 Cập nhật last_seen cho {member.name}")

                # Gán role nếu đủ 30 ngày offline
                if last_seen:
                    last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
                    if (now - last_seen_dt).days >= INACTIVE_DAYS and role_added == 0:
                        try:
                            await member.add_roles(role)
                            c.execute("UPDATE inactivity SET role_added=1 WHERE member_id=?", (str(member.id),))
                            conn.commit()
                            print(f"✅ Gán role '{ROLE_NAME}' cho {member.name}")
                        except discord.Forbidden:
                            print(f"🚫 Không đủ quyền để gán role cho {member.name}")
                        except Exception as e:
                            print(f"⚠️ Lỗi khi gán role cho {member.name}: {e}")
            except Exception as e:
                print(f"⚠️ Lỗi SQLite với {member.name}: {e}")
            finally:
                conn.close()

    print(f"✅ [{datetime.now(timezone.utc).isoformat()}] Kiểm tra hoàn tất!")

# ===== Command: test bot =====
@bot.command()
async def test(ctx):
    print(f"📩 Nhận lệnh !test từ {ctx.author}")
    await ctx.send("✅ Bot đang hoạt động và kiểm tra mỗi 24h 🕓")

# ===== Command: list offline members =====
@bot.command()
async def list_off(ctx):
    print(f"📩 Nhận lệnh !list_off từ {ctx.author}")
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}'")
        return

    offline_members = [f"{m.name}#{m.discriminator}" for m in role.members if str(m.status) == "offline"]
    if offline_members:
        await ctx.send("📋 **Danh sách member offline với role ngủ đông:**\n" + "\n".join(offline_members))
    else:
        await ctx.send("✅ Không có member offline nào với role này.")

# ===== Command: remove role =====
@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member):
    print(f"📩 Nhận lệnh !removerole từ {ctx.author} cho {member.name}")
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if not role:
        await ctx.send(f"⚠️ Không tìm thấy role '{ROLE_NAME}'")
        return

    bot_member = guild.me
    if role.position >= bot_member.top_role.position:
        await ctx.send("🚫 Bot không có quyền gỡ role này.")
        return

    try:
        await member.remove_roles(role)
        await ctx.send(f"✅ Gỡ role '{ROLE_NAME}' cho {member.name}")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE inactivity SET role_added=0 WHERE member_id=?", (str(member.id),))
        conn.commit()
        conn.close()
        print(f"🟢 Role '{ROLE_NAME}' đã được gỡ khỏi {member.name}")
    except discord.Forbidden:
        await ctx.send("🚫 Bot không có quyền để gỡ role.")
    except Exception as e:
        await ctx.send(f"⚠️ Lỗi: {e}")
        print(f"⚠️ Lỗi gỡ role cho {member.name}: {e}")

# ===== Command: Check inacvity =====
@bot.command()
@commands.has_permissions(administrator=True)
async def runcheck(ctx):
    """Chạy kiểm tra inactivity ngay lập tức"""
    if check_inactivity.is_running():
        await ctx.send("⚠️ Task check_inactivity đang chạy, vui lòng đợi.")
        return
    await ctx.send("⏳ Bắt đầu kiểm tra inactivity ngay lập tức...")
    await check_inactivity()
    await ctx.send("✅ Hoàn tất kiểm tra inactivity!")

# ===== Event: bot ready =====
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    if not check_inactivity.is_running():
        check_inactivity.start()
        print("🟢 Task check_inactivity đã được start")
    else:
        print("ℹ️ Task check_inactivity đã chạy trước đó, không start lại")
        
# ===== Run bot =====
if TOKEN:
    print("🟢 Bắt đầu chạy bot...")
    bot.run(TOKEN)
else:
    print("❌ Không tìm thấy TOKEN trong biến môi trường!")

