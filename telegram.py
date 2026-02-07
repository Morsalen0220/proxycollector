import asyncio, aiohttp, re, json, os

# কনফিগারেশন - গিটহাব সিক্রেটস থেকে নেবে
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# গ্লোবাল কন্ট্রোল ভ্যারিয়েবল
is_running = True
total_checked = 0
winner_buffer = []

async def get_commands():
    """টেলিগ্রাম থেকে রিমোট কমান্ড শোনা (/start, /stop, /status)"""
    global is_running, total_checked
    offset = 0
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"{url}?offset={offset}", timeout=10) as r:
                    data = await r.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" not in update or "text" not in update["message"]: continue
                        
                        msg = update["message"]["text"].lower()
                        if msg == "/start":
                            is_running = True
                            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                             json={"chat_id": CHAT_ID, "text": "🚀 **Engine STARTED!**\nDual-Checking Facebook & Google..."})
                        elif msg == "/stop":
                            is_running = False
                            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                             json={"chat_id": CHAT_ID, "text": "🛑 **Engine STOPPED!**"})
                        elif msg == "/status":
                            status_text = f"📊 **Status:** {'✅ Active' if is_running else '❌ Stopped'}\n- Checked: {total_checked}"
                            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                             json={"chat_id": CHAT_ID, "text": status_text})
            except: pass
            await asyncio.sleep(2)

async def check_and_post(session, sem, proxy):
    """ডুয়াল ভ্যালিডেশন: গুগল এবং ফেসবুক"""
    global total_checked, winner_buffer, is_running
    if not is_running: return 
    async with sem:
        try:
            # ১. গুগল চেক
            async with session.get("https://www.google.com", proxy=f"http://{proxy}", timeout=10) as g_res:
                if g_res.status == 200:
                    # ২. ফেসবুক চেক
                    async with session.get("https://mbasic.facebook.com", proxy=f"http://{proxy}", timeout=10, ssl=False) as fb_res:
                        total_checked += 1
                        if fb_res.status == 200:
                            winner_buffer.append(f"✅ `{proxy}` | ⚡ Dual-Pass")
                            if len(winner_buffer) >= 10:
                                msg = "🚀 **Elite Dual-Engine Batch!**\n\n" + "\n".join(winner_buffer[:10])
                                await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                                 json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                                winner_buffer = winner_buffer[10:]
        except: pass

async def worker():
    """আনলিমিটেড সোর্স থেকে প্রক্সি খুঁজে বের করা"""
    global is_running
    conn = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=conn) as session:
        while True:
            if is_running:
                # ডাইনামিক গিটহাব সোর্স
                source_url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all"
                async with session.get(source_url) as r:
                    all_p = re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", await r.text())
                
                sem = asyncio.Semaphore(50)
                tasks = [asyncio.create_task(check_and_post(session, sem, p)) for p in all_p[:1000]]
                await asyncio.gather(*tasks)
            await asyncio.sleep(5)

async def main():
    print("[*] Morapple-X Control Center Online.")
    await asyncio.gather(get_commands(), worker())

if __name__ == "__main__":
    asyncio.run(main())