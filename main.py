import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
from flask import Flask
from threading import Thread
import datetime
import asyncio

# ==================== ВЕБ-СЕРВЕР ДЛЯ ПИНГА ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot by Skarry | Minecraft Client Support"

@app.route('/health')
def health():
    return "✅ OK", 200

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Веб-сервер для пинга запущен")

# ==================== DISCORD БОТ ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ==================== ХРАНИЛИЩЕ ДАННЫХ ====================
support_role_name = "Support"

# ==================== МОДАЛЬНОЕ ОКНО СОЗДАНИЯ ТИКЕТА ====================
class TicketModal(Modal, title="📝 Создание тикета"):
    def __init__(self, ticket_type="problem"):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        
        if ticket_type == "problem":
            title_label = "Опишите проблему"
            title_placeholder = "Например: Клиент не запускается после обновления"
        else:  # idea
            title_label = "Опишите идею"
            title_placeholder = "Например: Добавить поддержку модов OptiFine"
        
        self.title_input = TextInput(
            label=title_label,
            placeholder=title_placeholder,
            max_length=100,
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
        await create_ticket_channel(interaction, self.ticket_type, self.title_input.value, self.description.value)

# ==================== КНОПКИ СОЗДАНИЯ ТИКЕТА ====================
class TicketTypeView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🚨 Проблема", style=discord.ButtonStyle.red, emoji="🚨", custom_id="ticket_problem")
    async def problem_ticket(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(ticket_type="problem")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💡 Идея", style=discord.ButtonStyle.green, emoji="💡", custom_id="ticket_idea")
    async def idea_ticket(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(ticket_type="idea")
        await interaction.response.send_modal(modal)

# ==================== КНОПКИ УПРАВЛЕНИЯ ТИКЕТОМ ====================
class TicketControlView(View):
    def __init__(self, channel_id, ticket_type):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.ticket_type = ticket_type
    
    @discord.ui.button(label="🔒 Закрыть", style=discord.ButtonStyle.red, emoji="🔒", custom_id=f"close_ticket_")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # Проверяем права
        is_support = any(role.name == support_role_name for role in interaction.user.roles)
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_support or is_admin):
            await interaction.response.send_message("❌ У вас нет прав для закрытия тикетов!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔒 Тикет закрывается",
            description="Канал удалится через 5 секунд...",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        
        # Удаляем канал
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            await channel.delete(reason=f"Тикет закрыт {interaction.user}")
    
    @discord.ui.button(label="👥 Добавить", style=discord.ButtonStyle.blurple, emoji="👥", custom_id=f"add_user_")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("📝 Используйте команду `!добавить @участник`", ephemeral=True)
    
    @discord.ui.button(label="✅ Решено", style=discord.ButtonStyle.green, emoji="✅", custom_id=f"solved_")
    async def mark_solved(self, interaction: discord.Interaction, button: Button):
        is_support = any(role.name == support_role_name for role in interaction.user.roles)
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_support or is_admin):
            await interaction.response.send_message("❌ У вас нет прав для отметки решенных тикетов!", ephemeral=True)
            return
        
        # Меняем цвет embed на зеленый
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            async for message in channel.history(limit=10):
                if message.embeds:
                    embed = message.embeds[0]
                    embed.color = discord.Color.green()
                    embed.add_field(name="✅ Статус", value=f"Решено {interaction.user.mention}", inline=False)
                    embed.add_field(name="🕐 Решено", value=f"<t:{int(datetime.datetime.now().timestamp())}:R>", inline=True)
                    await message.edit(embed=embed)
                    break
        
        await interaction.response.send_message("✅ Тикет отмечен как решенный!", ephemeral=True)

# ==================== ФУНКЦИИ ====================
async def create_ticket_channel(interaction, ticket_type, title, description):
    """Создает канал для тикета"""
    await interaction.response.defer(ephemeral=True)
    
    # Находим или создаем категорию
    category = None
    if ticket_type == "problem":
        category_name = "🚨 ПРОБЛЕМЫ"
        emoji = "🚨"
        color = discord.Color.red()
    else:  # idea
        category_name = "💡 ИДЕИ"
        emoji = "💡"
        color = discord.Color.green()
    
    for cat in interaction.guild.categories:
        if category_name in cat.name:
            category = cat
            break
    
    if not category:
        category = await interaction.guild.create_category(category_name, position=0)
    
    # Создаем канал
    user_name = interaction.user.name.replace(" ", "-").lower()
    clean_title = "".join(c for c in title if c.isalnum() or c in " -_").replace(" ", "-")[:30]
    channel_name = f"{user_name}-{clean_title}"
    
    # Создаем канал с правами
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    
    # Добавляем роль поддержки
    support_role = discord.utils.get(interaction.guild.roles, name=support_role_name)
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
    
    # Создаем канал
    try:
        ticket_channel = await category.create_text_channel(
            name=channel_name.lower(),
            overwrites=overwrites,
            topic=f"{emoji} {title} | Создал: {interaction.user}"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
        return
    
    # Создаем embed
    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=description,
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    if ticket_type == "problem":
        embed.add_field(name="📁 Тип", value="Проблема", inline=True)
    else:
        embed.add_field(name="📁 Тип", value="Идея/Предложение", inline=True)
    
    embed.add_field(name="👤 Автор", value=interaction.user.mention, inline=True)
    embed.add_field(name="🕐 Создан", value=f"<t:{int(datetime.datetime.now().timestamp())}:R>", inline=True)
    embed.set_author(name=f"Создал: {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text="ID: " + str(ticket_channel.id))
    
    # Кнопки управления
    view = TicketControlView(ticket_channel.id, ticket_type)
    
    # Отправляем сообщение
    mention_text = f"{interaction.user.mention}"
    if support_role:
        mention_text += f" | {support_role.mention}"
    
    await ticket_channel.send(mention_text, embed=embed, view=view)
    
    # Подтверждение пользователю
    success_embed = discord.Embed(
        title="✅ Тикет создан!",
        description=f"Перейдите в {ticket_channel.mention}",
        color=color
    )
    success_embed.add_field(name="Тип", value="Проблема" if ticket_type == "problem" else "Идея", inline=True)
    success_embed.add_field(name="Название", value=title, inline=True)
    await interaction.followup.send(embed=success_embed, ephemeral=True)

# ==================== КОМАНДЫ ====================
@bot.event
async def on_ready():
    """Вызывается при запуске бота"""
    print("=" * 50)
    print(f"🤖 Бот: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Серверов: {len(bot.guilds)}")
    print("=" * 50)
    
    # Устанавливаем статус
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Бот был создан Skarry"
        )
    )
    
    # Регистрируем персистентные View
    bot.add_view(TicketTypeView())
    print("✅ Бот готов к работе!")

@bot.command(name="пинг")
async def ping(ctx):
    """Проверка работоспособности"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Задержка: `{latency}ms`",
        color=discord.Color.green()
    )
    embed.add_field(name="🤖 Создатель", value="Skarry", inline=True)
    embed.add_field(name="🚀 Хостинг", value="Render.com", inline=True)
    embed.add_field(name="⏰ Онлайн", value="24/7", inline=True)
    embed.set_footer(text="Бот был создан Skarry")
    await ctx.send(embed=embed)

@bot.command(name="проблема")
async def problem_cmd(ctx, *, title=None):
    """Создать тикет с проблемой"""
    if not title:
        await ctx.send("❌ Укажите проблему: `!проблема [описание проблемы]`")
        return
    
    await create_ticket_channel(ctx, "problem", title, "Описание не предоставлено")

@bot.command(name="идея")
async def idea_cmd(ctx, *, title=None):
    """Создать тикет с идеей"""
    if not title:
        await ctx.send("❌ Укажите идею: `!идея [описание идеи]`")
        return
    
    await create_ticket_channel(ctx, "idea", title, "Описание не предоставлено")

@bot.command(name="панель")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    """Установить панель создания тикетов"""
    embed = discord.Embed(
        title="📞 Техническая поддержка",
        description="Выберите тип тикета:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🚨 Проблема",
        value="Для сообщения о проблемах, багах, ошибках\nИспользование: `!проблема [описание]`",
        inline=False
    )
    
    embed.add_field(
        name="💡 Идея/Предложение",
        value="Для предложений новых функций, улучшений\nИспользование: `!идея [описание]`",
        inline=False
    )
    
    embed.add_field(
        name="📋 Правила создания тикетов",
        value="1. Четко опишите проблему/идею\n2. Укажите детали\n3. Приложите скриншоты если нужно\n4. Будьте вежливы",
        inline=False
    )
    
    embed.set_footer(text="Бот был создан Skarry")
    
    view = TicketTypeView()
    await ctx.send(embed=embed, view=view)
    await ctx.message.delete()

@bot.command(name="добавить")
async def add_to_ticket(ctx, member: discord.Member):
    """Добавить участника в тикет"""
    if not any(role.name == support_role_name for role in ctx.author.roles) and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ У вас нет прав для добавления участников!")
        return
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ {member.mention} добавлен в тикет!")

@bot.command(name="закрыть")
async def close_ticket_cmd(ctx):
    """Закрыть текущий тикет"""
    if not any(role.name == support_role_name for role in ctx.author.roles) and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ У вас нет прав для закрытия тикетов!")
        return
    
    if "тикет" not in ctx.channel.name.lower() and not any(x in ctx.channel.category.name for x in ["ПРОБЛЕМЫ", "ИДЕИ"]):
        await ctx.send("❌ Эта команда работает только в тикетах!")
        return
    
    embed = discord.Embed(
        title="🔒 Тикет закрывается",
        description="Канал удалится через 5 секунд...",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    await asyncio.sleep(5)
    await ctx.channel.delete()

@bot.command(name="инфо")
async def info(ctx):
    """Информация о боте"""
    embed = discord.Embed(
        title="🤖 Информация о боте",
        description="Бот для техподдержки с системой тикетов",
        color=discord.Color.blue()
    )
    embed.add_field(name="👤 Создатель", value="Skarry", inline=True)
    embed.add_field(name="🌐 Хостинг", value="Render.com", inline=True)
    embed.add_field(name="🏓 Пинг", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="📊 Серверов", value=len(bot.guilds), inline=True)
    embed.add_field(name="⚙️ Префикс", value="!", inline=True)
    embed.add_field(name="📅 Запущен", value=f"<t:{int(datetime.datetime.now().timestamp())}:R>", inline=True)
    embed.set_footer(text="Бот был создан Skarry")
    await ctx.send(embed=embed)

@bot.command(name="помощь")
async def help_cmd(ctx):
    """Список команд"""
    embed = discord.Embed(
        title="📚 Список команд",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎫 ТИКЕТЫ", 
        value="`!проблема [описание]` - создать тикет с проблемой\n`!идея [описание]` - создать тикет с идеей\n`!панель` - панель тикетов (админы)\n`!добавить @участник` - добавить в тикет\n`!закрыть` - закрыть тикет",
        inline=False
    )
    
    embed.add_field(
        name="📊 ИНФОРМАЦИЯ", 
        value="`!пинг` - проверить работу\n`!инфо` - информация о боте\n`!помощь` - это меню",
        inline=False
    )
    
    embed.set_footer(text="Бот был создан Skarry")
    await ctx.send(embed=embed)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    keep_alive()  # Запускаем веб-сервер
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ Ошибка: Токен не найден!")
        print("💡 Добавьте переменную DISCORD_TOKEN в Render")
        exit(1)
    
    print("🚀 Запускаем Discord бота...")
    bot.run(TOKEN)