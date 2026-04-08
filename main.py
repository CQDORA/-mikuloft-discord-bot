import discord
import os
import asyncio
import requests
from flask import Flask, request, jsonify # 增加一个小网页服务器，方便 Zapier 调取
from threading import Thread
from discord.ext import commands

# 1. 配置信息
TOKEN = os.getenv("DISCORD_TOKEN")
# 这里的 URL 填入你 Zapier "Catch Hook" 的地址
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/27124366/u7mjszn/"

intents = discord.Intents.default()
intents.members = True 
intents.invites = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 内存缓存
invite_cache = {}
join_lock = asyncio.Lock()

# --- 网页服务器：让 Zapier 能主动找机器人要链接 ---
app = Flask('')

@app.route('/create_invite', methods=['POST'])
def create_invite_api():
    # 这个接口供 Zapier 调用
    data = request.json
    email = data.get('email', 'unknown')
    
    # 在 Discord 中生成链接
    # 注意：这里需要根据你的服务器 ID 调整，后续我们可以细调
    future = asyncio.run_coroutine_threadsafe(generate_invite_logic(email), bot.loop)
    invite_url = future.result()
    
    return jsonify({"invite_url": invite_url})

async def generate_invite_logic(email):
    # 找到第一个服务器的第一个频道生成链接
    guild = bot.guilds[0]
    channel = guild.text_channels[0]
    invite = await channel.create_invite(max_uses=1, max_age=0, unique=True, reason=f"Email: {email}")
    return invite.url

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- Discord 机器人：监测入群 ---
@bot.event
async def on_ready():
    print(f"机器人 {bot.user.name} 已上线")
    for guild in bot.guilds:
        invite_cache[guild.id] = {i.code: i.uses for i in await guild.invites()}

@bot.event
async def on_member_join(member):
    async with join_lock:
        guild = member.guild
        old_invites = invite_cache.get(guild.id, {})
        new_invites = {i.code: i.uses for i in await guild.invites()}
        
        used_code = None
        for code, old_uses in old_invites.items():
            if code not in new_invites or new_invites[code] > old_uses:
                used_code = code
                break
        
        if used_code:
            # 发给 Zapier 匹配 Excel
            requests.post(ZAPIER_WEBHOOK_URL, json={
                "invite_code": used_code,
                "discord_id": str(member.id),
                "discord_name": str(member)
            })
        invite_cache[guild.id] = new_invites

# 启动网页服务器
Thread(target=run).start()
bot.run(TOKEN)