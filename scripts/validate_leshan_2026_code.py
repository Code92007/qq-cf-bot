"""Compile the 13 published C++17 listings and compare with independent references.

Run from any directory: python3 scripts/validate_leshan_2026_code.py
Requires a C++17 compiler; uses only Python's standard library. No OJ access.
"""
import importlib.util
import math
import re
import shutil
import tempfile
from pathlib import Path
import subprocess

REPOSITORY = Path(__file__).resolve().parents[1]
temporary = tempfile.TemporaryDirectory(prefix="leshan-code-")
BUILD = Path(temporary.name)
(BUILD / "solutions").mkdir()
compiler = shutil.which("clang++") or shutil.which("g++")
if not compiler:
    raise SystemExit("A C++17 compiler is required")
for letter in "ABCDEFGHIJKLM":
    body = (REPOSITORY / "src/qq_cf_bot/catalog/editorials/2026" / f"ccpc-leshan-{letter}.md").read_text()
    code = re.search(r"```cpp\n([\s\S]+?)\n```", body)[1]
    source = BUILD / "solutions" / f"{letter}.cpp"
    source.write_text(code)
    subprocess.run([compiler, "-std=c++17", "-O2", str(source), "-o", str(source.with_suffix(""))], check=True)
spec = importlib.util.spec_from_file_location("references", Path(__file__).with_name("validate_leshan_2026_editorials.py"))
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

import heapq
import itertools
import json
import random
import subprocess
import time

ROOT = BUILD
RNG = random.Random(468501)
CHECKS = {}

def run(letter, data, timeout=30):
    p = subprocess.run([str(ROOT / 'solutions' / letter)], input=data, text=True, capture_output=True, timeout=timeout)
    assert p.returncode == 0, (letter, data[:3000], p.stderr)
    return p.stdout

def done(letter, count, detail):
    CHECKS[letter] = dict(passed=True, cases=count, detail=detail)
    print(letter, count, detail, flush=True)

def deer_brute(L,K,deer):
    n = len(deer)
    z = [2*a for a,d in deer]
    direction = [1 if d == 'E' else -1 for a,d in deer]
    active = [not (a == L if d == 'E' else a == 0) for a,d in deer]
    answer = [None if v else 0 for v in active]
    now = 0
    for iteration in range(10000):
        if not any(active): return answer
        velocity = direction[:]
        for i in range(n):
            if not active[i]: velocity[i] = 0; continue
            for j in range(i+1,n):
                if not active[j] or direction[i] == direction[j]: continue
                gap = (z[j]-z[i])*direction[i]
                if 0 < gap <= 2*K: velocity[i] = 0
        dt = min((2*L-z[i] if velocity[i] == 1 else z[i]) for i in range(n) if active[i] and velocity[i])
        for i in range(n):
            for j in range(i+1,n):
                if not active[i] or not active[j] or direction[i] == direction[j]: continue
                gap = (z[j]-z[i])*direction[i]
                closing = (velocity[i]-velocity[j])*direction[i]
                if gap > 0 and closing:
                    distance = gap-2*K if gap > 2*K else gap
                    assert distance % closing == 0
                    dt = min(dt, distance//closing)
        assert dt > 0
        now += dt
        z = [x+v*dt for x,v in zip(z,velocity)]
        for i in range(n):
            if active[i] and z[i] == (2*L if direction[i] == 1 else 0):
                active[i] = False
                assert now%2 == 0
                answer[i] = now//2
    raise AssertionError('brute event loop')

def check_b():
    cases=[]
    for n in range(1,5):
        for data in itertools.product([(a,d) for a in range(3) for d in 'EW'],repeat=n):
            for k in (1,2): cases.append((2,k,data))
    for _ in range(12000):
        n=RNG.randint(1,10); L=RNG.randint(1,30); K=RNG.randint(1,L)
        cases.append((L,K,[(RNG.randint(0,L),RNG.choice('EW')) for _ in range(n)]))
    for offset in range(0,len(cases),500):
        batch=cases[offset:offset+500]
        data=str(len(batch))+'\n'+''.join(f'{len(deer)} {L} {K}\n'+''.join(f'{a} {d}\n' for a,d in deer) for L,K,deer in batch)
        output=run('B',data).splitlines()
        assert len(output)==len(batch)
        for (L,K,deer),line in zip(batch,output):
            expected=deer_brute(L,K,deer)
            assert list(map(int,line.split()))==expected,(L,K,deer,line,expected)
    done('B',len(cases),'C++17 与全体异向配对事件扫描模拟对拍，含同坐标、阈值重合及连锁等待')

def check_a():
    for case in range(500):
        n=RNG.randint(2,8)
        edges=[(i,RNG.randrange(i),RNG.randint(1,20)) for i in range(1,n)]
        used={tuple(sorted((u,v))) for u,v,w in edges}
        for u in range(n):
            for v in range(u):
                if (v,u) not in used and RNG.random()<.5: edges.append((u,v,RNG.randint(1,20)))
        dist=[[0 if i==j else 10**9 for j in range(n)] for i in range(n)]
        for u,v,w in edges: dist[u][v]=dist[v][u]=w
        for k in range(n):
            for i in range(n):
                for j in range(n): dist[i][j]=min(dist[i][j],dist[i][k]+dist[k][j])
        c=[[0 if a==i else min([2*dist[a][u]+w for u,v,w in edges if v==i]+[2*dist[a][v]+w for u,v,w in edges if u==i]) for i in range(n)] for a in range(n)]
        s,t=RNG.randrange(n),RNG.randrange(n)
        ans=[10**9]*(n*n); ans[s*n+t]=0; heap=[(0,s*n+t)]
        while heap:
            d,v=heapq.heappop(heap)
            if d!=ans[v]: continue
            a,b=divmod(v,n)
            for i in range(n):
                for j in range(n):
                    nd=d+max(c[a][i],c[b][j]); v=i*n+j
                    if nd<ans[v]: ans[v]=nd; heapq.heappush(heap,(nd,v))
        data=f'{n} {len(edges)}\n'+''.join(f'{u+1} {v+1} {w}\n' for u,v,w in edges)+f'{s+1} {t+1}\n'
        actual=list(map(int,run('A',data).split()))
        assert actual==ans,(data,actual,ans)
    done('A',500,'C++17 与显式 n² 状态、n⁴ 转移最短路对拍')

def check_c():
    cases=[]; expected=[]
    for k in range(1,51):
        N=1000
        future=[0]*(N+1)
        for turn in range(N-1,-1,-1):
            player=bin(turn).count("1")%2
            current=[player]*(N+1)
            prefix=[0]
            for v in future[:N-turn+1]: prefix.append(prefix[-1]+(v==player))
            for n in range(k+1,N-turn+1):
                current[n]=player if prefix[n]>prefix[n-k] else 1-player
            future=current
        for n in range(1,N+1): cases.append((n,k)); expected.append('cat' if future[n]==0 else 'dog')
    actual=run('C',str(len(cases))+'\n'+''.join(f'{n} {k}\n' for n,k in cases)).split()
    assert actual==expected,next(((c,a,e) for c,a,e in zip(cases,actual,expected) if a!=e),None)
    done('C',len(cases),'C++17 与逐回合、逐石子数极小极大 DP 对拍')

def check_e():
    cases=[(4,list(s)) for s in itertools.combinations(range(1,17),4)]
    for n in range(5,61):
        for _ in range(10): cases.append((n,RNG.sample(range(1,n*n+1),n)))
    cases += [(n,list(range(1,n+1))) for n in (100,501,1000)]
    for offset in range(0,len(cases),100):
        batch=cases[offset:offset+100]
        data=str(len(batch))+'\n'+''.join(str(n)+'\n'+' '.join(map(str,x))+'\n' for n,x in batch)
        output=iter(map(int,run('E',data,90).split()))
        for n,x in batch:
            A=[[next(output) for _ in range(n)] for _ in range(n)]
            B=[[next(output) for _ in range(n)] for _ in range(n)]
            assert A[0]==B[0]==x
            assert sorted(sum(A,[]))==sorted(sum(B,[]))==list(range(1,n*n+1))
            delta=[None]*(2*n-1); changes=0
            for i in range(n):
                for j in range(n):
                    d=B[i][j]-A[i][j]
                    if delta[i+j] is None: delta[i+j]=d
                    assert delta[i+j]==d
                    changes+=bool(d)
            assert sum(delta)==0 and changes==n*(n-1)//2
        assert next(output,None) is None
    done('E',len(cases),'C++17 穷举 n=4 的 1820 种首行数值集合，并验证随机及 n=1000 构造的排列、反对角线差值和最优修改数')

def check_h():
    cases=[]
    for n in range(1,41):
        lengths=sorted([r-l+1 for l in range(1,n+1) for r in range(l,n+1)],reverse=True)
        M=sum(lengths[:n]); a=[RNG.randint(1,100) for _ in range(n)]
        for m in range(n,M+1): cases.append((n,m,a))
    for _ in range(100):
        n=RNG.randint(100,2000)
        lengths=[]
        for length in range(n,0,-1):
            lengths.extend([length]*min(n-len(lengths),n-length+1))
            if len(lengths)==n: break
        cases.append((n,RNG.randint(n,sum(lengths)),[RNG.randint(1,10**8) for _ in range(n)]))
    dog=[]
    for offset in range(0,len(cases),500):
        batch=cases[offset:offset+500]
        data='cat\n'+str(len(batch))+'\n'+''.join(f'{n} {m}\n'+' '.join(map(str,a))+'\n' for n,m,a in batch)
        output=iter(map(int,run('H',data).split()))
        for n,m,a in batch:
            intervals=[(next(output),next(output)) for _ in range(n)]
            assert len(set(intervals))==n
            assert all(1<=l<=r<=n for l,r in intervals)
            assert sum(r-l+1 for l,r in intervals)==m
            prefix=[0]
            for x in a: prefix.append(prefix[-1]+x)
            s=sum(prefix[r]-prefix[l-1] for l,r in intervals)
            dog.append((n,s,a,m))
        assert next(output,None) is None
    for offset in range(0,len(dog),500):
        batch=dog[offset:offset+500]
        data='dog\n'+str(len(batch))+'\n'+''.join(f'{n} {s}\n'+' '.join(map(str,a))+'\n' for n,s,a,m in batch)
        actual=list(map(int,run('H',data).split()))
        assert actual==[m for n,s,a,m in batch]
    done('H',len(cases),'C++17 双次运行往返验证，n≤40 覆盖全部可行 m，检查区间互异、长度和及解码')


for letter in "ABCEH":
    globals()["check_" + letter.lower()]()


R=random.Random(468502)
checks={}
def done(letter,count,detail):
    checks[letter]=dict(passed=True,cases=count,detail=detail)
    print(letter,count,detail,flush=True)

cases=[list(x) for n in range(1,7) for x in itertools.product(range(1,5),repeat=n)]
data=str(len(cases))+'\n'+''.join(str(len(a))+'\n'+' '.join(map(str,a))+'\n' for a in cases)
assert list(map(int,run('D',data).split()))==[ref.robot_brute(a) for a in cases]
done('D',len(cases),'实际 C++17 穷举与逐轮模拟一致')

for _ in range(300):
    slots=[[(R.randrange(10**8+1),R.randrange(10**8+1)) for j in range(R.randint(1,4))] for i in range(6)]
    data=' '.join(str(len(a)) for a in slots)+'\n'+''.join(f'{p} {d}\n' for a in slots for p,d in a)
    expected=1+max(min(sum(t[0] for t in choice),10**8)*sum(t[1] for t in choice) for choice in itertools.product(*slots))/10**16
    assert math.isclose(float(run('F',data)),expected,rel_tol=1e-10,abs_tol=1e-10)
done('F',300,'实际 C++17 与六槽位完整组合穷举一致，包含暴击封顶')

for _ in range(300):
    n=R.randint(1,9); x=sorted(R.sample(range(-30,31),n)); a=[R.randint(1,30) for i in x]
    changes=[(R.randrange(n),R.randint(1,30)) for j in range(8)]
    data=f'{n} {len(changes)}\n'+' '.join(map(str,x))+'\n'+' '.join(map(str,a))+'\n'+''.join(f'{p+1} {v}\n' for p,v in changes)
    expected=[ref.sticks_brute(x,a)]
    for p,v in changes: a[p]=v; expected.append(ref.sticks_brute(x,a))
    assert list(map(int,run('G',data).split()))==expected
done('G',2700,'实际 C++17 初值及点修改对比全部方向穷举')

for _ in range(250):
    n=R.randint(2,6); r=R.randint(1,n-1); p=R.randint(1,3)
    d=[[R.randint(1,4) if i!=j else 0 for j in range(n)] for i in range(n)]
    a=[sorted(R.sample(range(7),p)) for i in range(n-r)]
    b=[sorted(R.sample(range(9),p)) for i in range(n)]
    x,y=R.randrange(r,n),R.randrange(r)
    w=[[0]*n for i in range(n)]
    for i in range(r,n):
        for j in range(n):
            if i!=j:
                w[i][j]=sum(all(a[i-r][t]<=v and v+d[i][j]<=b[j][t] for t,v in enumerate(ts)) for ts in itertools.combinations(range(9),p))
    expected=ref.forest_brute(w,r,x,y)
    data=f'{n} {r} {p}\n'+''.join(' '.join(map(str,row))+'\n' for row in d+a+b)+f'{x+1} {y+1}\n'
    assert int(run('I',data))==expected
done('I',250,'实际 C++17 与发车时间及下一站双重穷举一致')

cases=[list(a) for n in range(1,7) for a in itertools.combinations_with_replacement(range(4),n)]
data=str(len(cases))+'\n'+''.join(str(len(a))+'\n'+' '.join(map(str,a))+'\n' for a in cases)
assert list(map(int,run('J',data).split()))==[ref.mice_brute(a) for a in cases]
done('J',len(cases),'实际 C++17 与位掩码匹配一致')

grid=[(x,y) for x in range(-3,4) for y in range(-3,4) if x or y]
cases=[R.sample(grid,R.randint(3,13)) for _ in range(2500)]
data=str(len(cases))+'\n'+''.join(str(len(a))+'\n'+''.join(f'{x} {y}\n' for x,y in a) for a in cases)
expected=[min([hi-lo for lo in range(len(a)) for hi in range(lo+3,len(a)+1) if ref.hull_brute(a[lo:hi])] or [-1]) for a in cases]
assert list(map(int,run('K',data).split()))==expected
done('K',len(cases),'实际 C++17 最短窗口与逐区间凸包判定一致')

cases=[''.join(a) for n in range(1,10) for a in itertools.product('ab',repeat=n)]
cases+=[''.join(R.choices('abc',k=R.randint(1,12))) for _ in range(1000)]
data=str(len(cases))+'\n'+''.join(str(len(s))+'\n'+s+'\n' for s in cases)
assert list(map(int,run('L',data).split()))==[ref.letters_brute(s) for s in cases]
done('L',len(cases),'实际 C++17 与不相交相邻交换穷举一致')

for case in range(100):
    n=1 if case==0 else 10**6 if case==99 else R.randint(2,2000)
    if case==99:
        points=[(i,i,i) for i in range(1,n+1)]
    else:
        points=list(zip(*[R.sample(range(1,n+1),n) for _ in range(3)]))
    process=subprocess.Popen([str(ROOT/'solutions/M')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    process.stdin.write('1\n'+str(n)+'\n'+''.join(f'{a} {b} {c}\n' for a,b,c in points)); process.stdin.flush()
    candidates=points; queries=0
    while True:
        line=process.stdout.readline().split(); assert line
        if line[0]=='!':
            assert len(candidates)==1 and tuple(map(int,line[1:]))==candidates[0]
            break
        assert line[0]=='?' and len(line)==4
        q=tuple(map(int,line[1:])); assert all(1<=v<=n for v in q)
        groups={}
        for point in candidates:
            reply=''.join(str(int(a>b)) for a,b in zip(q,point))
            groups.setdefault(reply,[]).append(point)
        reply,candidates=max(groups.items(),key=lambda t:len(t[1]))
        queries+=1; assert queries<=10
        process.stdin.write(reply+'\n'); process.stdin.flush()
    process.stdin.close(); assert process.wait(timeout=10)==0
done('M',100,'实际 C++17 自适应交互器每次选择最大候选分支，含 n=1000000，查询不超过10次')

release=json.loads((REPOSITORY/'src/qq_cf_bot/catalog/regional_statements.json').read_text())
sample_count=0
for letter in 'ABCDEFGIJKL':
    for data,expected in release['problems']['ccpc-2026-乐山:'+letter]['statement']['samples']:
        if letter=='E': continue
        actual=run(letter,data+'\n')
        if letter=='F': assert math.isclose(float(actual),float(expected),rel_tol=1e-10,abs_tol=1e-10)
        else: assert actual.split()==expected.split(),(letter,data,actual,expected)
        sample_count+=1
print('Statement samples passed:',sample_count,flush=True)

temporary.cleanup()
