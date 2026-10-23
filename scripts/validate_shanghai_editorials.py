#!/usr/bin/env python3
"""Independent small-case checks for the 2025 Shanghai explanations, Python 3.9+."""
import argparse
from pathlib import Path
from functools import lru_cache
from itertools import product,permutations,combinations_with_replacement
from collections import deque,Counter
from bisect import bisect_left,bisect_right
from math import comb
import random,json,hashlib
R=random.Random(20251024); REPORT={}
def record(k,n,method):
 REPORT[k]={'cases':n,'method':method,'passed':True}; print(k,n,flush=True)
def check_a():
 cases=0
 for n in (2,3,8,30,100):
  for _ in range(6):
   kids=[[] for _ in range(n)]; pa=[-1]*n; dep=[0]*n; available=[0]
   for v in range(1,n):
    u=R.choice(available);pa[v]=u;dep[v]=dep[u]+1;kids[u].append(v)
    if len(kids[u])==2:available.remove(u)
    available.append(v)
   desc=[set([v]) for v in range(n)]
   for v in range(n-1,0,-1):desc[pa[v]]|=desc[v]
   for target in range(n):
    lo,hi=0,n-1;calls=0
    while lo<hi:
     mid=(lo+hi)//2;calls+=1
     if dep[target]<=mid:hi=mid
     else:lo=mid+1
    cand={v for v in range(n) if dep[v]==lo}
    while len(cand)>1:
     v=min(range(1,n),key=lambda v:abs(len(cand)-2*len(cand&desc[v])))
     assert dep[v]<=lo
     calls+=1
     cand=cand&desc[v] if target in desc[v] else cand-desc[v]
    assert cand=={target} and calls<=40
    cases+=1
 record('A',cases,'all targets in random binary trees; subtree distance equivalence and query limit')
def construct_b(n,edges,s,mask):
 g=[[] for _ in range(n)]
 for u,v in edges:g[u].append(v);g[v].append(u)
 pa=[-2]*n;dep=[0]*n;kids=[[] for _ in range(n)];cycle=None
 def build(u):
  nonlocal cycle
  for v in g[u]:
   if pa[v]==-2:pa[v]=u;dep[v]=dep[u]+1;kids[u].append(v);build(v)
   elif dep[v]<=dep[u] and (dep[u]-dep[v])%2==0:cycle=(u,v)
 pa[s]=-1;build(s)
 if any(mask>>v&1 for v in range(n) if pa[v]==-2):return None
 odd=sum(mask>>v&1 for v in range(n) if pa[v]!=-2)%2
 if odd and cycle is None:return None
 if not odd:cycle=None
 out=[]
 def move(v):
  nonlocal mask
  out.append(v);mask^=1<<v
 def dfs(u):
  if cycle and u==cycle[0]:
   v=u
   while v!=cycle[1]:v=pa[v];move(v)
   move(u)
  for v in kids[u]:
   move(v);dfs(v);move(u)
   if mask>>v&1:move(v);move(u)
 dfs(s)
 assert mask==0 and len(out)<=5*n
 return out

def check_b():
 for _ in range(300):
  n=R.randrange(1,7);edges=[(u,v) for u in range(n) for v in range(u,n) if R.random()<.25];s=R.randrange(n);mask=R.randrange(1<<n)
  got=construct_b(n,edges,s,mask)
  q=deque([(s,mask)]);seen=set(q)
  while q:
   u,m=q.popleft()
   for x,y in edges:
    for v in ([y] if x==u else [])+([x] if y==u else []):
     t=(v,m^(1<<v))
     if t not in seen:seen.add(t);q.append(t)
  assert (got is not None)==((s,0) in seen)
  if got:
   u=s;m=mask
   for v in got:assert (u,v) in edges or (v,u) in edges;m^=1<<v;u=v
   assert u==s and m==0
 record('B',300,'closed-walk state-space search including disconnected graphs and self loops')
def fake(a,l,r):
 vals=sorted(a[l:r]);h=len(vals)//2;lo=iter(vals[:h]);hi=iter(vals[h:]);bound=vals[h-1]
 a[l:r]=[next(lo) if x<=bound else next(hi) for x in a[l:r]]
def construct_c(a):
 a=list(a);n=len(a);ops=[]
 def op(l,r):
  assert l>=1 and r<=n and (r-l+1)%2==0
  ops.append((l,r));fake(a,l-1,r)
 def bits():return [1 if v>n//2 else -1 for v in a]
 def prefixes():
  b=[0]
  for x in bits():b.append(b[-1]+x)
  return b
 def work(l,r,side):
  while l<=r:
   op(1,n);op(l,r)
   b=bits()
   if all(b[j]<=b[j+1] for j in range(l-1,r-1)):break
   if side=='L':
    while l+1<=r and b[l-1]==b[l]==-1:l+=2
   else:
    while l<=r-1 and b[r-1]==b[r-2]==1:r-=2
   assert len(ops)<=114
 c=prefixes()
 if max(c)-min(c)<=1:return None
 if max(c)==1 and min(c)==-1:
  pair=next(((u,v) for v in range(n+1) for u in range(v-3) if c[u]*c[v]==-1),None)
  if pair is None:return None
  op(1,n);op(pair[0]+1,pair[1]);c=prefixes()
 i=next(j for j in range(1,n+1) if abs(c[j])>=2)
 if c[i]<0:work(1,i,'R');work(3,n,'L')
 elif i>n//2:
  work(1,i,'L');op(1,n)
  if a[1]>n//2:
   p=i+1
   while p<n and a[p]>n//2:p+=1
   op(2,p) if p%2 else op(1,p)
  work(3,n,'L')
 else:
  work(i+1,n,'R');op(1,n)
  if a[-2]<=n//2:
   p=i
   while a[p-1]<=n//2:p-=1
   op(p,n) if (n-p)%2 else op(p,n-1)
  work(1,n-2,'R')
 op(1,n);assert a==list(range(1,n+1)) and len(ops)<=114
 return ops

def check_c():
 cases=0
 # The article handles n=4,6 by exact BFS; verify every shortest solution.
 for n in (4,6):
  states=list(permutations(range(1,n+1)));reverse={a:[] for a in states}
  for a in states:
   for l in range(n):
    for r in range(l+4,n+1,2):
     b=list(a);fake(b,l,r);reverse[tuple(b)].append((a,l,r))
  target=tuple(range(1,n+1));distance={target:0};q=deque([target])
  while q:
   b=q.popleft()
   for a,l,r in reverse[b]:
    if a not in distance:
     distance[a]=distance[b]+1;q.append(a)
     replay=list(a);fake(replay,l,r);assert tuple(replay)==b
  assert max(distance.values())<=114
  cases+=len(states)
 # Every balanced 8-bit pattern, with independently shuffled values within each class.
 for b in product(range(2),repeat=8):
  if sum(b)!=4:continue
  small=list(range(1,5));large=list(range(5,9));R.shuffle(small);R.shuffle(large)
  a=[(large if x else small).pop() for x in b];ops=construct_c(a)
  assert (ops is None)==all(b[i]!=b[i+1] for i in range(7));cases+=1
 for n in (10,16,50,100,1000):
  for _ in range(50):
   a=list(range(1,n+1));R.shuffle(a);ops=construct_c(a)
   if ops is None:assert all((a[i]>n//2)!=(a[i+1]>n//2) for i in range(n-1))
   cases+=1
 record('C',cases,'all length-4/6 permutation graphs, all balanced length-8 patterns and larger random permutations; simulate operations and enforce 114 limit')
def check_d():
 def rec(a):
  if len(a)==1:return a
  L=rec(a[:len(a)//2]);Q=rec(a[len(a)//2:]);return L+Q+[x+y for x,y in zip(L,Q)]
 for _ in range(100):
  n=R.randrange(1,6);a=[R.randrange(10) for _ in range(1<<n)]
  want=[sum(a[j] for j in range(1<<n) if all(v==2 or (j>>i&1)==v for i,v in enumerate(p))) for p in product(range(3),repeat=n)]
  assert sorted(rec(a))==sorted(want)
 record('D',100,'enumerate all ternary masks and all matching binary indices')
def check_e():
 for _ in range(150):
  n=R.randrange(2,15);m=R.randrange(4,18);k=R.randrange(1,4)
  a=[R.randrange(1<<m)]
  for i in range(1,n):
   x=R.choice(a)
   for p in R.sample(range(m),R.randrange(k+2)):x^=1<<p
   a.append(x)
  tree=[[] for _ in range(n)];got=[]
  for i in range(1,n):
   diff=a[i]^a[0];found=[]
   def dfs(v):
    nonlocal diff
    if bin(diff).count('1')<=k:found.append((v,diff))
    for u,change in tree[v]:diff^=change;dfs(u);diff^=change
   dfs(0);got.append(len(found))
   if not found:break
   v,change=found[0];tree[v].append((i,change))
  want=[sum(bin(a[i]^a[j]).count('1')<=k for j in range(i)) for i in range(1,n)]
  assert got==want[:len(got)] and (len(got)==n-1 or 0 in want)
 record('E',150,'incremental near-string tree against all pairwise Hamming distances')
def intersects(p,q,r,s):
 def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 if max(min(p[0],q[0]),min(r[0],s[0]))>min(max(p[0],q[0]),max(r[0],s[0])):return False
 if max(min(p[1],q[1]),min(r[1],s[1]))>min(max(p[1],q[1]),max(r[1],s[1])):return False
 return cross(p,q,r)*cross(p,q,s)<=0 and cross(r,s,p)*cross(r,s,q)<=0

def envelope_answer(segs,a,b,c):
 if c==0:return any(min(a,b)<=x<=max(a,b) or y==0 and max(x,0)>=min(a,b) for x,y in segs)
 for x,y in segs:
  if y==0 and a<=x:return True
  if x==0 and (a==0 or b==0 and c<=y):return True
  if x>0 and y>0:
   if x==a or x<a and y*(x-b)>=c*x or x>a and y*(x-b)<=c*x:return True
 return False

def check_f():
 cases=0
 for x,y,a,b,c in product(range(5),repeat=5):
  assert envelope_answer([(x,y)],a,b,c)==intersects((x,0),(0,y),(a,0),(b,c)),(x,y,a,b,c)
  cases+=1
 record('F',cases,'exhaustive coordinate grid 0..4; envelope conditions and all degeneracies versus segment intersection')
def maxbasis(a):
 bs={}
 for x in a:
  while x:
   b=x.bit_length()-1
   if b not in bs:bs[b]=x;break
   x^=bs[b]
 out=0
 for b in sorted(bs,reverse=True):out=max(out,out^bs[b])
 return out

def check_g():
 for _ in range(150):
  a=[R.randrange(1,32) for _ in range(R.randrange(1,8))];T=0
  for v in a:T^=v
  got=max(T,maxbasis([v&~T for v in a]));best=0
  def parts(i,groups):
   nonlocal best
   if i==len(a):
    v=groups[0]
    for x in groups[1:]:v&=x
    best=max(best,v);return
   for j in range(len(groups)):
    groups[j]^=a[i];parts(i+1,groups);groups[j]^=a[i]
   parts(i+1,groups+[a[i]])
  parts(0,[]);assert got==best
 record('G',150,'enumerate all set partitions versus masked linear basis')
@lru_cache(None)
def game(a,s,turn):
 if not a:return s==0
 values=[game(a[:i]+a[i+1:],s^v if turn==0 else s,1-turn) for i,v in enumerate(a) if i==0 or v!=a[i-1]]
 return any(values) if turn==0 else all(values)
def check_h():
 cases=0
 for n in (2,4,6):
  for a in combinations_with_replacement(range(5),n):
   cnt=Counter(a);X=0;odd=[]
   for v,c in cnt.items():
    if c//2%2:X^=v
    if c%2:odd.append(v)
   got=(X==0 if not odd else X in odd if len(odd)==2 else False)
   assert got==game(a,0,0),a;cases+=1
 record('H',cases,'exact minimax for every multiset of 2,4,6 values in 0..4')
def check_i():
 for _ in range(150):
  n=R.randrange(2,6);C=R.randrange(8);a=[0]+[R.randrange(8) for _ in range(n)]+[0];f=[0]+[10**9]*(n+1);best=[10**9]*64
  for i in range(1,n+2):
   j=i-1
   for low in range(8):
    idx=(a[j]//8)*8+low;best[idx]=min(best[idx],f[j]-(j+1)*C+(a[j]%8^low))
   f[i]=i*C+min(best[h*8+a[i]%8]+8*(h^(a[i]//8)) for h in range(8))
  want=min(sum((v!=x)*C for v,x in zip(vs,a[1:-1]))+vs[0]+vs[-1]+sum(x^y for x,y in zip(vs,vs[1:])) for vs in product(range(8),repeat=n))
  assert f[-1]==want
 for _ in range(150):
  n=R.randrange(2,20);C=R.randrange(100);a=[0]+[R.randrange(64) for _ in range(n)]+[0];f=[0];best=[10**9]*64
  for i in range(1,n+2):
   j=i-1
   for low in range(8):
    idx=(a[j]//8)*8+low;best[idx]=min(best[idx],f[j]-(j+1)*C+(a[j]%8^low))
   v=i*C+min(best[h*8+a[i]%8]+8*(h^(a[i]//8)) for h in range(8))
   assert v==min(f[j]+(i-j-1)*C+(a[j]^a[i]) for j in range(i))
   f.append(v)
 record('I',300,'150 exhaustive modification cases plus 150 full six-bit arrays against quadratic DP')
def lazy_paths(n,edges,k):
 g=[[] for _ in range(n)]
 for eid,(u,v,w) in enumerate(edges):g[u].append((w,eid,v))
 for row in g:row.sort()
 kids=[{}];fa=[-1];items=[[]];out=[]
 def add(p,w,item):
  if w not in kids[p]:kids[p][w]=len(kids);kids.append({});fa.append(p);items.append([])
  items[kids[p][w]].append(item)
 for u,row in enumerate(g):
  if row:w,_,v=row[0];add(0,w,(1,v,u,0))
 def dfs(p):
  i=0
  while i<len(items[p]) and len(out)<k:
   length,v,u,j=items[p][i];i+=1;out.append(length)
   if g[v]:w,_,to=g[v][0];add(p,w,(length+1,to,v,0))
   if j+1<len(g[u]):w,_,to=g[u][j+1];add(fa[p],w,(length,to,u,j+1))
  for w in range(1,9):
   if len(out)>=k:return
   if w in kids[p]:dfs(kids[p][w])
 dfs(0);return out+[-1]*(k-len(out))
def check_j():
 for _ in range(150):
  n=R.randrange(2,6);k=R.randrange(1,8)
  edges=[(R.randrange(n),R.randrange(n),R.randrange(1,4)) for _ in range(R.randrange(1,6))]
  g=[[] for _ in range(n)]
  for u,v,w in edges:g[u].append((v,w))
  strings=[]
  def gen(v,path):
   if path:strings.append(path)
   if len(path)==k:return
   for u,w in g[v]:gen(u,path+(w,))
  for v in range(n):gen(v,())
  want=[len(p) for p in sorted(strings)[:k]];want+= [-1]*(k-len(want))
  assert lazy_paths(n,edges,k)==want
 record('J',150,'enumerate all walks up to k edges, preserving duplicate edges, against lazy trie')
def block_sum(a,u,v):
 p=[];q=[]
 for x in a:p.append(min(p[-1],x) if p else x);q.append(max(q[-1],x) if q else x)
 A=sum(x>=u for x in p);B=sum(x<=v for x in q);x=min(A,B);y=max(A,B)
 ans=x*u*v
 if A<B:ans+=sum(p[x:y])*v
 else:ans+=sum(q[x:y])*u
 ans+=sum(p[i]*q[i] for i in range(y,len(a)))
 return ans

def check_k():
 for _ in range(500):
  a=[R.randrange(30) for _ in range(R.randrange(1,20))];u=R.randrange(30);v=R.randrange(u,40)
  p=u;q=v;want=0
  for x in a:p=min(p,x);q=max(q,x);want+=p*q
  assert block_sum(a,u,v)==want
  delta=R.randrange(-min(a),20);z=[x+delta for x in a]
  pp=[];qq=[]
  for x in a:pp.append(min(pp[-1],x) if pp else x);qq.append(max(qq[-1],x) if qq else x)
  assert sum((x+delta)*(y+delta) for x,y in zip(pp,qq))==sum(x*y for x,y in zip(pp,qq))+delta*(sum(pp)+sum(qq))+len(a)*delta*delta
  assert block_sum(z,u,v)==sum(min(u,min(z[:i]))*max(v,max(z[:i])) for i in range(1,len(a)+1))
 record('K',500,'block split points and lazy-add sum identities versus prefix scans')
@lru_cache(None)
def reachable(a):
 if len(a)==1:return frozenset([a])
 b=list(a);i=b.index(min(b));j=b.index(max(b));b[i],b[j]=b[j],b[i];out=set()
 for cur in (a,tuple(b)):
  for k in range(1,len(a)):
   out.update(x+y for x in reachable(cur[:k]) for y in reachable(cur[k:]))
 return frozenset(out)
def count_l(a):
 n=len(a)
 @lru_cache(None)
 def f(l,r,x,y):
  if l==r:return 1
  ids=sorted(range(l,r+1),key=lambda i:a[i]);m,M=ids[0],ids[-1]
  if x==1:m,M=ids[1],ids[0]
  if x==2:m,M=ids[-1],ids[-2]
  b1,b2=sorted((m,M));ans=0
  for k in range(l,b2):
   if k<b1:
    if y!=1:ans+=f(l,k,0,1)*f(k+1,r,x,y)
    continue
   if y!=1 and not(y==2 and m<=k) and not(y==3 and M<=k):
    p1=p2=0
    if x==1:
     if M<=k:p1=1
     else:p2=1
    if x==2:
     if m<=k:p1=2
     else:p2=2
    ans+=f(l,k,p1,1)*f(k+1,r,p2,y)
   if x==0:p1,p2=(1,2) if m<=k else (2,1)
   elif x==1:p1,p2=(1,0) if m<=k else (0,1)
   else:p1,p2=(2,0) if M<=k else (0,2)
   y2=0 if y==0 else 2 if m<=k else 3
   ans+=f(l,k,p1,1)*f(k+1,r,p2,y2)
  return ans
 return f(0,n-1,0,0)
def check_l():
 cases=0
 for n in range(1,7):
  choices=list(permutations(range(1,n+1)))
  if n==6:choices=R.sample(choices,100)
  for a in choices:
   assert count_l(a)==len(reachable(a)),a;cases+=1
 record('L',cases,'distinct reachable permutations from all recursive splits and extremal swaps versus 12-state DP')
@lru_cache(None)
def trees(s):
 if len(s)==1:return int(s=='0')
 flip=lambda s:''.join('1' if x=='0' else '0' for x in s)
 return sum(trees(s[:i])*trees(flip(s[i:]))+trees(flip(s[:i]))*trees(s[i:]) for i in range(1,len(s)))
def matching(s):
 f=[1];prev=[1]
 for i in range(1,len(s)):
  w=1 if s[i]!=s[i-1] else -1;new=f+[0]
  for k,v in enumerate(prev):new[k+1]+=w*v
  prev,f=f,new
 return f

def check_m():
 cases=0
 for n in range(2,10):
  for chars in product('01',repeat=n):
   s=''.join(chars);p=matching(s)
   val=sum(v*comb(2*(n-k-1),n-k-1)//(n-k) for k,v in enumerate(p) if k<=n//2)
   assert val%2==0 and val//2==trees(s),(s,val,trees(s));cases+=1
 record('M',cases,'all binary strings through length 9; enumerate ordered trees and edge orientations versus matching polynomial')
if __name__=='__main__':
 for f in (check_a,check_b,check_c,check_d,check_e,check_f,check_g,check_h,check_i,check_j,check_k,check_l,check_m):f()
 print('TOTAL',sum(x['cases'] for x in REPORT.values()))
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 report={'scope':'2025 ICPC Shanghai A-M','seed':20251024,'status':'passed','limitations':'Small-case algorithm checks only; no online judge submissions, extreme-scale timing, or NTT implementation verification.','checks':REPORT,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-shanghai-*.md'))}}
 if args.report: args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
