import discord
import database  # 导入你刚刚新建的数据库文件
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
intents.message_content = True  # <--- 新增这一行，允许机器人读取消息内容
# 如果你之前在网页端也开了 Presence Intent，建议也加上下面这行：
# intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)
# 确保程序启动时，数据库表已经建好
database.init_db()

# 内存缓存
invite_cache = {}
join_lock = asyncio.Lock()

# --- 网页服务器：让 Zapier 能主动找机器人要链接 ---
app = Flask('')

@app.route('/create_invite', methods=['POST'])
def create_invite_api():
    # 1. 获取请求里的数据
    data = request.json
    email = data.get('email', 'unknown')
    
    # 2. 调用 Discord 逻辑生成链接 (保留你原来的这两行)
    future = asyncio.run_coroutine_threadsafe(generate_invite_logic(email), bot.loop)
    invite_url = future.result() # 这行拿到了类似 https://discord.gg/ABCDEFG 的链接
    
    # --- 核心新增部分：保存到数据库 ---
    # 提取邀请码：把链接按 '/' 分割，取最后一段（比如 ABCDEFG）
    invite_code = invite_url.split('/')[-1]
    
    # 调用 database.py 里的函数存起来
    database.save_invite(invite_code, email)
    # --- 新增结束 ---

    # 3. 返回结果给 Zapier
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
            # 1. 去数据库里查这个邀请码是谁的
            target_email = database.get_email_by_code(used_code)
            
            if target_email:
                print(f"匹配成功！成员 {member.name} 对应邮箱: {target_email}")
                # 2. 发送给 Zapier，这次带上 email
                requests.post(ZAPIER_WEBHOOK_URL, json={
                    "invite_code": used_code,
                    "email": target_email,
                    "discord_id": str(member.id),
                    "discord_name": str(member)
                })
            else:
                print(f"检测到邀请码 {used_code}，但在数据库中没找到对应的邮箱。")

        # 3. 更新缓存，为下一个人加入做准备（这行就是你原来的第 90 行）
        invite_cache[guild.id] = new_invites

# 启动网页服务器
Thread(target=run).start()
bot.run(TOKEN)