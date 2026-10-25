#!/usr/bin/env python3
"""Exact integer certification of all 100+100+100 Nanjing L shapes."""
from itertools import combinations,product
from math import gcd
from time import monotonic
start=monotonic()
R=990
circles=list(product(range(-10,11),repeat=2))[:100]
triangles=[((-900+i,-1000),(1000,-900+i),(-600-i,900-i)) for i in range(1,101)]
lines=[((-800+i,-1000),(1000,-800+i)) for i in range(1,101)]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return a[0]-b[0],a[1]-b[1]
def orient(a,b,c):return cross(sub(b,a),sub(c,a))
def coef(a,b):return a[1]-b[1],b[0]-a[0],cross(a,b)
def intersect(l,m):
 a,b,c=l;d,e,f=m
 x,y,w=b*f-c*e,c*d-a*f,a*e-b*d
 if not w:return None
 if w<0:x,y,w=-x,-y,-w
 return x,y,w
prims=[]
for i,t in enumerate(triangles):
 for j in range(3):
  a,b=t[j],t[(j+1)%3];prims.append((a,b,False,i,coef(a,b)))
for i,(a,b) in enumerate(lines):prims.append((a,b,True,100+i,coef(a,b)))
def on(p,v):
 a,b,inf,_,_=v
 if inf:return True
 x,y,w=p
 return min(a[0],b[0])*w<=x<=max(a[0],b[0])*w and min(a[1],b[1])*w<=y<=max(a[1],b[1])*w
counts={}; points={};bad=[];checks=0
for i,u in enumerate(prims):
 for j in range(i):
  v=prims[j];p=intersect(u[4],v[4]);checks+=1
  if p and on(p,u) and on(p,v):
   x,y,w=p;g=gcd(gcd(abs(x),abs(y)),w);p=x//g,y//g,w//g
   if p in points:bad.append(('triple-linear',i,j,points[p]))
   points[p]=(i,j)
   if u[3]!=v[3]:
    key=tuple(sorted([u[3],v[3]]));counts[key]=counts.get(key,0)+1
for i,j in combinations(range(200),2):
 want=6 if j<100 else 2 if i<100 else 1
 assert counts.get((i,j),0)==want,(i,j,counts.get((i,j),0),want)
print('linear pairs',len(points),'bad',bad[:10],flush=True)
assert not bad
for p in points:
 x,y,w=p
 for cx,cy in circles:
  checks+=1
  assert (x-cx*w)**2+(y-cy*w)**2!=R*R*w*w,('1circle2line',p,cx,cy)
print('1circle2line done',monotonic()-start,flush=True)
for cx,cy in circles:
 for u in prims:
  a,b,inf,_,l=u;A,B,C=l
  assert (A*cx+B*cy+C)**2<R*R*(A*A+B*B),('no 2 roots',cx,cy,u)
  if not inf:
   assert sum((a[z]-(cx,cy)[z])**2 for z in [0,1])>R*R
   assert sum((b[z]-(cx,cy)[z])**2 for z in [0,1])>R*R
   t=(cx-a[0])*(b[0]-a[0])+(cy-a[1])*(b[1]-a[1]);d=sum((b[z]-a[z])**2 for z in [0,1])
   assert 0<t<d
  checks+=1
print('circle-line pairs done',monotonic()-start,flush=True)
def radical(c,d):
 return 2*(d[0]-c[0]),2*(d[1]-c[1]),c[0]**2+c[1]**2-d[0]**2-d[1]**2
for i,j in combinations(range(100),2):
 c,d=circles[i],circles[j];assert 0<sum((c[z]-d[z])**2 for z in [0,1])<4*R*R
 ra=radical(c,d)
 for u in prims:
  p=intersect(ra,u[4]);checks+=1
  if p and on(p,u):
   x,y,w=p
   assert (x-c[0]*w)**2+(y-c[1]*w)**2!=R*R*w*w,('2circle1line',i,j,u)
  elif not p:
   assert cross(ra[:2],u[4][:2])==0
   assert ra[0]*u[4][2]!=ra[2]*u[4][0] or ra[1]*u[4][2]!=ra[2]*u[4][1],('coincident radical',i,j,u)
print('2circle1line done',monotonic()-start,flush=True)
for i,j,k in combinations(range(100),3):
 c,d,e=circles[i],circles[j],circles[k];p=intersect(radical(c,d),radical(c,e));checks+=1
 if p:
  x,y,w=p
  assert (x-c[0]*w)**2+(y-c[1]*w)**2!=R*R*w*w,('3circle',i,j,k)
print('ALL PASS',checks,'seconds',monotonic()-start)

if __name__ == '__main__':
 import argparse,hashlib,json
 from pathlib import Path
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog'
 file=root/'editorials/2025/icpc-nanjing-L.md'
 report={'scope':'2025 ICPC 南京 L 固定整数构造完整校验','status':'passed','limitations':'对固定100+100+100个图形精确检查，所有合法输入取该集合前缀；未提交在线评测。cases是几何断言组合数量，不是独立OJ测试数量。','checks':{'L':{'passed':True,'cases':checks,'method':'整数叉积与齐次有理数坐标检查逐对最大交点数、全部四类三重共点、相切及端点退化；完整集合合法蕴含所有前缀合法。'}},'content_sha256':{file.name:hashlib.sha256(file.read_bytes()).hexdigest()}}
 if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
