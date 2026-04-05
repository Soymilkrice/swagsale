import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION DES IDS ---
TOKEN = os.getenv('DISCORD_TOKEN') 

PANEL_CHANNEL_ID = 1470112371115556865
TICKET_CATEGORY_ID = 1470396846970114175
STAFF_ROLE_ID = 1470093020132147230  # Ce rôle sera ping à l'ouverture
LOG_CHANNEL_ID = 1490353930138419400 # Salon où le transcript sera envoyé
VOUCH_CHANNEL_ID = 1470425558075572256

VERIFIED_ROLE_ID = 1490386183094669482 
RULES_IMAGE_URL = "https://media.discordapp.net/attachments/1459700315380125717/1459711191369781279/IMG_7356.jpg"

VERIFY_EMOJI_ANIMATED = "<a:vamp:1490384484112138353>" 
VERIFY_EMOJI_ID = 1490384484112138353 

# Informations de paiement
PAYPAL_INFO = "paypal.me/toncompte"
LTC_ADDRESS = "LTC_ADDRESS_HERE"
CASHAPP_TAG = "$YourCashAppTag"
REVOLUT_TAG = "@YourRevolutTag"

# Finitions Prestige
TOS_TEXT = "✧ All sales are final. No refunds once goods are delivered.\n✧ We are not responsible for bans.\n✧ Charging back = immediate blacklist."
THUMBNAIL_URL = "" # URL de ton logo S
EMBED_COLOR = 0x2b2d31 
# ------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

# --- TICKET CONTROLS (AVEC TRANSCRIPT & LOGS) ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.staff_notified = False 
        
    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("✧ Staff only.", ephemeral=True)
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✧ {interaction.user.mention} is now handling this request.")

    @discord.ui.button(label="Notify Staff", style=discord.ButtonStyle.primary, custom_id="notify_staff_btn")
    async def notify_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.staff_notified:
            return await interaction.response.send_message("✧ Staff already alerted.", ephemeral=True)
        self.staff_notified = True
        await interaction.response.send_message(f"✧ Alerting staff... <@&{STAFF_ROLE_ID}>")
        await asyncio.sleep(600) # Reset après 10min
        self.staff_notified = False

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✧ Generating transcript and closing...")
        
        # --- GÉNÉRATION DU TRANSCRIPT ---
        transcript_content = f"--- Transcript for {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time}] {msg.author.name}: {msg.content}\n"
        
        # Sauvegarde en mémoire
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"transcript-{interaction.channel.name}.txt")
        
        # Envoi dans le salon de LOGS
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Ticket Closed",
                description=f"**Channel:** {interaction.channel.name}\n**Closed by:** {interaction.user.mention}",
                color=0xff0000
            )
            await log_channel.send(embed=log_embed, file=file)
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- TICKET MODAL ---
class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"{ticket_type} Request")
        self.ticket_type = ticket_type
        self.add_item(discord.ui.TextInput(label="Payment Method", placeholder="PayPal, LTC, etc.", required=True))
        self.add_item(discord.ui.TextInput(label="Order Details", style=discord.TextStyle.paragraph, required=True))

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        staff_role = guild.get_role(STAFF_ROLE_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        channel = await guild.create_text_channel(name=f"{self.ticket_type}-{interaction.user.name}", category=category, overwrites=overwrites)
        
        embed = discord.Embed(description=f"Welcome {interaction.user.mention}. Staff will assist you shortly.\n───────────────", color=EMBED_COLOR)
        embed.set_author(name=f"S W A G S A L E S  |  {self.ticket_type.upper()}")
        
        for item in self.children:
            embed.add_field(name=f"✧ {item.label}", value=f"> {item.value}\n", inline=False)
            
        tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
        embed.add_field(name="\u200b", value=f"───────────────\n**✧ Terms of Service**\n{tos_formatted}", inline=False)
        
        # PING DES OWNERS/STAFF à l'ouverture
        await channel.send(content=f"{interaction.user.mention} | <@&{STAFF_ROLE_ID}>", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✧ Ticket established: {channel.mention}", ephemeral=True)

# --- SETUP COMMANDS ---
@bot.tree.command(name="setup_verify", description="Post rules and verification")
@app_commands.default_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    emb_img = discord.Embed(color=EMBED_COLOR)
    emb_img.set_image(url=RULES_IMAGE_URL)
    await interaction.channel.send(embed=emb_img)
    
    desc = f"✧ **Rules**\n\n╰ no nsfw, gore\n╰ no harassing\n╰ use common sense\n\n{VERIFY_EMOJI_ANIMATED} **react below to gain access**"
    emb_txt = discord.Embed(description=desc, color=EMBED_COLOR)
    msg = await interaction.channel.send(embed=emb_txt)
    
    emoji = bot.get_emoji(VERIFY_EMOJI_ID)
    await msg.add_reaction(emoji or "✅")
    await interaction.followup.send("✧ Setup complete.", ephemeral=True)

@bot.tree.command(name="setup_panel", description="Generate support panel")
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
    desc = f"-# Select a category.\n✧ **Buying**\n\n✧ **Selling**\n\n✧ **Business**\n\n✧ **Questions**\n\n───────────────\n**✧ Terms of Service**\n{tos_formatted}"
    embed = discord.Embed(description=desc, color=EMBED_COLOR)
    embed.set_author(name="S W A G S A L E S  |  Support Center")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✧ Panel established.", ephemeral=True)

@bot.tree.command(name="vouch", description="Submit feedback")
@app_commands.describe(member="Staff", stars="Rating", comment="Comment")
@app_commands.choices(stars=[app_commands.Choice(name=f"{i} Stars", value=i) for i in range(5, 0, -1)])
async def vouch(interaction: discord.Interaction, member: discord.Member, stars: app_commands.Choice[int], comment: str, image: discord.Attachment = None):
    vouch_channel = bot.get_channel(VOUCH_CHANNEL_ID)
    if vouch_channel:
        rating = ("✦" * stars.value) + ("✧" * (5 - stars.value))
        embed = discord.Embed(description=f"✧ **Feedback**\n\n> {comment}", color=EMBED_COLOR)
        embed.set_author(name=f"Vouch for {member.display_name}")
        embed.add_field(name="Rating", value=rating, inline=True)
        if image: embed.set_image(url=image.url)
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✧ Vouch sent.", ephemeral=True)

@bot.tree.command(name="paypal", description="PayPal info")
async def paypal(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="✧ PayPal", description=f"`{PAYPAL_INFO}`", color=EMBED_COLOR))

# --- VIEWS ---
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="Buying", emoji="🛒"), discord.SelectOption(label="Selling", emoji="💰"), discord.SelectOption(label="Business", emoji="💼"), discord.SelectOption(label="Questions", emoji="❔")]
        super().__init__(placeholder="Select option...", custom_id="ticket_select", options=options)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Support Center"))
    bot.add_view(TicketView())
    bot.add_view(TicketControlView()) 
    await bot.tree.sync()
    print(f'✧ {bot.user} is active.')

if TOKEN:
    bot.run(TOKEN)
    
