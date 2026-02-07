import asyncio, aiohttp, re, json

# টেলিগ্রাম কনফিগ
BOT_TOKEN = "8417109379:AAF2janQrpNHfRIXAPUEzoxTaTV2MLG4c7U"
CHAT_ID = "5588234368"

# গ্লোবাল কন্ট্রোল ভ্যারিয়েবল
is_running = False
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
                            if not is_running:
                                is_running = True
                                print("[!] System STARTED via Telegram")
                                await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                                 json={"chat_id": CHAT_ID, "text": "🚀 **Morapple-X: Engine STARTED!**\nHunting for fresh proxies..."})
                        
                        elif msg == "/stop":
                            is_running = False
                            print("[!] System STOPPED via Telegram")
                            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                             json={"chat_id": CHAT_ID, "text": "🛑 **Morapple-X: Engine STOPPED!**"})
                        
                        elif msg == "/status":
                            status_text = f"📊 **Current Status:**\n- Running: {'✅ Active' if is_running else '❌ Stopped'}\n- Total Checked: {total_checked}\n- Queue: {len(winner_buffer)}/10"
                            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                             json={"chat_id": CHAT_ID, "text": status_text})
            except: pass
            await asyncio.sleep(2) # কমান্ড চেক করার ফ্রিকোয়েন্সি

async def get_proxy_details(session, proxy):
    """আইপি-র দেশ এবং টাইপ বের করা"""
    try:
        async with session.get(f"http://ip-api.com/json/{proxy.split(':')[0]}", timeout=5) as geo:
            data = await geo.json()
            country = data.get('country', 'Unknown')
            port = proxy.split(':')[-1]
            p_type = "SOCKS5/4" if port in ['1080', '1081', '4145'] else "HTTP/S"
            return country, p_type
    except: return "Unknown", "HTTP/S"

async def send_batch_to_telegram(session):
    """১০টি লাইভ প্রক্সি একসাথে টেলিগ্রামে পাঠানো"""
    global winner_buffer
    if len(winner_buffer) >= 10:
        msg_lines = [f"✅ `{p}` | 🌍 {c} | ⚡ {t}" for p, c, t in winner_buffer[:10]]
        msg = f"🚀 **Premium Proxy Batch!**\n\n" + "\n".join(msg_lines)
        try:
            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            winner_buffer = winner_buffer[10:]
            print("[+] Batch sent to Telegram!")
        except: pass

async def check_and_post(session, sem, proxy):
    """প্রক্সি ভ্যালিডেশন লজিক"""
    global total_checked, is_running
    if not is_running: return 
    async with sem:
        try:
            # ফেসবুক দিয়ে চেক করা
            async with session.get("https://mbasic.facebook.com", proxy=f"http://{proxy}", timeout=15, ssl=False) as res:
                total_checked += 1
                if res.status == 200:
                    print(f"[*] WINNER: {proxy}")
                    country, p_type = await get_proxy_details(session, proxy)
                    winner_buffer.append((proxy, country, p_type))
                    if len(winner_buffer) >= 10:
                        await send_batch_to_telegram(session)
        except: pass

async def find_new_sources(session):
    """গিটহাব থেকে ডাইনামিক সোর্স খুঁজে বের করা"""
    search_url = "https://api.github.com/search/repositories?q=proxy-list+stars:>10&sort=updated"
    try:
        async with session.get(search_url) as res:
            items = (await res.json()).get('items', [])
            return list(set([f"https://raw.githubusercontent.com/{r['owner']['login']}/{r['name']}/master/http.txt" for r in items]))
    except: return []

async def worker():
    """মেইন ইঞ্জিন লুপ"""
    global is_running
    # কানেকশন লিমিট ৫০ করা হলো যাতে Error 10054 না আসে
    conn = aiohttp.TCPConnector(limit=50, limit_per_host=5)
    async with aiohttp.ClientSession(connector=conn) as session:
        while True:
            if is_running:
                sources = await find_new_sources(session)
                all_p = []
                for url in sources:
                    if not is_running: break
                    try:
                        async with session.get(url, timeout=10) as r:
                            all_p.extend(re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", await r.text()))
                    except: pass
                
                all_p = list(set(all_p))
                print(f"[!] Scraped {len(all_p)} proxies. Testing starts...")
                
                sem = asyncio.Semaphore(50) # সেমাফোর ৫০ রাখা হয়েছে স্ট্যাবিলিটির জন্য
                tasks = []
                for p in all_p:
                    if not is_running: break
                    # create_task ব্যবহার করা হয়েছে যাতে কমান্ড হ্যান্ডলার জ্যাম না হয়
                    tasks.append(asyncio.create_task(check_and_post(session, sem, p)))
                    await asyncio.sleep(0.02) # ছোট গ্যাপ যাতে লুপ কমান্ড শুনতে পায়
                
                if tasks: await asyncio.gather(*tasks)
            
            await asyncio.sleep(5) # ইঞ্জিন পজ থাকলে ৫ সেকেন্ড পর পর চেক করবে

async def main():
    print("[*] Morapple-X Control Center Online. Waiting for commands...")
    # কমান্ড লিসেনার এবং প্রক্সি ওয়ার্কার একসাথে চলবে
    await asyncio.gather(get_commands(), worker())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Powering down Morapple-X...")