"""Independent small exact checks for the 2025 CCPC Jinan explanations."""
from collections import Counter,deque
from functools import lru_cache
from itertools import product,permutations,combinations_with_replacement
from pathlib import Path
import hashlib,heapq,json,random
ROOT=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
rng=random.Random(20251116)

def cipher(a,b,w):
 mask=(1<<w)-1
 if a%2==0:
  p=1
  for x in range(w+1):
   if p==b:return x
   p=p*a&mask
  return None
 x=0;p=1;u=a;k=0
 while u!=1:
  z=(u-1)&mask;t=(z&-z).bit_length()-1
  if ((p^b)>>t)&1:p=p*u&mask;x|=1<<k
  u=u*u&mask;k+=1
 return x if p==b else None

def keywords(b,a):
 rank={x:i for i,x in enumerate(b)};cnt=[0]*len(b)
 for x in a:
  if x not in rank:continue
  p=rank[x]
  if p==0:cnt[0]+=1
  elif cnt[p-1]:cnt[p-1]-=1;cnt[p]+=1
 return cnt[-1]

def keyword_oracle(b,a):
 @lru_cache(None)
 def go(i,c):
  if i==len(a):return c[-1]
  ans=go(i+1,c)
  if a[i] in b:
   p=b.index(a[i]);d=list(c)
   if p==0 or d[p-1]:
    if p:d[p-1]-=1
    d[p]+=1;ans=max(ans,go(i+1,tuple(d)))
  return ans
 return go(0,(0,)*len(b))

def tree_info(par):
 n=len(par);children=[[] for _ in par]
 for v in range(1,n):children[par[v]].append(v)
 dep=[0]*n;sub=[set() for _ in par];order=[]
 def dfs(u):
  order.append(u);sub[u].add(u)
  for v in children[u]:dep[v]=dep[u]+1;dfs(v);sub[u]|=sub[v]
 dfs(0)
 return children,dep,sub,order

def pairs_count(par,col):
 ch,dep,sub,_=tree_info(par);n=len(par);V=set(range(n))
 def ways(s):return sum((1<<c)-1 for c in Counter(col[x] for x in s).values())
 inside=[ways(s) for s in sub];outside=[ways(V-s) for s in sub]
 ans=sum(2*inside[v]*outside[v] for v in range(1,n))
 for u in range(n):
  ws=[outside[u]]+[inside[v] for v in ch[u]]
  ans-=sum(ws)**2-sum(x*x for x in ws)
 return ans

def closure(par,vertices):
 if not vertices:return set()
 out=set(vertices);first=next(iter(vertices));anc=[];x=first
 while x!=-1:anc.append(x);x=par[x]
 for y in vertices:
  walk=[];x=y
  while x not in anc:walk.append(x);x=par[x]
  out.update(walk);out.update(anc[:anc.index(x)+1])
 return out

def pairs_oracle(par,col):
 n=len(par);sets=[]
 for mask in range(1,1<<n):
  s={i for i in range(n) if mask>>i&1}
  if len({col[i] for i in s})==1:sets.append(closure(par,s))
 return sum(not x&y for x in sets for y in sets)

def hash_dp(N,mod=10**30):
 F=[None]*(N+1)
 def get(i,j):return 1 if i==0 else F[i][j]
 for i in range(1,N+1):
  mx=N//i;cur=[1]+[0]*mx
  for l in range((i-1)//2+1):
   r=i-1-l;g=[get(l,k)*get(r,k)%mod if l!=r else get(l,2*k) for k in range(mx+1)]
   nxt=[0]*(mx+1)
   for j in range(mx+1):
    for k in range(j+1):nxt[j]=(nxt[j]+cur[j-k]*g[k])%mod
   cur=nxt
  F[i]=cur
 return F

def poly_sum(a,b):
 d=Counter(dict(a));d.update(dict(b));return tuple(sorted(d.items()))

def polynomials(N):
 P=[{()}]+[set() for _ in range(N)]
 for i in range(1,N+1):
  for l in range((i-1)//2+1):
   r=i-1-l
   for a in P[l]:
    for b in P[r]:
     d=Counter({():1})
     for sz,p in [(l,a),(r,b)]:
      for mon,c in p:d[tuple(sorted(mon+(sz,)))]+=c
     P[i].add(tuple(sorted(d.items())))
 return P

def ccpc(s):return len(s)>=4 and s[0]==s[1]==s[-1] and s[2:-1]==s[2:-1][::-1]
def ccpc_count(s):return sum(ccpc(s[l:r]) for l in range(len(s)) for r in range(l+1,len(s)+1))
def palsuf(s):return [s[i:] for i in range(len(s)) if s[i:]==s[i:][::-1]]
def good(P):return sum(len(q)>=3 and P[-len(q)-1]==q[0] for q in palsuf(P)[1:])
def right_increment(S,l,r):
 choices=[q for q in palsuf(S[:r+1]) if 3<=len(q)<=r-l]
 if not choices:return 0
 v=choices[0];return good(v)+int(S[r-len(v)]==S[r-len(v)+1])
def left_increment(S,l,r):
 if S[l]!=S[l+1]:return 0
 return sum(S[l+1:l+1+k]==S[l+1:l+1+k][::-1] for k in range(3,r-l+1))

def derive_d(par,perm):
 _,dep,sub,_=tree_info(par);pos={u:i for i,u in enumerate(perm)}
 return tuple(min((dep[v]-dep[u] for v in sub[u]-{u} if pos[v]<pos[u]),default=-1) for u in range(len(par)))

def recover(par,d):
 n=len(par);ch,dep,sub,_=tree_info(par)
 if 0 in d:return None
 outedges=[[] for _ in par];indeg=[0]*n
 for v in range(n):
  u=par[v]
  while u!=-1 and not(d[u]==-1 or dep[u]+d[u]>dep[v]):u=par[u]
  if u!=-1:outedges[u].append(v);indeg[v]+=1
 locked=[x!=-1 for x in d];groups={};owner=[-1]*n;up=[-1]*n
 for u in range(n):
  if locked[u]:
   t=dep[u]+d[u]
   if not any(dep[v]==t for v in sub[u]-{u}):return None
   groups.setdefault(t,[]).append(u)
 for t,group in groups.items():
  for u in group:
   ancestors=[v for v in group if v!=u and u in sub[v]]
   if ancestors:up[u]=max(ancestors,key=lambda v:dep[v])
  for x in range(n):
   if dep[x]==t:
    candidates=[u for u in group if x in sub[u]]
    if candidates:owner[x]=max(candidates,key=lambda u:dep[u])
 heap=[u for u in range(n) if not locked[u] and not indeg[u]];heapq.heapify(heap);ans=[]
 while heap:
  x=heapq.heappop(heap);ans.append(x)
  for v in outedges[x]:
   indeg[v]-=1
   if not indeg[v] and not locked[v]:heapq.heappush(heap,v)
  u=owner[x]
  while u!=-1 and locked[u]:
   locked[u]=False
   if not indeg[u]:heapq.heappush(heap,u)
   u=up[u]
 return tuple(ans) if len(ans)==n else None

def cards(a):
 n=len(a);pos=[[] for _ in range(n+1)]
 for i,x in enumerate(a):pos[x].append(i)
 own=[x for x in range(1,n+1) if not pos[x]];b=[None]*n
 for x in range(1,n+1):
  if len(pos[x])==2 and pos[x][0]>0:
   y=own.pop();i,j=pos[x];b[i-1]=y;b[j-1]=y
 rest=([own[0]]*2 if own else [])+[x for x in a if len(pos[x])==1];it=iter(rest)
 for i in range(n):
  if b[i] is None:b[i]=next(it)
 return b,int(len(pos[a[0]])==2)
def card_score(a,b):
 stack=[];ans=0
 for x,y in zip(a,b):
  for p,z in enumerate((x,y)):
   if z in stack:
    ans+=p==0;stack=stack[:stack.index(z)]
   else:stack.append(z)
 return ans

def build_matches(a):
 n=len(a);v=[0]+list(a)+[0]*(n-1);out=[0]*n
 for i in range(1,n):v[n+i]=min(v[2*i-1],v[2*i]);out[i]=max(v[2*i-1],v[2*i])
 return v,out

def update_match(v,out,p,x):
 n=(len(v))//2;v[p]=x
 while p<2*n-1:
  p=n+(p+1)//2;i=p-n
  out[i]=max(v[2*i-1],v[2*i]);v[p]=min(v[2*i-1],v[2*i])

def queue_oracle(a):
 q=deque(a);out=[]
 while len(q)>1:
  x=q.popleft();y=q.popleft();out.append(max(x,y));q.append(min(x,y))
 return out

from itertools import product
import random

def fill_cost(a):
 ans=0;i=0
 while i<len(a):
  j=i+1
  while j<len(a) and a[j]==a[i]:j+=1
  ans+=(j-i)**2;i=j
 return ans

def fill_small(seg):
 fixed=[];i=0
 while i<len(seg):
  if seg[i][0]==seg[i][1]:
   j=i+1
   while j<len(seg) and seg[j]==seg[i]:j+=1
   fixed.append((i,j,seg[i][0]));i=j
  else:i+=1
 if not fixed:return len(seg)
 extra=fixed[0][0]+len(seg)-fixed[-1][1];links=[]
 for left,right in zip(fixed,fixed[1:]):
  a,b=left[2],right[2];block=seg[left[1]:right[0]];m=len(block)
  if m==0:links.append(False);continue
  reach={a}
  for l,r in block:reach={v for v in (l,r) if any(u!=v for u in reach)}
  possible=any(v!=b for v in reach)
  if possible:extra+=m;links.append(False)
  elif m==1:links.append(True)
  else:extra+=m+2;links.append(False)
 dp={0:0};ans=extra
 for i,(l,r,_) in enumerate(fixed):
  w=r-l
  if i<len(links) and links[i]:
   new={}
   for t,val in dp.items():
    for nxt in (0,1):new[nxt]=min(new.get(nxt,10**20),val+(w+t+1-nxt)**2)
   dp=new
  else:ans+=min(val+(w+t)**2 for t,val in dp.items());dp={0:0}
 return ans

def fill_fast(seg):
 ans=0;st=0
 for i,(l,r) in enumerate(seg):
  if r-l>=2:ans+=fill_small(seg[st:i])+1;st=i+1
 return ans+fill_small(seg[st:])

from functools import lru_cache
from itertools import product
@lru_cache(None)
def triangulations(l,r):
 if r-l<2:return ((),)
 return tuple(left+right+((l,k,r),) for k in range(l+1,r) for left in triangulations(l,k) for right in triangulations(k,r))
def poly(tris,weights):
 out=[0]*8
 for tri in tris:
  part={0:1}
  for v in tri:
   const,mask=weights[v];new={}
   for old,c in part.items():
    new[old]=new.get(old,0)+c*const
    if mask:new[old|mask]=new.get(old|mask,0)+c
   part=new
  for mask,c in part.items():out[mask]+=c
 return out
rows=[]
for k in range(3,1000,2):
 x=k*(k+1)*(k+2)//(k*k-2)+1
 weights=[(k,0),(k+2,4),(k+1,0),(x,1),(k+2,0),(k+2,2)]
 center=poly(((0,2,4),(0,1,2),(2,3,4),(0,4,5)),weights)
 for tri in triangulations(0,5):
  p=poly(tri,weights)
  assert all(a>=b for a,b in zip(p,center)),(k,tri,p,center)
 T=center[0];low=T+(k+1)*(k*(k+2)-k-(k+2)+1)+k*k*(k+2)
 high=T+min((k+1)*(k+2)*(4000-x),k*(k+2)*(4000-k-2),k*(k+1)*(4000-k-2))
 rows.append((low,high,k,x,T))
cover=4000
for lo,hi,*_ in rows:
 assert lo<=cover+1,(lo,cover)
 cover=max(cover,hi)

def construct(X):
 if X<=4000:return [1,1,X]
 lo,hi,k,x,T=next(row for row in rows if row[0]<=X<=row[1])
 residual=X-T;dy=(-residual)%(k+1);N=(residual-k*(k+2)*dy)//(k+1)
 dx=N*((k+1)//2)%k;dz=(N-(k+2)*dx)//k
 return [k,k+2+dz,k+1,x+dx,k+2,k+2+dy]
def mcop(a):
 n=len(a);dp=[[0]*n for _ in a]
 for length in range(2,n):
  for l in range(n-length):
   r=l+length;dp[l][r]=min(dp[l][m]+dp[m][r]+a[l]*a[m]*a[r] for m in range(l+1,r))
 return dp[0][-1]

def check_matrix_targets():
 import random
 rng=random.Random(51)
 xs=list(range(1,5001))+[rng.randrange(1,10**9+1) for _ in range(20000)]
 for lo,hi,*_ in rows:
  xs.extend(x for x in (lo-1,lo,lo+1,hi-1,hi,hi+1) if 1<=x<=10**9)
 for X in xs:
  a=construct(X);assert all(1<=v<=4000 for v in a) and mcop(a)==X,(X,a,mcop(a))
 return len(xs)

def main():
 checks={};cnt=0
 for w in range(1,9):
  for a in range(1<<w):
   values={};p=1;x=0
   while p not in values:values[p]=x;x+=1;p=p*a% (1<<w)
   for b in range(1<<w):assert cipher(a,b,w)==values.get(b),(a,b,w);cnt+=1
 for a,b,x in [(2,4,2),(3,27,3),(1000000007,998244353,994996658310742016),(4,2,None),(1000000007,1000000009,None)]:assert cipher(a,b,64)==x;cnt+=1
 for _ in range(500):
  a=rng.randrange(1<<64);x=rng.randrange(1<<62);b=pow(a,x,1<<64);got=cipher(a,b,64);assert got is not None and pow(a,got,1<<64)==b and got<=x;cnt+=1
 checks['A']={'passed':True,'cases':cnt,'method':'all a,b modulo 2^w for w=1..8 against complete power cycles; official and random 64-bit checks'}
 cnt=0
 for _ in range(1600):
  m=rng.randrange(1,5);b=list(range(1,m+1));rng.shuffle(b);a=[rng.randrange(1,m+3) for _ in range(rng.randrange(12))]
  assert keywords(b,a)==keyword_oracle(b,a);cnt+=1
 checks['C']={'passed':True,'cases':cnt,'method':'greedy chain progress versus exhaustive skip/advance decision DP'}
 cnt=0
 for n in range(1,9):
  for _ in range(70):
   par=[-1]+[rng.randrange(i) for i in range(1,n)];col=[rng.randrange(3) for _ in range(n)]
   assert pairs_count(par,col)==pairs_oracle(par,col),(par,col);cnt+=1
 checks['E']={'passed':True,'cases':cnt,'method':'edge-minus-vertex separator formula versus all monochromatic subsets and exact Steiner subtree intersections'}
 cnt=0
 for n in range(1,10):
  for _ in range(1000):
   ints=[]
   for i in range(n):
    l=rng.randrange(1,5);r=rng.randrange(l,5);ints.append((l,r))
   brute=min(fill_cost(x) for x in product(*(range(l,r+1) for l,r in ints)))
   assert fill_fast(ints)==brute,(ints,fill_fast(ints),brute);cnt+=1
 checks['F']={'passed':True,'cases':cnt,'method':'all assignments of random small intervals versus separating flexible blocks and two-state fixed-run DP'}
 checks['G']={'passed':True,'cases':check_matrix_targets(),'method':'all 6986 triangulation-difference coefficient checks, exact interval coverage through 1e9, and complete matrix-chain DP for 26470 small/boundary/random targets'}

 N=12;F=hash_dp(N);P=polynomials(N);cnt=0
 for i in range(1,N+1):
  for j in range(N//i+1):
   sums={()}
   if j:
    sums=set()
    for items in combinations_with_replacement(sorted(P[i]),j):
     s=()
     for item in items:s=poly_sum(s,item)
     sums.add(s)
   assert F[i][j]==len(sums),(i,j,F[i][j],len(sums));cnt+=1
 assert hash_dp(15,1000000009)[15][1]==10904;cnt+=1
 checks['H']={'passed':True,'cases':cnt,'method':'enumerated exact hash polynomials of unordered binary trees and all size*j<=12 forest sums; official n=15 example'}
 cnt=0
 for _ in range(600):
  N=rng.randrange(4,23);S=''.join(rng.choice('abc') for _ in range(N));l=rng.randrange(N-2);r=rng.randrange(l+1,N)
  prev=ccpc_count(S[l:r]);assert right_increment(S,l,r)==ccpc_count(S[l:r+1])-prev
  assert left_increment(S,l,r)==ccpc_count(S[l:r+1])-ccpc_count(S[l+1:r+1]);cnt+=1
 for s,ops,expected in [('iloveccpc','Rj Ri Ln La Ln Ln',[1,1,1,1,1,1,2]),('cpcpccp','Lc Lc Rp Rc Lc Lc Rp Rp Rc',[0,2,3,3,4,5,7,8,8,9])]:
  actual=[ccpc_count(s)]
  for op in ops.split():s=op[1]+s if op[0]=='L' else s+op[1];actual.append(ccpc_count(s))
  assert actual==expected;cnt+=1
 checks['I']={'passed':True,'cases':cnt,'method':'exact palindrome suffix/fixed-context increments versus all literal CCPC substrings; both official operation examples; excludes optimized PAM implementation'}
 cnt=0
 for n in range(2,8):
  for _ in range(8):
   par=[-1]+[rng.randrange(i) for i in range(1,n)];solutions={}
   for perm in permutations(range(n)):
    d=derive_d(par,perm)
    if d not in solutions:solutions[d]=perm
   for d,perm in solutions.items():assert recover(par,d)==perm,(par,d,perm,recover(par,d));cnt+=1
   for _ in range(30):
    d=tuple(rng.randrange(-1,n+1) for _ in range(n));assert recover(par,d)==solutions.get(d),(par,d);cnt+=1
 checks['J']={'passed':True,'cases':cnt,'method':'all permutations for random trees through n=7, compressed ancestor edges and laminar unlocking versus lexicographically first valid permutation; includes invalid targets'}
 cnt=0
 for n in range(1,8):
  for a in product(range(1,n+1),repeat=n):
   if any(v>2 for v in Counter(a).values()):continue
   b,w=cards(a);assert Counter(a)+Counter(b)==Counter({x:2 for x in range(1,n+1)})
   assert card_score(a,b)==w,(a,b,w)
   if n<=4:assert min(card_score(a,p) for p in set(permutations(b)))==w
   cnt+=1
 checks['K']={'passed':True,'cases':cnt,'method':'every legal Alice sequence through n=7, verify all cards and literal game score; exhaustive Bob permutations through n=4'}
 cnt=0
 for n in range(2,45):
  a=list(range(1,n+1));rng.shuffle(a);v,out=build_matches(a)
  for _ in range(30):
   x,y=rng.sample(range(n),2);a[x],a[y]=a[y],a[x];update_match(v,out,x+1,a[x]);update_match(v,out,y+1,a[y])
   assert out[1:]==queue_oracle(a)
   l=rng.randrange(n-1);r=rng.randrange(l,n-1);assert sum(out[1:][l:r+1])==sum(queue_oracle(a)[l:r+1]);cnt+=1
 checks['L']={'passed':True,'cases':cnt,'method':'dependency-tree path updates after swaps versus literal queue simulation and interval sums'}
 files=[ROOT/f'editorials/2025/ccpc-jinan-{k}.md' for k in checks]
 report={'scope':'2025 CCPC Jinan '+' '.join(checks),'status':'passed','seed':20251116,'limitations':'Independent exact small-instance checks; no online submissions or maximum-scale timing. Optimized DSU-on-tree, PAM, segment-tree and Fenwick implementations are not benchmarked.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
 (ROOT/'regional_editorial_validation_ccpc_jinan_2025.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__':main()
