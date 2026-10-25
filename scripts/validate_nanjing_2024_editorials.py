#!/usr/bin/env python3
"""Independent checks for 2024 Nanjing A/B/E/G/I/J/K/M."""
from itertools import product,permutations,combinations
from collections import deque,Counter
from math import comb,factorial,atan2,asin,hypot,pi,sin,cos,floor
from functools import lru_cache
from pathlib import Path
import argparse,hashlib,json,random
R=random.Random(20241103);CHECKS={}
def record(c,n,m):CHECKS[c]={'passed':True,'cases':n,'method':m};print(c,n,flush=True)

def moves(h,w,mask):
 points=[i for i in range(h*w) if mask>>i&1];result={}
 for c,(dx,dy) in zip('UDLR',[(-1,0),(1,0),(0,-1),(0,1)]):
  a={}
  for i in points:
   x,y=divmod(i,w);xx,yy=x+dx,y+dy;j=xx*w+yy
   a[i]=j if 0<=xx<h and 0<=yy<w and mask>>j&1 else i
  result[c]=a
 return points,result

def kangaroo_fast(h,w,mask,seq):
 points,step=moves(h,w,mask);N=len(points);go={};deg=Counter()
 for u in points:
  v=u
  for c in seq:v=step[c][v]
  go[u]=v;deg[v]+=1
 height={u:0 for u in points};q=deque(u for u in points if not deg[u]);removed=set()
 while q:
  u=q.popleft();removed.add(u);v=go[u];height[v]=max(height[v],height[u]+1);deg[v]-=1
  if deg[v]==0:q.append(v)
 for u in points:
  if u not in removed:height[u]=N
 cur=dict(height);active=[0]*len(seq);expires=[[] for _ in range(N+1)];last=-1
 for phase,c in enumerate(seq):
  nxt={}
  for u,x in cur.items():
   v=step[c][u]
   if v in nxt:
    e=min(nxt[v],x);assert e<N;active[phase]+=1;expires[e+1].append(phase);last=max(last,e);nxt[v]=max(x,nxt[v])
   else:nxt[v]=x
  cur=nxt
 ans=[-1]*(h*w+1)
 for x in range(N,h*w+1):ans[x]=0
 cnt=N
 for q in range(last+1):
  for phase in expires[q]:active[phase]-=1
  for phase,loss in enumerate(active):
   old=cnt;cnt-=loss
   for x in range(cnt,old):ans[x]=q*len(seq)+phase+1
 assert cnt==N-len(removed)
 return ans[1:]

def kangaroo_brute(h,w,mask,seq):
 points,step=moves(h,w,mask);state=frozenset(points);seen=set();t=0;ans=[-1]*(h*w+1)
 while (state,t%len(seq)) not in seen:
  seen.add((state,t%len(seq)))
  for x in range(len(state),h*w+1):
   if ans[x]<0:ans[x]=t
  state=frozenset(step[seq[t%len(seq)]][x] for x in state);t+=1
 return ans[1:]

def check_a():
 cases=0
 seqs=[''.join(p) for k in range(1,4) for p in product('UDLR',repeat=k)]
 for mask in range(1,1<<6):
  for seq in seqs:assert kangaroo_fast(2,3,mask,seq)==kangaroo_brute(2,3,mask,seq);cases+=1
 for _ in range(300):
  h,w=R.randint(1,5),R.randint(1,5);mask=R.randrange(1,1<<(h*w));seq=''.join(R.choice('UDLR') for _ in range(R.randint(1,8)))
  assert kangaroo_fast(h,w,mask,seq)==kangaroo_brute(h,w,mask,seq);cases+=1
 record('A',cases,'穷举2x3所有非空地图及长度<=3的全部操作串；另含随机5x5地图，与同步状态+相位的完整循环检测比较全部阈值。')

def reduce_equal(s):
 stack=[]
 for x in s:
  if stack and stack[-1]==x:stack.pop()
  else:stack.append(x)
 return len(stack)

def check_b():
 cases=0
 for n in range(1,9):
  for s in product(range(3),repeat=n):
   counts=Counter(x^(i%2) for i,x in enumerate(s) if x<2);q=s.count(2);d=abs(counts[0]-counts[1]);fast=d-q if d>q else n%2
   best=n
   for fills in product(range(2),repeat=q):
    it=iter(fills);a=[x if x<2 else next(it) for x in s];best=min(best,reduce_equal(a))
   assert fast==best;cases+=1
 record('B',cases,'穷举长度<=8全部012串及每个2的所有赋值，按原题相同相邻消去规则用栈计算。')

def occurrences(s):return sum(s[i:i+7]=='nanjing' for i in range(max(0,len(s)-6)))
def check_e():
 for _ in range(700):
  s=''.join(R.choice(['nanjing','nan','jing','g','a','n']) for i in range(R.randint(1,30)));k=R.choice([0,1,2,6,7,8,10**9,R.randint(1,100)])
  fast=max(occurrences(s[d%len(s):]+s[:d%len(s)]) for d in range(min(k,7)+1))
  brute=max(occurrences(s[d:]+s[:d]) for d in range(min(k,len(s)-1)+1))
  assert fast==brute
 record('E',700,'在包含大量完整及破碎目标串的随机字符串上，与所有允许的不同旋转逐一计数比较。')

def check_g():
 cases=0
 for _ in range(140):
  n=R.randint(2,90);g=[[] for _ in range(n)];slots=[0];children=[0]*n
  for v in range(1,n):
   u=R.choice(slots);g[u].append(v);g[v].append(u);children[u]+=1
   if children[u]==2:slots.remove(u)
   slots.append(v)
  for secret in range(n):
   dist=[-1]*n;dist[secret]=0;q=deque([secret])
   while q:
    u=q.popleft()
    for v in g[u]:
     if dist[v]<0:dist[v]=dist[u]+1;q.append(v)
   alive=set(range(n));queries=0
   while len(alive)>1:
    best=None
    for c in alive:
     branches=[]
     for v in g[c]:
      if v not in alive:continue
      part={v};stack=[v]
      for u in stack:
       for z in g[u]:
        if z in alive and z!=c and z not in part:part.add(z);stack.append(z)
      branches.append((v,part))
     if max(map(lambda x:len(x[1]),branches),default=0)<=len(alive)//2:best=c,branches;break
    c,branches=best
    if len(branches)==1:u,v=c,branches[0][0]
    else:
     branches.sort(key=lambda x:-len(x[1]));u,v=branches[0][0],branches[1][0]
    # Independent exact-distance filter, not branch-selected by the hidden node.
    def distances(start):
     d=[-1]*n;d[start]=0;queue=deque([start])
     while queue:
      x=queue.popleft()
      for y in g[x]:
       if d[y]<0:d[y]=d[x]+1;queue.append(y)
     return d
    du,dv=distances(u),distances(v);cmp=(dist[u]>dist[v])-(dist[u]<dist[v]);old=len(alive)
    alive={x for x in alive if (du[x]>dv[x])-(du[x]<dv[x])==cmp}
    assert secret in alive and len(alive)<=old//2;queries+=1
   assert alive=={secret} and queries<=n.bit_length()-1;cases+=1
 record('G',cases,'随机二叉树全部隐藏点的真实距离比较模拟；逐轮检查候选规模至少减半和严格询问预算。')

def bingo_sum(n,m,a):
 N=n*m;a=sorted(a);f=[factorial(i) for i in range(N+1)];H=[0]*(N+1)
 # Rational-free direct coefficient expansion of the described reverse convolution.
 for c in range(1,N+1):
  coeff=sum(a[s]*f[s]//f[s-c+1] for s in range(c-1,N))
  H[c]=c*f[N-c]*coeff
  assert H[c]==sum(a[i]*comb(i,c-1)*f[c]*f[N-c] for i in range(c-1,N))
 return sum((-1)**(x+y-1)*comb(n,x)*comb(m,y)*H[m*x+n*y-x*y] for x in range(n+1) for y in range(m+1) if x+y)

def check_i():
 cases=0
 for n,m in [(1,1),(1,3),(3,1),(2,2),(2,3),(3,2)]:
  for _ in range(30):
   a=[R.randrange(7) for i in range(n*m)];brute=0
   for p in permutations(a):brute+=min([max(p[i*m:(i+1)*m]) for i in range(n)]+[max(p[j::m]) for j in range(m)])
   assert bingo_sum(n,m,a)==brute;cases+=1
 record('I',cases,'枚举小网格全部带下标排列的真实bingo值；独立展开反转卷积系数，与最大值组合数公式逐c核对。未测试NTT实现。')

def social(k,friends,edges):
 base=0;gain=[0]*k;pair=Counter()
 for a,b in edges:
  if a in friends and b in friends:base+=1
  elif a in friends:gain[b]+=1
  elif b in friends:gain[a]+=1
  elif a==b:gain[a]+=1
  else:pair[tuple(sorted((a,b)))]+=1
 top=sorted((gain[i] for i in range(k) if i not in friends),reverse=True);best=sum(top[:2])
 return base+max([best]+[gain[a]+gain[b]+v for (a,b),v in pair.items()])

def check_j():
 for _ in range(1200):
  k=R.randint(1,9);friends=set(R.sample(range(k),R.randint(1,k)));edges=[(R.randrange(k),R.randrange(k)) for i in range(R.randint(1,50))];candidates=set(range(k))-friends;brute=0
  for sz in range(3):
   for extra in combinations(candidates,sz):
    f=friends|set(extra);brute=max(brute,sum(a in f and b in f for a,b in edges))
  assert social(k,friends,edges)==brute
 record('J',1200,'枚举至多两个新增好友集合，逐条判断所有评论；包括重复评论、反向评论、自评论及无非好友。')

def strips(w,k,red,black):
 starts=[];bounds=[-1]+sorted(black)+[w]
 for left,right in zip(bounds,bounds[1:]):
  rr=sorted(x for x in red if left<x<right);local=[];end=-1
  for x in rr:
   if x>end:local.append(x);end=x+k-1
  if local:
   local[-1]=min(local[-1],right-k)
   for i in range(len(local)-2,-1,-1):local[i]=min(local[i],local[i+1]-k)
   if local[0]<=left:return None
   starts+=local
 return starts

def check_k():
 cases=0
 for w in range(1,8):
  for colors in product(range(3),repeat=w):
   red={i for i,x in enumerate(colors) if x==1};black={i for i,x in enumerate(colors) if x==2}
   if not red:continue
   for k in range(1,w+1):
    @lru_cache(None)
    def brute(p):
     if p==w:return 0
     ans=100 if p in red else brute(p+1)
     if p+k<=w and not any(x in black for x in range(p,p+k)):ans=min(ans,1+brute(p+k))
     return ans
    best=brute(0);out=strips(w,k,red,black)
    assert (out is None)==(best>=100)
    if out is not None:
     cover=[]
     for x in out:cover+=list(range(x,x+k))
     assert len(out)==best and len(set(cover))==len(cover) and red<=set(cover) and not black&set(cover) and all(0<=x<w for x in cover)
    cases+=1
 record('K',cases,'穷举长度<=7的红黑白分布和全部纸条长度；与逐格枚举不相交放置的DP比较，核验最少张数及实际覆盖。')

def sub(a,b):return a[0]-b[0],a[1]-b[1]
def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def hull(points):
 pts=sorted(set(points));lo=[];hi=[]
 for p in pts:
  while len(lo)>=2 and cross(sub(lo[-1],lo[-2]),sub(p,lo[-1]))<=0:lo.pop()
  lo.append(p)
 for p in reversed(pts):
  while len(hi)>=2 and cross(sub(hi[-1],hi[-2]),sub(p,hi[-1]))<=0:hi.pop()
  hi.append(p)
 return lo[:-1]+hi[:-1]
def segment_distance(a,b):
 v=sub(b,a);z=max(0,min(1,-dot(a,v)/dot(v,v)));return hypot(a[0]+z*v[0],a[1]+z*v[1])
def ray_segment_distance(v,a,b):
 z=sub(b,a);den=cross(v,z)
 if abs(den)>1e-12:
  t=cross(a,z)/den;s=cross(a,v)/den
  if t>=0 and 0<=s<=1:return 0.
 def point_ray(p):return abs(cross(v,p)) if dot(v,p)>=0 else hypot(*p)
 return min(point_ray(a),point_ray(b),segment_distance(a,b))
def angular(poly,d):
 ref=poly[0];vals=[]
 for p in poly:
  theta=atan2(cross(ref,p),dot(ref,p));beta=asin(d/hypot(*p));vals.append((theta-beta,theta+beta))
 return atan2(ref[1],ref[0])+min(a for a,b in vals),max(b for a,b in vals)-min(a for a,b in vals)
def damage(poly,d,start,t):
 left,width=angular(poly,d);left=(left-start)%(2*pi);right=left+width;q=floor(t/(2*pi));rem=t-q*2*pi
 return q*width+max(0,min(rem,right,2*pi)-left)+(min(rem,right-2*pi) if right>2*pi else 0)
def check_m():
 cases=0
 for _ in range(200):
  angle=R.random()*2*pi;cx=round(30*cos(angle));cy=round(30*sin(angle));poly=hull([(cx+R.randint(-8,8),cy+R.randint(-8,8)) for z in range(12)]);d=R.randint(1,8)
  assert min(segment_distance(poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly)))>d
  left,width=angular(poly,d);assert 0<width<pi
  for j in range(257):
   theta=(j+.25)*2*pi/257;v=cos(theta),sin(theta);distance=min(ray_segment_distance(v,poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly)))
   offset=(theta-left)%(2*pi)
   if abs(distance-d)>1e-8:assert (offset<=width)==(distance<=d),(poly,d,theta,left,width,distance)
   else:assert min(abs(offset),abs(offset-width),abs(offset-2*pi))<1e-8
   cases+=1
  start=R.random()*2*pi;t=R.random()*20
  assert abs(damage(poly,d,start,t+2*pi)-damage(poly,d,start,t)-width)<1e-10
  cases+=1
 poly=[(1,2),(2,1),(2,2)]
 for t,want in [(1,1),(2,pi/2),(10000,2500.707752257475)]:assert abs(damage(poly,1,0,t)-want)<1e-8;cases+=1
 record('M',cases,'随机凸包的257个方向以射线到每条线段的距离独立判定；另测周期恒等式和全部官方样例数值。')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path);args=p.parse_args()
 for check in [check_a,check_b,check_e,check_g,check_i,check_j,check_k,check_m]:check()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog/editorials/2024'
 report={'scope':'2024 ICPC 南京 A/B/E/G/I/J/K/M','status':'passed','seed':20241103,'limitations':'小规模穷举、交互模拟、几何独立判定和数值样例。未在线评测，未进行极限性能测试；I仅验证卷积系数和公式，未测试NTT实现。','checks':CHECKS,'content_sha256':{f'icpc-nanjing-{c}.md':hashlib.sha256((root/f'icpc-nanjing-{c}.md').read_bytes()).hexdigest() for c in CHECKS}}
 if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
