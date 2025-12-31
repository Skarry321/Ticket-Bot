import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
import time
from flask import Flask
from threading import Thread
import datetime
import asyncio

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('DISCORD_TOKEN')
TICKET_ROLE_NAME = "Ticket"  # Часть названия роли для поиска
COOLDOWN_TIME = 600  # 10 минут
AUTO_SETUP = True  # Автоматически создавать структуру при запуске

# ==================== БАЗА ДАННЫХ ====================
COOLDOWN_FILE = "cooldowns.json"
TICKETS_FILE = "tickets.json"
CONFIG_FILE = "config.json"

def load_data(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== ВЕБ-СЕРВЕР ====================
app = Flask('')
@app.route('/')
def home():
    return "🎫 Ticket Bot by Skarry"

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

# ==================== ПОМОЩНИКИ ДЛЯ РОЛЕЙ ====================
def find_ticket_role(guild):
    """Ищем роль по части названия"""
    for role in guild.roles:
        if "ticket" in role.name.lower():
            return role
    return None

def has_ticket_role(member):
    """Проверяет есть ли у пользователя роль Ticket"""
    for role in member.roles:
        if "ticket" in role.name.lower():
            return True
    return False

def is_admin(member):
    """Проверяет является ли пользователь админом"""
    return member.guild_permissions.administrator

# ==================== ЦВЕТА И ЭМОДЗИ ====================
class Colors:
    PRIMARY = 0x5865F2      # Discord синий
    SUCCESS = 0x57F287      # Зеленый
    WARNING = 0xFEE75C      # Желтый
    DANGER = 0xED4245       # Красный
    PROBLEM = 0xED4245      # Проблема (красный)
    IDEA = 0x57F287         # Идея (зеленый)
    YOUTUBE = 0xFF0000      # YouTube красный

class Emojis:
    TICKET = "🎫"
    PROBLEM = "🚨"
    IDEA = "💡"
    YOUTUBE = "📺"
    PLUS = "➕"
    CHECK = "✅"
    CROSS = "❌"
    LOCK = "🔒"
    UNLOCK = "🔓"
    CLOCK = "⏰"
    INFO = "ℹ️"
    WARNING = "⚠️"
    QUESTION = "❓"
    EDIT = "✏️"
    ADD_USER = "👥"
    STAFF = "🛡️"
    SETTINGS = "⚙️"
    ROBOT = "🤖"
    EMAIL = "📧"
    GAME = "🎮"
    SUBSCRIBE = "👥"
    LINK = "🔗"

# ==================== ФУНКЦИЯ СОЗДАНИЯ СТРУКТУРЫ ====================
async def auto_setup(guild):
    """Автоматически создает структуру при первом запуске"""
    
    config = load_data(CONFIG_FILE)
    if str(guild.id) in config.get('initialized_guilds', []):
        return
    
    print(f"🔄 Создаю структуру для гильдии {guild.name}...")
    
    # Создаем категорию если нет
    category = None
    for cat in guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        try:
            category = await guild.create_category(
                name=f"{Emojis.TICKET} ТИКЕТЫ",
                position=0
            )
        except Exception as e:
            print(f"❌ Ошибка создания категории: {e}")
            return
    
    # Сохраняем в конфиг
    config['initialized_guilds'] = config.get('initialized_guilds', [])
    config['initialized_guilds'].append(str(guild.id))
    save_data(CONFIG_FILE, config)

# ==================== МОДАЛЬНОЕ ОКНО ТИКЕТА ====================
class TicketModal(Modal):
    def __init__(self, ticket_type, title_placeholder, description_placeholder, description_label="📖 ПОДРОБНОЕ ОПИСАНИЕ"):
        # Устанавливаем красивое название
        if ticket_type == "problem":
            title_text = f"{Emojis.PROBLEM} СОЗДАНИЕ ПРОБЛЕМЫ"
            color = Colors.PROBLEM
        elif ticket_type == "idea":
            title_text = f"{Emojis.IDEA} СОЗДАНИЕ ИДЕИ"
            color = Colors.IDEA
        else:  # youtube
            title_text = f"{Emojis.YOUTUBE} ЗАПРОС ДЛЯ YOUTUBE"
            color = Colors.YOUTUBE
        
        super().__init__(title=title_text, timeout=600)
        
        # Красивые поля
        self.title_input = TextInput(
            label="📝 НАЗВАНИЕ / ТЕМА",
            placeholder=title_placeholder,
            max_length=100,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.description = TextInput(
            label=description_label,
            placeholder=description_placeholder,
            max_length=2000,
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description)
        self.ticket_type = ticket_type
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Проверка КД
            cooldowns = load_data(COOLDOWN_FILE)
            user_id = str(interaction.user.id)
            
            if user_id in cooldowns:
                elapsed = time.time() - cooldowns[user_id]
                if elapsed < COOLDOWN_TIME and not has_ticket_role(interaction.user):
                    remaining = COOLDOWN_TIME - elapsed
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    
                    embed = discord.Embed(
                        title=f"{Emojis.CLOCK} КУЛДАУН",
                        description=f"⏳ Следующий тикет через **{minutes} минут {seconds} секунд**",
                        color=Colors.WARNING
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            await interaction.response.defer(ephemeral=True)
            await create_ticket_channel(interaction, self.ticket_type, self.title_input.value, self.description.value)
        except Exception as e:
            print(f"Ошибка в модальном окне: {e}")
            try:
                await interaction.response.send_message(
                    f"{Emojis.CROSS} Произошла ошибка. Попробуйте еще раз.",
                    ephemeral=True
                )
            except:
                pass

# ==================== КНОПКИ ГЛАВНОЙ ПАНЕЛИ ====================
class MainPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label=f"{Emojis.PROBLEM} ПРОБЛЕМА", style=discord.ButtonStyle.red, custom_id="ticket_problem", row=0)
    async def problem_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "problem",
            "Кратко опишите проблему...",
            "• Что именно произошло?\n• Когда началось?\n• Как это влияет на игру?\n• Прикрепите скриншоты если есть"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.IDEA} ИДЕЯ", style=discord.ButtonStyle.green, custom_id="ticket_idea", row=0)
    async def idea_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "idea",
            "Название идеи...",
            "• В чем суть идеи?\n• Какую проблему решает?\n• Какие преимущества?\n• Возможная реализация"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.YOUTUBE} YOUTUBE", style=discord.ButtonStyle.red, custom_id="ticket_youtube", row=1)
    async def youtube_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "youtube",
            "Тема видео...",
            f"• {Emojis.YOUTUBE} **Канал YouTube:**\n• {Emojis.SUBSCRIBE} **Кол-во подписчиков:**\n• {Emojis.GAME} **Ник в игре:**\n• {Emojis.LINK} **Ссылки на соцсети:**\n• {Emojis.EMAIL} **Контакт для связи:**\n• **Описание видео:**",
            "📋 ИНФОРМАЦИЯ ДЛЯ СВЯЗИ"
        )
        await interaction.response.send_modal(modal)

# ==================== ВЫБОР УЧАСТНИКА ДЛЯ ДОБАВЛЕНИЯ ====================
class AddUserModal(Modal):
    def __init__(self, channel):
        super().__init__(title=f"{Emojis.ADD_USER} ДОБАВЛЕНИЕ УЧАСТНИКА", timeout=300)
        self.channel = channel
        
        self.user_input = TextInput(
            label="👤 УКАЖИТЕ УЧАСТНИКА",
            placeholder="@упоминание или ID пользователя",
            required=True,
            max_length=100
        )
        
        self.add_item(self.user_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            user_text = self.user_input.value.strip()
            user = None
            
            # Пробуем найти по упоминанию
            if user_text.startswith('<@') and user_text.endswith('>'):
                try:
                    user_id = int(user_text[2:-1].replace('!', ''))
                    user = interaction.guild.get_member(user_id)
                except:
                    pass
            
            # Пробуем найти по ID
            if not user and user_text.isdigit():
                user = interaction.guild.get_member(int(user_text))
            
            # Пробуем найти по имени
            if not user:
                for member in interaction.guild.members:
                    if user_text.lower() in member.name.lower() or user_text.lower() in (member.display_name or "").lower():
                        user = member
                        break
            
            if not user:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Участник не найден.",
                    color=Colors.DANGER
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            if user.bot:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Нельзя добавлять ботов!",
                    color=Colors.DANGER
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Добавляем участника
            await self.channel.set_permissions(user, 
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                attach_files=True
            )
            
            embed = discord.Embed(
                title=f"{Emojis.CHECK} УЧАСТНИК ДОБАВЛЕН",
                description=f"**{user.mention}** добавлен в тикет!",
                color=Colors.SUCCESS
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Уведомляем в тикете
            ticket_embed = discord.Embed(
                title=f"{Emojis.ADD_USER} НОВЫЙ УЧАСТНИК",
                description=f"{user.mention} добавлен в тикет",
                color=Colors.PRIMARY,
                timestamp=datetime.datetime.now()
            )
            
            await self.channel.send(embed=ticket_embed)
            
        except Exception as e:
            print(f"Ошибка добавления пользователя: {e}")
            try:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Не удалось добавить участника",
                    color=Colors.DANGER
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

# ==================== КНОПКИ ДЛЯ АВТОРА ТИКЕТА ====================
class UserTicketView(View):
    def __init__(self, channel_id, creator_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
    
    @discord.ui.button(label=f"{Emojis.ADD_USER} ДОБАВИТЬ", style=discord.ButtonStyle.blurple, custom_id="user_add", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        try:
            if interaction.user.id != self.creator_id:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только автор тикета может добавлять участников",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Канал не найден",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            modal = AddUserModal(channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в кнопке добавления: {e}")

# ==================== КНОПКИ ДЛЯ АДМИНИСТРАЦИИ ====================
class StaffTicketView(View):
    def __init__(self, channel_id, creator_id, is_open=True):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.is_open = is_open
        
        # Настройка кнопки открыть/закрыть
        if is_open:
            self.close_button.label = f"{Emojis.LOCK} ЗАКРЫТЬ"
            self.close_button.style = discord.ButtonStyle.red
        else:
            self.close_button.label = f"{Emojis.UNLOCK} ОТКРЫТЬ"
            self.close_button.style = discord.ButtonStyle.green
    
    @discord.ui.button(label=f"{Emojis.ADD_USER} ДОБАВИТЬ", style=discord.ButtonStyle.blurple, custom_id="staff_add", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        try:
            if not (has_ticket_role(interaction.user) or is_admin(interaction.user)):
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только администрация может добавлять участников",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Канал не найден",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            modal = AddUserModal(channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в кнопке добавления (staff): {e}")
    
    @discord.ui.button(label=f"{Emojis.QUESTION} ЗАПРОСИТЬ", style=discord.ButtonStyle.gray, custom_id="staff_request", row=0)
    async def request_info(self, interaction: discord.Interaction, button: Button):
        try:
            if not (has_ticket_role(interaction.user) or is_admin(interaction.user)):
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только администрация может запрашивать информацию",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            creator = interaction.guild.get_member(self.creator_id)
            
            if channel and creator:
                embed = discord.Embed(
                    title=f"{Emojis.WARNING} ТРЕБУЕТСЯ ИНФОРМАЦИЯ",
                    description=f"Администрация просит {creator.mention} предоставить дополнительную информацию",
                    color=Colors.WARNING,
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="👤 Запросил", value=interaction.user.mention, inline=True)
                
                await interaction.response.send_message(f"{creator.mention}", embed=embed)
        except Exception as e:
            print(f"Ошибка в кнопке запроса: {e}")
    
    @discord.ui.button(label="", style=discord.ButtonStyle.red, custom_id="close_ticket", row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        try:
            if not (has_ticket_role(interaction.user) or is_admin(interaction.user)):
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только администрация может закрывать тикеты",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} ОШИБКА",
                    description="Канал не найден",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if self.is_open:
                # Закрываем тикет
                embed = discord.Embed(
                    title=f"{Emojis.LOCK} ТИКЕТ ЗАКРЫТ",
                    description="Тикет закрыт. Канал будет удален через 5 секунд...",
                    color=Colors.DANGER,
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="👤 Модератор", value=interaction.user.mention, inline=True)
                
                await interaction.response.send_message(embed=embed)
                await asyncio.sleep(5)
                
                # Удаляем из базы данных
                tickets_data = load_data(TICKETS_FILE)
                if str(channel.id) in tickets_data:
                    del tickets_data[str(channel.id)]
                    save_data(TICKETS_FILE, tickets_data)
                
                await channel.delete()
        except Exception as e:
            print(f"Ошибка при закрытии тикета: {e}")

# ==================== ФУНКЦИЯ СОЗДАНИЯ ТИКЕТА ====================
async def create_ticket_channel(interaction, ticket_type, title, description):
    """Создает канал для тикета"""
    
    # Находим категорию
    category = None
    for cat in interaction.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        try:
            category = await interaction.guild.create_category(
                name=f"{Emojis.TICKET} ТИКЕТЫ",
                position=0
            )
        except:
            # Если не удалось создать категорию, используем существующую
            category = interaction.guild.categories[0]
    
    # Создаем имя канала
    user_name = interaction.user.name.replace(" ", "-").lower()[:10]
    clean_title = "".join(c for c in title if c.isalnum() or c in "-_ ").replace(" ", "-")[:20]
    
    if ticket_type == "problem":
        prefix = Emojis.PROBLEM
        color_name = "ПРОБЛЕМА"
        color = Colors.PROBLEM
    elif ticket_type == "idea":
        prefix = Emojis.IDEA
        color_name = "ИДЕЯ"
        color = Colors.IDEA
    else:  # youtube
        prefix = Emojis.YOUTUBE
        color_name = "YOUTUBE"
        color = Colors.YOUTUBE
    
    channel_name = f"{prefix}-{user_name}-{clean_title}".lower()
    
    # Настраиваем права
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, 
            send_messages=True, 
            read_message_history=True,
            attach_files=True,
            embed_links=True
        ),
        interaction.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            manage_channels=True
        )
    }
    
    # Добавляем права для роли Ticket
    ticket_role = find_ticket_role(interaction.guild)
    if ticket_role:
        overwrites[ticket_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            attach_files=True,
            embed_links=True
        )
    
    # Добавляем админов
    for member in interaction.guild.members:
        if member.guild_permissions.administrator:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True
            )
    
    # Создаем канал
    try:
        ticket_channel = await category.create_text_channel(
            name=channel_name[:100],
            overwrites=overwrites,
            topic=f"{prefix} | {title[:50]}"
        )
    except Exception as e:
        print(f"Ошибка создания канала: {e}")
        embed = discord.Embed(
            title=f"{Emojis.CROSS} ОШИБКА",
            description="Не удалось создать тикет. Попробуйте позже.",
            color=Colors.DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Создаем основное сообщение
    embed = discord.Embed(
        title=f"{prefix} {color_name}",
        description=f"**{title}**\n\n{description}",
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    embed.add_field(name=f"{Emojis.CLOCK} СОЗДАН", value=f"<t:{int(time.time())}:R>", inline=True)
    embed.add_field(name=f"{Emojis.STAFF} АВТОР", value=interaction.user.mention, inline=True)
    
    if ticket_role:
        embed.add_field(name=f"{Emojis.TICKET} ДОСТУП", value=ticket_role.mention, inline=True)
    
    embed.set_footer(text=f"ID: {ticket_channel.id}")
    
    # Создаем кнопки
    staff_view = StaffTicketView(ticket_channel.id, interaction.user.id, is_open=True)
    user_view = UserTicketView(ticket_channel.id, interaction.user.id)
    
    # Отправляем сообщения
    mention_text = f"{interaction.user.mention}"
    if ticket_role:
        mention_text += f" {ticket_role.mention}"
    
    await ticket_channel.send(content=mention_text, embed=embed, view=staff_view)
    
    # Сообщение с кнопками для автора
    user_embed = discord.Embed(
        description=f"{Emojis.INFO} **Ваши кнопки для управления тикетом:**",
        color=Colors.PRIMARY
    )
    await ticket_channel.send(embed=user_embed, view=user_view)
    
    # Сохраняем в базу
    tickets_data = load_data(TICKETS_FILE)
    tickets_data[str(ticket_channel.id)] = {
        "creator": interaction.user.id,
        "type": ticket_type,
        "created_at": time.time()
    }
    save_data(TICKETS_FILE, tickets_data)
    
    # Устанавливаем КД
    if not has_ticket_role(interaction.user):
        cooldowns = load_data(COOLDOWN_FILE)
        cooldowns[str(interaction.user.id)] = time.time()
        save_data(COOLDOWN_FILE, cooldowns)
    
    # Отправляем подтверждение
    confirm_embed = discord.Embed(
        title=f"{Emojis.CHECK} ТИКЕТ СОЗДАН",
        description=f"Ваш тикет создан: {ticket_channel.mention}",
        color=color
    )
    
    confirm_embed.add_field(
        name=f"{Emojis.INFO} ЧТО ДАЛЬШЕ?",
        value="1. Ожидайте ответа администрации\n2. Используйте кнопки в тикете\n3. Не закрывайте канал",
        inline=False
    )
    
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
            name="🎫 тикет систему"
        )
    )
    
    # Автонастройка
    if AUTO_SETUP:
        for guild in bot.guilds:
            await auto_setup(guild)
    
    # Регистрируем View
    bot.add_view(MainPanelView())
    bot.add_view(UserTicketView(0, 0))
    bot.add_view(StaffTicketView(0, 0, True))
    
    print("✅ Бот готов к работе")

@bot.command(name="панель")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    """Создает панель тикетов"""
    
    # Создаем/находим категорию
    category = None
    for cat in ctx.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        category = await ctx.guild.create_category(
            name=f"{Emojis.TICKET} ТИКЕТЫ",
            position=0
        )
    
    # Создаем/находим канал панели
    panel_channel = None
    for channel in category.text_channels:
        if "панель" in channel.name.lower():
            panel_channel = channel
            break
    
    if not panel_channel:
        # Права для канала панели
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                add_reactions=False
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True
            )
        }
        
        # Даем права админам
        for member in ctx.guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )
        
        panel_channel = await category.create_text_channel(
            name=f"{Emojis.TICKET}-панель",
            topic="Создание тикетов - используйте кнопки ниже",
            overwrites=overwrites
        )
    
    # Очищаем канал
    try:
        await panel_channel.purge(limit=100)
    except:
        pass
    
    # Создаем красивую панель
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СИСТЕМА ТИКЕТОВ",
        description="Выберите тип тикета, нажав на соответствующую кнопку:",
        color=Colors.PRIMARY
    )
    
    embed.add_field(
        name=f"{Emojis.PROBLEM} **ПРОБЛЕМА / БАГ**",
        value="• Технические неполадки\n• Ошибки в игре\n• Сбои и лаги\n• Критические проблемы",
        inline=False
    )
    
    embed.add_field(
        name=f"{Emojis.IDEA} **ИДЕЯ / ПРЕДЛОЖЕНИЕ**",
        value="• Новые функции\n• Улучшения геймплея\n• Предложения по балансу\n• Креативные идеи",
        inline=False
    )
    
    embed.add_field(
        name=f"{Emojis.YOUTUBE} **ЗАПРОС ДЛЯ YOUTUBE**",
        value="• Подача на сотрудничество\n• Рекламные интеграции\n• Обзоры и видео\n• Партнерские программы",
        inline=False
    )
    
    # Разделитель
    embed.add_field(name="📋 **ИНФОРМАЦИЯ**", value="═" * 30, inline=False)
    
    embed.add_field(
        name=f"{Emojis.INFO} **ПРАВИЛА СОЗДАНИЯ:**",
        value="• 1 тикет = 1 вопрос/проблема\n• Описывайте проблему максимально подробно\n• Будьте вежливы и уважительны\n• Ожидайте ответа в приватном канале",
        inline=False
    )
    
    embed.add_field(
        name=f"{Emojis.STAFF} **АДМИНИСТРАЦИЯ:**",
        value="• Ответ в течение 24 часов\n• Используйте кнопки в тикете для взаимодействия\n• Не спамьте созданием тикетов",
        inline=False
    )
    
    embed.add_field(
        name=f"{Emojis.CLOCK} **КУЛДАУН:**",
        value="• Между тикетами: 10 минут\n• Для администрации: нет кулдауна",
        inline=False
    )
    
    embed.set_footer(text="🎫 Бот создан Skarry")
    
    # Отправляем панель
    view = MainPanelView()
    message = await panel_channel.send(embed=embed, view=view)
    
    try:
        await message.pin()
    except:
        pass
    
    # Запрещаем писать в канале
    await panel_channel.edit(slowmode_delay=30)
    
    # Подтверждение
    success_embed = discord.Embed(
        title=f"{Emojis.CHECK} ПАНЕЛЬ СОЗДАНА",
        description=f"Панель создана в {panel_channel.mention}",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=success_embed, delete_after=10)
    await ctx.message.delete()

@bot.event
async def on_message(message):
    # Авто-удаление сообщений в канале панели
    if message.channel.name.lower().endswith("-панель") and not message.author.bot:
        try:
            await message.delete()
        except:
            pass
    
    await bot.process_commands(message)

@bot.command(name="пинг")
async def ping(ctx):
    """Проверка работы бота"""
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СТАТУС СИСТЕМЫ",
        color=Colors.PRIMARY
    )
    
    embed.add_field(name="📶 Задержка", value=f"{latency}ms", inline=True)
    embed.add_field(name="✅ Статус", value="Работает", inline=True)
    embed.add_field(name="🎫 Тикетов", value=str(len(load_data(TICKETS_FILE))), inline=True)
    
    embed.set_footer(text="Бот создан Skarry")
    await ctx.send(embed=embed)

@bot.command(name="статистика")
async def stats(ctx):
    """Статистика тикетов"""
    tickets_data = load_data(TICKETS_FILE)
    
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СТАТИСТИКА",
        color=Colors.PRIMARY
    )
    
    total = len(tickets_data)
    problems = len([t for t in tickets_data.values() if t.get("type") == "problem"])
    ideas = len([t for t in tickets_data.values() if t.get("type") == "idea"])
    youtube = len([t for t in tickets_data.values() if t.get("type") == "youtube"])
    
    embed.add_field(name="📊 Всего", value=f"**{total}**", inline=True)
    embed.add_field(name=f"{Emojis.PROBLEM} Проблем", value=f"**{problems}**", inline=True)
    embed.add_field(name=f"{Emojis.IDEA} Идей", value=f"**{ideas}**", inline=True)
    
    if youtube > 0:
        embed.add_field(name=f"{Emojis.YOUTUBE} YouTube", value=f"**{youtube}**", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="сбросить")
@commands.has_permissions(administrator=True)
async def reset_cd(ctx, user: discord.Member = None):
    """Сбросить кулдаун"""
    cooldowns = load_data(COOLDOWN_FILE)
    
    if user:
        if str(user.id) in cooldowns:
            del cooldowns[str(user.id)]
            save_data(COOLDOWN_FILE, cooldowns)
            embed = discord.Embed(
                title=f"{Emojis.CHECK} КУЛДАУН СБРОШЕН",
                description=f"Кулдаун сброшен для {user.mention}",
                color=Colors.SUCCESS
            )
        else:
            embed = discord.Embed(
                title=f"{Emojis.INFO} ИНФОРМАЦИЯ",
                description=f"У {user.mention} нет активного кулдауна",
                color=Colors.WARNING
            )
    else:
        cooldowns.clear()
        save_data(COOLDOWN_FILE, cooldowns)
        embed = discord.Embed(
            title=f"{Emojis.CHECK} ВСЕ КУЛДАУНЫ СБРОШЕНЫ",
            description="Все кулдауны успешно сброшены",
            color=Colors.SUCCESS
        )
    
    await ctx.send(embed=embed)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    keep_alive()
    
    if not TOKEN:
        print("❌ Токен не найден!")
        exit(1)
    
    print("🚀 Запуск бота...")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
