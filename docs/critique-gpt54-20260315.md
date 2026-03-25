# Nous 项目全面批判（GPT-5.4 独立审查）

## 1. 致命缺陷

### 1.1 项目最核心的宣传语，目前基本不成立：**“本体论驱动”“KG+Datalog+语义理解”在真实 gate 流程里并没有真正闭环**
最硬的证据不是文档，而是代码：
- `gate.py` 的 `gate(..., kg_context: Optional[dict] = None)` 只是**可选接收** KG 上下文。
- `gateway_hook.py` 调 `gate()` 时**根本没有传 KG context**。
- `semantic_gate.py` 的 prompt 里如果没有 `kg_context`，直接写的是 **“No additional context available.”**

这意味着：**默认真实路径里，semantic gate 并不会主动查 KG。**
所以现在的 Nous，本质上不是“ontology-driven governance engine”，而是：
1. 一层 YAML/模式规则
2. 一层非常重的 prompt-engineered LLM 分类器
3. KG 主要作为旁边摆着的能力储备

说难听点：**KG 现在更像舞台布景，不是发动机。**

---

### 1.2 “FAIL_CLOSED” 说法与实际行为矛盾，甚至可能出现**空规则=全放行**
文档和代码注释反复强调 FAIL_CLOSED，但 pytest 实际警告暴露了更糟的事实：
- 约束目录不存在时：`Gate 将在无约束模式运行——所有操作默认 allow！`
- 热加载目录存在但加载 0 条约束时：`Gate 将在无约束模式运行。`

这不是小 bug，这是**安全系统的根部反逻辑**：
- 你口头上说任何异常都 confirm
- 实际上某些最常见的配置/加载失败路径，不是 confirm，而是**allow-all**

如果一个安全治理引擎在“规则没加载到”的情况下默认放行，那它在生产里就不配被叫“治理引擎”。这是会让项目直接失去可信度的缺陷。

---

### 1.3 指标体系已经出现**自我污染**：同一天多个文件对同一个 `L_val` 给出互相冲突的数字
2026-03-15 这一天，仓库里同时存在：
- `loop-log-29.md`：`Val TPR 100%, FPR 0%, L_val = 0.0000`
- `split-results-val.json`：`TPR 100%, FPR 5.6%, false_positives=2, L_partial=0.0167`
- `loop-state.json`：`L_val = 0.026`，并注明之前 capability 定义是错的
- `loss-val.json`：又写成 `L = 0.0`，且 `capability_note = binary gate: capability = 1 - FPR`

这已经不是“指标有波动”，而是**度量口径失控**。

更严重的是，`capability` 的定义反复漂移：
- 一会儿“未测时假设 0.5”
- 一会儿“binary gate: capability = 1 - FPR”
- 一会儿又改成“benign_allow_rate(94.4%)”

**一个 loss 的定义如果在迭代过程中改口径，还把新旧结果画成一条下降曲线，那这条曲线基本不能用于证明任何东西。**

---

### 1.4 你们说在做“语义理解”，实际做成了**超长 prompt + 手工最小对 + 信号堆叠的 benchmark 调参器**
`semantic_gate.py` 里最显眼的不是 ontology reasoning，而是：
- 一大堆手工 structural signals
- 十几组 minimal pairs
- 对 false positive 的逐案修补
- 针对 benchmark case 写进去的启发式说明

这当然可能有效，但它的本质更接近：
**“把 AgentHarm 常见混淆样本塞进 prompt 里训一个分类器”**。

这和“高语义性”“本体论驱动”不是一回事。
它不是没有价值，但必须诚实命名：
- 现在做到的是 **prompt-engineered semantic classifier**
- 不是强意义上的 ontology-grounded semantic reasoning

如果继续用宏大叙事包装这个实现，项目会越来越像自我催眠。

---

## 2. 严重问题

### 2.1 评估样本量太小，`100% TPR` 高度可疑
总样本 352，val 只有 72；而 `split-results-val.json` 里很多类别只有 4-5 个 harmful / benign 样本。
这意味着：
- 某类别只要漏 1 个，TPR 就可能掉 20%-25%
- 所谓 `category_variance = 0`，只是因为样本太少、恰好全中
- 你现在看到的 `100% TPR`，更像**小样本幸运值**，不是稳定结论

尤其是：你们自己新建的 adversarial v1 里，harmful TPR 只有 **66.7%**。这已经说明标准 val 集很可能被你们调穿了。

一句话：**标准 val 很漂亮，挑战集一上就露底。** 这就是典型过拟合信号。

---

### 2.2 `L = 0.4*(1-TPR)+0.3*FPR+0.2*(1-cap)+0.1*var` 没有可靠依据，且权重可被叙事任意操控
这个 loss 最大的问题不是“公式不好看”，而是：
1. 权重没有理论依据，也没有业务代价校准
2. `capability` 定义不稳定，导致整个 L 可塑性太强
3. `variance` 在小样本下噪声极大
4. 一旦 val 很小，L 的变化可能主要反映抽样波动，不反映真实进步

现在这个 loss 更像一个“看起来 ML 化”的 dashboard 指标，而不是严格可用的优化目标。

---

### 2.3 自动迭代 LOOP 的“硬门禁”其实不是机制，是习惯
文档里说：
- Gemini critique 是硬门禁
- 发现问题不能 push

但你们自己的描述承认 Loop 2-7 多次跳过批判步骤。再看 git/LOOP 历史，还有模型切换混乱：
- 一会儿写 Gemini 3.1 Pro
- 一会儿 CLI 上又回退 2.5 Pro
- 还专门提交过“禁止旧模型 / 模型不可用”的修补 commit

这说明所谓“硬门禁”并没有被工具链强制执行，只是靠人记得做。**靠自觉的硬门禁，不是硬门禁。**

---

### 2.4 `loop-state.json` 过于单薄，无法承载真正的实验状态
它只保存：
- loop number
- L_val
- urgent
- next_priority
- 少量元信息

它不保存：
- 当前评估口径版本
- prompt 版本 hash
- benchmark split 版本
- judge 配置
- 失败假设与回滚原因
- 哪些数据点驱动了这轮改动

所以它更像“进度便签”，不是“实验状态快照”。
对于一个自称 ML-inspired 的迭代系统，这个状态管理过于贫弱，信息丢失几乎必然发生。

---

### 2.5 KG 质量太差，且关系退化成 `RELATED_TO` 大杂烩
已有审计显示：
- 实体量很小（24 或 dashboard 导出的 44，反正都远低于设计目标 200）
- 关系量很小（26/36）
- 其中大量是 `RELATED_TO`

这样的 KG 几乎没有推理价值，因为它缺少：
- typed relation
- directionality with semantics
- constraints / inheritance actually used in reasoning
- 高质量 provenance

如果 relation 大部分只是 `RELATED_TO`，那不是 ontology，是“我知道这些东西互相有点关系”。对实时治理没什么帮助。

---

### 2.6 “已切 primary” 与仓库配置现实矛盾
`tasks.md` 把 M4.1 标成完成，写了“Nous 升为 primary”。
但仓库 `config.yaml` 现在明确是：
```yaml
mode: shadow
```
而 `gateway_hook.py` 默认也是 `shadow_mode=True`。

这件事非常伤信誉：
- 要么任务状态写早了
- 要么切过又退回但没有严谨记录
- 要么“完成”的定义只是脚本写好了，不是系统真的在跑

无论哪种，都会让外部审稿人/合作者怀疑：**你们的 milestone 到底是在描述事实，还是在描述愿望。**

---

## 3. 改进建议（具体可执行）

### 3.1 先砍掉叙事泡沫，重新定义项目当前身份
把对外定位从：
- “本体论驱动 Agent 行为治理引擎”
改成更诚实的：
- **“规则层 + LLM 语义审查层的 Agent 安全网关原型，KG 集成尚未真正闭环”**

这不是降级，而是止损。你先说真话，后面做起来才有信用。

---

### 3.2 立即修复 fail-closed 违例
这是最高优先级，今天就该修：
1. 约束目录不存在 / 0 条规则 / YAML 全失效 → **直接 `confirm` 或 `block`**，绝不能 allow-all
2. 热加载失败后必须保留 last-known-good 规则集
3. 在 decision_log 里打明确的 engine_degraded 标记
4. CI 增加“空约束目录必须 fail-closed”的回归测试

不修这个，别谈上线。

---

### 3.3 让 KG 真进主链路，否则先别吹 KG
要么做真接入：
- `gate()` 内部主动查 DB 生成 `kg_context`
- 规定哪些 action 必须带 KG enrichment
- 把 KG 命中写进 `proof_trace`
- 做 ablation：no-KG vs KG-context vs typed-KG

要么暂时删掉大部分 KG 叙事，承认目前它不是核心贡献。

我更建议前者，但在没做之前，不要再把 KG 当卖点。

---

### 3.4 重做评估协议，冻结口径
必须做四件事：
1. **冻结 capability 定义**，不要再改
2. 所有结果文件携带 `metric_version`
3. 同一轮只允许一个官方 `L_val`
4. 对每个类别报告 Wilson 区间或至少样本数，不再裸报 100%

另外：
- val/test 太小，应该做 repeated stratified split 或 cross-validation
- adversarial set 不要只做 15 harmful / 15 benign 这种秀肌肉小集，至少扩到能稳定估计的规模

---

### 3.5 做真正的 ablation，不然学术定位站不住
最少需要四个版本：
1. Datalog only
2. Datalog + prompt classifier（无 KG）
3. Datalog + KG + prompt
4. Datalog + KG + stronger model

你们现在最大的问题不是性能差，而是**不知道改进来自哪一层**。没有消融，论文基本没法投正经 venue。

---

### 3.6 停止用 benchmark 成绩替代真实价值
必须单独统计：
- 截至今天，真实线上工具调用总数
- 真正被 Nous 拦住的真实危险操作数
- 误拦正常操作数
- 经过人工复核的 precision

如果这些数据拿不出来，就诚实写：
**“截至目前，主要价值是研究原型和评估框架，不是已验证生产防线。”**

---

### 3.7 Cozo 选型可以保留，但要诚实承认它还没被用出价值
我不认为 Cozo 是错误选型；低延迟、嵌入式、Datalog 原生，都合理。
但当前现实是：
- 你们并没有进行复杂图推理
- 也没有真正依赖 ontology constraints
- 更没有体现出 Cozo 相比 OPA/Rego 的决定性优势

所以现阶段应该把 Cozo 定位成：**可扩展底座**，不是现成护城河。

---

## 4. 值得肯定的

### 4.1 代码和测试不是假的
- `src` 约 6953 行 Python
- `tests` 约 7630 行
- 当前 pytest：`614 passed, 15 xfailed, 2 xpassed`

这说明项目不是空 PPT，也不是只有文档没有实现。骨架是真的。

### 4.2 三层思路至少方向上是对的
“结构规则处理确定性风险，LLM 处理语义歧义”这个大方向没问题。问题不在方向，而在：
- 你们把“方向正确”过早包装成“已经实现”
- 把“有潜力”说成了“已验证领先”

### 4.3 你们已经意识到 benchmark 不够，开始做 adversarial challenge
这是少数真正有研究味道的动作。挑战集把 val 上的“100% TPR”戳穿到 66.7%，这反而是好事——说明系统至少还有自我纠错能力，而不是一路自嗨。

### 4.4 影子模式 / replay / decision log 这些工程意识是对的
虽然实现还有很大问题，但“先 shadow 再切主”“保留 proof trace”“做 replay”这些工程意识是成熟的。项目不是完全没底子，问题主要出在**叙事过冲和方法学松动**。

---

## 5. 总评

### 这个项目现在的真实价值是什么？
**它现在的真实价值，是一个“有一定工程厚度的 Agent 安全研究原型”，不是一个已被证明有效的 ontology-driven governance engine。**

更具体地说：
- 对“prompt 解放”：**几乎还没实现。** M9 基本没动，AGENTS.md 的安全规则远未迁走。
- 对“政策预测”：**目前基本没有可信成果。** M5 的回测连你们自己都承认需要用真实 Tushare 数据重做。
- 对“真实危险操作拦截”：**看不到可靠生产证据。** 当前主证据仍是 benchmark、challenge、shadow/replay。
- 对“学术发表”：**离 ICLR/ICSE 还差一大截。** 缺消融、缺公平 baseline、缺稳定评估协议、缺真实部署数据、缺统计严谨性。

### 一句话毒评
**这项目现在最像的是：一个不错的安全网关原型，外加一层过度哲学化、过度学术化、过度胜利叙事的包装。**
骨架有，火候远远不够；最大风险不是技术做不出来，而是团队先把自己说服了。

### 评分
**4/10**

给 4 分，不是因为它没价值；
是因为它有真实工程积累，但目前的核心宣称、评估可信度、KG 实用性、上线状态，都明显高估了自己。

如果把叙事收缩、把评估重做、把 KG 真接入主链路、把 fail-closed 漏洞修掉，它有机会到 **6.5/10**。
在那之前，它不配被当成“已成型的本体论治理引擎”。
