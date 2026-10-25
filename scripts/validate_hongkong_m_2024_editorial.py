"""Exact independent checks for Hong Kong 2024 M: Godzilla."""
from itertools import combinations, product
from pathlib import Path
import hashlib,json,random

ROOT=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
RNG=random.Random(20241229)
NEG=-10**30

class DSU:
 def __init__(self,n):self.p=list(range(n));self.sz=[1]*n;self.cycle=[False]*n
 def find(self,x):
  while self.p[x]!=x:x=self.p[x]
  return x
 def add(self,u,v):
  u=self.find(u);v=self.find(v)
  if u==v:
   if self.cycle[u]:return False
   self.cycle[u]=True;return True
  if self.cycle[u] and self.cycle[v]:return False
  if self.sz[u]<self.sz[v]:u,v=v,u
  self.p[v]=u;self.sz[u]+=self.sz[v];self.cycle[u]|=self.cycle[v];return True

def basis(V,edges,ids):
 d=DSU(V)
 return len(ids)==V and all(d.add(edges[i][0],edges[i][1]) for i in ids)

def greedy(V,edges):
 d=DSU(V);out=[]
 for i in sorted(range(len(edges)),key=lambda i:(-edges[i][2],i)):
  if d.add(edges[i][0],edges[i][1]):out.append(i)
 assert len(out)==V
 return out

def conv(a,b):
 c=[NEG]*4
 for i,x in enumerate(a):
  for j,y in enumerate(b):
   if x!=NEG and y!=NEG:c[(i+j)%4]=max(c[(i+j)%4],x+y)
 return c
def vmax(*vectors):return [max(z) for z in zip(*vectors)]

def small_kernel(t,U,E,D):
 if t==1:return U[0]
 if t==2:return vmax(conv(U[0],U[1]),conv(E[0,1],vmax(*U)),D[0,1])
 ans=conv(conv(U[0],U[1]),U[2]);allU=vmax(*U)
 for i,j in combinations(range(3),2):
  k=3-i-j
  pair=vmax(conv(E[i,j],vmax(U[i],U[j])),D[i,j])
  ans=vmax(ans,conv(pair,U[k]))
  eik=E[min(i,k),max(i,k)];ejk=E[min(j,k),max(j,k)]
  ans=vmax(ans,conv(D[i,j],vmax(eik,ejk)))
 for i in range(3):
  j,k=[v for v in range(3) if v!=i]
  ans=vmax(ans,conv(conv(E[min(i,j),max(i,j)],E[min(i,k),max(i,k)]),allU))
 return vmax(ans,conv(conv(E[0,1],E[0,2]),E[1,2]))

def grouped_kernel(V,edges,B,removed):
 d=DSU(V);removed=set(removed)
 for i in B:
  if i not in removed:assert d.add(edges[i][0],edges[i][1])
 trees=sorted({d.find(v) for v in range(V) if not d.cycle[d.find(v)]});mp={r:i for i,r in enumerate(trees)};t=len(trees)
 assert t==len(removed)
 U=[[NEG]*4 for _ in trees];pairs={(i,j):[[] for z in range(4)] for i,j in combinations(range(t),2)}
 for eid,(u,v,w,e) in enumerate(edges):
  if eid in B:continue
  u=d.find(u);v=d.find(v)
  a=mp.get(u);b=mp.get(v)
  if a is None and b is None:continue
  if a is None or b is None or a==b:
   k=b if a is None else a;U[k][e]=max(U[k][e],w)
  else:pairs[min(a,b),max(a,b)][e].append(w)
 E={};D={}
 for key,buckets in pairs.items():
  buckets=[sorted(s,reverse=True)[:2] for s in buckets];E[key]=[s[0] if s else NEG for s in buckets];D[key]=[NEG]*4
  for i in range(4):
   for j in range(i,4):
    if i==j:
     if len(buckets[i])<2:continue
     val=sum(buckets[i])
    else:
     if not buckets[i] or not buckets[j]:continue
     val=buckets[i][0]+buckets[j][0]
    D[key][(i+j)%4]=max(D[key][(i+j)%4],val)
 return small_kernel(t,U,E,D)

def optimized_structure(V,edges):
 B=greedy(V,edges);Bset=set(B);sw=sum(edges[i][2] for i in B);se=sum(edges[i][3] for i in B)%4
 ans=[NEG]*4;ans[se]=sw
 for t in range(1,4):
  for removed in combinations(B,t):
   extra=grouped_kernel(V,edges,Bset,removed);w=sw-sum(edges[i][2] for i in removed);e=(se-sum(edges[i][3] for i in removed))%4
   for k,v in enumerate(extra):
    if v!=NEG:ans[(e+k)%4]=max(ans[(e+k)%4],w+v)
 return ans

def basis_oracle(V,edges):
 B=set(greedy(V,edges));ans=[NEG]*4;distance=[100]*4
 for ids in combinations(range(len(edges)),V):
  if not basis(V,edges,ids):continue
  w=sum(edges[i][2] for i in ids);e=sum(edges[i][3] for i in ids)%4;dist=len(B-set(ids))
  if w>ans[e]:ans[e]=w;distance[e]=dist
  elif w==ans[e]:distance[e]=min(distance[e],dist)
 assert all(d<=3 or v==NEG for d,v in zip(distance,ans))
 return ans

def attacks_oracle(n,m,edges):
 ans=[NEG]*4
 for choices in product(range(3),repeat=n*m):
  rows=[0]*n;cols=[0]*m;w=e=0
  for ch,(u,v,d,c) in zip(choices,edges):
   if ch==1:rows[u]+=1
   elif ch==2:cols[v-n]+=1
   else:continue
   w+=d;e+=c
  if rows==[1]*n and cols==[1]*m:ans[e%4]=max(ans[e%4],w)
 return ans

def direct_kernel(V,edges,B,removed):
 keep=set(B)-set(removed);rest=[i for i in range(len(edges)) if i not in B];ans=[NEG]*4
 for add in combinations(rest,len(removed)):
  if basis(V,edges,keep|set(add)):
   w=sum(edges[i][2] for i in add);e=sum(edges[i][3] for i in add)%4;ans[e]=max(ans[e],w)
 return ans

def dfs_preprocess(V,edges,B):
 d=DSU(V);adj=[[] for _ in range(V)];extra=[]
 for eid in B:
  u,v,_,_=edges[eid]
  if d.find(u)==d.find(v):extra.append(eid)
  else:
   assert d.add(u,v);adj[u].append((v,eid));adj[v].append((u,eid))
 tin=[0]*V;tout=[0]*V;depth=[0]*V;root=[0]*V;order=[];child={};roots=[]
 def dfs(v,p,r):
  root[v]=r;tin[v]=len(order);order.append(v)
  for u,eid in adj[v]:
   if u!=p:depth[u]=depth[v]+1;child[eid]=u;dfs(u,v,r)
  tout[v]=len(order)
 for v in range(V):
  if v not in order:roots.append(v);dfs(v,-1,v)
 return tin,tout,depth,root,order,child,extra,roots

def interval_components(V,edges,B,removed,pre):
 tin,tout,depth,root,order,child,extra,roots=pre
 affected={root[edges[eid][0]] for eid in removed};cuts=[child[eid] for eid in removed if eid in child]
 atoms=[];labels=[]
 for r in affected:
  points=sorted({tin[r],tout[r]}|{z for v in cuts if root[v]==r for z in [tin[v],tout[v]]})
  for l,end in zip(points,points[1:]):
   if l==end:continue
   v=order[l];anc=[u for u in cuts if tin[u]<=tin[v]<tout[u]];lab=max(anc,key=lambda u:depth[u]) if anc else r
   atoms.append((l,end));labels.append(lab)
 d=DSU(len(atoms));first={}
 for i,lab in enumerate(labels):
  if lab in first:
   u=d.find(i);v=d.find(first[lab]);d.p[u]=v
  else:first[lab]=i
 def atom(v):return next(i for i,(l,end) in enumerate(atoms) if l<=tin[v]<end)
 for eid in extra:
  u,v,_,_=edges[eid]
  if root[u] in affected and eid not in removed:assert d.add(atom(u),atom(v))
 actual=DSU(V)
 for eid in B:
  if eid not in removed:assert actual.add(edges[eid][0],edges[eid][1])
 for i,(l,end) in enumerate(atoms):
  v=order[l];assert d.cycle[d.find(i)]==actual.cycle[actual.find(v)]
  for x in range(l,end):assert actual.find(order[x])==actual.find(v)
 for i,(l,end) in enumerate(atoms):
  for j,(ll,ee) in enumerate(atoms):assert (d.find(i)==d.find(j))==(actual.find(order[l])==actual.find(order[ll]))

def main():
 cases=0;kernel_cases=0;interval_cases=0
 for n,m,repetitions in [(2,2,30),(2,3,25),(3,3,20),(3,4,12),(3,5,5),(4,4,5)]:
  V=n+m
  for z in range(repetitions):
   edges=[(i,n+j,RNG.randrange(1,30),RNG.randrange(4)) for i in range(n) for j in range(m)]
   got=optimized_structure(V,edges);ref=basis_oracle(V,edges)
   assert got==ref,(n,m,edges,got,ref)
   if n*m<=6 or (n==m==3 and z<3):assert got==attacks_oracle(n,m,edges)
   B=greedy(V,edges);pre=dfs_preprocess(V,edges,B)
   for t in range(1,4):
    for removed in combinations(B,t):
     assert grouped_kernel(V,edges,set(B),removed)==direct_kernel(V,edges,set(B),removed)
     kernel_cases+=1
     interval_components(V,edges,B,set(removed),pre);interval_cases+=1
   cases+=1
 for n,m,ds,es,expected in [(2,2,[[1,2],[3,4]],[[2,1],[0,3]],[NEG,NEG,10,NEG]),(3,3,[[1,2,3],[4,5,6],[7,8,9]],[[2,1,0],[0,3,2],[1,2,1]],[35,38,37,36])]:
  edges=[(i,n+j,ds[i][j],es[i][j]) for i in range(n) for j in range(m)]
  assert optimized_structure(n+m,edges)==expected;cases+=1
 path=ROOT/'editorials/2024/icpc-hongkong-M.md'
 report={'scope':'2024 ICPC Hong Kong M','status':'passed','seed':20241229,'limitations':'Exact small-instance validation of attack/pseudoforest equivalence, at-most-three exchange, tiny-kernel formulas, and DFS interval reconstruction. No maximum-scale timing, optimized two-dimensional sparse table, or online submission.','checks':{'M':{'passed':True,'cases':cases+kernel_cases+interval_cases,'full_instances':cases,'kernel_checks':kernel_cases,'interval_checks':interval_cases,'method':'all ternary attack choices on small grids; all size-(n+m) edge subsets through 4x4; every at-most-three deletion kernel versus all replacement edge subsets; DFS atoms versus direct DSU components; both official samples'}},'content_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest()}}
 (ROOT/'regional_editorial_validation_hongkong_m_2024.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report['checks']))

if __name__=='__main__':main()
