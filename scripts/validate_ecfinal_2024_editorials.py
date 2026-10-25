"""Independent small-case checks for ECFinal 2024 A/G/I/K; no online judge claim."""
import argparse,collections,functools,hashlib,heapq,itertools,json,math,random
from pathlib import Path
R=random.Random(1894)
def interval_greedy(a):
 active=[];used=set();groups=[];events=sorted([(l,0,i) for i,(l,r) in enumerate(a)]+[(r,1,i) for i,(l,r) in enumerate(a)])
 for t,kind,i in events:
  if kind==0:heapq.heappush(active,(a[i][1],i))
  elif i not in used:
   while active and active[0][1] in used:heapq.heappop(active)
   if len(active)<3:return None
   g=[heapq.heappop(active)[1] for j in range(3)];used.update(g);groups.append(g)
 return groups

def check_a():
 count=0
 for n in [3,6,9,12]:
  for _ in range(500):
   a=[tuple(sorted((R.randrange(8),R.randrange(8)))) for i in range(n)]
   @functools.lru_cache(None)
   def brute(mask):
    if not mask:return True
    i=(mask&-mask).bit_length()-1;rest=[j for j in range(i+1,n) if mask>>j&1]
    return any(max(a[x][0] for x in [i,j,k])<=min(a[x][1] for x in [i,j,k]) and brute(mask^(1<<i)^(1<<j)^(1<<k)) for j,k in itertools.combinations(rest,2))
   got=interval_greedy(a);assert (got is not None)==brute((1<<n)-1)
   if got:
    assert sorted(x for g in got for x in g)==list(range(n))
    assert all(max(a[x][0] for x in g)<=min(a[x][1] for x in g) for g in got)
   count+=1
 return count

def check_g():
 count=0
 for A in range(2,18):
  for B in range(1,18):
   if math.gcd(A,B)>1:continue
   for n in range(1,200):
    base=(n-1)%B+1;t=(-base*pow(B,-1,A))%A;got=n<=base+t*B
    seen=set();x=n
    while x not in seen:seen.add(x);x=x//A if x%A==0 else x+B
    assert got==(x==n),(A,B,n);count+=1
 return count

def tree_prufer(n,seq):
 degree=[1]*n;adj=[[] for _ in range(n)]
 for x in seq:degree[x]+=1
 for x in list(seq)+[n-1]:
  u=next(i for i in range(n) if degree[i]==1);degree[u]-=1;degree[x]-=1;adj[u].append(x);adj[x].append(u)
 return adj

def color_tree(adj):
 n=len(adj);par=[-1]*n;order=[0];par[0]=0;dep=[0]*n
 for u in order:
  for v in adj[u]:
   if v!=par[u]:par[v]=u;dep[v]=dep[u]^1;order.append(v)
 matched=[False]*n
 for u in order:
  if not matched[u]:
   for v in adj[u]:
    if par[v]==u and not matched[v]:matched[u]=matched[v]=True;break
 free=[i for i in range(n) if not matched[i]];assert all(len(adj[i])==1 for i in free)
 color=dep[:]
 for j,i in enumerate(free):color[i]=int(j>=len(free)//2)
 return color

def check_i():
 count=0
 for n in [2,4,6]:
  for seq in itertools.product(range(n),repeat=n-2):
   adj=tree_prufer(n,seq);color=color_tree(adj);assert sum(color)==n//2
   for s in range(n):
    stack=[(s,-1,0)]
    while stack:
     u,p,d=stack.pop();d+=2*color[u]-1;assert abs(d)<=3
     stack.extend((v,u,d) for v in adj[u] if v!=p)
   count+=1
 for _ in range(200):
  n=2*R.randrange(2,51);adj=tree_prufer(n,[R.randrange(n) for _ in range(n-2)]);c=color_tree(adj);assert sum(c)==n//2
  for s in range(n):
   stack=[(s,-1,0)]
   while stack:
    u,p,d=stack.pop();d+=2*c[u]-1;assert abs(d)<=3;stack.extend((v,u,d) for v in adj[u] if v!=p)
  count+=1
 return count

def boundary_order(adj,walls):
 n=len(adj);cnt=[0]*n
 for wall in walls:
  for u in wall:cnt[u]+=1
 pending=set(map(frozenset,walls));front={0};seen={0};q=collections.deque([0] if cnt[0]==0 else []);order=[]
 while front:
  while q:
   u=q.popleft();front.remove(u);order.append(u)
   for v in adj[u]:
    if v not in seen:
     seen.add(v);front.add(v)
     if cnt[v]==0:q.append(v)
  if not front:break
  wall=frozenset(front)
  if wall not in pending:return None
  pending.remove(wall)
  for u in wall:
   cnt[u]-=1
   if cnt[u]==0:q.append(u)
 if pending:return None
 return order

def all_boundaries(adj):
 result=[]
 def rec(done,front,seq):
  if not front:result.append(frozenset(seq));return
  current=frozenset(front)
  for u in front:
   nd=done|{u};nf=(front-{u})|set(adj[u])-nd;rec(nd,nf,seq+[current])
 rec(set(),{0},[]);return result

def check_k():
 cases=0
 for n in range(2,7):
  for _ in range(75):
   adj=[set() for i in range(n)]
   for i in range(1,n):j=R.randrange(i);adj[i].add(j);adj[j].add(i)
   for i,j in itertools.combinations(range(n),2):
    if R.random()<.25:adj[i].add(j);adj[j].add(i)
   legal=all_boundaries(adj)
   for repeat in range(10):
    if repeat<5:walls=R.sample(list(R.choice(legal)),R.randrange(1,n+1))
    else:walls=list(set(frozenset(i for i in range(n) if mask>>i&1) for mask in [R.randrange(1,1<<n) for _ in range(R.randrange(1,n+1))]))
    got=boundary_order(adj,walls);expected=any(set(walls)<=b for b in legal);assert (got is not None)==expected,(adj,walls)
    if got:
     pos={v:i for i,v in enumerate(got)};d=[10**9]*n;d[0]=0;q=[(0,0)];visited=set();observed=[]
     while q:
      observed.append(frozenset(v for v in range(n) if d[v]<10**9 and v not in visited))
      du,u=heapq.heappop(q)
      if u in visited:continue
      visited.add(u)
      for v in adj[u]:
       nd=du+abs(pos[u]-pos[v])
       if nd<d[v]:d[v]=nd;heapq.heappush(q,(nd,v))
     assert len(set(d))==n and set(walls)<=set(observed)
    cases+=1
 return cases
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args();methods={'A':'2000 random interval families of 3/6/9/12 items versus exhaustive triple partitions and returned grouping checks','G':'all coprime A,B through 17 and starts below 200 versus exact cycle simulation','I':'all labeled trees with 2/4/6 vertices plus 200 random even trees, all simple paths and color balance','K':'3750 connected-graph boundary requests against every connected exploration order, then actual Dijkstra for constructed weights'};checks={}
 for c,method in methods.items():
  count=globals()['check_'+c.lower()]();checks[c]={'passed':True,'cases':count,'method':method};print(c,count,flush=True)
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';report={'scope':'2024 ICPC ECFinal A G I K','status':'passed','seed':1894,'limitations':'Small-case independent checks; no online submissions or maximum-scale timing.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2024').glob('icpc-ecfinal-*.md'))}};(Path(args.output) if args.output else root/'regional_editorial_validation_ecfinal_2024.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
