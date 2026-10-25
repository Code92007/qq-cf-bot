"""Independent checks for 2025 Wuhan editorials (Python 3.10+)."""
import itertools,random,collections,functools,heapq,math,json,hashlib,argparse
from pathlib import Path
R=random.Random(2609)

def floor_sum(n,m,a,b):
 qa,a=divmod(a,m);qb,b=divmod(b,m);ans=qa*n*(n-1)//2+qb*n
 while True:
  qa,a=divmod(a,m);qb,b=divmod(b,m);ans+=qa*n*(n-1)//2+qb*n
  y=a*n+b
  if y<m:return ans
  n,b=divmod(y,m);m,a=a,m

def check_a():
 cases=0
 for f,x,g,y in itertools.product(range(1,6),repeat=4):
  for n,m in [(1,1),(7,3),(13,7),(20,2)]:
   ans=n-floor_sum(n,m,g,y)+floor_sum(n,m,f,x)+floor_sum(n,m,g-f,y-x-1)
   expect=sum((f*i+x)%m<(g*i+y)%m for i in range(n));assert ans==expect;cases+=1
 for _ in range(500):
  n=R.randrange(1,100);m=R.randrange(1,100);a=R.randrange(-100,100);b=R.randrange(-100,100);assert floor_sum(n,m,a,b)==sum((a*i+b)//m for i in range(n));cases+=1
 return cases

def scc(graph):
 rev=[[] for _ in graph]
 for u in range(len(graph)):
  for v in graph[u]:rev[v].append(u)
 seen=set();order=[]
 def dfs(u):
  seen.add(u)
  for v in graph[u]:
   if v not in seen:dfs(v)
  order.append(u)
 for u in range(len(graph)):
  if u not in seen:dfs(u)
 comp=[-1]*len(graph)
 def flood(u,c):
  comp[u]=c
  for v in rev[u]:
   if comp[v]<0:flood(v,c)
 c=0
 for u in order[::-1]:
  if comp[u]<0:flood(u,c);c+=1
 return comp

def base_stations(par,faults):
 n=len(par);children=[[] for _ in par];dep=[0]*n
 for v in range(1,n):children[par[v]].append(v);dep[v]=dep[par[v]]+1
 tin=[0]*n;tout=[0]*n;clock=0
 def tour(u):
  nonlocal clock
  tin[u]=clock;clock+=1
  for v in children[u]:tour(v)
  tout[u]=clock
 tour(0);levels={}
 for u in range(n):levels.setdefault(dep[u],[]).append(u)
 graph=[[] for _ in range(2*n)]
 for v in range(1,n):u=par[v];graph[2*u].append(2*v+1);graph[2*v].append(2*u+1)
 trees={}
 def node():graph.append([]);return len(graph)-1
 def build(arr,l,r):
  down=node();up=node()
  if r-l==1:
   graph[down].append(2*arr[l]);graph[2*arr[l]+1].append(up);return (l,r,down,up,None,None)
  mid=(l+r)//2;left=build(arr,l,mid);right=build(arr,mid,r)
  graph[down]+=[left[2],right[2]];graph[left[3]].append(up);graph[right[3]].append(up)
  return(l,r,down,up,left,right)
 for d,arr in levels.items():arr.sort(key=lambda u:tin[u]);trees[d]=build(arr,0,len(arr))
 def connect(t,l,r,x):
  a,b,d,u,left,right=t
  if r<=a or b<=l:return
  if l<=a and b<=r:graph[2*x+1].append(d);graph[u].append(2*x);return
  connect(left,l,r,x);connect(right,l,r,x)
 import bisect
 for x,y in faults:
  d=dep[x]+y
  if d not in levels:continue
  arr=levels[d];ts=[tin[u] for u in arr];l=bisect.bisect_left(ts,tin[x]);r=bisect.bisect_left(ts,tout[x])
  if l<r:connect(trees[d],l,r,x)
 comp=scc(graph)
 if any(comp[2*u]==comp[2*u+1] for u in range(n)):return None
 return [comp[2*u+1]>comp[2*u] for u in range(n)]

def check_b():
 for _ in range(600):
  n=R.randrange(2,9);par=[-1]+[R.randrange(i) for i in range(1,n)];faults=[(R.randrange(n),R.randrange(1,n+1)) for i in range(R.randrange(20))];dep=[0]*n
  for i in range(1,n):dep[i]=dep[par[i]]+1
  def valid(bits):
   if any(not(bits[i] or bits[par[i]]) for i in range(1,n)):return False
   for x,y in faults:
    if not bits[x]:continue
    for u in range(n):
     p=u
     while p!=-1 and p!=x:p=par[p]
     if p==x and dep[u]-dep[x]==y and bits[u]:return False
   return True
  exists=any(valid(bits) for bits in itertools.product((False,True),repeat=n));got=base_stations(par,faults)
  assert (got is not None)==exists and (got is None or valid(got)),(par,faults,got,exists)
 return 600

def grid(n,m):
 transpose=n>m
 if transpose:n,m=m,n
 if n<=2:
  if m>=9:return None
  ans=[list('012' if m==3 else '001122') for _ in range(n)]
 elif n==3:
  ans=[[s[j%6] for j in range(m)] for s in ('220011','102102','011220')]
 elif n==4:
  ans=[[s[j%6] for j in range(m)] for s in ('220011','102102','102102','011220')]
 else:
  if n%3:n,m=m,n;transpose=not transpose
  patterns=('220011','102102','011220');ans=[]
  for i in range(n):
   row=i%3 if (i//3)%2==0 else 2-i%3
   ans.append([patterns[row][j%6] for j in range(m)])
 if transpose:ans=[list(row) for row in zip(*ans)]
 return ans

def check_c():
 cases=0
 for n in range(1,61):
  for m in range(1,61):
   if n*m%3:continue
   a=grid(n,m)
   if a is None:assert min(n,m)<=2 and max(n,m)>=9;continue
   assert len(a)==n and all(len(row)==m for row in a)
   assert all(sum(row.count(c) for row in a)==n*m//3 for c in '012')
   for i in range(n):
    for j in range(m):
     if i>=2:assert not a[i][j]==a[i-1][j]==a[i-2][j]
     if j>=2:assert not a[i][j]==a[i][j-1]==a[i][j-2]
   for c in '012':
    cells={(i,j) for i in range(n) for j in range(m) if a[i][j]==c};seen={next(iter(cells))};q=list(seen)
    for i,j in q:
     for di,dj in itertools.product((-1,0,1),repeat=2):
      v=(i+di,j+dj)
      if v in cells and v not in seen:seen.add(v);q.append(v)
    assert seen==cells,(n,m,c)
   cases+=1
 return cases

def magic(a,b):
 a=tuple(sorted(a));b=tuple(sorted(b));return a==b or (sum(x%2 for x in a)==sum(x%2 for x in b) and any(y-x==1 for x,y in zip(a,a[1:])) and any(y-x==1 for x,y in zip(b,b[1:])))

def check_e():
 # Bounded BFS is only used to certify positive reachability; negatives use invariants.
 cases=0
 for n in range(1,5):
  states=list(itertools.combinations_with_replacement(range(-2,5),n));index={s:i for i,s in enumerate(states)};graph=[[] for s in states]
  for idx,s in enumerate(states):
   for i in range(n):
    for j in range(i+1,n):
     if s[j]-s[i]!=1:continue
     for delta in (-1,1):
      t=list(s);t[i]+=delta;t[j]+=delta;t=tuple(sorted(t))
      if t in index:graph[idx].append(index[t])
  comp=[-1]*len(states);cid=0
  for i in range(len(states)):
   if comp[i]>=0:continue
   comp[i]=cid;q=[i]
   for u in q:
    for v in graph[u]:
     if comp[v]<0:comp[v]=cid;q.append(v)
   cid+=1
  inner=list(itertools.combinations_with_replacement(range(0,3),n))
  for a in inner:
   for b in inner:assert magic(a,b)==(comp[index[a]]==comp[index[b]]);cases+=1
 return cases

def stab(intervals):
 points=[]
 for l,r in sorted(intervals,key=lambda x:x[1]):
  if not points or points[-1]<l:points.append(r)
 return len(points)

def check_f():
 cases=0
 for n in range(1,5):
  intervals=list(itertools.combinations_with_replacement(range(1,n+1),2))
  for mask in range(1,1<<len(intervals)):
   qs=tuple(v for i,v in enumerate(intervals) if mask>>i&1)
   @functools.lru_cache(None)
   def solve(lo,hi,items):
    if not items:return 0
    return 1+min(max(solve(lo,x-1,tuple((l,r) for l,r in items if r<x)),solve(x+1,hi,tuple((l,r) for l,r in items if l>x))) for x in range(lo,hi+1))
   assert stab(qs).bit_length()==solve(1,n,qs);cases+=1
 return cases

def projection(x,l,R2):
 def get(t):return [max(-b,min(b,t*a)) for a,b in zip(x,l)]
 if sum(v*v for v in get(1))<=R2:return get(1)
 lo=0.;hi=1.
 for _ in range(90):
  mid=(lo+hi)/2
  if sum(v*v for v in get(mid))<=R2:lo=mid
  else:hi=mid
 return get(lo)

def check_g():
 for _ in range(500):
  n=R.randrange(2,7);x=[R.randrange(-9,10) for i in range(n)];l=[R.randrange(1,5) for i in range(n)];R2=R.randrange(1,30);y=projection(x,l,R2);best=float('inf')
  box=[max(-b,min(b,a)) for a,b in zip(x,l)]
  if sum(v*v for v in box)<=R2:best=sum((a-b)**2 for a,b in zip(x,box))
  for mask in range(1<<n):
   fixed=sum(l[i]**2 for i in range(n) if mask>>i&1);norm=sum(x[i]**2 for i in range(n) if not(mask>>i&1))
   if fixed>R2 or norm==0:continue
   t=math.sqrt((R2-fixed)/norm);z=[math.copysign(l[i],x[i]) if mask>>i&1 else t*x[i] for i in range(n)]
   if all(abs(z[i])<=l[i]+1e-10 for i in range(n)):best=min(best,sum((x[i]-z[i])**2 for i in range(n)))
  assert sum(v*v for v in y)<=R2+1e-7 and abs(sum((a-b)**2 for a,b in zip(x,y))-best)<1e-7,(x,l,R2,y,best)
 return 500

def restore_set(values):
 full=(1<<30)-1;count=0
 def ask(c):
  nonlocal count
  count+=1;return max(a^c for a in values)^c
 hi=ask(0);lo=ask(full);known={lo,hi};stack=[(lo,hi)]
 while stack and len(known)<len(values):
  lo,hi=stack.pop()
  if lo==hi:continue
  bit=(lo^hi).bit_length()-1;highmask=full^((1<<(bit+1))-1);common=(~lo)&highmask
  lm=ask(common|(1<<bit));rm=ask(common|((1<<bit)-1));known.update((lm,rm))
  assert lo<=lm<rm<=hi
  if lo<lm:stack.append((lo,lm))
  if rm<hi:stack.append((rm,hi))
 assert known==set(values) and count<=2*len(values)-2
 return count

def check_h():
 cases=0
 for mask in range(1<<12):
  values=[i for i in range(12) if mask>>i&1]
  if len(values)>=2:restore_set(values);cases+=1
 for _ in range(1000):restore_set(R.sample(range(1<<30),R.randrange(2,40)));cases+=1
 return cases

def arrange(a,b):
 a=list(a);b=list(b);n=len(a);counts=collections.Counter(a+b)
 if any(c%2 for c in counts.values()):return None
 operations=[];cost=0
 def swap(i,j):
  nonlocal cost
  a[i],b[j]=b[j],a[i];operations.append((i,j));cost+=abs(i-j)
 for i in range(n):
  if a[i]==b[i]:continue
  x,y=a[i],b[i]
  px=next(p for p in range(i+1,n) if a[p]==x or b[p]==x);py=next(p for p in range(i+1,n) if a[p]==y or b[p]==y)
  if px<=py:
   if a[px]!=x:swap(px,px)
   swap(px,i)
  else:
   if b[py]!=y:swap(py,py)
   swap(i,py)
 assert a==b and len(operations)<=2*n
 return cost,operations

def check_k():
 cases=0
 for n in range(1,4):
  values=range(1,n+1);groups={}
  for state in itertools.product(values,repeat=2*n):
   got=arrange(state[:n],state[n:]);counts=tuple(sorted(collections.Counter(state).items()))
   if any(c%2 for v,c in counts):assert got is None;cases+=1;continue
   groups.setdefault(counts,[]).append(state)
  for counts,states in groups.items():
   half=[v for v,c in counts for _ in range(c//2)];distance={};q=[]
   for p in set(itertools.permutations(half)):
    s=p+p;distance[s]=0;heapq.heappush(q,(0,s))
   while q:
    d,s=heapq.heappop(q)
    if distance[s]!=d:continue
    for i in range(n):
     for j in range(n):
      t=list(s);t[i],t[n+j]=t[n+j],t[i];t=tuple(t);nd=d+abs(i-j)
      if nd<distance.get(t,10**9):distance[t]=nd;heapq.heappush(q,(nd,t))
   for s in states:assert arrange(s[:n],s[n:])[0]==distance[s];cases+=1
 return cases

def determinant(mat,mod):
 a=[row[:] for row in mat];ans=1
 for i in range(len(a)):
  p=next((j for j in range(i,len(a)) if a[j][i]%mod),None)
  if p is None:return 0
  if p!=i:a[i],a[p]=a[p],a[i];ans=-ans
  ans=ans*a[i][i]%mod;inv=pow(a[i][i],-1,mod)
  for j in range(i+1,len(a)):
   ratio=a[j][i]*inv%mod
   for k in range(i,len(a)):a[j][k]=(a[j][k]-ratio*a[i][k])%mod
 return ans%mod

def check_m():
 cases=0;mod=998244353
 for _ in range(100):
  n=R.randrange(1,8);a=[R.randrange(mod) for i in range(n)];A=[[(a[j]+(i==j))%mod for j in range(n)] for i in range(n)]
  for mask in range(1<<n):
   ids=[i for i in range(n) if mask>>i&1];got=determinant([[A[i][j] for j in ids] for i in ids],mod);assert got==(1+sum(a[i] for i in ids))%mod;cases+=1
 return cases

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
 methods={'A':'2500 modular comparisons plus 500 signed floor-sum cases against direct day enumeration','B':'600 random rooted-tree fault systems; compressed implication graph versus all station subsets and returned assignment verification','C':'all dimensions through 60; actual equal counts, no three equal, and eight-neighbor connectivity; no-solution family relies on proof','E':'small multisets via explicit bounded-state move graph with expanded [-2,4] search, compared on [0,2] targets','F':'all nonempty interval families for array sizes through four; every recursive pivot choice versus stabbing/height formula','G':'500 box-ball projections versus exhaustive active-face stationary candidates and feasibility','H':'all subsets of a 12-value universe plus 1000 random 30-bit sets; exact oracle transcript and query bound','K':'all row pairs through n=3; multi-source Dijkstra over every cross-row swap for true minimum cost','M':'all principal minors of 100 random matrices, modular Gaussian elimination versus required determinant formula'}
 checks={}
 for c in methods:
  n=globals()['check_'+c.lower()]();checks[c]={'passed':True,'cases':n,'method':methods[c]};print(c,n,flush=True)
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';report={'scope':'2025 ICPC Wuhan A B C E F G H K M','status':'passed','seed':2609,'limitations':'Independent small-case checks; no online submissions or maximum-scale timing. H uses a simulated fixed-set oracle; adaptive safety and query bound are proved in the text. E negative cases rely on invariants; C impossible narrow boards rely on proof.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-wuhan-*.md'))}}
 output=Path(args.output) if args.output else root/'regional_editorial_validation_wuhan_2025.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
