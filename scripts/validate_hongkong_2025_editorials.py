"""Independent checks for 2025 Hong Kong editorials (Python 3.10+)."""
import itertools,random,collections,functools,json,hashlib,argparse
from pathlib import Path
R=random.Random(3169)

def match_size(n1,adj,vertices):
 match=[-1]*n1
 def augment(r,vis):
  for l in adj[r]:
   if l in vis:continue
   vis.add(l)
   if match[l]<0 or augment(match[l],vis):match[l]=r;return True
  return False
 return sum(augment(r,set()) for r in vertices)

def matching_scan(n1,adj):
 n=len(adj);ml=[-1]*n1;mr=[-1]*n;result={}
 for r in range(n):
  queue=[r];vr={r};pl=[-1]*n1;free=-1
  for x in queue:
   for l in adj[x]:
    if pl[l]!=-1:continue
    pl[l]=x
    if ml[l]==-1:free=l;break
    if ml[l] not in vr:vr.add(ml[l]);queue.append(ml[l])
   if free!=-1:break
  if free==-1:
   old=min(vr)
   if old!=r:free=mr[old];mr[old]=-1
  while free!=-1:
   x=pl[free];old=mr[x];mr[x]=free;ml[free]=x;free=old
  for l in range(r+1):result[l,r]=sum(mr[x]!=-1 for x in range(l,r+1))
 return result

def check_a():
 cases=0
 for n1,n2 in [(2,3),(3,3)]:
  for mask in range(1<<(n1*n2)):
   adj=[[l for l in range(n1) if mask>>(r*n1+l)&1] for r in range(n2)]
   got=matching_scan(n1,adj)
   for (l,r),ans in got.items():assert ans==match_size(n1,adj,range(l,r+1))
   cases+=1
 for _ in range(300):
  n1=R.randrange(1,8);n2=R.randrange(1,9);adj=[[l for l in range(n1) if R.randrange(3)==0] for r in range(n2)]
  got=matching_scan(n1,adj)
  for (l,r),ans in got.items():assert ans==match_size(n1,adj,range(l,r+1))
  cases+=1
 return cases

def circuit_decode(n,edges):
 rev=[[] for _ in range(n)];out=[[] for _ in range(n)];deg=[0]*n
 for i,(u,v) in enumerate(edges):rev[v].append(i);out[u].append(i);deg[u]+=1
 queue=collections.deque(i for i in range(n) if deg[i]==0);alive=[True]*n
 while queue:
  v=queue.popleft();alive[v]=False
  for i in rev[v]:
   u=edges[i][0];deg[u]-=1
   if deg[u]==0:queue.append(u)
 keep=[alive[u] and alive[v] for u,v in edges];ind=[0]*n;xor=[0]*n
 for i,(u,v) in enumerate(edges):
  if keep[i]:ind[v]+=1;xor[v]^=i
 queue=collections.deque(v for v in range(n) if alive[v] and ind[v]==1);succ={}
 while queue:
  v=queue.popleft()
  if ind[v]!=1:continue
  edge=xor[v];u=edges[edge][0]
  if u in succ:continue
  succ[u]=v
  for i in out[u]:
   if i!=edge and keep[i]:
    keep[i]=False;w=edges[i][1];ind[w]-=1;xor[w]^=i
    if ind[w]==1:queue.append(w)
 assert len(succ)==sum(alive)
 return succ

def check_f():
 for _ in range(800):
  n=R.randrange(3,18);k=R.randrange(3,n+1);cycle=list(range(k));edges={(i,(i+1)%k) for i in range(k)}
  und={tuple(sorted(e)) for e in edges}
  for v in range(k,n):und.add((R.randrange(v),v))
  for u in range(n):
   for v in range(u+1,n):
    if R.randrange(4)==0:und.add((u,v))
  oriented=[(v,u) if (u,v)==(0,k-1) else (u,v) for u,v in und]
  perm=list(range(n));R.shuffle(perm);oriented=[(perm[u],perm[v]) for u,v in oriented];R.shuffle(oriented)
  got=circuit_decode(n,oriented);expected={perm[i]:perm[(i+1)%k] for i in range(k)};assert got==expected
 return 800

def check_h():
 cases=0
 for n in range(2,9):
  for s in itertools.product('ab',repeat=n):
   strings=[s[:i]+s[i+1:] for i in range(n)];best=0
   for i in range(n):
    for j in range(i):
     p=0
     while p<n-1 and strings[i][p]==strings[j][p]:p+=1
     best=max(best,p)
   got=n-1 if any(s[i]==s[i+1] for i in range(n-1)) else n-2;assert got==best;cases+=1
 return cases

def dfs_count(orders):
 n=len(orders[0]);m=len(orders);pos=[{v:i for i,v in enumerate(p)} for p in orders];base=orders[0]
 valid=[[True]*n for _ in range(n)]
 for l in range(n):
  mins=[n]*m;maxs=[-1]*m
  for r in range(l,n):
   for j in range(m):mins[j]=min(mins[j],pos[j][base[r]]);maxs[j]=max(maxs[j],pos[j][base[r]])
   valid[l][r]=all(maxs[j]-mins[j]==r-l and mins[j]==pos[j][base[l]] for j in range(m))
 f=[[0]*n for _ in range(n)];g=[[0]*n for _ in range(n)]
 for length in range(1,n+1):
  for l in range(n-length+1):
   r=l+length-1;f[l][r]=(1 if length==1 else g[l+1][r]) if valid[l][r] else 0
   g[l][r]=sum(f[l][t]*(1 if t==r else g[t+1][r]) for t in range(l,r+1))
 return f[0][n-1]

def check_i():
 cases=0
 for n in range(1,7):
  trees=[]
  # Any tree having base order 0..n-1 necessarily has parent[v]<v.
  for ps in itertools.product(*(range(v) for v in range(1,n))):
   children=[[] for _ in range(n)]
   for v,p in enumerate(ps,1):children[p].append(v)
   @functools.lru_cache(None)
   def orders(u):
    ans=set()
    for perm in itertools.permutations(children[u]):
     for sub in itertools.product(*(orders(v) for v in perm)):ans.add((u,)+sum(sub,()))
    return frozenset(ans)
   allorders=orders(0)
   if tuple(range(n)) in allorders:trees.append(allorders)
  choices=list(itertools.permutations(range(1,n)))
  for _ in range(60):
   want=[tuple(range(n))]+[(0,)+R.choice(choices) for j in range(R.randrange(3))]
   expected=sum(all(x in tree for x in want) for tree in trees);assert dfs_count(want)==expected,(n,want,dfs_count(want),expected);cases+=1
 return cases

def reverse_schedule(jobs):
 import heapq
 todo=sorted(jobs,reverse=True);i=0;end=sum(p for d,p in jobs);heap=[];answer=0
 while i<len(todo) or heap:
  while i<len(todo) and todo[i][0]>=end:heapq.heappush(heap,-todo[i][1]);i+=1
  if not heap:return None
  p=-heapq.heappop(heap);answer+=end;end-=p
 return answer

def check_j():
 for _ in range(350):
  n=R.randrange(1,8);ds=[R.randrange(1,20) for i in range(3)];jobs=[(R.choice(ds),R.randrange(1,6)) for i in range(n)];best=None
  for perm in itertools.permutations(jobs):
   t=0;cost=0
   for d,p in perm:
    t+=p;cost+=t
    if t>d:break
   else:best=cost if best is None else min(best,cost)
  assert reverse_schedule(jobs)==best,(jobs,reverse_schedule(jobs),best)
 return 350

def shift_rank(a):
 n=len(a);b=a+a;stack=[];nxt=[-1]*n
 for i in range(2*n-1,-1,-1):
  while stack and b[stack[-1]]<=b[i]:stack.pop()
  if i<n and stack and stack[-1]<i+n:nxt[i]=stack[-1]
  stack.append(i)
 groups={}
 for i,x in enumerate(a):groups.setdefault(x,[]).append(i)
 rank=[0]*n;nextid=0
 for value in sorted(groups,reverse=True):
  rows=[]
  for i in groups[value]:
   key=(0,0) if nxt[i]<0 else (-(nxt[i]-i),rank[nxt[i]%n])
   rows.append((key,i))
  rows.sort(reverse=True);last=None
  for key,i in rows:
   if key!=last:nextid-=1;last=key
   rank[i]=nextid
 p=min(range(n),key=lambda i:rank[i]);rot=a[p:]+a[:p];result=[];v=-1
 for x in rot:v=max(v,x);result.append(v)
 return tuple(result)

def check_k():
 cases=0
 for n in range(1,9):
  for a in itertools.product(range(1,4),repeat=n):
   def pref(b):
    out=[];x=-1
    for y in b:x=max(x,y);out.append(x)
    return tuple(out)
   expect=min(pref(a[p:]+a[:p]) for p in range(n));assert shift_rank(a)==expect,(a,shift_rank(a),expect);cases+=1
 return cases

def surface(a):
 n=len(a)//2;par=list(range(2*n));seen={};orient=True
 def find(x):
  while par[x]!=x:par[x]=par[par[x]];x=par[x]
  return x
 def join(a,b):par[find(a)]=find(b)
 for i,x in enumerate(a):
  ends=(i,(i+1)%(2*n)) if x>0 else ((i+1)%(2*n),i)
  if abs(x) in seen:
   j,old,sign=seen[abs(x)];join(ends[0],old[0]);join(ends[1],old[1]);orient&=(x*sign<0)
  else:seen[abs(x)]=(i,ends,x)
 return orient,len({find(i) for i in range(2*n)})-n+1

def check_l():
 cases=0
 for _ in range(500):
  n=R.randrange(1,8);a=[i for i in range(1,n+1) for t in range(2)];R.shuffle(a);a=[x*R.choice((-1,1)) for x in a];base=surface(a)
  for shift in range(2*n):assert surface(a[shift:]+a[:shift])==base;cases+=1
  assert surface([-x for x in a[::-1]])==base;cases+=1
  assert surface([n+1,-n-1]+a)==base;cases+=1
  for i,x in enumerate(a):
   if x<0:continue
   j=next(j for j in range(2*n) if j!=i and abs(a[j])==x)
   if j<i:continue
   for cut in range(i+1,j+1):
    s1=a[:i];s2=a[i+1:cut];s3=a[cut:j];s4=a[j+1:]
    rev=lambda s:[-x for x in s[::-1]]
    b=s1+rev(s3)+[x]+rev(s4)+s2+[a[j]] if a[j]==x else s1+s4+[x]+s3+s2+[a[j]]
    assert surface(b)==base,(a,b,base,surface(b));cases+=1
 assert surface([1,-1])==(True,2)
 assert surface([1,1])==(False,1)
 assert surface([1,2,-1,-2])==(True,0)
 return cases+3

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
 methods={'A':'all 2x3 and 3x3 bipartite graphs plus 300 random graphs; every interval compared to independent augmenting matching','F':'800 cycle-with-chords and outside-vertex graphs, random relabeling and edge order, exact directed-cycle recovery','H':'all binary strings of lengths 2..8 versus all deletion pairs and literal LCP','I':'360 DFS-order sets through six vertices versus enumeration of parent trees and all sibling orders','J':'350 job sets versus every permutation and exact deadlines/penalty','K':'all ternary arrays of lengths 1..8 versus all rotations and literal prefix maxima','L':'random explicit allowed cut/reversal/insertion/rotation operations preserve DSU invariants; sphere/projective-plane/torus examples; classification theorem itself is not a computational proof'}
 checks={}
 for letter in methods:
  count=globals()['check_'+letter.lower()]();checks[letter]={'passed':True,'cases':count,'method':methods[letter]};print(letter,count,flush=True)
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 report={'scope':'2025 ICPC Hong Kong A F H I J K L','status':'passed','seed':3169,'limitations':'Independent small-case checks; no online submissions or maximum-scale timing. L verifies operations and topological invariants, relying on the official classification-theorem argument for sufficiency.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-hongkong-*.md'))}}
 output=Path(args.output) if args.output else root/'regional_editorial_validation_hongkong_2025.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
