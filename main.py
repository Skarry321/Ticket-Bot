import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import logging

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ВЕБ-СЕРВЕР ДЛЯ ПИНГА ==========
app = Flask('')

@app.route('/')
def home():
    return "🤖 Discord Bot is ALIVE on Koyeb!"

@app.route('/health')
def health():
    return "✅ OK", 200

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("🌐 Веб-сервер для пинга запущен")

# ========== DISCORD БОТ ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'✅ БОТ ЗАПУЩЕН: {bot.user}')
    logger.info(f'📊 Серверов: {len(bot.guilds)}')
    
    # Меняем статус
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="тикеты 24/7 | Koyeb"
        )
    )
    
    # Отправляем сообщение в консоль
    print("=" * 50)
    print(f"Бот: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print(f"Koyeb: https://app.koyeb.com")
    print("=" * 50)

@bot.command(name="пинг", aliases=["ping"])
async def ping_command(ctx):
    """Проверка работы бота"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! `{latency}ms`\n"
                   f"🚀 Хостинг: **Koyeb**\n"
                   f"⏰ Работаю без перерыва!")

@bot.command(name="инфо", aliases=["info", "about"])
async def info_command(ctx):
    """Информация о боте"""
    embed = discord.Embed(
        title="🤖 Информация о боте",
        description="Бот для техподдержки с системой тикетов",
        color=discord.Color.blue()
    )
    embed.add_field(name="Хостинг", value="Koyeb (24/7)", inline=True)
    embed.add_field(name="Пинг", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Серверов", value=len(bot.guilds), inline=True)
    embed.add_field(name="Префикс", value="!", inline=True)
    embed.add_field(name="Статус", value="🟢 Онлайн", inline=True)
    embed.set_footer(text="Бесплатный хостинг от Koyeb")
    await ctx.send(embed=embed)

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    keep_alive()  # Запускаем веб-сервер
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.error("❌ ТОКЕН НЕ НАЙДЕН! Добавьте переменную DISCORD_TOKEN в Koyeb")
        exit(1)
    
    logger.info("🚀 Запускаем Discord бота...")
    bot.run(TOKEN)