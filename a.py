import discord
from discord import app_commands
from discord.ext import commands

TOKEN = "YOU_ARE_TOKEN"  # BOTのトークンを設定

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("Slash commands synced globally.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="embed", description="指定したメッセージにURLを埋め込みます。")
@app_commands.describe(text="表示するテキスト", url="埋め込むURL")
async def embed(interaction: discord.Interaction, text: str, url: str):
    # URLの簡単なバリデーションチェック
    if not url.startswith("http://") and not url.startswith("https://"):
        await interaction.response.send_message("無効なURLです。`http://` または `https://` から始まるURLを指定してください。", ephemeral=True)
        return
    
    embed = discord.Embed(description=f"[{text}]({url})", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
