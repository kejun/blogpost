# SQLite 如何成为基础设施

> 根据 CoRecursive 第 66 期访谈改写。主持人是 Adam Gordon Bell，受访者是 SQLite 创始人 Richard Hipp。节目发布于 2021 年 7 月 2 日。[节目音频与英文逐字稿](https://corecursive.com/066-sqlite-with-richard-hipp/)

2014 年，OpenSSL 的 Heartbleed 漏洞波及约 17% 使用受信任证书的 SSL Web 服务器。Bell 用这起事件开场，追问一段由小团队维护的开源代码嵌入大量产品之后，谁来承担持续开发和验证的成本。他把问题交给 Hipp，因为包括 Android、Chrome 和 Firefox 在内的许多软件都使用 SQLite。[Netcraft 当时的测量](https://www.netcraft.com/blog/half-a-million-widely-trusted-websites-vulnerable-to-heartbleed-bug) · [SQLite 使用案例](https://sqlite.org/famous.html)

## 舰载应用为何需要一个嵌入式数据库

在美国海军的奥斯卡·奥斯汀号导弹驱逐舰（DDG-79）上，一套软件需要读取管路和阀门的数据，再计算如何隔离故障并恢复下游供应。Hipp 将任意有向图上的一般判定问题归为 NP 完全问题。他回忆，在实际舰船的设计约束下，启发式算法可以很快找到最优解。[美国海军舰籍](https://www.nvr.navy.mil/nvr/getHull.htm?shipId=1344) · [早期项目记录](https://www.linuxjournal.com/article/6650)

当时的数据库是预装的 Informix。服务器进程一旦停掉，应用就读不到数据，Hipp 的团队也无法管理该服务。应用那一步只需要把数据读进内存，于是 Hipp 开始考虑把 SQL 引擎嵌入应用，由应用进程直接访问本地数据库文件。客户保留了 Informix，SQLite 后来用于该项目的开发测试。[SQLite 的进程模型](https://sqlite.org/serverless.html)

SQLite 的首次代码提交在 2000 年 5 月 29 日，1.0 版发布于同年 8 月 17 日。Hipp 在访谈中将动手的时机归于合同经费暂时中断，也提到克林顿与金里奇的预算争端。美国国会档案将相关联邦政府停摆记在 1995 至 1996 年，这段争端与项目经费中断之间的关系仍待确认。[首次提交纪念邮件](https://www.mail-archive.com/sqlite-users@mailinglists.sqlite.org/msg52662.html) · [版本年表](https://sqlite.org/chronology.html) · [美国国会研究处报告](https://www.congress.gov/crs_external_products/RS/PDF/RS20348/RS20348.37.pdf)

## 从编译 SQL 到读取磁盘页

Hipp 当时找不到实现 SQL 引擎的指南，便从熟悉的编译器入手，把 SQL 语句编译成字节码，再交给虚拟机 VDBE 执行。SQLite 1.0 使用 GDBM 做存储。到 2.0，Hipp 改用自有的 B 树存储层，有序键让索引支持范围查找。写 B 树时，他参考了 Donald Knuth 的《计算机程序设计艺术》。删除操作留在该章习题里，由他自己推导。[SQLite 架构](https://sqlite.org/arch.html) · [GDBM 与 B 树的演进](https://www.linuxjournal.com/article/6650)

不同的执行模型也会遇到相同的优化机会。Hipp 注意到，SQLite 的字节码模型与 PostgreSQL 的迭代器模型在一些优化上得出了相似的设计。他从 MySQL 联合创始人 David Axmark 那里听到覆盖索引的做法，回程航班上就把它写进了 SQLite。例如，一条查询按 `name` 筛选，只返回 `phone`，查询规划器可以使用 `(name, phone)` 索引，直接从索引里取得结果，省去一次查表。[SQLite 查询规划文档](https://sqlite.org/queryplanner.html)

## 企业为工程服务付费，维护者决定项目方向

早期使用者把 SQLite 跑在了 Palm Pilot 上。Motorola 为手机系统委托开发，Hipp 回忆当时的报价约为 8 万美元。AOL 想把数据库放进寄给用户的安装光盘。Hipp 在介绍临时索引时发现，索引只有创建者看得见，其他进程写入共享表后，索引就可能过时。Symbian 用自己的数据比较了 10 个引擎，选中 SQLite 后签约委托改进。[Hipp 对早期客户的回顾](https://camilocs.substack.com/p/entrevista-a-richard-hipp)

Symbian 希望提高 SQLite 的「巴士因子」，也就是让项目停摆所需失去的最少关键成员数。Mozilla 的 Mitchell Baker 建议让开发者保留技术决策权，企业通过出资获得支持。2007 年 12 月的成立公告列出 Mozilla 和 Symbian 两家创始成员。Adobe 于 2008 年 2 月成为第三家成员。SQLite 核心代码如今属于公共领域，联盟经费则支持持续开发和维护。[联盟成立公告](https://sqlite.org/pressrelease-20071212.html) · [Adobe 加入公告](https://www.mail-archive.com/sqlite-users@mailinglists.sqlite.org/msg31785.html) · [SQLite 版权声明](https://www.sqlite.org/copyright.html)

## Android 的规模推动 SQLite 加强验证

在早期 Android 团队，工程师通过工作站上的 GDB 调试原型手机时，原型机还能在公用移动通信网上接电话。真机一天能刷入多个系统版本。按 Hipp 的回忆，他见到的其他厂商更新周期以月计。Android 把 SQLite 带到数百万台设备上，频繁的崩溃也暴露了原有测试遗漏的情况。

Hipp 与航空电子供应商 Rockwell Collins 合作时接触到机载软件验证指南 DO-178B，并将其中的结构覆盖方法用于 SQLite。分支覆盖检查判定的分支是否都被执行。修正条件／判定覆盖（MC/DC）还要求证明判定中的每个基本条件都能独立改变判定结果。例如，对 `A && B`，可以用 `(真, 真)`、`(假, 真)` 和 `(真, 假)` 三组输入，分别检验 `A` 和 `B` 的作用。[FAA 关于 DO-178B 的咨询通告](https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentid/22122) · [NASA 的 MC/DC 指南](https://ntrs.nasa.gov/citations/20010057789)

为覆盖最后一批难以触发的代码路径，Hipp 投入了近一年。他回忆，来自 Android 团队的缺陷报告随后停了下来。SQLite 官方记录显示，在 Linux x86 和 x86-64 上运行 TH3 的覆盖测试，`gcov` 测得 SQLite 核心库的分支覆盖与 MC/DC 均为 100%。TH3 还可以通过公开 API 在目标环境中验证编译后的库，并模拟事务提交时断电、磁盘 I/O 错误和内存不足。[TH3 文档](https://sqlite.org/th3.html)

Hipp 原本打算向航空电子厂商销售 TH3。截至访谈时，套件的销量为零。团队把它用于 SQLite 自身的发布验证，加快了确认修复和新功能的速度。

## 数十亿次运行来自不同层次的测试

Hipp 在 2021 年的访谈中估计，约 10 万个独立用例经参数化展开后，一次典型发布会执行数十亿次测试，发布前至少测试 3 天。测试跨操作系统、处理器架构和字节序，团队当时还用一台大端序 PowerPC iBook。各套测试负责不同的验证目标。[SQLite 测试文档](https://sqlite.org/testing.html)

| 测试方式 | 验证内容 |
| --- | --- |
| Tcl 开发测试 | 在源码仓库中公开维护，覆盖常用功能和回归场景。 |
| TH3 | 专有测试套件，检查核心库的结构覆盖、错误处理和恢复行为。 |
| `sqllogictest` | 比较不同 SQL 引擎的查询结果。若 SQL 没有约定输出顺序，可按用例的规则排序后再比。 |
| 模糊测试 | 用大量生成或变异的输入寻找崩溃及其他异常。 |

Hipp 回忆，Shane Harrelson 做的早期跨引擎测试曾使 SQLite、Oracle 和 DB2 崩溃，PostgreSQL 在那一轮里通过了。比较查询结果还能找出执行顺利但返回内容有误的情况。[`sqllogictest` 文档](https://sqlite.org/sqllogictest/doc/trunk/about.wiki)

## 自己承担哪些依赖

SQLite 核心库可以与应用一起编译，依赖标准 C 库中的少量函数和操作系统接口。团队也掌握一部分开发工具。SQL 解析器由 Hipp 自己写的 Lemon 生成，需要调整解析器生成方式时，他可以直接改工具。Fossil 则是他为 SQLite 开发的版本控制系统，也把缺陷跟踪和 Wiki 纳入同一个工具。SQLite 的源码于 2009 年从 CVS 迁入 Fossil。[SQLite 的依赖范围](https://sqlite.org/selfcontained.html) · [Lemon 文档](https://sqlite.org/lemon.html) · [Fossil 项目史](https://www.fossil-scm.org/home/doc/version-2.13/www/history.md)

Hipp 用 Berkeley DB 说明自己为何在意外部组件的授权变化。Oracle 收购 Sleepycat 时，Berkeley DB 已提供开源和商业双重授权。后来 Berkeley DB 6.0 的开源许可证改为 AGPL v3，商业授权继续提供。[Oracle 收购公告](https://www.oracle.com/corporate/pressrelease/oracle-buys-sleepycat-021406.html) · [Berkeley DB 常见问题](https://www.oracle.com/database/technologies/berkeleydb-db-faq.html)

Hipp 用徒步者自己背装备来解释这种取舍。少依赖一项服务，就得自己承担一部分工作。访谈安排期间遇到 Gmail 退信，他考虑过自行运行邮件服务器，也清楚这会带来长期维护负担。

节目结尾，Hipp 回顾了 SQLite 当时少见的做法。它在进程内执行 SQL，直接访问数据库文件，并让值携带自己的类型。普通表的列具有类型亲和性，影响写入和比较时的转换。后来推出的 `STRICT` 表允许开发者对指定的表启用更严格的类型检查。Hipp 给出的建议是，从实际要解决的问题出发，用实现检验当时的共识。[SQLite 的类型系统](https://sqlite.org/datatype3.html)
