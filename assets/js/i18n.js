/* ==========================================================================
   i18n — English is authored inline in the HTML and captured on first run;
   the dictionary only carries the translations. One source of truth per
   string, so meaning never gets duplicated across pages.
   ========================================================================== */
(function () {
  var KEY = "napell_fc_lang";
  var DEFAULT = "en";

  /* zh dictionary. Keys map to the English text written in the markup. */
  var ZH = {
    /* nav */
    "nav.platform": "平台",
    "nav.platform.d": "网络、种植舱与生产指标",
    "nav.overview": "总览",
    "nav.overview.d": "全网状态与影响指标",
    "nav.network": "网络注册表",
    "nav.network.d": "GrowerID · 基地 · 种植舱",
    "nav.modules": "种植舱监控",
    "nav.modules.d": "IoT 遥测与环境闭环",
    "nav.analytics": "数据洞察",
    "nav.analytics.d": "单产、能耗与情景推演",
    "nav.trace": "溯源",
    "nav.trace.d": "可验证的供应链事件链",
    "nav.ledger": "溯源账本",
    "nav.ledger.d": "哈希链浏览与校验",
    "nav.lots": "批次",
    "nav.lots.d": "从播种到出运",
    "nav.compliance": "合规",
    "nav.compliance.d": "监管证据自动化",
    "nav.reports": "报告中心",
    "nav.reports.d": "EUDR 与 LCA 报告",
    "nav.consumer": "消费端",
    "nav.consumer.d": "Thank My Farm 扫码体验",
    "nav.consume": "Thank My Farm",
    "nav.consume.d": "扫码看种植旅程",
    "nav.projects": "社区项目",
    "nav.projects.d": "收益回流与资助",
    "nav.docs": "文档",
    "nav.docs.d": "集成与技术说明",
    "nav.api": "API 参考",
    "nav.api.d": "端点、鉴权与示例",
    "nav.why": "技术白皮书",
    "nav.why.d": "为什么气雾培改变溯源逻辑",

    /* common */
    "c.verified": "已验证",
    "c.open": "进行中",
    "c.all": "全部",
    "c.loading": "加载中…",
    "c.error": "加载失败",
    "c.retry": "重试",
    "c.refresh": "刷新",
    "c.export": "导出",
    "c.generate": "生成",
    "c.issue": "签发",
    "c.view": "查看",
    "c.detail": "详情",
    "c.back": "返回",
    "c.copy": "复制",
    "c.copied": "已复制",
    "c.hash": "哈希",
    "c.seq": "序号",
    "c.actor": "操作方",
    "c.time": "时间",
    "c.event": "事件",
    "c.stage": "阶段",
    "c.status": "状态",
    "c.cultivar": "品种",
    "c.facility": "基地",
    "c.module": "种植舱",
    "c.grower": "种植方",
    "c.country": "国家/地区",
    "c.city": "城市",
    "c.yield": "产量",
    "c.green": "生豆",
    "c.roasted": "熟豆",
    "c.batch": "批次",
    "c.events": "事件数",
    "c.none": "暂无数据",
    "c.empty": "这里还没有数据",
    "c.allgood": "一切正常",
    "c.integrity": "链完整性",
    "c.chain_ok": "哈希链校验通过",
    "c.chain_bad": "哈希链已损坏",
    "c.verified_chain": "链上已核验",
    "c.live": "实时",
    "c.offline_demo": "离线演示",
    "c.pending": "待定",
    "c.provisional": "预估值",
    "c.search": "搜索",
    "c.filter": "筛选",
    "c.of": "/",
    "c.samples": "样本数",
    "c.setpoint": "设定值",
    "c.mean": "均值",
    "c.hours": "小时",
    "c.days": "天",
    "c.acknowledge": "确认",
    "c.acknowledged": "已确认",

    /* home */
    "home.eyebrow": "气雾培咖啡供应链网络",
    "home.h1": "可证明的咖啡，不需要土地。",
    "home.lede": "farmerconnect 用人工申报与卫星影像去证明不存在砍伐。气雾培把这个问题直接消掉 —— 没有地块，没有土地转换，环境数据由传感器写入不可篡改的事件链。",
    "home.cta1": "打开溯源账本",
    "home.cta2": "看消费者扫码页",
    "home.kpi.growers": "注册种植方",
    "home.kpi.modules": "在网种植舱",
    "home.kpi.green": "累计生豆产量",
    "home.kpi.events": "账本事件",
    "home.why.eyebrow": "核心差异",
    "home.why.h": "同类平台证明一个否定命题。我们把它变成结构事实。",
    "home.why.them": "farmerconnect / Agridence 式的做法",
    "home.why.them.1": "数据由供应链各方人工上传，格式各异，时点滞后",
    "home.why.them.2": "EUDR 要求证明 2020 年后未砍伐，只能靠地块多边形与卫星推断",
    "home.why.them.3": "水耗、土地占用是估算值，无法复现",
    "home.why.them.4": "公平贸易承诺依赖第三方审计抽查",
    "home.why.us": "气雾培封闭系统的做法",
    "home.why.us.1": "EC / pH / VPD / PPFD / CO₂ 由控制器直接写入，无法人工回填",
    "home.why.us.2": "没有地块，土地转换风险结构性为零，不是估计为零",
    "home.why.us.3": "水耗与能耗来自批次实测，任何人可用同一输入复算",
    "home.why.us.4": "每一次收获都可追溯到具体舱位与那段环境曲线",
    "home.pillars.eyebrow": "四个模块",
    "home.pillars.h": "从注册到扫码，一条连续的证据线。",
    "home.p1.t": "身份注册",
    "home.p1.d": "GrowerID 自权身份，绑定基地、种植舱与批次。凭证来自链上事件而非申报表。",
    "home.p2.t": "IoT 遥测",
    "home.p2.d": "每舱 8 路传感器通道，阈值偏离自动告警，周期性环境摘要写入账本。",
    "home.p3.t": "合规引擎",
    "home.p3.d": "EUDR 尽职调查声明与 LCA 水碳核算，采收时自动签发，附链上锚点。",
    "home.p4.t": "消费端",
    "home.p4.d": "扫码看到种植旅程、环境曲线与省水量，收益可追踪回流到种植方。",
    "home.impact.eyebrow": "影响核算",
    "home.impact.h": "实测，不是宣称。",
    "home.impact.note": "缺口对比基于 config 中的常规种植基准，套用在账本记录的实测产量上。能源强度一项我们如实披露为更高。",
    "home.water": "蓝水取水量节省",
    "home.land": "土地占用节省",
    "home.co2": "碳足迹缺口",
    "home.energy": "能源强度缺口",
    "home.live.eyebrow": "实时状态",
    "home.live.h": "网络当前状态",
    "home.pipeline": "批次管道",
    "home.alerts": "未确认告警",
    "home.recent": "最近账本事件",
    "home.viewall": "查看全部",

    /* metrics */
    "m.water": "蓝水取水",
    "m.land": "土地占用",
    "m.energy": "能源强度",
    "m.co2": "碳足迹",
    "m.deforest": "砍伐暴露",
    "m.agro": "农化投入",
    "m.perkg.green": "每公斤生豆",
    "m.vs.conv": "对比常规种植",
    "m.better": "更优",
    "m.worse": "更高",
    "m.baseline": "基准",

    /* network */
    "net.h": "网络注册表",
    "net.lede": "注册种植方、基地与在网种植舱。每个对象在创建时写入账本，之后不可静默修改。",
    "net.growers": "种植方",
    "net.growers.lede": "自权身份与信用信号。评分由链上事件量与合规报告数推导，不由人工填写。",
    "net.facilities": "基地",
    "net.modules": "种植舱",
    "net.trust": "信任分",
    "net.yield": "产量分",
    "net.compliance": "合规分",
    "net.tier": "评级",
    "net.did": "去中心化标识",
    "net.wallet": "收款地址",
    "net.kyc": "KYC 等级",
    "net.area": "建筑面积",
    "net.racks": "货架数",
    "net.cycles": "年轮次数",
    "net.system": "系统类型",
    "net.commissioned": "投运时间",
    "net.registry_map": "基地分布",
    "net.new_grower": "注册种植方",
    "net.new_facility": "新建基地",

    /* modules */
    "mod.h": "种植舱监控",
    "mod.lede": "每舱 8 路通道。曲线来自控制器上报的原始读数，未作平滑处理；周期摘要同时写入溯源账本。",
    "mod.select": "选择种植舱",
    "mod.setpoints": "闭环设定值",
    "mod.window": "时间窗",
    "mod.alerts": "告警",
    "mod.alerts.lede": "偏离设定值超过容差即触发。告警本身不写入账本 —— 它是运维信号，不是合规证据。",
    "mod.ack": "确认",
    "mod.simulate": "推进 6 小时",
    "mod.simulate.d": "把确定性传感器读数向前推 6 小时，用于现场演示。",
    "mod.ingest": "手动上报读数",
    "mod.ingest.d": "模拟设备网关调用，验证阈值告警与账本锚定。",
    "mod.water": "本窗口耗水",
    "mod.energy": "本窗口耗电",
    "mod.plant_count": "株数",
    "mod.active_batch": "在种批次",
    "mod.chart.ec": "EC 电导率",
    "mod.chart.ph": "pH",
    "mod.chart.temp": "空气与根区温度",
    "mod.chart.vpd": "VPD",
    "mod.chart.ppfd": "光照 PPFD",
    "mod.chart.rh": "空气湿度",

    /* traceability */
    "tr.h": "溯源账本",
    "tr.lede": "每个事件提交到前一个事件的哈希。改动任意历史行都会让它之后的所有行校验失败 —— 这就是可验证的含义。",
    "tr.verify": "校验整条链",
    "tr.verify.d": "重算全部事件哈希并与存储值比对。",
    "tr.len": "链长度",
    "tr.head": "链头哈希",
    "tr.algo": "算法",
    "tr.filter.entity": "按对象筛选",
    "tr.filter.type": "按类型筛选",
    "tr.event_count": "事件标签",
    "tr.payload": "载荷",
    "tr.prev": "前序哈希",
    "tr.self": "本事件哈希",
    "tr.tamper": "篡改演示",
    "tr.tamper.d": "直接改写数据库中的一个历史载荷，再回来校验 —— 链会在被改动的位置断开。",

    /* lots */
    "lot.h": "批次",
    "lot.lede": "每个批次是一段封闭生命周期。未完成采收的批次只展示预测产量，LCA 标记为预估值。",
    "lot.progress": "生命周期进度",
    "lot.current": "当前阶段",
    "lot.projected": "预测生豆产量",
    "lot.actual": "实际生豆产量",
    "lot.retail": "零售就绪",
    "lot.missing": "缺失证据",
    "lot.grower": "种植方",
    "lot.journey": "种植旅程",
    "lot.attestations": "环境存证",
    "lot.attestations.lede": "周期性环境摘要，由控制器网关签名后写入账本。",
    "lot.env": "环境实测",
    "lot.lca": "生命周期评价",
    "lot.eudr": "EUDR 尽职调查",
    "lot.auto": "采收时自动签发",
    "lot.issue_now": "立即签发",
    "lot.regenerate": "重新签发",
    "lot.scans": "扫码次数",
    "lot.tips": "打赏笔数",
    "lot.tip_total": "打赏金额",
    "lot.scenario": "可再生电力情景",
    "lot.scenario.d": "拖动以观察碳足迹随电网结构变化。水与土地不受影响。",
    "lot.renewable": "可再生电力占比",
    "lot.checks": "合规检查项",
    "lot.satisfied": "已满足",
    "lot.geolocation": "地理定位",
    "lot.geom": "生产地几何",

    /* consumer */
    "con.eyebrow": "Thank My Farm",
    "con.h": "这一杯从哪来。",
    "con.lede": "扫码或输入令牌，看到这包咖啡的完整种植旅程、封闭环境曲线，以及相比常规种植省下的水与土地。",
    "con.token": "溯源令牌",
    "con.open": "打开旅程",
    "con.demo": "试用演示令牌",
    "con.grown_by": "种植方",
    "con.grown_at": "种植基地",
    "con.system": "生产系统",
    "con.journey": "这段旅程",
    "con.env": "封闭环境",
    "con.env.d": "所有读数来自舱内控制器，非人工申报。",
    "con.impact": "你这一杯的影响",
    "con.impact.d": "以本批次实测投入计算，对比常规露天种植基准。",
    "con.integrity": "可核验性",
    "con.integrity.d": "你看到的事件都由哈希互相链接。任何改动都会被校验发现。",
    "con.community": "支持产地",
    "con.community.d": "资金去向写入账本，可追溯到具体种植方。",
    "con.tip": "打赏",
    "con.tip.amt": "金额 USD",
    "con.tip.send": "送出",
    "con.tip.ok": "已记录，资金将回流至该种植方",
    "con.scans": "本批次扫码",
    "con.projects": "社区项目",
    "con.progress": "筹款进度",
    "con.backers": "支持者",
    "con.funded": "已筹",

    /* api */
    "api.h": "API 参考",
    "api.lede": "整站由同一组 REST 端点驱动。写入操作通过 X-Napell-User 头归属操作方，未提供时归属系统。",
    "api.auth": "鉴权",
    "api.endpoints": "端点",
    "api.example": "示例",
    "api.readonly": "只读",
    "api.write": "写入",
    "api.docs": "交互式文档",
    "api.docs.d": "FastAPI 自动生成的 OpenAPI 界面。",
    "api.liveonly": "由实时 API 进程提供，静态构建下不可用",
    "api.docs.offline": "这三个端点由 API 进程直接提供。当前为静态只读快照构建，因此在此不可用 —— 下方端点清单完整。",

    /* analytics */
    "ana.lede": "生产强度、按批次的资源消耗，以及唯一还会显著影响碳数字的变量：电力结构。",
    "ana.intensity": "单产强度",
    "ana.produced": "生豆产量",
    "ana.carbon": "加权碳足迹",
    "ana.yield": "各基地单产强度",
    "ana.resource": "各批次资源消耗",
    "ana.table": "按批次资源强度",
    "ana.note": "如何读这些数字",
    "ana.n1": "闭环系统可从冷凝水中回收约 94% 的循环水，净取水量低于每公斤生豆 2 升，而基准为 250 升。",
    "ana.n2": "土地口径只计建筑占地面积。实际在架的栽培面积是其数倍，因此这个对比是偏保守的。",
    "ana.n3": "能源缺口是真实存在的。封闭环境用水与土地的节省，是用电换来的；可再生比例为 0 时，碳足迹会劣于露天种植。",
    "ana.n4": "暴露为零，因为没有土地被转换。这是唯一一个结构性为零、而非实测为零的项。",

    /* compliance page */
    "cmp.lede": "每个批次两份档案。EUDR 尽职调查声明主张没有土地被转换；生命周期评价用公开基准量化水、土地、能源与碳。两者在签发瞬间锚定进账本。",
    "cmp.baseline": "对比基准",

    /* home extras */
    "home.honest": "封闭环境的用电强度高于露天种植，我们把它如实列为赤字而不是隐藏。水、土地、农化与砍伐四项则朝相反方向移动。",
    "home.close1": "把账本拿掉，这仍然是一座咖啡农场。留下它，销售沟通里的每一句话背后都有一个哈希 —— 包括那些对我们不利的数字。",
    "home.close2": "EUDR 对大型运营方的强制执行从 2026 年 12 月 30 日开始。一个不含土地的生产系统，没有任何东西需要回溯到森林边界。",

    /* traceability extras */
    "tr.tamper.d2": "指针全部失配。自动化测试会对运行中的数据库执行这次改写，并断言断链被检出。",
    "tr.tamper.note": "哈希链证明记录在事后未被篡改。它本身不能证明传感器是诚实的 —— 那需要硬件证明，详见运营方文档。",

    /* api extras */
    "api.auth.d": "本演示构建为离线且免鉴权，便于无凭据评审。归属仍然强制：每次写入都记录执行方，并把该执行方一并哈希进事件。",

    /* whitepaper */
    "why.h1": "当生产不涉及土地，溯源就不再是一个报表问题。",
    "why.lede": "这是本平台要论证的核心观点，也是决定欧盟进口商能否接受这批咖啡的关键。",
    "why.s1": "自申报产地的结构性问题",
    "why.h2": "链条上每个人都有动机让数据朝有利方向偏移。",
    "why.a.t": "采集缺口",
    "why.a.d": "一个有四百户小农的合作社按月用纸笔上报产量。进入系统时已经是汇总值，而下游所有人依赖的正是这个汇总值。",
    "why.b.t": "推断缺口",
    "why.b.d": "免砍伐状态由地块多边形与卫星时序推断。这是可辩护的推断，不是观测，而且只覆盖被测绘过的土地。",
    "why.c.t": "复现缺口",
    "why.c.d": "水耗强度与碳排由区域平均值建模，两个买家向同一农场要同一个数字，可能得到不同答案且都“正确”。",
    "why.concl": "这些都不是不诚实。当证据由收入取决于它的一方生成时，结果必然如此。",
    "why.s2": "封闭系统改变了什么",
    "why.h3": "把植株移到室内，五个问题里有四个直接消失。",
    "why.col.a": "露天供应链",
    "why.col.a1": "地块几何必须在采收季开始前就采集完成。",
    "why.col.a2": "用水量是降雨、灌溉方式与区域的建模函数。",
    "why.col.a3": "碳排放取决于施肥制度、土壤碳与运输距离。",
    "why.col.a4": "农化暴露靠证书定期核验。",
    "why.col.a5": "每一次混装点都让监管链断裂。",
    "why.col.b": "封闭气雾培系统",
    "why.col.b1": "没有地块。生产地是一栋有坐标与占地面积的建筑。",
    "why.col.b2": "水在循环回路计量，在冷凝器回收。",
    "why.col.b3": "电在电表计量，碳就是用已知电网因子做的算术。",
    "why.col.b4": "不存在需要核验的施药计划。",
    "why.col.b5": "一舱一批，到包装前不发生混装。",
    "why.d1": "砍伐",
    "why.d1.d": "风险从“估计很低”变成“结构性为零”。没有地块需要与截止日期比对，且基地可在一个下午内现场核查。",
    "why.d2": "水",
    "why.d2.d": "闭环回收让净取水低于每公斤生豆 2 升，来自抄表读数而非模型。约为常规蓝水基准的 0.4%。",
    "why.d3": "能源",
    "why.d3.d": "这是坦诚承认的短板。封闭环境比露天耗电更多。可再生 60% 时全网碳足迹优于基准，0% 时则不是 —— 平台两种情况都会报。",
    "why.s3": "证据如何构建",
    "why.h4": "四层结构，每层的强度上限由下一层决定。",
    "why.l1": "第一层 —— 身份",
    "why.l1.d": "种植方、基地或种植舱都是带去中心化标识的对象。创建是事件，修改也是事件。不存在没有对应记录的状态变更，因此一段关系的全部历史是可检视的，而不是靠回忆重建。",
    "why.l2": "第二层 —— 遥测",
    "why.l2.d": "EC、pH、根区与空气温度、相对湿度、VPD、PPFD 与 CO₂。原始流数据量大，留在常规存储中。写入账本的是周期性摘要：窗口、样本数、均值与设定值 —— 足以证明一个批次所生长的气候条件，又不会让链条淹没在噪声里。",
    "why.l3": "第三层 —— 账本",
    "why.l3.d": "每个事件把自己的内容与前一事件的哈希一起哈希。从创世事件重算即可在发生改动的确切序号上检出任何篡改。证明与透明是两个不同问题：本系统解决透明，并明确说明传感器诚实性仍需硬件证明。",
    "why.l4": "第四层 —— 合规与消费端",
    "why.l4.d": "采收时系统从批次自身记录推导出两份档案并锚定。同一套证据同时服务填写尽职调查声明的欧盟进口商，和在厨房台面上扫码的消费者。一份证据，两个受众，无需二次录入。",
    "why.s4": "与既有玩家的定位",
    "why.h5": "同样三个产品，但底层行为不同。",
    "why.s5": "尚未完成的部分",
    "why.h6": "在买家自己发现之前，先把边界说清楚。",
    "why.gap.t": "已知缺口",
    "why.gap.1": "传感器诚实性目前依托网关，尚未做成签名硬件。",
    "why.gap.2": "常规种植对比用的是文献中位数，不是实测竞品。",
    "why.gap.3": "直接提交欧盟 TRACES 需要先完成运营方注册。",
    "why.gap.4": "碳核算为摇篮到大门，不含使用阶段与末端处置。",
    "why.next.t": "下一步",
    "why.next.1": "在种植舱控制器上实现传感器签名证明。",
    "why.next.2": "联盟写入模型，让合作方共同持有账本。",
    "why.next.3": "种植方结算与消费者打赏的支付通路。",
    "why.next.4": "多语言消费者页面，先做日语（对应大阪基地）。",

    /* footer */
    "f.tag": "气雾培咖啡的身份、溯源与合规网络。",
    "f.platform": "平台",
    "f.compliance": "合规",
    "f.docs": "文档",
    "f.built": "离线演示构建",
    "f.demo": "合成数据，用于产品演示",
    "f.rights": "Napell BIO · Napell Farmer Connect"
  };

  var dict = { zh: ZH };

  function current() {
    try { return localStorage.getItem(KEY) || DEFAULT; } catch (e) { return DEFAULT; }
  }

  /* data-en-title / data-en-aria-label  →  dataset.enTitle / dataset.enAriaLabel.
     The original form was "en" + attr, which produced "entitle" — a key that
     matches no attribute, so the authored English was never found and the
     attribute got written as an empty string. Since nothing used
     data-i18n-attr at the time, the fault stayed dormant. */
  function enKey(attr) {
    var camel = attr.replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
    return "en" + camel.charAt(0).toUpperCase() + camel.slice(1);
  }

  function enValue(el, attr) {
    var v = el.dataset[enKey(attr)];
    if (v === undefined) v = el.dataset["en" + attr];   // legacy single-word form
    return v;
  }

  function setEnValue(el, attr, v) { el.dataset[enKey(attr)] = v; }

  /* capture the authored English once, so switching back is lossless */
  function snapshot(root) {
    root.querySelectorAll("[data-i18n]").forEach(function (el) {
      if (el.dataset.enHtml === undefined) el.dataset.enHtml = el.innerHTML;
    });
    root.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.dataset.i18nAttr.split(",").forEach(function (spec) {
        var attr = spec.split(":")[0].trim();
        if (enValue(el, attr) === undefined) setEnValue(el, attr, el.getAttribute(attr) || "");
      });
    });
    root.querySelectorAll(".en, .zh").forEach(function (el) {
      if (el.dataset.enHtml === undefined && el.classList.contains("en")) el.dataset.enHtml = el.innerHTML;
      if (el.dataset.zhHtml === undefined && el.classList.contains("zh")) el.dataset.zhHtml = el.innerHTML;
    });
  }

  function apply(root) {
    root = root || document;
    var lang = current();
    snapshot(root);

    root.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.dataset.i18n;
      var table = dict[lang];
      el.innerHTML = (table && table[key] !== undefined && lang !== DEFAULT)
        ? table[key] : el.dataset.enHtml;
    });

    root.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.dataset.i18nAttr.split(",").forEach(function (spec) {
        var p = spec.split(":");
        var attr = p[0].trim();
        var key = p[1].trim();
        var table = dict[lang];
        var val = (table && table[key] !== undefined && lang !== DEFAULT) ? table[key] : enValue(el, attr);
        if (val !== undefined && val !== null) el.setAttribute(attr, val);
      });
    });

    root.querySelectorAll(".en, .zh").forEach(function (el) {
      var wantEn = lang === DEFAULT;
      var isEn = el.classList.contains("en");
      if (wantEn && isEn) el.innerHTML = el.dataset.enHtml;
      if (!wantEn && !isEn && el.dataset.zhHtml) el.innerHTML = el.dataset.zhHtml;
    });

    document.documentElement.lang = lang === "zh" ? "zh-Hans" : "en";
    document.documentElement.dataset.lang = lang;
    document.querySelectorAll(".lang button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.lang === lang);
    });
  }

  /* t(key, englishFallback) — for strings rendered from JavaScript */
  function t(key, fallback) {
    var lang = current();
    var table = dict[lang];
    if (table && table[key] !== undefined) return table[key];
    return fallback !== undefined ? fallback : key;
  }

  function setLang(lang) {
    try { localStorage.setItem(KEY, lang); } catch (e) { /* private mode */ }
    apply(document);
    window.dispatchEvent(new CustomEvent("langchange", { detail: { lang: lang } }));
  }

  window.NAPI18N = {
    t: t, apply: apply, setLang: setLang, current: current,
    languages: [{ code: "en", label: "EN" }, { code: "zh", label: "中文" }]
  };
  window.t = t;

  document.addEventListener("DOMContentLoaded", function () { apply(document); });
})();
