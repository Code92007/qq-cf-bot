"""Hong Kong 2024 independent checkers, extended as editorials are completed."""
import argparse,collections,functools,hashlib,itertools,json,random
from pathlib import Path
R=random.Random(1885)
MOD=998244353

def symmetry(a,k,B=7):
 n=len(a);good={v:sum(1<<j for j,x in enumerate(a) if abs(v-x)<=k) for v in set(a)};bits=1;sample={}
 for r,v in enumerate(a):
  bits=((bits>>1)&good[v])|(1<<r)|(1<<(r+1))
  if r%B==0:sample[r]=bits
 ans=[]
 for c in range(2*n-1):
  base=c//2;upper=min(n-1,c);first=(base//B+1)*B;count=max(0,(upper-first)//B+1);lo=-1;hi=count
  while hi-lo>1:
   mid=(hi+lo)//2;r=first+mid*B;l=c-r
   if sample[r]>>l&1:lo=mid
   else:hi=mid
  r=base if lo<0 else first+lo*B
  while r<upper and abs(a[c-r-1]-a[r+1])<=k:r+=1
  ans.append(2*r-c+1)
 return ans

def check_a():
 count=0
 for _ in range(1500):
  n=R.randrange(2,90);a=[R.randrange(9) for _ in range(n)];k=R.randrange(5);got=symmetry(a,k,R.randrange(1,12));want=[]
  for c in range(2*n-1):
   r=c//2
   while r+1<n and c-r-1>=0 and abs(a[c-r-1]-a[r+1])<=k:r+=1
   want.append(2*r-c+1)
  assert got==want;count+=1
 return count

def attacks(a,b,c):
 k=len(c);L=max(x+y for x,y in zip(a,b));height=[0]*(L+2*k+1)
 for x,y in zip(a,b):height[y]=max(height[y],x)
 answer=10**30;ways=0
 for S in range(L,L+2*k-1):
  dp=[10**30]*(S+1);cnt=[0]*(S+1);dp[0]=0;cnt[0]=1
  for q in range(1,S+1):
   h=0
   for x in range(1,min(k,q)+1):
    p=q-x;h=max(h,height[p+1])
    if q+h>S:continue
    candidate=dp[p]+c[x-1]
    if candidate<dp[q]:dp[q]=candidate;cnt[q]=cnt[p]
    elif candidate==dp[q]:cnt[q]=(cnt[q]+cnt[p])%MOD
  if dp[S]<answer:answer=dp[S];ways=cnt[S]
  elif dp[S]==answer:ways=(ways+cnt[S])%MOD
 return answer,ways

def check_b():
 cases=0
 for _ in range(300):
  n=R.randrange(1,4);a=tuple(R.randrange(1,5) for _ in range(n));b=tuple(R.randrange(1,5) for _ in range(n));c=tuple(R.randrange(1,7) for _ in range(R.randrange(1,4)))
  @functools.lru_cache(None)
  def brute(hp,shield):
   if not any(hp):return 0,1
   best=10**9;ways=0
   for x,cost in enumerate(c,1):
    nh=list(hp);ns=list(shield)
    for i in range(n):
     if not hp[i]:continue
     if shield[i]:ns[i]=max(0,shield[i]-x)
     else:nh[i]=max(0,hp[i]-x)
    value,w=brute(tuple(nh),tuple(ns));value+=cost
    if value<best:best=value;ways=w
    elif value==best:ways+=w
   return best,ways%MOD
  assert attacks(a,b,c)==brute(a,b),(a,b,c,attacks(a,b,c),brute(a,b));cases+=1
 return cases

def check_c():
 cases=0
 for n in range(1,9):
  for a in itertools.product(range(1,4),repeat=n):
   @functools.lru_cache(None)
   def possible(l,r):
    if l==r:return {l}
    z=set()
    if a[l]<=a[r]:z|=possible(l+1,r)
    if a[r]<=a[l]:z|=possible(l,r-1)
    return z
   assert possible(0,n-1)=={i for i,x in enumerate(a) if x==max(a)};cases+=1
 return cases

def profiles(a):
 n=len(a);out=[None]*n;profile=[(0,0)]
 for i in range(2*n-2,-1,-1):
  nxt=[(0,0)]
  for length,value in profile:
   if length+1>=n:break
   value=(a[(i+1)%n]+value)//2
   if value!=nxt[-1][1]:nxt.append((length+1,value))
  profile=nxt
  if i<n:out[i]=profile[:]
 return out

def money(a):
 n=len(a)
 if n==1:return a[:]
 left=profiles(a);rev=profiles(a[::-1]);ans=[]
 for i in range(n):
  right=rev[n-1-i];j=len(right)-1;best=0
  for y,v in left[i]:
   while right[j][0]>n-1-y:j-=1
   best=max(best,v+right[j][1])
  ans.append(a[i]+best)
 return ans

def check_f():
 count=0
 for _ in range(120):
  n=R.randrange(1,6);a=tuple(R.randrange(5) for i in range(n))
  @functools.lru_cache(None)
  def game(mask,state):
   best=list(state)
   for i in range(n):
    if mask>>i&1:continue
    for j in {(i-1)%n,(i+1)%n}:
     t=list(state);d=t[i]//2;t[i]-=d;t[j]+=d;future=game(mask|1<<i,tuple(t));best=[max(x,y) for x,y in zip(best,future)]
   return tuple(best)
  assert money(list(a))==list(game(0,a)),(a,money(list(a)),game(0,a));count+=1
 for _ in range(1000):
  n=R.randrange(1,100);a=[R.randrange(10**9) for i in range(n)];want=[]
  for i in range(n):
   best=0
   for y in range(n):
    l=r=0
    for d in range(y,0,-1):l=(a[(i+d)%n]+l)//2
    for d in range(n-1-y,0,-1):r=(a[(i-d)%n]+r)//2
    best=max(best,l+r)
   want.append(a[i]+best)
  assert money(a)==want;count+=1
 return count

def trie_score(strings,k):
 counts=collections.Counter(s[:j] for s in strings for j in range(1,len(s)+1));return sum(v//k for v in counts.values())
def check_g():
 count=0
 for _ in range(180):
  n=R.randrange(1,8);s=[''.join(R.choice('ab') for j in range(R.randrange(1,5))) for i in range(n)]
  for k in range(1,n+1):
   @functools.lru_cache(None)
   def brute(mask):
    ids=[i for i in range(n) if mask>>i&1]
    if len(ids)<k:return 0
    best=0
    for group in itertools.combinations(ids,k):
     l=0
     while all(len(s[i])>l for i in group) and len({s[i][l] for i in group})==1:l+=1
     best=max(best,l+brute(mask-sum(1<<i for i in group)))
    return best
   assert trie_score(s,k)==brute((1<<n)-1);count+=1
 return count

POW=[3**i for i in range(8)]
PLANS=[]
for c in itertools.product(range(3),repeat=6):
 need=[0]*8
 for i,v in enumerate(c):
  for j in range(i,i+3):need[j]+=v
 PLANS.append(need)

def mahjong(a):
 n=len(a);pref=[0];cnt=[0]*8
 for x in a:
  old=cnt[x]%3;cnt[x]+=1;pref.append(pref[-1]+((cnt[x]%3)-old)*POW[x])
 ans=0
 for need in PLANS:
  bucket=collections.Counter();counts=[0]*8;missing=sum(v>0 for v in need);left=0
  for r,x in enumerate(a):
   counts[x]+=1
   if counts[x]==need[x]:missing-=1
   while missing==0 and left<=r:
    bucket[pref[left]]+=1;y=a[left];left+=1
    if counts[y]==need[y]:missing+=1
    counts[y]-=1
   target=sum(((pref[r+1]//POW[j])%3-need[j])%3*POW[j] for j in range(8));ans+=bucket[target]
 return ans

def check_h():
 cases=0
 @functools.lru_cache(None)
 def valid(cnt):
  if not any(cnt):return True
  x=next(i for i,v in enumerate(cnt) if v)
  if cnt[x]>=3:
   t=list(cnt);t[x]-=3
   if valid(tuple(t)):return True
  if x<=5 and cnt[x+1] and cnt[x+2]:
   t=list(cnt)
   for j in range(x,x+3):t[j]-=1
   if valid(tuple(t)):return True
  return False
 for _ in range(150):
  a=[R.randrange(8) for i in range(R.randrange(1,18))];want=0
  for l in range(len(a)):
   c=[0]*8
   for r in range(l,len(a)):c[a[r]]+=1;want+=valid(tuple(c))
  assert mahjong(a)==want,(a,mahjong(a),want);cases+=1
 return cases

def check_k():
 cases=0
 for n in range(1,10):
  for chars in itertools.product('LR',repeat=n):
   s=''.join(chars);seen={s};q=[s]
   for t in q:
    for i,c in enumerate(t):
     j=i-1 if c=='L' else i+1
     if 0<=j<len(t):u=t[:j]+t[j+1:];
     else:continue
     if u not in seen:seen.add(u);q.append(u)
   subs={''.join(s[i] for i in range(n) if mask>>i&1) for mask in range(1,1<<n)}
   want={t for t in subs if (s[0]!='L' or t[0]=='L') and (s[-1]!='R' or t[-1]=='R')};assert seen==want;sizes=len(subs);cases+=sizes
 return cases

def flip_grid(a,target):
 n=len(a);m=len(a[0]);b=[[x^target for x in row] for row in a];par=[sum(b[i][d-i] for i in range(n) if 0<=d-i<m)%2 for d in range(n+m-1)]
 if len(set(par))>1:return None
 paths=[]
 def use(path):
  i=j=0;b[0][0]^=1
  for c in path:
   if c=='D':i+=1
   else:j+=1
   assert 0<=i<n and 0<=j<m;b[i][j]^=1
  assert (i,j)==(n-1,m-1);paths.append(path)
 for d in range(n-1,2-m,-1):
  cells=[(i,i-d) for i in range(1,n) if 0<=i-d<m-1]
  if not cells:continue
  i,j=cells[0];path='R'*j+'D'*(i-1)
  for i,j in cells:path+='DR' if b[i][j] else 'RD'
  i,j=cells[-1];i,j=i,j+1;path+='D'*(n-1-i)+'R'*(m-1-j);use(path)
 if b[0][0]:use('R'*(m-1)+'D'*(n-1))
 assert not any(x for row in b for x in row);assert len(paths)<=n+m-2 if n>1 and m>1 else len(paths)<=1
 return paths

def check_l():
 cases=0
 for n in range(1,4):
  for m in range(1,4):
   if n*m<2:continue
   masks=[]
   for ds in itertools.combinations(range(n+m-2),n-1):
    ds=set(ds);i=j=0;mask=1
    for k in range(n+m-2):
     if k in ds:i+=1
     else:j+=1
     mask^=1<<(i*m+j)
    masks.append(mask)
   reachable={0}
   for mask in masks:reachable|={x^mask for x in list(reachable)}
   for state in range(1<<(n*m)):
    a=[[state>>(i*m+j)&1 for j in range(m)] for i in range(n)];got=flip_grid(a,0);assert (got is not None)==(state in reachable);cases+=1
 for _ in range(500):
  n=R.randrange(2,201);m=R.randrange(2,201);a=[[R.randrange(2) for j in range(m)] for i in range(n)]
  # Force all anti-diagonal parities to agree, using the top/right boundary.
  for d in range(n+m-1):
   parity=sum(a[i][d-i] for i in range(n) if 0<=d-i<m)%2;i=max(0,d-m+1);j=d-i;a[i][j]^=parity
  assert flip_grid(a,0) is not None;cases+=1
 return cases

INF=10**18
IDENT=(0,INF,INF,0)
def mm(a,b):return tuple(min(a[2*i]+b[j],a[2*i+1]+b[2+j]) for i in range(2) for j in range(2))
def dmg(z):return (2*z,z,2*z,INF)
class Seg:
 def __init__(self,left=None,right=None,mat=IDENT,count=0):self.left=left;self.right=right;self.mat=mat;self.count=count
 def pull(self):self.mat=mm(self.left.mat if self.left else IDENT,self.right.mat if self.right else IDENT);self.count=(self.left.count if self.left else 0)+(self.right.count if self.right else 0)
def modify(node,l,r,pos,z):
 if node is None:node=Seg()
 if l==r:node.mat=dmg(z) if z is not None else IDENT;node.count=int(z is not None);return node
 mid=(l+r)//2
 if pos<=mid:node.left=modify(node.left,l,mid,pos,z)
 else:node.right=modify(node.right,mid+1,r,pos,z)
 node.pull();return node
def merge_seg(a,b,l,r):
 if a is None:return b
 if b is None:return a
 if l==r:
  assert a.mat==b.mat;return a
 mid=(l+r)//2;a.left=merge_seg(a.left,b.left,l,mid);a.right=merge_seg(a.right,b.right,mid+1,r);a.pull();return a
def suffix_query(node,q,limit,h):
 acc=IDENT;answer=0
 def walk(v,l,r):
  nonlocal acc,answer
  if v is None or l>limit:return True
  if r<=limit:
   cand=mm(v.mat,acc)
   if min(cand[:2])<2*h:acc=cand;answer+=v.count;return True
   if l==r:return False
  mid=(l+r)//2
  return walk(v.right,mid+1,r) and walk(v.left,l,mid)
 walk(node,0,q-1);return answer

def check_d():
 cases=0
 for repeat in range(180):
  n=R.randrange(1,12);q=R.randrange(5,26);adj=[[] for _ in range(n)];parent=[0]*n;depth=[0]*n
  for i in range(1,n):parent[i]=R.randrange(i);depth[i]=depth[parent[i]]+1;adj[parent[i]].append(i)
  def path(x,y):
   a=[];b=[]
   while x!=y:
    if depth[x]>=depth[y]:a.append(x);x=parent[x]
    else:b.append(y);y=parent[y]
   return a+[x]+b[::-1],x
  roots=[None]*n;rem=[[] for _ in range(n)];queries=[[] for _ in range(n)];history=[[] for _ in range(n)]
  for t in range(q):
   if R.random()<.6:
    x=R.randrange(n);y=R.randrange(n);z=R.randrange(1,9);p,lca=path(x,y)
    roots[x]=modify(roots[x],0,q-1,t,z)
    if x!=y:roots[y]=modify(roots[y],0,q-1,t,z)
    if lca:rem[parent[lca]].append(t)
    for u in p:history[u].append(z)
   else:
    u=R.randrange(n);h=R.randrange(1,35);a=history[u][:];want=0
    for start in range(len(a)):
     v=a[start:];best=min(sum(z*(1 if mask>>i&1 else 2) for i,z in enumerate(v)) for mask in range(1<<len(v)) if not mask&(mask<<1))
     if best<2*h:want=max(want,len(v))
    queries[u].append((t,h,want))
  for u in range(n-1,-1,-1):
   for v in adj[u]:roots[u]=merge_seg(roots[u],roots[v],0,q-1)
   for t in rem[u]:roots[u]=modify(roots[u],0,q-1,t,None)
   for t,h,want in queries[u]:assert suffix_query(roots[u],q,t-1,h)==want;cases+=1
 return cases

class PersistentCounts:
 def __init__(self,n):self.n=n;self.nodes=[(0,0,0)]
 def add(self,old,l,r,x):
  left,right,c=self.nodes[old]
  if l<r:
   mid=(l+r)//2
   if x<=mid:left=self.add(left,l,mid,x)
   else:right=self.add(right,mid+1,r,x)
  self.nodes.append((left,right,c+1));return len(self.nodes)-1
 def query(self,root,l,r,a,b):
  if not root or r<a or b<l:return 0
  left,right,c=self.nodes[root]
  if a<=l and r<=b:return c
  mid=(l+r)//2;return self.query(left,l,mid,a,b)+self.query(right,mid+1,r,a,b)
def reconstruction(t1,t):
 n=len(t);tin=[0]*n;tout=[0]*n;par=[-1]*n;timer=0
 def dfs(u,p):
  nonlocal timer
  par[u]=p;tin[u]=timer;timer+=1
  for v in t[u]:
   if v!=p:dfs(v,u)
  tout[u]=timer-1
 dfs(0,-1);seg=PersistentCounts(n);version=[0]*n;p1=[-1]*n;dep=[0]*n
 def build(u,p):
  p1[u]=p;version[u]=seg.add(version[p] if p>=0 else 0,0,n-1,tin[u])
  for v in t1[u]:
   if v!=p:dep[v]=dep[u]+1;build(v,u)
 build(0,-1);diff=[0]*(n+1);global_bad=0
 for v in range(1,n):
  u=par[v];x=u;y=v
  while x!=y:
   if dep[x]>=dep[y]:x=p1[x]
   else:y=p1[y]
  lca=x;length=dep[u]+dep[v]-2*dep[lca]-1
  if length==0:continue
  count=sum(sign*seg.query(root,0,n-1,tin[v],tout[v]) for root,sign in [(version[u],1),(version[v],1),(version[lca],-1),(version[p1[lca]] if p1[lca]>=0 else 0,-1)])-1
  if 0<count<length:return [False]*n
  if count==length:diff[tin[v]]+=1;diff[tout[v]+1]-=1
  else:global_bad+=1;diff[tin[v]]-=1;diff[tout[v]+1]+=1
 values=[];running=global_bad
 for i in range(n):running+=diff[i];values.append(running==0)
 return [values[tin[u]] for u in range(n)]
def check_j():
 cases=0
 for _ in range(600):
  n=R.randrange(1,13);trees=[]
  for z in range(2):
   adj=[[] for i in range(n)]
   for i in range(1,n):j=R.randrange(i);adj[i].append(j);adj[j].append(i)
   perm=list(range(n));R.shuffle(perm);out=[[] for i in range(n)]
   for i in range(n):out[perm[i]]=[perm[j] for j in adj[i]]
   trees.append(out)
  t1,t=trees
  def reachable(adj,allowed,start):
   seen={start};q=[start]
   for u in q:
    for v in adj[u]:
     if v in allowed and v not in seen:seen.add(v);q.append(v)
   return seen
  def valid(allowed,root):
   rest=allowed-{root};children=[v for v in t[root] if v in rest];parts=[]
   for v in children:parts.append(reachable(t,rest,v))
   actual=[];remaining=set(rest)
   while remaining:s=next(iter(remaining));comp=reachable(t1,rest,s);actual.append(comp);remaining-=comp
   if set(map(frozenset,parts))!=set(map(frozenset,actual)):return False
   return all(valid(part,v) for part,v in zip(parts,children))
  want=[valid(set(range(n)),u) for u in range(n)];assert reconstruction(t1,t)==want;cases+=1
 return cases

P=998244353;ORDER=P-1;TWO=1<<23;g2=pow(3,119,P)
TAB8={pow(pow(g2,1<<15,P),i,P):i for i in range(256)}
TAB7={pow(pow(g2,1<<16,P),i,P):i for i in range(128)}
TAB119={pow(pow(3,TWO,P),i,P):i for i in range(119)}
INV0=[pow(pow(g2,i,P),P-2,P) for i in range(256)]
INV1=[pow(pow(g2,256*i,P),P-2,P) for i in range(256)]
EXPLOW=[1]
for i in range(1,1<<15):EXPLOW.append(EXPLOW[-1]*3%P)
EXPHIGH=[1];step=pow(3,1<<15,P)
for i in range(1,(ORDER>>15)+1):EXPHIGH.append(EXPHIGH[-1]*step%P)
def logarithm(y):
 if y==0:return None
 h=pow(y,119,P);a0=TAB8[pow(h,1<<15,P)];h=h*INV0[a0]%P;a1=TAB8[pow(h,1<<7,P)];h=h*INV1[a1]%P;a2=TAB7[h];u=a0+256*a1+65536*a2;v=TAB119[pow(y,TWO,P)];return u+TWO*((v-u)*pow(TWO,-1,119)%119)
def fastpower(log,d):
 if log is None:return 0
 e=log*(d%ORDER)%ORDER;return EXPLOW[e&((1<<15)-1)]*EXPHIGH[e>>15]%P
def color_count(n,m):
 logs={}
 @functools.lru_cache(None)
 def solve(n,m):
  primes=[];v=n;p=2
  while p*p<=v:
   if v%p==0:
    primes.append(p)
    while v%p==0:v//=p
   p+=1
  if v>1:primes.append(v)
  div=[(1,1)]
  for p in primes:div +=[(d*p,-mu) for d,mu in div[:]]
  ans=sum(mu*(m//d) for d,mu in div)%P
  for d,mu in div:
   if d>1:
    base=solve(n//d,m//d);log=logs.setdefault(base,logarithm(base));ans=(ans-mu*fastpower(log,d))%P
  return ans
 return solve(n,m)
def check_i():
 cases=0
 for n in range(1,8):
  for m in range(1,6):
   @functools.lru_cache(None)
   def outcomes(group):
    ans=set();members=set(group)
    for x in range(1,m+1):
     if {(i+x)%n for i in group}!=members:continue
     unseen=set(group);cycles=[]
     while unseen:
      start=next(iter(unseen));u=start;cycle=[]
      while u in unseen:unseen.remove(u);cycle.append(u);u=(u+x)%n
      cycles.append(tuple(sorted(cycle)))
     if len(cycles)==1:ans.add((x,)*len(group))
     else:
      for combo in itertools.product(*(outcomes(c) for c in cycles)):
       mapping={v:color for c,result in zip(cycles,combo) for v,color in zip(c,result)};ans.add(tuple(mapping[v] for v in group))
    return ans
   want=len(outcomes(tuple(range(n))));assert color_count(n,m)==want,(n,m,color_count(n,m),want);cases+=1
 for _ in range(5000):
  y=R.randrange(P);d=R.randrange(1,10**18);l=logarithm(y)
  if y:assert pow(3,l,P)==y
  assert fastpower(l,d)==pow(y,d,P);cases+=1
 return cases

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return a[0]-b[0],a[1]-b[1]
def turn(a,b,c):return cross(sub(b,a),sub(c,b))
def hull(points):
 order=sorted(range(len(points)),key=lambda i:points[i]);st=[]
 for i in order:
  while len(st)>=2 and turn(points[st[-2]],points[st[-1]],points[i])<=0:st.pop()
  st.append(i)
 low=st[:-1];st=[]
 for i in order[::-1]:
  while len(st)>=2 and turn(points[st[-2]],points[st[-1]],points[i])<=0:st.pop()
  st.append(i)
 return low+st[:-1]
def fast(points):
 H=hull(points);hs=set(H);area=sum(cross(points[H[i]],points[H[(i+1)%len(H)]]) for i in range(len(H)));answer=count=0;polygons=[]
 for p,P in enumerate(points):
  if p in hs:continue
  vectors=[sub(q,P) for q in points]
  def cmp(i,j):
   a=vectors[i];b=vectors[j];ha=int(a[1]<0 or a[1]==0 and a[0]<0);hb=int(b[1]<0 or b[1]==0 and b[0]<0)
   if ha!=hb:return -1 if ha<hb else 1
   v=cross(a,b);return -1 if v>0 else 1
  order=sorted([i for i in range(len(points)) if i!=p],key=functools.cmp_to_key(cmp));first=next(i for i,v in enumerate(order) if v in hs);order=order[first:]+order[:first];order.append(order[0]);marks=[i for i,v in enumerate(order) if v in hs]
  for l,r in zip(marks,marks[1:]):
   seq=[vectors[order[i]] for i in range(l,r+1)];N=len(seq);pre=[];suf=[0]*N;stack=[];s=0
   for q in seq:
    while len(stack)>=2 and turn(stack[-2],stack[-1],q)<=0:
     s-=cross(stack[-2],stack[-1]);stack.pop()
    if stack:s+=cross(stack[-1],q)
    stack.append(q);pre.append(s)
   stack=[];s=0
   for k in range(N-1,-1,-1):
    q=seq[k]
    while len(stack)>=2 and turn(stack[-2],stack[-1],q)>=0:
     s-=cross(stack[-1],stack[-2]);stack.pop()
    if stack:s+=cross(q,stack[-1])
    stack.append(q);suf[k]=s
   for k in range(N-1):answer+=area-cross(seq[0],seq[-1])+pre[k]+suf[k+1];count+=1
 return answer,count

def brute(points):
 n=len(points);total=count=0
 def intersect(a,b,c,d):return turn(a,b,c)*turn(a,b,d)<0 and turn(c,d,a)*turn(c,d,b)<0
 def inside(poly,p):
  if p in poly:return True
  parity=False
  for a,b in zip(poly,poly[1:]+poly[:1]):
   if (a[1]>p[1])!=(b[1]>p[1]):
    x=a[0]+(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])
    if x>p[0]:parity=not parity
  return parity
 H=set(hull(points))
 for k in range(4,n+1):
  for ids in itertools.combinations(range(n),k):
   if not H<=set(ids):continue
   for tail in itertools.permutations(ids[1:]):
    poly=[points[i] for i in (ids[0],)+tail];area=sum(cross(poly[i],poly[(i+1)%k]) for i in range(k))
    if area<=0:continue
    if sum(turn(poly[i-1],poly[i],poly[(i+1)%k])<0 for i in range(k))!=1:continue
    if any(intersect(poly[i],poly[(i+1)%k],poly[j],poly[(j+1)%k]) for i in range(k) for j in range(i+2,k) if not(i==0 and j==k-1)):continue
    if not all(inside(poly,p) for p in points):continue
    total+=area;count+=1
 return total,count

def check_e():
 cases=0
 for case in range(500):
  n=R.randrange(4,9);points=[]
  while len(points)<n:
   p=(R.randrange(31),R.randrange(31))
   if p in points or any(turn(a,b,p)==0 for a,b in itertools.combinations(points,2)):continue
   points.append(p)
  got=fast(points);want=brute(points)
  assert got==want,(points,got,want)
  cases+=1
 for case in range(30):
  points=[(0,0),(100,0),(0,100)]
  while len(points)<8:
   p=(R.randrange(1,90),R.randrange(1,90))
   if sum(p)>=100 or p in points or any(turn(a,b,p)==0 for a,b in itertools.combinations(points,2)):continue
   points.append(p)
  assert fast(points)==brute(points),(points,fast(points),brute(points))
  cases+=1
 return cases

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args();methods={'A':'1500 random arrays and randomized checkpoint block widths versus direct center expansion','B':'300 random enemy systems versus memoized actual shield/health attack games, checking cost and count','C':'all ternary arrays through length eight versus all legal reverse deletion branches','F':'120 small exhaustive one-use donation games plus 1000 random circles versus every split','G':'random string multisets versus exhaustive disjoint team partitions for every team size','H':'150 random arrays versus recursive exact Pong/Chow decomposition for every interval','K':'every LR source through length nine; full reachable deletion graph versus corrected formal-statement conditions','L':'all grids through 3x3 against complete XOR span of paths plus 500 random boards through 200x200 with full construction replay'};methods.update({'D':'offline dynamic segment-tree unions/deletions versus actual path histories and exhaustive nonadjacent half-damage choices','I':'35 explicit original grouping/coloring games and 5000 smooth-order discrete-log/constant-time power checks against built-in modular exponentiation','J':'600 random tree pairs against direct recursive deletion-component reconstruction for every root'});methods['E']='530 general-position point sets, including dense interior points; enumerate all vertex subsets and simple polygon orders versus polar-sector prefix/suffix Graham area formula';checks={}
 for c,method in methods.items():
  count=globals()['check_'+c.lower()]();checks[c]={'passed':True,'cases':count,'method':method};print(c,count,flush=True)
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';report={'scope':'2024 ICPC Hong Kong A B C D E F G H I J K L','status':'passed','seed':1885,'limitations':'Independent small-case and construction checks; no online submissions. Optimized complexity requires the data structures described in each text; reference validators favor clarity over maximum-scale performance.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2024').glob('icpc-hongkong-*.md')) if p.stem.rsplit('-',1)[-1] in methods}};(Path(args.output) if args.output else root/'regional_editorial_validation_hongkong_2024.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
