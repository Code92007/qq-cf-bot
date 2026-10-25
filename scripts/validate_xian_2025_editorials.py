#!/usr/bin/env python3
"""Independent small-case verification of the 2025 Xi'an explanations."""
from pathlib import Path
from itertools import product,permutations,combinations
from functools import lru_cache
from collections import deque
import random,heapq,json,hashlib,argparse
R=random.Random(20251019);checks={}
def rec(x,n,m):checks[x]={'cases':n,'method':m,'passed':True};print(x,n,flush=True)
def feasible(cnt,L,Rr):
 n=sum(cnt);return all(2*cnt[c]-n+(L==c)+(Rr==c)<=1 for c in range(3))
@lru_cache(None)
def arrange(cnt,L,Rr):
 if not sum(cnt):return () if L!=Rr or L==-1 else None
 for c in range(3):
  if cnt[c] and c!=L:
   rest=list(cnt);rest[c]-=1;tail=arrange(tuple(rest),c,Rr)
   if tail is not None:return (c,)+tail
 return None
def check_b():
 cases=0
 for n in range(10):
  for a in range(n+1):
   for b in range(n-a+1):
    cnt=(a,b,n-a-b)
    for L,Rr in product(range(-1,3),repeat=2):
     assert feasible(cnt,L,Rr)==(arrange(cnt,L,Rr) is not None),(cnt,L,Rr)
     if feasible(cnt,L,Rr):
      counts=list(cnt);out=[];left=L
      while sum(counts):
       for c in range(3):
        if counts[c] and c!=left:
         counts[c]-=1
         if feasible(counts,c,Rr):out.append(c);left=c;break
         counts[c]+=1
       else:raise AssertionError('no greedy continuation')
      assert len(out)==n and all(x!=y for x,y in zip(([L] if L!=-1 else [])+out,out+([Rr] if Rr!=-1 else []))) if L!=-1 and Rr!=-1 else True
     cases+=1
 for _ in range(300):
  n=R.randrange(1,10);s=[R.randrange(3) for _ in range(n)]
  good=[]
  for length in range(1,n+1):
   found=False
   for l in range(n-length+1):
    r=l+length-1
    outside=all(s[i]!=s[i+1] for i in range(n-1) if i<l-1 or i>r)
    cnt=tuple(s[l:r+1].count(c) for c in range(3));L=s[l-1] if l else -1;Rr=s[r+1] if r+1<n else -1
    fast=outside and feasible(cnt,L,Rr);slow=outside and arrange(cnt,L,Rr) is not None;assert fast==slow
    found|=fast
   good.append(found)
  assert good==sorted(good);cases+=1
 rec('B',cases,'all 3-color count vectors through length9 with 16 boundary choices versus recursive arrangements; random full interval monotonicity')
def penguins(a,target):
 n=len(a);d=[1 if a[target[i]]>a[i] else -1 for i in range(n)];followers=[[] for _ in a];q=[];ver=[0]*n;stop=[None]*n
 for i,j in enumerate(target):
  followers[j].append(i)
  if d[i]!=d[j]:heapq.heappush(q,(abs(a[j]-a[i]),i,0))
 while q:
  time,i,v=heapq.heappop(q)
  if stop[i] is not None or ver[i]!=v:continue
  stop[i]=time;pos=2*a[i]+d[i]*time
  for j in followers[i]:
   if stop[j] is None:ver[j]+=1;heapq.heappush(q,((pos-2*a[j])//d[j],j,ver[j]))
 return stop
def check_f():
 for _ in range(1000):
  n=R.randrange(2,9);a=R.sample(range(-15,16),n);target=[R.choice([j for j in range(n) if j!=i]) for i in range(n)];got=penguins(a,target);pos=[2*x for x in a];d=[1 if a[target[i]]>a[i] else -1 for i in range(n)];stop=[None]*n
  for time in range(1,500):
   for i in range(n):
    if stop[i] is None:pos[i]+=d[i]
   newly=[i for i in range(n) if stop[i] is None and pos[i]==pos[target[i]]]
   for i in newly:stop[i]=time
   if all(x is not None for x in stop):break
  assert stop==got,(a,target,got,stop)
 rec('F',1000,'priority events versus simultaneous integer-time simulation with all contacts processed together')
def check_g():
 cases=0
 for n in range(1,7):
  for _ in range(30):
   a=[R.randrange(-3,4) for _ in range(n)]
   def calc(p):
    s=0
    for x in p:s+=1 if s>=x else -1
    return s
   vals=[calc(p) for p in set(permutations(a))];assert (calc(sorted(a)),calc(sorted(a,reverse=True)))==(max(vals),min(vals));cases+=1
 rec('G',cases,'all distinct voter permutations for random n<=6 arrays')
def check_i():
 for _ in range(500):
  n=R.randrange(2,35);pa=[-1]+[R.randrange(i) for i in range(1,n)];g=[[] for _ in range(n)]
  for i in range(1,n):g[i].append(pa[i]);g[pa[i]].append(i)
  A=[[0]*n for _ in range(n)]
  for s in range(n):
   q=[(s,-1,s+1)]
   for u,p,xor in q:
    A[s][u]=xor
    for v in g[u]:
     if v!=p:q.append((v,u,xor^(v+1)))
  anc=[[A[0][x]^A[x][y]^A[y][0]==x+1 for y in range(n)] for x in range(n)]
  dep=[sum(anc[x][y] for x in range(n) if x!=y) for y in range(n)];edges={(x,y) for x in range(n) for y in range(n) if anc[x][y] and dep[y]==dep[x]+1}
  assert edges=={(pa[y],y) for y in range(1,n)}
 rec('I',500,'path-XOR matrices from random trees, recovered ancestor depths and all original parent edges')
def check_j():
 cases=0
 for _ in range(60):
  kids=[[]];pa=[-1]
  for grow in range(R.randrange(1,4)):
   leaves=[i for i in range(len(kids)) if not kids[i]];u=R.choice(leaves)
   for z in range(2):v=len(kids);kids[u].append(v);kids.append([]);pa.append(u)
  n=len(kids);cost=[R.randrange(1,10) for _ in range(n)];f=cost[:];w=[0]*n;pref=[0]*n
  for u in range(n-1,-1,-1):
   if kids[u]:f[u]=min(cost[u],sum(sorted(f[v] for v in kids[u])[:2]))
  for u in range(1,n):w[u]=min(f[v] for v in kids[pa[u]] if v!=u);pref[u]=pref[pa[u]]+w[u]
  for x in range(n):
   dist={1<<x:0};q=[(0,1<<x)]
   while q:
    value,s=heapq.heappop(q)
    if value!=dist[s]:continue
    nxt=[]
    for v in range(n):
     if not s>>v&1:nxt.append((s|1<<v,cost[v]))
    for p in range(n):
     if s>>p&1:continue
     for a,b in combinations(kids[p],2):
      if s>>a&1 and s>>b&1:nxt.append(((s^(1<<a)^(1<<b))|1<<p,0))
    for t,c in nxt:
     if value+c<dist.get(t,10**9):dist[t]=value+c;heapq.heappush(q,(value+c,t))
   ancestors=set();u=x
   while u!=-1:ancestors.add(u);u=pa[u]
   for y in range(n):
    got=pref[x]-pref[y] if y in ancestors else -1;want=dist.get(1<<y,-1);assert got==want;cases+=1
 rec('J',cases,'all source/target pairs on small branching trees versus Dijkstra over owned-node subsets with buy/merge operations')
def check_k():
 cases=0
 for n in range(1,5):
  perms=list(permutations(range(n)));arrays=list(product(range(n),repeat=n));match={b:any(all(p[i]&b[i]==b[i] for i in range(n)) for p in perms) for b in arrays}
  for a in arrays:
   seen={a};q=[a]
   for s in q:
    for p in perms:
     t=tuple(s[i]&p[i] for i in range(n))
     if t not in seen:seen.add(t);q.append(t)
   for b in arrays:
    got=a==b or (all(a[i]&b[i]==b[i] for i in range(n)) and match[b]);assert got==(b in seen);cases+=1
 rec('K',cases,'all arrays a,b for n<=4 and full closure under every permutation-AND operation versus matching criterion')
def check_l():
 for _ in range(1000):
  n=R.randrange(1,10);a=sorted(R.randrange(1,20) for _ in range(n));p=n-1;got=[0]*(n+1)
  for k in range(n,2,-1):
   while p+1>=k and sum(a[p-k+1:p+1])<=2*a[p]:p-=1
   if p+1>=k:got[k]=sum(a[p-k+1:p+1])
  want=[0]*(n+1)
  for k in range(3,n+1):want[k]=max([0]+[sum(v) for v in combinations(a,k) if sum(v)>2*max(v)])
  assert got==want
 rec('L',1000,'descending-size monotone pointer versus all stick subsets, including no-solution larger k followed by feasible smaller k')
def main():
 for f in (check_b,check_f,check_g,check_i,check_j,check_k,check_l):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 out={'scope':'2025 ICPC Xian B F G I J K L','seed':20251019,'status':'passed','limitations':'Small-case verification only; no online judge submissions or maximum-size runtime tests. K verifies the matching criterion and operation closure, not a production Dinic implementation.','checks':checks,'content_sha256':{f'icpc-xian-{x}.md':hashlib.sha256((root/'editorials/2025'/f'icpc-xian-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_xian_2025.json');args=p.parse_args();args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
