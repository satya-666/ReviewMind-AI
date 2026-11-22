"""Optional SerpApi India Shopping retrieval; never fetch model-supplied URLs."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import ipaddress,json,logging,re,threading,time,urllib.parse,urllib.request,urllib.error

LOG=logging.getLogger(__name__)

def public_url(value):
    if not isinstance(value,str) or len(value)>2000:return None
    try:
        p=urllib.parse.urlsplit(value)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in {None,443}:return None
        host=p.hostname.lower()
        if '.' not in host or host.endswith(('.local','.internal','.localhost')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:pass
        return urllib.parse.quote(value,safe=":/?#[]@!$&'()*+,;=%")
    except ValueError:return None

def budget_from(messages):
    budget=None
    for text in messages:
        for m in re.finditer(r'(?:under|below|budget(?:\s+is)?|up to|₹|INR|Rs\.?)\s*(?:₹|INR|Rs\.?)?\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh)?',text,re.I):
            try:
                value=Decimal(m[1].replace(',',''))*{'k':1000,'thousand':1000,'lakh':100000,None:1}[m[2].lower() if m[2] else None]
                if 0<value<=10000000:budget=float(value)
            except InvalidOperation:pass
    return budget

def brand_from(messages):
    brand=None
    for text in messages:
        matches=list(re.finditer(r'\b(?:only|prefer|preferred brand(?: is)?|brand is)\s+([A-Za-z][A-Za-z0-9-]{1,40})',text,re.I))
        if matches:brand=matches[-1][1]
    return brand

class ProductData:
    def __init__(self,key=''):
        self.key=key;self.lock=threading.Lock();self.calls=[]
        from backend.app.chat import NoRedirect
        self.opener=urllib.request.build_opener(NoRedirect())
    @property
    def configured(self):return bool(self.key)
    def lookup(self,intent,messages):
        return {'available':False,'configured':self.configured,'status':'not_searched' if self.configured else 'not_configured','sources':[],'products':[],
          'limitation':'Use product tools for current data if configured. Otherwise no verified catalogue is connected; give general guidance without inventing products, prices, ratings or availability.'}
    def search(self,query,budget=None,brand=None):
        result=self.lookup('',[])
        if not self.configured:return dict(result,status='not_configured')
        if not isinstance(query,str) or not 1<=len(query.strip())<=300 or re.search(r'https?://|api.?key|@',query,re.I):return dict(result,status='invalid_query')
        with self.lock:
            now=time.monotonic();self.calls=[t for t in self.calls if now-t<3600]
            if len(self.calls)>=40:return dict(result,status='rate_limited')
            self.calls.append(now)
        params={'engine':'google_shopping','q':query,'gl':'in','hl':'en','google_domain':'google.co.in','api_key':self.key,
          'json_restrictor':'error,shopping_results[0:40].{title,product_id,product_link,link,price,extensions,rating,reviews,source}'}
        if budget:params['tbs']='mr:1,price:1,ppr_max:'+str(budget)
        try:
            request=urllib.request.Request('https://serpapi.com/search.json?'+urllib.parse.urlencode(params))
            with self.opener.open(request,timeout=12) as response:raw=response.read(262145)
            if len(raw)>262144:raise ValueError()
            data=json.loads(raw)
            if data.get('error'):return dict(result,status='provider_error')
            rows=data.get('shopping_results',[])
            if not isinstance(rows,list):raise ValueError()
        except urllib.error.HTTPError as error:
            LOG.warning('Product search failed (http=%s)',error.code)
            return dict(result,status='quota_exhausted' if error.code==429 else 'authentication_failed' if error.code in {401,403} else 'unavailable')
        except TimeoutError:
            LOG.warning('Product search timed out')
            return dict(result,status='timeout')
        except (urllib.error.URLError,OSError,ValueError,TypeError) as error:
            # Exception text can contain the request URL and API key.
            LOG.warning('Product search failed (type=%s)',type(error).__name__)
            return dict(result,status='unavailable')
        stamp=datetime.now(timezone.utc).isoformat();products=[]
        for row in rows[:40]:
            if not isinstance(row,dict):continue
            title=row.get('title');url=public_url(row.get('product_link') or row.get('link'))
            if not isinstance(title,str) or not url or self.key in url:continue
            if brand and brand.casefold() not in title.casefold():continue
            price_text=row.get('price','');price=None
            # India locale alone does not prove the currency of a returned offer.
            if isinstance(price_text,str) and re.search(r'₹|\bINR\b|\bRs\.?',price_text,re.I):
                match=re.search(r'[\d,]+(?:\.\d+)?',price_text)
                if match:
                    try:price=float(Decimal(match[0].replace(',','')))
                    except (InvalidOperation,OverflowError):pass
            if price is not None and not 0<price<=10000000:price=None
            if budget is not None and (price is None or price>budget):continue
            specs=[s[:250] for s in row.get('extensions',[])[:8] if isinstance(s,str)] if isinstance(row.get('extensions'),list) else []
            rating=row.get('rating');reviews=row.get('reviews')
            products.append({'id':str(row.get('product_id') or len(products))[:100],'title':title[:300],
              'price_inr':price,'currency':'INR' if price is not None else None,'source_url':url,'source':str(row.get('source','Google Shopping'))[:100],
              'retrieved_at':stamp,'specifications':specs,'availability':'Not independently confirmed; check the source',
              'rating':rating if isinstance(rating,(int,float)) and 0<=rating<=5 else None,
              'review_count':reviews if isinstance(reviews,int) and 0<=reviews<=100000000 else None})
            if len(products)==4:break
        return {'available':bool(products),'configured':True,'status':'ok' if products else 'no_results','products':products,
          'sources':[p['source_url'] for p in products],'retrieved_at':stamp,
          'limitation':'Provider-retrieved shopping listings, not independently verified checkout prices. Missing specifications and review text are unknown. Ratings are aggregate listing evidence, not our sentiment model. Do not claim availability or best battery life without evidence.'}
