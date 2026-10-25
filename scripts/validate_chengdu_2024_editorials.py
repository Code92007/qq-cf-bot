#!/usr/bin/env python3
from pathlib import Path
from itertools import product
from collections import deque,Counter
from math import gcd
import random,json,hashlib,argparse
R=random.Random(20241027);checks={}
def rec(x,n,m):checks[x]={'cases':n,'method':m,'passed':True};print(x,n,flush=True)
def arrows(s):
 n=len(s)
 if s[0]!='>' or s[-3:]!='>>>' or '-' not in s:return None
 k=s.rindex('-');ops=[(r-4,r) for r in range(n-1,k+2,-1)]+[(i,k+3) for i in range(k) if s[i]=='>'];out=['*']*n
 for l,r in ops:assert 0<=l<r<n and r-l+1>=5;out[l:r+1]='>'+'-'*(r-l-3)+'>>>'
 assert ''.join(out)==s and len(ops)<=n
 return ops
def check_a():
 cases=0
 for n in range(5,9):
  start='*'*n;seen={start};q=deque([start]);ops=[(l,r) for l in range(n) for r in range(l+4,n)]
  while q:
   s=q.popleft()
   for l,r in ops:
    t=s[:l]+'>'+'-'*(r-l-3)+'>>>'+s[r+1:]
    if t not in seen:seen.add(t);q.append(t)
  for bits in product('>-',repeat=n):s=''.join(bits);assert (arrows(s) is not None)==(s in seen);cases+=1
 for n in range(9,13):
  for bits in product('>-',repeat=n):arrows(''.join(bits));cases+=1
 rec('A',cases,'full painting-state reachability through n8 and actual construction replay for every binary target through n12')
def clothing(s):
 K=s.count('?');dp={(0,0,''):1}
 for c in s:
  nd=Counter()
  for (a,b,last),v in dp.items():
   for x in ('abc' if c=='?' else c):
    if x!=last:nd[a+(c=='?' and x=='a'),b+(c=='?' and x=='b'),x]+=v
  dp=nd
 F=[[[0]*(K+1) for y in range(K+1)] for x in range(K+1)]
 for (a,b,last),v in dp.items():F[a][b][K-a-b]+=v
 for axis in range(3):
  for x,y,z in product(range(K+1),repeat=3):
   pos=[x,y,z]
   if pos[axis]:pos[axis]-=1;F[x][y][z]+=F[pos[0]][pos[1]][pos[2]]
 return F
def check_b():
 cases=0
 for _ in range(200):
  s=''.join(R.choice('abc?') for i in range(R.randrange(1,9)));K=s.count('?');F=clothing(s);counts=[]
  for fill in product('abc',repeat=K):
   it=iter(fill);t=''.join(next(it) if c=='?' else c for c in s)
   if all(x!=y for x,y in zip(t,t[1:])):counts.append(tuple(fill.count(x) for x in 'abc'))
  for x,y,z in product(range(K+1),repeat=3):assert F[x][y][z]==sum(a<=x and b<=y and c<=z for a,b,c in counts);cases+=1
 rec('B',cases,'rolling count/last DP and actual three-axis prefix sums versus every question-mark filling and every capacity triple on random strings')
def check_g():
 cases=0
 for x,y in product(range(32),repeat=2):
  seq=[x,y]
  def ins(i,kind):
   a,b=seq[i:i+2];seq.insert(i+1,{'and':a&b,'or':a|b,'xor':a^b}[kind])
  for _ in range(5):ins(0,'xor');ins(0,'xor');ins(2,'xor')
  for start,kind in zip(range(15,-1,-3),('and','or','xor','left','right','zero')):
   assert seq[start:start+2]==[x,y]
   if kind in ('and','or','xor'):ins(start,kind)
   elif kind=='left':ins(start,'xor');ins(start,'and')
   elif kind=='right':ins(start,'xor');ins(start+1,'and')
   else:ins(start,'and');ins(start,'or');ins(start,'xor')
  expected={0,x,y,x&y,x|y,x^y,x&(x^y),y&(x^y)};assert set(seq)==expected
  closure={x,y}
  while True:
   updated=closure|{z for a,b in product(closure,repeat=2) for z in (a&b,a|b,a^b)}
   if updated==closure:break
   closure=updated
  assert closure==expected;cases+=1
 rec('G',cases,'replay all adjacent insertions producing the eight candidates and compare with unrestricted algebra closure for endpoints0..31')
def check_i():
 cases=0
 for _ in range(200):
  n=R.randrange(1,40);a=[R.randrange(20) for i in range(n)];size=1
  while size<n:size*=2
  tree=[0]*(2*size)
  def update(i):
   if not 0<=i<n-1:return
   p=size+i;tree[p]=i+1 if a[i]>a[i+1] else 0;p//=2
   while p:tree[p]=gcd(tree[2*p],tree[2*p+1]);p//=2
  for i in range(n-1):update(i)
  for step in range(30):
   g=tree[1];got=n if g==0 else sum(g%d==0 for d in range(1,g+1));want=sum(all(i%k==0 or a[i-1]<=a[i] for i in range(1,n)) for k in range(1,n+1));assert got==want;cases+=1
   p=R.randrange(n);a[p]=R.randrange(20);update(p-1);update(p)
 rec('I',cases,'actual gcd segment-tree point updates versus explicitly checking every block size after each random modification')
def check_j():
 for _ in range(1000):
  n=R.randrange(1,10);m=R.randrange(2,12);logs=[];levels=list(range(1,n+1));R.shuffle(levels)
  for level in [None]+levels:
   if level is not None:logs.append((1,level))
   for z in range(R.randrange(15)):logs.append((R.choice((2,3)),R.randrange(m),R.randrange(1,n+1)))
  score=[0]*m;seen=[-1]*m;epoch=0;active=None;done=0
  for op in logs:
   if op[0]==1:active=op[1];done=0;epoch+=1
   elif op[2]==active and seen[op[1]]!=epoch:
    seen[op[1]]=epoch
    if op[0]==2:score[op[1]]+=m-done;done+=1
  want=[0]*m
  for pos,op in enumerate(logs):
   if op[0]!=1:continue
   end=next((j for j in range(pos+1,len(logs)) if logs[j][0]==1),len(logs));first={}
   for event in logs[pos+1:end]:
    if event[2]==op[1] and event[1] not in first:first[event[1]]=event[0]
   finish=[p for p,t in first.items() if t==2]
   for rank,p in enumerate(finish):want[p]+=m-rank
  assert score==want
 rec('J',1000,'timestamp stream processing versus independent per-level log extraction, first valid event selection, and finish ranking')
def check_l():
 for _ in range(1000):
  a,b,c=sorted(R.sample(range(1,10**9),3));seq=[a]*50+[b]*45+[c]*4+[c+1];assert len(seq)==100 and all(1<=x<=10**9 for x in seq) and [sum(x<=v for x in seq) for v in (a,b,c)]==[50,95,99]
 rec('L',1000,'generated datasets independently counted at all three threshold values and checked against output bounds')
def main():
 for f in (check_a,check_b,check_g,check_i,check_j,check_l):f()
 root=Path(__file__).resolve().parents[1]/'src/qq_cf_bot/catalog';out={'scope':'2024 ICPC Chengdu A B G I J L','seed':20241027,'status':'passed','limitations':'Small-case checks only; no online submissions or maximum-size runtime tests.','checks':checks,'content_sha256':{f'icpc-chengdu-{x}.md':hashlib.sha256((root/'editorials/2024'/f'icpc-chengdu-{x}.md').read_bytes()).hexdigest() for x in checks}}
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'regional_editorial_validation_chengdu_2024.json');args=p.parse_args();args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
