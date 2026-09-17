# Jev 的 400 多个社区实验，揭示了 AI 应用的另一种架构

> 当 AI 不再先写一段话，而是直接回答“选哪个、到什么程度、是否成立”，软件应该怎样重新组织自己的决策过程？Jev 早期生态的价值，正在于把这个问题变成了一批可以阅读、运行和检验的项目。

2026 年 9 月 15 日，TypeSafe AI 开放了 System One 模型 Jev 的早期访问。两天后，社区维护的 [awesome-jev](https://github.com/hellogumbo/awesome-jev) 已经列出 409 个条目，覆盖游戏、模型路由、浏览器自动化、内容审核、排序、机器人仿真，以及各种本地复现实验。

这个数字需要准确理解：目录里包含 SDK、文章、封装、实验和演示，不能把它读成“409 个成熟产品”。但这些项目集中探索同一种接口，本身就是一个值得关注的信号：开发者正在尝试把模型接进软件运行时，让它承担大量细小、频繁、需要语义理解的判断。

过去，我们常问：“大模型能不能独立完成这个任务？”Jev 把另一个问题推到了前台：“这个任务里，哪些判断值得交给模型，其他部分又应该由谁负责？”

本文沿着实时游戏、Agent 路由与护栏、计算机使用、分类评分，以及具身与其他实验五条线索，梳理这个早期生态，并讨论它对 AI Native 工作流的实际意义。

文中的项目状态与数字以 **2026 年 9 月 17 日**公开资料为截点。性能数据属于官方或项目作者报告，本文没有重新运行这些基准；架构建议与企业场景示例则是基于这些资料的分析，不代表已经上线的客户案例。

## 一、先弄清楚：Jev 给软件增加了什么

TypeSafe 把 Jev 定位为快速输出类型化决策的模型。官方介绍的训练方法是 RLCD，即 Reinforcement Learning for Calibrated Decisions，并强调并行输出多个判断、概率分布与不确定性。System One 这个名字借用了“快思考”的概念，但不能因此推断它复制了人脑的工作方式。有关架构和训练效果的描述，目前主要来自厂商披露。[官方发布文章](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

对应用开发者而言，更有用的是三个具体接口：

| 原语 | 适合回答的问题 | 软件获得什么 |
| --- | --- | --- |
| Choice | 这几个候选项中应该选哪一个？ | 选项、选项概率分布和 confidence |
| Score | 按事先定义的有序等级，这件事处于什么程度？ | 分数、等级相关信息、概率分布和 confidence |
| Noul | 这个陈述有多大可能成立？ | 一个 0 到 1 的值 |

这里的 Noul 不是已经替你做完业务决策的布尔值。模型返回判断，程序决定什么阈值触发什么动作。同一请求可以包含多道问题，但这些问题独立读取同一份状态；第二道题不会自动读到第一道题刚生成的答案。[原语文档](https://docs.typesafe.ai/primitives)

于是，一次“理解客服工单”的调用，可以同时产出所属队列、用户是否要求退款、是否存在紧迫性、情绪程度等信号。程序再把这些信号组合成分派、升级、继续核验或人工处理的动作。

**真正发生变化的是职责划分：模型承担不容易用规则表达的判断，软件保留执行结构。**

这种模式并非只有 Jev 才能实现。普通 LLM 的结构化输出、专用分类器、规则系统都能参与类似流程。Jev 的差异化主张，是把这一类判断作为模型和服务本身的优化目标。它能否产生实际优势，最终仍要比较任务质量、端到端延迟和总体成本。

## 二、封闭的选项，不等于提前写好所有情况

Jev 最容易引发的疑问是：如果必须枚举候选动作，那是不是只有完全可预测的任务才适合它？国际象棋、浏览器操作这样的复杂环境，又怎么提前列出所有可能性？

关键在于，**每次调用需要一个明确的候选集合，但整个任务不需要一份永远不变的动作清单。**

以国际象棋为例。程序可以在每一回合根据当前棋盘生成合法走法，再把这一步的候选动作交给模型。下一回合棋盘变了，候选集也重新生成。这里枚举的是当前状态下允许采取的下一步，不是从开局到终局的整棵博弈树。

不过，选出合法走法只解决了合法性，并不自动解决棋力。局面搜索、长期规划和胜率评估仍是另一组问题；“能下棋”和“下得强”需要不同证据。

浏览器也是如此。一页中当前可见、可操作的元素构成一批候选项；点击之后重新观察，新页面会产生新的候选项。变化的是运行时的动作集合，稳定的是候选项的格式和执行规则。

选项描述也不必写成穷尽所有条件的规则。它首先要说明这个选项意味着什么，与其他选项有什么区别。例如，一次运维工单分派请求可以写成下面这样。以下为教学示例，展示请求结构，未实际调用服务：

```json
{
  "model": "jev-latest",
  "state": {
    "message": "升级后部分查询超时，暂时没有发现数据丢失，希望尽快协助定位。",
    "service_status": "仍可访问，但存在间歇性错误"
  },
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "根据工单内容，选择最合适的初始处理队列；证据不足时选择人工分诊。",
      "criteria": {
        "incident": "正在影响线上可用性或性能的问题，需要值班团队及时排查。",
        "consulting": "使用方法、配置建议或方案咨询，没有已知线上影响。",
        "manual_triage": "信息不足、类别冲突，或现有队列无法明确承接。"
      }
    }
  }
}
```

`instructions` 规定这一轮要判断什么，`criteria` 给出候选项及其含义。这样既不要求人写完所有匹配条件，也不会让模型自由创造一个执行器无法识别的新队列。[Choice 文档](https://docs.typesafe.ai/primitives/choice)

对于动作特别多的场景，还要处理候选集规模。当前 Choice 文档给出的上限是 255 个选项；超过这一规模，可以分层选择或先评分再筛选。筛选本身会引入风险：正确动作如果没有进入候选集，后面的决策器再强也选不到它。

因此，设计此类系统的核心工作之一，是把开放环境转成一个足够完整、当前有效、可执行的候选空间。

## 三、实时游戏：最直观的，是模型与控制器的分工

游戏成为 Jev 的第一批热门演示，很容易理解。动作频繁、反馈及时、结果可见，延迟也能被直接感受到。

官方 Doom 演示报告约每秒 10 次查询、每小时约 7 美元；发布文章给出的服务响应时间范围为约 70—500 毫秒。这些数字属于特定演示和测量条件，不能直接视为所有应用的速度与价格保证。尤其需要明确：官方 Doom 输入的是文本和结构化游戏状态，不是游戏画面的像素。[官方 Doom 说明](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

社区的 [lukaske/jev-doom-agent](https://github.com/lukaske/jev-doom-agent) 把这种分工做得更具体：浏览器中的 Chocolate Doom WebAssembly 运行游戏，模型参与战术动作选择，外围代码承担控制落地。值得观察的并不只是“模型按了哪个键”，而是游戏状态如何被整理成对选择有用的信息。

从工程角度看，“靠近补给”“保持距离”“转向目标”这样的战术动作，通常比每帧直接决定一组按键更容易形成稳定接口。动作的持续时间、取消条件和执行过程由控制器处理，模型在需要重新判断时介入。这是可以迁移到其他领域的设计方法，并不意味着所有游戏项目都采用了完全相同的实现。

俄罗斯方块则展示了另一种划分。在初期社区的 Tetris 实验中，一类常见做法是由程序枚举合法落点，把每个落点的结果作为候选方案，让 Jev 选择 placement。旋转、碰撞检测和下落执行仍由游戏逻辑完成。类似思路也出现在 2048、五子棋、马里奥和其他棋盘或模拟器项目中。

这些实验共同提醒我们：**环境负责规则，状态构造负责证据，模型负责选择，控制器负责动作。** 把四者分开之后，我们才能判断失败来自哪里。是状态遗漏了敌人？合法动作列表有错误？模型选错？还是执行器没有完成它所声称的动作？

可以进一步浏览 [KyleKreuter/jev2048](https://github.com/KyleKreuter/jev2048)、[mizchi/jev-gomoku](https://github.com/mizchi/jev-gomoku)、[fhshaik/typesafe-mario](https://github.com/fhshaik/typesafe-mario) 和 [shantanugoel/mario-jev](https://github.com/shantanugoel/mario-jev)。它们适合作为不同状态表示和动作粒度的观察样本，而不是仅按演示的流畅程度比较模型能力。

## 四、Agent 路由与护栏：把昂贵生成前后的判断独立出来

对于企业应用，游戏演示之后更值得关注的是 Agent 基础设施。

一个执行任务的 Agent，除了写代码、写文案或生成计划，还要不断判断：这一轮需要什么模型？应该加载哪个技能？返回的工具结果是否相关？当前操作是否超出任务范围？失败之后应该重试、升级还是停止？

这些判断通常比完整任务小，却可能发生得更多。把它们全部交给同一个昂贵的生成模型，会让主模型在大量控制事务上反复消耗时间和上下文。

### 模型路由：省钱需要连同失败成本一起计算

[0xNatoshi/jev-codex-router](https://github.com/0xNatoshi/jev-codex-router) 以每轮选择模型、思考深度和速度模式为目标。作者报告，在 7 天、237 个真实轮次的回放上，相对全程使用前沿模型的基线，估算成本节省约 60%。这是特定回放和成本口径下的结果，不能直接解释为任何真实任务都能在同等完成质量下节省 60%。

[gargpratyush/jev-router](https://github.com/gargpratyush/jev-router) 与 [prismhq/jev-router](https://github.com/prismhq/jev-router) 也探索了把任务分给不同后端模型的方向。

这种路由是否划算，需要看完整账单：判断器的成本、被选模型的成本、路由错误导致的返工，以及升级到更强模型的额外开销。如果便宜模型让同一个问题多试三轮，单次调用便宜并不等于任务便宜。

一个更有解释力的指标是“达到验收标准的每个任务成本”。与之一起报告的，应当是完成率、尾部延迟、升级比例和人工介入率。

### Skill 与 Tool 路由：先匹配，再检查能不能用

[TheoOliveira/pi-jev](https://github.com/TheoOliveira/pi-jev) 和 [GodsBoy/jev-agent-skill-router](https://github.com/GodsBoy/jev-agent-skill-router) 把判断层用于工具或技能选择。后者报告过合成数据上的 94.4% 路由准确率，对比词法基线的 70.8%。这说明值得进一步评估，但合成集成绩并不等于真实组织中复杂请求的覆盖率。[项目说明](https://github.com/GodsBoy/jev-agent-skill-router)

对组织级工作流而言，技能目录需要同时描述“适合什么任务”和“具备什么执行条件”。一个技能在语义上很匹配，仍可能因为缺少数据、没有权限、依赖不可用或当前状态不允许而不能执行。

因此，路由结果只能是进入后续检查的建议。配置和运行时需要共同保证：选中的技能存在，输入满足契约，权限有效，失败有明确去处。

### 护栏：增加一层判断，但保留确定性的权限边界

[caiovicentino/jev-shield](https://github.com/caiovicentino/jev-shield) 将 Jev 放在 MCP 工具调用、工具结果和工具描述的检查位置；[0xArx/jevegis](https://github.com/0xArx/jevegis) 探索注入、越狱、泄漏和不安全内容检测；[DevMortimer/pi-warden](https://github.com/DevMortimer/pi-warden) 则关注 Agent 执行中的行为监督。

这类产品的吸引力是，在每次动作发生前后增加语义检查成为一种可以尝试的工程选择。例如，一条命令看起来是导出报表，但目标地址与用户任务不相关，判断层可能帮助发现这种不一致。

不过，概率判断不能替代身份认证、目录隔离、授权策略或沙箱。模型认为“安全”，并不会让一个本来没有权限的操作获得权限。反过来，命令本身合法，也不代表它符合用户此刻的意图。

[AbdelStark/bicameral](https://github.com/AbdelStark/bicameral) 的职责拆分很有参考价值：生成模型继续写代码，Jev 返回判断信号，确定性的策略代码把信号转成放行、确认、阻止、告警或引导。项目也明确说明，它本身不是沙箱。

### 上下文筛选：减少占用，也要允许找回来

[GhalebDweikat/winnow](https://github.com/GhalebDweikat/winnow) 处理的是另一个容易被忽略的问题：工具返回的内容，是否都值得进入主模型上下文？

它将较大的工具结果拆成块，让判断器评估相关性。对确信不相关的部分，缓存原文，用摘要和可恢复的引用替代；不确定的内容保留，错误信息也有保留规则。摘要由另一个模型承担，而不是让 Jev 生成正文。

因此，它更接近“进入上下文前的可恢复筛选”，与把整段历史重新总结的 compaction 有区别。这里值得借鉴的是恢复机制：过滤器会误判，而主任务可能在后续阶段才需要原先不相关的证据。上下文优化不能只计算省掉多少 token，还要计算关键证据被隐藏后，系统能否及时取回。

## 五、计算机使用：把界面变成动态动作目录

浏览器和桌面自动化进一步展示了这种架构的边界。

一个完整的计算机使用系统至少要解决三件事：观察界面，决定动作，可靠执行。Jev 可以承担其中的判断，但不会因此自动获得视觉感知、鼠标控制或操作系统权限。

[Cua](https://github.com/trycua/cua) 的 Driver 提供跨 macOS、Windows 和 Linux 的观察与操作能力。将这样的执行基础设施与决策模型组合时，应用仍要构造候选动作，把选择结果映射成驱动器能够执行的操作。

[browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) 是更具体的案例：每次观察产生带编号的元素表；Jev 选择操作和对应目标；需要输入自由文本时，再调用一个小型 LLM。操作类型和多个可能用到的目标问题可以在同一轮评估，程序只使用与最终操作对应的答案。

作者展示的 Google Flights 查询约耗时 7.1 秒，但计时从初次页面观察之后开始，而且是一个特定航班查询任务。仓库也说明，这不是通用可靠性基准；它查询并验证航班结果，不负责订票。不能把它写成“几秒内完成所有网站任务”，也不应把它解释成 Jev 独立生成了所有内容。[演示与测量边界](https://github.com/browser-use/jev-ultrafast)

这种设计带来的控制优势很直观：执行器接受的是已观察到的目标引用，而不是模型临时编造的选择器或脚本。但即使编号有效，页面也可能已经变化，按钮可能被遮挡，表单内容可能被其他动作修改。

因此，在模型作出选择之后、真正点击之前，还需要重新检查目标和状态；动作之后，再确认目标是否实现。模型选择 `DONE` 只能表示它认为任务结束，不能替代完成条件的验证。

这一点同样适用于桌面端的 [paulsmith/computer_use](https://github.com/paulsmith/computer_use)、OCR 路线的 [awlevin/typesafe-computer-use](https://github.com/awlevin/typesafe-computer-use)，以及围绕现有浏览器工具构建的 [vlad-terin/jev-browser](https://github.com/vlad-terin/jev-browser) 和 [vinilana/jev-browser](https://github.com/vinilana/jev-browser)。它们探索的共同问题是：怎样把感知结果整理成可选择、可执行、可核验的动作。

## 六、分类、评分与排序：最不炫目，也最容易定义验收条件

对企业软件来说，Jev 最直接的切入点可能是工单分类、文档打标、内容筛选、候选排序和多维评分。

这类场景的优势不在于技术看起来新，而在于可以明确规定输入、输出和验收标准。工单有没有分错队列？紧急问题漏掉了多少？排序是否帮助用户更快找到目标？这些都能用真实业务样本检验。

[jomatsu/zod-jev](https://github.com/jomatsu/zod-jev) 把两个层次放在一起：Zod 检查数据形状，Jev 检查语义。一个字段是字符串，可以由类型验证确定；一段说明是否含敏感个人信息，则需要另一类判断。两者组合后，语义结果仍应保持其概率性质，不能因为它出现在验证器里，就被当作绝对正确的事实。

[jkudish/jev-mcp](https://github.com/jkudish/jev-mcp) 把筛选、验证、查找和评估包装成 MCP 工具。它的候选语义排序展示了一条不以 embedding 相似度为最终判断标准的路径。不过，这不意味着可以跳过大规模检索：当候选数量和总文本量很大时，仍需先缩小范围，再做精细判断。

### 多维信号，通常比一句“好不好”更有用

假设我们要为用户排序酒店。直接问“哪家最好”，把设施、价格、位置、证据质量和个人偏好揉成了一个难以检查的答案。

更容易治理的方案，是分别评估与目标有关的维度：遮光条件、夜间噪声、网络可靠性、交通便利程度，以及证据是否充分。用户偏好决定权重，程序根据明确规则计算综合排序。

这不是对酒店事实的自动保证。评论中没有提到网速，不应被静默转换成“网速很好”或“网速很差”；信息不足需要作为独立状态保留下来。事实缺失、评价不确定和用户偏好，是三个不同问题。

类似分解也适用于内容审核、线索分派和需求优先级：先让判断层产出几个具有明确含义的信号，再由可版本化的策略决定如何组合。TypeSafe 的 [Patterns](https://docs.typesafe.ai/patterns) 也将组合评分和基于置信度的路由列为基本模式。

### 钓鱼邮件实验：一个数字背后可能是不同系统

[anisselbd/jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench) 的 2,000 封邮件实验尤其值得仔细读。初始结果中，Jev 的单点 verdict 准确率为 62.6%，Haiku 为 81.3%；把多个信号组合起来后，结果显著提高。

作者 9 月 17 日补充的留出集对照进一步显示：Jev 单信号规则为 89.4%，正则规则基线为 91.8%；Jev 五个信号加回归为 95.0%，同样分解的 Haiku 加回归为 93.2%，后两者的准确率差异未达到该实验采用的统计显著性标准。数据集本身也容易被规则分开。[基准及补充对照](https://github.com/anisselbd/jev-phishing-bench)

因此，不能只引用“Jev 达到 95%”。那是模型信号与下游分类逻辑组成的系统结果，也不能把它与另一个模型未分解问题的成绩直接比较。

这个实验更有价值的启发是：**评估对象应该是完整决策管线，同时给规则基线和其他模型公平的任务分解机会。**

## 七、具身、驾驶与其他实验：快判断要接在合适的时间尺度上

[RomanSlack/jev-drone](https://github.com/RomanSlack/jev-drone) 在 MuJoCo 无人机仿真中展示了清楚的分层：飞行控制约 500Hz，安全与引导约 50Hz，感知约 15Hz，Jev 约 2.5Hz 提供战术判断。这里的感知由深度和分割信息处理产生，Jev 读取整理后的状态；不能把它描述为 Jev 直接看图驾驶。

这种分层的意义在于，转子控制不能等待一次远程模型调用。模型可以建议绕行、爬升或重新寻找目标，但高频控制和安全反射保留否决权。作者也披露了单次成功演示和更早实验表现不佳的情况，不能据此推断真实无人机上的普遍收益。[项目结构与限制](https://github.com/RomanSlack/jev-drone)

这背后的工程原则可以推广：**不同时间尺度的问题，交给不同的处理机制。** 有确定算法的问题交给算法，必须及时响应的环节保留本地控制，需要语义判断的环节再调用模型。

[TarunTomar122/jev-askable-arm](https://github.com/TarunTomar122/jev-askable-arm) 的机械臂仿真、[juancamiloqhz/roverlab](https://github.com/juancamiloqhz/roverlab) 的行星车沙盒，以及 [lbotinelly/jev-little-airways](https://github.com/lbotinelly/jev-little-airways) 的航空调度实验，都可沿着这个角度观察：模型究竟决定哪个层级的动作，动作原语由谁实现，失败由谁处理。

另一些实验探索生成模型与判断模型的内容协作。例如 [phureewat29/got-jev](https://github.com/phureewat29/got-jev) 将故事生成与地点、情绪、危险程度等判断组合。可迁移的想法是，创作内容和检查内容可以由不同组件承担，而不是要求一个模型同时完成所有职责。

至于交易和预测市场演示，应把“能输出买入或等待的选项”与“有可信收益证据”严格分开。一个明确的输出类型不会自动带来预测能力。本文不把这类早期实验当作成熟交易系统的依据。

## 八、本地“仿 Jev”：可比较的首先是方法，不是品牌

生态中还有一条很有意思的支线：开发者尝试用其他模型实现相近的决策接口。

[daseinlabs/open-jev](https://github.com/daseinlabs/open-jev) 探索本地模型的候选评分；[kikoncuo/jevfire](https://github.com/kikoncuo/jevfire)、[vinnylarouge/jevlike](https://github.com/vinnylarouge/jevlike) 和 [rorshopping/jev-on-a-laptop](https://github.com/rorshopping/jev-on-a-laptop) 则提供了不同的本地或开源实验方向。

这里需要避免一个概念跳跃：有相似 API，或者也能对选项评分，并不意味着复现了 TypeSafe 的训练方法、概率校准效果或性能。同样，另一个项目能从图像选择动作，也不能证明官方 Jev 已经具备相同输入能力。

这些项目的价值是让架构讨论摆脱单一供应商。应用可以明确自己的决策契约，再比较托管 Jev、普通 LLM、专用小模型与规则系统。TypeSafe 自己也提供了 [system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python)，用于以其他模型承接相近接口、开展比较。

最终应该保留的是可测试的任务定义、数据和执行边界。模型服务可以更换，工作流不必因此重新发明一遍。

## 九、从演示走向产品，最容易混淆的四件事

**第一，类型正确不等于判断正确。** Choice 可以保证输出来自候选集，但候选集中的某一项仍可能是错误选择。Score 在范围内，也不说明它准确反映了事实。类型约束缩小了一类错误空间，并没有消除语义错误。

**第二，confidence 不等于“本次一定正确的概率”。** Choice 文档说明，confidence 是根据选项概率分布的集中程度计算的，不能直接与最大选项概率混用。即便一个系统具有良好的总体校准，也仍需验证它在当前语言、任务分布和版本上的表现。[Choice 返回值说明](https://docs.typesafe.ai/primitives/choice)

对团队来说，可行的做法是在留出样本中观察：当某个分数区间允许自动执行时，覆盖了多少请求，又发生了多少错误。阈值应由实际误差和业务代价决定，不应因为 0.8 或 0.9 看起来足够高，就直接采用。

**第三，一次请求中并行提问，不等于自动执行一条推理链。** 如果后续判断真的需要根据前一步结果查询新数据，就仍需另一次调用。独立信号可以批量提问，有真实数据依赖的步骤则必须保留顺序。[多问题调用说明](https://docs.typesafe.ai/primitives)

**第四，单次推理快，不等于任务完成快。** 页面加载、工具执行、数据查询、重试和人工接管都可能成为主要耗时。优化模型调用之后，瓶颈很可能转移到观察与执行环节。

还应把计数、算术、网格规则等精确计算留给确定性程序。对语义判断模型而言，给它一个长而杂乱的状态，再期待它自己补齐所有结构，并不是稳妥的默认方案。状态需要提供决策所需证据，同时尽量去掉无关内容；“精简”也不应删掉足以改变判断的关键信息。

## 十、对 AI Native 工作流，真正值得标准化的是什么

如果一个组织希望各个角色都通过 Agent 工作流完成任务，那么 Jev 这类模型最有价值的位置，可能是多个工作流共享的判断层。

例如，以下是可以进一步设计和验证的企业场景，而非本文声称已经被这些项目证明的生产用法：

| 角色或流程 | 适合拆出的判断 | 仍由程序或人员承担的责任 |
| --- | --- | --- |
| 客户支持 | 问题分类、紧迫性、是否需要补充材料 | 权限、退款政策、执行与回执 |
| 研发 | 任务路由、变更风险信号、是否反复失败 | 测试、代码权限、合并与回滚 |
| 运维 | 告警关联、升级建议、下一项检查 | 精确指标计算、操作授权、恢复验证 |
| 内容团队 | 品牌风格、敏感表述、是否偏离主题 | 内容生成、事实核查、发布决定 |
| 数据治理 | 文档类别、敏感信息线索、证据相关性 | 访问控制、保留策略、审计与处置 |

要让这些工作流能够配置、复用和迁移，光统一提示词远远不够。更值得标准化的是一份“决策契约”：

- 状态来自哪里，哪些字段必须存在，证据是否过期；
- 当前有哪些候选动作，分别意味着什么；
- 输出如何解释，什么情况需要保留不确定性；
- 哪些规则可以否决模型建议；
- 如何执行、验证、重试、回滚和转人工；
- 使用哪个版本的模型、问题定义、阈值与评估集。

在实现上，可以把稳定的职责和政策放进 YAML 等配置，把实时候选动作、权限检查和执行状态放在运行时。配置说明“如何判断和控制”，运行时确保这些约定真的被执行。

例如，配置可以描述一个工具选择问题及其低置信度处理策略；运行时则必须根据当前可用工具、用户授权和输入完整性，构造这次真正可选的列表。否则，配置里写着一个工具，并不代表它此刻存在或有权执行。

模型升级后，团队首先重跑决策评估、检查概率分布和阈值表现，而不是只看一个总体基准分数。这样才能把模型能力变化与工作流行为变化联系起来。

## 十一、怎样选择第一个值得落地的场景

对于准备采用这一模式的团队，我更建议从一个高频、边界明确、失败可观测的判断切入，例如工单路由或低风险内容分流。这是架构上的建议，是否采用 Jev 仍应由比较结果决定。

首先，把原来的一项复杂任务拆成几个可独立检查的小问题。不要一上来就问“下一步应该做什么最好”，而应先弄清楚当前到底缺少哪个判断。

接着，准备包含正常、边缘、信息不足和冲突情况的业务样本，建立规则、现有分类器或普通 LLM 基线。对照双方应获得相同证据和相近的任务分解，避免把架构差异误记为模型差异。

然后让新判断层在后台给出建议，暂不影响真实执行。记录它会改变哪些决定、节省多少调用、引入多少误判，以及低置信度是否真的对应更高错误率。

最后才逐步开放自动执行，并同时观察任务完成率、错误代价、端到端延迟和人工接管比例。允许模型参与多少，应由这组数据决定。

如果规则系统已经准确、快速而且维护成本很低，就没有必要为了使用新模型增加一层依赖。相反，当规则难以表达、任务频率很高、候选动作可定义、失败也能够被检查时，这类判断层才更可能产生价值。

## 十二、Jev 生态真正值得关注的变化

早期项目数量的增长，还不足以证明一种模型已经成为基础设施。但这批实验提供了一种清楚的应用设计方向：把生成、判断、规则、执行和验证拆开，让每个部分接受适合自己的约束和评估。

游戏展示动作空间的组织方式；路由器展示判断如何影响计算成本；护栏展示语义信号与权限策略的关系；浏览器实验展示动态候选项与执行验证；分类和仿真项目则提醒我们，状态设计与任务分解往往和模型本身一样重要。

对产品经理而言，工作重点会更多落在“系统要判断什么、有哪些可接受结果、失败后怎样继续”。对工程师而言，需要构建可观测、可替换、可回放的决策接口。对组织而言，则需要把业务偏好、风险代价和权限边界变成能够持续维护的策略。

Jev 提供了一个观察窗口：当一次语义判断能够以更小的单位嵌入软件，AI 应用的创新空间就不只在聊天框，也在那些过去只能依赖僵硬规则，或者每次都要等待人工判断的流程节点上。

真正值得长期保留的能力，是把这些节点设计清楚，并证明它们在真实任务中工作得更好。

## 项目索引与继续阅读

以下索引保留更多早期探索方向，便于继续阅读。列入索引不表示本文已逐一运行、审计或验证其性能；文中展开的数字以相应作者说明为准。同名项目较多，应按完整仓库地址辨认。

| 方向 | 项目入口 | 观察重点 |
| --- | --- | --- |
| 社区总目录 | [awesome-jev](https://github.com/hellogumbo/awesome-jev)、[awesomejev.com](https://awesomejev.com) | 生态发现入口；条目数量不代表生产成熟度 |
| 官方资源 | [文档](https://docs.typesafe.ai)、[Playground](https://console.typesafe.ai/playground)、[agent skills](https://github.com/typesafe-ai/skills) | 接口、问题设计与实验 |
| 游戏 | [jev2048](https://github.com/KyleKreuter/jev2048)、[jev-gomoku](https://github.com/mizchi/jev-gomoku)、[cyber-breach-jev](https://github.com/rchovatiya88/cyber-breach-jev) | 状态表达、动作粒度与反馈循环 |
| 游戏与 NPC 实验 | [wondertwins/jev-benchmark](https://github.com/wondertwins/jev-benchmark) | 棋类决策和交互判断的不同难点 |
| 模型路由 | [jev-codex-router](https://github.com/0xNatoshi/jev-codex-router)、[prismhq/jev-router](https://github.com/prismhq/jev-router) | 路由收益与端到端质量 |
| 技能选择 | [pi-jev](https://github.com/TheoOliveira/pi-jev)、[jev-agent-skill-router](https://github.com/GodsBoy/jev-agent-skill-router) | 候选描述、召回和回退 |
| 护栏与监督 | [jevegis](https://github.com/0xArx/jevegis)、[jev-shield](https://github.com/caiovicentino/jev-shield)、[pi-warden](https://github.com/DevMortimer/pi-warden) | 判断信号、误报漏报与策略执行 |
| 上下文筛选 | [winnow](https://github.com/GhalebDweikat/winnow) | 相关性判断、证据保留与恢复 |
| 审查与执行控制 | [jev-review](https://github.com/devagrawal09/jev-review)、[diffjury](https://github.com/raihankhan-rk/diffjury)、[bicameral](https://github.com/AbdelStark/bicameral) | 风险分流、行为监督与确定性策略 |
| 浏览器 | [jev-ultrafast](https://github.com/browser-use/jev-ultrafast)、[vinilana/jev-browser](https://github.com/vinilana/jev-browser)、[Ying-Kai-Liao/jev-browser](https://github.com/Ying-Kai-Liao/jev-browser) | 动态元素表、动作执行与结果检查 |
| 桌面与测试 | [computer_use](https://github.com/paulsmith/computer_use)、[otto](https://github.com/NobleSpartan6/otto)、[JevTest](https://github.com/CorieW/JevTest) | 可访问性、平台差异与可回放证据 |
| 语义验证与 MCP | [zod-jev](https://github.com/jomatsu/zod-jev)、[jev-mcp](https://github.com/jkudish/jev-mcp)、[typesafe-mcp](https://github.com/itsmostafa/typesafe-mcp) | 数据形状、语义判断和工具包装 |
| 评估 | [jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench) | 公平基线、任务分解、校准与留出验证 |
| 仿真与驾驶 | [jev-drone](https://github.com/RomanSlack/jev-drone)、[typesafe-playground](https://github.com/kavehmz/typesafe-playground)、[jev-behavior-study](https://github.com/RINNECODER/jev-behavior-study) | 战术判断与高频控制的分层 |
| 内容与语言实验 | [got-jev](https://github.com/phureewat29/got-jev)、[jev-chat](https://github.com/adhyaay-karnwal/jev-chat)、[jev-lm](https://github.com/y0usaf/jev-lm) | 判断模型与生成任务的边界 |
| 本地探索 | [open-jev](https://github.com/daseinlabs/open-jev)、[jevfire](https://github.com/kikoncuo/jevfire)、[jevlike](https://github.com/vinnylarouge/jevlike)、[jev-on-a-laptop](https://github.com/rorshopping/jev-on-a-laptop) | 类似接口与实际模型能力的区别 |

跟进这些项目时，优先看状态构造、候选动作生成、执行器、失败轨迹和评估条件。演示告诉我们某件事发生过，这些材料才帮助我们判断它为什么发生，以及能否在自己的系统里重复发生。
