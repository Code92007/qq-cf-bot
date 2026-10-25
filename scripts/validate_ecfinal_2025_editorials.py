import itertools, random, functools, math
from fractions import Fraction

def badge(s):
 a=b=c=0
 for ch in s[::-1]:
  if ch=='p':a+=1
  elif ch=='c':
   if not b:return False
   b-=1;c+=1
  elif a:a-=1;b+=1
  elif c:c-=1
  else:return False
 return a==b==c==0

def badge_brute(s):
 states={(0,0,0)}
 for ch in s:
  nex=set()
  for a,b,c in states:
   if ch=='u':
    nex.add((a+1,b,c))
    if b:nex.add((a,b-1,c+1))
   if ch=='c' and a:nex.add((a-1,b+1,c))
   if ch=='p' and c:nex.add((a,b,c-1))
  states=nex
 return (0,0,0) in states

def high(a,b):
 k=len(a);n=len(b);A=max(a); b=sorted(b)
 if k==1:return max(Fraction(A),Fraction(sum(b),n))
 ans=Fraction(0)
 for j in range(k-2,n):
  P=Fraction(math.comb(j,k-2),math.comb(n,k-1))
  R=Fraction((j-k+2)*b[j]+sum(b[j+1:]),n-k+1)
  ans+=P*max(A,b[j],R)
 return ans
@functools.lru_cache(None)
def high_brute(slots,deck,mask):
 ans=Fraction(max(slots))
 for i in range(len(slots)):
  if mask>>i&1:continue
  val=0
  for j,x in enumerate(deck):
   t=slots[:i]+(x,)+slots[i+1:]
   val+=high_brute(t,deck[:j]+deck[j+1:],mask|1<<i)
  ans=max(ans,val/len(deck))
 return ans

def echo(b):
 last={};best=0
 for i,x in enumerate(b):
  if x in last:best=max(best,i-last[x])
  else:last[x]=i
 return best

def refrain(a,k,m,construct=False):
 n=len(a);intervals=[]
 for c in range(1,k+1):
  pos=[i for i,x in enumerate(a) if x==c]
  if pos:
   lo=pos[-1]-m;hi=pos[0]
   if lo>hi:return None
  else:lo=-m;hi=n-1
  intervals.append((lo,hi,c))
 intervals.sort();h=[];i=0;x=0;b=list(a)
 import heapq
 while x<n:
  while i<k and intervals[i][0]<=x:
   lo,hi,c=intervals[i];heapq.heappush(h,(hi,c));i+=1
  while h and h[0][0]+m<x:heapq.heappop(h)
  if not h:return None
  hi,c=heapq.heappop(h);end=min(hi,x)+m
  for j in range(x,min(end+1,n)):
   if b[j]==0:b[j]=c
  x=end+1
 return b

def resonance(p):
 n=len(p)-1;q=[0]*(n+1)
 for t in range(2,n+1):
  q[t-1]=t; chain=[];u=p[t]
  while u:chain.append(u);u=q[u]
  inc={chain[i]:chain[i+1] for i in range(len(chain)-1)}
  st=set(chain)
  old=q[:]
  for i in range(1,t):
   if i not in st and old[i] in inc:q[i]=inc[old[i]]
 return q

def resonance_inv(q):
 q=q[:];n=len(q)-1;p=[0]*(n+1)
 for t in range(n,1,-1):
  ch=[[] for _ in range(t+1)]
  for i in range(1,t):ch[q[i]].append(i)
  chain=[t]
  while ch[chain[-1]]:chain.append(max(ch[chain[-1]]))
  p[t]=chain[-1];nex={chain[i]:chain[i+1] for i in range(len(chain)-1)};st=set(chain);old=q[:]
  for i in range(1,t):
   if i not in st and old[i] in nex:q[i]=nex[old[i]]
  q[t-1]=0
 return p

def tree_paths(n,edges):
 adj=[[] for _ in range(n)]
 for u,v in edges:adj[u].append(v);adj[v].append(u)
 def dfs(u,p):
  # state (open endpoint or None, covered): (closed paths, endpoint)
  states={(0,False):(0,[],None)}
  for v in adj[u]:
   if v==p:continue
   v0,v1=dfs(v,u);ns={}
   def put(key,data):
    if key not in ns or data[0]<ns[key][0]:ns[key]=data
   for (op,covered),(cost,paths,end) in states.items():
    put((op,covered),(cost+v0[0],paths+v0[1],end))
    cost2=cost+v1[0];paths2=paths+v1[1]
    if op:put((0,True),(cost2+1,paths2+[(end,v1[2],u)],None))
    else:put((1,True),(cost2,paths2,v1[2]))
   states=ns
  out0=[];out1=[]
  for (op,covered),(cost,paths,end) in states.items():
   if op:
    out0.append((cost+1,paths+[(end,u,u)],None));out1.append((cost,paths,end))
   elif covered:
    out0.append((cost,paths,None));out1.append((cost,paths,u))
   else:
    out0.append((cost+1,paths+[(u,u,u)],None));out1.append((cost,paths,u))
  return min(out0,key=lambda x:x[0]),min(out1,key=lambda x:x[0])
 ret=dfs(0,-1)[0]
 depths=[0]*n
 def dep(u,p):
  for v in adj[u]:
   if v!=p:depths[v]=depths[u]+1;dep(v,u)
 dep(0,-1)
 paths=sorted(ret[1],key=lambda x:depths[x[2]])
 def path(a,b):
  prev={a:-1};st=[a]
  for x in st:
   for y in adj[x]:
    if y not in prev:prev[y]=x;st.append(y)
  mask=0
  while b!=-1:mask|=1<<b;b=prev[b]
  return mask
 active=0
 for a,b,c in paths:
  mask=path(a,b);assert (active&mask).bit_count()<=1
  active|=mask
 assert active==(1<<n)-1
 masks=[path(a,b) for a in range(n) for b in range(a,n)]
 d={0:0};queue=[0]
 for used in queue:
  if used==(1<<n)-1:break
  for m in masks:
   if (used&m).bit_count()<=1 and used|m not in d:d[used|m]=d[used]+1;queue.append(used|m)
 assert ret[0]==d[(1<<n)-1],(n,edges,ret,d[(1<<n)-1])

def prufer_tree(s):
 n=len(s)+2;deg=[1]*n;edges=[]
 for x in s:deg[x]+=1
 for x in s:
  y=next(i for i in range(n) if deg[i]==1);edges.append((x,y));deg[x]-=1;deg[y]-=1
 edges.append(tuple(i for i in range(n) if deg[i]==1));return edges

def run():
 checks={}
 c=0
 for n in (1,2):
  for s in itertools.product('ucp',repeat=4*n):assert badge(s)==badge_brute(s);c+=1
 checks['B']=c
 c=0; rng=random.Random(3295)
 for _ in range(150):
  n=rng.randint(1,5);k=rng.randint(1,min(3,n));a=tuple(rng.randint(-2,3) for _ in range(k));b=tuple(rng.randint(-2,3) for _ in range(n));assert high(a,b)==high_brute(a,b,0),(a,b,high(a,b),high_brute(a,b,0));c+=1
 checks['H']=c
 c=0
 for n in range(2,6):
  for k in range(1,min(n,3)+1):
   for a in itertools.product(range(k+1),repeat=n):
    holes=[i for i,x in enumerate(a) if x==0];best=n
    for values in itertools.product(range(1,k+1),repeat=len(holes)):
     b=list(a)
     for i,x in zip(holes,values):b[i]=x
     best=min(best,echo(b))
    got=next(m for m in range(n) if refrain(a,k,m) is not None)
    assert got==best,(a,k,best,got)
    b=refrain(a,k,got);assert echo(b)==best and all(x==0 or x==y for x,y in zip(a,b));c+=1
 checks['I']=c
 c=0
 for n in range(2,9):
  for x in itertools.product(*(range(1,i) for i in range(2,n+1))):
   p=[0,0]+list(x);q=resonance(p);assert all(i<q[i]<=n for i in range(1,n)) and q[n]==0
   assert all((i not in p[2:])==(i in q[1:n]) for i in range(1,n+1))
   assert resonance_inv(q)==p,(p,q,resonance_inv(q));c+=1
 checks['L']=c
 c=0
 for n in range(2,7):
  for s in itertools.product(range(n),repeat=n-2):tree_paths(n,prufer_tree(s));c+=1
 checks['J']=c
 return checks



def check_a():
 def cross(a,b):return a[0]*b[1]-a[1]*b[0]
 def sub(a,b):return (a[0]-b[0],a[1]-b[1])
 def dot(a,b):return a[0]*b[0]+a[1]*b[1]
 def formula(A,B,C,D):
  if dot(sub(B,A),sub(C,A))==0:A,B=B,A
  X,Y,Z=sub(B,A),sub(C,A),sub(D,A)
  u=Fraction(cross(Z,Y),cross(X,Y));v=Fraction(cross(X,Z),cross(X,Y))
  return 0<=v<=1 and (v in (0,1) or u.denominator==1 or (u+v).denominator==1 or (dot(sub(A,B),sub(C,B))==0 and (u+2*v).denominator==1 and u+2*v!=1))
 def explicit(A,B,C,D):
  if dot(sub(B,A),sub(C,A))==0:A,B=B,A
  X=sub(B,A);h=cross(X,sub(C,A));v=Fraction(cross(X,sub(D,A)),h)
  if not 0<=v<=1:return False
  if v in (0,1):return True
  def on(P,Q):return cross(sub(D,P),sub(Q,P))==0 and dot(sub(D,P),sub(D,Q))<=0
  for t in range(-12,13):
   shift=lambda P:(P[0]+t*X[0],P[1]+t*X[1])
   if on(shift(A),shift(C)) or on(shift(B),shift(C)):return True
   if t and dot(sub(A,B),sub(C,B))==0:
    Q=(A[0]+C[0]-B[0],A[1]+C[1]-B[1])
    if on(shift(B),shift(Q)):return True
  return False
 cases=0
 for C in [(-2,2),(0,2),(1,2),(2,2),(3,2)]:
  A=(0,0);B=(2,0)
  for x in range(-15,16):
   for y in range(-2,9):
    D=(Fraction(x,3),Fraction(y,3));assert formula(A,B,C,D)==explicit(A,B,C,D);cases+=1
 return cases

def check_k():
 cases=0;rng=random.Random(3295)
 for n in range(2,7):
  for s in itertools.product(range(n),repeat=n-2):
   edges=prufer_tree(s);adj=[[] for _ in range(n)]
   for i,(u,v) in enumerate(edges):adj[u].append((v,i));adj[v].append((u,i))
   used=[False]*n;chosen=set()
   def dfs(u,p):
    for v,i in adj[u]:
     if v!=p:
      dfs(v,u)
      if not used[u] and not used[v]:used[u]=used[v]=True;chosen.add(i)
   dfs(0,-1)
   best=0
   for mask in range(1<<(n-1)):
    vertices=set();ok=True
    for i,(u,v) in enumerate(edges):
     if mask>>i&1:
      if u in vertices or v in vertices:ok=False;break
      vertices.update((u,v))
    if ok:best=max(best,mask.bit_count())
   assert len(chosen)==best
   bits=[0]*n
   def paint(u,p):
    for v,i in adj[u]:
     if v!=p:bits[v]=bits[u]^(i in chosen);paint(v,u)
   paint(0,-1)
   order=list(range(n-1));rng.shuffle(order)
   got=[i for i in order if bits[edges[i][0]]!=bits[edges[i][1]]]
   assert set(got)==chosen
   cases+=1
 return cases

def check_badge_count():
 def dp(s):
  states={(0,0,0):1}
  for char in s[::-1]:
   nex={}
   for (a,b,c),cnt in states.items():
    for ch in ('ucp' if char=='?' else char):
     if ch=='p':st=(a+1,b,c)
     elif ch=='c' and b:st=(a,b-1,c+1)
     elif ch=='u' and a:st=(a-1,b+1,c)
     elif ch=='u' and c:st=(a,b,c-1)
     else:continue
     nex[st]=nex.get(st,0)+cnt
   states=nex
  return states.get((0,0,0),0)
 rng=random.Random(3295)
 for _ in range(100):
  s=''.join(rng.choice('ucp?') for i in range(8));holes=[i for i,x in enumerate(s) if x=='?'];ans=0
  for vals in itertools.product('ucp',repeat=len(holes)):
   t=list(s)
   for i,x in zip(holes,vals):t[i]=x
   ans+=badge_brute(t)
  assert dp(s)==ans
 assert dp('????????')==11
 return 101

if __name__=='__main__':
 import argparse,json,hashlib
 from pathlib import Path
 parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
 checks=run();checks['A']=check_a();checks['K']=check_k();checks['B']+=check_badge_count()
 methods={'A':'exact rational-coordinate formula versus explicit translated-segment membership on 1705 points; not a tiling-structure proof','B':'all complete three-letter strings of length 4/8 versus exhaustive parsing, plus 101 wildcard-count checks','H':'150 exact-rational comparisons against complete adaptive reroll decision trees','I':'1764 partial arrays against all completions, checking optimal span and constructed assignments','J':'all 1441 labeled trees through 6 vertices; activated-set BFS optimum and reconstructed path legality','K':'all 1441 labeled trees through 6 vertices; exhaustive maximum matching and encoded shuffled-edge reconstruction','L':'all 5913 increasing trees through 8 vertices; parent directions, leaf complement, and exact inverse'}
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 report={'scope':'2025 ICPC ECFinal A B H I J K L','status':'passed','seed':3295,'limitations':'Small-case independent checks, no online submissions or maximum-scale performance testing. A checks geometry formula implementation against official boundary characterization. H uses a corrected probability ratio.','checks':{k:{'passed':True,'cases':v,'method':methods[k]} for k,v in sorted(checks.items())},'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-ecfinal-*.md'))}}
 output=Path(args.output) if args.output else root/'regional_editorial_validation_ecfinal_2025.json'
 output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['checks'],ensure_ascii=False))
