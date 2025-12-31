import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
import os
import json
import time
from flask import Flask
from threading import Thread
import datetime
import asyncio

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('DISCORD_TOKEN')
TICKET_ROLE = "Ticket"  # Роль которая видит ВСЕ тикеты
COOLDOWN_TIME = 600  # 10 минут

# ==================== БАЗА ДАННЫХ ====================
COOLDOWN_FILE = "cooldowns.json"
TICKETS_FILE = "tickets.json"

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
    return "🎫 Ticket Bot by Skarry | YouTube Guide Available"

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
def has_ticket_role(member):
    """Проверяет есть ли у пользователя роль Ticket"""
    return discord.utils.get(member.roles, name=TICKET_ROLE) is not None

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

# ==================== МОДАЛЬНОЕ ОКНО ТИКЕТА ====================
class TicketModal(Modal):
    def __init__(self, ticket_type, title_placeholder, description_placeholder):
        # Устанавливаем красивое название
        if ticket_type == "problem":
            title_text = f"{Emojis.PROBLEM} СОЗДАНИЕ ПРОБЛЕМЫ"
            color = Colors.PROBLEM
        elif ticket_type == "idea":
            title_text = f"{Emojis.IDEA} СОЗДАНИЕ ИДЕИ"
            color = Colors.IDEA
        else:  # youtube
            title_text = f"{Emojis.YOUTUBE} СОЗДАНИЕ YOUTUBE ЗАПРОСА"
            color = Colors.YOUTUBE
        
        super().__init__(title=title_text, timeout=300)
        
        # Красивые поля
        self.title_input = TextInput(
            label="📝 КРАТКОЕ ОПИСАНИЕ",
            placeholder=title_placeholder,
            max_length=100,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.description = TextInput(
            label="📖 ПОДРОБНОЕ ОПИСАНИЕ",
            placeholder=description_placeholder,
            max_length=1500,
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description)
        self.ticket_type = ticket_type
    
    async def on_submit(self, interaction: discord.Interaction):
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
                    title=f"{Emojis.CLOCK} КУЛДАУН АКТИВЕН",
                    description=f"⏳ Вы сможете создать следующий тикет через **{minutes} минут {seconds} секунд**",
                    color=Colors.WARNING
                )
                embed.set_footer(text="Администраторы и роль Ticket не имеют кулдауна")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        await create_ticket_channel(interaction, self.ticket_type, self.title_input.value, self.description.value)

# ==================== КНОПКИ ГЛАВНОЙ ПАНЕЛИ ====================
class MainPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label=f"{Emojis.PROBLEM} ПРОБЛЕМА", style=discord.ButtonStyle.red, custom_id="ticket_problem_main", row=0)
    async def problem_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "problem",
            "Опишите проблему кратко...",
            "• Что произошло?\n• Когда началось?\n• Как воспроизвести?\n• Скриншоты/логи если есть"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.IDEA} ИДЕЯ", style=discord.ButtonStyle.green, custom_id="ticket_idea_main", row=0)
    async def idea_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "idea",
            "Название идеи/предложения...",
            "• В чем суть идеи?\n• Какая проблема решается?\n• Как это улучшит проект?\n• Примеры реализации"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.YOUTUBE} YOUTUBE", style=discord.ButtonStyle.red, custom_id="ticket_youtube_main", row=1)
    async def youtube_button(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal(
            "youtube",
            "Тема для YouTube видео...",
            "• О чем должно быть видео?\n• Для кого это видео?\n• Какие моменты осветить?\n• Примерная структура"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.INFO} ИНСТРУКЦИЯ", style=discord.ButtonStyle.blurple, custom_id="ticket_guide", row=2)
    async def guide_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title=f"{Emojis.YOUTUBE} ВИДЕО-ГИД ПО ИСПОЛЬЗОВАНИЮ",
            description="📺 **Полная инструкция как пользоваться системой тикетов:**",
            color=Colors.PRIMARY,
            url="https://www.youtube.com"  # Замени на свою ссылку
        )
        
        embed.add_field(
            name="🎬 ЧТО В ВИДЕО:",
            value="• Как создавать тикеты\n• Правильное описание проблем\n• Что делать после создания\n• Ответы на частые вопросы",
            inline=False
        )
        
        embed.add_field(
            name="📋 ОСНОВНЫЕ ПРАВИЛА:",
            value="• 1 тикет = 1 проблема\n• Описывайте четко и подробно\n• Прикрепляйте скриншоты\n• Будьте вежливы и терпеливы",
            inline=False
        )
        
        embed.add_field(
            name="⚡ БЫСТРЫЕ ШАГИ:",
            value="1. Выберите тип тикета\n2. Заполните форму\n3. Ждите ответа в личном канале\n4. Общайтесь с поддержкой",
            inline=False
        )
        
        embed.set_image(url="https://i.imgur.com/3tM5Z6G.png")  # Замени на превью своего видео
        embed.set_footer(text="Нажмите на заголовок чтобы перейти к видео-гиду")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== ВЫБОР УЧАСТНИКА ДЛЯ ДОБАВЛЕНИЯ ====================
class AddUserModal(Modal):
    def __init__(self, channel):
        super().__init__(title=f"{Emojis.ADD_USER} ДОБАВЛЕНИЕ УЧАСТНИКА", timeout=120)
        self.channel = channel
        
        self.user_input = TextInput(
            label="👤 УПОМЯНИТЕ УЧАСТНИКА",
            placeholder="@username или ID пользователя",
            required=True
        )
        
        self.reason = TextInput(
            label="📝 ПРИЧИНА ДОБАВЛЕНИЯ",
            placeholder="Зачем добавляете этого участника?",
            required=False,
            style=discord.TextStyle.short
        )
        
        self.add_item(self.user_input)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Парсим упоминание или ID
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
            error_embed = discord.Embed(
                title=f"{Emojis.CROSS} ОШИБКА",
                description="Участник не найден. Укажите:\n• @упоминание\n• ID пользователя\n• Имя пользователя",
                color=Colors.DANGER
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        if user.bot:
            error_embed = discord.Embed(
                title=f"{Emojis.CROSS} ОШИБКА",
                description="Нельзя добавлять ботов в тикет!",
                color=Colors.DANGER
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        # Добавляем участника
        try:
            await self.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
            
            success_embed = discord.Embed(
                title=f"{Emojis.CHECK} УЧАСТНИК ДОБАВЛЕН",
                description=f"**{user.mention}** добавлен в тикет!",
                color=Colors.SUCCESS
            )
            
            if self.reason.value:
                success_embed.add_field(name="📋 Причина", value=self.reason.value, inline=False)
            
            success_embed.add_field(name="👤 Добавил", value=interaction.user.mention, inline=True)
            success_embed.add_field(name="📅 Время", value=f"<t:{int(time.time())}:R>", inline=True)
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Уведомляем в тикете
            ticket_embed = discord.Embed(
                title=f"{Emojis.ADD_USER} НОВЫЙ УЧАСТНИК",
                description=f"**{user.mention}** был добавлен в тикет {interaction.user.mention}",
                color=Colors.PRIMARY,
                timestamp=datetime.datetime.now()
            )
            
            if self.reason.value:
                ticket_embed.add_field(name="📝 Причина", value=self.reason.value, inline=False)
            
            await self.channel.send(embed=ticket_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title=f"{Emojis.CROSS} ОШИБКА",
                description=f"Не удалось добавить участника: {str(e)}",
                color=Colors.DANGER
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

# ==================== КНОПКИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ (без роли Ticket) ====================
class UserTicketView(View):
    def __init__(self, channel_id, creator_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
    
    @discord.ui.button(label=f"{Emojis.PLUS} ДОБАВИТЬ", style=discord.ButtonStyle.blurple, emoji=Emojis.PLUS, custom_id="user_add", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                f"{Emojis.CROSS} Только автор тикета может добавлять участников!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(f"{Emojis.CROSS} Канал не найден!", ephemeral=True)
            return
        
        modal = AddUserModal(channel)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.EDIT} ДОПОЛНИТЬ", style=discord.ButtonStyle.gray, emoji=Emojis.EDIT, custom_id="user_supplement", row=0)
    async def supplement(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                f"{Emojis.CROSS} Только автор тикета может дополнить тикет!",
                ephemeral=True
            )
            return
        
        # Отправляем сообщение от имени бота
        embed = discord.Embed(
            title=f"{Emojis.EDIT} ЗАПРОС НА ДОПОЛНЕНИЕ",
            description=f"**{interaction.user.mention} просит администрацию дополнить информацию по тикету.**\n\nПожалуйста, уточните детали если это необходимо.",
            color=Colors.WARNING,
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text="Инициатор запроса")
        
        await interaction.response.send_message(
            f"{Emojis.STAFF} <@&{TICKET_ROLE}> запрос на дополнение информации!",
            embed=embed
        )

# ==================== КНОПКИ ДЛЯ АДМИНОВ/РОЛИ TICKET ====================
class StaffTicketView(View):
    def __init__(self, channel_id, creator_id, is_open=True):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.is_open = is_open
        
        # Динамически меняем кнопку открыть/закрыть
        if is_open:
            self.open_close_button.label = f"{Emojis.LOCK} ЗАКРЫТЬ"
            self.open_close_button.style = discord.ButtonStyle.red
        else:
            self.open_close_button.label = f"{Emojis.UNLOCK} ОТКРЫТЬ"
            self.open_close_button.style = discord.ButtonStyle.green
    
    @discord.ui.button(label=f"{Emojis.PLUS} ДОБАВИТЬ", style=discord.ButtonStyle.blurple, emoji=Emojis.PLUS, custom_id="staff_add", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        if not has_ticket_role(interaction.user) and not is_admin(interaction.user):
            await interaction.response.send_message(
                f"{Emojis.CROSS} Только администрация может добавлять участников!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(f"{Emojis.CROSS} Канал не найден!", ephemeral=True)
            return
        
        modal = AddUserModal(channel)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label=f"{Emojis.QUESTION} ДОПОЛНИТЬ", style=discord.ButtonStyle.gray, emoji=Emojis.QUESTION, custom_id="staff_request_info", row=0)
    async def request_info(self, interaction: discord.Interaction, button: Button):
        if not has_ticket_role(interaction.user) and not is_admin(interaction.user):
            await interaction.response.send_message(
                f"{Emojis.CROSS} Только администрация может запрашивать информацию!",
                ephemeral=True
            )
            return
        
        # Отправляем сообщение с упоминанием автора
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            creator = interaction.guild.get_member(self.creator_id)
            if creator:
                embed = discord.Embed(
                    title=f"{Emojis.WARNING} ТРЕБУЕТСЯ ДОПОЛНИТЬ",
                    description=f"**Администрация просит {creator.mention} дополнить информацию по тикету.**\n\nПожалуйста, предоставьте:\n• Дополнительные детали\n• Скриншоты если есть\n• Уточняющую информацию",
                    color=Colors.WARNING,
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="👤 Запросил", value=interaction.user.mention, inline=True)
                embed.set_footer(text="Просьба ответить в течение 24 часов")
                
                await interaction.response.send_message(f"{creator.mention} {Emojis.WARNING}", embed=embed)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.red, custom_id="open_close", row=1)
    async def open_close_button(self, interaction: discord.Interaction, button: Button):
        if not has_ticket_role(interaction.user) and not is_admin(interaction.user):
            await interaction.response.send_message(
                f"{Emojis.CROSS} Только администрация может менять статус тикета!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(f"{Emojis.CROSS} Канал не найден!", ephemeral=True)
            return
        
        if self.is_open:
            # Закрываем тикет
            embed = discord.Embed(
                title=f"{Emojis.LOCK} ТИКЕТ ЗАКРЫТ",
                description=f"Тикет закрыт {interaction.user.mention}\nКанал будет удален через 10 секунд...",
                color=Colors.DANGER,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="📅 Закрыт", value=f"<t:{int(time.time())}:R>", inline=True)
            embed.add_field(name="👤 Модератор", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(10)
            await channel.delete()
        else:
            # Открываем тикет (если вдруг понадобится)
            await interaction.response.send_message(f"{Emojis.UNLOCK} Тикет открыт!", ephemeral=True)

# ==================== ФУНКЦИЯ СОЗДАНИЯ ТИКЕТА ====================
async def create_ticket_channel(interaction, ticket_type, title, description):
    """Создает красивый канал для тикета"""
    
    # Находим или создаем категорию
    category = None
    for cat in interaction.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        category = await interaction.guild.create_category(
            name=f"{Emojis.TICKET} ТИКЕТЫ",
            position=0
        )
    
    # Создаем красивое название канала
    user_name = interaction.user.name.replace(" ", "-").lower()[:12]
    clean_title = "".join(c for c in title if c.isalnum() or c in "-_ ").replace(" ", "-")[:25]
    
    if ticket_type == "problem":
        prefix = Emojis.PROBLEM
        color_name = "проблема"
        color = Colors.PROBLEM
    elif ticket_type == "idea":
        prefix = Emojis.IDEA
        color_name = "идея"
        color = Colors.IDEA
    else:  # youtube
        prefix = Emojis.YOUTUBE
        color_name = "ютуб"
        color = Colors.YOUTUBE
    
    channel_name = f"{prefix}-{user_name}-{clean_title}".lower()
    
    # Настраиваем права доступа
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
            manage_channels=True,
            manage_roles=True
        )
    }
    
    # Добавляем права для роли Ticket и админов
    ticket_role = discord.utils.get(interaction.guild.roles, name=TICKET_ROLE)
    if ticket_role:
        overwrites[ticket_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            manage_channels=True,
            attach_files=True,
            embed_links=True
        )
    
    # Добавляем админов
    for member in interaction.guild.members:
        if member.guild_permissions.administrator:
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
            topic=f"{prefix} | {title} | Автор: {interaction.user}"
        )
    except Exception as e:
        error_embed = discord.Embed(
            title=f"{Emojis.CROSS} ОШИБКА",
            description=f"Не удалось создать канал: {str(e)}",
            color=Colors.DANGER
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)
        return
    
    # Создаем красивый embed
    embed = discord.Embed(
        title=f"{prefix} ТИКЕТ: {title.upper()}",
        description=description,
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    # Добавляем поля
    embed.add_field(name=f"{Emojis.TICKET} ТИП", value=color_name.capitalize(), inline=True)
    embed.add_field(name=f"{Emojis.INFO} СТАТУС", value="🔓 ОТКРЫТ", inline=True)
    embed.add_field(name=f"{Emojis.CLOCK} СОЗДАН", value=f"<t:{int(time.time())}:R>", inline=True)
    
    embed.add_field(name=f"{Emojis.STAFF} АВТОР", value=interaction.user.mention, inline=True)
    embed.add_field(name="📊 ID", value=f"`{ticket_channel.id}`", inline=True)
    embed.add_field(name="🏷️ ТЭГ", value=f"`{ticket_type}`", inline=True)
    
    # Разделитель
    embed.add_field(name="📋 ДОСТУПНЫЕ ДЕЙСТВИЯ", value="="*30, inline=False)
    
    if ticket_role:
        embed.add_field(
            name=f"{Emojis.STAFF} ДЛЯ АДМИНИСТРАЦИИ",
            value=f"• Используйте кнопки ниже\n• Роль {ticket_role.mention} видит все тикеты\n• Добавляйте участников при необходимости",
            inline=False
        )
    
    embed.add_field(
        name=f"{Emojis.INFO} ДЛЯ АВТОРА",
        value="• Вы можете добавлять других участников\n• Можете запросить дополнение информации\n• Тикет будет закрыт администрацией",
        inline=False
    )
    
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text=f"Тикет #{ticket_channel.id} • Бот создан Skarry")
    
    # Создаем кнопки
    user_view = UserTicketView(ticket_channel.id, interaction.user.id)
    staff_view = StaffTicketView(ticket_channel.id, interaction.user.id, is_open=True)
    
    # Отправляем сообщение
    mention_text = f"{interaction.user.mention}"
    if ticket_role:
        mention_text += f" {ticket_role.mention}"
    
    # Отправляем основное сообщение с кнопками для админов
    staff_message = await ticket_channel.send(
        content=mention_text,
        embed=embed,
        view=staff_view
    )
    
    # Отправляем отдельное сообщение с кнопками для автора (под основным)
    user_embed = discord.Embed(
        description=f"{Emojis.INFO} **Кнопки ниже доступны только вам (автору тикета):**",
        color=Colors.PRIMARY
    )
    user_message = await ticket_channel.send(embed=user_embed, view=user_view)
    
    # Сохраняем ID сообщений для будущих обновлений
    tickets_data = load_data(TICKETS_FILE)
    tickets_data[str(ticket_channel.id)] = {
        "staff_message": staff_message.id,
        "user_message": user_message.id,
        "creator": interaction.user.id,
        "type": ticket_type,
        "created_at": time.time()
    }
    save_data(TICKETS_FILE, tickets_data)
    
    # Устанавливаем КД для обычных пользователей
    if not has_ticket_role(interaction.user) and not is_admin(interaction.user):
        cooldowns = load_data(COOLDOWN_FILE)
        cooldowns[str(interaction.user.id)] = time.time()
        save_data(COOLDOWN_FILE, cooldowns)
    
    # Отправляем подтверждение пользователю
    confirm_embed = discord.Embed(
        title=f"{Emojis.CHECK} ТИКЕТ СОЗДАН!",
        description=f"Ваш тикет успешно создан: {ticket_channel.mention}",
        color=color
    )
    
    confirm_embed.add_field(
        name=f"{Emojis.INFO} ЧТО ДАЛЬШЕ?",
        value=f"1. Перейдите в {ticket_channel.mention}\n2. Ожидайте ответа администрации\n3. Используйте кнопки в тикете для взаимодействия",
        inline=False
    )
    
    confirm_embed.add_field(name="📁 КАТЕГОРИЯ", value=category.name, inline=True)
    confirm_embed.add_field(name="🎯 ТИП", value=color_name.capitalize(), inline=True)
    confirm_embed.add_field(name="👤 АДМИНИСТРАЦИЯ", value=f"Роль {TICKET_ROLE}", inline=True)
    
    confirm_embed.set_footer(text="Спасибо за использование нашей системы!")
    
    await interaction.followup.send(embed=confirm_embed, ephemeral=True)

# ==================== КОМАНДЫ БОТА ====================
@bot.event
async def on_ready():
    print("=" * 60)
    print(f"🤖 БОТ: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 СЕРВЕРОВ: {len(bot.guilds)}")
    print(f"🎫 РОЛЬ ДЛЯ ПРОСМОТРА: {TICKET_ROLE}")
    print("=" * 60)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🎫 систему тикетов | Skarry"
        )
    )
    
    # Регистрируем персистентные View
    bot.add_view(MainPanelView())
    bot.add_view(UserTicketView(0, 0))
    bot.add_view(StaffTicketView(0, 0, True))
    
    print(f"✅ Бот готов! Используйте !панель для создания панели")

@bot.command(name="панель")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    """Создает красивую панель тикетов"""
    
    # Создаем категорию
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
    
    # Создаем канал панели
    panel_channel = None
    for channel in category.text_channels:
        if "панель" in channel.name.lower():
            panel_channel = channel
            break
    
    if not panel_channel:
        # Настраиваем права (только чтение + кнопки)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                add_reactions=False,
                send_tts_messages=False,
                attach_files=False,
                embed_links=False
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }
        
        # Даем права админам и роли Ticket
        ticket_role = discord.utils.get(ctx.guild.roles, name=TICKET_ROLE)
        if ticket_role:
            overwrites[ticket_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True
            )
        
        for member in ctx.guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True
                )
        
        panel_channel = await category.create_text_channel(
            name=f"{Emojis.TICKET}-панель-тикетов",
            topic="🎫 Создание тикетов | Не писать в этот канал!",
            overwrites=overwrites,
            slowmode_delay=5
        )
    
    # Очищаем канал
    try:
        await panel_channel.purge(limit=100)
    except:
        pass
    
    # Создаем красивый embed панели
    main_embed = discord.Embed(
        title=f"{Emojis.TICKET} СИСТЕМА ТИКЕТОВ",
        description="Выберите тип тикета, нажав на соответствующую кнопку ниже:",
        color=Colors.PRIMARY
    )
    
    main_embed.add_field(
        name=f"{Emojis.PROBLEM} **ПРОБЛЕМА / БАГ**",
        value="• Что-то не работает\n• Ошибки и сбои\n• Технические неполадки\n• Критические проблемы",
        inline=False
    )
    
    main_embed.add_field(
        name=f"{Emojis.IDEA} **ИДЕЯ / ПРЕДЛОЖЕНИЕ**",
        value="• Новые функции\n• Улучшения\n• Предложения\n• Оптимизации",
        inline=False
    )
    
    main_embed.add_field(
        name=f"{Emojis.YOUTUBE} **YOUTUBE ЗАПРОС**",
        value="• Темы для видео\n• Контент-идеи\n• Вопросы к видео\n• Предложения по формату",
        inline=False
    )
    
    # Разделитель
    main_embed.add_field(name="📋 **ИНФОРМАЦИЯ**", value="═"*40, inline=False)
    
    main_embed.add_field(
        name=f"{Emojis.INFO} **КАК РАБОТАЕТ:**",
        value="1. **Выберите тип** тикета\n2. **Заполните** форму\n3. **Создастся** приватный канал\n4. **Администрация** ответит там",
        inline=False
    )
    
    main_embed.add_field(
        name=f"{Emojis.WARNING} **ПРАВИЛА:**",
        value="• 1 тикет = 1 проблема\n• Описывайте ЧЕТКО и ПОДРОБНО\n• Прикрепляйте скриншоты\n• Будьте вежливы и терпеливы\n• **КД между тикетами: 10 минут**",
        inline=False
    )
    
    main_embed.add_field(
        name=f"{Emojis.STAFF} **АДМИНИСТРАЦИЯ:**",
        value=f"• Роль **{TICKET_ROLE}** видит ВСЕ тикеты\n• Администрация ответит в течение 24 часов\n• Используйте кнопки в тикете для управления",
        inline=False
    )
    
    main_embed.set_thumbnail(url="https://i.imgur.com/3tM5Z6G.png")  # Красивая иконка
    main_embed.set_footer(text="🎫 Бот создан Skarry | 🕐 Работает 24/7 на Render.com")
    
    # Создаем второй embed для YouTube гида
    youtube_embed = discord.Embed(
        title=f"{Emojis.YOUTUBE} **ВИДЕО-ГИД ПО ИСПОЛЬЗОВАНИЮ**",
        description="Не знаете как пользоваться системой? Посмотрите наше обучающее видео!",
        color=Colors.YOUTUBE,
        url="https://www.youtube.com"  # ЗАМЕНИ НА СВОЮ ССЫЛКУ!
    )
    
    youtube_embed.add_field(
        name="🎬 **ЧТО ВЫ УЗНАЕТЕ:**",
        value="• Как правильно создавать тикеты\n• Что писать в описании\n• Как общаться с поддержкой\n• Все функции системы",
        inline=False
    )
    
    youtube_embed.add_field(
        name="📱 **ДОПОЛНИТЕЛЬНО:**",
        value="• Примеры хороших тикетов\n• Частые ошибки\n• Советы по описанию проблем\n• FAQ по системе",
        inline=False
    )
    
    youtube_embed.set_image(url="https://i.imgur.com/example.jpg")  # Превью видео
    youtube_embed.set_footer(text="Нажмите на заголовок чтобы перейти к видео")
    
    # Отправляем панели
    view = MainPanelView()
    
    # Отправляем основную панель
    main_message = await panel_channel.send(embed=main_embed, view=view)
    
    # Отправляем YouTube embed
    await panel_channel.send(embed=youtube_embed)
    
    # Закрепляем сообщения
    try:
        await main_message.pin()
    except:
        pass
    
    # Включаем медленный режим и запрещаем писать
    await panel_channel.edit(slowmode_delay=30)
    
    # Удаляем все лишние сообщения
    await asyncio.sleep(2)
    try:
        async for msg in panel_channel.history(limit=50):
            if msg.id != main_message.id and not msg.embeds:
                await msg.delete()
    except:
        pass
    
    # Отправляем подтверждение
    success_embed = discord.Embed(
        title=f"{Emojis.CHECK} ПАНЕЛЬ СОЗДАНА!",
        description=f"Красивая панель тикетов создана в {panel_channel.mention}",
        color=Colors.SUCCESS
    )
    success_embed.add_field(name="🎨 Дизайн", value="Современный и понятный", inline=True)
    success_embed.add_field(name="🎯 Функции", value="3 типа тикетов + YouTube гид", inline=True)
    success_embed.add_field(name="🛡️ Права", value=f"Роль {TICKET_ROLE} видит все", inline=True)
    
    await ctx.message.delete()
    await ctx.send(embed=success_embed, delete_after=10)

@bot.event
async def on_message(message):
    # Авто-удаление сообщений в канале панели (кроме бота)
    if message.channel.name.lower() == f"{Emojis.TICKET}-панель-тикетов".lower() and not message.author.bot:
        try:
            await message.delete()
            
            # Отправляем предупреждение
            if not message.author.guild_permissions.administrator:
                try:
                    warning = discord.Embed(
                        title=f"{Emojis.WARNING} ВНИМАНИЕ!",
                        description=f"В канале {message.channel.mention} **нельзя писать сообщения**!\n\nИспользуйте **кнопки** для создания тикетов.",
                        color=Colors.WARNING
                    )
                    warning.add_field(name="📝 Что делать?", value="Нажмите на одну из кнопок выше", inline=False)
                    warning.set_footer(text="Этот канал предназначен только для кнопок")
                    await message.author.send(embed=warning)
                except:
                    pass
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
    
    embed.add_field(name=f"{Emojis.CLOCK} ЗАДЕРЖКА", value=f"`{latency}ms`", inline=True)
    embed.add_field(name=f"{Emojis.STAFF} РОЛЬ", value=TICKET_ROLE, inline=True)
    embed.add_field(name=f"{Emojis.INFO} ВЕРСИЯ", value="2.0", inline=True)
    
    embed.add_field(name=f"{Emojis.CHECK} СТАТУС", value="✅ **ОНЛАЙН**", inline=False)
    embed.add_field(name=f"{Emojis.YOUTUBE} ГИД", value="Доступен в панели тикетов", inline=True)
    embed.add_field(name="🎨 ДИЗАЙН", value="Премиум", inline=True)
    
    embed.set_footer(text="Бот создан Skarry | Работает на Render.com")
    
    await ctx.send(embed=embed)

@bot.command(name="обновить")
@commands.has_permissions(administrator=True)
async def refresh_panel(ctx):
    """Обновить панель тикетов"""
    await setup_panel(ctx)

@bot.command(name="статистика")
async def stats(ctx):
    """Статистика тикетов"""
    tickets_data = load_data(TICKETS_FILE)
    
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СТАТИСТИКА ТИКЕТОВ",
        color=Colors.PRIMARY
    )
    
    total = len(tickets_data)
    problems = len([t for t in tickets_data.values() if t.get("type") == "problem"])
    ideas = len([t for t in tickets_data.values() if t.get("type") == "idea"])
    youtube = len([t for t in tickets_data.values() if t.get("type") == "youtube"])
    
    embed.add_field(name="📊 ВСЕГО ТИКЕТОВ", value=f"**{total}**", inline=True)
    embed.add_field(name=f"{Emojis.PROBLEM} ПРОБЛЕМЫ", value=f"**{problems}**", inline=True)
    embed.add_field(name=f"{Emojis.IDEA} ИДЕИ", value=f"**{ideas}**", inline=True)
    
    if youtube > 0:
        embed.add_field(name=f"{Emojis.YOUTUBE} YOUTUBE", value=f"**{youtube}**", inline=True)
    
    # Самый старый тикет
    if tickets_data:
        oldest = min(tickets_data.values(), key=lambda x: x.get("created_at", 0))
        oldest_time = int(oldest.get("created_at", time.time()))
        embed.add_field(name="📅 САМЫЙ СТАРЫЙ", value=f"<t:{oldest_time}:R>", inline=True)
    
    embed.set_footer(text=f"Роль для просмотра: {TICKET_ROLE}")
    await ctx.send(embed=embed)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    keep_alive()
    
    if not TOKEN:
        print(f"{Emojis.CROSS} ОШИБКА: Токен не найден!")
        print(f"{Emojis.INFO} Добавьте DISCORD_TOKEN в переменные окружения Render")
        exit(1)
    
    print(f"{Emojis.TICKET} Запускаем Discord бота...")
    print(f"{Emojis.INFO} Роль для просмотра тикетов: {TICKET_ROLE}")
    print(f"{Emojis.CLOCK} КД между тикетами: {COOLDOWN_TIME//60} минут")
    
    bot.run(TOKEN)
