import hmac, os, time, threading
from collections import deque
from flask import Flask,request,jsonify
from backend.rag import OpenAI,ProviderError,answer_question
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=20000
lock=threading.Lock();calls=deque()

def configured():return all(os.getenv(k) for k in ['OPENAI_API_KEY','OPENAI_VECTOR_STORE_ID']) and len(os.getenv('RAG_ACCESS_CODE',''))>=32
@app.after_request
def cors(response):
    if request.headers.get('Origin')==os.getenv('ALLOWED_ORIGIN','https://octavianro.github.io'):
        response.headers['Access-Control-Allow-Origin']=request.headers['Origin']
        response.headers['Vary']='Origin'
        response.headers['Access-Control-Allow-Headers']='Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods']='POST, GET, OPTIONS'
    response.headers['Cache-Control']='no-store'
    return response
@app.get('/health')
def health():return jsonify({'mode':'rag','ready':configured()})
@app.route('/chat',methods=['POST','OPTIONS'])
def chat():
    if request.method=='OPTIONS':return ('',204)
    if not configured():return jsonify(error='RAG is not configured yet.'),503
    expected='Bearer '+os.environ['RAG_ACCESS_CODE']
    if not hmac.compare_digest(request.headers.get('Authorization','').encode(),expected.encode()):return jsonify(error='Enter the correct assistant access code.'),401
    d=request.get_json(silent=True)
    if not isinstance(d,dict):return jsonify(error='Invalid request.'),400
    q=d.get('question');history=d.get('history',[]);category=d.get('category','All products')
    if not isinstance(q,str) or not q.strip() or len(q)>1500 or not isinstance(category,str) or len(category)>80 or not isinstance(history,list) or len(history)>6:return jsonify(error='Invalid question or conversation.'),400
    if any(not isinstance(m,dict) or m.get('role') not in ['user','assistant'] or not isinstance(m.get('content'),str) or len(m['content'])>2000 for m in history):return jsonify(error='Invalid conversation.'),400
    with lock:
        now=time.time()
        while calls and calls[0]<now-86400:calls.popleft()
        if len(calls)>=int(os.getenv('DAILY_REQUEST_LIMIT','200')) or sum(t>now-60 for t in calls)>=10:return jsonify(error='Assistant usage limit reached. Please try again later.'),429
        calls.append(now)
    try:return jsonify(answer_question(OpenAI(os.environ['OPENAI_API_KEY']),os.environ['OPENAI_VECTOR_STORE_ID'],os.getenv('OPENAI_MODEL','gpt-4.1-mini'),q.strip(),history,category))
    except ProviderError as e:return jsonify(error=str(e)),502
@app.errorhandler(413)
def too_large(e):return jsonify(error='Request too large.'),413
