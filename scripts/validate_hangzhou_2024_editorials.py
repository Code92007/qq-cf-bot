#!/usr/bin/env python3
"""Independent small-instance oracles for the published 2024 Hangzhou explanations."""
from itertools import product,permutations,combinations,combinations_with_replacement
from collections import deque,Counter
from math import comb,gcd
from pathlib import Path
import argparse,hashlib,json,random
R=random.Random(20241110);CHECKS={};MASK=(1<<63)-1

def record(c,n,m):
 CHECKS[c]={'passed':True,'cases':n,'method':m};print(c,n,flush=True)

def check_a():
 def fast(a,b,c):
  if len(a)!=len(b):return False
  if len(a)!=len(c):return True
  p=list(range(3))
  def find(x):
   while p[x]!=x:x=p[x]
   return x
  for x,y in zip(a,b):p[find(x)]=find(y)
  return any(find(x)!=find(y) for x,y in zip(a,c))
 def brute(a,b,c):
  return any(tuple(f[x] for x in a)==tuple(f[x] for x in b)!=tuple(f[x] for x in c) for f in product(range(2),repeat=3))
 cases=0
 for n in [1,2]:
  ss=list(product(range(3),repeat=n))
  for a,b,c in product(ss,repeat=3):assert fast(a,b,c)==brute(a,b,c);cases+=1
 for _ in range(200):
  a,b,c=[tuple(R.randrange(3) for _ in range(R.randint(1,6))) for _ in range(3)]
  assert fast(a,b,c)==brute(a,b,c);cases+=1
 record('A',cases,'穷举三字母短串与全部二色映射；另含不同长度随机串。')

def merge(x,y):return x[0]&y[0],(x[0]&y[1])|(x[1]&y[0])
class Tree:
 def __init__(self,a):
  self.n=len(a);self.g=[MASK]*(4*self.n);self.f=[0]*(4*self.n);self.tag=[MASK]*(4*self.n)
  def build(u,l,r):
   if l+1==r:self.g[u]=a[l];self.f[u]=MASK^a[l];return
   m=(l+r)//2;build(2*u,l,m);build(2*u+1,m,r);self.pull(u)
  build(1,0,self.n)
 def pull(self,u):self.g[u],self.f[u]=merge((self.g[2*u],self.f[2*u]),(self.g[2*u+1],self.f[2*u+1]))
 def apply(self,u,l,r,x):
  self.g[u]&=x;self.f[u]=(MASK^self.g[u]) if r-l==1 else self.f[u]&x;self.tag[u]&=x
 def push(self,u,l,r):
  if r-l>1:
   m=(l+r)//2;self.apply(2*u,l,m,self.tag[u]);self.apply(2*u+1,m,r,self.tag[u])
  self.tag[u]=MASK
 def update(self,ql,qr,x,assign=False,u=1,l=0,r=None):
  if r is None:r=self.n
  if r<=ql or qr<=l:return
  if ql<=l and r<=qr:
   if assign:self.g[u]=x;self.f[u]=MASK^x;self.tag[u]=MASK
   else:self.apply(u,l,r,x)
   return
  self.push(u,l,r);m=(l+r)//2
  self.update(ql,qr,x,assign,2*u,l,m);self.update(ql,qr,x,assign,2*u+1,m,r);self.pull(u)
 def query(self,ql,qr,u=1,l=0,r=None):
  if r is None:r=self.n
  if qr<=l or r<=ql:return MASK,0
  if ql<=l and r<=qr:return self.g[u],self.f[u]
  self.push(u,l,r);m=(l+r)//2
  return merge(self.query(ql,qr,2*u,l,m),self.query(ql,qr,2*u+1,m,r))
 def find(self,ql,qr,bit,u=1,l=0,r=None):
  if r is None:r=self.n
  if qr<=l or r<=ql or self.g[u]&bit:return None
  if r-l==1:return l
  self.push(u,l,r);m=(l+r)//2;p=self.find(ql,qr,bit,2*u,l,m)
  return p if p is not None else self.find(ql,qr,bit,2*u+1,m,r)
 def answer(self,l,r):
  g,f=self.query(l,r)
  if not f:return g
  p=self.find(l,r,1<<(f.bit_length()-1));return self.query(l,p)[0]&self.query(p+1,r)[0]

def band(a):
 x=MASK
 for y in a:x&=y
 return x

def check_b():
 cases=0
 for _ in range(120):
  n=R.randint(2,20);a=[R.getrandbits(63) for _ in range(n)];tree=Tree(a)
  for __ in range(150):
   op=R.randrange(3);l=R.randrange(n);r=R.randrange(l+1,n+1);x=R.getrandbits(63)
   if op==0:
    tree.update(l,r,x)
    for i in range(l,r):a[i]&=x
   elif op==1:tree.update(l,l+1,x,True);a[l]=x
   else:
    l=R.randrange(n-1);r=R.randrange(l+2,n+1)
    assert tree.answer(l,r)==max(band(a[l:i]+a[i+1:r]) for i in range(l,r));cases+=1
   g,f=tree.query(0,n)
   assert g==band(a)
   assert f==sum((1<<b) for b in range(63) if sum(not(x>>b&1) for x in a)==1)
 record('B',cases,'实际懒标记线段树混合AND、赋值、删除查询，与数组逐项模拟和枚举删除比较，覆盖全部63位。')

def elevator(a,f):
 n=len(a);order=sorted(range(n),key=lambda i:a[i][0]);p=0;cur=f;served=set();out=[];top=max(r for l,r in a)
 while cur<top:
  best=None
  while p<n and a[order[p]][0]<=cur:
   i=order[p];p+=1
   if a[i][1]>cur and (best is None or a[i][1]>a[best][1]):best=i
  if best is None:best=order[p];p+=1
  served.add(best);out.append(best);cur=a[best][1]
 out+=sorted((i for i in range(n) if i not in served),key=lambda i:-a[i][1])
 return out

def ecost(a,f,order):
 cost=0
 for i in order:l,r=a[i];cost+=max(0,l-f)+r-l;f=r
 return cost

def check_e():
 for _ in range(250):
  n=R.randint(1,7);a=[];f=R.randint(1,12)
  for i in range(n):l=R.randint(1,10);a.append((l,R.randint(l+1,12)))
  out=elevator(a,f);assert sorted(out)==list(range(n))
  assert ecost(a,f,out)==min(ecost(a,f,p) for p in permutations(range(n)))
 record('E',250,'对随机小区间枚举所有乘客顺序，比较构造顺序的真实电量。')

def cuts(rows):
 n=len(rows[0]);rank={x:i+1 for i,x in enumerate(rows[0])};mx=[0]*n
 for row in rows:
  for i,x in enumerate(row):mx[i]=max(mx[i],rank[x])
 blocks=[];last=0;m=0
 for i in range(n):
  m=max(m,mx[i])
  if m==i+1:blocks.append((last,i));last=i+1
 return blocks

def check_f():
 cases=0
 for n in range(1,5):
  ps=list(permutations(range(n)))
  for x,y in product(ps,repeat=2):
   rows=[x,y];reach=[1<<i for i in range(n)]
   for row in rows:
    for i in range(n):
     for j in range(i+1,n):reach[row[i]]|=1<<row[j]
   for k in range(n):
    for i in range(n):
     if reach[i]>>k&1:reach[i]|=reach[k]
   blocks=cuts(rows)
   for row in rows:
    for l in range(n):
     for r in range(l,n):
      a=sum(comb(max(0,min(r,b)-max(l,a)+1),2) for a,b in blocks)
      b=sum(bool(reach[u]>>v&1 and reach[v]>>u&1) for u,v in combinations(row[l:r+1],2))
      assert a==b;cases+=1
 record('F',cases,'穷举n<=4的两份排列，完整有向图传递闭包与所有榜单子区间的SCC分块计数比较。')

def partitions(n,lo=1):
 if n==0:yield ();return
 for x in range(lo,n+1):
  for p in partitions(n-x,x):yield (x,)+p

def h_construct(lens):
 n=sum(lens);chains=[];nextid=0
 for z in lens:chains.append(list(range(nextid,nextid+z)));nextid+=z
 k=len(lens);L=max(lens);s=min(lens)
 if k>1 and (s==L or s==L-1 and lens.count(L)>1):return None
 main=lens.index(L);short=lens.index(s);root=chains[main][0];pa=[-1]*n
 for chain in chains:
  for x,y in zip(chain,chain[1:]):pa[y]=x
 for i,chain in enumerate(chains):
  if i!=main:pa[chain[0]]=chains[main][1] if lens.count(L)>1 and i==short else root
 return pa,chains

def h_valid(pa,chains):
 n=len(pa);root=pa.index(-1);children=[[] for _ in pa];order=[root]
 for i,p in enumerate(pa):
  if p>=0:children[p].append(i)
 for u in order:order+=children[u]
 assert len(order)==n and len(set(order))==n
 size=[1]*n
 for u in reversed(order):
  if pa[u]>=0:size[pa[u]]+=size[u]
 heavy={u:v for c in chains for u,v in zip(c,c[1:])}
 for u in range(n):
  if children[u]:assert u in heavy and size[heavy[u]]==max(size[v] for v in children[u])

def h_feasible(n):
 if n==1:return {(1,)}
 result=set()
 for seq in product(range(n),repeat=n-2):
  deg=[1]*n
  for x in seq:deg[x]+=1
  edges=[]
  for x in seq:
   leaf=next(i for i in range(n) if deg[i]==1);edges.append((x,leaf));deg[x]-=1;deg[leaf]-=1
  leaves=[i for i in range(n) if deg[i]==1];edges.append(tuple(leaves));g=[[] for _ in range(n)]
  for u,v in edges:g[u].append(v);g[v].append(u)
  for root in range(n):
   pa=[-1]*n;order=[root]
   for u in order:
    for v in g[u]:
     if v!=pa[u]:pa[v]=u;order.append(v)
   size=[1]*n;options=[None]*n
   for u in reversed(order):
    children=[v for v in g[u] if v!=pa[u]]
    if not children:options[u]={(1,())};continue
    for v in children:size[u]+=size[v]
    opts=set();mx=max(size[v] for v in children)
    for picks in product(*(options[v] for v in children)):
     for h,v in enumerate(children):
      if size[v]!=mx:continue
      rest=[]
      for j,(length,others) in enumerate(picks):rest+=list(others)+([] if j==h else [length])
      opts.add((picks[h][0]+1,tuple(sorted(rest))))
    options[u]=opts
   result.update(tuple(sorted((h,)+rest)) for h,rest in options[root])
 return result

def check_h():
 cases=0
 for n in range(1,15):
  feasible=h_feasible(n) if n<=5 else None
  for lens in partitions(n):
   out=h_construct(lens)
   if feasible is not None:assert (out is not None)==(lens in feasible),(lens,feasible)
   if out:h_valid(*out)
   cases+=1
 record('H',cases,'所有总长度<=14的链长分拆检查构造的真实重儿子条件；总长度<=5另穷举所有标号树、根与重儿子选择核验无解判定。')

def card_count(n1,n2,m,edges):
 used=sorted(set(x for e in edges for x in e));M=len(used);U=m-M;ids={x:i for i,x in enumerate(used)};adj=[0]*M
 for a,b in edges:adj[ids[a]]|=1<<ids[b];adj[ids[b]]|=1<<ids[a]
 good=[True]*(1<<M);f=[0]*(1<<M)
 def c(n,r):return comb(n,r) if 0<=r<=n else 0
 for mask in range(1,1<<M):
  bit=mask&-mask;v=bit.bit_length()-1;good[mask]=good[mask^bit] and not(adj[v]&mask)
 for mask in range(1<<M):
  if good[mask]:f[mask]=c(n1+U-1,m-mask.bit_count()-1)
 for bit in range(M):
  for mask in range(1<<M):
   if mask>>bit&1:f[mask]+=f[mask^(1<<bit)]
 return sum(c(n2+U-1,m-mask.bit_count()-1)*f[((1<<M)-1)^mask] for mask in range(1<<M) if good[mask])

def check_j():
 for _ in range(300):
  m=R.randint(1,5);n1=R.randint(1,4);n2=R.randint(1,4);edges=[(R.randrange(m),R.randrange(m)) for i in range(R.randint(1,10))]
  brute=sum(all(a in red and b in blue or b in red and a in blue for a,b in edges) for red in combinations_with_replacement(range(m),n1) for blue in combinations_with_replacement(range(m),n2))
  assert card_count(n1,n2,m,edges)==brute,(n1,n2,m,edges,brute)
 record('J',300,'枚举两色全部小多重集，逐条判断异色约束，与独立集+SOS插板计数比较（含自环和重复边）。')

def bingo(p,m):
 ct=Counter()
 for i,x in enumerate(p,1):
  ct[x//m]+=1
  if ct[x//m]==m:return i

def check_k():
 cases=0
 for n,m in [(1,4),(2,2),(2,3),(3,2)]:
  for _ in range(35):
   p=list(range(n*m));R.shuffle(p);p=tuple(p);k=R.randrange(4)
   seen={p};front={p};best=bingo(p,m)
   for z in range(k):
    nxt=set()
    for x in front:
     for i,j in combinations(range(n*m),2):
      y=list(x);y[i],y[j]=y[j],y[i];y=tuple(y)
      if y not in seen:nxt.add(y);seen.add(y);best=min(best,bingo(y,m))
    front=nxt
   positions=[[] for _ in range(n)]
   for t,x in enumerate(p,1):positions[x//m].append(t)
   fast=m if k>=m else min(max(m,x[m-k-1]) for x in positions)
   assert fast==best;cases+=1
 record('K',cases,'对小排列BFS枚举至k次任意交换，逐个计算真实首次整行完成时刻。')

def divisible(b,k):
 d=0
 for x,y in zip(b,b[1:]):d=gcd(d,abs(x-y))
 if d==0:return list(range(1,k+1))
 candidates=[];mn=min(b)
 for x in range(1,int(d**.5)+1):
  if d%x==0:
   for z in {x,d//x}:
    if 1<=z-mn<=k:candidates.append(z-mn)
 pa=[-1]*len(b);st=[]
 for i,x in enumerate(b):
  last=-1
  while st and b[st[-1]]>x:last=st.pop()
  if st:pa[i]=st[-1]
  if last>=0:pa[last]=i
  st.append(i)
 return sorted(x for x in candidates if all(p<0 or (b[i]+x)%(b[p]+x)==0 for i,p in enumerate(pa)))

def check_m():
 cases=0
 for n in range(1,6):
  for b in product(range(1,5),repeat=n):
   want=[]
   for x in range(1,9):
    a=[y+x for y in b]
    if all(all(y%min(a[l:r])==0 for y in a[l:r]) for l in range(n) for r in range(l+1,n+1)):want.append(x)
   assert divisible(b,8)==want;cases+=1
 record('M',cases,'穷举长度<=5、值1..4的全部数组和x=1..8，直接检查所有子数组的最小值整除条件。')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
 for check in [check_a,check_b,check_e,check_f,check_h,check_j,check_k,check_m]:check()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog/editorials/2024'
 report={'scope':'2024 ICPC 杭州 A/B/E/F/H/J/K/M','status':'passed','seed':20241110,'limitations':'小规模穷举、随机操作与独立暴力对照。尚未在线评测，未验证最大输入运行时间及内存。','checks':CHECKS,'content_sha256':{f'icpc-hangzhou-{x}.md':hashlib.sha256((root/f'icpc-hangzhou-{x}.md').read_bytes()).hexdigest() for x in CHECKS}}
 if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
