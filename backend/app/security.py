"""Single-process beta safeguards; do not trust user-supplied forwarded-IP headers."""
from collections import OrderedDict,deque
import json,time
from starlette.responses import JSONResponse

class Guard:
    def __init__(self,app,settings):
        self.app=app;self.settings=settings;self.clients=OrderedDict();self.global_requests=deque()

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.lower():v for k,v in scope.get('headers',[])}
        async def reply(status,code,message,extra=None):
            response=JSONResponse({'error':{'code':code,'message':message}},status_code=status,headers=extra)
            await response(scope,receive,secure_send)
        async def secure_send(message):
            if message['type']=='http.response.start':
                message['headers']=list(message.get('headers',[]))+[
                  (b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),
                  (b'x-frame-options',b'DENY'),(b'cache-control',b'no-store'),
                  (b'permissions-policy',b'camera=(), microphone=(), geolocation=()')]
                if self.settings.environment=='production':message['headers'].append((b'strict-transport-security',b'max-age=31536000'))
                connect="'self'"+(' '+self.settings.api_base_url if self.settings.api_base_url else '')
                policy=f"default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com/gsi/style; font-src 'self' https://fonts.gstatic.com; connect-src {connect} https://accounts.google.com/gsi/; frame-src https://accounts.google.com/gsi/; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                message['headers'].append((b'content-security-policy',policy.encode()))
            await send(message)
        if scope['method'] in {'POST','DELETE'} and scope['path'].startswith('/api/'):
            origin=headers.get(b'origin',b'').decode(errors='replace')
            if origin and origin not in self.settings.origins:
                return await reply(403,'origin_not_allowed','This browser origin is not approved.')
            now=time.monotonic();cutoff=now-60
            while self.global_requests and self.global_requests[0]<cutoff:self.global_requests.popleft()
            if len(self.global_requests)>=self.settings.global_rate_per_minute:
                return await reply(429,'rate_limited','The beta is busy. Retry in one minute.',{'Retry-After':'60'})
            key=(scope.get('client') or ('unknown',0))[0]
            times=self.clients.pop(key,deque())
            while times and times[0]<cutoff:times.popleft()
            self.clients[key]=times
            while len(self.clients)>10000:self.clients.popitem(last=False)
            if len(times)>=self.settings.rate_per_minute:
                return await reply(429,'rate_limited','Too many requests. Retry in one minute.',{'Retry-After':'60'})
            times.append(now);self.global_requests.append(now)
            try:length=int(headers.get(b'content-length',b'0'))
            except ValueError:return await reply(400,'invalid_length','Invalid request length.')
            if length>self.settings.body_limit:
                return await reply(413,'body_too_large','Request body exceeds the beta limit.')
            chunks=[];size=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                size+=len(message.get('body',b''))
                if size>self.settings.body_limit:
                    return await reply(413,'body_too_large','Request body exceeds the beta limit.')
                chunks.append(message.get('body',b''))
                if not message.get('more_body'):break
            delivered=False
            async def bounded_receive():
                nonlocal delivered
                if delivered:return await receive()
                delivered=True;return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await self.app(scope,bounded_receive,secure_send)
        await self.app(scope,receive,secure_send)
