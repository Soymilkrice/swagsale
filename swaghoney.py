import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import io
import os
import itertools
import random
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

TOS_TEXT = "All sales are final. No refunds once goods are securely delivered.\nWe are not responsible for any game-side restrictions or bans.\nCharging back will result in an immediate blacklist from our services."
THUMBNAIL_URL = "" # URL de ton logo S
BANNER_URL = "" # URL d'une grande image horizontale
EMBED_COLOR = 0x2b2d31 
# ------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- STATUT ANIMÉ (ROTATING PRESENCE) ---
status_cycle = itertools.cycle(["over Support Center", "Premium Services", "150+ Happy Customers"])

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
                    title="✧ Verification Successful",
                    description=f"Your access to **{guild.name}** has been securely granted. Feel free to browse our services and reach out if you need anything.\n\n*Welcome aboard.*",
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
            discord.SelectOption(label="Payment Methods", description="View our accepted secure payment gateways.", emoji="💳"),
            discord.SelectOption(label="Delivery Time", description="Information regarding order fulfillment speed.", emoji="⏳"),
            discord.SelectOption(label="Refund Policy", description="Details on our final-sale and return policies.", emoji="🛑")
        ]
        super().__init__(placeholder="Select a topic to explore...", custom_id="faq_select", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        answers = {
            "Payment Methods": f"✧ **Secure Payment Gateways**\nWe currently accept the following methods to ensure your security:\n> **PayPal:** `{PAYPAL_INFO}`\n> **Revolut:** `{REVOLUT_TAG}`\n> **Crypto:** LTC / BTC\n> **CashApp:** Supported upon request.",
            "Delivery Time": "✧ **Fulfillment Speed**\nDelivery is typically **instantaneous** once your payment is confirmed by our dedicated staff. In rare cases, it may take up to 15 minutes.",
            "Refund Policy": "✧ **Transaction Policy**\nAs meticulously stated in our Terms of Service, **all sales are final**. We do not offer refunds once goods have been securely delivered to you."
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
            return await interaction.response.send_message("✧ Access denied. Restricted to authorized personnel.", ephemeral=True)
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✧ {interaction.user.mention} has taken charge of your request.")

    @discord.ui.button(label="Notify Staff", style=discord.ButtonStyle.primary, custom_id="notify_staff_btn")
    async def notify_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.staff_notified:
            return await interaction.response.send_message("✧ Our team has already been paged. Thank you for your patience.", ephemeral=True)
        self.staff_notified = True
        await interaction.response.send_message(f"✧ Paging available representatives... <@&{STAFF_ROLE_ID}>")
        await asyncio.sleep(900)
        self.staff_notified = False

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="transcript_ticket_btn")
    async def transcript_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        transcript_content = f"--- Official Live Transcript ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time_formatted = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time_formatted}] {msg.author.name}: {msg.content}\n"
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"transcript_{interaction.channel.name}.txt")
        await interaction.followup.send(content="✧ Live transcript generated successfully.", file=file)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Phrases dynamiques pour l'Auto-Vouch
        farewells = [
            "We hope your transaction was flawlessly executed. If you have a moment, please leave a review using `/vouch` in our server.",
            "Thank you for your trust. Your feedback is highly appreciated—consider typing `/vouch` to let others know about your experience.",
            "It was a pleasure doing business with you. Feel free to share your experience using the `/vouch` command.",
            "Your order is complete! We strive for excellence, and your review via `/vouch` helps us grow."
        ]
        
        try:
            creator_id = int(interaction.channel.topic) 
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="✧ Thank you for choosing SWAGSALES",
                    description=f"> {random.choice(farewells)}\n\n*We look forward to serving you again soon.*",
                    color=EMBED_COLOR
                )
                await creator.send(embed=dm_embed)
        except:
            pass 
        
        # Transcript envoyé dans les logs
        transcript_content = f"--- Final Encrypted Transcript for {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            time_formatted = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript_content += f"[{time_formatted}] {msg.author.name}: {msg.content}\n"
        buffer = io.BytesIO(transcript_content.encode('utf-8'))
        file = discord.File(buffer, filename=f"archive-{interaction.channel.name}.txt")
        
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="🔒 Archived Record", description=f"**Reference:** {interaction.channel.name}\n**Authorized by:** {interaction.user.mention}", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
            log_embed.set_footer(text="swagsales • secure archive")
            await log_channel.send(embed=log_embed, file=file)
            
        await interaction.followup.send("✧ Archive secured. Commencing closure sequence...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- TICKET MODAL (FORMULAIRES DYNAMIQUES) ---
class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"{ticket_type} Concierge")
        self.ticket_type = ticket_type

        if ticket_type == "Buying":
            self.add_item(discord.ui.TextInput(label="Preferred payment method", placeholder="e.g. PayPal, CashApp, Crypto", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Order Specification", placeholder="Detail the items you wish to acquire...", style=discord.TextStyle.paragraph, required=True))
            self.add_item(discord.ui.TextInput(label="Additional Requirements", placeholder="Any specific requests or budget constraints?", style=discord.TextStyle.paragraph, required=False))
        elif ticket_type == "Selling":
            self.add_item(discord.ui.TextInput(label="Preferred receiving method", placeholder="e.g. PayPal, Crypto", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Asset Inventory", placeholder="List the items you are looking to sell...", style=discord.TextStyle.paragraph, required=True))
            self.add_item(discord.ui.TextInput(label="Additional Notes", placeholder="Desired prices, bundle deals, etc.", style=discord.TextStyle.paragraph, required=False))
        elif ticket_type in ["Business", "Questions"]:
            self.add_item(discord.ui.TextInput(label="Inquiry Topic", placeholder="e.g. Partnership, Account Support, Bulk Deal", style=discord.TextStyle.short, required=True))
            self.add_item(discord.ui.TextInput(label="Detailed Description", placeholder="Elaborate on your inquiry so we can assist you better...", style=discord.TextStyle.paragraph, required=True))

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
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=str(interaction.user.id))
        
        embed = discord.Embed(description="───────────────", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        if THUMBNAIL_URL: embed.set_thumbnail(url=THUMBNAIL_URL)
        
        for item in self.children:
            answer = item.value if item.value else "*None provided*"
            embed.add_field(name=f"✧ {item.label}", value=f"> {answer}\n", inline=False)
            
        tos_formatted = "\n".join([f"-# ╰ {line}" for line in TOS_TEXT.split('\n')])
        embed.add_field(name="\u200b", value=f"───────────────\n**✧ Service Agreement**\n{tos_formatted}", inline=False)
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
    
    desc = f"✧ **Community Guidelines**\n\n-# ╰ no nsfw, gore, or self harm\n-# ╰ no harassing or inappropriate behavior\n-# ╰ no advertising of any kind\n-# ╰ no scamming or doxxing\n-# ╰ be respectful towards staff and members\n\n{VERIFY_EMOJI_ANIMATED} **React below to unlock the server.**"
    embed_rules = discord.Embed(description=desc, color=EMBED_COLOR)
    msg_rules = await interaction.channel.send(embed=embed_rules)
    
    emoji = bot.get_emoji(VERIFY_EMOJI_ID)
    await msg_rules.add_reaction(emoji or "✅")
    await interaction.followup.send("✧ Verification system online.", ephemeral=True)

@bot.tree.command(name="setup_panel", description="Generate support panel")
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    tos_formatted = "\n".join([f"-# ╰ {line}" for line in TOS_TEXT.split('\n')])
    desc = (f"✧ **Buying**\n-# Browse and purchase our premium selection.\n\n"
            f"✧ **Selling**\n-# Offer your goods for a secure and fast exchange.\n\n"
            f"✧ **Business**\n-# Propose partnerships or promotional inquiries.\n\n"
            f"✧ **Questions**\n-# Get assistance from our dedicated support team.\n\n"
            f"───────────────\n**✧ Service Agreement**\n{tos_formatted}")
    
    embed = discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
    embed.set_footer(text="swagsales © 2026 • Premium Services")
    if BANNER_URL: embed.set_image(url=BANNER_URL)
    
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("✧ Support panel deployed.", ephemeral=True)

@bot.tree.command(name="setup_faq", description="Generate Interactive FAQ panel")
@app_commands.default_permissions(administrator=True)
async def setup_faq(interaction: discord.Interaction):
    embed = discord.Embed(description="✧ Have an inquiry? Browse our interactive knowledge base below before opening a ticket to save time.", color=EMBED_COLOR)
    embed.set_author(name="S W A G S A L E S  |  F.A.Q")
    await interaction.channel.send(embed=embed, view=FAQView())
    await interaction.response.send_message("✧ FAQ panel deployed.", ephemeral=True)

@bot.tree.command(name="setup_referral", description="Generate the Ambassador Program panel")
@app_commands.default_permissions(administrator=True)
async def setup_referral(interaction: discord.Interaction):
    desc = (
        "───────────────\n"
        "✧ **Milestones**\n"
        "> 🥉 **5 Invites:** `Loyalty` Role\n"
        "> 🥈 **15 Invites:** `5% Off Next Order` + `Affiliate` Role\n"
        "> 🥇 **30 Invites:** `10% Off Next Order` + `Ambassador` Role\n"
        "> 💎 **50+ Invites:** `$15 Store Credit` + `Priority Access`\n\n"
        "───────────────\n"
        "✧ **Guidelines**\n"
        "-# ╰ Fake accounts and alt-farming will result in a permanent blacklist.\n"
        "-# ╰ Invites are only counted if the user stays in the server."
    )

    embed = discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
    embed.set_footer(text="swagsales © 2026 • network")
    
    if THUMBNAIL_URL: embed.set_thumbnail(url=THUMBNAIL_URL)

    view = discord.ui.View()
    btn = discord.ui.Button(label="Claim Privileges", style=discord.ButtonStyle.secondary, emoji="🥂")
    
    async def btn_callback(btn_interaction: discord.Interaction):
        await btn_interaction.response.send_message(
            "✧ **To claim your privileges:**\n"
            "Please navigate to the Support Center and open a **Questions** ticket. A representative will verify your invites.", 
            ephemeral=True
        )
    btn.callback = btn_callback
    view.add_item(btn)

    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✧ Referral panel deployed.", ephemeral=True)

@bot.tree.command(name="prices", description="Display current luxury pricing list")
async def prices(interaction: discord.Interaction):
    desc = (
        "───────────────\n"
        "✧ **Tier 1 Services**\n"
        "> Item A: `$10.00`\n"
        "> Item B: `$25.00`\n\n"
        "✧ **Tier 2 Services**\n"
        "> Premium Package: `$50.00`\n"
        "> Elite Bundle: `$100.00`\n"
        "───────────────\n"
        "-# Prices are subject to market fluctuations. Please open a ticket to lock in your rate."
    )
    embed = discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
    embed.set_author(name="S W A G S A L E S  |  Price Index")
    embed.set_footer(text="swagsales • pricing")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch", description="Submit feedback")
@app_commands.describe(member="Staff", stars="Rating", comment="Comment")
@app_commands.choices(stars=[app_commands.Choice(name=f"{i} Stars", value=i) for i in range(5, 0, -1)])
async def vouch(interaction: discord.Interaction, member: discord.Member, stars: app_commands.Choice[int], comment: str, image: discord.Attachment = None):
    vouch_channel = bot.get_channel(VOUCH_CHANNEL_ID)
    if vouch_channel:
        rating = ("✦" * stars.value) + ("✧" * (5 - stars.value))
        embed = discord.Embed(description=f"✧ **Client Feedback**\n\n> {comment}", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"Vouch provided for {member.display_name}")
        embed.add_field(name="Rating", value=rating, inline=True)
        embed.set_footer(text="swagsales • verified reputation")
        if image: embed.set_image(url=image.url)
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✧ Your feedback has been securely registered. Thank you.", ephemeral=True)

@bot.tree.command(name="paypal", description="PayPal info")
async def paypal(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="✧ Secured Payment | PayPal", description=f"> `{PAYPAL_INFO}`", color=EMBED_COLOR))

@bot.tree.command(name="revolut", description="Revolut info")
async def revolut(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title="✧ Secured Payment | Revolut", description=f"> `{REVOLUT_TAG}`", color=EMBED_COLOR))

# --- VIEWS ET MENUS DÉROULANTS ---
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Buying", description="Browse and purchase our premium selection.", emoji="🛒"),
            discord.SelectOption(label="Selling", description="Offer your goods for a secure and fast exchange.", emoji="💰"),
            discord.SelectOption(label="Business", description="Propose partnerships or promotional inquiries.", emoji="💼"),
            discord.SelectOption(label="Questions", description="Get assistance from our dedicated support team.", emoji="❔")
        ]
        super().__init__(placeholder="Select an inquiry category...", custom_id="ticket_select", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@event
async def on_ready():
    change_status.start()
    bot.add_view(TicketView())
    bot.add_view(TicketControlView())
    bot.add_view(FAQView()) 
    await bot.tree.sync()
    print(f'✧ {bot.user} is active and fully loaded.')

if TOKEN:
    bot.run(TOKEN)
