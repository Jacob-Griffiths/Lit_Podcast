import asyncio, json, os, glob, subprocess, html, datetime, email.utils
import edge_tts

BASE = os.environ["PAGES_BASE_URL"].rstrip("/")
VOICES = {"Alex": "en-US-GuyNeural", "Sam": "en-US-AriaNeural"}


async def synth(script_path):
    d = os.path.dirname(script_path)
    out = os.path.join(d, "episode.mp3")
    if os.path.exists(out):
        return
    ep = json.load(open(script_path))
    segs = []
    for i, t in enumerate(ep["turns"]):
        p = os.path.join(d, "seg_%03d.mp3" % i)
        voice = VOICES.get(t.get("speaker"), VOICES["Alex"])
        for attempt in range(3):
            try:
                await edge_tts.Communicate(t["text"], voice).save(p)
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(5)
        segs.append(p)
    lst = os.path.join(d, "list.txt")
    with open(lst, "w") as f:
        for p in segs:
            f.write("file '" + os.path.basename(p) + "'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:a", "libmp3lame", "-b:a", "96k", out], check=True)
    for p in segs + [lst]:
        os.remove(p)


def build_rss():
    items = []
    for sp in sorted(glob.glob("episodes/*/script.json"), reverse=True):
        d = os.path.dirname(sp)
        mp3 = os.path.join(d, "episode.mp3")
        if not os.path.exists(mp3):
            continue
        ep = json.load(open(sp))
        dt = datetime.datetime.strptime(ep["date"], "%Y-%m-%d").replace(hour=6, tzinfo=datetime.timezone.utc)
        links = "".join('<li><a href="%s">%s</a> (%s)</li>' % (p["pubmedUrl"], html.escape(p["title"]), html.escape(p.get("journal", ""))) for p in ep["papers"])
        items.append(
            "<item><title>%s</title><guid isPermaLink=\"false\">%s</guid><pubDate>%s</pubDate>"
            "<enclosure url=\"%s/%s\" length=\"%d\" type=\"audio/mpeg\"/>"
            "<description><![CDATA[<ul>%s</ul>]]></description></item>"
            % (html.escape(ep["title"]), ep["date"], email.utils.format_datetime(dt),
               BASE, mp3, os.path.getsize(mp3), links))
    rss = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>'
           '<title>TRIM71 &amp; Kidney Organoid Weekly</title><link>%s/</link>'
           '<description>Weekly AI-curated literature podcast with Alex and Sam.</description>'
           '<language>en-us</language><itunes:author>Alex &amp; Sam</itunes:author>'
           '<itunes:explicit>false</itunes:explicit>%s</channel></rss>' % (BASE, "".join(items)))
    open("rss.xml", "w").write(rss)


async def main():
    for sp in sorted(glob.glob("episodes/*/script.json")):
        await synth(sp)
    build_rss()


asyncio.run(main())
