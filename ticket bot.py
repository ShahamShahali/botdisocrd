import discord
import os
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import sqlite3
import asyncio
from itertools import cycle
import sys
import subprocess
import time



# اتصال به دیتابیس
conn = sqlite3.connect("bot_database.db")
cursor = conn.cursor()

# ایجاد جدول برای ذخیره تیکت‌ها
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        user_id INTEGER PRIMARY KEY,
        channel_id INTEGER
    )
''')

# ایجاد جدول برای ذخیره شماره‌های استفاده‌شده
cursor.execute('''
    CREATE TABLE IF NOT EXISTS used_ticket_numbers (
        ticket_number INTEGER PRIMARY KEY
    )
''')
conn.commit()

# دریافت شماره تیکت بعدی
def get_next_ticket_number():
    cursor.execute("SELECT MAX(ticket_number) FROM used_ticket_numbers")
    result = cursor.fetchone()
    return result[0] + 1 if result[0] is not None else 1

# ذخیره تیکت در دیتابیس
def add_ticket(user_id, channel_id, ticket_number):
    cursor.execute("INSERT INTO tickets (user_id, channel_id) VALUES (?, ?)", (user_id, channel_id))
    cursor.execute("INSERT INTO used_ticket_numbers (ticket_number) VALUES (?)", (ticket_number,))
    conn.commit()

# حذف تیکت از دیتابیس
def remove_ticket(user_id):
    cursor.execute("DELETE FROM tickets WHERE user_id = ?", (user_id,))
    conn.commit()

# بررسی اینکه آیا کاربر تیکت باز دارد
def has_open_ticket(user_id):
    cursor.execute("SELECT * FROM tickets WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True


bot = commands.Bot(command_prefix="!", intents=intents)

TICKET_CATEGORY_ID = 1342420761692082246
TICKET_CHANNEL_ID = 1342415408950546432
ANNOUNCEMENT_CHANNEL_ID = 1343167692714151998  # آیدی کانال اعلام وضعیت ربات
OFFLINE_NOTIFICATION_CHANNEL_ID = 1343167692714151998  # کانال برای اعلام آفلاین شدن بات
GUILD_ID = 1339573715179933758  # آی‌دی سرور موردنظر
ROLE_ID = 1342464970004107294  # آی‌دی نقش موردنظر
# لیست وضعیت‌های مورد نظر

@bot.event
async def on_ready():
    print(f' bot on shod!')
    # ارسال پیام اعلام روشن شدن ربات
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel:
        await channel.send(f"<@&1343172298022195352> <:bot:1343170633164525698> **{bot.user.name}** Online Shod <a:notif2:1343170568874364998>!")

    # همگام‌سازی دستورات اسلش
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")

        bot.loop.create_task(update_status())  # اجرای تابع برای بروزرسانی وضعیت
        # ارسال پیام ایجاد تیکت و حذف پیام قبلی
        channel = bot.get_channel(TICKET_CHANNEL_ID)
        if channel:
            async for message in channel.history(limit=10):
                if message.author == bot.user:
                    await message.delete()  
                    break

            button = Button(label="🎫 ایجاد تیکت", style=discord.ButtonStyle.primary)

            async def button_callback(interaction: discord.Interaction):
                await create_ticket(interaction)

            button.callback = button_callback
            view = View(timeout=None)  # اضافه کردن timeout=None
            view.add_item(button)
            await channel.send("برای ایجاد تیکت روی دکمه زیر کلیک کنید:", view=view)

    except Exception as e:
        print(f"Error syncing slash commands: {e}")

async def create_ticket(interaction):
    user_id = interaction.user.id
    username = interaction.user.name

    if has_open_ticket(user_id):
        await interaction.response.send_message("<a:800536235931467796:1343540530994352208> Shoma Yek Ticket Baz Darid!", ephemeral=True)
        return

    guild = interaction.guild
    category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
    if not category:
        await interaction.response.send_message("⚠ دسته‌بندی تیکت یافت نشد!", ephemeral=True)
        return

    ticket_number = get_next_ticket_number()
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    ticket_channel = await guild.create_text_channel(f"ticket-{ticket_number}", category=category, overwrites=overwrites)

    add_ticket(user_id, ticket_channel.id, ticket_number)

    close_button = Button(label="🔒 بستن تیکت", style=discord.ButtonStyle.danger)

    async def close_callback(interaction: discord.Interaction):
        await ticket_channel.set_permissions(interaction.user, read_messages=False, send_messages=False)
        remove_ticket(user_id)
        await interaction.response.send_message("Ticket Shoma Baste Shod.<a:7799890954631249921:1343540553471627325> ", ephemeral=True)

        delete_button = Button(label="❌ Delete Ticket", style=discord.ButtonStyle.danger)

        async def delete_callback(interaction: discord.Interaction):
            if interaction.user.guild_permissions.administrator:
                await ticket_channel.delete()
                await interaction.response.send_message("✅ Ticket Hazf Shod.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠ شما اجازه حذف تیکت را ندارید!", ephemeral=True)

        delete_button.callback = delete_callback
        delete_view = View(timeout=None)  # اضافه کردن timeout=None
        delete_view.add_item(delete_button)

        await ticket_channel.send("<:notif:1343170658854506607> <@&1342464970004107294> TICKET BASTE SHODE JAHAT DELETE:", view=delete_view)

    close_button.callback = close_callback
    close_view = View(timeout=None)  # اضافه کردن timeout=None
    close_view.add_item(close_button)

    await ticket_channel.send(f"{interaction.user.mention} ||<@&1342464970004107294>||", view=close_view)
    await interaction.response.send_message(f"✅ Ticket Shoma Sakhte Shode: {ticket_channel.mention}", ephemeral=True)

@bot.event
async def on_error(event, *args, **kwargs):
    # زمانی که خطا رخ می‌دهد (مثلاً بات آفلاین می‌شود)
    if isinstance(args[0], discord.ConnectionClosed):
        # زمانی که اتصال بات قطع شده است(pak beshe!!!!!!!!)
        channel = bot.get_channel(OFFLINE_NOTIFICATION_CHANNEL_ID)
        if channel:
            await channel.send(f"**{bot.user.name}** به دلیل قطع ارتباط از دیسکورد آفلاین شد!")

@bot.tree.command(name="clear_db", description="Hazf Data Base")
@app_commands.default_permissions(administrator=True)
async def clear_db(interaction: discord.Interaction):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets")
    conn.commit()
    conn.close()
    await interaction.response.send_message("Data Base Removed!<a:7799890954631249921:1343540553471627325>  ", ephemeral=True)

COLOR_CHOICES = [
    app_commands.Choice(name="قرمز", value="red"),
    app_commands.Choice(name="سبز", value="green"),
    app_commands.Choice(name="ابی", value="blue"),
    app_commands.Choice(name="زرد", value="yellow"),
    app_commands.Choice(name="بنفش", value="purple")
]

@bot.tree.command(name="c", description="ایجاد ایمبد از یک پیام")
@app_commands.describe(message="پیام", color="رنگ")
@app_commands.choices(color=COLOR_CHOICES)
async def c(interaction: discord.Interaction, message: str, color: app_commands.Choice[str]=None):
    user = interaction.user 
    user = user.mention

    if color is None:
        colore = discord.Color.red()
    else:
        color_map = {
            "red": discord.Color.red(),
            "green": discord.Color.green(),
            "blue": discord.Color.blue(),
            "yellow": discord.Color.yellow(),
            "purple": discord.Color.purple()
        }
        colore = color_map[color.value]

    embed = discord.Embed(description="📜", color=colore)
    embed.add_field(name="پیام از طرف :", value=user, inline=False)
    embed.add_field(name="🔻🔻🔻", value="", inline=False)   
    embed.add_field(name="پیام : ", value=message, inline=False)

    await interaction.response.send_message(embed=embed)

# اضافه کردن دستور /cc برای ارسال پیام ناشناس
@bot.tree.command(name="cc", description="Ersal Payam Nashenas Az Taraf Bot")
@app_commands.default_permissions(administrator=True)
async def cc(interaction: discord.Interaction, message: str):
    if interaction.user.guild_permissions.administrator:
        # ارسال پیام ناشناس/
        await interaction.channel.send(message)
        await interaction.response.send_message("<a:7799890954631249921:1343540553471627325>", ephemeral=True)
    else:
        await interaction.response.send_message("⚠ شما دسترسی به این دستور را ندارید.", ephemeral=True)
# دستور برای خاموش و روشن کردن بات
@bot.command()
async def restart(ctx):
    # چک می‌کنیم که آیا کاربر ادمین است یا نه
    if ctx.author.guild_permissions.administrator:
        # پیام فرد را حذف می‌کنیم
        await ctx.message.delete()
        
        await ctx.send("بات در حال خاموش و روشن شدن است...")
        
        await bot.close()  # بات را خاموش می‌کند
        time.sleep(5)  # 5 ثانیه منتظر می‌مانیم
        subprocess.Popen([sys.executable, sys.argv[0]])  # بات را مجدداً اجرا می‌کنیم
    else:
        await ctx.send("شما اجازه دسترسی به این دستور را ندارید.")

# دستور برای خاموش کردن بات
@bot.command()
async def off(ctx):
    # چک می‌کنیم که آیا کاربر ادمین است یا نه
    if ctx.author.guild_permissions.administrator:
        # پیام فرد را حذف می‌کنیم
        await ctx.message.delete()
        
        await ctx.send("بات در حال خاموش شدن است...")
        await bot.close()  # بات را خاموش می‌کند
    else:
        await ctx.send("شما اجازه دسترسی به این دستور را ندارید.")
        
async def update_status():
    await bot.wait_until_ready()
    while not bot.is_closed():
        guild = bot.get_guild(GUILD_ID)  # دریافت سرور مشخص‌شده
        if guild:
            member_count = guild.member_count  # تعداد کل اعضای سرور
            role = guild.get_role(ROLE_ID)  # دریافت نقش مشخص‌شده
            if role:
                role_member_count = len(role.members)  # تعداد اعضای دارای این نقش
                
                # نمایش تعداد اعضای سرور با "Watching"
                await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"👥 {member_count} members"))
                await asyncio.sleep(15)  # نمایش برای ۳۰ ثانیه
                
                # نمایش تعداد اعضای نقش با "Watching"
                await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{role_member_count} {role.name}"))
            else:
                print("❌ نقش یافت نشد!")
        else:
            print("❌ سرور یافت نشد!")

        await asyncio.sleep(15)  # بروزرسانی هر ۳۰ ثانیه

bot.run("MTMzOTU3Mzg1MTc5Njc5OTU3OQ.G1QIM_.rycCfxUQcfSLfdgIOUugcKyByoQEGkZfuYGPeo")
