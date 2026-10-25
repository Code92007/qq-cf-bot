"""Independent exact checks for the 2024 CCPC Chongqing editorial batch."""
from collections import defaultdict, deque
from bisect import bisect_right
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, permutations, product
from math import comb, factorial, gcd
from pathlib import Path
import hashlib, json, random

ROOT=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
RNG=random.Random(20241110)
MOD=998244353

def phi(x):
 out=x;p=2
 while p*p<=x:
  if x%p==0:
   out=out//p*(p-1)
   while x%p==0:x//=p
  p+=1
 if x>1:out=out//x*(x-1)
 return out

def euler_subsets(a):
 primes=[2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53]
 groups=defaultdict(list)
 for x in a:
  z=x;m=0
  for i,p in enumerate(primes):
   if z%p==0:
    m|=1<<i
    while z%p==0:z//=p
  groups[z].append((x,m))
 dp={0:1}
 for p,items in groups.items():
  base=dp;some={}
  for x,t in items:
   nxt=defaultdict(int,some)
   for s,v in some.items():nxt[s|t]=(nxt[s|t]+v*x)%MOD
   for s,v in base.items():nxt[s|t]=(nxt[s|t]+v*x)%MOD
   some=dict(nxt)
  factor=(p-1)*pow(p,-1,MOD)%MOD if p!=1 else 1
  dp=defaultdict(int,base)
  for s,v in some.items():dp[s]=(dp[s]+v*factor)%MOD
 ans=0
 for s,v in dp.items():
  for i,p in enumerate(primes):
   if s>>i&1:v=v*(p-1)*pow(p,-1,MOD)%MOD
  ans=(ans+v)%MOD
 return ans

def mania(a,cap):
 n=sum(a);A=sum(x*y for x,y in zip(a,[300,300,200,100,50,0]));S=A+20*a[0]
 roundfrac=lambda p,q:(2*p+q)//(2*q)
 return roundfrac(10000*A,300*n),roundfrac(max(0,S-256*n)*cap,64*n)

def grid(a,b):
 n=len(a)
 if ('.' not in a)!=('.' not in b):return None
 if '.' not in a:return ['#'*n]*7
 def port(s):return next(i for i,x in enumerate(s) if x=='#' and any(0<=j<n and s[j]=='.' for j in [i-1,i+1]))
 p,q=port(a),port(b);out=[list('.'*n) for _ in range(7)]
 out[0]=list(a);out[6]=list(b)
 out[1]=['.' if x=='#' else '#' for x in a];out[5]=['.' if x=='#' else '#' for x in b]
 out[2][p]=out[4][q]='#'
 if abs(p-q)<=1:out[3][p]='#'
 else:
  for i in range(min(p,q)+1,max(p,q)):out[3][i]='#'
 return [''.join(row) for row in out]

def components(g,diagonal):
 cells={(i,j) for i,row in enumerate(g) for j,x in enumerate(row) if x=='#'};out=[]
 while cells:
  q=[cells.pop()];part=set(q)
  for x,y in q:
   for dx,dy in product([-1,0,1],repeat=2):
    if (dx or dy) and (diagonal or abs(dx)+abs(dy)==1) and (x+dx,y+dy) in cells:
     cells.remove((x+dx,y+dy));part.add((x+dx,y+dy));q.append((x+dx,y+dy))
  out.append(part)
 return out

def decimal_choice(a,b,L):
 w=b
 for p in [2,5]:
  while w%p==0:w//=p
 if w==1:return 0,1
 inv=pow(b//w,-1,w);best=(10**9,0);pow2=1
 while pow2<=L//w:
  D=pow2
  while D<=L//w:
   c=(-a*D*inv)%w
   if c<best[0]:best=c,w*D
   D*=5
  pow2*=2
 return best

def finite(a,b,c,d):
 den=b*d//gcd(a*d+b*c,b*d)
 for p in [2,5]:
  while den%p==0:den//=p
 return den==1

@lru_cache(None)
def graph_opt(weights,edges):
 n=len(weights)
 if n==1:return weights[0]
 adj=[set() for _ in weights]
 for u,v in edges:adj[u].add(v);adj[v].add(u)
 ans=0
 for y in range(n):
  for x,z in combinations(adj[y],2):
   S={x,y,z};remain=[v for v in range(n) if v not in S];mp={v:i for i,v in enumerate(remain)}
   for v in S:mp[v]=len(remain)
   w=tuple(weights[v] for v in remain)+(max(weights[y],min(weights[x],weights[z])),)
   e=tuple(sorted({tuple(sorted((mp[u],mp[v]))) for u,v in edges if mp[u]!=mp[v]}))
   ans=max(ans,graph_opt(w,e))
 return ans

def transform(s):
 return ''.join(('[' if i==0 else ' ')+('"' if c=="'" else "'")+c+('"' if c=="'" else "'")+(']' if i==len(s)-1 else ',') for i,c in enumerate(s))

def string_stats(s,k,p):
 md=10**9+7;h=[0]*p;f=[0]*p;g=[0]*p
 for j,c in enumerate(s):h[j%p]+=1;f[j%p]+=ord(c);g[j%p]+=c=="'"
 length=len(s)%p
 for _ in range(k):
  nh=[0]*p;nf=[0]*p;ng=[0]*p
  for r in range(p):
   vals=[32*h[r],39*h[r]-5*g[r],f[r],39*h[r]-5*g[r],44*h[r]]
   quotes=[0,h[r]-g[r],g[r],h[r]-g[r],0]
   for t in range(5):
    j=(5*r+t)%p;nh[j]+=h[r];nf[j]+=vals[t];ng[j]+=quotes[t]
  length=length*5%p;nf[0]+=59;nf[(length-1)%p]+=49
  h=[x%md for x in nh];f=[x%md for x in nf];g=[x%md for x in ng]
 return h,f,g

def arithmetic(a):
 c=[0]*11
 for x in a:c[x]+=1
 z=min(c[1],c[2]);c[1]-=z;c[2]-=z;c[3]+=z
 z=c[1]//3;c[1]-=3*z;c[3]+=z
 if c[1]>=2:c[1]-=2;c[2]+=1
 if c[1]:
  others=[i for i in range(2,10) if c[i]]
  if not others:return 1
  x=min(others);c[1]-=1;c[x]-=1;c[x+1]+=1
 ans=1
 for x in range(2,11):ans*=x**c[x]
 return ans

@lru_cache(None)
def expression_best(a):
 if len(a)==1:return a[0]
 ans=0;n=len(a)
 for mask in range(1,1<<n):
  if not mask&1 or mask==(1<<n)-1:continue
  x=expression_best(tuple(a[i] for i in range(n) if mask>>i&1));y=expression_best(tuple(a[i] for i in range(n) if not(mask>>i&1)))
  ans=max(ans,x+y,x*y)
 return ans

def roll(o,d):
 t,b,n,s,e,w=o
 return {'R':(w,e,n,s,t,b),'L':(e,w,n,s,b,t),'D':(n,s,b,t,e,w),'U':(s,n,t,b,e,w)}[d]

def fractal(n):
 if n==0:return [[1]]
 a=fractal(n-1);m=len(a)
 return [[a[i%m][j%m] if i//m==1 or j//m==1 else 0 for j in range(3*m)] for i in range(3*m)]

def ternary(x,n):
 out=[]
 for _ in range(n):out.append(x%3);x//=3
 return out

def median_value(a):return max(min(a[i],a[j]) for i in range(len(a)) for j in range(i+1,min(len(a),i+3)))

def median_oracle(a):
 seen={a};q=[a];ans=0
 for s in q:
  if len(set(s))==1:ans=max(ans,s[0])
  for l in range(len(a)):
   for r in range(l+3,len(a)+1,2):
    val=sorted(s[l:r])[(r-l)//2];t=s[:l]+(val,)*(r-l)+s[r:]
    if t not in seen:seen.add(t);q.append(t)
 return ans

def threshold(ints,x):
 md=10**9+7;P=1;f0,f1,f2=1,0,0
 for l,r in ints:
  z=max(0,min(r,x-1)-l+1);o=r-l+1-z;P=P*(r-l+1)%md
  f0,f1,f2=(f0+f2)*z%md,f0*o%md,f1*z%md
 return (P-f0-f1-f2)%md

def interpolate(y,t):
 md=10**9+7;d=len(y)-1
 if 0<=t<=d:return y[t]
 pref=[1]*(d+2);suff=[1]*(d+2);fac=[1]*(d+1)
 for i in range(d+1):pref[i+1]=pref[i]*(t-i)%md
 for i in range(d,-1,-1):suff[i]=suff[i+1]*(t-i)%md
 for i in range(1,d+1):fac[i]=fac[i-1]*i%md
 return sum(y[i]*pref[i]*suff[i+1]*pow(fac[i]*fac[d-i],-1,md)*(-1 if (d-i)%2 else 1) for i in range(d+1))%md

def median_sum(ints):
 n=len(ints);md=10**9+7;cuts=sorted({1,max(r for l,r in ints)+1}|{l for l,r in ints}|{r+1 for l,r in ints});ans=0
 for L,end in zip(cuts,cuts[1:]):
  length=end-L
  if length<=n+1:ans+=sum(threshold(ints,x) for x in range(L,end))
  else:
   y=[0]
   for x in range(L,L+n+1):y.append((y[-1]+threshold(ints,x))%md)
   ans+=interpolate(y,length)
 return ans%md

def shooting_dp(s):
 n=len(s);W=[[0]*n for _ in s]
 for l in range(n):
  for r in range(l,n):
   t=s[l:r+1];m=len(t);a=t.count('R')
   if 'LR' in t:continue
   if a==m:W[l][r]=m-1+(r==n-1)
   elif a==0:W[l][r]=m-1+(l==0)
   else:W[l][r]=(m-1)*comb(m,a)
 dp=[[0]*(n+1) for _ in range(n+1)];dp[0][0]=1
 for r in range(1,n+1):
  for l in range(1,r+1):
   for k in range(1,r+1):dp[r][k]+=dp[l-1][k-1]*W[l-1][r-1]*comb(r,r-l+1)
 return [x%MOD for x in dp[n][1:]]

def shoot(s,order,magic):
 alive=set(range(len(s)))
 for i in order:
  if i not in alive:continue
  targets=sorted(j for j in alive if j<i) if s[i]=='L' else sorted(j for j in alive if j>i)
  if targets:
   if magic:alive.difference_update(targets)
   else:alive.remove(targets[-1] if s[i]=='L' else targets[0])
 return alive

def magic_formula(s):
 n=len(s);A=[1]*n;B=[1]*n;ans=[0]*n
 for i in range(n):
  for j in range(i):
   if s[j]=='R':A[i]=A[i]*(i-j)*pow(i-j+1,-1,MOD)%MOD
  for j in range(i+1,n):
   if s[j]=='L':B[i]=B[i]*(j-i)*pow(j-i+1,-1,MOD)%MOD
 for i in range(n-1):
  if s[i:i+2]=='LR':
   z=A[i]*B[i+1]%MOD;ans[i]+=z;ans[i+1]+=z
 if s[0]=='R':ans[0]+=B[0]
 if s[-1]=='L':ans[-1]+=A[-1]
 return [x*factorial(n)%MOD for x in ans]

def polymul(a,b):
 c=[0]*(len(a)+len(b)-1)
 for i,x in enumerate(a):
  for j,y in enumerate(b):c[i+j]=(c[i+j]+x*y)%MOD
 return c

def polyrem(a,b):
 a=a[:]
 while len(a)>=len(b):
  c=a[-1]*pow(b[-1],-1,MOD)%MOD;shift=len(a)-len(b)
  for j,v in enumerate(b):a[j+shift]=(a[j+shift]-c*v)%MOD
  a.pop()
 return a or [0]

def prefix_products(s,offset):
 n=len(s);tree={};out=[0]*n
 def build(l,r):
  if l==r:
   P=[(-l)%MOD,1] if s[l]=='R' else [1];Q=[(-l-offset)%MOD,1]
  else:
   m=(l+r)//2;p,q=build(l,m);pp,qq=build(m+1,r);P=polymul(p,pp);Q=polymul(q,qq)
  tree[l,r]=P,Q;return P,Q
 def walk(l,r,H):
  if l==r:out[l]=H[0];return
  m=(l+r)//2;p,q=tree[l,m];pp,qq=tree[m+1,r]
  walk(l,m,polyrem(H,q));walk(m+1,r,polyrem(polymul(H,p),qq))
 build(0,n-1);walk(0,n-1,[1]);return out

def sand_events(par,c):
 n=len(par)
 if sum(c)>n-2:return None
 ch=[[] for _ in par];deg=[1]*n;deg[0]=0
 for v in range(1,n):ch[par[v]].append(v);deg[par[v]]+=1
 missing=[[] for _ in par];base=[0]*n
 for v in range(n-1,-1,-1):
  C=c[v]+sum(base[u] for u in ch[v]);S=sorted(x for u in ch[v] for x in missing[u]);d=deg[v]
  if v==0:
   base[v]=0 if C<d else S[C-d]
   continue
  lo=0;hi=C
  while lo<hi:
   m=(lo+hi)//2
   if C-m-bisect_right(S,m)<d:hi=m
   else:lo=m+1
  q=lo;base[v]=q;rank=bisect_right(S,q);beta=C-q-rank;k0=d-1-beta
  missing[v]=list(range(1,k0+1))+[e-q+i+k0 for i,e in enumerate(S[rank:],1)]
  assert missing[v]==sorted(set(missing[v]))
 actual=[0]*n;actual[0]=base[0]
 for v in range(1,n):
  k=actual[par[v]];actual[v]=base[v]+k-bisect_right(missing[v],k)
 final=[]
 for v in range(n):
  incoming=sum(actual[u] for u in ch[v])+(actual[par[v]] if v else 0)
  final.append(c[v]+incoming-deg[v]*actual[v])
 return final,actual

def sand_queue(par,c):
 n=len(par);adj=[[] for _ in par]
 for v in range(1,n):adj[v].append(par[v]);adj[par[v]].append(v)
 c=c[:];fired=[0]*n;q=deque(v for v in range(n) if c[v]>=len(adj[v]))
 while q:
  v=q.popleft()
  if c[v]<len(adj[v]):continue
  c[v]-=len(adj[v]);fired[v]+=1
  for u in adj[v]:
   c[u]+=1
   if c[u]>=len(adj[u]):q.append(u)
  if c[v]>=len(adj[v]):q.append(v)
 return c,fired

def main():
 checks={};count=0
 for n in range(1,10):
  for _ in range(35):
   a=[RNG.choice([1,2,3,4,6,9,59,118,177,61,122]) for _ in range(n)];brute=0
   for mask in range(1<<n):
    x=1
    for i,v in enumerate(a):
     if mask>>i&1:x*=v
    brute+=phi(x)
   assert euler_subsets(a)==brute%MOD;count+=1
 assert euler_subsets([1,2,3])==12;count+=1
 checks['A']={'passed':True,'cases':count,'method':'all subsets of random small arrays; exact integer totient versus grouped small-prime DP, including repeated large primes and ones'}
 count=0
 for _ in range(1000):
  a=[RNG.randrange(20001) for _ in range(6)];cap=RNG.randrange(3001);n=sum(a)
  A=sum(x*y for x,y in zip(a,[300,300,200,100,50,0]));S=A+20*a[0]
  ref=(int((Decimal(A)*10000/(300*n)).quantize(Decimal(1),rounding=ROUND_HALF_UP)),int((max(Decimal(0),Decimal(S)/(320*n)-Decimal('0.8'))*5*cap).quantize(Decimal(1),rounding=ROUND_HALF_UP)))
  assert mania(a,cap)==ref;count+=1
 assert mania([3029,2336,377,41,10,61],630)==(9620,423)
 assert mania([20000,10000,0,0,0,0],3000)==(10000,2688);count+=2
 checks['B']={'passed':True,'cases':count,'method':'high-precision Decimal ROUND_HALF_UP oracle and both official samples'}
 count=0
 for n in range(2,8):
  ss=[''.join(s) for s in product('.#',repeat=n) if '#' in s]
  for a in ss:
   for b in ss:
    g=grid(a,b)
    if g is not None:
     assert g[0]==a and g[6]==b and len(components(g,True))==1
     for C in components(g,False):
      xs=[x for x,y in C];ys=[y for x,y in C]
      assert len(C)==(max(xs)-min(xs)+1)*(max(ys)-min(ys)+1),(a,b,g,C)
    else:assert ('.' not in a)!=('.' not in b)
    count+=1
 checks['C']={'passed':True,'cases':count,'method':'all nonempty first/last rows for widths 2..7; BFS eight-connectivity and exact bounding rectangles of every four-component'}
 count=0
 for b in range(1,45):
  for a in range(1,b+1):
   if gcd(a,b)!=1:continue
   L=90;c,d=decimal_choice(a,b,L)
   ref=next(c for c in range(b+1) if any(finite(a,b,c,d) for d in range(1,L+1)))
   assert c==ref and d<=L and finite(a,b,c,d),(a,b,c,d,ref);count+=1
 checks['D']={'passed':True,'cases':count,'method':'all reduced fractions through denominator 44 with bounded denominator 90; enumerate every denominator and numerator and inspect reduced decimal denominator'}
 count=0
 for n in [1,3,5,7]:
  for _ in range(35 if n<7 else 12):
   edges={(RNG.randrange(v),v) for v in range(1,n)}
   for u,v in combinations(range(n),2):
    if RNG.randrange(7)==0:edges.add((u,v))
   w=tuple(RNG.randrange(1,5) for _ in range(n));deg=[0]*n
   for u,v in edges:deg[u]+=1;deg[v]+=1
   pred=w[0] if n==1 else max([sorted(w)[-2]]+[w[i] for i in range(n) if deg[i]>1])
   assert graph_opt(w,tuple(sorted(edges)))==pred,(w,edges,pred);count+=1
 checks['E']={'passed':True,'cases':count,'method':'exhaustive legal contraction search on random connected odd graphs through 7 vertices, including cycles and equal maxima'}
 count=0
 for _ in range(220):
  s=''.join(RNG.choice("a'\\\"[,]!") for _ in range(RNG.randrange(1,5)));k=RNG.randrange(5);p=RNG.randrange(1,20);t=s
  for z in range(k):t=transform(t)
  h=[0]*p;f=[0]*p;g=[0]*p
  for j,c in enumerate(t):h[j%p]+=1;f[j%p]+=ord(c);g[j%p]+=c=="'"
  assert string_stats(s,k,p)==(h,f,g);count+=1
 assert string_stats('abc',2,7)[1]==[472,420,580,408,474,439,429];count+=1
 assert string_stats('abc',1,16)[1]==[91,39,97,39,44,32,39,98,39,44,32,39,99,39,93,0];count+=1
 checks['H']={'passed':True,'cases':count,'method':'literal formal transformation versus all three aggregated residue states; quotes, backslashes, punctuation, p=1, official second example'}
 count=0
 for n in range(1,9):
  for a in combinations_with_replacement(range(1,5),n):
   assert arithmetic(a)==expression_best(a),a;count+=1
 for _ in range(100):
  a=tuple(sorted(RNG.randrange(1,10) for _ in range(RNG.randrange(1,8))))
  assert arithmetic(a)==expression_best(a);count+=1
 for counts,expected in [([5,3,0,0,0,0,0,0,0],54),([4,1,1,1,0,0,0,0,0],108),([1,0,0,0,0,0,0,0,0],1),([1,0,0,0,0,0,0,0,1],10),([1,0,0,0,0,0,0,0,2],90),([99,88,77,66,55,44,33,22,11],90553232),([100,90,80,70,60,50,40,30,20],143532368)]:
  a=tuple(x for x in range(1,10) for _ in range(counts[x-1]));assert arithmetic(a)%MOD==expected;count+=1
 checks['I']={'passed':True,'cases':count,'method':'all multisets over 1..4 through size 8 and random 1..9 multisets; exact full expression-partition DP with both operators'}
 initial=(1,6,2,5,3,4);orient={initial};q=[initial]
 for o in q:
  for d in 'LRUD':
   oo=roll(o,d)
   if oo not in orient:orient.add(oo);q.append(oo)
 assert len(orient)==24;count=0
 for o in orient:
  for macro in ['RDL','LDR','RUL','LUR','URD','DRU','ULD','DLU']:
   z=o
   for d in macro:z=roll(z,d)
   assert z[1]==o[1];count+=1
 for n,m in [(2,2),(2,3),(3,4)]:
  seen={(0,0,initial)};q=list(seen)
  for x,y,o in q:
   for d,dx,dy in [('L',0,-1),('R',0,1),('U',-1,0),('D',1,0)]:
    if 0<=x+dx<n and 0<=y+dy<m:
     st=x+dx,y+dy,roll(o,d)
     if st not in seen:seen.add(st);q.append(st)
  assert {(x,y) for x,y,o in seen if o[1]==6}==set(product(range(n),range(m)));count+=1
 checks['J']={'passed':True,'cases':count,'method':'all 24 orientations and eight three-roll macros; full orientation/position BFS on three small grids'}
 count=0
 for n in range(1,5):
  mat=fractal(n)
  for i,row in enumerate(mat):
   for j,val in enumerate(row):assert val==int(all(x==1 or y==1 for x,y in zip(ternary(i,n),ternary(j,n))));count+=1
 checks['K']={'passed':True,'cases':count,'method':'explicit recursive matrices through n=4, all coordinates versus ternary digit condition'}
 count=0
 for n in range(3,7):
  for _ in range(35):
   a=tuple(RNG.randrange(1,4) for _ in range(n));assert median_value(a)==median_oracle(a);count+=1
 for n in range(3,7):
  for _ in range(50):
   ints=[]
   for i in range(n):
    l=RNG.randrange(1,5);ints.append((l,RNG.randrange(l,6)))
   brute=sum(median_value(a) for a in product(*(range(l,r+1) for l,r in ints)))
   assert median_sum(ints)==brute;count+=1
 for R in [10,17,100,999999937,1000000000]:
  assert median_sum([(1,R)]*3)==(R**3*(R+1)//2)%(10**9+7);count+=1
 checks['M']={'passed':True,'cases':count,'method':'literal median-operation BFS, exhaustive bounded assignments, and large-range median symmetry oracle for interpolation'}
 countF=countG=0
 for n in range(2,8):
  strings=[''.join(t) for t in product('LR',repeat=n)] if n<=5 else [''.join(RNG.choice('LR') for _ in range(n)) for z in range(14)]
  for s in strings:
   f=[0]*n;g=[0]*n
   for order in permutations(range(n)):
    f[len(shoot(s,order,False))-1]+=1
    for v in shoot(s,order,True):g[v]+=1
   assert shooting_dp(s)==f,(s,shooting_dp(s),f);countF+=1
   assert magic_formula(s)==g,(s,magic_formula(s),g);countG+=1
 for s,expected in [('RL',[2,0]),('LLRR',[0,24,0,0]),('LRLRLLRRRR',[0,0,0,604800,3024000,0,0,0,0,0])]:
  assert shooting_dp(s)==expected;countF+=1
 for n in range(1,45):
  for _ in range(5):
   s=''.join(RNG.choice('LR') for _ in range(n))
   for offset in [0,1]:
    out=prefix_products(s,offset)
    for i in range(n):
     z=1
     for j in range(i):
      if s[j]=='R':z=z*(i+offset-j)%MOD
     assert out[i]==z,(s,offset,i,out[i],z)
   countG+=1
 checks['F']={'passed':True,'cases':countF,'method':'all firing permutations for all directions through n=5 and random n=6,7; interval-chain DP; all three official samples'}
 checks['G']={'passed':True,'cases':countG,'method':'literal all-target shooting for all small permutations, plus independent naive polynomial multiplication/long division for the prefix-product tree; excludes NTT implementation'}
 count=0
 for n in range(2,32):
  for _ in range(35):
   par=[-1]+[RNG.randrange(v) for v in range(1,n)];c=[0]*n
   for j in range(RNG.randrange(n-1)):c[RNG.randrange(n)]+=1
   got=sand_events(par,c);ref=sand_queue(par,c)
   assert got==ref,(par,c,got,ref);count+=1
 for n in range(2,65):
  for par in [[-1]+list(range(n-1)),[-1]+[0]*(n-1)]:
   for v in [0,n-1]:
    c=[0]*n;c[v]=n-2
    assert sand_events(par,c)==sand_queue(par,c);count+=1
 for par,c,expected in [([-1,0,1,1,0,3],[1,1,0,0,1,1],[1,2,0,1,0,0]),([-1,0,0,1,2,4,1,6,3,7,4,2],[2,0,0,0,1,0,1,0,1,1,0,1],[0,1,2,1,1,0,1,1,0,0,0,0])]:
  assert sand_events(par,c)[0]==expected;count+=1
 assert sand_events([-1],[0]) is None;count+=1
 checks['L']={'passed':True,'cases':count,'method':'sorted-event recurrence and top-down firing counts versus literal legal queue stabilization; random trees, paths/stars at maximum stable mass, both official samples; excludes optimized persistent/rollback treap'}
 files=[ROOT/f'editorials/2024/ccpc-chongqing-{k}.md' for k in checks]
 report={'scope':'2024 CCPC Chongqing '+' '.join(checks),'status':'passed','seed':20241110,'limitations':'Independent exact small-instance checks; no online submissions or maximum-scale timing.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
 (ROOT/'regional_editorial_validation_ccpc_chongqing_2024.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
