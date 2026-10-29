# A2 双路径精确性推导（RTL前）

基线是numeric.accumulate_48(term_bits=72)，包括非规范化零的指数和有符号负边界，不仅比较实数值。

## 位宽上界

FP8最大Q9=229376，|X|≤131072，128项故|RAW|≤3848290697216<2^42。FP32 sig<2^24，故|term|<2^66；term exponent在[-286,222]。K≤65535，Block≤512。每次RNE误差≤半ULP；用保守递推|state value|<j*2^289（单term<2^288，另预留一倍覆盖每步RNE）可得任意合法state绝对值<2^298。因min target≥-286、归一化不会降低target，state exponent≥-286；非零state exponent若大于target，mantissa幅度≥2^46（溢出retry后仍如此），故exponent≤251。于是合法指数差≤537，对齐整数加法用610个signed bits足够（537+72+1）；10×64=640足够。无需实际存610bit，更无需610bit桶形移位器。

实现额外支持全部signed16 state exp与signed12 term exp：最大差34815，最大精确signed工作宽度34888bit（统一72bit上界）。用10bit chunk index与17bit指数/位置运算覆盖，串行扫描最多546个64bit chunk；完整字段非核心范围测试耗时可高于64cycle，合法核心最多10 chunks。

快速路径非零指数差≤48：signed72左移最多48需signed120，48bit旧状态最多96bit；两者和signed121，signed128完全覆盖。旧state=0不对齐旧指数，term=0必须原pair直返。

## 特殊路径的精确分段加减

写精确公共指数整数S=H*2^d+L，d>48，H对应较大指数。分别取绝对幅度，先确定最终符号。若d≥72，非零|H|*2^d>|L|；若d<72，128bit比较即可（最大143? 此比较仅在d<72时不能直接假设128能容纳72+d；实际只需当高位非零判定H更大，再比较低128bit。RTL以位长比较优先，仅同位长≤72才执行对齐比较，保证不丢高位）。

同号做unsigned65加法传播carry，异号以较大绝对值减较小绝对值，unsigned65逐段传播borrow；结果总非负。输入chunk由72bit源及位位置提取，负位置仅左移0..63、正位置仅右移0..71，gap全0；不存在宽度依赖d的运算。迭代ceil((d+73)/64)段，为最高可能carry预留一位。最后carry/borrow必须0，否则40。

每轮保存previous64及其以下所有已算结果的OR；遇到非零chunk C_i时保存W={C_i,C_(i-1)}、b=64(i-1)、L=64i+bit_length(C_i)、sticky=OR(C_0..C_(i-2))。扫描结束，最后保存的i恰为精确最高非零chunk（更高的0不覆盖W）。即使严重抵消导致最高有效chunk很低，也不丢失其完整有效窗口。若全零，W=L=0、b=0、sticky=0。

对最终符号n：精确最小归一化shift s=max(0,L-47)，仅当负且|S|为2的幂时改成max(0,L-48)。是否幂由最高chunk单1、previous=0、sticky=0精确确定。这复现required_signed_bits对负数的非对称定义。

保留128bit窗口足够：当i≥1，s-b至少17（负2幂为16）；当i=0，b=-64，s-b≥64。所有舍入截点及guard都在W内，其以下只需要“是否有任意非零”来比较半值，sticky是完整精确加减后结果的OR，不是对输入小Term的近似。q=W>>(s-b)；guard=bit(s-b-1)，tail=其下W的OR或sticky。guard&&(tail||q[0])即RNE进位。恢复符号后若超signed48范围，以原W/sticky在s+1重新舍入，禁止对第一次rounded再舍入。一次retry足够，因为第一次q最多2^47（负允许），retry至多2^46。

零Term原pair保留；旧state零忽略se；精确抵消输出(0,min(se,te))。提交前target+s在17bit计算并验证signed16范围，溢出报32且不改state。

指定反例S=2^286+1，L=287，s=240，q=2^46，exp=-286+240=-46，精确输出(70368744177664,-46)。这说明不能简单丢小Term：丢弃它后保留(1,0)虽然实数近似却pair错误。

验证：stage4_golden.py用Fraction和区间搜索，不调用numeric或本原型；stage4_a2_math.py实现分段不构造宽S；两者与原numeric逐pair对照，切换边界±48、±49以及可在128内执行的重叠区双路径直接对照。运行证据见numeric_prototype.log；这为数学推导+有限随机/定向验证，不是形式化穷举证明。

补充宽度界的归纳细节：每次有损RNE的相对误差不大于2^-46（实际更小），未右移时误差为0。若j≤512且旧幅度<j·2^289，加一个幅度<2^288的Term，则舍入前<(j+1/2)·2^289，舍入后<(j+1/2)(1+2^-46)·2^289<(j+1)·2^289。因此全Channel幅度<2^298。若归一化右移过，提交mantissa幅度至少2^46（overflow retry后也如此），所以提交exp≤251；若未右移，exp只是target≤222。由此没有依赖“假设FP32常见范围”截断工作宽度。

RTL提取器的缩位也是精确的：position≥72或≤-64时chunk必为0；否则非负position只可能0..71，取其[6:0]完全等值；负position只可能-63..-1，其6bit二补数再求负得到1..63，恰为左移量。S_SETUP锁存high_offset=-gap，之后每段+64，与i*64-gap逐段恒等。相关RTL优化不减少任何有效位。
