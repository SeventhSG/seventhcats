import discord
from discord import app_commands
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import asyncio
import io
import os
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')  # Optional: for instant slash command sync in your server

# ── Cat registry ────────────────────────────────────────────────────────────────
cats = {
    "HappyCanteen": "https://meow.camera/viewer/#4258783365322591678",
    "Ms.Dress":     "https://meow.camera/viewer/#4154701567245307824",
    "Mr.Fresh":     "https://meow.camera/viewer/#5144313095337151915",
    "Mr.Long":      "https://meow.camera/viewer/#4303090694701059290",
    "Mr.Yap":       "https://meow.camera/viewer/#4908902089087167112",
    "Ms.Gucci":     "https://meow.camera/viewer/#4543591306641236417",
    "CoalBall":     "https://meow.camera/viewer/#4709667282046985918",
}

# Semaphore: only 1 screenshot job at a time (prevents browser pile-up on Pi)
screenshot_lock = asyncio.Semaphore(1)

# ── Bot setup ────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='s!', intents=intents)
tree = bot.tree  # shortcut for slash commands


# ── Selenium helpers ─────────────────────────────────────────────────────────────
def _build_driver() -> webdriver.Chrome:
    """Build a headless Chrome driver compatible with Pi 5 / Ubuntu ARM64."""
    options = Options()
    options.add_argument('--headless=new')       # new headless mode (Chrome 112+)
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')  # crucial on Pi (limited /dev/shm)
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1280,800')   # explicit size for consistent crops
    options.add_argument('--disable-software-rasterizer')

    # chromedriver path installed via apt on Ubuntu
    service = Service('/usr/bin/chromedriver')
    return webdriver.Chrome(service=service, options=options)


def _selenium_job(url: str, mode: str | None) -> tuple[bytes, bytes]:
    """
    Synchronous Selenium work — runs in a thread so it won't block the event loop.
    Returns (first_crop_bytes, second_crop_bytes).
    """
    driver = _build_driver()
    try:
        driver.get(url)

        # Click the camera angle button if requested
        if mode == "top":
            driver.execute_script("document.elementFromPoint(348, 526).click();")
        elif mode == "back":
            driver.execute_script("document.elementFromPoint(413, 526).click();")

        # Wait up to 25 s for the page to stabilise (better than a blind sleep)
        try:
            WebDriverWait(driver, 25).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass  # proceed anyway

        # Extra settle time for the live stream to render
        import time
        time.sleep(3)

        # ── First screenshot ─────────────────────────────────────────────────────
        raw1 = driver.get_screenshot_as_png()
        img1 = Image.open(io.BytesIO(raw1)).crop((236, 38, 799, 354))
        buf1 = io.BytesIO()
        img1.save(buf1, format="PNG")
        buf1.seek(0)

        time.sleep(1)

        # ── Second screenshot ────────────────────────────────────────────────────
        raw2 = driver.get_screenshot_as_png()
        img2 = Image.open(io.BytesIO(raw2)).crop((247, 370, 561, 456))
        buf2 = io.BytesIO()
        img2.save(buf2, format="PNG")
        buf2.seek(0)

        return buf1.read(), buf2.read()
    finally:
        driver.quit()


# ── Shared logic ─────────────────────────────────────────────────────────────────
async def _handle_photo(
    responder,          # callable that sends a message (works for both ctx and interaction)
    cat_name: str,
    mode: str | None,
):
    """Core logic shared by prefix and slash commands."""
    cat_name = cat_name.replace("_", " ").strip()

    if cat_name not in cats:
        await responder(
            f"❌ Cat **{cat_name}** not found. "
            f"Available cats: {', '.join(f'`{c}`' for c in cats)}"
        )
        return

    url = cats[cat_name]

    if mode and mode not in ("top", "back"):
        mode = None

    await responder(f"📸 Taking photo of **{cat_name}**… (this takes ~25 s)")

    async with screenshot_lock:
        try:
            crop1, crop2 = await asyncio.to_thread(_selenium_job, url, mode)
        except Exception as e:
            await responder(f"⚠️ Screenshot failed: `{e}`")
            return

    await responder(
        files=[
            discord.File(io.BytesIO(crop1), filename=f"{cat_name}_camera.png"),
            discord.File(io.BytesIO(crop2), filename=f"{cat_name}_info.png"),
        ]
    )


# ── Events ───────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # Sync slash commands
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print(f"Slash commands synced to guild {GUILD_ID}")
    else:
        await tree.sync()
        print("Slash commands synced globally (may take up to 1 hour)")

    print(f"✅ Logged in as {bot.user} (id: {bot.user.id})")


# ── Prefix commands (legacy s! prefix) ───────────────────────────────────────────
@bot.command(name="photo")
async def prefix_photo(ctx, cat_name: str, mode: str = None):
    """s!photo <cat_name> [top|back]"""
    await _handle_photo(ctx.send, cat_name, mode)


@bot.command(name="cats")
async def prefix_cats(ctx):
    """s!cats — list all available cats"""
    lines = "\n".join(f"• `{name}`" for name in cats)
    await ctx.send(f"🐱 **Available cats:**\n{lines}")


# ── Slash commands ────────────────────────────────────────────────────────────────
cat_choices = [app_commands.Choice(name=name, value=name) for name in cats]
mode_choices = [
    app_commands.Choice(name="Default", value="default"),
    app_commands.Choice(name="Top view", value="top"),
    app_commands.Choice(name="Back view", value="back"),
]


@tree.command(name="photo", description="Take a photo of a cat from the live camera")
@app_commands.describe(
    cat="Which cat to photograph",
    view="Camera angle (optional)"
)
@app_commands.choices(cat=cat_choices, view=mode_choices)
async def slash_photo(
    interaction: discord.Interaction,
    cat: app_commands.Choice[str],
    view: app_commands.Choice[str] = None,
):
    await interaction.response.defer(thinking=True)  # prevents 3-s timeout

    mode = view.value if view and view.value != "default" else None

    async def responder(**kwargs):
        # After defer, use followup
        if "files" in kwargs:
            await interaction.followup.send(**kwargs)
        else:
            await interaction.followup.send(kwargs.get("content", ""), **{k: v for k, v in kwargs.items() if k != "content"})

    # Wrap string-only calls too
    async def simple_responder(msg=None, **kwargs):
        if isinstance(msg, str):
            await interaction.followup.send(msg)
        else:
            await interaction.followup.send(**kwargs)

    await _handle_photo(simple_responder, cat.value, mode)


@tree.command(name="cats", description="List all available cats")
async def slash_cats(interaction: discord.Interaction):
    lines = "\n".join(f"• `{name}`" for name in cats)
    await interaction.response.send_message(f"🐱 **Available cats:**\n{lines}")


# ── Run ───────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in .env file!")
    bot.run(TOKEN)
