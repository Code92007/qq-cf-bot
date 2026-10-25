#!/usr/bin/env python3
"""Reproducible small-case checks for the 2025 Chengdu explanations."""
from collections import deque,Counter
from itertools import product,combinations
from functools import lru_cache
from math import gcd
from pathlib import Path
import json,random,hashlib,argparse
R=random.Random(20251025); checks={}
def record(k,n,method): checks[k]={'cases':n,'method':method,'passed':True};print(k,n,flush=True)
def check_a():
 cases=0
 for n in range(1,12):
  arrays=[list(a) for a in product((0,33,50,100),repeat=n)] if n<=4 else [[R.randrange(101) for _ in range(n)] for _ in range(500)]
  arrays += [[0]*n,[100]+[0]*(n-1)]
  for a in arrays:
   s=sum(a);c=sum(x>0 for x in a)
   feasible=sum(max(0,2*x-1) for x in a)<=200 and (sum(min(200,2*x+1) for x in a)>200 or a.count(100)==1 and s==100)
   got=2*s-c<=200 and 2*s+n>200
   assert got==feasible
   if got:
    if s>100:
     b=[2*x for x in a];need=2*(s-100)
     for i in range(n):
      if b[i] and need:b[i]-=1;need-=1
     assert need==0
    else:b=[n*x+100-s for x in a]
    total=sum(b);assert total>0 and all(0<=x<=10**9 for x in b)
    assert [(200*x+total)//(2*total) for x in b]==a
   cases+=1
 record('A',cases,'integer construction checked against independent exact rounding intervals and exact fraction rounding')
def check_b():
 def mul(a,b):
  n=len(a);c=[[-10**18]*n for _ in range(n)]
  for i in range(n):
   for j in range(n):
    for k in range(n):
     if a[i][k]>-10**18 and b[k][j]>-10**18:c[i][j]=max(c[i][j],a[i][k]+b[k][j])
  return c
 for _ in range(150):
  n=R.randrange(1,4);m=R.randrange(1,8);k=R.randrange(1,4);rounds=R.randrange(1,8)
  costs=[R.randrange(1,m+1) for _ in range(n)];attack=[R.randrange(1,9) for _ in range(n)];q=1<<n
  M=[[-10**18]*q for _ in range(q)]
  for t in range(q):
   for s in range(q):
    if sum(costs[i]+(k if t>>i&1 else 0) for i in range(n) if s>>i&1)<=m:M[t][s]=sum(attack[i] for i in range(n) if s>>i&1)
  P=[[0 if i==j else -10**18 for j in range(q)] for i in range(q)];base=M;e=rounds
  while e:
   if e&1:P=mul(P,base)
   base=mul(base,base);e//=2
  @lru_cache(None)
  def brute(left,last):
   if not left:return 0
   return max(sum(attack[i] for i in range(n) if s>>i&1)+brute(left-1,s) for s in range(q) if sum(costs[i]+k*(last>>i&1) for i in range(n) if s>>i&1)<=m)
  assert max(P[0])==brute(rounds,0)
 record('B',150,'max-plus power versus recursive enumeration of all feasible skill subsets for each round')
def check_c():
 for _ in range(1000):
  a=sorted(R.randrange(1,15) for _ in range(R.randrange(1,6)));b=sorted(R.randrange(1,15) for _ in range(R.randrange(1,6)));k=R.randrange(1,5)
  def greedy(last):
   pool=[list(a),list(b)];rev=[];side=last
   while pool[0] or pool[1]:
    if pool[side]:rev.append((side,pool[side].pop()))
    side^=1
   t=0;prev=None
   for s,arrival in reversed(rev):t=max(arrival,t+(0 if prev is None else k*(1+(prev==s))));prev=s
   return t+k
  @lru_cache(None)
  def brute(i,j,last):
   if i+j==0:return 0
   ans=10**9;arrival=(a[i-1] if last==0 and i else b[j-1] if last==1 and j else None)
   if arrival is None:return ans
   x,y=i-(last==0),j-(last==1)
   if not x+y:return arrival
   for prev in (0,1):ans=min(ans,max(arrival,brute(x,y,prev)+k*(1+(prev==last))))
   return ans
  assert min(greedy(0),greedy(1))==min(brute(len(a),len(b),0),brute(len(a),len(b),1))+k
 record('C',1000,'two reverse schedules versus exact DP over every interleaving of sorted bank arrivals')
def check_d():
 start=(0,0,21,0,0);prev={start:None};dist={start:0};q=deque([start])
 while q:
  a,b,n,p,z=q.popleft();s=(a,b,n,p,z)
  if not n:continue
  nxt=[((a,b,n,1-p,0),'/')]
  cs=range(2,8) if z else [1 if n>6 else 8-n]
  for c in cs:
   t=(a+(c if p==0 else 0),b+(c if p==1 else 0),n-(not z),p,int(not z and n>6));nxt.append((t,str(c)))
  for t,ch in nxt:
   if t not in prev:prev[t]=(s,ch);dist[t]=dist[s]+1;q.append(t)
 assert max(dist.values())<=100
 assert (147,0,0,0,0) in prev and (147,0,0,1,0) not in prev
 states=R.sample(list(prev),500)
 for target in states:
  u=target;path=[]
  while prev[u] is not None:u,ch=prev[u];path.append(ch)
  score=[0,0];red=15;colors=list(range(2,8));player=0;need_color=False
  for ch in reversed(path):
   assert red or colors
   if ch=='/':player^=1;need_color=False;continue
   c=int(ch)
   if need_color:assert 2<=c<=7;need_color=False
   elif red:assert c==1;red-=1;need_color=True
   else:assert c==colors.pop(0)
   score[player]+=c
  assert (score[0],score[1],red+len(colors),player,int(need_color))==target
 record('D',len(prev)+500,'full reachable-state BFS, shortest path length limit, terminal-turn rejection and independent ball-list replay of 500 paths')
def check_g():
 cases=0
 for n in range(1,5):
  for k in range(1,n+1):
   best=[0]*(n+1)
   for a in product(range(1,n+1),repeat=n):
    edits=sum(x!=i+1 for i,x in enumerate(a));good=[]
    for s in range(1,1<<n):
     g=0
     for i in range(n):
      if s>>i&1:g=gcd(g,a[i])
     if g==k:good.append(s)
    dp=[0]*(1<<n)
    for s in range(1,1<<n):
     dp[s]=max([0]+[1+dp[s^t] for t in good if t&s==t])
    best[edits]=max(best[edits],dp[-1]);cases+=1
   for m in range(n+1):
    if m:best[m]=max(best[m],best[m-1])
    q=n//k;base=(q+1)//2;u=n-(2*base-1);x=min(m,u)
    assert best[m]==base+x+(m-x)//2,(n,k,m,best)
 record('G',cases,'all replacement arrays for n<=4, all target gcds and budgets; exact disjoint subset packing')
def check_j():
 for _ in range(500):
  n=R.randrange(1,8);m=R.randrange(1,6);b=R.randrange(n+1);k=R.randrange(-5,6);a=[[R.randrange(-3,4) for _ in range(m)] for _ in range(n)]
  old=[sum(row) for row in a];new=[sum(x+1 if x<=0 else x-1 for x in row) for row in a]
  got=sum(s>=k for s in old)+min(b,sum(s<k<=t for s,t in zip(old,new)))
  want=max(sum((new[i] if mask>>i&1 else old[i])>=k for i in range(n)) for mask in range(1<<n) if bin(mask).count('1')<=b)
  assert got==want
 record('J',500,'all rebuttal subsets on random score tables including zero scores and negative thresholds')
def coverage(a,L,k):
 c=Counter(x for l in a for x in range(l,l+L));return sum(v==k for v in c.values())
def check_k():
 for _ in range(1000):
  n=R.randrange(1,9);L=R.randrange(1,n+1);k=R.randrange(1,n+1);a=[R.randrange(2*n+1) for _ in range(n)];N=4*n+2
  d=[sum(l<=x<l+L for l in a) for x in range(N)]
  X=[int(v==k+1)-int(v==k) for v in d];Y=[int(v==k-1)-int(v==k) for v in d]
  px=[0];py=[0]
  for x,y in zip(X,Y):px.append(px[-1]+x);py.append(py[-1]+y)
  W=[py[s+L]-py[s] for s in range(3*n+1)];pre=[];suf=[0]*len(W)
  for w in W:pre.append(max(w,pre[-1] if pre else -10**9))
  for i in range(len(W)-1,-1,-1):suf[i]=max(W[i],suf[i+1] if i+1<len(W) else -10**9)
  F=[px[s]+py[s+L] for s in range(3*n+1)];H=[py[s]+px[s+L] for s in range(3*n+1)]
  # Direct range maxima isolate the derived overlap identities from the independent brute scorer.
  gain=0
  for l in a:
   removal=px[l+L]-px[l]
   if l>=L:gain=max(gain,removal+pre[l-L])
   gain=max(gain,removal+suf[l+L],max(F[l:l+L+1])-F[l],H[l]-min(H[max(0,l-L):l+1]))
  got=sum(v==k for v in d)+gain
  want=max(coverage(a[:i]+[s]+a[i+1:],L,k) for i in range(n) for s in range(3*n+1))
  assert got==want,(n,L,k,a,got,want)
 record('K',1000,'all moved segments and all relevant new positions versus disjoint/left-overlap/right-overlap prefix identities; deque optimization not timed')
def check_l():
 for _ in range(500):
  n=R.randrange(1,9);a=[R.randrange(4) for _ in range(n)];b=[R.randrange(4) for _ in range(n)];kids=[[] for _ in range(n)]
  for i in range(1,n):kids[R.randrange(i)].append(i)
  def dfs(u):
   sub=[u]
   for v in kids[u]:sub+=dfs(v)
   ca=Counter(a[v] for v in sub);cb=Counter(b[v] for v in sub);got=sum(max(ca[x],cb[x]) for x in set(ca)|set(cb) if x)!=0
   got=sum(max(ca[x],cb[x]) for x in set(ca)|set(cb) if x)<=len(sub)
   @lru_cache(None)
   def match(i,mask):
    if i==len(sub):return True
    return any(match(i+1,mask|1<<j) for j in range(len(sub)) if not mask>>j&1 and (a[sub[i]]==0 or b[sub[j]]==0 or a[sub[i]]==b[sub[j]]))
   assert got==match(0,0)
   return sub
  dfs(0)
 record('L',500,'every subtree of random trees versus exact wildcard bipartite matching; DSU traversal optimization not benchmarked')
import math,itertools,random

def solve3(matrix,b):
 a=[list(row)+[v] for row,v in zip(matrix,b)]
 for c in range(3):
  k=max(range(c,3),key=lambda r:abs(a[r][c]));a[c],a[k]=a[k],a[c];v=a[c][c]
  assert abs(v)>1e-12
  a[c]=[x/v for x in a[c]]
  for r in range(3):
   if r!=c:
    z=a[r][c];a[r]=[x-z*y for x,y in zip(a[r],a[c])]
 return [a[i][3] for i in range(3)]
def recover(n,r,p,rounding=False):
 v=[(math.cos(2*math.pi*i/n),math.sin(2*math.pi*i/n)) for i in (0,n//4,n//2,3*n//4)]
 def row(i,j):
  a,b=v[i],v[j];return [a[0]*b[1]-a[1]*b[0],a[1]-b[1],b[0]-a[0]]
 truth=[r*r,r*p[0],r*p[1]]
 def query(i,j):
  value=abs(sum(a*b for a,b in zip(row(i,j),truth)))/2
  return float(format(value,'.10g'))*2 if rounding else value*2
 pairs=[(0,1),(0,2),(1,2)];values=[query(*ij) for ij in pairs];a,b=pairs[max(range(3),key=lambda k:values[k])];extra=[(a,3),(b,3)];extra_values=[query(*ij) for ij in extra];candidates=[]
 for signs in itertools.product((-1,1),repeat=3):
  u,x,y=solve3([row(*ij) for ij in pairs],[s*w for s,w in zip(signs,values)])
  if u<=0:continue
  score=max(abs(abs(sum(c*d for c,d in zip(row(*ij),(u,x,y))))-val)/(1+val) for ij,val in zip(extra,extra_values));distance=math.hypot(x,y)/math.sqrt(u);candidates.append((score,distance))
 return min(candidates)[1]

def check_e():
 rng=random.Random(20251026);cases=0
 for n in range(4,201):
  for r in (1,3,100):
   pts=[(0,0),(r,0),(-r,0),(10000,0),(0,-10000),(r/2,r/2)]
   pts += [(rng.uniform(-1,1)*7000,rng.uniform(-1,1)*7000) for _ in range(10)]
   for p in pts:
    for rounding in (False,True):
     got=recover(n,r,p,rounding);want=math.hypot(*p);assert abs(got-want)/max(1,want)<=1e-4,(n,r,p,rounding,got,want);cases+=1
 record('E',cases,'five-query signed-area reconstruction for every N4..200, radii1/3/100, center/vertex/far/random points, both full precision and 10 significant digit replies')

def main():
 for f in (check_a,check_b,check_c,check_d,check_e,check_g,check_j,check_k,check_l):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 report={'scope':'2025 ICPC Chengdu A B C D E G J K L','seed':20251025,'status':'passed','limitations':'Small-case algorithm checks only; no online submissions or extreme-scale timing. K deque and L DSU-on-tree optimization are explained but not performance-tested.','checks':checks,'content_sha256':{f'icpc-chengdu-{x}.md':hashlib.sha256((root/'editorials/2025'/f'icpc-chengdu-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_chengdu_2025.json');args=p.parse_args();args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
