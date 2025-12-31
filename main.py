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
import traceback
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
TICKET_ROLE_NAME = "Ticket"
COOLDOWN_TIME = 600
AUTO_SETUP = True

COOLDOWN_FILE = "cooldowns.json"
TICKETS_FILE = "tickets.json"
CONFIG_FILE = "config.json"

def load_data(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

app = Flask('')

@app.route('/')
def home():
    return "🎫 Ticket Bot by Skarry"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

def find_ticket_role(guild):
    for role in guild.roles:
        if "ticket" in role.name.lower():
            return role
    return None

def has_ticket_role(member):
    for role in member.roles:
        if "ticket" in role.name.lower():
            return True
    return False

def is_admin(member):
    return member.guild_permissions.administrator

class Colors:
    PRIMARY = 0x5865F2
    SUCCESS = 0x57F287
    WARNING = 0xFEE75C
    DANGER = 0xED4245
    PROBLEM = 0xED4245
    IDEA = 0x57F287
    YOUTUBE = 0xFF0000
    STATUS_OPEN = 0x57F287
    STATUS_IN_REVIEW = 0xFEE75C
    STATUS_CLOSED = 0xED4245

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
    STATUS = "📊"
    EYE = "👁️"

# ==================== ФУНКЦИЯ СОЗДАНИЯ СТРУКТУРЫ ====================
async def auto_setup(guild):
    config = load_data(CONFIG_FILE)
    if str(guild.id) in config.get('initialized_guilds', []):
        return
    
    print(f"🔄 Создаю структуру для гильдии {guild.name}...")
    
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
    
    config['initialized_guilds'] = config.get('initialized_guilds', [])
    config['initialized_guilds'].append(str(guild.id))
    save_data(CONFIG_FILE, config)

# ==================== МОДАЛЬНОЕ ОКНО ДЛЯ РЕДАКТИРОВАНИЯ ====================
class EditTicketModal(Modal):
    def __init__(self, current_data, ticket_type):
        super().__init__(title=f"{Emojis.EDIT} РЕДАКТИРОВАНИЕ ЗАЯВКИ", timeout=None)
        self.ticket_type = ticket_type
        
        if ticket_type == "problem":
            title_placeholder = "Кратко опишите проблему..."
            description_placeholder = "• Что именно произошло?\n• Когда началось?\n• Как это влияет на игру?"
            description_label = "📖 ПОДРОБНОЕ ОПИСАНИЕ"
        elif ticket_type == "idea":
            title_placeholder = "Название идеи..."
            description_placeholder = "• В чем суть идеи?\n• Какую проблему решает?\n• Какие преимущества?"
            description_label = "📖 ОПИСАНИЕ ИДЕИ"
        else:  # youtube
            title_placeholder = "Название видео / коллаборации..."
            description_placeholder = "• Информация о канале\n• Игровая информация\n• Предложение по сотрудничеству"
            description_label = "📖 ПОЛНАЯ ИНФОРМАЦИЯ"
        
        self.title_input = TextInput(
            label="📝 НАЗВАНИЕ / ТЕМА",
            placeholder=title_placeholder,
            max_length=100,
            required=True,
            style=discord.TextStyle.short,
            default=current_data.get('title', '')
        )
        
        self.description = TextInput(
            label=description_label,
            placeholder=description_placeholder,
            max_length=2000,
            required=True,
            style=discord.TextStyle.paragraph,
            default=current_data.get('description', '')
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.send_message(
                f"{Emojis.CHECK} Заявка обновлена!",
                ephemeral=True,
                delete_after=3
            )
            
            # Обновляем данные в файле
            tickets_data = load_data(TICKETS_FILE)
            channel_id = str(interaction.channel.id)
            
            if channel_id in tickets_data:
                tickets_data[channel_id]['title'] = self.title_input.value
                tickets_data[channel_id]['description'] = self.description.value
                tickets_data[channel_id]['last_edited'] = time.time()
                tickets_data[channel_id]['edited_by'] = str(interaction.user.id)
                save_data(TICKETS_FILE, tickets_data)
                
                # Обновляем сообщение в канале
                channel = interaction.channel
                async for message in channel.history(limit=10):
                    if message.embeds and message.author == bot.user:
                        embed = message.embeds[0]
                        embed.title = f"{embed.title.split('|')[0].strip()} | {self.title_input.value[:50]}"
                        embed.description = f"**{self.title_input.value}**\n\n{self.description.value}"
                        
                        # Обновляем поле статуса если есть
                        for i, field in enumerate(embed.fields):
                            if field.name.startswith(f"{Emojis.STATUS}"):
                                embed.set_field_at(i, name=field.name, value=field.value, inline=True)
                                break
                        
                        await message.edit(embed=embed)
                        break
        except Exception as e:
            print(f"Ошибка при редактировании заявки: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка при обновлении заявки.",
                ephemeral=True
            )

# ==================== МОДАЛЬНОЕ ОКНО ДЛЯ YOUTUBE ====================
class YouTubeModal(Modal):
    def __init__(self):
        super().__init__(title=f"{Emojis.YOUTUBE} ЗАПРОС НА YOUTUBE", timeout=None)
        
        self.name_input = TextInput(
            label="👤 ВАШЕ ИМЯ",
            placeholder="Пример: Алексей",
            max_length=50,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.age_input = TextInput(
            label="🎂 ВАШ ВОЗРАСТ",
            placeholder="Пример: 25",
            max_length=3,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.channel_link = TextInput(
            label="🔗 ССЫЛКА НА КАНАЛ",
            placeholder="https://www.youtube.com/@вашканал",
            max_length=100,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.nickname = TextInput(
            label="🎮 ОСНОВНОЙ НИК В ИГРЕ",
            placeholder="Пример: Skarry_Pro",
            max_length=50,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.video_type = TextInput(
            label="🎬 КАКОЙ ВИД ВИДЕО ВЫ СНИМАЕТЕ?",
            placeholder="Пример: Обзоры игр, Геймплей, Гайды, Разборы...",
            max_length=200,
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.subscribers = TextInput(
            label="👥 КОЛИЧЕСТВО ПОДПИСЧИКОВ",
            placeholder="Пример: 10,000 или 1.5K",
            max_length=20,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.telegram = TextInput(
            label="📱 ТЕЛЕГРАМ ДЛЯ СВЯЗИ",
            placeholder="Пример: @username или +79991234567",
            max_length=50,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.timezone = TextInput(
            label="⏰ ЧАСОВОЙ ПОЯС",
            placeholder="Пример: МСК (UTC+3)",
            max_length=20,
            required=True,
            style=discord.TextStyle.short
        )
        
        self.additional_info = TextInput(
            label="📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ",
            placeholder="• Ваши предложения по сотрудничеству\n• Идеи для видео\n• Предпочтительное время для записи",
            max_length=1000,
            required=False,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.name_input)
        self.add_item(self.age_input)
        self.add_item(self.channel_link)
        self.add_item(self.nickname)
        self.add_item(self.video_type)
        self.add_item(self.subscribers)
        self.add_item(self.telegram)
        self.add_item(self.timezone)
        self.add_item(self.additional_info)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
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
            
            await interaction.response.send_message(
                f"{Emojis.YOUTUBE} Создаю YouTube запрос...",
                ephemeral=True
            )
            
            # Формируем описание
            full_description = f"""
**👤 ОБЩАЯ ИНФОРМАЦИЯ:**
> **Имя:** {self.name_input.value}
> **Возраст:** {self.age_input.value}
> **Часовой пояс:** {self.timezone.value}

**📺 YOUTUBE КАНАЛ:**
> **Ссылка:** {self.channel_link.value}
> **Подписчики:** {self.subscribers.value}
> **Тематика:** {self.video_type.value}

**🎮 ИГРОВАЯ ИНФОРМАЦИЯ:**
> **Основной ник:** {self.nickname.value}

**📱 КОНТАКТНАЯ ИНФОРМАЦИЯ:**
> **Telegram:** {self.telegram.value}
"""
            
            if self.additional_info.value.strip():
                full_description += f"""

**📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:**
{self.additional_info.value}
"""
            
            full_description += f"\n**🎫 Discord пользователь:** {interaction.user.mention}"
            
            # Сохраняем данные для возможного редактирования
            youtube_data = {
                'name': self.name_input.value,
                'age': self.age_input.value,
                'channel_link': self.channel_link.value,
                'nickname': self.nickname.value,
                'video_type': self.video_type.value,
                'subscribers': self.subscribers.value,
                'telegram': self.telegram.value,
                'timezone': self.timezone.value,
                'additional_info': self.additional_info.value
            }
            
            title = f"YouTube запрос от {self.name_input.value}"
            await create_ticket_channel(interaction, "youtube", title, full_description, youtube_data)
            
        except Exception as e:
            print(f"Ошибка в YouTube модальном окне: {e}")
            traceback.print_exc()
            
            try:
                await interaction.response.send_message(
                    f"{Emojis.CROSS} Произошла ошибка при создании тикета. Попробуйте еще раз.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        f"{Emojis.CROSS} Произошла ошибка при создании тикета. Попробуйте еще раз.",
                        ephemeral=True
                    )
                except:
                    pass

# ==================== МОДАЛЬНОЕ ОКНО ДЛЯ ПРОБЛЕМЫ И ИДЕИ ====================
class TicketModal(Modal):
    def __init__(self, ticket_type):
        if ticket_type == "problem":
            title_text = f"{Emojis.PROBLEM} СОЗДАНИЕ ПРОБЛЕМЫ"
            color = Colors.PROBLEM
            title_placeholder = "Кратко опишите проблему..."
            description_placeholder = "• Что именно произошло?\n• Когда началось?\n• Как это влияет на игру?\n• Прикрепите скриншоты если есть"
            description_label = "📖 ПОДРОБНОЕ ОПИСАНИЕ"
        else:  # idea
            title_text = f"{Emojis.IDEA} СОЗДАНИЕ ИДЕИ"
            color = Colors.IDEA
            title_placeholder = "Название идеи..."
            description_placeholder = "• В чем суть идеи?\n• Какую проблему решает?\n• Какие преимущества?\n• Возможная реализация"
            description_label = "📖 ОПИСАНИЕ ИДЕИ"
        
        super().__init__(title=title_text, timeout=None)
        
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
            
            await interaction.response.send_message(
                f"{Emojis.CLOCK} Создаю тикет...",
                ephemeral=True,
                delete_after=2
            )
            
            await create_ticket_channel(interaction, self.ticket_type, self.title_input.value, self.description.value)
            
        except Exception as e:
            print(f"Ошибка в модальном окне: {e}")
            traceback.print_exc()
            
            try:
                await interaction.response.send_message(
                    f"{Emojis.CROSS} Произошла ошибка при создании тикета. Попробуйте еще раз.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        f"{Emojis.CROSS} Произошла ошибка при создании тикета. Попробуйте еще раз.",
                        ephemeral=True
                    )
                except:
                    pass

# ==================== ВЫБОР УЧАСТНИКА ДЛЯ ДОБАВЛЕНИЯ ====================
class AddUserModal(Modal):
    def __init__(self, channel):
        super().__init__(title=f"{Emojis.ADD_USER} ДОБАВЛЕНИЕ УЧАСТНИКА", timeout=None)
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
            
            if user_text.startswith('<@') and user_text.endswith('>'):
                try:
                    user_id = int(user_text[2:-1].replace('!', ''))
                    user = interaction.guild.get_member(user_id)
                except:
                    pass
            
            if not user and user_text.isdigit():
                user = interaction.guild.get_member(int(user_text))
            
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

# ==================== ВЫБОР СТАТУСА ====================
class StatusSelect(Select):
    def __init__(self, channel_id):
        options = [
            discord.SelectOption(
                label="РАССМАТРИВАЕТСЯ",
                value="review",
                emoji="👁️",
                description="Заявка находится на рассмотрении"
            ),
            discord.SelectOption(
                label="ОТКРЫТ",
                value="open",
                emoji="✅",
                description="Заявка открыта и обрабатывается"
            ),
            discord.SelectOption(
                label="ЗАКРЫТ",
                value="closed",
                emoji="🔒",
                description="Заявка закрыта"
            )
        ]
        
        super().__init__(
            placeholder="Выберите статус заявки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="status_select"
        )
        self.channel_id = channel_id
    
    async def callback(self, interaction: discord.Interaction):
        if not (has_ticket_role(interaction.user) or is_admin(interaction.user)):
            embed = discord.Embed(
                title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                description="Только администрация может менять статус",
                color=Colors.DANGER
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        status_emoji = "👁️" if self.values[0] == "review" else "✅" if self.values[0] == "open" else "🔒"
        status_text = "РАССМАТРИВАЕТСЯ" if self.values[0] == "review" else "ОТКРЫТ" if self.values[0] == "open" else "ЗАКРЫТ"
        status_color = Colors.STATUS_IN_REVIEW if self.values[0] == "review" else Colors.STATUS_OPEN if self.values[0] == "open" else Colors.STATUS_CLOSED
        
        # Обновляем статус в базе данных
        tickets_data = load_data(TICKETS_FILE)
        channel_id_str = str(self.channel_id)
        
        if channel_id_str in tickets_data:
            tickets_data[channel_id_str]['status'] = self.values[0]
            tickets_data[channel_id_str]['status_changed'] = time.time()
            tickets_data[channel_id_str]['status_changed_by'] = str(interaction.user.id)
            save_data(TICKETS_FILE, tickets_data)
        
        # Обновляем сообщение в канале
        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            async for message in channel.history(limit=10):
                if message.embeds and message.author == bot.user:
                    embed = message.embeds[0]
                    
                    # Обновляем или добавляем поле статуса
                    status_field_exists = False
                    for i, field in enumerate(embed.fields):
                        if field.name.startswith(f"{Emojis.STATUS}"):
                            embed.set_field_at(i, 
                                name=f"{Emojis.STATUS} СТАТУС",
                                value=f"{status_emoji} **{status_text}**",
                                inline=True
                            )
                            status_field_exists = True
                            break
                    
                    if not status_field_exists:
                        embed.add_field(
                            name=f"{Emojis.STATUS} СТАТУС",
                            value=f"{status_emoji} **{status_text}**",
                            inline=True
                        )
                    
                    # Изменяем цвет embed в зависимости от статуса
                    if self.values[0] == "closed":
                        embed.color = Colors.STATUS_CLOSED
                    elif self.values[0] == "open":
                        embed.color = Colors.STATUS_OPEN
                    else:
                        embed.color = Colors.STATUS_IN_REVIEW
                    
                    await message.edit(embed=embed)
                    
                    # Отправляем уведомление
                    embed_notify = discord.Embed(
                        title=f"{Emojis.STATUS} СТАТУС ИЗМЕНЕН",
                        description=f"Статус заявки изменен на **{status_text}**",
                        color=status_color,
                        timestamp=datetime.datetime.now()
                    )
                    embed_notify.add_field(name="👤 Изменил", value=interaction.user.mention, inline=True)
                    await channel.send(embed=embed_notify)
                    break
        
        await interaction.response.send_message(
            f"{Emojis.CHECK} Статус изменен на **{status_text}**",
            ephemeral=True
        )

class StatusSelectView(View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.add_item(StatusSelect(channel_id))

# ==================== КНОПКИ ДЛЯ АВТОРА ТИКЕТА ====================
class UserTicketView(View):
    def __init__(self, channel_id, creator_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
    
    @discord.ui.button(label=f"{Emojis.EDIT} РЕДАКТИРОВАТЬ", style=discord.ButtonStyle.green, custom_id="user_edit", row=0)
    async def edit_ticket(self, interaction: discord.Interaction, button: Button):
        try:
            if interaction.user.id != self.creator_id:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только автор заявки может редактировать её",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Загружаем текущие данные
            tickets_data = load_data(TICKETS_FILE)
            channel_id_str = str(interaction.channel.id)
            
            if channel_id_str in tickets_data:
                ticket_data = tickets_data[channel_id_str]
                
                # Определяем тип тикета
                ticket_type = ticket_data.get('type', 'problem')
                
                # Создаем модальное окно с текущими данными
                current_data = {
                    'title': ticket_data.get('title', ''),
                    'description': ticket_data.get('description', '')
                }
                
                modal = EditTicketModal(current_data, ticket_type)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(
                    f"{Emojis.CROSS} Данные заявки не найдены.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Ошибка в кнопке редактирования: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка. Попробуйте снова.",
                ephemeral=True
            )
    
    @discord.ui.button(label=f"{Emojis.ADD_USER} ДОБАВИТЬ", style=discord.ButtonStyle.blurple, custom_id="user_add", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        try:
            if interaction.user.id != self.creator_id:
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только автор заявки может добавлять участников",
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
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка. Попробуйте снова.",
                ephemeral=True
            )

# ==================== КНОПКИ ДЛЯ АДМИНИСТРАЦИИ ====================
class StaffTicketView(View):
    def __init__(self, channel_id, creator_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.creator_id = creator_id
    
    @discord.ui.button(label=f"{Emojis.STATUS} СМЕНИТЬ СТАТУС", style=discord.ButtonStyle.blurple, custom_id="staff_status", row=0)
    async def change_status(self, interaction: discord.Interaction, button: Button):
        try:
            if not (has_ticket_role(interaction.user) or is_admin(interaction.user)):
                embed = discord.Embed(
                    title=f"{Emojis.CROSS} НЕТ ДОСТУПА",
                    description="Только администрация может менять статус",
                    color=Colors.DANGER
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            view = StatusSelectView(self.channel_id)
            await interaction.response.send_message(
                f"{Emojis.STATUS} Выберите новый статус заявки:",
                view=view,
                ephemeral=True
            )
        except Exception as e:
            print(f"Ошибка в кнопке смены статуса: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка. Попробуйте снова.",
                ephemeral=True
            )
    
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
                embed.add_field(name="💡 Рекомендация", value="Используйте кнопку 'РЕДАКТИРОВАТЬ' для добавления информации", inline=True)
                
                await interaction.response.send_message(f"{creator.mention}", embed=embed)
        except Exception as e:
            print(f"Ошибка в кнопке запроса: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка. Попробуйте снова.",
                ephemeral=True
            )
    
    @discord.ui.button(label=f"{Emojis.LOCK} ЗАКРЫТЬ", style=discord.ButtonStyle.red, custom_id="close_ticket", row=1)
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
            
            # Обновляем статус на "ЗАКРЫТ"
            tickets_data = load_data(TICKETS_FILE)
            if str(channel.id) in tickets_data:
                tickets_data[str(channel.id)]['status'] = 'closed'
                tickets_data[str(channel.id)]['status_changed'] = time.time()
                tickets_data[str(channel.id)]['status_changed_by'] = str(interaction.user.id)
                save_data(TICKETS_FILE, tickets_data)
            
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
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка закрытия тикета.",
                ephemeral=True
            )

# ==================== ФУНКЦИЯ СОЗДАНИЯ ТИКЕТА ====================
async def create_ticket_channel(interaction, ticket_type, title, description, additional_data=None):
    """Создает канал для тикета"""
    
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
            category = interaction.guild.categories[0]
    
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
        color_name = "ЗАПРОС НА YOUTUBE"
        color = Colors.YOUTUBE
    
    channel_name = f"{prefix}-{user_name}-{clean_title}".lower()[:100]
    
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
    
    ticket_role = find_ticket_role(interaction.guild)
    if ticket_role:
        overwrites[ticket_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            attach_files=True,
            embed_links=True
        )
    
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
            name=channel_name,
            overwrites=overwrites,
            topic=f"{prefix} | {title[:50]}"
        )
    except Exception as e:
        print(f"Ошибка создания канала: {e}")
        try:
            embed = discord.Embed(
                title=f"{Emojis.CROSS} ОШИБКА",
                description="Не удалось создать тикет. Попробуйте позже.",
                color=Colors.DANGER
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            pass
        return
    
    # Создаем основное сообщение
    embed = discord.Embed(
        title=f"{prefix} {color_name} | {title}",
        description=description,
        color=Colors.STATUS_IN_REVIEW,  # Начальный цвет - рассмотрение
        timestamp=datetime.datetime.now()
    )
    
    embed.add_field(name=f"{Emojis.CLOCK} СОЗДАН", value=f"<t:{int(time.time())}:R>", inline=True)
    embed.add_field(name=f"{Emojis.STAFF} АВТОР", value=interaction.user.mention, inline=True)
    embed.add_field(name=f"{Emojis.STATUS} СТАТУС", value=f"{Emojis.EYE} **РАССМАТРИВАЕТСЯ**", inline=True)
    
    embed.set_footer(text=f"ID: {ticket_channel.id} | Для редактирования нажмите 'РЕДАКТИРОВАТЬ'")
    
    # Создаем кнопки
    staff_view = StaffTicketView(ticket_channel.id, interaction.user.id)
    user_view = UserTicketView(ticket_channel.id, interaction.user.id)
    
    # Отправляем сообщения
    mention_text = f"{interaction.user.mention}"
    if ticket_role:
        mention_text += f" {ticket_role.mention}"
    
    try:
        await ticket_channel.send(content=mention_text, embed=embed, view=staff_view)
        
        user_embed = discord.Embed(
            description=f"{Emojis.INFO} **Ваши кнопки для управления заявкой:**",
            color=Colors.PRIMARY
        )
        await ticket_channel.send(embed=user_embed, view=user_view)
    except Exception as e:
        print(f"Ошибка отправки сообщений в тикет: {e}")
    
    # Сохраняем в базу
    tickets_data = load_data(TICKETS_FILE)
    ticket_data = {
        "creator": interaction.user.id,
        "type": ticket_type,
        "title": title,
        "description": description,
        "created_at": time.time(),
        "status": "review",
        "channel_name": channel_name
    }
    
    # Добавляем дополнительные данные для YouTube
    if additional_data and ticket_type == "youtube":
        ticket_data.update(additional_data)
    
    tickets_data[str(ticket_channel.id)] = ticket_data
    save_data(TICKETS_FILE, tickets_data)
    
    # Устанавливаем КД
    if not has_ticket_role(interaction.user):
        cooldowns = load_data(COOLDOWN_FILE)
        cooldowns[str(interaction.user.id)] = time.time()
        save_data(COOLDOWN_FILE, cooldowns)
    
    # Отправляем подтверждение
    try:
        if ticket_type == "youtube":
            confirm_title = f"{Emojis.CHECK} ЗАПРОС НА YOUTUBE СОЗДАН"
            confirm_desc = f"Ваш запрос создан: {ticket_channel.mention}"
        else:
            confirm_title = f"{Emojis.CHECK} ТИКЕТ СОЗДАН"
            confirm_desc = f"Ваш тикет создан: {ticket_channel.mention}"
        
        confirm_embed = discord.Embed(
            title=confirm_title,
            description=confirm_desc,
            color=color
        )
        
        confirm_embed.add_field(
            name=f"{Emojis.INFO} ЧТО ДАЛЬШЕ?",
            value="1. Ожидайте ответа администрации\n2. Используйте кнопки в заявке\n3. Для обновления информации нажмите 'РЕДАКТИРОВАТЬ'\n4. Не закрывайте канал",
            inline=False
        )
        
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)
    except Exception as e:
        print(f"Ошибка отправки подтверждения: {e}")

# ==================== КНОПКИ ГЛАВНОЙ ПАНЕЛИ ====================
class MainPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label=f"{Emojis.PROBLEM} ПРОБЛЕМА", style=discord.ButtonStyle.red, custom_id="ticket_problem", row=0)
    async def problem_button(self, interaction: discord.Interaction, button: Button):
        try:
            print(f"Нажата кнопка ПРОБЛЕМА пользователем {interaction.user}")
            modal = TicketModal("problem")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в кнопке проблемы: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка открытия формы. Попробуйте снова.",
                ephemeral=True
            )
    
    @discord.ui.button(label=f"{Emojis.IDEA} ИДЕЯ", style=discord.ButtonStyle.green, custom_id="ticket_idea", row=0)
    async def idea_button(self, interaction: discord.Interaction, button: Button):
        try:
            print(f"Нажата кнопка ИДЕЯ пользователем {interaction.user}")
            modal = TicketModal("idea")
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в кнопке идеи: {e}")
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка открытия формы. Попробуйте снова.",
                ephemeral=True
            )
    
    @discord.ui.button(label=f"{Emojis.YOUTUBE} ЗАПРОС НА YOUTUBE", style=discord.ButtonStyle.red, custom_id="ticket_youtube", row=1)
    async def youtube_button(self, interaction: discord.Interaction, button: Button):
        try:
            print(f"Нажата кнопка ЗАПРОС НА YOUTUBE пользователем {interaction.user}")
            modal = YouTubeModal()
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в кнопке YouTube: {e}")
            traceback.print_exc()
            await interaction.response.send_message(
                f"{Emojis.CROSS} Ошибка открытия формы YouTube. Попробуйте снова.",
                ephemeral=True
            )

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
            name="🎫 систему заявок"
        )
    )
    
    if AUTO_SETUP:
        for guild in bot.guilds:
            await auto_setup(guild)
    
    # Регистрируем View
    try:
        bot.add_view(MainPanelView())
        bot.add_view(UserTicketView(0, 0))
        bot.add_view(StaffTicketView(0, 0))
        print("✅ View зарегистрированы")
    except Exception as e:
        print(f"Ошибка регистрации View: {e}")
    
    print("✅ Бот готов к работе")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get('custom_id', 'unknown')
            print(f"🔘 Кнопка нажата: {custom_id} пользователем {interaction.user.name}")
    except Exception as e:
        print(f"Ошибка в обработчике взаимодействия: {e}")
    
    await bot.process_application_commands(interaction)

@bot.command(name="панель")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    """Создает панель заявок"""
    
    category = None
    for cat in ctx.guild.categories:
        if "тикет" in cat.name.lower():
            category = cat
            break
    
    if not category:
        category = await ctx.guild.create_category(
            name=f"{Emojis.TICKET} ЗАЯВКИ",
            position=0
        )
    
    panel_channel = None
    for channel in category.text_channels:
        if "панель" in channel.name.lower():
            panel_channel = channel
            break
    
    if not panel_channel:
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
        
        for member in ctx.guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )
        
        panel_channel = await category.create_text_channel(
            name=f"{Emojis.TICKET}-панель",
            topic="Создание заявок - используйте кнопки ниже",
            overwrites=overwrites
        )
    
    try:
        await panel_channel.purge(limit=100)
    except:
        pass
    
    # Создаем красивую панель с обновленным описанием
    embed = discord.Embed(
        title="🎫 **СИСТЕМА ЗАЯВОК**",
        description="Выберите тип заявки, нажав на соответствующую кнопку:",
        color=Colors.PRIMARY
    )
    
    embed.add_field(
        name="🚨 **ПРОБЛЕМА / БАГ**",
        value="• Технические неполадки\n• Ошибки в игре\n• Сбои и лаги\n• Критические проблемы",
        inline=False
    )
    
    embed.add_field(
        name="💡 **ИДЕЯ / ПРЕДЛОЖЕНИЕ**",
        value="• Новые функции\n• Улучшения геймплея\n• Предложения по балансу\n• Креативные идеи",
        inline=False
    )
    
    embed.add_field(
        name="📺 **ЗАПРОС НА YOUTUBE**",
        value="""• **Для YouTube авторов и блогеров**
• **Обязательные поля:** Имя, возраст, ссылка на канал
• **Требуется:** Количество подписчиков, Telegram
• **Цель:** Сотрудничество, обзоры, коллаборации""",
        inline=False
    )
    
    embed.add_field(name="📋 **ИНФОРМАЦИЯ О СТАТУСАХ**", value="─" * 30, inline=False)
    
    embed.add_field(
        name="👁️ **РАССМАТРИВАЕТСЯ**",
        value="Заявка получена и находится на рассмотрении",
        inline=True
    )
    
    embed.add_field(
        name="✅ **ОТКРЫТ**",
        value="Заявка принята в работу и обрабатывается",
        inline=True
    )
    
    embed.add_field(
        name="🔒 **ЗАКРЫТ**",
        value="Заявка завершена или отклонена",
        inline=True
    )
    
    embed.add_field(
        name="✏️ **ФУНКЦИИ ДЛЯ АВТОРА:**",
        value="• **РЕДАКТИРОВАТЬ** - изменить информацию в заявке\n• **ДОБАВИТЬ** - добавить участника в обсуждение",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ **ФУНКЦИИ ДЛЯ АДМИНИСТРАЦИИ:**",
        value="• **СМЕНИТЬ СТАТУС** - изменить статус заявки\n• **ЗАПРОСИТЬ** - запросить доп. информацию\n• **ЗАКРЫТЬ** - завершить заявку",
        inline=False
    )
    
    embed.set_footer(text="🎫 Бот создан Skarry | Система статусов и редактирования")
    
    # Отправляем панель
    view = MainPanelView()
    message = await panel_channel.send(embed=embed, view=view)
    
    try:
        await message.pin()
    except:
        pass
    
    await panel_channel.edit(slowmode_delay=30)
    
    success_embed = discord.Embed(
        title=f"{Emojis.CHECK} ПАНЕЛЬ СОЗДАНА",
        description=f"Панель создана в {panel_channel.mention}",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=success_embed, delete_after=10)
    await ctx.message.delete()

@bot.event
async def on_message(message):
    if message.channel.name.lower().endswith("-панель") and not message.author.bot:
        try:
            await message.delete()
        except:
            pass
    
    await bot.process_commands(message)

@bot.command(name="пинг")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СТАТУС СИСТЕМЫ",
        color=Colors.PRIMARY
    )
    
    embed.add_field(name="📶 Задержка", value=f"{latency}ms", inline=True)
    embed.add_field(name="✅ Статус", value="Работает", inline=True)
    embed.add_field(name="🎫 Заявок", value=str(len(load_data(TICKETS_FILE))), inline=True)
    
    embed.set_footer(text="Бот создан Skarry")
    await ctx.send(embed=embed)

@bot.command(name="статистика")
async def stats(ctx):
    tickets_data = load_data(TICKETS_FILE)
    
    embed = discord.Embed(
        title=f"{Emojis.TICKET} СТАТИСТИКА ЗАЯВОК",
        color=Colors.PRIMARY
    )
    
    total = len(tickets_data)
    problems = len([t for t in tickets_data.values() if t.get("type") == "problem"])
    ideas = len([t for t in tickets_data.values() if t.get("type") == "idea"])
    youtube = len([t for t in tickets_data.values() if t.get("type") == "youtube"])
    
    review = len([t for t in tickets_data.values() if t.get("status") == "review"])
    open_tickets = len([t for t in tickets_data.values() if t.get("status") == "open"])
    closed = len([t for t in tickets_data.values() if t.get("status") == "closed"])
    
    embed.add_field(name="📊 Всего заявок", value=f"**{total}**", inline=True)
    embed.add_field(name=f"{Emojis.PROBLEM} Проблем", value=f"**{problems}**", inline=True)
    embed.add_field(name=f"{Emojis.IDEA} Идей", value=f"**{ideas}**", inline=True)
    
    if youtube > 0:
        embed.add_field(name=f"{Emojis.YOUTUBE} YouTube", value=f"**{youtube}**", inline=True)
    
    embed.add_field(name=f"{Emojis.EYE} На рассмотрении", value=f"**{review}**", inline=True)
    embed.add_field(name=f"{Emojis.CHECK} Открыто", value=f"**{open_tickets}**", inline=True)
    embed.add_field(name=f"{Emojis.LOCK} Закрыто", value=f"**{closed}**", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="сбросить")
@commands.has_permissions(administrator=True)
async def reset_cd(ctx, user: discord.Member = None):
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

@bot.command(name="очистить")
@commands.has_permissions(administrator=True)
async def cleanup(ctx):
    tickets_data = load_data(TICKETS_FILE)
    channels_to_remove = []
    
    for channel_id, data in list(tickets_data.items()):
        channel = ctx.guild.get_channel(int(channel_id))
        if not channel:
            channels_to_remove.append(channel_id)
    
    for channel_id in channels_to_remove:
        del tickets_data[channel_id]
    
    save_data(TICKETS_FILE, tickets_data)
    
    embed = discord.Embed(
        title=f"{Emojis.CHECK} БАЗА ОЧИЩЕНА",
        description=f"Удалено {len(channels_to_remove)} несуществующих заявок",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name="тест")
async def test_youtube(ctx):
    view = MainPanelView()
    await ctx.send("Тест кнопки YouTube:", view=view)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Запуск Discord Ticket Bot")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден!")
        print("ℹ️  Проверьте переменную окружения DISCORD_TOKEN")
        print("ℹ️  Если используете .env файл, убедитесь что он создан")
        exit(1)
    
    keep_alive()
    print("✅ Flask сервер запущен")
    
    print(f"🎫 Поиск роли: {TICKET_ROLE_NAME}")
    print(f"⏰ Кулдаун: {COOLDOWN_TIME//60} минут")
    print(f"🤖 Автонастройка: {'ВКЛ' if AUTO_SETUP else 'ВЫКЛ'}")
    print("=" * 50)
    
    try:
        print("🔗 Подключение к Discord...")
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен бота!")
        print("ℹ️  Проверьте правильность токена в настройках бота Discord")
    except discord.PrivilegedIntentsRequired:
        print("❌ ОШИБКА: Не включены привилегированные интенты!")
        print("ℹ️  Включите 'Message Content Intent' на портале разработчика Discord")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        traceback.print_exc()
