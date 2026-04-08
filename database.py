import sqlite3

# 初始化数据库：如果文件不存在，就建一个
def init_db():
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    # 建立表格：邀请码 (code), 邮箱 (email), Discord ID (discord_id)
    c.execute('''CREATE TABLE IF NOT EXISTS invites 
                 (invite_code TEXT PRIMARY KEY, email TEXT, discord_id TEXT)''')
    conn.commit()
    conn.close()

# 存入邀请码和邮箱
def save_invite(code, email):
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO invites (invite_code, email) VALUES (?, ?)", (code, email))
    conn.commit()
    conn.close()

# 根据邀请码查邮箱
def get_email_by_code(code):
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    c.execute("SELECT email FROM invites WHERE invite_code = ?", (code,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None