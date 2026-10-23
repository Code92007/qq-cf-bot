#!/usr/bin/env python3
"""Independent small-case checks for published 2025 Nanjing explanations (Python 3.10+)."""
import argparse
from collections import deque
from functools import cmp_to_key, lru_cache
from itertools import combinations, permutations, product
from math import comb, gcd
from pathlib import Path
import hashlib
import json
import random

R=random.Random(20251109)
REPORT={}

def record(letter,cases,method):
    REPORT[letter]={'passed':True,'cases':cases,'method':method}
    print(letter,cases,flush=True)

# The decision tree uses only the observed drop, not the hidden coordinates.
def solve(n,m,ask):
 k=0
 for k in range(1,n//2+1):
  if ask('D')<=m:break
 else:
  if n%2:
   k=n//2+1;t=0
   while True:
    t+=1;d=ask('L')
    if d<=n-k+1:return k,t if d<=n-2*k+2 else m+1-t
 if k>1:
  d=ask('L')
  if d==n-2*k:return k,1
  if d==n-2*k+1:return n+1-k,1
  if d==n-k+1:row=n+1-k
  elif ask('U')>0:row=k
  else:
   ask('R');ask('R');return (k if ask('D')==0 else n+1-k),m
  t=0
  while True:
   t+=1;d=ask('L')
   if d<=n-k:return row,t+1 if d<=n-2*k+1 else m-t
 d=ask('L')
 if d==n-2:return 1,1
 if d==n:row=n;direction='D'
 elif ask('U')>0:row=1;direction='U'
 else:
  if ask('U')==m-2:return 1,m
  return (n,m) if ask('L')==n-2 else (n,1)
 t=0
 while True:
  t+=1
  if ask('L')<n:break
 return row,t+1 if ask(direction)>m-2*t-2 else m-t

def verify(n,m,r,c):
 allbits=(1<<(n*m))-1;hole=1<<((r-1)*m+c-1);live=allbits^hole
 left=sum(1<<(i*m) for i in range(n));right=left<<(m-1);count=0
 def ask(d):
  nonlocal live,count
  before=live.bit_count();count+=1
  if d=='D':live=(live<<m)&allbits
  elif d=='U':live>>=m
  elif d=='L':live=(live&~left)>>1
  else:live=((live&~right)<<1)&allbits
  live&=~hole
  assert count<=n+m+10,(n,m,r,c,count)
  return before-live.bit_count()
 out=solve(n,m,ask);assert out==(r,c),(n,m,r,c,out,count)
 return count
def check_a():
    cases=0
    for n in range(3,31):
        for m in range(3,31):
            for r in range(1,n+1):
                for c in range(1,m+1):verify(n,m,r,c);cases+=1
    record('A',cases,'every allowed board size and hole position; exact moving-bitboard simulation and query bound')

def check_b():
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    def compare(a,b):
        h=lambda p:int(p[1]<0 or p[1]==0 and p[0]<0)
        return h(a)-h(b) if h(a)!=h(b) else -((cross(a,b)>0)-(cross(a,b)<0))
    for _ in range(300):
        a=[(R.randrange(-4,5),R.randrange(-4,5)) for _ in range(R.randrange(1,10))];groups={}
        for x,y in a:
            if not(x or y):continue
            d=gcd(x,y);p=(x//d,y//d);groups[p]=groups.get(p,0)+1
        v=sorted(groups,key=cmp_to_key(compare));n=len(v);arr=v+v;ans=0;r=0;total=0
        for l in range(n):
            while r<l+n and (r==l or cross(arr[l],arr[r])>0):total+=groups[arr[r]];r+=1
            ans=max(ans,total);total-=groups[arr[l]]
        want=max(sum(x*u+y*v<0 for x,y in a) for u in range(-9,10) for v in range(-9,10))
        assert ans==want,(a,ans,want)
    record('B',300,'integer-direction enumeration versus grouped angular sweep, including zeros and opposite rays')

def check_c():
    for n in range(1,301):assert (n%2==0)==any(n%a==0 and n%(n-a)==0 for a in range(1,n))
    record('C',300,'enumerate all positive splits')

def check_e():
    for _ in range(300):
        n=R.randrange(2,16);par=[-1]+[R.randrange(i) for i in range(1,n)];children=[[] for _ in range(n)];color=[R.randrange(2) for _ in range(n)]
        for v in range(1,n):children[par[v]].append(v)
        got=[-10**9]*n
        for flip in range(2):
            def dfs(u):
                s=1 if color[u]^flip==0 else -1;z=-1 if s==1 else 3;cur={s:z}
                if s>=0:got[u]=max(got[u],z)
                for v in children[u]:
                    sub=dfs(v)
                    def threshold(a,i):return max([val for d,val in a.items() if d>=i]+[-10**9])
                    h=max(abs(d) for d in sub)
                    for i in range(-h,h+1):got[u]=max(got[u],threshold(cur,-i)+threshold(sub,i))
                    for d,val in sub.items():cur[d+s]=max(cur.get(d+s,-10**9),val+z)
                    got[u]=max(got[u],threshold(cur,0))
                return cur
            dfs(0)
        want=[-10**9]*n
        for a in range(n):
            pa=[];u=a
            while u>=0:pa.append(u);u=par[u]
            for b in range(a,n):
                pb=[];u=b
                while u not in pa:pb.append(u);u=par[u]
                path=pa[:pa.index(u)+1]+pb;c=sum(color[x]==0 for x in path);w=len(path)-c
                want[u]=max(want[u],len(path)-2*abs(c-w))
        assert got==want,(par,color,got,want)
    record('E',300,'threshold DP and both color passes versus enumeration of every simple path; excludes optimized deque')

class DSU:
    def __init__(self,n):self.p=list(range(n))
    def find(self,x):
        while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
        return x
    def join(self,u,v):
        u=self.find(u);v=self.find(v)
        if u==v:return False
        self.p[u]=v;return True

def check_f():
    cases=0
    for _ in range(80):
        n=R.randrange(2,7);ds=[DSU(n) for _ in range(16)];adj=[[] for _ in range(n)]
        def add(s,u,v):
            if not ds[s].join(u,v):return
            for b in range(4):
                if s>>b&1:add(s^(1<<b),u,v)
        for step in range(35):
            u,v=R.sample(range(n),2)
            if R.random()<0.6:
                w=R.randrange(16);adj[u].append((v,w));adj[v].append((u,w));add(w,u,v)
            else:
                ans=-1
                if ds[0].find(u)==ds[0].find(v):
                    ans=0
                    for b in range(3,-1,-1):
                        s=ans|(1<<b)
                        if ds[s].find(u)==ds[s].find(v):ans=s
                seen={(u,15)};q=deque(seen)
                while q:
                    x,w=q.popleft()
                    for y,z in adj[x]:
                        state=(y,w&z)
                        if state not in seen:seen.add(state);q.append(state)
                want=max([w for x,w in seen if x==v]+[-1]);assert ans==want;cases+=1
    record('F',cases,'incremental subset DSUs versus exhaustive vertex-and-mask reachability')

def check_g():
    for _ in range(250):
        n=R.randrange(1,8);v=[R.randrange(1,20) for _ in range(n)];l=[R.randrange(8) for _ in range(n)];t=R.randrange(9)
        vs=sorted(v);ls=sorted(l,reverse=True);d=0
        while d<n and vs[d]<t*ls[d]:d+=1
        got=sum(vs[d:])-t*sum(ls[d:]);want=0
        def parts(i,groups):
            nonlocal want
            if i==n:
                want=max(want,sum(max(0,max(v[j] for j in g)-t*min(l[j] for j in g)) for g in groups));return
            for g in groups:g.append(i);parts(i+1,groups);g.pop()
            parts(i+1,groups+[[i]])
        parts(0,[]);assert got==want,(v,l,t,got,want)
    record('G',250,'all set partitions of buckets versus extreme-pair deletion')

def prefix(s):
    p=[0]*len(s)
    for i in range(1,len(s)):
        j=p[i-1]
        while j and s[j]!=s[i]:j=p[j-1]
        if s[j]==s[i]:j+=1
        p[i]=j
    return p

def fast_h(s):
    n=len(s);f=[[0]*(n+2) for _ in range(n+2)]
    for r in range(1,n+1):
        pat=s[r-1:];pi=prefix(pat);cnt=[0]
        for i in range(len(pat)):cnt.append(cnt[pi[i]]+1)
        z=0
        for l in range(1,r):
            while z and (z==len(pat) or pat[z]!=s[l-1]):z=pi[z-1]
            if z<len(pat) and pat[z]==s[l-1]:z+=1
            f[l][r]=cnt[z]
    prev=[0]*(n+2);col=[0]*(n+2);ans=0
    for l in range(n,0,-1):
        pat=s[l-1:];pi=prefix(pat);cnt=[0]
        for i in range(len(pat)):cnt.append(cnt[pi[i]]+1)
        h=[0]*(n+2);z=0
        for L in range(1,len(pat)+1):
            while z and pat[z]!=pat[L-1]:z=pi[z-1]
            if pat[z]==pat[L-1]:z+=1
            while 2*z>L:z=pi[z-1]
            h[l+L-1]=cnt[z]
            # Independent direct border count checks this optimization too.
            assert cnt[z]==sum(pat[:b]==pat[L-b:L] for b in range(1,L//2+1))
        row=[0]*(n+2)
        for r in range(l,n+1):
            col[r]+=h[r];row[r]=prev[r]+row[r-1]-prev[r-1]+col[r]-h[r]
            if l>=2 and r<n:ans+=f[l-1][r+1]*row[r]
        prev=row
    return ans

def brute_h(s):
    n=len(s);ans=0
    for a in range(n):
      for b in range(a+1,n+1):
       for c in range(b,n):
        for d in range(c+1,n+1):
         for e in range(d,n):
          for f in range(e+1,n+1):
           if f-e>=d-c or not s[c:d].endswith(s[e:f]):continue
           for g in range(f,n):
            h=g+b-a
            if h<=n and s[g:h]==s[a:b]:ans+=1
    return ans

def check_h():
    cases=0
    for n in range(1,10):
        for bits in product('ab',repeat=n):
            s=''.join(bits);assert fast_h(s)==brute_h(s),s;cases+=1
    assert fast_h('penpineappleapplepen')==1502
    record('H',cases+1,'all binary strings through length 9 against literal four-substring enumeration, plus published long example')

def check_i():
    for _ in range(250):
        n=R.randrange(1,5);budget=R.randrange(1,12);days=[(R.randrange(10),R.randrange(6),R.randrange(10),R.randrange(6),R.randrange(6),R.choice([0,25,50,75,100])) for _ in range(n)]
        prev=[[0.0]*4 for _ in range(budget+1)]
        for a,b,c,d,e,p in reversed(days):
            row=[[None]*4 for _ in range(budget+1)]
            for money in range(budget+1):
                for mask in range(4):
                    options=[]
                    for cost,gain,taxi in [(b,a,False),(d,c,mask==3)]:
                        if taxi:cost+=e
                        if cost>money:continue
                        branches=[(1.0,0)] if taxi else [(p/100,mask|1),(1-p/100,mask|2)]
                        active=[(prob,prev[money-cost][m]) for prob,m in branches if prob>0]
                        if all(value is not None for prob,value in active):options.append(gain+sum(prob*value for prob,value in active))
                    if options:row[money][mask]=max(options)
            prev=row
        # Brute policy tree retains full payment history rather than a bit mask.
        def oracle(i,money,history):
            if i==n:return 0.0
            a,b,c,d,e,p=days[i];values=[]
            for eat in (False,True):
                taxi=eat and 'A' in history and 'B' in history;cost=(d if eat else b)+(e if taxi else 0)
                if money<cost:continue
                branches=[(1.0,'')] if taxi else [(p/100,history+'A'),(1-p/100,history+'B')]
                v=[]
                for prob,hist in branches:
                    if prob>0:v.append((prob,oracle(i+1,money-cost,hist)))
                if all(x is not None for prob,x in v):values.append((c if eat else a)+sum(prob*x for prob,x in v))
            return max(values) if values else None
        assert prev[budget][0]==oracle(0,budget,'')
    record('I',250,'full history policy-tree enumeration versus four-state backward DP, including zero probability')

def tarjan(g,root,bad=False):
    n=len(g);depth=[-1]*n;low=[0]*n;cut=set()
    def dfs(u,pa,d):
        depth[u]=low[u]=d;children=0;mark=False
        for v in g[u]:
            if v==pa:continue
            if depth[v]<0:
                dfs(v,u,d+1);children+=1
                if low[v]>=depth[u]:mark=True
                low[u]=min(low[u],low[v])
            else:low[u]=min(low[u],low[v] if bad else depth[v])
        if pa>=0 and mark or pa<0 and children>1:cut.add(u)
    dfs(root,-1,0);return cut,depth

def check_j():
    cases=0
    for n in range(2,6):
      edges=list(combinations(range(n),2))
      for mask in range(1,1<<len(edges)):
        if n==5 and R.random()>0.1:continue
        chosen=[e for i,e in enumerate(edges) if mask>>i&1];g=[[] for _ in range(n)]
        for u,v in chosen:g[u].append(v);g[v].append(u)
        cut,depth=tarjan(g,0)
        if -1 in depth:continue
        bridge_vertices=set()
        for banned in chosen:
            d=DSU(n)
            for e in chosen:
                if e!=banned:d.join(*e)
            if len({d.find(i) for i in range(n)})>1:bridge_vertices.update(banned)
        want=cut-bridge_vertices;observed=set()
        orders=product(*(list(permutations(row)) for row in g)) if n<=4 else (tuple(R.sample(row,len(row)) for row in g) for _ in range(120))
        for order in orders:
            for root in range(n):observed|=cut-tarjan(order,root,True)[0]
        assert observed==want,(g,want,observed);cases+=1
    record('J',cases,'enumerate roots and neighbor orders for small connected graphs; compare with true cuts and brute bridges')

def check_k():
    cells=[(x,y) for x in range(1,10) for y in range(1,11)];index={p:i for i,p in enumerate(cells)}
    WIN=16200;LOSE=16201;rev=[[] for _ in range(16202)];out=[0]*16202;horse={}
    def sid(h,r,t):return (h*90+r)*2+t
    for h,(x,y) in enumerate(cells):
      for r,(rx,ry) in enumerate(cells):
       if h==r:continue
       moves=[]
       for dx,dy in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(-1,2),(1,-2),(-1,-2)]:
        leg=(x+dx//2,y) if abs(dx)==2 else (x,y+dy//2)
        dest=(x+dx,y+dy)
        if dest in index and leg!=(rx,ry):moves.append(index[dest])
       horse[h,r]=moves
       for to in moves:
        p=sid(h,r,0);child=LOSE if to==r else sid(to,r,1);rev[child].append(p);out[p]+=1
       for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        tx,ty=rx+dx,ry+dy
        while (tx,ty) in index:
         p=sid(h,r,1);to=index[tx,ty];child=WIN if to==h else sid(h,to,0);rev[child].append(p);out[p]+=1
         if to==h:break
         tx+=dx;ty+=dy
    winning={WIN};q=deque([WIN]);remaining=out[:]
    while q:
        child=q.popleft()
        for p in rev[child]:
            if p in winning:continue
            remaining[p]-=1
            if p%2==1 or remaining[p]==0:winning.add(p);q.append(p)
    cases=0
    for (h,r),moves in horse.items():
        rx,ry=cells[r]
        immediate=all(to!=r and (cells[to][0]==rx or cells[to][1]==ry) for to in moves)
        assert (sid(h,r,0) in winning)==immediate,(cells[h],cells[r]);cases+=1
    record('K',cases,'full 16020-state retrograde graph versus immediate-capture characterization on all 8010 initial positions')

def conv(a,b):
    c=[0]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):c[i+j]+=x*y
    return c

def check_m():
    for _ in range(200):
        n=R.randrange(3,10);xs=sorted(R.sample(range(-15,16),n));pts=[(x,x*x) for x in xs];X=[p[0] for p in pts];Y=[p[1] for p in pts]
        xy=conv(X[::-1],Y+Y);yx=conv(Y[::-1],X+X);f=[xy[n-1+d]-yx[n-1+d] for d in range(n)]
        want=[0]*(n+1)
        for k in range(3,n+1):
            for chosen in combinations(pts,k):want[k]+=sum(a*d-b*c for (a,b),(c,d) in zip(chosen,chosen[1:]+chosen[:1]))
            got=sum(f[d]*comb(n-1-d,k-2) for d in range(1,n-k+2));assert got==want[k]
        mod=998244353;fac=[1]
        for i in range(1,n+1):fac.append(fac[-1]*i%mod)
        inv=[pow(x,mod-2,mod) for x in fac]
        A=[f[n-1-t]*fac[t]%mod for t in range(n-1)];C=conv(A[::-1],inv[:n-1])
        for k in range(3,n+1):assert C[n-k]*inv[k-2]%mod==want[k]%mod
    record('M',200,'enumerate all polygon vertex subsets; verify both convolution indices with exact naive multiplication, not NTT')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    for check in (check_a,check_b,check_c,check_e,check_f,check_g,check_h,check_i,check_j,check_k,check_m):check()
    root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
    report={'scope':'2025 ICPC Nanjing A B C E F G H I J K M','status':'passed','seed':20251109,'limitations':'Independent checks of explanations; no online submissions, extreme-scale timing, optimized E deque or NTT implementation verification. A covers every valid hidden board state.','checks':REPORT,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-nanjing-*.md'))}}
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TOTAL',sum(x['cases'] for x in REPORT.values()))
