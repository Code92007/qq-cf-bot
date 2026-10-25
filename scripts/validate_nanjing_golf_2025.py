#!/usr/bin/env python3
"""Nanjing D: tree elimination versus full joint-state Bellman policy iteration (NumPy)."""
import numpy as np
import itertools,random,heapq

def tree_table(g,s):
 n=len(g);pa=[-1]*n;order=[0];pa[0]=0
 for u in order:
  for v in g[u]:
   if v!=pa[u]:pa[v]=u;order.append(v)
 active=[False]*n;active[0]=True;grades=[0.]*n;rows=[]
 def dp():
  alpha=[0.]*n;beta=[0.]*n;kap=[0.]*n
  for u in order[:0:-1]:
   if active[u]:
    sons=[v for v in g[u] if v!=pa[u]]
    den=len(g[u])-sum(alpha[v] for v in sons)
    alpha[u]=1/den
    beta[u]=(len(g[u])+sum(beta[v] for v in sons))/den
    kap[u]=(sum(not active[v] for v in sons)+sum(kap[v] for v in sons))/den
  a=[0.]*n;b=[0.]*n;q=[1.]*n;a[0]=1;q[0]=0
  for u in order[1:]:
   if active[u]:
    a[u]=alpha[u]*a[pa[u]]
    b[u]=alpha[u]*b[pa[u]]+beta[u]
    q[u]=alpha[u]*q[pa[u]]+kap[u]
  return a,b,q
 for _ in range(n-1):
  a,b,q=dp()
  value,u=min(((len(g[u])+b[pa[u]])/a[pa[u]],u) for u in range(1,n) if not active[u] and active[pa[u]])
  value=max(value,rows[-1][0] if rows else 0.0)
  active[u]=True;grades[u]=value
  a,b,q=dp()
  assert abs(q[s]-(1-a[s]))<1e-8
  rows.append((value,b[s],max(0.,min(1.,1-a[s]))))
 return rows,grades

def fast(gs,ss):
 tables=[tree_table(g,s)[0] for g,s in zip(gs,ss)]
 events=sorted((v,i,j,t,q) for i,tab in enumerate(tables) for j,(v,t,q) in enumerate(tab))
 ts=[0.]*len(gs);qs=[1.]*len(gs);ans=0.
 for v,i,j,t,q in events:
  prod=1.
  for z,x in enumerate(qs):
   if z!=i:prod*=x
  ans+=(t-ts[i])*prod
  ts[i]=t;qs[i]=q
 return ans

def brute(gs,ss):
 states=list(itertools.product(*(range(1,len(g)) for g in gs)));ids={s:i for i,s in enumerate(states)};N=len(states)
 transitions=[]
 for s in states:
  choices=[]
  for j,g in enumerate(gs):
   edges=[]
   for v in g[s[j]]:
    if v:
     ns=list(s);ns[j]=v;edges.append(ids[tuple(ns)])
   choices.append((1/len(g[s[j]]),edges))
  transitions.append(choices)
 pol=[0]*N
 for _ in range(100):
  A=np.eye(N)
  for i,actions in enumerate(transitions):
   prob,edges=actions[pol[i]]
   for v in edges:A[i,v]-=prob
  val=np.linalg.solve(A,np.ones(N))
  new=[]
  for i,actions in enumerate(transitions):
   costs=[1+prob*sum(val[v] for v in edges) for prob,edges in actions]
   best=min(range(len(costs)),key=costs.__getitem__)
   new.append(best if costs[best]<costs[pol[i]]-1e-10 else pol[i])
  if new==pol:return val[ids[tuple(ss)]]
  pol=new
 raise AssertionError('iteration')

def graph(par):
 g=[[] for _ in range(len(par)+1)]
 for v,u in enumerate(par,1):g[u].append(v);g[v].append(u)
 return g
if __name__=='__main__':
 rng=random.Random(20261025);cases=0
 for _ in range(500):
  k=rng.randint(1,3);ns=[rng.randint(2,6) for _ in range(k)]
  gs=[graph([rng.randrange(i) for i in range(1,n)]) for n in ns];ss=[rng.randrange(1,n) for n in ns]
  a,b=fast(gs,ss),brute(gs,ss)
  assert abs(a-b)<1e-8,(gs,ss,a,b)
  cases+=1
 small=[]
 for n in range(2,5):
  for par in itertools.product(*(range(i) for i in range(1,n))):
   for start in range(1,n):small.append((graph(par),start))
 for x,y in itertools.product(small,repeat=2):
  gs=[x[0],y[0]];ss=[x[1],y[1]]
  assert abs(fast(gs,ss)-brute(gs,ss))<1e-8
  cases+=1
 assert abs(fast([graph([0,1,2])]*2,[1,2])-14/3)<1e-10
 cases+=1
 for n in [100,200,300]:
  # Hitting time from the far end of a path is (n-1)^2.
  assert abs(fast([graph(list(range(n-1)))],[n-1])-(n-1)**2)<1e-5
  cases+=1
 print('PASS',cases)
 import argparse,hashlib,json
 from pathlib import Path
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 file=root/'editorials/2025/icpc-nanjing-D.md'
 report={'scope':'2025 ICPC 南京 D 最优策略与树上消元','status':'passed','seed':20261025,'limitations':'完整联合状态Bellman策略迭代仅覆盖小树；另核对100/200/300节点单链数值稳定性。未在线评测，未测试C++极限运行时间。','checks':{'D':{'passed':True,'cases':cases,'method':'500组1至3棵随机小树与所有n<=4递增父编号树/起点的有序两树组合，与联合状态Bellman策略迭代比较；另含样例和3组长链闭式期望。'}},'content_sha256':{file.name:hashlib.sha256(file.read_bytes()).hexdigest()}}
 if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
