# 实测周期分解

Actual RTL JSONL events; phase counts from every PRE state bit-checked against actual RTL (including scheduler state)

inclusive Job accept through Status accept; cleanup after Status excluded; no DDR/compute overlap

|Profile|Job|N|K|输入|Scale|Weight|计算|Requant|输出|Status等待|调度额外|端到端|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|integration_s0_b3|100|2|129|153|7|18|106|9|6|39|7|345|
|integration_s0_b3|101|129|1|4|18|1124|2466|143|28|39|7|3829|
|integration_s0_b3|102|1|127|149|7|8|35|8|6|39|7|259|
|integration_s0_b3|103|2|128|150|8|21|70|9|8|39|7|312|
|integration_s0_b3|104|3|129|153|7|27|159|10|6|39|7|408|
|integration_s0_b3|105|1|2048|2385|9|91|530|8|7|39|7|3076|
|integration_s0_b3|106|2|2049|2388|8|118|1090|9|6|39|7|3665|
|integration_s0_b3|107|2|4096|4769|9|361|2116|9|6|39|7|7316|
|integration_s0_b3|108|2|12288|14305|14|648|6340|9|6|39|7|21368|
|integration_s0_b3|109|257|7|10|26|2143|5140|278|53|39|7|7696|
|integration_s1_b3|100|2|129|153|7|18|106|9|6|39|7|345|
|integration_s1_b3|101|2|129|153|8|23|100|9|6|39|7|345|
|integration_s0_b1|100|2|129|153|7|26|106|9|6|39|7|353|
|integration_s0_b1|101|129|1|4|18|1124|2466|143|28|39|7|3829|
|integration_s0_b1|102|1|127|149|7|10|35|8|6|39|7|261|
|integration_s0_b1|103|2|128|150|8|25|70|9|6|39|7|314|
|integration_s0_b1|104|3|129|153|7|39|159|10|6|39|7|420|
|integration_s0_b1|105|1|2048|2385|9|157|530|8|6|39|7|3141|
|integration_s0_b1|106|2|2049|2388|10|206|1090|9|6|39|7|3755|
|integration_s0_b1|107|2|4096|4769|13|612|2116|9|8|39|7|7573|
|integration_s0_b1|108|2|12288|14305|22|1160|6340|9|6|39|7|21888|
|integration_s0_b1|109|257|7|10|24|2135|5140|278|51|39|7|7684|
|integration_s0_b2|100|2|129|153|7|22|106|9|6|39|7|349|
|integration_s0_b2|101|129|1|4|18|1124|2466|143|28|39|7|3829|
|integration_s0_b2|102|1|127|149|7|8|35|8|6|39|7|259|
|integration_s0_b2|103|2|128|150|8|21|70|9|8|39|7|312|
|integration_s0_b2|104|3|129|153|7|33|159|10|6|39|7|414|
|integration_s0_b2|105|1|2048|2385|9|114|530|8|6|39|7|3098|
|integration_s0_b2|106|2|2049|2388|8|142|1090|9|6|39|7|3689|
|integration_s0_b2|107|2|4096|4769|12|435|2116|9|6|39|7|7393|
|integration_s0_b2|108|2|12288|14305|16|776|6340|9|6|39|7|21498|
|integration_s0_b2|109|257|7|10|24|2136|5140|278|54|39|7|7688|
|integration_s0_b64|100|2|129|153|7|18|106|9|6|39|7|345|
|integration_s0_b64|101|129|1|4|18|1124|2466|143|28|39|7|3829|
|integration_s0_b64|102|1|127|149|7|8|35|8|6|39|7|259|
|integration_s0_b64|103|2|128|150|8|21|70|9|8|39|7|312|
|integration_s0_b64|104|3|129|153|7|27|159|10|6|39|7|408|
|integration_s0_b64|105|1|2048|2385|9|59|530|8|7|39|7|3044|
|integration_s0_b64|106|2|2049|2388|8|78|1090|9|6|39|7|3625|
|integration_s0_b64|107|2|4096|4769|10|201|2116|9|7|39|7|7158|
|integration_s0_b64|108|2|12288|14305|12|404|6340|9|6|39|7|21122|
|integration_s0_b64|109|257|7|10|24|2147|5140|278|47|39|7|7692|
|integration_max_n|100|12288|1|4|672|86016|235140|12960|1733|39|7|336571|
|integration_retry|900|129|1|4|14|903|2580|274|24|19|7|3825|

计算列独立核对每个真实 COMPUTE_ACCEPT→RESULT_ACCEPT 包含两端的间隔；输入包含Parser解包及X RAM提交，DDR列包含合法Gap与逻辑提交，输出包含下游反压，Status等待取真实终态状态驻留。
Scheduler额外包括Job接受、预检查、子模块启动、整Job发布观察及终态提交；没有将DDR/输入或Requant计为纯计算。
Stage6完整128组无stall从start到最后握手含起止沿22 cycles。末EOT握手到status_valid相差2沿，最早Status接受再下一沿。
Status后的受控清理/重开门控不计入端到端Job周期；其释放链和Ready仍逐拍比对。

Topological graph length can traverse RAM vendor models; it is not a timed register path, ns, Fmax, or Vivado sign-off
