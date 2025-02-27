import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# Intents設定
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True  # メッセージの内容を取得するために必要

# Botのインスタンスを作成
bot = commands.Bot(command_prefix="/", intents=intents)

# チケット設定（ギルドごとの設定を保存）
ticket_settings = {}
ticket_titles = {}  # チケットタイトルや説明を保存
staff_roles = {}  # スタッフロールを保存
developed_info = {}  # Developed情報を保存
dm_messages = {}  # チケットを開いた際に送信するDMメッセージを保存
ticket_colors = {}  # チケットカラーを保存
ticket_links = {}  # チケットリンクを保存
panel_images = {}  # パネルに表示する画像やGIF
panel_embed_colors = {}  # パネルの埋め込みカラー
panel_top_right_images = {}  # パネルの右上に表示する画像やGIF
panel_developer_text = {}  # パネルの左下に表示する文章
panel_developer_image = {}  # パネルの左下に表示する画像
ticket_open_images = {}  # チケットを開いた時のembedに表示する画像
ticket_close_images = {}  # チケットを閉じた時のembedに表示する画像

def create_ticket_embed(title="チケットサポート", description="以下のボタンを押してチケットを開いてください。", image_url=None, thumbnail_url=None, color=discord.Color.blue(), developed_text=None, developed_icon_url=None, top_right_image_url=None, developer_text=None, developer_image_url=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if image_url:
        embed.set_image(url=image_url)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if developed_text and developed_icon_url:
        embed.set_footer(text=developed_text, icon_url=developed_icon_url)
    if top_right_image_url:
        embed.set_thumbnail(url=top_right_image_url)
    if developer_image_url:
        embed.set_thumbnail(url=developer_image_url)
    if developer_text:
        embed.add_field(name="\u200b", value=developer_text, inline=False)
    return embed

class TicketView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(options))

class TicketSelect(discord.ui.Select):
    def __init__(self, options):
        select_options = [
            discord.SelectOption(label=option["name"], value=str(option["category"]), description=option["description"], emoji=option["emoji"])
            for option in options
        ]
        super().__init__(placeholder="チケットを開くカテゴリーを選択してください...", options=select_options)

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, int(self.values[0]))

async def create_ticket(interaction: discord.Interaction, category_id: int, answers=None):
    guild = interaction.guild
    category = discord.utils.get(guild.categories, id=category_id)
    if not category:
        await interaction.response.send_message("カテゴリーが見つかりません！", ephemeral=True)
        return

    if discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name.lower()}"):
        await interaction.response.send_message("既にチケットが開かれています！", ephemeral=True)
        return

    # チケット作成時に通知するスタッフロールを取得
    staff_role = discord.utils.get(guild.roles, id=staff_roles.get(guild.id))

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    ticket_channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}", category=category, overwrites=overwrites
    )

    title = ticket_titles.get(guild.id, {}).get("title", "チケット")
    description = ticket_titles.get(guild.id, {}).get("description", "サポートが必要ですか？")
    color = ticket_colors.get(guild.id, discord.Color.blue())
    image_url = ticket_open_images.get(guild.id)

    if answers:
        description += "\n\n" + "\n".join([f"{key}: {value}" for key, value in answers.items()])

    await interaction.response.send_message(
        embed=discord.Embed(
            title="🎫 チケットが作成されました。",
            description="下のボタンをクリックしてアクセスしてください。",
            color=color
        ).set_author(
            name=interaction.user.name,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        ),
        view=VisitTicketView(ticket_channel),
        ephemeral=True,
    )

    guild_info = developed_info.get(guild.id, {})
    embed = discord.Embed(
        title=title, description=description, color=color
    ).set_author(
        name=guild.name, icon_url=guild.icon.url if guild.icon else None
    ).set_thumbnail(
        url=interaction.user.avatar.url if interaction.user.avatar else None
    ).set_footer(
        text=guild_info.get("text", ""), icon_url=guild_info.get("icon_url", "")
    ).set_image(
        url=image_url
    )

    await ticket_channel.send(
        f"{interaction.user.mention} {staff_role.mention if staff_role else ''}",
        embed=embed,
        view=CloseTicketView(),
    )

class VisitTicketView(discord.ui.View):
    def __init__(self, ticket_channel):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="チケットに行く",
            style=discord.ButtonStyle.success,
            emoji="🎫",
            url=ticket_channel.jump_url
        ))

class CloseTicketView(discord.ui.View):
    @discord.ui.button(label="Pin チケット", style=discord.ButtonStyle.green, custom_id="pin_ticket", emoji="📌")
    async def pin_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, id=staff_roles.get(interaction.guild.id))
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message("この操作を行う権限がありません。", ephemeral=True)
            return
        await interaction.channel.edit(name=f"📌{interaction.channel.name}")
        await interaction.response.send_message("チケットがピンされました。", ephemeral=True)

    @discord.ui.button(label="チケットを閉じる", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="❎")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="チケットを閉じますか？",
            description="本当にこのチケットを閉じますか？",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

class ConfirmCloseView(discord.ui.View):
    @discord.ui.button(label="はい", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        dm_message = dm_messages.get(interaction.guild.id, "")
        ticket_link = ticket_links.get(interaction.guild.id, "")
        image_url = ticket_close_images.get(interaction.guild.id)
        if dm_message:
            embed = discord.Embed(
                title="📄チケットが閉じました", description=dm_message, color=discord.Color.red()
            ).set_author(
                name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            ).add_field(
                name="作成者", value=f"{interaction.user.mention}\nID: {interaction.user.id}", inline=False
            ).add_field(
                name="作成日時", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), inline=False
            ).set_thumbnail(
                url=interaction.user.avatar.url if interaction.user.avatar else None
            ).set_image(
                url=image_url
            )
            view = discord.ui.View()
            if ticket_link:
                view.add_item(discord.ui.Button(
                    label="チケットをもう一度作成する",
                    style=discord.ButtonStyle.primary,
                    url=ticket_link
                ))
            await interaction.user.send(embed=embed, view=view)
        await interaction.channel.delete()

    @discord.ui.button(label="いいえ", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("キャンセルしました。", ephemeral=True)

@bot.tree.command(name="ticket_button", description="チケット作成ボタンとスタッフロールを設定します。")
@app_commands.describe(emoji="ボタンに表示する絵文字", name="ボタンの名前", description="ボタンの説明", staff_role="通知するスタッフロール（@メンション）")
async def ticket_button_command(interaction: discord.Interaction, emoji: str, name: str, description: str, staff_role: discord.Role):
    category_options = [
        discord.SelectOption(label=category.name, value=str(category.id))
        for category in interaction.guild.categories
    ]

    class CategorySelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(CategorySelect())

    class CategorySelect(discord.ui.Select):
        def __init__(self):
            super().__init__(placeholder="カテゴリーを選択してください...", options=category_options)

        async def callback(self, interaction: discord.Interaction):
            category_id = int(self.values[0])
            if interaction.guild.id not in ticket_settings:
                ticket_settings[interaction.guild.id] = []

            ticket_settings[interaction.guild.id].append(
                {"category": category_id, "emoji": emoji, "name": name, "description": description}
            )

            staff_roles[interaction.guild.id] = staff_role.id
            await interaction.response.send_message(
                f"ボタン '{name}' (カテゴリー: {category_id}, 絵文字: {emoji}) とスタッフロール '{staff_role.name}' を追加しました。",
                ephemeral=True,
            )

    await interaction.response.send_message("カテゴリーを選択してください：", view=CategorySelectView(), ephemeral=True)

@bot.tree.command(name="ticket_modal", description="チケットのタイトルと説明を設定します。")
async def ticket_modal_command(interaction: discord.Interaction):
    class TicketModal(discord.ui.Modal, title="チケット設定"):
        title_field = discord.ui.TextInput(
            label="チケットのタイトル", style=discord.TextStyle.short, placeholder="例: サポートチケット", required=True,
        )
        description_field = discord.ui.TextInput(
            label="チケットの説明", style=discord.TextStyle.paragraph, placeholder="例: サポートチームに連絡したい内容を書いてください。", required=False,
        )

        async def on_submit(self, interaction: discord.Interaction):
            if interaction.guild.id not in ticket_titles:
                ticket_titles[interaction.guild.id] = {}
            ticket_titles[interaction.guild.id]["title"] = self.title_field.value
            ticket_titles[interaction.guild.id]["description"] = self.description_field.value

            await interaction.response.send_message(f"チケットのタイトルを '{self.title_field.value}' に、説明を設定しました。", ephemeral=True)

    await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="open_ticket_settings", description="チケットのEmbedカラー、タイトル、説明を設定します。")
@app_commands.describe(title="チケットのタイトル", description="チケットの説明", color="チケットのEmbedカラー（赤、青、黄色、緑から選択）")
async def open_ticket_settings_command(interaction: discord.Interaction, title: str, description: str, color: str):
    color_dict = {
        "赤": discord.Color.red(), "青": discord.Color.blue(), "黄色": discord.Color.gold(), "緑": discord.Color.green()
    }
    embed_color = color_dict.get(color, discord.Color.blue())

    ticket_titles[interaction.guild.id] = {"title": title, "description": description}
    ticket_colors[interaction.guild.id] = embed_color
    await interaction.response.send_message("チケットの設定を保存しました。", ephemeral=True)

@bot.tree.command(name="ticket_panel", description="チケットパネルを作成します。")
async def ticket_panel_command(interaction: discord.Interaction):
    buttons = ticket_settings.get(interaction.guild.id, [])
    if not buttons:
        await interaction.response.send_message("チケットのボタンが設定されていません！", ephemeral=True)
        return

    title = "チケットサポート"
    description = "以下のボタンを押してチケットを開いてください。"
    guild_info = developed_info.get(interaction.guild.id, {})
    image_url = panel_images.get(interaction.guild.id)
    top_right_image_url = panel_top_right_images.get(interaction.guild.id)
    developer_text = panel_developer_text.get(interaction.guild.id)
    developer_image_url = panel_developer_image.get(interaction.guild.id)
    color = panel_embed_colors.get(interaction.guild.id, discord.Color.blue())
    embed = create_ticket_embed(
        title=title, description=description, image_url=image_url, thumbnail_url=guild_info.get("thumbnail_url"),
        color=color, developed_text=guild_info.get("text"), developed_icon_url=guild_info.get("icon_url"),
        top_right_image_url=top_right_image_url, developer_text=developer_text, developer_image_url=developer_image_url
    ).set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    view = TicketView(buttons)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("チケットパネルを作成しました。", ephemeral=True)

@bot.tree.command(name="ticket_dm", description="チケットを開いた際にDMで送信する内容を設定します。")
async def ticket_dm_command(interaction: discord.Interaction):
    class DmModal(discord.ui.Modal, title="DMメッセージ設定"):
        message_field = discord.ui.TextInput(
            label="DMメッセージ", style=discord.TextStyle.paragraph, placeholder="例: チケットが開かれました。ご利用ありがとうございました。", required=True,
        )
        link_field = discord.ui.TextInput(
            label="チケットリンク", style=discord.TextStyle.short, placeholder="例: https://discord.com/channels/...", required=True,
        )

        async def on_submit(self, interaction: discord.Interaction):
            dm_messages[interaction.guild.id] = self.message_field.value
            ticket_links[interaction.guild.id] = self.link_field.value

            await interaction.response.send_message("DMメッセージとチケットリンクを設定しました。", ephemeral=True)

    await interaction.response.send_modal(DmModal())

@bot.tree.command(name="ticket_settings", description="チケットパネルの設定を管理します。")
@app_commands.describe(image_url="パネルに表示する画像やGIFのURL", color="パネルの埋め込みカラー（赤、青、黄色、緑から選択）", top_right_image_url="パネルの右上に表示する画像やGIFのURL")
async def ticket_settings_command(interaction: discord.Interaction, image_url: str, color: str, top_right_image_url: str):
    color_dict = {
        "赤": discord.Color.red(), "青": discord.Color.blue(), "黄色": discord.Color.gold(), "緑": discord.Color.green()
    }
    embed_color = color_dict.get(color, discord.Color.blue())

    panel_images[interaction.guild.id] = image_url
    panel_embed_colors[interaction.guild.id] = embed_color
    panel_top_right_images[interaction.guild.id] = top_right_image_url
    await interaction.response.send_message("チケットパネルの設定を保存しました。", ephemeral=True)

@bot.tree.command(name="ticket_embed_settings", description="チケットを開いた時と閉じた時のembedに画像を追加します。")
@app_commands.describe(open_image_url="チケットを開いた時のembedに表示する画像のURL", close_image_url="チケットを閉じた時のembedに表示する画像のURL")
async def ticket_embed_settings_command(interaction: discord.Interaction, open_image_url: str, close_image_url: str):
    ticket_open_images[interaction.guild.id] = open_image_url
    ticket_close_images[interaction.guild.id] = close_image_url
    await interaction.response.send_message("チケットのembed画像設定を保存しました。", ephemeral=True)

@bot.tree.command(name="ticket_developers", description="チケットパネルの左下に表示する文章と画像を設定します。")
@app_commands.describe(text="表示する文章", image_url="表示する画像のURL")
async def ticket_developers_command(interaction: discord.Interaction, text: str, image_url: str):
    panel_developer_text[interaction.guild.id] = text
    panel_developer_image[interaction.guild.id] = image_url
    await interaction.response.send_message("チケットパネルの開発者情報を設定しました。", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        for attachment in message.attachments:
            if attachment.url.lower().endswith(('png', 'jpg', 'jpeg', 'gif')):
                await message.channel.send(f"画像/ファイルのURLを取得しました: {attachment.url}")

bot.run("YOUR_BOT_TOKEN")