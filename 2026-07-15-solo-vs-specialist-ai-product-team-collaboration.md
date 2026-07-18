# AI 让一个人能闭环，然后呢

最近有个反复被问到的问题：AI 工具已经能让一个人独立完成从 coding 到 design 到 deployment 的整个 loop，那还需要 designer、PM、QA 这些角色吗？

答案很简单：看你要的是 baseline 还是 judgment。

---

## Baseline 已经被 AI 抬高了

一个有经验的全栈工程师，配合 Cursor、Claude Code、v0，现在可以在几小时内做出一个看起来不错的产品。不是那种"能用就行"的 crud admin panel，而是真正 layout 整洁、component 协调、交互流畅的东西。

这背后的原因是 AI 正在抬高 non-designer 产出的 baseline quality。以前你自己搭界面，大概率间距不一、color scheme 混乱、hover state 缺失。现在 v0 生成的 component、Claude 调整的 spacing，至少保证了"整洁可用"这个底线。

所以对于 baseline quality 就够了的场景——internal tool、MVP 验证、一次性脚本、标准化 landing page——一个人闭环完全合理。引入 designer 的 marginal return 太低，沟通成本反而拖慢节奏。

更极端地说，一些规则明确的交付型工作，连人都不需要了。根据 OpenAPI spec 自动生成前端页面、根据 Figma design 自动生成代码、根据 PRD 自动生成 CRUD 后台。这些场景下问题已经不是几个人做，而是还需要不需要人。

## 那 specialist 的价值在哪

如果 baseline 被 AI 抬到了可接受水平，specialist 到底还能提供什么？

不是 implementation 能力。AI 写 code、出 prototype 的速度已经超过了大多数中级工程师和 designer。

真正的差距在两个地方：judgment 和 taste。

Judgment 是知道该做什么、不做什么。功能放 navigation bar 还是 sidebar？核心 user path 是什么，secondary path 应该弱化到什么程度？这个 interaction pattern 在目标用户群体中是否 familiar？这些是 product sense 的问题，不是技术问题。AI 可以给出建议，但它没有 user empathy，没有行业 context，没有"这个场景我见过"的直觉。

Taste 是对细节的敏感度。spacing 是否和谐、motion 是否自然、copy 是否准确、error state 是否体面。全栈工程师 + AI 做出来的东西，宏观上"看起来还行"，但微观上经常充满不协调：button 间距不一致、loading 态和处理态不统一、error message 生硬。工程师能注意到这些问题，但不会优先修它们——因为 training 目标是"功能跑通"，不是"体验到位"。designer 的 training 目标恰恰相反。

## 不同项目，不同打法

所以不是非黑即白的选择。不同类型的项目，协作模式应该不一样。

做 MVP 验证、internal tool、一次性的 delivery，一个人 + AI 就够了。zero communication overhead，decision making 一致，速度最快。代价是品质有天花板，可能存在审美盲区和 UX 盲区。但在这个阶段，速度就是质量，快速拿到 real user feedback 比 pixel perfect 重要得多。

中等重要度的功能，可以让一个全栈工程师独立做，但在关键节点请 designer 或 PM 做一次 review。不是全程参与，是按需介入。保留 solo 的效率，同时用专业视角纠正明显问题。前提是 review 要有重点、有效率，不能变成走形式的 approval meeting。

面向 C 端的核心产品、brand-oriented 的项目、复杂的 information architecture，必须从一开始就混协作。全栈 + designer + PM 深度合作，但角色边界是模糊的——工程师做 design 决策，designer 写 code，PM 直接出 prototype。品质的保障不靠"专业角色把关"，而靠"全员具备专业意识"。

## 先进团队的做法

看 Vercel、Stripe、Linear、Anthropic 这些以 product quality 著称的团队，它们的做法很有意思：不是消除 specialist，而是消除 handoff tax。

Vercel 有个角色叫 Design Engineer，既能在 Figma 做 design，也能在 code 里实现 design。他们分布在 marketing、product、design system 各个地方。Stripe 叫 Product Design Engineer，Apple 叫 Design Technologist。这个角色的存在价值不是"一个人干两个人的活"，而是让 design 和 engineering 之间的交接损耗消失。design 直接在 code 里验证，而不是先出 mockup 再等开发。

Anthropic 的 Claude Code 团队更极端。全员统一叫 Member of Technical Staff，没有 PM、designer、eng 的 title 区分。他们靠五种 archetype 来组织工作：Prototyper 快速试错，Builder 把 prototype 变成 production code，Sweeper 清理技术债务，Grower 推动 product-market fit，Maintainer 保持系统可靠性。一个人这周可能做 Builder，下周做 Sweeper。角色跟随工作，工作不跟随角色。

这些团队传递的信号很明确：品质的保障从"某个角色负责 quality"转向"每个人都有 quality 意识"。specialist 的专业判断力依然存在，但不再是某个人的专属职责。

## 一个实用的判断方法

拿到一个项目，问自己几个问题：

这个项目面向大量 C 端用户吗？visual quality 直接影响 brand image 吗？information architecture 复杂吗？需要长期迭代吗？

如果大部分答案是 yes，从一开始就拉 specialist 进来协作。如果大部分是 no，一个人做，做完找人 review。中间地带的，一个人做关键节点 review。

不管选哪种模式，提前定义清楚什么是"够用的好"。layout 整洁、spacing 一致、core flow 畅通、error state 有反馈、首屏加载不慢。达到 baseline 之后，再决定要不要投入额外资源去追求更高品质。

---

AI 让一个人能闭环，这是事实。但能闭环不等于该闭环。关键是判断当前项目需要的是 baseline quality 还是 judgment，然后选择匹配的方式。

不要因为 AI 让一个人能做所有事就放弃对 quality 的追求，也不要因为追求 quality 就盲目引入所有 specialist。specialization is for scaling, generalists are for starting. 0 到 1 的阶段，速度就是生命。1 到 N 的阶段，quality 才是 moat。

当所有人都能用同样的 generation tools，baseline quality 会升高，但 mediocre work 的数量也会升高。the real value is judgment——知道该选什么。

