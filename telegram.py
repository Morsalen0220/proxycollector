import asyncio, aiohttp, re, json, os

# কনফিগারেশন - গিটহাব সিক্রেটস থেকে নেবে
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# গ্লোবাল কন্ট্রোল ভ্যারিয়েবল
is_running = True
total_checked = 0
winner_buffer = []

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
                            country, p_type = await get_proxy_details(session, proxy)
                            winner_buffer.append(f"✅ `{proxy}` | 🌍 {country} | ⚡ {p_type}")
                            
                            if len(winner_buffer) >= 10:
                                msg = "🚀 **Elite Dual-Engine Batch!**\n\n" + "\n".join(winner_buffer[:10])
                                await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                                 json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                                winner_buffer = winner_buffer[10:]
        except: pass

async def find_new_sources(session):
    """গিটহাব থেকে ডাইনামিক এবং নতুন প্রক্সি সোর্স খুঁজে বের করা"""
    search_url = "https://api.github.com/search/repositories?q=proxy-list+stars:>5&sort=updated"
    try:
        async with session.get(search_url) as res:
            items = (await res.json()).get('items', [])
            return list(set([f"https://raw.githubusercontent.com/{r['owner']['login']}/{r['name']}/master/http.txt" for r in items]))
    except: return []

async def get_commands():
    """টেলিগ্রাম কমান্ড হ্যান্ডলার"""
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
                        msg = update.get("message", {}).get("text", "").lower()
                        if msg == "/start":
                            is_running = True
                            await session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=▶️ Engine STARTED!")
                        elif msg == "/stop":
                            is_running = False
                            await session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🛑 Engine STOPPED!")
                        elif msg == "/status":
                            await session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text=📊 Checked: {total_checked}")
            except: pass
            await asyncio.sleep(2)

async def worker():
    """মেইন ইঞ্জিন: গিটহাব সোর্স এবং এপিআই সোর্স চেক করবে"""
    global is_running
    async with aiohttp.ClientSession() as session:
        while True:
            if is_running:
                # গিটহাব থেকে নতুন সোর্স এবং এপিআই থেকে ডাটা নেওয়া
                github_sources = await find_new_sources(session)
                all_p = []
                for url in github_sources[:10]:
                    try:
                        async with session.get(url, timeout=10) as r:
                            all_p.extend(re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", await r.text()))
                    except: pass
                
                api_url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
                async with session.get(api_url) as r:
                    all_p.extend(re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", await r.text()))
                
                all_p = list(set(all_p))
                sem = asyncio.Semaphore(50)
                tasks = [asyncio.create_task(check_and_post(session, sem, p)) for p in all_p[:800]]
                await asyncio.gather(*tasks)
            await asyncio.sleep(5)

async def main():
    print("[*] Morapple-X Ultimate Edition Online.")
    await asyncio.gather(get_commands(), worker())

if __name__ == "__main__":
    asyncio.run(main())