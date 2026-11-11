"""Configurable RSS news metadata ingestion. Does not mirror full articles."""
import asyncio,hashlib,time
from email.utils import parsedate_to_datetime
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
DEFAULT_FEEDS={
 "SEC Press Releases":"https://www.sec.gov/news/pressreleases.rss",
 "ECB Press Releases":"https://www.ecb.europa.eu/rss/press.html",
 "Federal Reserve Press Releases":"https://www.federalreserve.gov/feeds/press_all.xml",
}
def _parse(raw,source,url):
 root=ET.fromstring(raw); items=[]
 for item in root.findall(".//item"):
  title=(item.findtext("title") or "").strip(); link=(item.findtext("link") or "").strip()
  if not title or not link: continue
  date=(item.findtext("pubDate") or "").strip()
  try: published=parsedate_to_datetime(date).isoformat() if date else None
  except (TypeError,ValueError): published=None
  key=hashlib.sha256((source+"|"+link).encode()).hexdigest()
  items.append({"id":key,"source":source,"feed_url":url,"title":title,"url":link,
   "published_at":published,"summary":(item.findtext("description") or "")[:600],
   "ingested_at":time.time(),"content_policy":"metadata_and_short_excerpt"})
 return items
async def fetch_feed(source,url,timeout=8):
 def fetch():
  req=Request(url,headers={"User-Agent":"MARKET-MIND-AI research aggregator; configure contact details"})
  with urlopen(req,timeout=timeout) as response:
   if response.status!=200: raise RuntimeError(f"HTTP {response.status}")
   return _parse(response.read(2_000_000),source,url)
 return await asyncio.to_thread(fetch)
async def ingest_news(feeds=None,concurrency=4):
 configured=feeds or DEFAULT_FEEDS; sem=asyncio.Semaphore(max(1,min(concurrency,16)))
 async def run(name,url):
  async with sem:
   try: return await fetch_feed(name,url)
   except Exception as exc:
    # Keep network and server internals out of public API error payloads.
    return [{"source":name,"feed_url":url,"error":"Feed fetch failed",
             "error_type":type(exc).__name__}]
 batches=await asyncio.gather(*(run(n,u) for n,u in configured.items()))
 unique={x.get("id",str(x)):x for batch in batches for x in batch}
 return {"items":list(unique.values()),"sources":len(configured),"count":len(unique),
  "note":"Verify feed availability, publisher terms, copyright and reuse rights before production."}
