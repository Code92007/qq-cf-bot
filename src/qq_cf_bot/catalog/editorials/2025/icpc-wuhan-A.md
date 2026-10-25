# A · Planting Trees

## 先学什么

先学取模、向下取整和类欧几里得算法 floor_sum。建议先写O(n)逐日模拟，再把它与快速公式对拍。负数除法尤其重要：数学floor与C++向零截断不同，不能直接用负数/正数代替floor。

## 题意

左树初始x、每天长f，右树初始y、每天长g，每天把高度减到[0,m)范围内，统计前n天左边严格低于右边的次数。第一天也修剪，故时间从t=0到n-1。每个参数≤10^6，最多10^4组。

## 把比较变成整除

对两个余数u、v，v-u-1介于-m与m-2之间：u<v时它非负、除m向下取整为0；u≥v时它为负、取整为-1。因此

```text
[u<v] = 1 + floor((v-u-1)/m)
```

设X=ft+x，Y=gt+y，用u=X-m floor(X/m)、v=Y-m floor(Y/m)代入，得到

```text
[u<v] = 1 - floor(Y/m) + floor(X/m) + floor((Y-X-1)/m)
```

定义 F(n,m,a,b)=sum(floor((a*t+b)/m),t=0..n-1)，答案即

```text
n - F(n,m,g,y) + F(n,m,f,x) + F(n,m,g-f,y-x-1)
```

最后一个F的a、b可能负，不能忽略。

## floor_sum的完整实现思路

先把a、b按数学floor拆成 a=qa*m+ra、b=qb*m+rb，其中0≤ra,rb<m。对应贡献为

```text
qa*n*(n-1)/2 + qb*n
```

剩余只需算非负ra、rb。之后使用欧几里得式交换：

```text
ans=上述归一化贡献；a=ra；b=rb
循环：
    ans += (a//m)*n*(n-1)/2 + (b//m)*n
    a%=m；b%=m
    Y=a*n+b
    若 Y<m：结束
    n=Y//m；b=Y%m
    交换 a,m
```

交换对应把直线下的整点计数横纵互换；较大参数不断取余，复杂度O(log m)。归一化后的循环中参数非负，普通整数除法即可。

C++负数floor可写成：q=a/m，r=a%m；若r<0，则q--、r+=m。对b同样处理。不要把斜率g-f当成无符号数。

## 例子、复杂度与验证

样例f=7,x=4,g=6,y=3,n=3,m=4，两边余数依次是(0,3)、(3,1)、(2,3)，答案2。m=1时双方永远0，公式也应得到0；严格小于必须保留式子里的-1。

单组O(log m)，额外空间O(1)。中间乘积用64位，通用实现也可用128位保护三角项。工程逐日枚举检查比较公式，并单独对负斜率、负截距的floor_sum进行对拍。尚未在线提交。

## 来源

依据[官方讲义](https://contest.ucup.ac/download.php?type=attachments&id=2609&r=2)第27,28页与[正式题面](https://contest.ucup.ac/download.php?type=attachments&id=2609&r=1)展开。示例、细化证明与验证程序由本工程补充。
