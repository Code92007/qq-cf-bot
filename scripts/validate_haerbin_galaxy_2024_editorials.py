"""Reproduce independent checks for 2024 CCPC Harbin F.

The tested algorithm uses a heap, linked neighboring groups, permanent DSU
coincidence, parity-compressed oscillators and simultaneous event closure.
The small-instance oracle recomputes every left/right sum for every second.
This is a correctness model, not a maximum-size performance certification.
"""
from dataclasses import dataclass
import heapq

def sign(x):return (x>0)-(x<0)
@dataclass
class Group:
 roots:tuple
 x:int
 velocity:int
 time:int
 left_weight:int
 previous:int=-1
 following:int=-1
 active:bool=True
 def left(self,t):return self.x+self.velocity*(t-self.time)
 def right(self,t):return self.left(t)+(len(self.roots)-1)
 def atoms(self,t):
  if len(self.roots)==1:return [(self.left(t),self.roots[0])]
  return [(self.x+((i+t-self.time)&1),root) for i,root in enumerate(self.roots)]

def galaxy(initial,weights,queries):
 n=len(initial);parent=list(range(n));size=[1]*n;weight=weights[:];total=sum(weights);groups=[];owner=[-1]*n;heap=[];event_count=0
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):
  a=find(a);b=find(b)
  if a==b:return a
  if size[a]<size[b]:a,b=b,a
  parent[b]=a;size[a]+=size[b];weight[a]+=weight[b];return a
 def consolidate(atoms):
  atoms.sort();out=[]
  for x,r in atoms:
   if out and out[-1][0]==x:out[-1]=(x,union(out[-1][1],r))
   else:out.append((x,find(r)))
  return out
 def build(atoms,t,prefix):
  result=[];i=0
  while i<len(atoms):
   x,a=atoms[i];wa=weight[a];va=sign(total-2*prefix-wa);roots=(a,);speed=va
   if i+1<len(atoms):
    y,b=atoms[i+1];wb=weight[b];vb=sign(total-2*(prefix+wa)-wb);delta=total-2*prefix-wa-wb
    if y==x+1 and va==1 and vb==-1 and sign(delta+wa)==1 and sign(delta-wb)==-1:roots=(a,b);speed=0
   node=len(groups);groups.append(Group(roots,x,speed,t,prefix));result.append(node)
   for r in roots:owner[r]=node;prefix+=weight[r]
   i+=len(roots)
  for a,b in zip(result,result[1:]):groups[a].following=b;groups[b].previous=a
  return result
 def schedule(a,b,t):
  if a<0 or b<0:return
  A,B=groups[a],groups[b];gap=B.left(t)-A.right(t);assert gap>0,(t,a,b,gap,A,B)
  speed=A.velocity-B.velocity
  if speed>0:heapq.heappush(heap,(t+(gap+speed-1)//speed,a,b))
 initial_atoms=consolidate(list(zip(initial,range(n))));ids=build(initial_atoms,0,0)
 for a,b in zip(ids,ids[1:]):schedule(a,b,0)
 def event(t,a,b):
  nonlocal event_count
  first,last=a,b;lo=min(groups[a].left(t),groups[b].left(t));hi=max(groups[a].right(t),groups[b].right(t))
  while True:
   changed=False
   while groups[first].previous>=0:
    p=groups[first].previous
    if groups[p].right(t)<lo:break
    first=p;lo=min(lo,groups[p].left(t));hi=max(hi,groups[p].right(t));changed=True
   while groups[last].following>=0:
    q=groups[last].following
    if groups[q].left(t)>hi:break
    last=q;lo=min(lo,groups[q].left(t));hi=max(hi,groups[q].right(t));changed=True
   if not changed:break
  previous=groups[first].previous;following=groups[last].following;prefix=groups[first].left_weight;atoms=[];node=first
  while True:
   group=groups[node];atoms.extend(group.atoms(t));group.active=False
   if node==last:break
   node=group.following
  new=build(consolidate(atoms),t,prefix);first,last=new[0],new[-1];groups[first].previous=previous;groups[last].following=following
  if previous>=0:groups[previous].following=first
  if following>=0:groups[following].previous=last
  for a,b in zip([previous]+new,new+[following]):schedule(a,b,t)
  event_count+=1
 result=[None]*len(queries)
 for qi in sorted(range(len(queries)),key=lambda j:queries[j][0]):
  t,i=queries[qi]
  while heap and heap[0][0]<=t:
   tm,a,b=heapq.heappop(heap)
   if not groups[a].active or not groups[b].active or groups[a].following!=b:continue
   event(tm,a,b)
  r=find(i);group=groups[owner[r]]
  if len(group.roots)==1:result[qi]=group.left(t)
  else:result[qi]=group.x+((group.roots.index(r)+t-group.time)&1)
 return result,event_count

def direct(initial,weights,limit):
 pos=initial[:];answer=[pos[:]]
 for t in range(limit):
  pos=[x+sign(sum(weights[j] for j,y in enumerate(pos) if y>x)-sum(weights[j] for j,y in enumerate(pos) if y<x)) for x in pos];answer.append(pos[:])
 return answer

def run_validation():
 from itertools import product
 from pathlib import Path
 import hashlib,json,random
 rng=random.Random(20241020);counts={};most=0;queries_checked=0
 def compare(initial,weights,limit,category,shuffle=False):
  nonlocal most,queries_checked
  queries=[(t,i) for t in range(limit+1) for i in range(len(initial))]
  if shuffle:
   queries.extend(queries[:min(50,len(queries))]);rng.shuffle(queries)
  got,events=galaxy(initial,weights,queries);oracle=direct(initial,weights,limit)
  want=[oracle[t][i] for t,i in queries]
  assert got==want,(initial,weights,next((q,a,b) for q,a,b in zip(queries,got,want) if a!=b))
  counts[category]=counts.get(category,0)+1;most=max(most,events);queries_checked+=len(queries)
 examples=[([-100,0,1],[5,-4,6]),([0,1,2,3,4,5],[1,1,10,10,1,1]),([0,1,-1,2],[1,2,3,2])]
 for initial,weights in examples:compare(initial,weights,30,'original_focused')
 for n in range(1,6):
  for weights in product(range(-2,3),repeat=n):compare(list(range(n)),list(weights),12,'exhaustive_weights')
 for _ in range(5000):
  n=rng.randrange(1,15);initial=[rng.randrange(-30,31) for i in range(n)];weights=[rng.randrange(-20,21) for i in range(n)]
  compare(initial,weights,100,'random_literal',shuffle=True)
 special=[([-100,0,1,2],[100,-4,6,4]),([-100,0,1,2],[5,-4,6,3]),([-2,-1,0,1,2],[1,-2,0,2,-1]),([0,1,2,3,4,5],[1,1,10,10,1,1]),([-100,0,1],[5,-4,6])]
 for initial,weights in special:
  for reflected in (False,True):
   points=[-x if reflected else x for x in initial]
   for shift in (-999999900,0,999999800):compare([x+shift for x in points],weights,250,'boundary_contact',shuffle=True)
 for _ in range(200):
  n=rng.randrange(1,31);x=rng.choice((-10**9,0,10**9));initial=[x]*n;weights=[rng.randrange(-10**9,10**9+1) for i in range(n)]
  queries=[(t,i) for t in (0,1,2,10**9-1,10**9) for i in range(n)];rng.shuffle(queries)
  got,events=galaxy(initial,weights,queries);assert got==[x]*len(queries);assert events==0
  counts['coincident_large_time']=counts.get('coincident_large_time',0)+1;queries_checked+=len(queries)
 def two_planets(x,y,a,b,t):
  if x==y:return x,y
  va,vb=sign(b),-sign(a);d=y-x;c=va-vb
  if c<=0 or t<(d+c-1)//c:return x+va*t,y+vb*t
  contact=(d+c-1)//c
  if d%c==0:return (x+va*contact,)*2
  assert c==2 and va==1 and vb==-1
  phase=(t-contact)&1
  return x+contact-phase,y-contact+phase
 for test in range(2000):
  x,y=sorted([rng.choice((-10**9,-999999999,-1,0,1,999999999,10**9)) for _ in range(2)])
  a,b=[rng.choice((-10**9,-1,0,1,10**9)) for _ in range(2)]
  times=[0,1,2,10**9-1,10**9,rng.randrange(10**9+1)];queries=[(t,i) for t in times for i in (0,1)];rng.shuffle(queries)
  got,events=galaxy([x,y],[a,b],queries);want=[two_planets(x,y,a,b,t)[i] for t,i in queries]
  assert got==want,(x,y,a,b,queries,got,want)
  counts['two_planet_analytic']=counts.get('two_planet_analytic',0)+1;queries_checked+=len(queries);most=max(most,events)
 # Official sample output is checked independently of the direct simulator.
 sample_queries=[(t,i) for t in range(3) for i in range(4)]
 sample,_=galaxy([0,1,-1,2],[1,2,3,2],sample_queries)
 assert sample==[0,1,-1,2,1,0,0,1,0,1,1,0],sample
 counts['official_sample']=1;queries_checked+=12
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 file=root/'editorials/2024/ccpc-haerbin-F.md'
 report={
  'scope':'2024 CCPC Harbin F', 'seed':20241020, 'status':'passed',
  'limitations':'Complete event algorithm checked against literal small-instance simulation and exact two-planet formulas. No online judge submission and no n=100000 performance test.',
  'checks':{'F':{'cases':sum(counts.values()),'passed':True,
   'method':'Full priority-queue/linked-list/DSU event simulation versus all-pairs simultaneous updates; negative-weight drifting pairs, rigid triples, simultaneous two-sided oscillator contacts, repeated initial coordinates, shuffled and repeated queries; analytic two-planet checks at coordinates/weights/times up to 1e9.',
   'categories':counts,'queries_checked':queries_checked,'maximum_events_observed':most}},
  'content_sha256':{file.name:hashlib.sha256(file.read_bytes()).hexdigest()}}
 out=root/'regional_editorial_validation_haerbin_galaxy_2024.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report['checks'],ensure_ascii=False))

if __name__=='__main__':run_validation()
