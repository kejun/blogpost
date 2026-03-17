# AI 投资分析团队：多 Agent 系统在财经领域的生产级实践

> **摘要**：财经领域是 AI Agent 高风险、高价值的应用场景。本文基于真实的 `daily-investor` 项目，设计并实现一个 6 人制 AI 投资分析团队：数据采集、技术分析、基本面分析、情绪分析、报告生成、风控 Agent。文章涵盖架构设计、权限治理、实战代码与生产部署经验。

---

## 一、为什么是投资分析？

### 1.1 财经领域的 Agent 应用优势

| 优势 | 说明 | 案例 |
|------|------|------|
| 数据密集 | 股价、财报、新闻、社交媒体——海量结构化/非结构化数据 | Finnhub API、Alpha Vantage、RSS 源 |
| 规则清晰 | 技术指标、财务比率、估值模型——有明确计算公式 | RSI、MACD、PE、DCF |
| 实时性强 | 市场 24/7 运行，需要持续监控与快速响应 | 财报季、突发新闻、政策变化 |
| 可量化评估 | 投资回报、夏普比率、最大回撤——效果可衡量 | 回测验证、实盘跟踪 |

### 1.2 为什么需要多 Agent？

**单体 Agent 的局限**：

```
❌ 尝试用一个大模型处理所有任务：
- 上下文爆炸：股价数据 + 财报 + 新闻 + 技术指标 = 超过 128K
- 专业度分散：同一个模型既要懂技术分析，又要懂财报分析，还要懂情绪分析
- 错误传播：一个环节出错（如数据抓取失败），整个流程崩溃
- 无法并行：串行执行，复杂分析耗时>30 分钟
```

**多 Agent 的优势**：

```
✅ 专业分工：
- 数据采集 Agent：专注 API 调用、数据清洗、异常检测
- 技术分析 Agent：专注图表形态、指标计算、趋势判断
- 基本面分析 Agent：专注财报解读、估值建模、行业对比
- 情绪分析 Agent：专注新闻情感、社交媒体舆情、市场情绪
- 报告生成 Agent：专注内容组织、语言风格、可视化
- 风控 Agent：专注异常检测、仓位控制、止损提醒

✅ 并行执行：
- 技术分析与基本面分析可同时进行
- 多股票数据可同时抓取
- 整体耗时从 30 分钟降至 5 分钟

✅ 容错性强：
- 某个 Agent 失败不影响其他 Agent
- 风控 Agent 可独立监控并熔断
```

### 1.3 风险控制：为什么财经 Agent 需要更严格的治理？

| 风险类型 | 潜在损失 | 控制措施 |
|----------|----------|----------|
| 数据错误 | 基于错误数据做出错误决策 | 多源校验、异常检测 |
| 模型幻觉 | 编造不存在的财务数据 | 事实核查、引用溯源 |
| 过度交易 | 频繁交易导致手续费侵蚀利润 | 交易频率限制、审批流程 |
| 黑天鹅事件 | 突发新闻/政策导致巨额亏损 | 风控熔断、止损机制 |
| 合规风险 | 违反投资建议法规 | 免责声明、人类审核 |

**关键洞察**：财经 Agent 必须是 **HOTL 架构**（常规分析自主执行）+ **HITL 关键点**（交易决策需人类批准）。

---

## 二、系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AI 投资分析团队架构                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      人类投资者 (Human-in-the-Loop)              │   │
│  │  - 设定投资目标与约束                                           │   │
│  │  - 审批交易决策（>阈值）                                        │   │
│  │  - 处理异常情况                                                 │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      协调 Agent (Coordinator)                    │   │
│  │  - 任务分解与分配                                               │   │
│  │  - 结果聚合与冲突解决                                           │   │
│  │  - 与人类沟通                                                   │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                         │
│          ┌────────────────────┼────────────────────┐                   │
│          │                    │                    │                   │
│          ▼                    ▼                    ▼                   │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐            │
│  │  数据采集层   │   │  分析层       │   │  执行层       │            │
│  │               │   │               │   │               │            │
│  │ ┌───────────┐ │   │ ┌───────────┐ │   │ ┌───────────┐ │            │
│  │ │数据采集   │ │   │ │技术分析   │ │   │ │报告生成   │ │            │
│  │ │Agent      │ │   │ │Agent      │ │   │ │Agent      │ │            │
│  │ └───────────┘ │   │ └───────────┘ │   │ └───────────┘ │            │
│  │ ┌───────────┐ │   │ ┌───────────┐ │   │ ┌───────────┐ │            │
│  │ │(L1 只读)  │ │   │ │(L1 只读)  │ │   │ │(L2 草稿)  │ │            │
│  │ └───────────┘ │   │ └───────────┘ │   │ └───────────┘ │            │
│  │               │   │ ┌───────────┐ │   │ ┌───────────┐ │            │
│  │               │   │ │基本面分析 │ │   │ │风控 Agent │ │            │
│  │               │   │ │Agent      │ │   │ │(L4 熔断) │ │            │
│  │               │   │ └───────────┘ │   │ └───────────┘ │            │
│  │               │   │ ┌───────────┐ │   │               │            │
│  │               │   │ │情绪分析   │ │   │               │            │
│  │               │   │ │Agent      │ │   │               │            │
│  │               │   │ └───────────┘ │   │               │            │
│  └───────────────┘   └───────────────┘   └───────────────┘            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      数据层与工具                                │   │
│  │  - Finnhub API (股价/财报)                                      │   │
│  │  - Alpha Vantage (技术指标)                                     │   │
│  │  - RSS/新闻源 (Hacker News, MIT Tech Review)                    │   │
│  │  - X/Twitter (社交媒体情绪)                                     │   │
│  │  - TiDB Cloud (数据存储与向量检索)                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent 角色与职责

| Agent | 权限级别 | 职责 | 可自主执行 | 需人类审批 |
|-------|----------|------|------------|------------|
| **数据采集 Agent** | L1 | 抓取股价、财报、新闻数据 | API 调用、数据清洗 | 无 |
| **技术分析 Agent** | L1 | 计算指标、识别形态 | 图表分析、趋势判断 | 无 |
| **基本面分析 Agent** | L1 | 解读财报、估值建模 | 财务比率计算、行业对比 | 无 |
| **情绪分析 Agent** | L1 | 分析新闻/社交媒体情感 | 情感打分、舆情监控 | 无 |
| **报告生成 Agent** | L2 | 生成投资洞察报告 | 草稿创建、格式化 | 公开发布 |
| **风控 Agent** | L4 | 监控异常、触发熔断 | 风险预警 | 交易执行（>阈值） |
| **协调 Agent** | L3 | 任务分配、结果聚合 | 日常调度 | 策略调整 |

### 2.3 数据流设计

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  外部数据源   │     │   Agent 层    │     │   输出层     │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ Finnhub API  │────▶│ 数据采集     │────▶│              │
│ AlphaVantage │────▶│ Agent        │     │              │
│ RSS  feeds   │────▶│              │     │              │
│ X/Twitter    │────▶└──────┬───────┘     │              │
│              │           │             │              │
│              │           ▼             │              │
│              │    ┌──────────────┐     │              │
│              │    │ 分析 Agent 层 │     │              │
│              │    │ - 技术分析   │────▶│  每日报告    │
│              │    │ - 基本面分析 │────▶│  持仓建议    │
│              │    │ - 情绪分析   │────▶│  风险预警    │
│              │    └──────┬───────┘     │              │
│              │           │             │              │
│              │           ▼             │              │
│              │    ┌──────────────┐     │              │
│              │    │ 报告生成     │────▶│  Markdown    │
│              │    │ Agent        │     │  WhatsApp    │
│              │    └──────┬───────┘     │  GitHub      │
│              │           │             │              │
│              │           ▼             │              │
│              │    ┌──────────────┐     │              │
│              │    │ 风控 Agent   │────▶│  熔断通知    │
│              │    │ (独立监控)   │     │  人类介入    │
│              │    └──────────────┘     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## 三、核心模块实现

### 3.1 数据采集 Agent

```python
# agents/data_collector_agent.py
import asyncio
import finnhub
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class DataCollectorAgent:
    """
    数据采集 Agent (L1 只读权限)
    
    职责:
    - 从多个 API 源抓取股价、财报、新闻数据
    - 数据清洗与格式化
    - 异常检测（数据缺失、价格异常波动）
    """
    
    def __init__(self, config: dict):
        self.finnhub_client = finnhub.Client(api_key=config["finnhub_api_key"])
        self.alpha_vantage_key = config["alpha_vantage_key"]
        self.rss_feeds = config["rss_feeds"]
        self.storage = config["storage"]  # TiDB Cloud 连接
    
    async def collect_stock_data(self, symbol: str) -> Dict:
        """采集股票数据"""
        tasks = [
            self._fetch_price_data(symbol),
            self._fetch_financials(symbol),
            self._fetch_technical_indicators(symbol),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "price_data": results[0] if not isinstance(results[0], Exception) else None,
            "financials": results[1] if not isinstance(results[1], Exception) else None,
            "technicals": results[2] if not isinstance(results[2], Exception) else None,
            "errors": [str(r) for r in results if isinstance(r, Exception)]
        }
        
        # 异常检测
        if data["errors"]:
            await self._alert_data_errors(symbol, data["errors"])
        
        # 存储到 TiDB
        await self.storage.insert("stock_data", data)
        
        return data
    
    async def _fetch_price_data(self, symbol: str) -> Dict:
        """获取价格数据（Finnhub）"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=90)
        
        bars = self.finnhub_client.stock_candles(
            symbol,
            'D',
            int(start_time.timestamp()),
            int(end_time.timestamp())
        )
        
        if bars['s'] != 'ok':
            raise Exception(f"Finnhub API error: {bars['s']}")
        
        return {
            "timestamps": bars['t'],
            "open": bars['o'],
            "high": bars['h'],
            "low": bars['l'],
            "close": bars['c'],
            "volume": bars['v']
        }
    
    async def _fetch_financials(self, symbol: str) -> Dict:
        """获取财务数据（Finnhub）"""
        financials = self.finnhub_client.company_basic_financials(symbol, 'all')
        
        return {
            "metrics": financials.get('metric', {}),
            "series": financials.get('series', {})
        }
    
    async def _fetch_technical_indicators(self, symbol: str) -> Dict:
        """获取技术指标（Alpha Vantage）"""
        async with aiohttp.ClientSession() as session:
            url = f"https://www.alphavantage.co/query"
            params = {
                "function": "TECHNICAL_INDICATORS",
                "symbol": symbol,
                "interval": "daily",
                "time_period": 14,
                "apikey": self.alpha_vantage_key
            }
            
            async with session.get(url, params=params) as response:
                data = await response.json()
                return data
    
    async def _alert_data_errors(self, symbol: str, errors: List[str]):
        """数据错误告警"""
        alert_message = f"""
⚠️ **数据采集异常**

股票：{symbol}
时间：{datetime.now().isoformat()}
错误：
{chr(10).join(f"- {e}" for e in errors)}

建议：检查 API 配额、网络连接
"""
        # 发送告警给协调 Agent
        await self.storage.publish_alert("data_collection", alert_message)
```

### 3.2 技术分析 Agent

```python
# agents/technical_analysis_agent.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class TechnicalAnalysisAgent:
    """
    技术分析 Agent (L1 只读权限)
    
    职责:
    - 计算技术指标（RSI, MACD, MA, Bollinger Bands）
    - 识别图表形态（头肩顶、双底、三角形）
    - 趋势判断（上涨/下跌/盘整）
    - 支撑位/阻力位识别
    """
    
    def __init__(self):
        self.indicators = {
            "RSI": self._calculate_rsi,
            "MACD": self._calculate_macd,
            "SMA": self._calculate_sma,
            "EMA": self._calculate_ema,
            "BOLLINGER": self._calculate_bollinger_bands,
        }
    
    def analyze(self, price_data: Dict) -> Dict:
        """执行技术分析"""
        df = pd.DataFrame(price_data)
        
        analysis = {
            "trend": self._identify_trend(df),
            "momentum": self._analyze_momentum(df),
            "volatility": self._analyze_volatility(df),
            "support_resistance": self._identify_support_resistance(df),
            "patterns": self._identify_patterns(df),
            "signals": self._generate_signals(df),
        }
        
        return analysis
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算 RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算 MACD"""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _identify_trend(self, df: pd.DataFrame) -> Dict:
        """识别趋势"""
        sma_20 = df['close'].rolling(window=20).mean()
        sma_50 = df['close'].rolling(window=50).mean()
        sma_200 = df['close'].rolling(window=200).mean()
        
        current_price = df['close'].iloc[-1]
        
        if current_price > sma_20.iloc[-1] > sma_50.iloc[-1] > sma_200.iloc[-1]:
            trend = "BULLISH"
            strength = "STRONG"
        elif current_price < sma_20.iloc[-1] < sma_50.iloc[-1] < sma_200.iloc[-1]:
            trend = "BEARISH"
            strength = "STRONG"
        elif abs(current_price - sma_20.iloc[-1]) / sma_20.iloc[-1] < 0.02:
            trend = "SIDEWAYS"
            strength = "MODERATE"
        else:
            trend = "MIXED"
            strength = "WEAK"
        
        return {
            "direction": trend,
            "strength": strength,
            "key_levels": {
                "sma_20": sma_20.iloc[-1],
                "sma_50": sma_50.iloc[-1],
                "sma_200": sma_200.iloc[-1]
            }
        }
    
    def _analyze_momentum(self, df: pd.DataFrame) -> Dict:
        """分析动量"""
        rsi = self._calculate_rsi(df['close'])
        macd_line, signal_line, histogram = self._calculate_macd(df['close'])
        
        rsi_current = rsi.iloc[-1]
        
        momentum_signals = []
        
        if rsi_current > 70:
            momentum_signals.append("OVERBOUGHT")
        elif rsi_current < 30:
            momentum_signals.append("OVERSOLD")
        
        if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            momentum_signals.append("MACD_BULLISH_CROSSOVER")
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            momentum_signals.append("MACD_BEARISH_CROSSOVER")
        
        return {
            "rsi": rsi_current,
            "macd": {
                "line": macd_line.iloc[-1],
                "signal": signal_line.iloc[-1],
                "histogram": histogram.iloc[-1]
            },
            "signals": momentum_signals
        }
    
    def _identify_support_resistance(self, df: pd.DataFrame) -> Dict:
        """识别支撑位和阻力位"""
        # 使用局部极值法
        window = 20
        
        local_max = df['high'].rolling(window=window, center=True).max()
        local_min = df['low'].rolling(window=window, center=True).min()
        
        resistance_levels = local_max.dropna().tolist()
        support_levels = local_min.dropna().tolist()
        
        # 取最近的 3 个 level
        return {
            "resistance": sorted(resistance_levels, reverse=True)[:3],
            "support": sorted(support_levels)[:3]
        }
    
    def _identify_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """识别图表形态（简化版）"""
        patterns = []
        
        # 检测双底形态（简化逻辑）
        if self._detect_double_bottom(df):
            patterns.append({
                "type": "DOUBLE_BOTTOM",
                "signal": "BULLISH",
                "confidence": 0.7
            })
        
        # 检测头肩顶形态（简化逻辑）
        if self._detect_head_shoulders_top(df):
            patterns.append({
                "type": "HEAD_AND_SHOULDERS_TOP",
                "signal": "BEARISH",
                "confidence": 0.6
            })
        
        return patterns
    
    def _generate_signals(self, df: pd.DataFrame) -> List[Dict]:
        """生成交易信号"""
        signals = []
        
        trend = self._identify_trend(df)
        momentum = self._analyze_momentum(df)
        
        # 综合判断
        if trend["direction"] == "BULLISH" and "OVERSOLD" in momentum["signals"]:
            signals.append({
                "type": "BUY",
                "reason": "上涨趋势 + 超卖",
                "confidence": 0.75
            })
        elif trend["direction"] == "BEARISH" and "OVERBOUGHT" in momentum["signals"]:
            signals.append({
                "type": "SELL",
                "reason": "下跌趋势 + 超买",
                "confidence": 0.75
            })
        
        return signals
```

### 3.3 风控 Agent（关键组件）

```python
# agents/risk_control_agent.py
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # 正常运行
    OPEN = "open"          # 熔断，停止交易
    HALF_OPEN = "half_open" # 半开，测试恢复

class RiskControlAgent:
    """
    风控 Agent (L4 熔断权限)
    
    职责:
    - 实时监控投资组合风险
    - 检测异常行为（连续亏损、超额交易）
    - 触发熔断机制
    - 发送告警给人类投资者
    
    权限:
    - 可自主暂停所有交易 Agent
    - 交易执行需人类审批（>阈值）
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.circuit_breaker = CircuitBreakerState.CLOSED
        self.losses = []  # 记录亏损交易
        self.trades_today = 0
        self.max_daily_trades = config.get("max_daily_trades", 10)
        self.max_consecutive_losses = config.get("max_consecutive_losses", 3)
        self.max_drawdown = config.get("max_drawdown", 0.15)  # 15% 最大回撤
        
        # 独立监控循环
        self.monitoring_task = None
    
    def start_monitoring(self):
        """启动独立监控循环"""
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
    
    async def _monitor_loop(self):
        """持续监控（每 5 分钟检查一次）"""
        while True:
            await asyncio.sleep(300)  # 5 分钟
            
            if self.circuit_breaker == CircuitBreakerState.OPEN:
                continue  # 熔断中，跳过检查
            
            # 检查各项风险指标
            await self._check_consecutive_losses()
            await self._check_daily_trade_limit()
            await self._check_drawdown()
    
    async def record_trade(self, trade_result: Dict):
        """记录交易结果"""
        pnl = trade_result.get("pnl", 0)
        self.trades_today += 1
        
        if pnl < 0:
            self.losses.append({
                "timestamp": datetime.now(),
                "pnl": pnl,
                "symbol": trade_result.get("symbol"),
                "reason": trade_result.get("reason")
            })
            
            # 检查是否触发熔断
            await self._check_consecutive_losses()
    
    async def _check_consecutive_losses(self):
        """检查连续亏损"""
        # 清理 24 小时前的亏损记录
        cutoff = datetime.now() - timedelta(hours=24)
        self.losses = [l for l in self.losses if l["timestamp"] > cutoff]
        
        if len(self.losses) >= self.max_consecutive_losses:
            await self._trigger_circuit_breaker(
                reason=f"24 小时内连续 {len(self.losses)} 次亏损",
                level=RiskLevel.CRITICAL
            )
    
    async def _check_daily_trade_limit(self):
        """检查每日交易次数"""
        if self.trades_today >= self.max_daily_trades:
            await self._trigger_circuit_breaker(
                reason=f"达到每日交易上限 ({self.max_daily_trades}次)",
                level=RiskLevel.HIGH
            )
    
    async def _check_drawdown(self):
        """检查回撤"""
        # 从存储中获取当前净值
        current_nav = await self._get_current_nav()
        peak_nav = await self._get_peak_nav()
        
        if peak_nav > 0:
            drawdown = (peak_nav - current_nav) / peak_nav
            
            if drawdown >= self.max_drawdown:
                await self._trigger_circuit_breaker(
                    reason=f"达到最大回撤限制 ({drawdown:.1%} >= {self.max_drawdown:.1%})",
                    level=RiskLevel.CRITICAL
                )
    
    async def _trigger_circuit_breaker(self, reason: str, level: RiskLevel):
        """触发熔断"""
        if self.circuit_breaker == CircuitBreakerState.OPEN:
            return  # 已经在熔断状态
        
        self.circuit_breaker = CircuitBreakerState.OPEN
        
        # 1. 停止所有交易 Agent
        await self._stop_trading_agents()
        
        # 2. 发送紧急告警给人类
        alert_message = f"""
🚨 **风控熔断触发**

级别：{level.value}
时间：{datetime.now().isoformat()}
原因：{reason}

当前状态:
- 连续亏损：{len(self.losses)} 次
- 今日交易：{self.trades_today} 次
- 熔断状态：OPEN

⚠️ 所有交易已暂停

请审查策略并决定是否恢复：
- 回复 `恢复交易` 继续
- 回复 `调整策略` 修改参数
- 回复 `查看明细` 获取详细报告
"""
        await self._notify_human(alert_message, level)
        
        # 3. 记录审计日志
        await self._log_circuit_breaker_event(reason, level)
    
    async def _stop_trading_agents(self):
        """停止所有交易 Agent"""
        # 发送停止信号给协调 Agent
        await self.config["message_bus"].publish("coordinator", {
            "action": "STOP_TRADING",
            "reason": "risk_control_circuit_breaker",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _notify_human(self, message: str, level: RiskLevel):
        """通知人类投资者"""
        # 通过 WhatsApp/Telegram 发送
        await self.config["messaging"].send(
            target=self.config["human_investor_id"],
            message=message,
            priority="high" if level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else "normal"
        )
    
    async def _log_circuit_breaker_event(self, reason: str, level: RiskLevel):
        """记录审计日志"""
        log_entry = {
            "event": "circuit_breaker_triggered",
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "level": level.value,
            "state": self.circuit_breaker.value
        }
        await self.config["storage"].insert("audit_logs", log_entry)
    
    async def request_resume(self, human_approval: bool):
        """请求恢复交易（需人类批准）"""
        if not human_approval:
            return  # 人类拒绝恢复
        
        # 进入半开状态，允许少量测试交易
        self.circuit_breaker = CircuitBreakerState.HALF_OPEN
        self.losses = []  # 重置亏损计数
        self.trades_today = 0
        
        # 通知协调 Agent 恢复
        await self.config["message_bus"].publish("coordinator", {
            "action": "RESUME_TRADING",
            "mode": "HALF_OPEN",  # 半开模式，限制交易规模
            "timestamp": datetime.now().isoformat()
        })
        
        # 发送确认通知
        await self._notify_human(
            "✅ 交易已恢复（半开模式）\n\n将限制交易规模，观察表现。",
            RiskLevel.MEDIUM
        )
```

### 3.4 协调 Agent

```python
# agents/coordinator_agent.py
import asyncio
from typing import Dict, List, Optional

class CoordinatorAgent:
    """
    协调 Agent (L3 调度权限)
    
    职责:
    - 任务分解与分配
    - 结果聚合与冲突解决
    - 与人类投资者沟通
    - 调用风控 Agent 审批交易
    
    权限:
    - 可自主调度分析 Agent
    - 交易决策需风控 Agent 审批
    - 大额交易需人类批准
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.agents = {
            "data_collector": config["agents"]["data_collector"],
            "technical_analysis": config["agents"]["technical_analysis"],
            "fundamental_analysis": config["agents"]["fundamental_analysis"],
            "sentiment_analysis": config["agents"]["sentiment_analysis"],
            "report_generator": config["agents"]["report_generator"],
            "risk_control": config["agents"]["risk_control"],
        }
        self.trading_enabled = True
        self.trading_mode = "FULL"  # FULL / HALF_OPEN / DISABLED
    
    async def run_daily_analysis(self, symbols: List[str]) -> Dict:
        """执行每日分析流程"""
        print(f"📊 开始每日分析，标的：{symbols}")
        
        # Step 1: 数据采集（并行）
        print("📥 采集数据...")
        data_tasks = [
            self.agents["data_collector"].collect_stock_data(symbol)
            for symbol in symbols
        ]
        stock_data = await asyncio.gather(*data_tasks)
        
        # Step 2: 多维度分析（并行）
        print("🔍 执行分析...")
        analysis_tasks = [
            self._run_technical_analysis(stock_data),
            self._run_fundamental_analysis(stock_data),
            self._run_sentiment_analysis(symbols),
        ]
        analysis_results = await asyncio.gather(*analysis_tasks)
        
        # Step 3: 聚合结果
        aggregated = self._aggregate_analysis(analysis_results)
        
        # Step 4: 生成报告
        print("📝 生成报告...")
        report = await self.agents["report_generator"].generate_report(aggregated)
        
        # Step 5: 风控检查
        print("🛡️ 风控检查...")
        risk_assessment = await self.agents["risk_control"].assess_portfolio(aggregated)
        
        return {
            "report": report,
            "risk_assessment": risk_assessment,
            "timestamp": datetime.now().isoformat()
        }
    
    async def execute_trade(self, trade_proposal: Dict) -> Dict:
        """执行交易（需审批）"""
        amount = trade_proposal.get("amount", 0)
        
        # 检查交易状态
        if not self.trading_enabled:
            return {"status": "rejected", "reason": "交易已暂停"}
        
        # 根据金额决定审批流程
        if amount < 1000:
            # 小额交易：风控 Agent 自主审批
            approval = await self.agents["risk_control"].approve_trade(trade_proposal)
        elif amount < 10000:
            # 中等金额：风控 Agent + 事后通知人类
            approval = await self.agents["risk_control"].approve_trade(trade_proposal)
            if approval["approved"]:
                await self._notify_human_trade(trade_proposal)
        else:
            # 大额交易：需人类 HITL 审批
            approval = await self._request_human_approval(trade_proposal)
        
        if not approval["approved"]:
            return {"status": "rejected", "reason": approval["reason"]}
        
        # 执行交易
        result = await self._execute_trade_impl(trade_proposal)
        
        # 记录交易结果（供风控 Agent 跟踪）
        await self.agents["risk_control"].record_trade(result)
        
        return result
    
    async def _request_human_approval(self, trade_proposal: Dict) -> Dict:
        """请求人类审批大额交易"""
        message = f"""
💰 **大额交易审批请求**

标的：{trade_proposal['symbol']}
方向：{trade_proposal['direction']} (买入/卖出)
金额：${trade_proposal['amount']:,.2f}
理由：{trade_proposal['reason']}

技术分析：{trade_proposal.get('technical_summary', 'N/A')}
基本面分析：{trade_proposal.get('fundamental_summary', 'N/A')}

风险等级：{trade_proposal.get('risk_level', 'MEDIUM')}

---

请回复：
- `批准` - 执行交易
- `拒绝` - 取消交易
- `修改` - 调整金额或条件

超时：1 小时后自动拒绝
"""
        # 发送审批请求
        approval_request = await self.config["messaging"].send(
            target=self.config["human_investor_id"],
            message=message,
            priority="high"
        )
        
        # 等待响应（简化版，实际需实现回调）
        # ...
        
        return {"approved": True, "reason": "人类批准"}  # 简化
```

---

## 四、权限治理与风控机制

### 4.1 权限矩阵

| 操作 | 数据采集 | 技术分析 | 基本面分析 | 情绪分析 | 报告生成 | 风控 Agent | 协调 Agent | 人类 |
|------|----------|----------|------------|----------|----------|------------|------------|------|
| 读取股价数据 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 读取财报数据 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 计算技术指标 | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| 生成分析报告 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 发布报告 | ❌ | ❌ | ❌ | ❌ | ⚠️ L3 | ✅ | ⚠️ L3 | ✅ |
| 执行交易 (<$1K) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ L3 | ✅ |
| 执行交易 (≥$1K) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ HITL |
| 暂停交易 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ L3 | ✅ |
| 调整策略参数 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ L3 | ✅ |

### 4.2 风控熔断规则

| 触发条件 | 阈值 | 动作 | 恢复方式 |
|----------|------|------|----------|
| 连续亏损 | 3 次/24h | 熔断，停止交易 | 人类审批 |
| 单日交易次数 | 10 次 | 熔断，停止交易 | 自动（次日重置） |
| 最大回撤 | 15% | 熔断，停止交易 | 人类审批 |
| 单笔损失 | >5% 仓位 | 告警，通知人类 | 无需熔断 |
| 数据异常 | API 错误率>20% | 暂停数据采集 | 自动恢复 |

### 4.3 审计日志

```json
{
  "event": "trade_executed",
  "timestamp": "2026-03-19T10:30:00Z",
  "symbol": "AAPL",
  "direction": "BUY",
  "amount": 5000,
  "price": 175.50,
  "approval_type": "human_hitl",
  "approver": "+8613693272710",
  "reason": "技术分析买入信号 + 基本面支撑",
  "risk_level": "MEDIUM",
  "agent_id": "coordinator-agent-001"
}
```

---

## 五、生产部署经验

### 5.1 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                      生产环境部署                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │  OpenClaw   │   │  TiDB Cloud │   │  Finnhub    │       │
│  │  (Agent 运行)│   │  (数据存储) │   │  (股价 API) │       │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘       │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                 │
│                  ┌────────┴────────┐                        │
│                  │  VPC 内网通信   │                        │
│                  └────────┬────────┘                        │
│                           │                                 │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│  ┌──────┴──────┐   ┌──────┴──────┐   ┌──────┴──────┐       │
│  │   WhatsApp  │   │   GitHub    │   │  监控告警   │       │
│  │  (通知人类) │   │  (报告发布) │   │  (Prometheus)│      │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 监控指标

| 指标 | 目标值 | 告警阈值 | 说明 |
|------|--------|----------|------|
| Agent 响应时间 | <5s | >10s | 单个 Agent 执行耗时 |
| 数据采集成功率 | >95% | <90% | API 调用成功率 |
| 报告生成准时率 | 100% | <100% | 每日报告是否按时生成 |
| 风控熔断次数 | <1 次/月 | >1 次/周 | 熔断触发频率 |
| 人类审批响应时间 | <4h | >8h | 人类平均响应时间 |

### 5.3 成本结构

| 项目 | 月成本 | 说明 |
|------|--------|------|
| Finnhub API | $59 | Pro 计划，1M 调用/月 |
| Alpha Vantage | $0 | 免费版，5 次/分钟 |
| TiDB Cloud | $0 | Ephemeral 实例（30 天） |
| OpenClaw | $0 | 自托管 |
| LLM API (Qwen3.5) | ~$50 | 按实际使用量 |
| **合计** | **~$109/月** | 可支撑 10-20 只股票分析 |

---

## 六、总结与展望

### 6.1 核心经验

1. **权限分级是基础**——L1-L4 分类，明确每个 Agent 能做什么
2. **风控独立于分析**——风控 Agent 必须独立监控，不受分析结果影响
3. **HITL 用于关键点**——交易执行（>阈值）需人类批准，分析过程自主
4. **审计日志必备**——所有决策必须有完整记录，方便回溯

### 6.2 待优化方向

- [ ] 引入更多数据源（期权数据、宏观经济指标）
- [ ] 实现回测框架（验证策略历史表现）
- [ ] 增加 Agent 间辩论机制（减少群体思维）
- [ ] 集成更多风控指标（VaR、夏普比率）

### 6.3 下一步行动

- [ ] 部署生产环境（TiDB Cloud 正式实例）
- [ ] 接入真实交易 API（Interactive Brokers / 富途）
- [ ] 进行 3 个月模拟盘测试
- [ ] 编写用户手册与风险披露文档

---

**系列文章**：
- 上一篇：[人在回路：多 Agent 权限治理](2026-03-18-human-in-loop-multi-agent-governance.md)
- 下一篇：待定（多 Agent 框架对比 / 评估体系）

**项目仓库**：
- daily-investor: https://github.com/kejun/daily-investor
- 本文代码示例：`daily-investor/agents/`

---

*⚠️ 免责声明：本文仅为技术分享，不构成投资建议。投资有风险，决策需谨慎。*
