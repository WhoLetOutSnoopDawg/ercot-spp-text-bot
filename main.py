import os, requests, datetime
from bs4 import BeautifulSoup
from twilio.rest import Client

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
SUBSCRIBERS_FILE = "subscribers.txt"

def get_today_url():
    today = datetime.date.today().strftime("%Y%m%d")
    return f"https://www.ercot.com/content/cdr/html/{today}_real_time_spp.html"

def fetch_spp():
    url = get_today_url()
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "realTimeSPPTable"})
    headers = [th.text.strip() for th in table.find_all("th")]
    zones = headers[1:]
    data = {z: [] for z in zones}
    for row in table.find_all("tr")[1:]:
        cols = [td.text.strip() for td in row.find_all("td")]
        if len(cols) != len(headers):
            continue
        try:
            t = datetime.datetime.strptime(cols[0], "%H:%M").time()
        except:
            continue
        if datetime.time(6,15) <= t <= datetime.time(22,0):
            for z, val in zip(zones, cols[1:]):
                try: data[z].append(float(val))
                except: pass
    return data

def format_message(data):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    lines = [f"ERCOT RT: {today_str}"]
    zone_map = {
        "HB_SOUTH":"SOUTH","HB_HOUSTON":"HOUSTON","HB_BUSAVG":"BUSAVG",
        "HB_HUBAVG":"HUBAVG","HB_NORTH":"NORTH","HB_PAN":"PAN","HB_WEST":"WEST"
    }
    all_vals = []
    for src, nicename in zone_map.items():
        vals = data.get(src, [])
        if vals:
            avg = round(sum(vals)/len(vals), 2)
            lines.append(f"{nicename:<7} |  Onpk ${avg:.2f}")
            all_vals += vals
        else:
            lines.append(f"{nicename:<7} |  NoData")
    if all_vals:
        overall = round(sum(all_vals)/len(all_vals), 2)
        lines += ["", f"Average from 0615 to 2200: ${overall:.2f}"]
    else:
        lines += ["", "⚠️ No data; likely a scrape error."]
    return "\n".join(lines)

def send_sms(body, to_number):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(body=body, from_=TWILIO_FROM, to=to_number)

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    return set(line.strip() for line in open(SUBSCRIBERS_FILE) if line.strip())

def main():
    subs = load_subscribers()
    try:
        data = fetch_spp()
        msg = format_message(data)
    except Exception:
        msg = (f"Sorry information was unable to be displayed, contact developer if persist, "
               f"if urgent click link to see ERCOT data: {get_today_url()}")
    for num in subs:
        send_sms(msg, num)

if __name__ == "__main__":
    main()
