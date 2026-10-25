"""Small independent oracle checks for CCPC Final 2025 G/J/K/L."""
from collections import deque
from itertools import product
from pathlib import Path
import hashlib,json,random
ROOT=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
rng=random.Random(20251025)

def fill(a,limited):
 n=len(a);dp=[{} for _ in range(n+1)];dp[0][0]=None
 for r in range(1,n+1):
  prev=next((a[i] for i in range(r-1,-1,-1) if a[i]),0)
  lengths={1,2,3,4,prev} if limited else range(1,r+1)
  for k in lengths:
   if not 1<=k<=r or any(x not in (0,k) for x in a[r-k:r]):continue
   for old in dp[r-k]:
    if old!=k:dp[r][k]=old;break
 if not dp[n]:return None
 out=[0]*n;r=n;k=next(iter(dp[n]))
 while r:
  out[r-k:r]=[k]*k;old=dp[r][k];r-=k;k=old
 return out

def simulate(x,b,negative=False):
 p=c=ans=0
 for t,add in enumerate(x):
  p+=add;c+=b[t];k=c if negative else min(c,p)
  ans+=k*p-k*(k-1)//2;p-=k
 return ans

def poison(x):
 n=len(x);S=[];z=0
 for v in x:z+=v;S.append(z)
 tail=[0]*(n+1);W=[0]*(n+1)
 for s in range(n-1,-1,-1):tail[s]=tail[s+1]+S[s];W[s]=W[s+1]+tail[s]
 ans=0
 for s in range(n):
  ans=max(ans,simulate(x,[int(i>=s) for i in range(n)]))
  C=(n-s)*(n-s+1)//2
  for j in range(s,n):
   cp=C-(n-j);ans=max(ans,W[s]-tail[j]-cp*(cp-1)//2)
 return ans

def mex(a):
 s=set(a);v=0
 while v in s:v+=1
 return v

def repair(a):
 n=len(a);seen=set();c=0
 for x in a:
  if x>=n or x in seen:x=mex(seen);c+=1
  seen.add(x)
 return c

def mex_answer(a):return (a[-1],0) if a[-1]>=len(a)-1 else (len(a)-1,repair(a[:-1])+1)

def mex_bfs(a):
 goal=max(a[-1],len(a)-1);q=deque([(a,0)]);seen={a}
 while q:
  x,d=q.popleft()
  if x[-1]==goal:return goal,d
  for i in range(len(x)):
   y=x[:i]+(mex(x[:i]),)+x[i+1:]
   if y not in seen:seen.add(y);q.append((y,d+1))

def canon_add(b,x):
 for k in range(len(b)-1,-1,-1):
  if not x>>k&1:continue
  if b[k]:x^=b[k]
  else:
   for j in range(k-1,-1,-1):
    if x>>j&1:x^=b[j]
   for j in range(k+1,len(b)):
    if b[j]>>k&1:b[j]^=x
   b[k]=x;break

def span(a):
 s={0}
 for x in a:s|={v^x for v in list(s)}
 return frozenset(s)

def spaces(a,bits):
 b=[0]*bits;p=[-1]*bits;found=set()
 for r,x in enumerate(a):
  z=r
  for k in range(bits-1,-1,-1):
   if not x>>k&1:continue
   if not b[k]:b[k]=x;p[k]=z;break
   if p[k]<z:b[k],x=x,b[k];p[k],z=z,p[k]
   x^=b[k]
  for l in range(r+1):assert span([b[k] for k in range(bits) if p[k]>=l])==span(a[l:r+1])
  cb=[0]*bits
  if a[r]==0:found.add(tuple(cb))
  for _,v in sorted(((p[k],b[k]) for k in range(bits) if b[k]),reverse=True):
   canon_add(cb,v);found.add(tuple(cb))
 return len(found)

import heapq
from math import isqrt
from itertools import permutations

def modular_four(p,m,a,b):
 ans=min((m*pow(x,-1,p)%p)*y for x,y in zip(a,b))
 for order in permutations(range(4)):
  aa=[a[i] for i in order];bb=[b[i] for i in order];inv=pow(aa[3],-1,p);u=1
  while u**4<=p:
   v=u
   while u*v**3<=p:
    for w in range(v,isqrt(p//(u*v))+1):
     z=((m-aa[0]*(u-1)-aa[1]*(v-1)-aa[2]*(w-1))*inv)%p
     if z>=w-1 and u*v*w*(z+1)<=p:ans=min(ans,bb[0]*(u-1)+bb[1]*(v-1)+bb[2]*(w-1)+bb[3]*z)
    v+=1
   u+=1
 return ans

def modular_oracle(p,m,a,b):
 d=[10**30]*p;d[0]=0;q=[(0,0)]
 while q:
  cost,u=heapq.heappop(q)
  if cost!=d[u]:continue
  if u==m:return cost
  for x,y in zip(a,b):
   v=(u+x)%p;nd=cost+y
   if nd<d[v]:d[v]=nd;heapq.heappush(q,(nd,v))

D8=[(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
class GridCuts:
 def __init__(self,n,m):
  self.n=n;self.m=m;N=n*m;self.par=list(range(N+1));self.size=[1]*(N+1);self.size[0]=N+1;self.members=[[]]+[[i] for i in range(1,N+1)];self.dead={0};self.cut=set();self.answer=0
 def find(self,x):
  while self.par[x]!=x:self.par[x]=self.par[self.par[x]];x=self.par[x]
  return x
 def neighbors(self,p):
  x,y=divmod(p-1,self.m)
  return [(x+dx)*self.m+y+dy+1 if 0<=x+dx<self.n and 0<=y+dy<self.m else 0 for dx,dy in D8]
 def is_cut(self,p):
  if p in self.dead:return False
  ns=self.neighbors(p);ports=[i for i in range(0,8,2) if ns[i] not in self.dead]
  if len(ports)<2:return False
  labels=[]
  for a,b in zip(ports,ports[1:]+[ports[0]+8]):
   v={self.find(ns[k%8]) for k in range(a+1,b) if ns[k%8] in self.dead}
   assert len(v)<=1
   labels+=list(v)
  return len(labels)!=len(set(labels))
 def erase(self,p):
  p+=1;changed=set(self.neighbors(p));self.dead.add(p)
  if p in self.cut:self.cut.remove(p)
  for q in self.neighbors(p):
   if q not in self.dead:continue
   a,b=self.find(p),self.find(q)
   if a==b:continue
   if self.size[a]<self.size[b]:a,b=b,a
   for z in self.members[b]:changed.update(self.neighbors(z))
   self.par[b]=a;self.size[a]+=self.size[b];self.members[a]+=self.members[b];self.members[b]=[]
  for q in changed-self.dead:
   if self.is_cut(q):self.cut.add(q)
   else:self.cut.discard(q)
  return len(self.cut)

def brute_grid(n,m,dead):
 def comps(removed):
  seen=set(removed);cnt=0
  for p in range(n*m):
   if p in seen:continue
   cnt+=1;seen.add(p);q=[p]
   for u in q:
    x,y=divmod(u,m)
    for dx,dy in D8[::2]:
     xx,yy=x+dx,y+dy;v=xx*m+yy
     if 0<=xx<n and 0<=yy<m and v not in seen:seen.add(v);q.append(v)
  return cnt
 c=comps(dead)
 return {p for p in range(n*m) if p not in dead and comps(dead|{p})>c}

def check_more(rng):
 checks={};cnt=0
 primes=[2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97]
 for _ in range(500):
  p=rng.choice(primes);m=rng.randrange(p);a=[rng.randrange(1,p) for _ in range(4)];b=[rng.randrange(1,50) for _ in range(4)]
  assert modular_four(p,m,a,b)==modular_oracle(p,m,a,b),(p,m,a,b);cnt+=1
 assert modular_four(101,99,[1,2,3,4],[5,6,7,8])==199;cnt+=1
 checks['C']={'passed':True,'cases':cnt,'method':'24-order product-bound enumeration versus Dijkstra shortest paths on every residue; first official example'}
 cnt=0
 for n,m in [(2,2),(2,3),(3,3),(3,4)]:
  for mask in range(1<<(n*m)):
   dead={i for i in range(n*m) if mask>>i&1};g=GridCuts(n,m)
   for p in dead:g.erase(p)
   assert {x-1 for x in g.cut}==brute_grid(n,m,dead),(n,m,dead,g.cut);cnt+=1
 for _ in range(150):
  n=rng.randrange(2,8);m=rng.randrange(2,8);order=list(range(n*m));rng.shuffle(order);g=GridCuts(n,m);dead=set()
  for p in order:
   dead.add(p);assert g.erase(p)==len(brute_grid(n,m,dead));cnt+=1
 enc=[(0,1),(0,1),(1,4),(2,3),(4,1),(2,4),(1,1),(4,2),(2,1),(4,2),(1,0),(0,0)]
 expected=[1,2,2,6,5,7,10,7,6,7,7,4];last=0;g=GridCuts(5,5)
 for (x,y),answer in zip(enc,expected):
  p=((x+last)%5)*5+(y+last)%5;last=g.erase(p);assert last==answer;cnt+=1
 checks['M']={'passed':True,'cases':cnt,'method':'all deletion states on 2x2,2x3,3x3,3x4 grids and random online deletions versus brute four-connected component counts; official encrypted sample'}
 return checks

def main():
 checks={};cnt=0
 for n in range(1,7):
  for a in product(range(min(n+1,4)),repeat=n):
   if n>=6 and rng.randrange(8):continue
   got=fill(a,True);ref=fill(a,False);assert (got is None)==(ref is None),(a,got,ref)
   if got is not None:
    assert all(not x or x==y for x,y in zip(a,got))
    i=0
    while i<n:
     j=i+1
     while j<n and got[j]==got[i]:j+=1
     assert j-i==got[i];i=j
   cnt+=1
 for _ in range(500):
  n=rng.randrange(1,40);a=[0 if rng.random()<.7 else rng.randrange(1,n+1) for _ in range(n)]
  assert (fill(a,True) is None)==(fill(a,False) is None);cnt+=1
 checks['G']={'passed':True,'cases':cnt,'method':'restricted five-length constructive DP versus all-length DP; verify restored segments and clues'}
 cnt=0
 for n in range(1,9):
  for _ in range(100):
   x=[rng.randrange(8) for _ in range(n)]
   expected=max(simulate(x,b) for b in product(range(2),repeat=n))
   assert poison(x)==expected,(x,poison(x),expected);cnt+=1
 for x,answer in [([1,1,0,3,7],33),([0,3,2],11),([9,9,8,2,4,4,3,5,3],750),([1,1,4,5,1,4,1,9,1,9,8,1,0],725)]:
  assert poison(x)==answer;cnt+=1
 checks['J']={'passed':True,'cases':cnt,'method':'enumerate every binary accelerant policy through length 8 plus all four official examples'}
 cnt=0
 for n in range(1,6):
  for a in product(range(n+1),repeat=n):
   if n==5 and rng.randrange(30):continue
   assert mex_answer(a)==mex_bfs(a),(a,mex_answer(a),mex_bfs(a));cnt+=1
   # The lower-bound potential must decrease by at most one per legal prefix edit.
   F=repair(a)
   for i in range(n):
    b=a[:i]+(mex(a[:i]),)+a[i+1:]
    assert repair(b)>=F-1,(a,b,F,repair(b))
 checks['K']={'passed':True,'cases':cnt,'method':'BFS over literal mex operation state graph, plus one-operation repair potential bound'}
 cnt=0
 for n in range(1,9):
  for _ in range(120):
   a=[rng.randrange(16) for _ in range(n)]
   assert spaces(a,4)==len({span(a[l:r+1]) for r in range(n) for l in range(r+1)}),a;cnt+=1
 checks['L']={'passed':True,'cases':cnt,'method':'all interval subset-xor sets versus timestamp basis and exact canonical tuples; checks every suffix invariant'}
 checks.update(check_more(rng))
 files=[ROOT/f'editorials/2025/ccpc-final-{k}.md' for k in checks]
 report={'scope':'2025 CCPC Final C G J K L M','status':'passed','seed':20251025,'limitations':'Independent small-instance algorithm checks; no online submissions, maximum-scale performance or probabilistic hash validation.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
 path=ROOT/'regional_editorial_validation_ccpc_final_2025.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__':main()
