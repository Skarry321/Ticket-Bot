import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# Веб-сервер для пинга
app = Flask('')

@app.route('/')
def home():
    return "Bot by Skarry"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Сам бот
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} работает!')
    await bot.change_presence(activity=discord.Game(name="Бот был создан Skarry"))

@bot.command()
async def пинг(ctx):
    await ctx.send('🏓 Pong!')

@bot.command()
async def помощь(ctx):
    embed = discord.Embed(title="📚 Помощь", color=0x00ff00)
    embed.add_field(name="🎫 Тикеты", value="`!тикет [проблема]` - создать тикет", inline=False)
    embed.add_field(name="📊 Инфо", value="`!пинг` - проверка\n`!инфо` - о боте", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def инфо(ctx):
    await ctx.send('🤖 Бот создан Skarry | Хостинг: Render.com')

# Запуск
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))
