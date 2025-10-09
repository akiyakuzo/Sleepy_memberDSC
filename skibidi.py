import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True
intents.message_content = True  # Bật intents cho lệnh text

bot = commands.Bot(command_prefix="!", intents=intents)

# Flask để Render health check
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot đang chạy!"

Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()

INACTIVE_DAYS = 30
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"

@tasks.loop(hours=24)
async def check_inactivity():
    print("🔍 Kiểm tra thành viên không hoạt động...")
    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if not role:
            print(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server '{guild.name}'")
            continue

        for member in guild.members:
            if member.bot:
                continue
            if member.joined_at < datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS):
                if member.activity is None and str(member.status) == "offline":
                    try:
                        await member.add_roles(role)
                        print(f"✅ Đã gán role '{ROLE_NAME}' cho {member.name}")
                    except discord.Forbidden:
                        print(f"🚫 Không đủ quyền cho {member.name}")
                    except Exception as e:
                        print(f"⚠️ Lỗi: {e}")
    print("✅ Kiểm tra hoàn tất!")

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    check_inactivity.start()

@bot.command()
async def test(ctx):
    await ctx.send("✅ Bot đang hoạt động!")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Không tìm thấy TOKEN trong biến môi trường!")
