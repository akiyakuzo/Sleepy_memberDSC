import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# 🔐 Lấy token từ biến môi trường (Render -> Environment Variables)
TOKEN = os.getenv("TOKEN")

# ⚙️ Cấu hình intents (quan trọng để đọc member & activity)
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.presences = True  # Cần để kiểm tra trạng thái hoạt động
bot = commands.Bot(command_prefix="!", intents=intents)

# 💤 Cấu hình thông số bot
INACTIVE_DAYS = 30
ROLE_NAME = "💤 Tín Đồ Ngủ Đông"

# 🔁 Vòng lặp kiểm tra hoạt động mỗi 24 giờ
@tasks.loop(hours=24)
async def check_inactivity():
    print("🔍 Bắt đầu kiểm tra thành viên không hoạt động...")
    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if not role:
            print(f"⚠️ Không tìm thấy role '{ROLE_NAME}' trong server '{guild.name}'")
            continue

        for member in guild.members:
            if member.bot:
                continue

            # Nếu người chơi không hoạt động trong khoảng thời gian quy định
            if member.joined_at < datetime.utcnow() - timedelta(days=INACTIVE_DAYS):
                # Nếu không có hoạt động (offline lâu)
                if member.activity is None and str(member.status) == "offline":
                    try:
                        await member.add_roles(role)
                        print(f"✅ Đã gán role '{ROLE_NAME}' cho {member.name}")
                    except discord.Forbidden:
                        print(f"🚫 Không đủ quyền để gán role cho {member.name}")
                    except Exception as e:
                        print(f"⚠️ Lỗi khi gán role cho {member.name}: {e}")

    print("✅ Kiểm tra hoàn tất!")

# 🟢 Khi bot online
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} đã online!")
    await bot.change_presence(activity=discord.Game("Theo dõi tín đồ 😴"))
    check_inactivity.start()

# Lệnh test
@bot.command()
async def test(ctx):
    await ctx.send("Bot đang hoạt động và kiểm tra mỗi 24h 🕓")

# 🚀 Chạy bot
if TOKEN:
    bot.run(MTQyNTUyOTcxNDUyODg4MjczMg.G2NANG.5P-yCtnxvHMdEOBru9une0YtSLzBCwv9xE9Km8)
else:
    print("❌ Không tìm thấy TOKEN trong biến môi trường!")
