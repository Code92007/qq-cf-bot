#!/usr/bin/env python3
from pathlib import Path
from itertools import product,combinations,permutations
from collections import deque,Counter
from functools import lru_cache
from math import isqrt
import random,json,hashlib,argparse
R=random.Random(20241020);checks={}
def rec(x,n,m):checks[x]={'cases':n,'method':m,'passed':True};print(x,n,flush=True)
def computer(L,U):
 graph=[[]];free={0:0}
 def F(k):
  if k not in free:
   child=F(k-1);free[k]=len(graph);graph.append([(child,0),(child,1)])
  return free[k]
 def build(p,k):
  lo=p<<k;hi=((p+1)<<k)-1
  if hi<L or lo>U:return None
  if L<=lo and hi<=U:return F(k)
  edges=[]
  for bit in (0,1):
   child=build(2*p+bit,k-1)
   if child is not None:edges.append((child,bit))
  node=len(graph);graph.append(edges);return node
 edges=[]
 for length in range(1,U.bit_length()+1):
  node=build(1,length-1)
  if node is not None:edges.append((node,1))
 source=len(graph);graph.append(edges);return graph,source

def check_a():
 cases=0
 for L in range(1,65):
  for U in range(L,65):
   g,s=computer(L,U);numbers=[]
   def dfs(u,text):
    if not g[u]:assert text and text[0]=='1';numbers.append(int(text,2))
    for v,b in g[u]:dfs(v,text+str(b))
   dfs(s,'');assert sorted(numbers)==list(range(L,U+1));assert len(g)<=100 and max(map(len,g))<=200;cases+=1
 for _ in range(1000):
  L=R.randrange(1,10**6+1);U=R.randrange(L,10**6+1);g,s=computer(L,U);indeg=[0]*len(g)
  for u,edges in enumerate(g):
   for v,b in edges:assert v<u;indeg[v]+=1
  assert [i for i,x in enumerate(indeg) if x==0]==[s] and [i for i,x in enumerate(g) if not x]==[0] and len(g)<=100
  count=[1]+[0]*(len(g)-1)
  for u in range(1,len(g)):count[u]=sum(count[v] for v,b in g[u])
  assert count[s]==U-L+1;cases+=1
 rec('A',cases,'all accepted DAG paths for every interval in1..64, plus topological/source/sink/node/count checks on1000 full-range random intervals')
def check_c():
 direction='NESW';steps=[(0,1),(1,0),(0,-1),(-1,0)]
 for _ in range(1000):
  n=R.randrange(1,11);dirs=[R.randrange(4)];dist=[R.randrange(1,11) for i in range(n)]
  for i in range(1,n):dirs.append((dirs[-1]+R.choice((1,3)))%4)
  plan=[('Z',dist[0])]
  for i in range(1,n):plan.extend([('R' if (dirs[i]-dirs[i-1])%4==1 else 'L',0),('Z',dist[i])])
  facing=dirs[0];x=y=0
  for op,d in plan:
   if op=='Z':x+=steps[facing][0]*d;y+=steps[facing][1]*d
   else:facing=(facing+(1 if op=='R' else -1))%4
  want=tuple(sum(steps[z][j]*d for z,d in zip(dirs,dist)) for j in range(2));assert (x,y)==want and len(plan)<=20 and plan[0][0]=='Z'
 rec('C',1000,'relative-command simulator versus independent absolute displacement on random valid routes')
def invite(n,edges,busy):
 normal=set(range(n))-busy
 if not normal:return None
 graph=[[] for _ in range(n)]
 for u,v in edges:graph[u].append(v);graph[v].append(u)
 root=min(normal);seen={root};q=[root];plan=[]
 for u in q:
  add=[]
  for v in graph[u]:
   if v not in seen:
    seen.add(v);add.append(v)
    if v not in busy:q.append(v)
  if add:plan.append((u,add))
 return plan if len(seen)==n else None

def check_g():
 cases=0
 for n in range(2,6):
  possible=list(combinations(range(n),2))
  for mask in range(1<<len(possible)):
   edges=[e for i,e in enumerate(possible) if mask>>i&1]
   if any(not any(v in e for e in edges) for v in range(n)):continue
   for bmask in range(1<<n):
    busy={i for i in range(n) if bmask>>i&1};plan=invite(n,edges,busy);states={1<<i for i in range(n) if i not in busy};queue=list(states)
    for s in queue:
     for u,v in edges:
      for a,b in ((u,v),(v,u)):
       if s>>a&1 and a not in busy and not s>>b&1:
        t=s|1<<b
        if t not in states:states.add(t);queue.append(t)
    assert (plan is not None)==((1<<n)-1 in states)
    if plan:
     seen={plan[0][0]};used=set()
     for u,add in plan:
      assert u in seen and u not in busy and u not in used and add;used.add(u)
      for v in add:assert v not in seen and (min(u,v),max(u,v)) in edges;seen.add(v)
     assert len(seen)==n
    cases+=1
 rec('G',cases,'all no-isolated graphs through n5 and all busy subsets versus exhaustive meeting-membership transitions, then replay every emitted invitation')
def tree_total(pa):
 n=len(pa);kids=[[] for _ in pa]
 for v in range(1,n):kids[pa[v]].append(v)
 size=[1]*n;S=[0]*n;ans=0
 for u in range(n-1,-1,-1):
  pref=0
  for v in kids[u]:size[u]+=size[v];ans+=2*pref*S[v];pref+=S[v]
  S[u]=size[u]**2+pref
  if u:ans+=(size[u]*(n-size[u]))**2+2*(n-size[u])**2*(S[u]-size[u]**2)
 return ans
def check_l():
 for _ in range(1000):
  n=R.randrange(2,15);pa=[-1]+[R.randrange(i) for i in range(1,n)];g=[[] for _ in pa]
  for v in range(1,n):g[pa[v]].append((v,v));g[v].append((pa[v],v))
  paths=[]
  for s in range(n):
   q=[(s,-1,0)]
   for u,p,mask in q:
    if u>s:paths.append(mask)
    for v,edge in g[u]:
     if v!=p:q.append((v,u,mask|1<<edge))
  want=sum(bin(a&b).count('1')**2 for a,b in product(paths,repeat=2));assert tree_total(pa)==want
 rec('L',1000,'all ordered pairs of actual path edge masks on random trees versus linear subtree-square aggregation')
def check_m():
 for n in range(1,2001):
  d=sorted({z for i in range(1,isqrt(n)+1) if n%i==0 for z in (i,n//i)});got=1+sum((b-a)*(n//a) for a,b in zip(d,d[1:]));want=0
  for b in range(1,n+1):
   i=b
   while i>=2 and n%i:i-=1
   want+=n//i
  assert got==want
 rec('M',2000,'literal execution of the statement pseudocode for every b and n<=2000 versus divisor interval grouping')
import heapq,bisect
from fractions import Fraction

def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def hull(points):
 p=sorted(points);low=[];high=[]
 for x in p:
  while len(low)>1 and cross(low[-2],low[-1],x)<=0:low.pop()
  low.append(x)
 for x in p[::-1]:
  while len(high)>1 and cross(high[-2],high[-1],x)<=0:high.pop()
  high.append(x)
 return low[:-1]+high[:-1]
def area2(p):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1])))
def concave(points):
 H=hull(points);inside=[p for p in points if p not in H]
 if not inside:return -1
 K=hull(inside) if len(inside)>1 else inside
 if len(K)<=2:loss=min(cross(a,b,p) for a,b in zip(H,H[1:]+H[:1]) for p in K)
 else:
  j=min(range(len(K)),key=lambda j:cross(H[0],H[1],K[j]));loss=10**100
  for a,b in zip(H,H[1:]+H[:1]):
   moved=0
   while moved<len(K) and cross(a,b,K[(j+1)%len(K)])<=cross(a,b,K[j]):j=(j+1)%len(K);moved+=1
   loss=min(loss,cross(a,b,K[j]))
 return area2(H)-loss
def brute_polygon(points):
 best=-1;n=len(points)
 for length in range(4,n+1):
  for indices in combinations(range(n),length):
   first=indices[0]
   for tail in permutations(indices[1:]):
    if tail[0]>tail[-1]:continue
    p=[points[i] for i in (first,)+tail];signs=[cross(p[i-1],p[i],p[(i+1)%length])>0 for i in range(length)]
    if all(signs) or not any(signs):continue
    valid=True
    for i in range(length):
     for j in range(i+1,length):
      if j==i+1 or i==0 and j==length-1:continue
      a,b=p[i],p[(i+1)%length];c,d=p[j],p[(j+1)%length]
      if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:valid=False;break
     if not valid:break
    if valid:best=max(best,area2(p))
 return best
def check_b():
 cases=0
 for _ in range(80):
  n=R.randrange(3,8);points=[]
  while len(points)<n:
   p=(R.randrange(-8,9),R.randrange(-8,9))
   if p not in points and all(cross(a,b,p)!=0 for a,b in combinations(points,2)):points.append(p)
  assert concave(points)==brute_polygon(points),(points,concave(points),brute_polygon(points));cases+=1
 for _ in range(500):
  points=[]
  while len(points)<20:
   p=(R.randrange(-1000,1001),R.randrange(-1000,1001))
   if p not in points and all(cross(a,b,p)!=0 for a,b in combinations(points,2)):points.append(p)
  H=hull(points);inside=[p for p in points if p not in H];want=area2(H)-min(cross(a,b,p) for a,b in zip(H,H[1:]+H[:1]) for p in inside);assert concave(points)==want;cases+=1
 rec('B',cases,'all simple concave polygons over every vertex subset for random n<=7, plus rotating calipers versus all edge/interior-point pairs')
def farm(crops,m):
 crops=sorted(crops,reverse=True);L=sum(l for w,l,r in crops);P=sum(w*l for w,l,r in crops);C=[0];V=[0]
 for w,l,r in crops:C.append(C[-1]+r-l);V.append(V[-1]+w*(r-l))
 ans=0
 for i,(w,l,r) in enumerate(crops):
  rem=m-L+l;value=P-w*l
  if rem>=C[i]:value+=V[i]+(rem-C[i])*w
  elif rem:
   p=bisect.bisect_left(C,rem,0,i+1);value+=V[p-1]+(rem-C[p-1])*crops[p-1][0]
  ans=max(ans,value)
 return ans
def check_k():
 for _ in range(1000):
  n=R.randrange(1,6);crops=[]
  for i in range(n):l=R.randrange(1,4);crops.append((R.randrange(1,10),l,R.randrange(l,5)))
  m=R.randrange(sum(x[1] for x in crops),sum(x[2] for x in crops)+1);want=0
  def dfs(i,left,value,bad):
   nonlocal want
   if i==n:
    if left==0:want=max(want,value)
    return
   w,l,r=crops[i]
   for t in range(left+1):
    nb=bad+(not l<=t<=r)
    if nb<=1:dfs(i+1,left-t,value+w*t,nb)
  dfs(0,m,0,0);assert farm(crops,m)==want,(crops,m,farm(crops,m),want)
 rec('K',1000,'sorted prefix-capacity optimization versus every integral time allocation allowing at most one crop outside its bounds')
def vehicle(cap,stations):
 n=len(cap);m=len(stations);nxt=[m]*m;first=[m]*n
 for j in range(m-1,-1,-1):i=stations[j][1];nxt[j]=first[i];first[i]=j
 q=[(first[i],i,0) for i in range(n)];heapq.heapify(q);energy=cap[:];version=[0]*n;pos=0
 for j,(x,i) in enumerate(stations):
  delta=x-pos
  while delta:
   while q and (q[0][2]!=version[q[0][1]] or energy[q[0][1]]==0):heapq.heappop(q)
   if not q:return pos
   key,b,v=heapq.heappop(q);use=min(delta,energy[b]);energy[b]-=use;delta-=use;pos+=use
   if energy[b]:heapq.heappush(q,(key,b,v))
  version[i]+=1;energy[i]=cap[i];heapq.heappush(q,(nxt[j],i,version[i]))
 return pos+sum(energy)
def check_j():
 for _ in range(1000):
  n=R.randrange(1,5);cap=[R.randrange(1,5) for i in range(n)];m=R.randrange(1,7);xs=sorted(R.sample(range(1,15),m));stations=[(x,R.randrange(n)) for x in xs];at=dict(stations);states={tuple(cap)};position=0
  while states:
   position+=1;new=set()
   for energy in states:
    for i,x in enumerate(energy):
     if x:
      a=list(energy);a[i]-=1
      if position in at:a[at[position]]=cap[at[position]]
      new.add(tuple(a))
   if not new:break
   states=new
  assert vehicle(cap,stations)==position-1,(cap,stations,vehicle(cap,stations),position-1)
 rec('J',1000,'next-recharge priority heap versus exhaustive per-kilometer choices of battery, retaining all reachable charge vectors')
def marble(xs,speeds):
 mod=10**9+7;n=len(xs);m=len(speeds);h=(m+1)//2;events=sorted((Fraction(-x,v),j) for j,v in enumerate(speeds) for x in xs);c=[0]*m;P=[pow(n,m,mod)]+[0]*(h-1);ans=0
 for time,j in events:
  a=n-c[j];b=c[j];inv=pow(a,mod-2,mod);Q=[]
  for k in range(h):Q.append((P[k]-(b*Q[k-1] if k else 0))*inv%mod)
  ans=(ans+time.numerator*pow(time.denominator,mod-2,mod)*Q[h-1])%mod
  P=[((a-1)*Q[k]+((b+1)*Q[k-1] if k else 0))%mod for k in range(h)];c[j]+=1
 return ans*pow(pow(n,m,mod),mod-2,mod)%mod
def check_e():
 mod=10**9+7
 for _ in range(500):
  n=R.randrange(1,5);m=R.choice((1,3,5));xs=R.sample(range(-12,0),n);speeds=[R.randrange(1,7) for j in range(m)];total=Fraction(0)
  for choice in product(xs,repeat=m):total+=sorted(Fraction(-x,v) for x,v in zip(choice,speeds))[m//2]
  want=total/Fraction(n**m);assert marble(xs,speeds)==want.numerator*pow(want.denominator,mod-2,mod)%mod
 rec('E',500,'actual truncated remove/multiply generating-function sweep versus exact rational median times for every starting-position assignment, including simultaneous events')
def square(S,T):
 U=S+'#';V='$'+T;N=len(U)
 def right(A,a,B,b):
  ans=0
  while a+ans<len(A) and b+ans<len(B) and A[a+ans]==B[b+ans]:ans+=1
  return ans
 def left(A,a,B,b):
  ans=0
  while a-ans-1>=0 and b-ans-1>=0 and A[a-ans-1]==B[b-ans-1]:ans+=1
  return ans
 for d in range(N//2,0,-1):
  for anchor in range(0,N-d,d):
   la=anchor-left(U,anchor,U,anchor+d);ra=anchor+right(U,anchor,U,anchor+d)
   lb=anchor-left(U,anchor,V,anchor+d);rb=anchor+right(U,anchor,V,anchor+d)
   lc=anchor-left(V,anchor,V,anchor+d);rc=anchor+right(V,anchor,V,anchor+d)
   if ra-la+right(U,ra,V,ra+d)>=d:return 2*d
   if rb-lb+left(U,lb,U,lb+d)>=d:return 2*d
   if rb-lb+right(V,rb,V,rb+d)>=d:return 2*d
   if rc-lc+left(U,lc,V,lc+d)>=d:return 2*d
 return 0

def slow(S,T):
 n=len(S);ans=0
 for s in (S,T):
  for l in range(n):
   for r in range(l+2,n+1,2):
    v=s[l:r]
    if v[:len(v)//2]==v[len(v)//2:]:ans=max(ans,len(v))
 for l in range(n):
  for j in range(l,n):
   for r in range(j,n):
    v=S[l:j+1]+T[j:r+1]
    if len(v)%2==0 and v[:len(v)//2]==v[len(v)//2:]:ans=max(ans,len(v))
 return ans

def check_d():
 cases=0
 for n in range(1,7):
  for p in product('ab',repeat=2*n):
   S=''.join(p[:n]);T=''.join(p[n:]);assert square(S,T)==slow(S,T),(S,T,square(S,T),slow(S,T));cases+=1
 rec('D',cases,'all binary 2xn grids through n6: anchor/LCP-LCS interval criterion versus every right/down path and every square substring')

def factor_hybrid(initial,S,M,B=5):
 counts=Counter(initial);divs=[d for d in range(1,M+1) if M%d==0];dp={1:{0:0}}
 for v in divs:
  if not 2<=v<B:continue
  nd={d:states.copy() for d,states in dp.items()}
  for d,states in dp.items():
   power=v;c=1
   while M%(d*power)==0:
    target=nd.setdefault(d*power,{})
    for s,cost in states.items():
     ns=s+c*v
     if ns<=S:target[ns]=min(target.get(ns,10**30),cost+c-2*min(counts[v],c))
    c+=1;power*=v
  dp=nd
 structures={}
 for d,states in dp.items():
  sums=sorted(states);pre=[];best=10**30
  for s in sums:best=min(best,states[s]-s);pre.append(best)
  size=1
  while size<len(sums):size*=2
  tree=[10**30]*(2*size)
  for i,s in enumerate(sums):tree[size+i]=states[s]+s
  for i in range(size-1,0,-1):tree[i]=min(tree[2*i],tree[2*i+1])
  structures[d]=(sums,pre,size,tree)
 def query(d,r):
  if d not in structures or r<0:return 10**30
  sums,pre,size,tree=structures[d];cut=r-counts[1];pos=bisect.bisect_right(sums,cut)-1;ans=pre[pos]+r-2*counts[1] if pos>=0 else 10**30;l=bisect.bisect_left(sums,cut)+size;rr=bisect.bisect_right(sums,r)+size;best=10**30
  while l<rr:
   if l&1:best=min(best,tree[l]);l+=1
   if rr&1:rr-=1;best=min(best,tree[rr])
   l//=2;rr//=2
  return min(ans,best-r)
 best=10**30
 def dfs(rem,last,total,cost,previous,repeat):
  nonlocal best
  best=min(best,cost+query(rem,S-total))
  for v in divs:
   if v<last or v<B or rem%v or total+v>S:continue
   count=repeat+1 if v==previous else 1
   dfs(rem//v,v,total+v,cost+(-1 if count<=counts[v] else 1),v,count)
 dfs(M,B,0,0,-1,0)
 return len(initial)+best if best<10**25 else -1
@lru_cache(None)
def sum_partitions(total,least=1):
 if total==0:return ((),)
 return tuple((x,)+tail for x in range(least,total+1) for tail in sum_partitions(total-x,x))
def check_i():
 import math
 cases=0
 for _ in range(1500):
  S=R.randrange(1,23);M=R.randrange(1,151);initial=[R.randrange(1,25) for i in range(R.randrange(1,10))];cnt=Counter(initial);want=10**9
  for target in sum_partitions(S):
   if math.prod(target)!=M:continue
   to=Counter(target);want=min(want,sum(abs(cnt[x]-to[x]) for x in cnt.keys()|to.keys()))
  if want==10**9:want=-1
  for B in (3,5,10):assert factor_hybrid(initial,S,M,B)==want,(initial,S,M,B,factor_hybrid(initial,S,M,B),want);cases+=1
 rec('I',cases,'small-factor grouped DP, sorted large-factor DFS and actual segment-tree joining queries at three thresholds versus all integer partitions of the target sum and multiset edit distance')

def main():
 for f in (check_a,check_b,check_c,check_d,check_e,check_g,check_i,check_j,check_k,check_l,check_m):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';out={'scope':'2024 CCPC Harbin A B C D E G I J K L M','seed':20241020,'status':'passed','limitations':'Independent small-case checks only; no online judge submissions or maximum-size runtime tests.','checks':checks,'content_sha256':{f'ccpc-haerbin-{x}.md':hashlib.sha256((root/'editorials/2024'/f'ccpc-haerbin-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_haerbin_2024.json');args=p.parse_args();args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
