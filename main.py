import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
import time
from flask import Flask
from threading import Thread
import datetime

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('DISCORD_TOKEN')
SUPPORT_ROLES = ["Admin", "Support", "Модератор"]  # Роли которые видят ВСЕ тикеты
COOLDOWN_TIME = 600  # 10 минут в секундах

# ==================== БАЗА ДАННЫХ ДЛЯ КД ====================
COOLDOWN_FILE = "cooldowns.json"

def load_cooldowns():
    try:
        with open(COOLDOWN_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_cooldowns(data):
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump(data, f)

def check_cooldown(user_id):
    cooldowns = load_cooldowns()
    if str(user_id) in cooldowns:
        elapsed = time.time() - cooldowns[str(user_id)]
        if elapsed < COOLDOWN_TIME:
            return COOLDOWN_TIME - elapsed
    return 0

def set_cooldown(user_id):
    cooldowns = load_cooldowns()
    cooldowns[str(user_id)] = time.time()
    save_cooldowns(cooldowns)

# ==================== ВЕБ-СЕРВЕР ====================
app = Flask('')
@app.route('/')
def home():
    return "Ticket Bot by Skarry | Render.com"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ==================== DISCORD БОТ ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ==================== ПРОВЕРКИ ПРАВ ====================
def is_support(member):
    """Проверяет есть ли у пользователя права поддержки"""
    if member.guild_permissions.administrator:
        return True
    for role_name in SUPPORT_ROLES:
        if discord.utils.get(member.roles, name=role_name):
            return True
    return False

# ==================== МОДАЛЬНОЕ ОКНО ТИКЕТА ====================
class TicketModal(Modal, title="📝 Создание тикета"):
    def __init__(self, ticket_type):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        
        self.title_input = TextInput(
            label="Краткое описание" if ticket_type == "problem" else "Название идеи",
            placeholder="Опишите в 1-2 словах..." if ticket_type == "problem" else "Название предложения...",
            max_length=50,
            required=True
        )
        
        self.description = TextInput(
            label="Подробное описание",
            style=discord.TextStyle.paragraph,
            placeholder="Опишите всё подробно...",
            max_length=1000,
            required=True
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Проверка КД для обычных пользователей
        if not is_support(interaction.user):
            cooldown_left = check_cooldown(interaction.user.id)
            if cooldown_left > 0:
                minutes = int(cooldown_left // 60)
                seconds = int(cooldown_left % 60)
                await interaction.response.send_message(
                    f"⏳ Вы можете создать следующий тикет через {minutes}м {seconds}с",
                    ephemeral=True
                )
                return
        
        await interaction.response.defer(ephemeral=True)
        await create_ticket_channel(interaction, self.ticket_type, self.title_input.value, self.description.value)

# ==================== КНОПКИ ВЫБОРА ТИПА ТИКЕТА ====================
class TicketTypeView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🚨 Проблема", style=discord.ButtonStyle.red, emoji="🚨", custom_id="ticket_problem")
    async def problem_ticket(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal("problem")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💡 Идея", style=discord.ButtonStyle.green, emoji="💡", custom_id="ticket_idea")
    async def idea_ticket(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal("idea")
        await interaction.response.send_modal(modal)

# ==================== КНОПКИ УПРАВЛЕНИЯ ТИКЕТОМ ====================
class TicketControlView(View):
    def __init__(self, channel_id, creator_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
    
    @discord.ui.button(label="🔒 Закрыть", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not is_support(interaction.user) and interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ У вас нет прав для закрытия тикетов!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔒 Тикет закрывается",
            description="Канал удалится через 5 секунд...",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        
        await interaction.channel.delete(reason=f"Тикет закрыт {interaction.user}")
    
    @discord.ui.button(label="👥 Добавить", style=discord.ButtonStyle.blurple, emoji="👥", custom_id="add_user")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        if not is_support(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав для добавления участников!", ephemeral=True)
            return
        
        await interaction.response.send_message("📝 Ответьте на это сообщение, упомянув пользователя: `@username`", ephemeral=True)

# ==================== ОСНОВНАЯ ФУНКЦИЯ СОЗДАНИЯ ТИКЕТА ====================
async def create_ticket_channel(interaction, ticket_type, title, description):
    """Создает канал для тикета"""
    
    # Находим или создаем категорию ТИКЕТЫ
    category = None
    for cat in interaction.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        category = await interaction.guild.create_category("🎫 ТИКЕТЫ", position=0)
    
    # Создаем название канала
    user_name = interaction.user.name.replace(" ", "-").lower()[:10]
    clean_title = "".join(c for c in title if c.isalnum() or c in "-_ ").replace(" ", "-")[:30]
    channel_name = f"{user_name}-{clean_title}".lower()
    
    # Настраиваем права доступа
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    
    # Добавляем права для всех Support/Admin ролей
    for member in interaction.guild.members:
        if is_support(member):
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                manage_messages=True,
                manage_channels=True
            )
    
    # Создаем канал
    try:
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"{'🚨' if ticket_type == 'problem' else '💡'} {title} | Автор: {interaction.user}"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка при создании канала: {e}", ephemeral=True)
        return
    
    # Создаем embed сообщение
    color = discord.Color.red() if ticket_type == "problem" else discord.Color.green()
    embed = discord.Embed(
        title=f"{'🚨 ПРОБЛЕМА' if ticket_type == 'problem' else '💡 ИДЕЯ'}",
        description=f"**{title}**\n\n{description}",
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    embed.add_field(name="👤 Автор", value=interaction.user.mention, inline=True)
    embed.add_field(name="📅 Создан", value=f"<t:{int(time.time())}:R>", inline=True)
    embed.add_field(name="📁 Тип", value="Проблема" if ticket_type == "problem" else "Идея", inline=True)
    
    if not is_support(interaction.user):
        embed.set_footer(text="Support ответит в ближайшее время")
    
    # Создаем кнопки управления
    control_view = TicketControlView(ticket_channel.id, interaction.user.id)
    
    # Отправляем сообщение в тикет
    support_mention = ""
    for role_name in SUPPORT_ROLES:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            support_mention += f"{role.mention} "
    
    await ticket_channel.send(
        content=f"{interaction.user.mention} {support_mention}".strip(),
        embed=embed,
        view=control_view
    )
    
    # Устанавливаем КД для обычных пользователей
    if not is_support(interaction.user):
        set_cooldown(interaction.user.id)
    
    # Отправляем подтверждение пользователю
    confirm_embed = discord.Embed(
        title="✅ Тикет создан!",
        description=f"Перейдите в {ticket_channel.mention}",
        color=color
    )
    confirm_embed.add_field(name="Канал", value=ticket_channel.mention, inline=True)
    confirm_embed.add_field(name="Тип", value="Проблема" if ticket_type == "problem" else "Идея", inline=True)
    
    await interaction.followup.send(embed=confirm_embed, ephemeral=True)

# ==================== КОМАНДЫ БОТА ====================
@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 Бот: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Серверов: {len(bot.guilds)}")
    print("=" * 50)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Бот был создан Skarry"
        )
    )
    
    # Регистрируем персистентные View
    bot.add_view(TicketTypeView())
    print("✅ Бот готов к работе!")

@bot.command(name="панель")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    """Создает панель тикетов (только для админов)"""
    
    # Создаем категорию если нет
    category = None
    for cat in ctx.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        category = await ctx.guild.create_category("🎫 ТИКЕТЫ", position=0)
    
    # Создаем канал для панели
    panel_channel = None
    for channel in category.text_channels:
        if "панель" in channel.name.lower():
            panel_channel = channel
            break
    
    if not panel_channel:
        panel_channel = await category.create_text_channel(
            name="📝-панель-тикетов",
            topic="Панель для создания тикетов"
        )
    
    # Очищаем канал
    try:
        await panel_channel.purge(limit=100)
    except:
        pass
    
    # Создаем embed панели
    embed = discord.Embed(
        title="🎫 Система тикетов",
        description="Выберите тип тикета:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🚨 Проблема",
        value="• Баги, ошибки, неполадки\n• Технические проблемы\n• Что-то не работает",
        inline=False
    )
    
    embed.add_field(
        name="💡 Идея / Предложение",
        value="• Новые функции\n• Улучшения\n• Предложения по развитию",
        inline=False
    )
    
    embed.add_field(
        name="📋 Правила",
        value="• Опишите проблему четко\n• Будьте вежливы\n• Один тикет - одна проблема\n• КД между тикетами: 10 минут",
        inline=False
    )
    
    embed.set_footer(text="Бот создан Skarry | Админы видят все тикеты")
    
    # Отправляем панель с кнопками
    view = TicketTypeView()
    await panel_channel.send(embed=embed, view=view)
    
    await ctx.message.delete()
    await ctx.send(f"✅ Панель создана в {panel_channel.mention}", delete_after=5)

@bot.command(name="пинг")
async def ping(ctx):
    """Проверка работы бота"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="Задержка", value=f"`{latency}ms`", inline=True)
    embed.add_field(name="Создатель", value="Skarry", inline=True)
    embed.add_field(name="Хостинг", value="Render.com", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="кд")
async def check_cooldown_cmd(ctx):
    """Проверить свой КД"""
    if is_support(ctx.author):
        await ctx.send("✅ У вас нет КД (права Support/Admin)")
        return
    
    cooldown_left = check_cooldown(ctx.author.id)
    if cooldown_left > 0:
        minutes = int(cooldown_left // 60)
        seconds = int(cooldown_left % 60)
        await ctx.send(f"⏳ Ваш КД: {minutes} минут {seconds} секунд")
    else:
        await ctx.send("✅ Вы можете создать тикет сейчас!")

@bot.command(name="тикет")
async def create_ticket_cmd(ctx, *, title=None):
    """Создать тикет через команду (альтернатива кнопкам)"""
    if not title:
        await ctx.send("❌ Используйте: `!тикет [описание]`")
        return
    
    if not is_support(ctx.author):
        cooldown_left = check_cooldown(ctx.author.id)
        if cooldown_left > 0:
            minutes = int(cooldown_left // 60)
            await ctx.send(f"⏳ Вы можете создать тикет через {minutes} минут")
            return
    
    await create_ticket_channel(ctx, "problem", title, "Создано через команду")
    await ctx.message.delete()

@bot.command(name="добавить")
async def add_to_ticket(ctx, member: discord.Member):
    """Добавить участника в тикет (только Support)"""
    if not is_support(ctx.author):
        await ctx.send("❌ У вас нет прав для добавления участников!")
        return
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ {member.mention} добавлен в тикет!")

@bot.command(name="закрыть")
async def close_ticket(ctx):
    """Закрыть текущий тикет"""
    channel = ctx.channel
    if "тикет" not in channel.category.name.lower():
        await ctx.send("❌ Эта команда работает только в тикетах!")
        return
    
    # Находим создателя тикета (первое упоминание в теме)
    creator_id = None
    if channel.topic:
        for part in channel.topic.split():
            if part.startswith('<@') and part.endswith('>'):
                try:
                    creator_id = int(part[2:-1])
                    break
                except:
                    pass
    
    if not is_support(ctx.author) and ctx.author.id != creator_id:
        await ctx.send("❌ У вас нет прав для закрытия этого тикета!")
        return
    
    embed = discord.Embed(
        title="🔒 Тикет закрывается",
        description="Канал удалится через 5 секунд...",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    await channel.delete()

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    keep_alive()
    
    if not TOKEN:
        print("❌ Ошибка: Токен не найден!")
        print("💡 Добавьте DISCORD_TOKEN в переменные окружения Render")
        exit(1)
    
    print("🚀 Запускаем Discord бота...")
    bot.run(TOKEN)
