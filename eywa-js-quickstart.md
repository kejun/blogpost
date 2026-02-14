# eywa-js 快速接入（10 分钟）

本手册只覆盖“能跑起来”的最小路径。  
目标：在现有对话应用中，以最小改动接入 `eywa-js` 记忆能力。

---

## 1) 你需要准备什么

- 一个可访问的 `eywa-js` 服务地址（`EYWA_ENDPOINT`）
- 一个 API Key（`EYWA_API_KEY`）
- 你的业务标识：`tenantId`，可选 `userId/sessionId`

---

## 2) 最小接入方式（只改两处）

你只需要在一次对话请求中做两次调用：

1. 模型调用前：`beforeLLM()` 取上下文  
2. 模型调用后：`afterLLM()` 写记忆

```ts
import { createEywaMemory } from "eywa-js";

const memory = createEywaMemory({
  endpoint: process.env.EYWA_ENDPOINT!,
  apiKey: process.env.EYWA_API_KEY!,
});

export async function chatHandler(input: {
  tenantId: string;
  userId?: string;
  sessionId?: string;
  message: string;
}) {
  const { context, traceId } = await memory.beforeLLM({
    tenantId: input.tenantId,
    userId: input.userId,
    sessionId: input.sessionId,
    message: input.message,
  });

  const modelOutput = await callYourLLM({
    systemPrompt: context,
    userMessage: input.message,
  });

  await memory.afterLLM({
    tenantId: input.tenantId,
    userId: input.userId,
    sessionId: input.sessionId,
    userMessage: input.message,
    assistantMessage: modelOutput,
    traceId,
  });

  return { reply: modelOutput };
}
```

---

## 3) 默认行为（不用配置）

默认已经启用：
- 自动检索策略（`strategy=auto`）
- `topK=8`
- 当前态优先（`currentStateOnly=true`）
- 返回引用（`returnCitations=true`）
- 异步写入（`writeMode=async`）

你不需要在业务代码里传递检索权重、冲突阈值、压缩级别等高级参数。

---

## 4) LangGraph 接入示例

在节点执行前后挂两次调用即可：

```ts
// before node
const pre = await memory.beforeLLM({
  tenantId,
  userId,
  sessionId,
  message: state.input,
});

// call model with pre.context
const output = await llm.invoke([
  { role: "system", content: pre.context },
  { role: "user", content: state.input },
]);

// after node
await memory.afterLLM({
  tenantId,
  userId,
  sessionId,
  userMessage: state.input,
  assistantMessage: output.content,
  traceId: pre.traceId,
});
```

---

## 5) 常见错误与处理

- `E_BAD_REQUEST`：参数缺失或格式不对  
  - 检查 `tenantId` 是否传入
- `E_TENANT_FORBIDDEN`：租户越权  
  - 确认 token 中租户与请求一致
- `E_DEP_TIMEOUT` / `E_DEP_UNAVAILABLE`：依赖超时或不可用  
  - 使用短上下文降级，稍后重试
- `E_DIM_MISMATCH`：向量维度配置不一致  
  - 检查服务端 embedding 与 collection 配置

---

## 6) 生产最小检查清单

- [ ] 所有请求都带 `tenantId`
- [ ] `beforeLLM` 成功后再调用模型
- [ ] `afterLLM` 失败不阻断主回复（异步重试）
- [ ] 日志中记录 `traceId/requestId`
- [ ] 压测验证 P95 与错误率达标

---

## 7) 你暂时不需要关心的内容

以下能力由 `eywa-js` 服务端接管：
- 原子事实抽取（AFU）
- 时序推理与知识更新
- 分层索引（L0/L1/L2）
- 冲突检测与版本链管理
- Outbox 重试与补偿

---

## 8) 下一步（可选）

如果要进一步优化效果，再按顺序启用：

1. 返回引用展示（UI 展示来源）
2. 用户级策略（只看当前用户记忆）
3. 历史追踪问答（history trace）
4. 业务场景专项调参（由平台侧统一配置）
