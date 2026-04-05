import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import os # Added for Environment Variables
from dotenv import load_dotenv # Added to load .env locally

# Load environment variables (Local testing will use a .env file, Railway uses its dashboard)
load_dotenv()

# --- CONFIGURATION DES IDS ---
# Railway will pull this from the "Variables" tab
TOKEN = os.getenv('DISCORD_TOKEN') 

PANEL_CHANNEL_ID = 1470112371115556865
TICKET_CATEGORY_ID = 1470396846970114175
STAFF_ROLE_ID = 1470093020132147230
LOG_CHANNEL_ID = 1490353930138419400
VOUCH_CHANNEL_ID = 1470425558075572256

# Payment Information
PAYPAL_INFO = "paypal.me/toncompte"
LTC_ADDRESS = "LTC_ADDRESS_HERE"
CASHAPP_TAG = "$YourCashAppTag"
REVOLUT_TAG = "@YourRevolutTag"

# Prestige Finishes
TOS_TEXT = "✧ All sales are final. No refunds once goods are delivered.\n✧ We are not responsible for any game-side restrictions or bans.\n✧ Charging back will result in an immediate blacklist from our services."
# ------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- TICKET CONTROLS ---
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

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        transcript_content = f"--- Final Transcript for {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time_formatted = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time_formatted}] {msg.author.name}: {msg.content}\n"
        
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"archive-{interaction.channel.name}.txt")
        
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="Archived Record", description=f"**Reference:** {interaction.channel.name}\n**Authorized by:** {interaction.user.mention}", color=0x2b2d31)
            log_embed.set_footer(text="swagsales • secure archive")
            await log_channel.send(embed=log_embed, file=file)

        await interaction.followup.send("✧ Archive secured. Commencing closure sequence...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

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

# --- MODAL ---
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
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        embed = discord.Embed(description=f"Welcome {interaction.user.mention}. A representative will be with you shortly.\n───────────────", color=0x2b2d31)
        embed.set_author(name=f"S W A G S A L E S  |  {self.ticket_type.upper()}")
        embed.set_thumbnail(url=THUMBNAIL_URL) 
        
        for item in self.children:
            answer = item.value if item.value else "*None provided*"
            embed.add_field(name=f"✧ {item.label}", value=f"> {answer}\n", inline=False)
            
        tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
        embed.add_field(name="\u200b", value=f"───────────────\n**✧ Terms of Service**\n{tos_formatted}", inline=False)
            
        embed.set_footer(text="swagsales © 2026 • Secure Transaction Desk")
        await ticket_channel.send(content=f"{interaction.user.mention} | <@&{STAFF_ROLE_ID}>", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✧ Request established: {ticket_channel.mention}", ephemeral=True)

# --- SLASH COMMANDS ---
@bot.tree.command(name="tos", description="Display our Terms of Service directly to the user")
async def tos(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ Terms of Service", description=TOS_TEXT, color=0x2b2d31)
    embed.set_footer(text="swagsales • legal")
    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="setup_tos", description="Post a permanent TOS message in this channel (Admins only)")
@app_commands.default_permissions(administrator=True)
async def setup_tos(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ Terms of Service", description=TOS_TEXT, color=0x2b2d31)
    embed.set_footer(text="swagsales © 2026 • Legal & Policy")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✧ Permanent TOS established.", ephemeral=True)

@bot.tree.command(name="paypal", description="Display PayPal information")
async def paypal(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ PayPal Payment", description=f"Please send the agreed amount to:\n`{PAYPAL_INFO}`\n\n-# Select 'Friends & Family' if possible.", color=0x2b2d31)
    embed.set_footer(text="swagsales • checkout")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ltc", description="Display Litecoin address")
async def ltc(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ Litecoin Payment", description=f"Network: **LTC**\nAddress:\n`{LTC_ADDRESS}`", color=0x2b2d31)
    embed.set_footer(text="swagsales • checkout")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="revolut", description="Display Revolut tag")
async def revolut(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ Revolut Payment", description=f"Please send the agreed amount to:\n`{REVOLUT_TAG}`", color=0x2b2d31)
    embed.set_footer(text="swagsales • checkout")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cashapp", description="Display CashApp tag")
async def cashapp(interaction: discord.Interaction):
    embed = discord.Embed(title="✧ CashApp Payment", description=f"Please send the agreed amount to:\n`{CASHAPP_TAG}`", color=0x2b2d31)
    embed.set_footer(text="swagsales • checkout")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch", description="Submit feedback")
@app_commands.describe(member="Staff member", stars="Rating", comment="Feedback", image="Screenshot")
@app_commands.choices(stars=[app_commands.Choice(name=f"{i} Stars", value=i) for i in range(5, 0, -1)])
async def vouch(interaction: discord.Interaction, member: discord.Member, stars: app_commands.Choice[int], comment: str, image: discord.Attachment = None):
    vouch_channel = bot.get_channel(VOUCH_CHANNEL_ID)
    if vouch_channel:
        rating_display = ("✦" * stars.value) + ("✧" * (5 - stars.value))
        embed = discord.Embed(description=f"✧ **Customer Feedback**\n\n> {comment}", color=0x2b2d31)
        embed.set_author(name=f"Vouch for {member.display_name}")
        embed.add_field(name="Customer", value=interaction.user.mention, inline=True)
        embed.add_field(name="Rating", value=rating_display, inline=True)
        embed.set_footer(text="swagsales • reputation system")
        if image: embed.set_image(url=image.url)
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✧ Feedback submitted.", ephemeral=True)

@bot.tree.command(name="setup_panel", description="Generate the Support Center (Admins only)")
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    tos_formatted = "\n".join([f"-# {line}" for line in TOS_TEXT.split('\n')])
    desc = (
        "-# Please select the category that best matches your inquiry.\n"
        "✧ **Buying**\n*Interested in acquiring goods or accounts.*\n\n"
        "✧ **Selling**\n*Willing to sell or estimate accounts.*\n\n"
        "✧ **Business**\n*Partnerships and network associates.*\n\n"
        "✧ **Questions**\n*General support.*\n\n"
        "───────────────\n"
        "**✧ Terms of Service**\n"
        f"{tos_formatted}"
    )
    
    embed = discord.Embed(description=desc, color=0x2b2d31)
    embed.set_author(name="S W A G S A L E S  |  Support Center")
    embed.set_footer(text="swagsales © 2026 • Premium Services")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✧ Support panel established.", ephemeral=True)

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Buying", description="Acquire in-game goods", emoji="🛒"),
            discord.SelectOption(label="Selling", description="Sell your goods", emoji="💰"),
            discord.SelectOption(label="Business", description="Promote and associate", emoji="💼"),
            discord.SelectOption(label="Questions", description="General inquiries", emoji="❔")
        ]
        super().__init__(placeholder="Select an option...", min_values=1, max_values=1, options=options, custom_id="ticket_category_select")
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(ticket_type=self.values[0]))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Support Center"))
    bot.add_view(TicketView()) 
    bot.add_view(TicketControlView()) 
    try:
        synced = await bot.tree.sync()
        print(f'✧ {bot.user} is active. Synced {len(synced)} slash commands.')
    except Exception as e: print(f"✧ Sync error: {e}")

# Check if token exists before running
if TOKEN:
    bot.run(TOKEN)
else:
    print("✧ CRITICAL ERROR: DISCORD_TOKEN not found in environment variables.")
