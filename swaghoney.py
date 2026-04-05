import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import io
import os
import itertools
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION DES IDS ---
TOKEN = os.getenv('DISCORD_TOKEN') 

PANEL_CHANNEL_ID = 1470112371115556865
TICKET_CATEGORY_ID = 1470396846970114175
STAFF_ROLE_ID = 1470093020132147230
LOG_CHANNEL_ID = 1490353930138419400
VOUCH_CHANNEL_ID = 1470425558075572256

VERIFIED_ROLE_ID = 1490386183094669482 
RULES_IMAGE_URL = "https://media.discordapp.net/attachments/1459700315380125717/1459711191369781279/IMG_7356.jpg"

VERIFY_EMOJI_ANIMATED = "<a:vamp:1490384484112138353>" 
VERIFY_EMOJI_ID = 1490384484112138353 

# Informations de paiement & Esthétique
PAYPAL_INFO = "paypal.me/toncompte"
LTC_ADDRESS = "LTC_ADDRESS_HERE"
CASHAPP_TAG = "$YourCashAppTag"
REVOLUT_TAG = "@YourRevolutTag"

TOS_TEXT = "✧ All sales are final. No refunds once goods are delivered.\n✧ We are not responsible for any game-side restrictions or bans.\n✧ Charging back will result in an immediate blacklist from our services."
THUMBNAIL_URL = "" # URL de ton logo S
BANNER_URL = "" # URL d'une grande image horizontale pour habiller le bas de tes panels
EMBED_COLOR = 0x2b2d31 
# ------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- STATUT ANIMÉ (ROTATING PRESENCE) ---
status_cycle = itertools.cycle(["Support Center", "Premium Services", "150+ Happy Customers"])

@tasks.loop(seconds=15)
async def change_status():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=next(status_cycle)))

# --- SYSTÈME DE RÉACTION (VÉRIFICATION) ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    if payload.emoji.id == VERIFY_EMOJI_ID:
        guild = bot.get_guild(payload.guild_id)
        if not guild: return
        
        role = guild.get_role(VERIFIED_ROLE_ID)
        member = guild.get_member(payload.user_id)
        
        if role and member:
            try:
                await member.add_roles(role)
                embed_confirm = discord.Embed(
                    description=f"✧ Access granted to **{guild.name}**. Welcome aboard!",
                    color=EMBED_COLOR
                )
                try:
                    await member.send(embed=embed_confirm)
                except:
                    pass
            except Exception as e:
                print(f"Erreur Role: {e}")

# --- FAQ INTERACTIVE ---
class FAQSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Payment Methods", description="How can I pay?", emoji="💳"),
            discord.SelectOption(label="Delivery Time", description="When will I get my items?", emoji="⏳"),
            discord.SelectOption(label="Refund Policy", description="Can I get a refund?", emoji="🛑")
        ]
        super().__init__(placeholder="Select a question...", custom_id="faq_select", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        answers = {
            "Payment Methods": f"✧ We accept PayPal (`{PAYPAL_INFO}`), Revolut (`{REVOLUT_TAG}`), CashApp and Crypto (LTC).",
            "Delivery Time": "✧ Delivery is usually instant once payment is confirmed by our staff.",
            "Refund Policy": "✧ As stated in our TOS, all sales are final. No refunds once delivered."
        }
        await interaction.response.send_message(answers[self.values[0]], ephemeral=True)

class FAQView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FAQSelect())

# --- TICKET CONTROLS (AVEC AUTO-VOUCH & TRANSCRIPT) ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.staff_notified = False 
        
    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("✧ Access denied. Staff authorization required.", ephemeral=True)
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✧ {interaction.user.mention} is now assigned to this request.")

    @discord.ui.button(label="Notify Staff", style=discord.ButtonStyle.primary, custom_id="notify_staff_btn")
    async def notify_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.staff_notified:
            return await interaction.response.send_message("✧ Staff has already been alerted. Please wait.", ephemeral=True)
        self.staff_notified = True
        await interaction.response.send_message(f"✧ Alerting staff representatives... <@&{STAFF_ROLE_ID}>")
        await asyncio.sleep(900)
        self.staff_notified = False

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="transcript_ticket_btn")
    async def transcript_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        transcript_content = f"--- Live Transcript ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time_formatted = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time_formatted}] {msg.author.name}: {msg.content}\n"
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"transcript_{interaction.channel.name}.txt")
        await interaction.followup.send(content="✧ Live transcript generated.", file=file)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # 1. Envoi du DM de relance (Auto-Vouch) au client
        try:
            creator_id = int(interaction.channel.topic) # On récupère l'ID caché dans le topic
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="Thank you for choosing SWAGSALES!",
                    description="✧ We hope your transaction was smooth. Please consider leaving a review in our server by typing `/vouch`.\n\n*Have a great day!*",
                    color=EMBED_COLOR
                )
                await creator.send(embed=dm_embed)
        except:
            pass # Si le DM est bloqué, on continue
        
        # 2. Transcript envoyé dans les logs
        transcript_content = f"--- Final Transcript for {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time_formatted = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time_formatted}] {msg.author.name}: {msg.content}\n"
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"archive-{interaction.channel.name}.txt")
        
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="Archived Record", description=f"**Reference:** {interaction.channel.name}\n**Authorized by:** {interaction.user.mention}", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
            log_embed.set_footer(text="swagsales • secure archive")
            await log_channel.send(embed=log_embed, file=file)
            
        await interaction.followup.send("✧ Archive secured. Commencing closure sequence...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- TICKET MODAL (FORMULAIRES DYNAMIQUES) ---
class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"{ticket_type} Request")
        self.ticket_type = ticket_type

        if ticket_type == "Buying":
            self.add_item(discord.ui.TextInput(label="Preferred payment method", placeholder="e.g. PayPal, CashApp, Revolut", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Items", placeholder="What items are you buying?", style=discord.TextStyle.paragraph, required=True))
            self.add_item(discord.ui.TextInput(label="Additional Notes", placeholder="Any other details...", style=discord.TextStyle.paragraph, required=False))
        elif ticket_type == "Selling":
            self.add_item(discord.ui.TextInput(label="Preferred receiving method", placeholder="e.g. PayPal, Crypto", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Items", placeholder="What items are you selling?", style=discord.TextStyle.paragraph, required=True))
            self.add_item(discord.ui.TextInput(label="Additional Notes", placeholder="Any other details...", style=discord.TextStyle.paragraph, required=False))
        elif ticket_type in ["Business", "Questions"]:
            self.add_item(discord.ui.TextInput(label="Inquiry type", placeholder="e.g. General, Partnership", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Details", placeholder="Describe your request...", style=discord.TextStyle.paragraph, required=True))

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        staff_role = guild.get_role(STAFF_ROLE_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        channel_name = f"{self.ticket_type.lower()}-{interaction.user.name}"
        # On sauvegarde l'ID du créateur dans le "topic" du salon pour l'Auto-Vouch plus tard
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=str(interaction.user.id))
        
        embed = discord.Embed(description=f"Welcome {interaction.user.mention}. A representative will be with you shortly.\n───────────────", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"S W A G S A L E S  |  {self.ticket_type.upper()}")
        if THUMBNAIL_URL: embed.set_thumbnail(url=THUMBNAIL_URL)
        
        for item in self.children:
            answer = item.value if item.value else "*None provided*"
            embed.add_field(name=f"✧ {item.label}", value=f"> {answer}\n", inline=False)
            
        tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
        embed.add_field(name="\u200b", value=f"───────────────\n**✧ Terms of Service**\n{tos_formatted}", inline=False)
        embed.set_footer(text="swagsales © 2026 • Secure Transaction Desk")
        
        await ticket_channel.send(content=f"{interaction.user.mention} | <@&{STAFF_ROLE_ID}>", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✧ Request established: {ticket_channel.mention}", ephemeral=True)

# --- SLASH COMMANDS ---
@bot.tree.command(name="setup_verify", description="Post rules and verification reaction")
@app_commands.default_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    embed_image = discord.Embed(color=EMBED_COLOR)
    embed_image.set_image(url=RULES_IMAGE_URL)
    await interaction.channel.send(embed=embed_image)
    
    desc = f"✧ **Rules**\n\n╰ no nsfw, gore, self harm\n╰ no harassing or being weird\n╰ no advertising\n╰ no scamming, doxxing\n╰ be respectful\n\n{VERIFY_EMOJI_ANIMATED} **react below to gain access**"
    embed_rules = discord.Embed(description=desc, color=EMBED_COLOR)
    msg_rules = await interaction.channel.send(embed=embed_rules)
    
    emoji = bot.get_emoji(VERIFY_EMOJI_ID)
    await msg_rules.add_reaction(emoji or "✅")
    await interaction.followup.send("✧ Verification system established.", ephemeral=True)

@bot.tree.command(name="setup_panel", description="Generate support panel")
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
    desc = (f"-# Select a category.\n✧ **Buying**\n*Buy goods.*\n\n✧ **Selling**\n*Sell goods.*\n\n✧ **Business**\n*Partnerships.*\n\n✧ **Questions**\n*Support.*\n\n───────────────\n**✧ Terms of Service**\n{tos_formatted}")
    embed = discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
    embed.set_author(name="S W A G S A L E S  |  Support Center")
    embed.set_footer(text="swagsales © 2026 • Premium Services")
    if BANNER_URL: embed.set_image(url=BANNER_URL)
    
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✧ Support panel established.", ephemeral=True)

@bot.tree.command(name="setup_faq", description="Generate Interactive FAQ panel")
@app_commands.default_permissions(administrator=True)
async def setup_faq(interaction: discord.Interaction):
    embed = discord.Embed(description="✧ Have a question? Check our interactive FAQ below before opening a ticket.", color=EMBED_COLOR)
    embed.set_author(name="S W A G S A L E S  |  F.A.Q")
    await interaction.channel.send(embed=embed, view=FAQView())
    await interaction.response.send_message("✧ FAQ established.", ephemeral=True)

@bot.tree.command(name="prices", description="Display current pricing list")
async def prices(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ Current Price List", description="**Service 1:** $10\n**Service 2:** $25\n**Service 3:** $50\n\n*Prices are subject to change. Open a ticket to buy.*", color=EMBED_COLOR)
    embed.set_footer(text="swagsales • pricing")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch", description="Submit feedback")
@app_commands.describe(member="Staff", stars="Rating", comment="Comment")
@app_commands.choices(stars=[app_commands.Choice(name=f"{i} Stars", value=i) for i in range(5, 0, -1)])
async def vouch(interaction: discord.Interaction, member: discord.Member, stars: app_commands.Choice[int], comment: str, image: discord.Attachment = None):
    vouch_channel = bot.get_channel(VOUCH_CHANNEL_ID)
    if vouch_channel:
        rating = ("✦" * stars.value) + ("✧" * (5 - stars.value))
        embed = discord.Embed(description=f"✧ **Feedback**\n\n> {comment}", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"Vouch for {member.display_name}")
        embed.add_field(name="Rating", value=rating, inline=True)
        embed.set_footer(text="swagsales • reputation system")
        if image: embed.set_image(url=image.url)
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✧ Vouch sent.", ephemeral=True)

@bot.tree.command(name="paypal", description="PayPal info")
async def paypal(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="✧ PayPal", description=f"`{PAYPAL_INFO}`", color=EMBED_COLOR))

@bot.tree.command(name="revolut", description="Revolut info")
async def revolut(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="✧ Revolut", description=f"`{REVOLUT_TAG}`", color=EMBED_COLOR))

# --- VIEWS ET MENUS DÉROULANTS ---
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Buying", description="Buy goods", emoji="🛒"),
            discord.SelectOption(label="Selling", description="Sell goods", emoji="💰"),
            discord.SelectOption(label="Business", description="Promote & Partner", emoji="💼"),
            discord.SelectOption(label="Questions", description="General Support", emoji="❔")
        ]
        super().__init__(placeholder="Select an option...", custom_id="ticket_select", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    change_status.start() # Lancement du statut animé
    bot.add_view(TicketView())
    bot.add_view(TicketControlView())
    bot.add_view(FAQView()) 
    await bot.tree.sync()
    print(f'✧ {bot.user} is active and fully loaded.')

if TOKEN:
    bot.run(TOKEN)
