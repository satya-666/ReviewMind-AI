"""Bounded intent routing and Gemini text generation, separate from sentiment inference."""
from collections import deque
from decimal import Decimal
import json,re,socket,threading,time,urllib.error,urllib.request
from backend.app.prompts import REVIEWMIND_INSTRUCTION,TOOL_INSTRUCTION

PRODUCT=r'phone|smartphone|laptop|tablet|earbud|headphone|watch|television|monitor|router|charger|power bank|iphone|samsung|pixel|redmi|oneplus|product|प्रोडक्ट|फोन|मोबाइल'
FEATURE=r'battery|camera|display|screen|performance|sound|bass|keyboard|charging|बैटरी|कैमरा'

def intent_for(text,mode='auto'):
    if mode=='review' or re.match(r'^\s*(?:analy[sz]e\s+(?:this\s+)?review\s*:|review\s*:)',text,re.I):return 'review'
    if re.search(r'\b(system prompt|api key|secret key|credentials)\b',text,re.I):return 'unsupported'
    if re.search(r'\b(?:why|explain|how come)\b.*\b(?:classif|predict|sentiment|positive|negative|neutral|result|score)|why (?:that|so)|क्यों',text,re.I):return 'explanation'
    if re.search(r'\b(?:recommend|suggest|buy|shopping|best\s+(?:phone|smartphone|laptop|tablet|earbuds?))\b|सुझाव|कौन.*(?:फोन|खरीद)',text,re.I):return 'recommendation'
    if re.search(r'\b(?:compare|versus|vs\.?)\b|तुलना',text,re.I):return 'comparison'
    if re.search(r'\b(?:i (?:want|need|prefer|would like|am looking)|my budget|my priority|matters most|is my priority)\b',text,re.I):return 'conversation'
    if re.search(r'^(?:hi|hello|hey|namaste|thanks|thank you|good morning|नमस्ते)\b|who are you|what can you do|your name|कौन हो',text,re.I):return 'conversation'
    question=bool(re.search(r'\?|^(?:what|which|how|why|can|could|does|is|are|tell me|do you|please tell)\b',text.strip(),re.I))
    if question and re.search(FEATURE,text,re.I):return 'aspect_question'
    if question and re.search(PRODUCT+r'|price|availability|specification',text,re.I):return 'product_info'
    if re.search(r'^(?:analy[sz]e\b|review\s*:)',text,re.I):return 'review'
    if not question and re.search(FEATURE+r'|'+PRODUCT,text,re.I) and re.search(r'\b(?:excellent|great|good|bad|poor|disappointing|love|hate|works?|drains?|slow|fast|comfortable|broken|acha|achha|kharab)\b|अच्छ|खराब|शानदार',text,re.I):return 'review'
    # Short replies, typos and preferences need the LLM's context, not a canned guide.
    return 'conversation'

from backend.app.products import ProductData

class ProviderError(Exception):
    def __init__(self,code,status=None):self.code=code;self.status=status;super().__init__(code)

def currency_amounts(text):
    return {str(Decimal(re.sub(r'[,\s]','',m.group(1)).rstrip('.')).normalize()) for m in re.finditer(r'(?:₹|\$|\bINR\b|\bRs\.?|\bUSD\b)\s*(\d[\d,]*(?:\.\d+)?)',text,re.I)}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class GeminiConversation:
    def __init__(self,settings):
        self.key=settings.gemini_api_key;self.model=settings.gemini_model
        self.opener=urllib.request.build_opener(NoRedirect())
        self.responded=False
        self.slots=threading.BoundedSemaphore(2);self.lock=threading.Lock();self.calls=deque()

    @property
    def configured(self):return bool(self.key)

    def generate(self,message,history,context,language,tools=None,execute=None):
        context=context or {}
        if not self.configured:raise ProviderError('not_configured')
        with self.lock:
            now=time.monotonic()
            while self.calls and self.calls[0]<now-60:self.calls.popleft()
            if len(self.calls)>=10:raise ProviderError('rate_limited')
            if not self.slots.acquire(blocking=False):raise ProviderError('busy')
            self.calls.append(now)
        try:
            instruction=REVIEWMIND_INSTRUCTION+(TOOL_INSTRUCTION if tools else '')+'\nRequested language: '+language+'\nServer tool results: '+json.dumps(context)
            contents=[]
            for role,text in [('user' if m.role=='user' else 'model',m.text) for m in history]+[('user',message)]:
                if not contents and role=='model':continue
                if contents and contents[-1]['role']==role:contents[-1]['parts'].append({'text':text})
                else:contents.append({'role':role,'parts':[{'text':text}]})
            payload={'systemInstruction':{'parts':[{'text':instruction}]},'contents':contents,
              'generationConfig':{'maxOutputTokens':512,'temperature':0.2}}
            if tools:payload['tools']=[{'functionDeclarations':tools}]
            for round_number in range(2):
                if round_number:
                    with self.lock:
                        now=time.monotonic()
                        while self.calls and self.calls[0]<now-60:self.calls.popleft()
                        if len(self.calls)>=10:raise ProviderError('rate_limited')
                        self.calls.append(now)
                request=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+self.model+':generateContent',
                  data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':self.key},method='POST')
                with self.opener.open(request,timeout=20) as response:raw=response.read(65537)
                if len(raw)>65536:raise ProviderError('invalid_response')
                data=json.loads(raw);candidate=(data.get('candidates') or [{}])[0]
                if candidate.get('finishReason') not in {'STOP','MAX_TOKENS'}:raise ProviderError('blocked')
                parts=candidate.get('content',{}).get('parts',[])
                calls=[p['functionCall'] for p in parts if 'functionCall' in p]
                if not calls:break
                if round_number or not execute or len(calls)>3:raise ProviderError('invalid_response')
                responses=[]
                for call in calls:
                    output=execute(call.get('name'),call.get('args',{}))
                    responses.append({'functionResponse':{'name':call.get('name'),'response':output,**({'id':call['id']} if 'id' in call else {})}})
                # Preserve model parts, including provider thought signatures, verbatim for tool responses.
                payload['contents'].extend([candidate['content'],{'role':'user','parts':responses}])
                payload.pop('tools',None)
            reply='\n'.join(p['text'] for p in candidate.get('content',{}).get('parts',[]) if isinstance(p.get('text'),str) and not p.get('thought')).strip()
            if not reply or len(reply)>6000:raise ProviderError('invalid_response')
            supplied=' '.join([m.text for m in history if m.role=='user']+[message])+' '+' '.join('INR '+str(p['price_inr']) for p in context.get('product_data',{}).get('products',[]) if p.get('price_inr') is not None)
            urls=re.findall(r'https?://[^\s<>\]\)]+',reply)
            sources=context.get('product_data',{}).get('sources',[])
            if self.key in reply or any(url.rstrip('.,') not in sources for url in urls) or not currency_amounts(reply)<=currency_amounts(supplied):raise ProviderError('ungrounded_response')
            if not (context or {}).get('prediction') and re.search(r"\b(?:I|we)(?:['’]ve| have)?\s+(?:analy[sz]ed|classified|predicted)\b",reply,re.I):raise ProviderError('ungrounded_response')
            self.responded=True
            return reply
        except urllib.error.HTTPError as problem:
            raise ProviderError('provider_rate_limited' if problem.code==429 else 'authentication_failed' if problem.code in {401,403} else 'request_rejected' if problem.code==400 else 'unavailable',problem.code) from None
        except (TimeoutError,socket.timeout):raise ProviderError('timeout') from None
        except (urllib.error.URLError,OSError):raise ProviderError('network_error') from None
        except (ValueError,KeyError,TypeError,AttributeError):raise ProviderError('invalid_response') from None
        finally:self.slots.release()
