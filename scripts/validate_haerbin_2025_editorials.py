#!/usr/bin/env python3
"""Independent checks for published 2025 Harbin editorials."""
from pathlib import Path
from collections import deque,Counter
from itertools import product,combinations
from fractions import Fraction
from functools import reduce
from math import gcd
import random,json,hashlib,argparse
R=random.Random(20251109);checks={}
def rec(x,n,m):checks[x]={'cases':n,'method':m,'passed':True};print(x,n,flush=True)
def check_a():
 cases=0
 for n in range(1,5):
  for a in product(range(1,6),repeat=n):
   g=reduce(gcd,[abs(x-a[0]) for x in a],0)
   vals=[]
   for k in range(1,7):
    sums={0}
    for _ in range(k):sums={x+y for x in sums for y in a}
    val=reduce(gcd,sums);assert val==gcd(k*a[0],g);vals.append(val);cases+=1
   if g:
    bestk=g//gcd(g,a[0]);assert vals[bestk-1]==g and g not in vals[:bestk-1]
   else:assert vals==[k*a[0] for k in range(1,7)]
 rec('A',cases,'all arrays of length<=4 over 1..5; enumerate distinct repeated-choice sums for k<=6')
def sim(x,L,U,v,vl,vr,T,exact=False):
 t=Fraction(0) if exact else 0.;x=Fraction(x) if exact else float(x);T=Fraction(T) if exact else float(T)
 if not exact and vl==vr==0:
  w=U-L;z=(x-L+v*T)%(2*w);return L+min(z,2*w-z)
 cnt=0
 while t<T:
  if v>0:
   if v<=vr:return x+v*(T-t)
   dt=(U+vr*t-x)/(v-vr)
  else:
   if -v<=vl:return x+v*(T-t)
   dt=(x-L+vl*t)/(-v-vl)
  if dt>=T-t:return x+v*(T-t)
  x+=v*dt;t+=dt;v=-v;cnt+=1;assert cnt<100000
 return x
def check_b():
 for _ in range(1000):
  L=R.randrange(0,10);U=L+R.randrange(2,20);x=R.randrange(L+1,U);v=R.choice([i for i in range(-20,21) if i]);vl=R.randrange(21);vr=R.randrange(21);T=Fraction(R.randrange(1,200),R.randrange(1,20))
  got=sim(x,L,U,v,vl,vr,T);want=float(sim(x,L,U,v,vl,vr,T,True));assert abs(got-want)<1e-7*max(1,abs(want))
 rec('B',1000,'floating event simulation/static folding versus exact rational collision simulation')
def greedy_g(h):
 h=[r[:] for r in h];n=len(h);m=len(h[0]);ans=0
 for i in range(n):
  p=[];s=0
  for x in h[i]:s+=x;p.append(s)
  add=max(0,-min(p));ans+=add;p=[x+add for x in p]
  if i==n-1:ans+=p[-1];break
  for j in range(m-2,-1,-1):p[j]=min(p[j],p[j+1])
  last=0
  for j in range(m):h[i+1][j]+=p[j]-last;last=p[j]
 return ans
def flow_g(h):
 n=len(h);m=len(h[0]);N=n*m+2;s=N-2;t=N-1;g=[[] for _ in range(N)]
 def add(u,v,c):g[u].append([v,c,len(g[v])]);g[v].append([u,0,len(g[u])-1])
 for i in range(n):
  for j in range(m):
   v=i*m+j;x=h[i][j]
   if x>0:add(s,v,x)
   if x<0:add(v,t,-x)
   if i+1<n:add(v,v+m,10**9)
   if j+1<m:add(v,v+1,10**9)
 flow=0
 while True:
  pa=[None]*N;pa[s]=(-1,-1);q=deque([s])
  while q and pa[t] is None:
   u=q.popleft()
   for z,(v,c,back) in enumerate(g[u]):
    if c and pa[v] is None:pa[v]=(u,z);q.append(v)
  if pa[t] is None:break
  v=t;f=10**9
  while v!=s:u,z=pa[v];f=min(f,g[u][z][1]);v=u
  v=t
  while v!=s:u,z=pa[v];edge=g[u][z];edge[1]-=f;g[v][edge[2]][1]+=f;v=u
  flow+=f
 return sum(abs(x) for row in h for x in row)-2*flow
def check_g():
 cases=0
 for n,m in [(1,1),(1,3),(2,2)]:
  for a in product(range(-2,3),repeat=n*m):
   h=[list(a[i*m:(i+1)*m]) for i in range(n)];assert greedy_g(h)==flow_g(h),(h,greedy_g(h),flow_g(h));cases+=1
 for _ in range(1000):
  n=R.randrange(1,5);m=R.randrange(1,5);h=[[R.randrange(-5,6) for _ in range(m)] for _ in range(n)];assert greedy_g(h)==flow_g(h);cases+=1
 rec('G',cases,'row suffix-minimum greedy versus independent maximum-flow supply/deficit matching, exhaustive 2x2 and random grids')
def check_i():
 pts=[(x,y) for x in range(-3,4) for y in range(-3,4)];index={p:i for i,p in enumerate(pts)};basis={}
 delta=[(0,-1),(1,-1),(1,0),(0,1),(-1,1),(-1,0)]
 def reduce_mask(s,insert=False):
  while s:
   i=s.bit_length()-1
   if i in basis:s^=basis[i]
   elif insert:basis[i]=s;return 0
   else:return s
  return 0
 for x in range(-2,3):
  for y in range(-2,3):reduce_mask(sum(1<<index[x+dx,y+dy] for dx,dy in delta),True)
 small=[(x,y) for x in range(-1,2) for y in range(-1,2)]
 for mask in range(1<<len(small)):
  active=[p for j,p in enumerate(small) if mask>>j&1];coords=[Counter(p[0] for p in active),Counter(p[1] for p in active),Counter(-p[0]-p[1] for p in active)]
  want=all(v%2==0 for c in coords for v in c.values());got=reduce_mask(sum(1<<index[p] for p in active))==0;assert got==want
 rec('I',1<<len(small),'all 512 patterns in a 3x3 axial window; GF(2) span of actual six-neighbor flips versus three coordinate parities')
def check_l():
 cases=0
 for _ in range(250):
  n=R.randrange(1,6);m=R.randrange(2,7);cols=R.sample(range(1,m-1),R.randrange(min(4,m-2)+1));obs=sorted((c,R.randrange(n)) for c in cols);obsmap={c:(j,r) for j,(c,r) in enumerate(obs)}
  for mask in range(1<<len(obs)):
   def ok(r,c):
    if c not in obsmap:return True
    j,o=obsmap[c];return r>o if mask>>j&1 else r<o
   dist={(r,0):0 for r in range(n)};q=deque(dist)
   while q:
    r,c=q.popleft()
    for rr,cc in [(r-1,c),(r+1,c),(r,c+1)]:
     if 0<=rr<n and cc<m and ok(rr,cc) and (rr,cc) not in dist:dist[rr,cc]=dist[r,c]+1;q.append((rr,cc))
   got=min([dist.get((r,m-1),10**9) for r in range(n)])
   dp=[0]*n
   for c in range(1,m):
    allowed=[r for r in range(n) if ok(r,c)];nxt=[10**9]*n
    for r in allowed:nxt[r]=min([10**9]+[dp[u]+1+abs(r-u) for u in allowed])
    dp=nxt
   assert got==min(dp);cases+=1
 rec('L',cases,'all masks of random obstacle layouts; grid BFS versus independent per-column interval DP')
def longest(s):
 t=[];boundary=[0];w=[]
 for i,ch in enumerate(s):
  if ch=='w':t.extend('vv');w.extend([True,True]);boundary.extend([-1,i+1])
  else:t.append(ch);w.append(False);boundary.append(i+1)
 n=len(t);nxt=[n]*(n+1);prev=[-1]*n;v=-1
 for i in range(n):
  if not w[i]:v=i
  prev[i]=v
 for i in range(n-1,-1,-1):nxt[i]=i if not w[i] else nxt[i+1]
 def fix(l,r):
  if boundary[l]>=0 and boundary[r]>=0:return boundary[l],boundary[r]
  if boundary[l]<0 and boundary[r]<0:l+=1;r-=1
  else:
   d=min(nxt[l]-l,r-1-prev[r-1],(r-l)//2);l+=d;r-=d
   if l>=r:return 0,0
   if boundary[l]<0 or boundary[r]<0:l+=1;r-=1
  if l>=r:return 0,0
  assert boundary[l]>=0 and boundary[r]>=0,(s,t,l,r)
  return boundary[l],boundary[r]
 best=(0,1);odd=[0]*n;l=0;r=-1
 for i in range(n):
  k=1 if i>r else min(odd[l+r-i],r-i+1)
  while i-k>=0 and i+k<n and t[i-k]==t[i+k]:k+=1
  odd[i]=k;cur=fix(i-k+1,i+k)
  if cur[1]-cur[0]>best[1]-best[0]:best=cur
  if i+k-1>r:l=i-k+1;r=i+k-1
 even=[0]*n;l=0;r=-1
 for i in range(n):
  k=0 if i>r else min(even[l+r-i+1],r-i+1)
  while i-k-1>=0 and i+k<n and t[i-k-1]==t[i+k]:k+=1
  even[i]=k
  if k:
   cur=fix(i-k,i+k)
   if cur[1]-cur[0]>best[1]-best[0]:best=cur
  if i+k-1>r:l=i-k;r=i+k-1
 return s[best[0]:best[1]]
def slow(s):
 ans=0
 for l in range(len(s)):
  for r in range(l+1,len(s)+1):
   t=s[l:r].replace('w','vv')
   if t==t[::-1]:ans=max(ans,r-l)
 return ans

def check_j():
 cases=0
 for n in range(1,10):
  for p in product('ovw',repeat=n):
   s=''.join(p);got=longest(s);assert len(got)==slow(s),(s,got,slow(s));assert got.replace('w','vv')==got.replace('w','vv')[::-1];cases+=1
 rec('J',cases,'every ovw string through length9: full Manacher and constant-time boundary adjustment versus all original substrings')
def ntt(a,invert=False):
 mod=998244353;n=len(a);j=0
 for i in range(1,n):
  b=n>>1
  while j&b:j^=b;b>>=1
  j^=b
  if i<j:a[i],a[j]=a[j],a[i]
 length=2
 while length<=n:
  root=pow(3,(mod-1)//length,mod)
  if invert:root=pow(root,mod-2,mod)
  for i in range(0,n,length):
   w=1
   for j in range(i,i+length//2):
    u=a[j];v=a[j+length//2]*w%mod;a[j]=(u+v)%mod;a[j+length//2]=(u-v)%mod;w=w*root%mod
  length*=2
 if invert:
  inv=pow(n,mod-2,mod)
  for i in range(n):a[i]=a[i]*inv%mod
 return a
def triangles(strings):
 n=len(strings[0]);ans=0
 for color in '01':
  A,B,C=[[0]+[int(x==color) for x in s] for s in strings];suffix=[]
  for a in (A,B,C):
   su=[0]*(n+2)
   for i in range(n,0,-1):su[i]=su[i+1]+a[i]
   suffix.append(su)
  SA,SB,SC=suffix
  for i in range(1,n+1):
   lo=max(i,n-i);strict=max(i+1,n-i);ans+=A[i]*SB[lo]*SC[lo]+B[i]*SA[strict]*SC[lo]+C[i]*SA[strict]*SB[strict]
  size=1
  while size<2*n+1:size*=2
  fa=ntt(A+[0]*(size-len(A)));fb=ntt(B+[0]*(size-len(B)));conv=ntt([a*b%998244353 for a,b in zip(fa,fb)],True)
  ans-=sum(C[k]*conv[2*n-k] for k in range(1,n+1))
 return ans
def geometric_triangles(strings):
 n=len(strings[0]);points=[(x,y) for x in range(n+1) for y in range(n+1-x)];ans=0
 for pts in combinations(points,3):
  edges=[];directions=set()
  for p,q in combinations(pts,2):
   if p[0]==q[0]:kind=0;idx=n-p[0];forward=p[1]<q[1]
   elif sum(p)==sum(q):kind=1;idx=sum(p);forward=p[0]<q[0]
   elif p[1]==q[1]:kind=2;idx=n-p[1];forward=p[0]>q[0]
   else:break
   if idx<1:break
   directions.add(kind);bit=int(strings[kind][idx-1]);edges.append((p,q) if forward==(bit==0) else (q,p))
  else:
   if len(directions)==3 and all(sum(u==p for u,v in edges)==sum(v==p for u,v in edges)==1 for p in pts):ans+=1
 return ans
def check_m():
 cases=0
 for n in range(1,4):
  for p in product('01',repeat=3*n):
   strings=[''.join(p[i*n:(i+1)*n]) for i in range(3)];assert triangles(strings)==geometric_triangles(strings),(strings,triangles(strings),geometric_triangles(strings));cases+=1
 for _ in range(500):
  n=R.randrange(1,25);strings=[''.join(R.choice('01') for _ in range(n)) for i in range(3)];want=sum(strings[0][i-1]==strings[1][j-1]==strings[2][k-1] and i+j>=n and i+k>=n and j+k>=n and i+j+k!=2*n for i,j,k in product(range(1,n+1),repeat=3));assert triangles(strings)==want;cases+=1
 rec('M',cases,'all direction assignments through n3 against explicit vertex triples and directed cycles, plus random n<=24 triple enumeration versus suffix sums and actual NTT')

def main():
 for f in (check_a,check_b,check_g,check_i,check_l,check_j,check_m):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 out={'scope':'2025 CCPC Harbin A B G I J L M','seed':20251109,'status':'passed','limitations':'Small-case mathematical/algorithm checks; no online judge submission or extreme-scale performance validation.','checks':checks,'content_sha256':{f'ccpc-haerbin-{x}.md':hashlib.sha256((root/'editorials/2025'/f'ccpc-haerbin-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_haerbin_2025.json');args=p.parse_args();args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
