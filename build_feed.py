# -*- coding: utf-8 -*-
"""
Costruisce feed.xml (RSS 2.0 + tag iTunes/Podcasting 2.0) da podcast.json ed
episodes.json. Include SOLO gli episodi con release_at <= adesso: e' cosi' che
funziona la pubblicazione programmata. Gira su GitHub Actions ogni ora.
"""
import html
import json
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

show = json.load(open("podcast.json", encoding="utf-8"))
episodes = json.load(open("episodes.json", encoding="utf-8"))
now = datetime.now(timezone.utc)


def released(ep):
    return datetime.fromisoformat(ep["release_at"]) <= now


def notes_html(text):
    """show notes testuali -> HTML semplice con link cliccabili."""
    out = []
    for block in text.strip().split("\n\n"):
        lines = [html.escape(l.strip()) for l in block.split("\n")]
        lines = [re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', l) for l in lines]
        out.append("<p>" + "<br/>".join(lines) + "</p>")
    return "".join(out)


def body(ep):
    """show notes senza la prima riga se e' il titolo (le app lo mostrano gia')."""
    text = ep["show_notes"].strip()
    first, _, rest = text.partition("\n")
    return rest.strip() if first.strip() == ep["title"].strip() else text


def hms(seconds):
    s = int(round(seconds))
    return "{:02d}:{:02d}:{:02d}".format(s // 3600, s % 3600 // 60, s % 60)


def cdata(s):
    return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"


eps = sorted((e for e in episodes if released(e)),
             key=lambda e: e["release_at"], reverse=True)

cats = []
for c in show["categories"]:
    if len(c) == 2:
        cats.append('<itunes:category text="{}"><itunes:category text="{}"/></itunes:category>'
                    .format(escape(c[0]), escape(c[1])))
    else:
        cats.append('<itunes:category text="{}"/>'.format(escape(c[0])))

items = []
for e in eps:
    pub = format_datetime(datetime.fromisoformat(e["release_at"]).astimezone(timezone.utc))
    items.append("""    <item>
      <title>{title}</title>
      <description>{desc}</description>
      <content:encoded>{desc}</content:encoded>
      <itunes:summary>{summary}</itunes:summary>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub}</pubDate>
      <enclosure url="{url}" length="{length}" type="audio/mpeg"/>
      <itunes:duration>{dur}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>{explicit}</itunes:explicit>
    </item>""".format(
        title=escape(e["title"]),
        desc=cdata(notes_html(body(e))),
        summary=escape(body(e)[:3900]),
        guid=escape(e["guid"]),
        pub=pub,
        url=escape(e["audio_url"]),
        length=int(e["audio_bytes"]),
        dur=hms(e["duration_s"]),
        explicit="true" if show["explicit"] else "false",
    ))

feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>{title}</title>
    <link>{website}</link>
    <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>
    <language>{language}</language>
    <copyright>{copyright}</copyright>
    <description>{description}</description>
    <itunes:subtitle>{subtitle}</itunes:subtitle>
    <itunes:summary>{description}</itunes:summary>
    <itunes:author>{author}</itunes:author>
    <itunes:owner>
      <itunes:name>{owner_name}</itunes:name>
      <itunes:email>{owner_email}</itunes:email>
    </itunes:owner>
    <itunes:image href="{cover_url}"/>
    <image><url>{cover_url}</url><title>{title}</title><link>{website}</link></image>
    {categories}
    <itunes:explicit>{explicit}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <podcast:locked>yes</podcast:locked>
    <lastBuildDate>{now}</lastBuildDate>
{items}
  </channel>
</rss>
""".format(
    title=escape(show["title"]), website=escape(show["website"]),
    feed_url=escape(show["feed_url"]), language=show["language"],
    copyright=escape(show["copyright"]), description=escape(show["description"]),
    subtitle=escape(show["subtitle"]), author=escape(show["author"]),
    owner_name=escape(show["owner_name"]), owner_email=escape(show["owner_email"]),
    cover_url=escape(show["cover_url"]), categories="\n    ".join(cats),
    explicit="true" if show["explicit"] else "false",
    now=format_datetime(now), items="\n".join(items),
)

# Confronto con il feed ATTUALMENTE online: si ripubblica solo se cambia qualcosa
old = ""
try:
    import urllib.request
    with urllib.request.urlopen(show["feed_url"] + "?nocache=" + str(int(now.timestamp())),
                                timeout=20) as r:
        old = r.read().decode("utf-8")
except Exception as e:
    print("feed online non leggibile ({}): pubblico comunque".format(e))

# lastBuildDate cambia sempre: confronto senza
strip = lambda s: re.sub(r"<lastBuildDate>.*?</lastBuildDate>", "", s)
changed = strip(old) != strip(feed)
open("feed.xml", "w", encoding="utf-8").write(feed)
print("{}: {} episodi pubblicati".format("CAMBIATO" if changed else "nessun cambiamento", len(eps)))

import os
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("changed={}\n".format("true" if changed else "false"))
