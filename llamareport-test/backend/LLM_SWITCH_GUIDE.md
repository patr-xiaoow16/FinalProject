# LLM 切换使用指南

## 概述

现在后端支持通过环境变量 `LLM_PROVIDER` 在 DeepSeek 和 Claude 之间切换使用。

## 配置方式

### 1. 使用 DeepSeek（默认）

在 `.env` 文件中配置：

```env
# LLM Provider 选择
LLM_PROVIDER=deepseek

# DeepSeek API 配置
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-chat  # 可选，默认为 deepseek-chat

# OpenAI API 配置（用于 Embedding）
OPENAI_API_KEY=your-openai-api-key-here
```

### 2. 使用 Claude

在 `.env` 文件中配置（支持 `claude` 或 `anthropic` 两种写法）：

```env
# LLM Provider 选择（可以使用 claude 或 anthropic）
LLM_PROVIDER=claude
# 或者
# LLM_PROVIDER=anthropic

# Anthropic Claude API 配置
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # 可选，默认为 claude-3-5-sonnet-20241022
# 如果使用中转站，设置自定义 Base URL（可选）
# ANTHROPIC_BASE_URL=https://api.uniapi.io/claude  # 示例：UniAPI 中转站

# OpenAI API 配置（用于 Embedding）
OPENAI_API_KEY=your-openai-api-key-here
```

## Claude 模型选择

支持的 Claude 模型：

- `claude-3-5-sonnet-20241022` - 推荐，性能好（默认）
- `claude-3-opus-20240229` - 最强性能，成本较高
- `claude-3-haiku-20240307` - 最快响应，成本较低

## 安装依赖

如果使用 Claude，需要安装 Anthropic 依赖：

```bash
pip install llama-index-llms-anthropic anthropic
```

或者安装所有依赖：

```bash
pip install -r requirements.txt
```

## 验证配置

启动服务后，查看日志确认使用的 LLM：

- DeepSeek: `✅ DeepSeek LLM配置成功 - 模型: deepseek-chat`
- Claude: `✅ Anthropic Claude LLM配置成功 - 模型: claude-3-5-sonnet-20241022`

也可以通过 `/info` 接口查看当前配置：

```bash
curl http://localhost:8000/info
```

## 使用中转站 API

如果你的 `ANTHROPIC_API_KEY` 是中转站（代理服务）的 API Key，需要设置 `ANTHROPIC_BASE_URL`：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-relay-api-key-here
ANTHROPIC_BASE_URL=https://api.uniapi.io/claude  # 替换为你的中转站地址
```

### 常见中转站配置

| 中转站服务 | Base URL 示例 |
|-----------|--------------|
| UniAPI | `https://api.uniapi.io/claude` |
| LiteLLM | `https://your-litellm-server:4000` |
| 其他中转站 | 根据服务商提供的文档设置 |

**注意**：如果不设置 `ANTHROPIC_BASE_URL`，默认使用官方 API (`https://api.anthropic.com`)

## 注意事项

1. **Embedding 模型**：无论选择哪个 LLM Provider，Embedding 都使用 OpenAI（`text-embedding-3-small`）
2. **API Key 要求**：
   - 使用 DeepSeek 时需要 `DEEPSEEK_API_KEY`
   - 使用 Claude 时需要 `ANTHROPIC_API_KEY`
   - 两种情况下都需要 `OPENAI_API_KEY`（用于 Embedding）
3. **切换 Provider**：修改 `.env` 文件后需要重启服务
4. **成本考虑**：Claude 的成本通常高于 DeepSeek，请根据需求选择
5. **中转站使用**：如果使用中转站，确保 `ANTHROPIC_BASE_URL` 指向正确的中转站地址

## 故障排查

### 错误：Configuration errors: ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude

**解决方案**：确保在 `.env` 文件中设置了 `ANTHROPIC_API_KEY`

### 错误：Configuration errors: DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek

**解决方案**：确保在 `.env` 文件中设置了 `DEEPSEEK_API_KEY`

### 错误：LLM_PROVIDER must be 'deepseek', 'claude', or 'anthropic'

**解决方案**：确保 `LLM_PROVIDER` 的值是 `deepseek`、`claude` 或 `anthropic`（不区分大小写）
- `claude` 和 `anthropic` 是等价的，都会使用 Anthropic Claude API

