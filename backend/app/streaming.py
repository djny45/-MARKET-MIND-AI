"""Low-overhead in-process asynchronous event primitives; not a durable broker."""
import asyncio,time
from dataclasses import dataclass,field
@dataclass
class MarketEvent:
 channel:str
 payload:dict
 created_ns:int=field(default_factory=time.perf_counter_ns)
class EventBus:
 def __init__(self,queue_size=10000):
  self.queue=asyncio.Queue(maxsize=queue_size); self.dropped=0
 async def publish(self,event):
  try: self.queue.put_nowait(event)
  except asyncio.QueueFull: self.dropped+=1
 async def consume(self):
  while True:
   event=await self.queue.get()
   try: yield event
   finally: self.queue.task_done()
 def metrics(self):
  return {"queue_depth":self.queue.qsize(),"dropped_events":self.dropped,"clock":"process_monotonic","durability":"in_memory_only"}
def latency_budget():
 return {"microsecond_end_to_end_guarantee":False,
 "scope":"Some in-memory operations may reach microsecond scale after profiling; network-to-dashboard latency cannot be promised.",
 "optimizations":["async network I/O","bounded queues and backpressure","persistent connections when permitted","batching and vectorized analytics","monotonic stage timestamps","separate ingestion, compute and UI workloads"],
 "measure":["p50","p95","p99","max","queue depth","dropped events"],
 "execution":"Research only; no broker order routing."}
