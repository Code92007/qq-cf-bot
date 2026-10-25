"""Independent small-case checks for 2025 Shenyang explanations (Python 3.10+)."""
import itertools,math,random,collections,functools,json,hashlib,argparse
from fractions import Fraction
from pathlib import Path
R=random.Random(2641)

def kth(n,k,a,b):
 q=min(n,math.isqrt(2*k)+2)
 while q>2 and (q-1)*(q-2)//2>=k:q-=1
 lo=0;hi=a*(q*q-1)+2*b*(q-1)
 def count(v):
  total=0
  for d in range(1,q):
   top=v-2*b*d-a*d*d
   if top<2*a*d:break
   total+=min(n-d,top//(2*a*d))
   if total>=k:break
  return total
 while lo<hi:
  mid=(lo+hi)//2
  if count(mid)>=k:hi=mid
  else:lo=mid+1
 return Fraction(lo,a)

def check_a():
 cases=0
 for n in range(2,16):
  for a in (1,2,5):
   for b in (0,1,9):
    vals=sorted(Fraction((j-i)*(a*(i+j)+2*b),a) for i in range(1,n+1) for j in range(i+1,n+1))
    for k,val in enumerate(vals,1):assert kth(n,k,a,b)==val;cases+=1
 return cases

def paint_cost(counts,a,b):
 freq=sorted(counts[1:],reverse=True);cost=a*sum(freq);best=cost
 for k,c in enumerate(freq,1):cost+=b*counts[0]+(b*(k-1)-a)*c;best=min(best,cost)
 return best

def check_b():
 cases=0
 for counts in itertools.product(range(4),repeat=4):
  for a,b in [(1,1),(4,1),(1,4),(5,3)]:
   best=a*sum(counts[1:])
   for k in range(1,4):
    for cols in itertools.permutations(range(1,4),k):
     cost=k*b*counts[0]+sum(counts[c]*min(a,b*cols.index(c)) if c in cols else a*counts[c] for c in range(1,4))
     best=min(best,cost)
   assert paint_cost(counts,a,b)==best;cases+=1
 return cases

def prime(m):
 p=m
 while any(p%d==0 for d in range(2,math.isqrt(p)+1)):p+=1
 return p

def check_c():
 cases=0
 for m in range(2,10):
  p=prime(m);base=list(range(m))+list(range(p-m));tail=list(range(p-m,m))
  for x in range(m):
   seq=list(range(m))+base[x:]+base[:x]+tail;assert all(seq.count(i)==3 for i in range(m))
   for mask in range(1,(1<<m)-1):
    bits=[mask>>v&1 for v in seq];known=bits[:m];u=[known[v] for v in base];v=bits[m:m+p];count=sum(u)
    decoded=(sum(i*z for i,z in enumerate(u))-sum(i*z for i,z in enumerate(v)))*pow(count,-1,p)%p
    assert decoded==x;cases+=1
 return cases

# Segment order: top, upper-left, upper-right, middle, lower-left, lower-right, bottom.
DIGITS=[0b1110111,0b0100100,0b1011101,0b1101101,0b0101110,0b1101011,0b1111011,0b0100101,0b1111111,0b1101111]
def allowed(states,repair):
 def ok(mask):return all(repair>>j&1 or ch=='W' or int(ch)==(mask>>j&1) for j,ch in enumerate(states))
 digits=[d for d,m in enumerate(DIGITS) if ok(m)];return len(digits),sum(d!=0 for d in digits),ok(0),set(digits)

def led_dp(rows,k):
 # (cost, all-empty possible) -> best, ways attaining best, all ways
 states={(0,True):(0,1,1)}
 for i,row in enumerate(rows):
  ns={}
  for mask in range(128):
   c=mask.bit_count();d,z,blank,_=allowed(row,mask);first=d if i==len(rows)-1 else z
   for (oldc,B),(best,ways,total) in states.items():
    if oldc+c>k:continue
    key=(oldc+c,B and blank);value=best*d+B*first;num=ways if d else total
    old=ns.get(key)
    if old is None:ns[key]=(value,num,total)
    else:
     ob,ow,ot=old;ns[key]=(max(ob,value),ow+num if ob==value else (num if value>ob else ow),ot+total)
  states=ns
 best=max(v[0] for v in states.values());ways=sum(v[1] for v in states.values() if v[0]==best);return best,ways

def check_d():
 cases=0
 for _ in range(80):
  n=R.choice((1,2));rows=[''.join(R.choice('W01') for j in range(7)) for i in range(n)];k=R.randrange(0,min(4,7*n));best=-1;ways=0
  for repaired in itertools.chain.from_iterable(itertools.combinations(range(7*n),c) for c in range(k+1)):
   masks=[0]*n
   for z in repaired:masks[z//7]|=1<<(z%7)
   infos=[allowed(row,m) for row,m in zip(rows,masks)];count=0
   for x in range(10**n):
    s=str(x).rjust(n,' ')
    if all(info[2] if d==' ' else int(d) in info[3] for info,d in zip(infos,s)):count+=1
   if count>best:best=count;ways=1
   elif count==best:ways+=1
  assert led_dp(rows,k)==(best,ways),(rows,k,led_dp(rows,k),(best,ways));cases+=1
 return cases

def orient(n,edges,x,y):
 adj=[[] for _ in range(n)]
 for i,(u,v) in enumerate(edges):adj[u].append((v,i));adj[v].append((u,i))
 bypair={tuple(sorted(e)):i for i,e in enumerate(edges)}
 if tuple(sorted((x,y))) not in bypair:
  return [(v,u) if u in (x,y) else (u,v) if v in (x,y) else (u,v) for u,v in edges]
 if len(edges)==n-1:return None
 def without(u,v,ban):
  prev={u:-1};queue=[u]
  for z in queue:
   for w,i in adj[z]:
    if i!=ban and w not in prev:prev[w]=z;queue.append(w)
  if v not in prev:return None
  path=[]
  while v!=-1:path.append(v);v=prev[v]
  return path[::-1]
 first=bypair[tuple(sorted((x,y)))];path=without(x,y,first);pre={x:-1,y:x};front=[x,y];checked={first};handle=None
 if path is None:
  for u in front:
   for v,i in adj[u]:
    if i in checked:continue
    checked.add(i);p=without(u,v,i)
    if p is not None:path=p;handle=u;break
    if v not in pre:pre[v]=u;front.append(v)
   if path is not None:break
 cycle=path;direction={}
 for u,v in zip(cycle,cycle[1:]+cycle[:1]):direction[bypair[tuple(sorted((u,v)))]]=(u,v)
 core=set(cycle)
 if handle is not None:
  stem=[];u=handle
  while u!=-1:stem.append(u);u=pre[u]
  stem=stem[::-1]
  if y not in stem:stem=[y]+stem
  for u,v in zip(stem,stem[1:]):direction[bypair[tuple(sorted((u,v)))]]=(u,v)
  core.update(stem)
 for i,(u,v) in enumerate(edges):
  if i in direction:continue
  assert not(u in core and v in core),(n,edges,x,y,cycle,core,(u,v))
  direction[i]=(v,u) if u in core else (u,v)
 return [direction[i] for i in range(len(edges))]

def check_f():
 cases=0
 for n in range(2,6):
  potential=list(itertools.combinations(range(n),2))
  for mask in range(1<<len(potential)):
   edges=[e for i,e in enumerate(potential) if mask>>i&1];adj=[[] for _ in range(n)]
   for u,v in edges:adj[u].append(v);adj[v].append(u)
   seen={0};queue=[0]
   for u in queue:
    for v in adj[u]:
     if v not in seen:seen.add(v);queue.append(v)
   if len(seen)<n:continue
   for x,y in itertools.combinations(range(n),2):
    answer=orient(n,edges,x,y)
    if answer is None:assert len(edges)==n-1 and y in adj[x]
    else:
     outgoing=[[] for _ in range(n)]
     for u,v in answer:outgoing[u].append(v)
     queue=[(x,y)];seen={(x,y)}
     for u,v in queue:
      assert u!=v
      for a in outgoing[u] or [u]:
       for b in outgoing[v] or [v]:
        if (a,b) not in seen:seen.add((a,b));queue.append((a,b))
    cases+=1
 return cases

def hull(points):
 points=sorted(set(points))
 def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 lower=[];upper=[]
 for p in points:
  while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
  lower.append(p)
 for p in points[::-1]:
  while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
  upper.append(p)
 return lower[:-1]+upper[:-1]
def area(p):return abs(sum(x*v-y*u for (x,y),(u,v) in zip(p,p[1:]+p[:1])))/2

def check_g():
 cases=0
 for w,h,v,z in itertools.product(range(1,6),repeat=4):
  P=[(0,0),(w,0),(w,h),(0,h)];Q=[(0,0),(v,0),(v,z),(0,z)];D=hull([(x-u,y-t) for x,y in P for u,t in Q]);ans=area(P)*area(Q)/area(D)
  expected=w*h*v*z/((w+v)*(h+z));assert abs(ans-expected)<1e-12;cases+=1
 P=[(0,0),(1,0),(0,1)];Q=[(0,0),(1,0),(0,1)];assert abs(area(P)*area(Q)/area(hull([(x-u,y-v) for x,y in P for u,v in Q]))-1/12)<1e-12;return cases+1

def check_i():
 cases=0
 for _ in range(200):
  records=sorted((R.randrange(300),R.randrange(8),R.randrange(5)) for i in range(100));seen=set();ball=[0]*8;prior=[]
  for t,a,b in records:
   first=(a,b) not in seen;seen.add((a,b));got=first and (t<240 or ball[a]<3)
   if got:ball[a]+=1
   old={(x,y) for tt,x,y in prior if x==a};expected=(a,b) not in old and (t<240 or len(old)<3)
   assert got==expected;prior.append((t,a,b));cases+=1
 return cases

def check_k():
 cases=0
 for _ in range(1000):
  n=R.randrange(2,10);P=R.sample([(x,y) for x in range(-5,6) for y in range(-5,6)],n);Q=P[:];s=R.randrange(n);t=s
  for step in range(R.randrange(30)):
   j=R.choice([i for i in range(n) if i!=t]);Q[t]=(2*Q[j][0]-Q[t][0],2*Q[j][1]-Q[t][1]);t=j
  target=tuple(sum(Q[i][d]-P[i][d] for i in range(n))+2*P[s][d] for d in (0,1))
  assert tuple(2*Q[t][d] for d in (0,1))==target
  if len(set(Q))==n:assert [i for i in range(n) if tuple(2*Q[i][d] for d in (0,1))==target]==[t]
  cases+=1
 return cases

def logic_circuit(n):
 gates=[]
 def add(op,x,y):gates.append((op,x,y));return n+len(gates)-1
 a=list(range(n))
 for i in range(n-2,-1,-1):a[i]=add('|',add('|',i,a[i+1]),a[i+1])
 f=a[0];answer=a[0]
 for i in range(1,n):
  b=add('|',f,a[i]);f=add('&',f,a[i]);answer=add('|',add('|',answer,a[i]),b)
 assert answer==n+len(gates)-1 and len(gates)<=6*n
 return gates

def check_l():
 cases=0
 for n in range(3,9):
  gates=logic_circuit(n)
  for vals in itertools.product(range(4),repeat=n):
   if not all(i in vals for i in range(3)):continue
   expected=max(range(3),key=lambda c:vals.index(c));state=list(vals)
   for op,i,j in gates:
    x,y=state[i],state[j]
    z=x if x==y else 3 if op=='&' else y if x==3 else x if y==3 else 3-x-y
    state.append(z)
   assert state[-1]==expected;cases+=1
 return cases

def tournament(seed,A,B):
 def go(ids):
  if len(ids)==1:return {ids[0]:Fraction(1)}
  h=len(ids)//2;left=go(ids[:h]);right=go(ids[h:]);ans={i:Fraction(0) for i in ids}
  for i,pi in left.items():
   for j,pj in right.items():
    ans[i]+=pi*pj*Fraction(A[i],A[i]+B[j]);ans[j]+=pi*pj*Fraction(B[j],A[i]+B[j])
  return ans
 return go(seed)

def check_m():
 for _ in range(50):
  A=[R.randrange(1,6) for i in range(8)];B=[R.randrange(1,6) for i in range(8)];seed=list(range(8));R.shuffle(seed);want=[Fraction(0)]*8
  for mask in range(128):
   alive=seed[:];prob=Fraction(1);bit=0
   while len(alive)>1:
    nxt=[]
    for i,j in zip(alive[::2],alive[1::2]):
     take=mask>>bit&1;bit+=1;prob*=Fraction(B[j] if take else A[i],A[i]+B[j]);nxt.append(j if take else i)
    alive=nxt
   want[alive[0]]+=prob
  got=tournament(seed,A,B);assert all(got[i]==want[i] for i in range(8)) and sum(got.values())==1
 assert tournament(list(range(8)),[1]*8,[1]*8)[0]==Fraction(1,8)
 return 51

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
 methods={'A':'all kth pairwise differences for n<=15 and nine (a,b) settings, exact fractions','B':'1024 frequency/cost settings versus every ordered subset of solid-color layers and independent per-pixel choice','C':'all nonconstant binary color partitions, messages, and m=2..9; exact three copies and modular decoding','D':'80 one/two-digit displays versus every repair subset up to budget and every displayable integer','F':'all connected labeled graphs through five vertices and every starting pair; complete product-state reachability checks of constructed orientations','G':'625 rectangle pairs with independently integrated overlap formula plus official triangle sample','I':'20000 chronological records checked against full prior unique-solve history','K':'1000 random legal jump sequences and exact endpoint invariant','L':'every legal four-state input through n=8, gate evaluation and <=6n node bound','M':'50 random seed/strength settings versus all 128 tournament outcome trees with exact rational probabilities, plus symmetric case'}
 checks={}
 for c in methods:
  n=globals()['check_'+c.lower()]();checks[c]={'passed':True,'cases':n,'method':methods[c]};print(c,n,flush=True)
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';report={'scope':'2025 ICPC Shenyang A B C D F G I K L M','status':'passed','seed':2641,'limitations':'Independent small-case checks; no online submissions or maximum-scale timing. G verifies the overlap identity analytically and rectangle/triangle geometry numerically; F validates universal avoidance with exhaustive product-state reachability.','checks':checks,'content_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'editorials/2025').glob('icpc-shenyang-*.md'))}}
 output=Path(args.output) if args.output else root/'regional_editorial_validation_shenyang_2025.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
