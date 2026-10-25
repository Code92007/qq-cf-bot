#!/usr/bin/env python3
"""Independent small-case checks for 2025 CCPC Zhengzhou explanations."""
from pathlib import Path
from itertools import product,permutations,combinations
from collections import Counter,deque
import random,heapq,json,hashlib,argparse,math
R=random.Random(20251123);checks={};MOD=998244353
def rec(x,n,m):checks[x]={'cases':n,'method':m,'passed':True};print(x,n,flush=True)
def chocolate(dims,pts,cuts):
 n=len(pts);blocks=math.prod(c+1 for c in cuts)
 if blocks>n or n%blocks:return 0
 groups=[[0]*3 for _ in pts];ans=1
 for ax,c in enumerate(cuts):
  seq=sorted(range(n),key=lambda i:pts[i][ax]);size=n//(c+1)
  for k,i in enumerate(seq):groups[i][ax]=k//size
  for k in range(size,n,size):ans*=pts[seq[k]][ax]-pts[seq[k-1]][ax]
 if any(v!=n//blocks for v in Counter(tuple(x) for x in groups).values()) or len(set(tuple(x) for x in groups))!=blocks:return 0
 return ans
def check_b():
 for _ in range(1500):
  dims=tuple(R.randrange(2,6) for i in range(3));cuts=tuple(R.randrange(d) for d in dims);cells=list(product(*(range(1,d+1) for d in dims)));pts=R.sample(cells,R.randrange(1,min(len(cells),16)+1));want=0
  for axes in product(*(list(combinations(range(1,d),c)) for d,c in zip(dims,cuts))):
   counts=Counter(tuple(sum(v>cut for cut in axis) for v,axis in zip(p,axes)) for p in pts);blocks=math.prod(c+1 for c in cuts)
   if len(counts)==blocks and len(set(counts.values()))==1:want+=1
  got=chocolate(dims,pts,cuts);assert got==want,(dims,pts,cuts,got,want)
 rec('B',1500,'all integral cutting-plane choices for random small boxes versus forced sorted ranks and joint 3D buckets')
def plusxor(a,b):
 Q=1<<b.bit_length();dist={(a%Q,a%b):a};q=[(a,a%Q,a%b)]
 while q:
  v,x,y=heapq.heappop(q)
  if dist[x,y]!=v:continue
  for delta in (b,(x^b)-x+b):
   t=((x+delta)%Q,(y+delta)%b);nv=v+delta
   if nv<dist.get(t,10**30):dist[t]=nv;heapq.heappush(q,(nv,*t))
 best=[10**30]*b
 for (x,y),v in dist.items():best[y]=min(best[y],v)
 return lambda c:any(best[t%b]<=t for t in (c,c^b))
def check_g():
 cases=0
 for b in range(1,17):
  Q=1<<b.bit_length();cap=((128//Q)+1)*Q
  for a in range(65):
   seen={a};q=deque([a])
   while q:
    v=q.popleft()
    for t in (v+b,v^b):
     if t<cap and t not in seen:seen.add(t);q.append(t)
   got=plusxor(a,b)
   for c in range(129):assert got(c)==(c in seen),(a,b,c);cases+=1
 rec('G',cases,'original integer-operation BFS, bounded by the monotone high binary block, versus nonnegative block Dijkstra')
def expectation(n,k):
 powers=[1]*n;invfact=pow(math.factorial(n),MOD-2,MOD);facpow=1;ans=0
 for j in range(1,k+1):
  val=1
  for t in range(n):powers[t]=powers[t]*t%MOD;val=val*(1+powers[t])%MOD
  facpow=facpow*invfact%MOD;ans=(ans+(-1)**(j+1)*math.comb(k,j)*val*facpow)%MOD
 return ans
def check_i():
 cases=0
 for n in range(1,8):
  cnt=Counter()
  for p in permutations(range(1,n+1)):
   maximum=0;S=[]
   for x in p:
    if x>maximum:S.append(x);maximum=x
   cnt[tuple(sorted(S))]+=1
  for mask in range(1<<n):
   S=tuple(x+1 for x in range(n) if mask>>x&1);f=math.prod(n-x for x in range(1,n+1) if x not in S);assert f==cnt[S];cases+=1
  inv=pow(math.factorial(n),MOD-2,MOD)
  for k in range(1,21):
   want=sum(1-pow((1-v*inv)%MOD,k,MOD) for v in cnt.values())%MOD;assert expectation(n,k)==want;cases+=1
 assert expectation(3,2)==31*pow(18,MOD-2,MOD)%MOD
 rec('I',cases,'all permutations n<=7 to recover record-value set frequencies, followed by direct per-set sampling probabilities for k<=20')
def rectangle(a,b):
 kids=[[-1,-1]];cnt=[0]
 for x,y in zip(b,b[1:]):
  if x^y!=1:continue
  u=0
  for bit in range(30):
   z=x>>bit&1
   if kids[u][z]<0:kids[u][z]=len(kids);kids.append([-1,-1]);cnt.append(0)
   u=kids[u][z];cnt[u]+=1
 ans=0
 for x,y in zip(a,a[1:]):
  D=x^y
  if D<2 or (D+2)&(D+1):continue
  h=(D+2).bit_length()-1;target=x^((1<<(h-1))-2);u=0
  for bit in range(h):
   u=kids[u][target>>bit&1]
   if u<0:break
  if u>=0:ans+=cnt[u]
 return ans
def naive_rect(a,b):
 return sum((a[i]^b[j+1],a[i+1]^b[j],a[i+1]^b[j+1])==((a[i]^b[j])+1,(a[i]^b[j])+2,(a[i]^b[j])+3) for i in range(len(a)-1) for j in range(len(b)-1))
def check_j():
 cases=0
 for a,b,c,d in product(range(16),repeat=4):
  assert rectangle([a,b],[c,d])==naive_rect([a,b],[c,d]);cases+=1
 for _ in range(1000):
  a=[R.randrange(64) for i in range(R.randrange(1,20))];b=[R.randrange(64) for i in range(R.randrange(1,20))];assert rectangle(a,b)==naive_rect(a,b);cases+=1
 a=[0,(1<<30)-2];b=[(1<<29)-2,(1<<29)-1];assert rectangle(a,b)==naive_rect(a,b)==1;cases+=1
 rec('J',cases,'all four corner-generating values in [0,15], random arrays, and highest-bit carry boundary versus explicit XOR matrix')
def xorstrings(s,p):
 left=s[:p];right=s[p+1:];out=[]
 for k in range(1,max(len(left),len(right))+1):out.append(str((int(left[-k]) if k<=len(left) else 0)^(int(right[-k]) if k<=len(right) else 0)))
 return ''.join(out[::-1]).lstrip('0') or '0'
def replacement(s):
 return max((xorstrings(s,p) for p in {1,2,len(s)-2} if 0<p<len(s)-1),key=lambda s:(len(s),s))
def check_m():
 cases=0
 for n in range(3,16):
  for v in range(1<<n):
   s=f'{v:0{n}b}';want=max(int(s[:p],2)^int(s[p+1:],2) for p in range(1,n-1));assert int(replacement(s),2)==want,(s,replacement(s),want);cases+=1
 for _ in range(100):
  s=''.join(R.choice('01') for i in range(R.randrange(3,1000)));want=max(int(s[:p],2)^int(s[p+1:],2) for p in range(1,len(s)-1));assert int(replacement(s),2)==want;cases+=1
 rec('M',cases,'every binary string of length3..15 and random long strings versus every legal operator position using exact integers')
def main():
 for f in (check_b,check_g,check_i,check_j,check_m):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';out={'scope':'2025 CCPC Zhengzhou B G I J M','seed':20251123,'status':'passed','limitations':'Independent small-case checks only; no online judge submissions or maximum-size runtime tests.','checks':checks,'content_sha256':{f'ccpc-zhengzhou-{x}.md':hashlib.sha256((root/'editorials/2025'/f'ccpc-zhengzhou-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_zhengzhou_2025.json');args=p.parse_args();args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
