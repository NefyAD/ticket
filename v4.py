import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os

# Intents設定
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

# Botのインスタンスを作成
bot = commands.Bot(command_prefix="/", intents=intents)

# チケット設定（ギルドごとの設定を保存）
ticket_settings = {}
ticket_titles = {}  # チケットタイトルや説明を保存
staff_roles = {}  # スタッフロールを保存
developed_info = {}  # Developed情報を保存
dm_messages = {}  # チケットを開いた際に送信するDMメッセージを保存
ticket_colors = {}  # チケットカラーを保存
ticket_questions = {}  # チケットの質問を保存
ticket_links = {}  # チケットリンクを保存


def create_ticket_embed(title="チケットサポート", description="以下のボタンを押してチケットを開いてください。", image_url=None, thumbnail_url=None, color=discord.Color.blue(), developed_text=None, developed_icon_url=None):
    """
    チケットパネル用のEmbedを作成
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
    )
    if image_url:
        embed.set_image(url=image_url)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if developed_text and developed_icon_url:
        embed.set_footer(text=developed_text, icon_url=developed_icon_url)
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
        category_id = int(self.values[0])
        guild_id = interaction.guild.id
        if guild_id in ticket_questions:
            question_data = ticket_questions[guild_id].get(category_id)
            if question_data:
                questions = question_data["questions"]
                modal = TicketQuestionModal(questions, category_id)
                await interaction.response.send_modal(modal)
            else:
                await create_ticket(interaction, category_id)
        else:
            await create_ticket(interaction, category_id)


class TicketQuestionModal(discord.ui.Modal):
    def __init__(self, questions, category_id):
        super().__init__(title="チケット質問")
        self.questions = questions
        self.category_id = category_id
        for index, question in enumerate(questions):
            self.add_item(discord.ui.TextInput(
                label=f"質問 {index + 1}",
                style=discord.TextStyle.paragraph,
                placeholder=question,
                required=True,
            ))

    async def on_submit(self, interaction: discord.Interaction):
        answers = {f"質問 {index + 1}": item.value for index, item in enumerate(self.children)}
        await create_ticket(interaction, self.category_id, answers)


async def create_ticket(interaction: discord.Interaction, category_id: int, answers=None):
    guild = interaction.guild
    category = discord.utils.get(guild.categories, id=category_id)
    existing_ticket = discord.utils.get(
        guild.text_channels, name=f"ticket-{interaction.user.name.lower()}"
    )

    if existing_ticket:
        await interaction.response.send_message(
            "既にチケットが開かれています！", ephemeral=True
        )
        return

    if category is None:
        await interaction.response.send_message("カテゴリーが見つかりません！", ephemeral=True)
        return

    # チケット作成時に通知するスタッフロールを取得
    staff_role_id = staff_roles.get(guild.id)
    staff_role = discord.utils.get(guild.roles, id=staff_role_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(
            read_messages=True, send_messages=True
        ),
    }
    ticket_channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}",
        category=category,
        overwrites=overwrites,
    )

    # チケットタイトルと説明を取得
    title = ticket_titles.get(guild.id, {}).get("title", "チケット")
    description = ticket_titles.get(guild.id, {}).get("description", "サポートが必要ですか？")
    
    # チケットカラーを取得
    color = ticket_colors.get(guild.id, discord.Color.blue())

    # Embedに質問の回答を追加
    if answers:
        description += "\n\n"
        description += "\n".join([f"{key}: {value}" for key, value in answers.items()])

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
        title=title,
        description=description,
        color=color
    ).set_author(
        name=guild.name,
        icon_url=guild.icon.url if guild.icon else None
    ).set_thumbnail(
        url=interaction.user.avatar.url if interaction.user.avatar else None
    ).set_footer(
        text=guild_info.get("text", ""),
        icon_url=guild_info.get("icon_url", "")
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
            style=discord.ButtonStyle.link,
            emoji="🎫",
            url=ticket_channel.jump_url
        ))


class CloseTicketView(discord.ui.View):
    @discord.ui.button(
        label="Pin チケット", style=discord.ButtonStyle.green, custom_id="pin_ticket", emoji="📌"
    )
    async def pin_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # スタッフロールを取得
        staff_role_id = staff_roles.get(interaction.guild.id)
        staff_role = discord.utils.get(interaction.guild.roles, id=staff_role_id)

        # スタッフロールを持っていないユーザーはボタンを押せない
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "この操作を行う権限がありません。", ephemeral=True
            )
            return

        await interaction.channel.edit(name=f"📌{interaction.channel.name}")
        await interaction.response.send_message("チケットがピンされました。", ephemeral=True)

    @discord.ui.button(
        label="チケットを閉じる", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="❎"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "チケットを閉じますか？", view=ConfirmCloseView(), ephemeral=True
        )


class ConfirmCloseView(discord.ui.View):
    @discord.ui.button(label="はい", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        dm_message = dm_messages.get(interaction.guild.id, "")
        ticket_link = ticket_links.get(interaction.guild.id, "")
        if dm_message or ticket_link:
            embed = discord.Embed(
                title="📄チケットが閉じました",
                description=dm_message,
                color=discord.Color.red()
            ).set_author(
                name=interaction.guild.name,
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            ).add_field(
                name="作成者",
                value=f"{interaction.user.mention}\nID: {interaction.user.id}",
                inline=False
            ).add_field(
                name="作成日時",
                value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                inline=False
            ).set_thumbnail(
                url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            if ticket_link:
                embed.add_field(
                    name="チケットリンク",
                    value=f"[こちらをクリック]({ticket_link})",
                    inline=False
                )
            await interaction.user.send(embed=embed)
        await interaction.channel.delete()

    @discord.ui.button(label="いいえ", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("キャンセルしました。", ephemeral=True)


@bot.tree.command(name="ticket_button", description="チケット作成ボタンとスタッフロールを設定します。")
@app_commands.describe(
    emoji="ボタンに表示する絵文字", name="ボタンの名前", description="ボタンの説明", staff_role="通知するスタッフロール（@メンション）"
)
async def ticket_button_command(
    interaction: discord.Interaction, emoji: str, name: str, description: str, staff_role: discord.Role
):
    """
    サーバー内のカテゴリーを選択してチケットボタンを設定
    """
    categories = interaction.guild.categories
    category_options = [
        discord.SelectOption(label=category.name, value=str(category.id))
        for category in categories
    ]

    class CategorySelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(CategorySelect())

    class CategorySelect(discord.ui.Select):
        def __init__(self):
            super().__init__(
                placeholder="カテゴリーを選択してください...",
                options=category_options,
            )

        async def callback(self, interaction: discord.Interaction):
            category_id = int(self.values[0])  # 選択されたカテゴリーIDを取得
            if interaction.guild.id not in ticket_settings:
                ticket_settings[interaction.guild.id] = []

            # ボタン設定を追加
            ticket_settings[interaction.guild.id].append(
                {"category": category_id, "emoji": emoji, "name": name, "description": description}
            )

            # スタッフロールを保存
            staff_roles[interaction.guild.id] = staff_role.id

            await interaction.response.send_message(
                f"ボタン '{name}' (カテゴリー: {category_id}, 絵文字: {emoji}) とスタッフロール '{staff_role.name}' を追加しました。",
                ephemeral=True,
            )

    await interaction.response.send_message(
        "カテゴリーを選択してください：", view=CategorySelectView(), ephemeral=True
    )


@bot.tree.command(name="ticket_modal", description="チケットのタイトルと説明を設定します。")
async def ticket_modal_command(interaction: discord.Interaction):
    """
    チケットのタイトルと説明を設定するためのモーダルを表示
    """
    class TicketModal(discord.ui.Modal, title="チケット設定"):
        title_field = discord.ui.TextInput(
            label="チケットのタイトル",
            style=discord.TextStyle.short,
            placeholder="例: サポートチケット",
            required=True,
        )
        description_field = discord.ui.TextInput(
            label="チケットの説明",
            style=discord.TextStyle.paragraph,
            placeholder="例: サポートチームに連絡したい内容を書いてください。",
            required=False,
        )

        async def on_submit(self, interaction: discord.Interaction):
            # 設定内容を保存
            if interaction.guild.id not in ticket_titles:
                ticket_titles[interaction.guild.id] = {}
            ticket_titles[interaction.guild.id]["title"] = self.title_field.value
            ticket_titles[interaction.guild.id]["description"] = self.description_field.value

            await interaction.response.send_message(
                f"チケットのタイトルを '{self.title_field.value}' に、説明を設定しました。",
                ephemeral=True,
            )

    await interaction.response.send_modal(TicketModal())


@bot.tree.command(name="open_ticket_settings", description="チケットのEmbedカラー、タイトル、説明を設定します。")
@app_commands.describe(
    title="チケットのタイトル",
    description="チケットの説明",
    color="チケットのEmbedカラー（赤、青、黄色、緑から選択）"
)
async def open_ticket_settings_command(interaction: discord.Interaction, title: str, description: str, color: str):
    """
    チケットのEmbedカラー、タイトル、説明を設定
    """
    color_dict = {
        "赤": discord.Color.red(),
        "青": discord.Color.blue(),
        "黄色": discord.Color.gold(),
        "緑": discord.Color.green()
    }
    embed_color = color_dict.get(color, discord.Color.blue())

    ticket_titles[interaction.guild.id] = {"title": title, "description": description}
    ticket_colors[interaction.guild.id] = embed_color
    await interaction.response.send_message(
        "チケットの設定を保存しました。",
        ephemeral=True,
    )


@bot.tree.command(name="ticket_panel", description="チケットパネルを作成します。")
async def ticket_panel_command(interaction: discord.Interaction):
    """
    チケットパネルを作成
    """
    buttons = ticket_settings.get(interaction.guild.id, [])
    if not buttons:
        await interaction.response.send_message(
            "チケットのボタンが設定されていません！", ephemeral=True
        )
        return

    # パネルに表示する情報を取得
    title = "チケットサポート"
    description = "以下のボタンを押してチケットを開いてください。"

    guild_info = developed_info.get(interaction.guild.id, {})
    embed = create_ticket_embed(
        title=title, 
        description=description, 
        image_url=guild_info.get("image_url"), 
        thumbnail_url=guild_info.get("thumbnail_url"), 
        color=guild_info.get("color", discord.Color.blue()), 
        developed_text=guild_info.get("text"), 
        developed_icon_url=guild_info.get("icon_url")
    ).set_author(
        name=interaction.guild.name,
        icon_url=interaction.guild.icon.url if interaction.guild.icon else None
    )
    view = TicketView(buttons)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("チケットパネルを作成しました。", ephemeral=True)


@bot.tree.command(name="ticket_dm", description="チケットを開いた際にDMで送信する内容を設定します。")
async def ticket_dm_command(interaction: discord.Interaction):
    """
    チケットを開いた際にDMで送信する内容を設定するためのモーダルを表示
    """
    class DmModal(discord.ui.Modal, title="DMメッセージ設定"):
        message_field = discord.ui.TextInput(
            label="DMメッセージ",
            style=discord.TextStyle.paragraph,
            placeholder="例: チケットが開かれました。ご利用ありがとうございました。",
            required=True,
        )
        link_field = discord.ui.TextInput(
            label="チケットリンク",
            style=discord.TextStyle.short,
            placeholder="例: https://discord.com/channels/...",
            required=True,
        )

        async def on_submit(self, interaction: discord.Interaction):
            # 設定内容を保存
            dm_messages[interaction.guild.id] = self.message_field.value
            ticket_links[interaction.guild.id] = self.link_field.value

            await interaction.response.send_message(
                "DMメッセージとチケットリンクを設定しました。",
                ephemeral=True,
            )

    await interaction.response.send_modal(DmModal())


@bot.tree.command(name="ticket_questions", description="チケットに質問を設定します。")
@app_commands.describe(
    button_name="質問を設定するチケットボタンの名前",
    question_count="設定する質問の数"
)
async def ticket_questions_command(interaction: discord.Interaction, button_name: str, question_count: int):
    """
    チケットに質問を設定するためのモーダルを表示
    """
    if interaction.guild.id not in ticket_settings:
        await interaction.response.send_message(
            "まず /ticket_button コマンドでチケットボタンを設定してください。", ephemeral=True
        )
        return

    matching_button = None
    for button in ticket_settings[interaction.guild.id]:
        if button["name"] == button_name:
            matching_button = button
            break

    if not matching_button:
        await interaction.response.send_message(
            f"名前 '{button_name}' のチケットボタンが見つかりません。", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"{question_count}個の質問を設定します。以下のモーダルで質問内容を設定してください。", ephemeral=True
    )

    modal = QuestionContentsModal(question_count, matching_button["category"])
    await interaction.response.send_modal(modal)


class QuestionContentsModal(discord.ui.Modal):
    def __init__(self, question_count, category_id):
        super().__init__(title="質問内容の設定")
        self.question_count = question_count
        self.category_id = category_id
        self.questions = []
        for index in range(question_count):
            self.add_item(discord.ui.TextInput(
                label=f"質問 {index + 1}",
                style=discord.TextStyle.paragraph,
                placeholder="質問内容を入力してください。",
                required=True,
            ))

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in ticket_questions:
            ticket_questions[guild_id] = {}
        ticket_questions[guild_id][self.category_id] = {
            "questions": [item.value for item in self.children]
        }
        await interaction.response.send_message(
            "質問内容を設定しました。", ephemeral=True
        )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


bot.run("YOUR_BOT_TOKEN")