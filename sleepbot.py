# ===== Skibidi Bot v6 • Phoebe Style 💜 =====
# Giữ nguyên toàn bộ tính năng bản v5, thêm:
# /setinactive <days> – chỉnh số ngày inactive
# /toggle_autodelete – bật/tắt tự xóa embed
# /status – xem số lượng user có role ngủ đông
# ============================================

import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
import sqlite3
import asyncio
import json
import pathlib
from flask import Flask
from threading import Thread
import csv
import time

# ===== Đường dẫn cơ bản =====
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "inactivity.db"
CONFIG_PATH = BASE_DIR / "config.json"

# ===== Flask Uptime Server =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 Skibidi Bot v6 đang chạy ổn định!"

@app.route('/healthz')
def health():
    return "OK"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()
time.sleep(3)  # Đảm bảo Flask đã bind cổng trước khi bot chạy

# ===== Cấu hình & config.json =====
DEFAULT_CONFIG = {
    "INACTIVE_DAYS": 30,
    "AUTO_DELETE_ENABLED": True
}

CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

config = load_config()

# ===== Discord Bot =====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== Biến toàn cục =====
last_command_msg_id = {}
delete_timers = {}

# ===== Hàm tiện ích =====
def make_embed(title="", desc="", color=discord.Color.purple()):
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.timestamp = datetime.now(timezone.utc)
    return embed

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS inactivity (
                    member_id TEXT,
                    guild_id TEXT,
                    last_seen TEXT,
                    role_added TEXT
                )""")
    conn.commit()
    return conn

# ===== schedule_autodelete =====
async def schedule_autodelete(channel_id: int, msg_id: int):
    """Tự động xóa tin nhắn cũ nếu bật AUTO_DELETE_ENABLED."""
    if not config.get("AUTO_DELETE_ENABLED", True):
        return
    if channel_id in delete_timers:
        delete_timers[channel_id].cancel()

    async def delayed_delete():
        await asyncio.sleep(3)
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                return
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
            print(f"🗑️ Đã xóa embed cũ ở #{channel.name}")
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"⚠️ Lỗi xóa embed: {e}")
        finally:
            delete_timers.pop(channel_id, None)

    task = asyncio.create_task(delayed_delete())
    delete_timers[channel_id] = task

# ===== /setinactive =====
@tree.command(name="setinactive", description="Chỉnh số ngày inactive để kiểm tra.")
@app_commands.checks.has_permissions(administrator=True)
async def setinactive(interaction: discord.Interaction, days: int):
    if days < 1:
        await interaction.response.send_message("❌ Số ngày phải ≥ 1.", ephemeral=True)
        return
    config["INACTIVE_DAYS"] = days
    save_config(config)
    embed = make_embed("✅ Cập nhật thành công", f"Số ngày inactive được đặt là **{days} ngày**.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== /toggle_autodelete =====
@tree.command(name="toggle_autodelete", description="Bật/tắt tự xóa embed cũ.")
@app_commands.checks.has_permissions(administrator=True)
async def toggle_autodelete(interaction: discord.Interaction):
    config["AUTO_DELETE_ENABLED"] = not config["AUTO_DELETE_ENABLED"]
    save_config(config)
    status = "✅ BẬT" if config["AUTO_DELETE_ENABLED"] else "❌ TẮT"
    embed = make_embed("⚙️ Cập nhật cài đặt", f"Tự xóa embed hiện đang: **{status}**")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== /status =====
@tree.command(name="status", description="Xem số lượng user đang bị role ngủ đông.")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    role_name = "💤 Tín Đồ Ngủ Đông"
    guild = interaction.guild
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        await interaction.followup.send(f"❌ Không tìm thấy role `{role_name}` trong server.")
        return
    members = [m for m in guild.members if role in m.roles]
    embed = make_embed("💤 Trạng thái ngủ đông",
                       f"Hiện có **{len(members)}** thành viên đang có role `{role_name}`.")
    await interaction.followup.send(embed=embed)

# ===== /exportcsv =====
@tree.command(name="exportcsv", description="Xuất dữ liệu inactivity thành file CSV.")
@app_commands.checks.has_permissions(administrator=True)
async def exportcsv(interaction: discord.Interaction):
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
        await schedule_autodelete(interaction.channel_id, sent.id)
        return

    csv_file_path = BASE_DIR / f"inactivity_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Guild_ID", "Member_ID", "Member_Name", "Last_Seen", "Role_Added"])
        for member_id, guild_id, last_seen, role_added in rows:
            guild = bot.get_guild(int(guild_id))
            member_name = "Unknown"
            if guild:
                member = guild.get_member(int(member_id))
                if member:
                    member_name = member.display_name
            writer.writerow([guild_id, member_id, member_name, last_seen, role_added])

    try:
        sent = await interaction.followup.send(file=discord.File(csv_file_path))
        last_command_msg_id[interaction.channel_id] = sent.id
        await schedule_autodelete(interaction.channel_id, sent.id)
    except Exception as e:
        embed = make_embed("❌ Lỗi", f"Không thể gửi file CSV: {e}")
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id
        await schedule_autodelete(interaction.channel_id, sent.id)

    try:
        os.remove(csv_file_path)
    except Exception as e:
        print(f"⚠️ Không thể xóa file CSV tạm: {e}")

# ===== /help paginate =====
@tree.command(name="help", description="Hiển thị danh sách lệnh của Skibidi Bot (tương tác paginate).")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    commands_list = [
        ("/setinactive", "Chỉnh số ngày inactive để kiểm tra."),
        ("/toggle_autodelete", "Bật/tắt tự xóa embed."),
        ("/status", "Xem số lượng user đang có role ngủ đông."),
        ("/exportcsv", "Xuất file CSV dữ liệu inactivity."),
        ("/runcheck", "Kiểm tra inactivity thủ công."),
        ("/recheck30days", "Kiểm tra lại người offline ≥30 ngày."),
        ("/list_off", "Danh sách offline ≥1 ngày."),
        ("/list_off_30days", "Danh sách offline ≥30 ngày."),
        ("/exportdb", "Xuất database SQLite.")
    ]

    PAGE_SIZE = 4
    pages = [commands_list[i:i + PAGE_SIZE] for i in range(0, len(commands_list), PAGE_SIZE)]
    total_pages = len(pages)

    def make_help_embed(page_idx):
        embed = make_embed(
            title=f"📖 Danh sách lệnh Skibidi Bot (Trang {page_idx+1}/{total_pages})",
            color=discord.Color.purple()
        )
        for name, desc in pages[page_idx]:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_thumbnail(url="https://files.catbox.moe/rvvejl.png")
        embed.set_footer(text="Skibidi Bot v6 • Phoebe Style 💜")
        return embed

    class HelpView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.current_page = 0

        async def update_message(self, interaction: discord.Interaction):
            try:
                await interaction.response.edit_message(
                    embed=make_help_embed(self.current_page),
                    view=self
                )
            except discord.InteractionResponded:
                await interaction.edit_original_response(
                    embed=make_help_embed(self.current_page),
                    view=self
                )

        @discord.ui.button(label="⬅ Trước", style=discord.ButtonStyle.gray)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_message(interaction)

        @discord.ui.button(label="Tiếp ➡", style=discord.ButtonStyle.gray)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_message(interaction)

    view = HelpView()
    embed = make_help_embed(0)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

# ===== /list_off (paginate) =====
@tree.command(name="list_off", description="Danh sách offline ≥1 ngày (paginate).")
@app_commands.checks.has_permissions(administrator=True)
async def list_off(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    days_limit = 1
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_limit)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen FROM inactivity")
    rows = c.fetchall()
    conn.close()

    offline_members = []
    for member_id, guild_id, last_seen in rows:
        last_seen_dt = datetime.fromisoformat(last_seen)
        if last_seen_dt <= cutoff:
            guild = bot.get_guild(int(guild_id))
            member_name = "Unknown"
            if guild:
                member = guild.get_member(int(member_id))
                if member:
                    member_name = member.display_name
            offline_members.append(f"{member_name} ({member_id})")

    if not offline_members:
        embed = make_embed("💤 Offline ≥1 ngày", "Không có thành viên offline ≥1 ngày.")
        sent = await interaction.followup.send(embed=embed, ephemeral=True)
        await schedule_autodelete(interaction.channel_id, sent.id)
        return

    PAGE_SIZE = 25
    pages = [offline_members[i:i + PAGE_SIZE] for i in range(0, len(offline_members), PAGE_SIZE)]
    total_pages = len(pages)

    def make_embed_page(page_idx):
        desc = "\n".join(pages[page_idx])
        embed = make_embed(f"💤 Offline ≥1 ngày (Trang {page_idx+1}/{total_pages})", desc)
        return embed

    class PaginateView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.current_page = 0

        async def update_message(self, interaction: discord.Interaction):
            try:
                await interaction.response.edit_message(embed=make_embed_page(self.current_page), view=self)
            except discord.InteractionResponded:
                await interaction.edit_original_response(embed=make_embed_page(self.current_page), view=self)

        @discord.ui.button(label="⬅ Trước", style=discord.ButtonStyle.gray)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_message(interaction)

        @discord.ui.button(label="Tiếp ➡", style=discord.ButtonStyle.gray)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_message(interaction)

    view = PaginateView()
    sent = await interaction.followup.send(embed=make_embed_page(0), view=view, ephemeral=True)
    await schedule_autodelete(interaction.channel_id, sent.id)

# ===== /list_off_30days (paginate) =====
@tree.command(name="list_off_30days", description="Danh sách offline ≥30 ngày (paginate).")
@app_commands.checks.has_permissions(administrator=True)
async def list_off_30days(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    days_limit = 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_limit)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen FROM inactivity")
    rows = c.fetchall()
    conn.close()

    offline_members = []
    for member_id, guild_id, last_seen in rows:
        last_seen_dt = datetime.fromisoformat(last_seen)
        if last_seen_dt <= cutoff:
            guild = bot.get_guild(int(guild_id))
            member_name = "Unknown"
            if guild:
                member = guild.get_member(int(member_id))
                if member:
                    member_name = member.display_name
            offline_members.append(f"{member_name} ({member_id})")

    if not offline_members:
        embed = make_embed("💤 Offline ≥30 ngày", "Không có thành viên offline ≥30 ngày.")
        sent = await interaction.followup.send(embed=embed, ephemeral=True)
        await schedule_autodelete(interaction.channel_id, sent.id)
        return

    PAGE_SIZE = 25
    pages = [offline_members[i:i + PAGE_SIZE] for i in range(0, len(offline_members), PAGE_SIZE)]
    total_pages = len(pages)

    def make_embed_page(page_idx):
        desc = "\n".join(pages[page_idx])
        embed = make_embed(f"💤 Offline ≥30 ngày (Trang {page_idx+1}/{total_pages})", desc)
        return embed

    class PaginateView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.current_page = 0

        async def update_message(self, interaction: discord.Interaction):
            try:
                await interaction.response.edit_message(embed=make_embed_page(self.current_page), view=self)
            except discord.InteractionResponded:
                await interaction.edit_original_response(embed=make_embed_page(self.current_page), view=self)

        @discord.ui.button(label="⬅ Trước", style=discord.ButtonStyle.gray)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_message(interaction)

        @discord.ui.button(label="Tiếp ➡", style=discord.ButtonStyle.gray)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_message(interaction)

    view = PaginateView()
    sent = await interaction.followup.send(embed=make_embed_page(0), view=view, ephemeral=True)
    await schedule_autodelete(interaction.channel_id, sent.id)

# ===== /runcheck =====
@tree.command(name="runcheck", description="Kiểm tra inactivity thủ công.")
@app_commands.checks.has_permissions(administrator=True)
async def runcheck(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen FROM inactivity")
    rows = c.fetchall()
    conn.close()

    embed = make_embed("✅ Kiểm tra Inactivity", f"Đã kiểm tra **{len(rows)}** thành viên trong DB.")
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id
    await schedule_autodelete(interaction.channel_id, sent.id)

# ===== /recheck30days =====
@tree.command(name="recheck30days", description="Kiểm tra lại người offline ≥30 ngày.")
@app_commands.checks.has_permissions(administrator=True)
async def recheck30days(interaction: discord.Interaction):
    await interaction.response.defer()
    days_limit = 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_limit)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT member_id, guild_id, last_seen FROM inactivity")
    rows = c.fetchall()
    conn.close()

    count = 0
    for member_id, guild_id, last_seen in rows:
        last_seen_dt = datetime.fromisoformat(last_seen)
        if last_seen_dt <= cutoff:
            count += 1

    embed = make_embed("📊 Recheck 30 days",
                       f"Hiện có **{count}** thành viên offline ≥{days_limit} ngày.")
    sent = await interaction.followup.send(embed=embed)
    last_command_msg_id[interaction.channel_id] = sent.id
    await schedule_autodelete(interaction.channel_id, sent.id)

# ===== /exportdb =====
@tree.command(name="exportdb", description="Xuất database SQLite.")
@app_commands.checks.has_permissions(administrator=True)
async def exportdb(interaction: discord.Interaction):
    await interaction.response.defer()
    db_file_path = DB_PATH
    if not db_file_path.exists():
        embed = make_embed("❌ Lỗi", "Database không tồn tại.")
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id
        await schedule_autodelete(interaction.channel_id, sent.id)
        return

    try:
        sent = await interaction.followup.send(file=discord.File(db_file_path))
        last_command_msg_id[interaction.channel_id] = sent.id
        await schedule_autodelete(interaction.channel_id, sent.id)
    except Exception as e:
        embed = make_embed("❌ Lỗi", f"Không thể gửi database: {e}")
        sent = await interaction.followup.send(embed=embed)
        last_command_msg_id[interaction.channel_id] = sent.id
        await schedule_autodelete(interaction.channel_id, sent.id)

# ===== Khởi chạy bot =====
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Skibidi Bot v6 đã sẵn sàng! Đăng nhập dưới: {bot.user}")

TOKEN = os.getenv("TOKEN")
print(f"[DEBUG] TOKEN loaded: {bool(TOKEN)}")
bot.run(TOKEN)
