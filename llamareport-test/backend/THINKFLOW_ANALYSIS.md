# Thinkflow 架构分析与改进方案

## 一、现有系统架构分析

### 1.1 当前系统结构

```
用户请求
    ↓
FastAPI (API层)
    ├─ /query/ask → RAGEngine → VisualizationAgent
    ├─ /agent/query → ReportAgent (FunctionAgent)
    └─ /agent/generate-report → ReportAgent
    ↓
Agent层
    ├─ ReportAgent (使用 LlamaIndex FunctionAgent)
    │   └─ 工具选择：通过 FunctionAgent 的自动工具选择
    └─ VisualizationAgent (独立 Agent)
        └─ 固定流程：需求分析 → 类型分类 → 数据提取 → 图表推荐 → 配置生成
    ↓
工具层 (agents/report_tools.py)
    ├─ generate_financial_review()
    ├─ generate_business_guidance()
    ├─ generate_business_highlights()
    ├─ generate_profit_forecast_and_valuation()
    ├─ retrieve_financial_data()
    └─ generate_dupont_analysis()
    ↓
核心层
    ├─ RAGEngine (文档检索)
    ├─ DocumentProcessor (文档处理)
    └─ TableExtractor (表格提取)
```

### 1.2 现有系统的优势

1. **已有 Agent 架构**：ReportAgent 使用 FunctionAgent，具备工具选择能力
2. **已有工具抽象**：report_tools.py 中的工具函数已经具备 Atomic Skill 的特征
3. **已有路由机制**：通过 FunctionAgent 的 system_prompt 指导工具选择
4. **已有问题分类**：VisualizationAgent 中有问题类型分类逻辑
5. **已有可视化流程**：完整的可视化生成流程

### 1.3 现有系统的不足（对比 Thinkflow 理念）

#### 1.3.1 缺少认知路由层（SKILL.md）
- **现状**：路由逻辑硬编码在 system_prompt 中
- **问题**：无法复用"专家如何判断问题"的思维结构
- **影响**：每次修改需要改代码，无法沉淀决策知识

#### 1.3.2 缺少 Thinkflow 执行文档（references/thinkflow.md）
- **现状**：执行步骤散落在代码中（VisualizationAgent 的 8 个步骤）
- **问题**：没有明确的 Checklist、Steps、Feedback Loops 文档化
- **影响**：无法复用"在什么情况下，应该如何思考和权衡"

#### 1.3.3 Atomic Skill 边界不清晰
- **现状**：工具函数混合了数据获取、处理、生成等多个职责
- **问题**：行为不够确定，边界不够清晰
- **影响**：上层推理需要处理执行细节的不确定性

#### 1.3.4 缺少 Feedback Loops
- **现状**：没有自我反思机制
- **问题**：无法校验结果的逻辑自洽性
- **影响**：错误难以发现和纠正

#### 1.3.5 执行路径固定
- **现状**：VisualizationAgent 有固定的 8 步流程
- **问题**：假设"有一个最优流程"，无法根据上下文动态选择路径
- **影响**：无法允许多种判断路径并存

---

## 二、Thinkflow 改进方案

### 2.1 整体架构设计

```
用户意图
    ↓
SKILL.md（认知路由：走哪条路）
    ├─ Scope：意图识别（这是哪一类问题）
    ├─ Knowledge Injection：认知注入（行业术语/专家推理方式/约束条件）
    └─ Adaptive Routing：路由决策（该走哪条分析路径）
    ↓
references/thinkflow.md（怎么走）
    ├─ Checklist：执行前要制定的每一步checklist
    ├─ Steps：具体的执行步骤（Thinkflow 调用底层能力的接口）
    └─ Feedback Loops：自我反思机制（校验结果的逻辑自洽性）
    ↓
Atomic Skills / Tools / Data（具体怎么做）
    ├─ 数据获取类：retrieve_financial_data, retrieve_business_data
    ├─ 内容处理类：extract_table_data, parse_financial_data
    ├─ 结构化写入类：generate_financial_review, generate_business_guidance
    └─ 可视化生成类：generate_chart_config, generate_timeline_data
```

### 2.2 改进步骤

#### 步骤 1：创建 SKILL.md 文档结构

**位置**：`llamareport-test/backend/skills/`

**文件结构**：
```
skills/
├── financial_analysis.md      # 财务分析技能
├── business_analysis.md       # 业务分析技能
├── visualization.md           # 可视化技能
├── dupont_analysis.md         # 杜邦分析技能
└── general_query.md           # 通用查询技能
```

**每个 SKILL.md 包含**：
1. **Scope**：意图识别和边界定义
   - 这是哪一类问题？
   - 能做 / 不能做什么？
   - 防止模型幻觉和越权

2. **Knowledge Injection**：认知注入
   - 行业术语（财务术语、业务术语）
   - 专家常用的推理方式
   - 约束条件（如各阶段预算比例、分析标准）

3. **Adaptive Routing**：路由决策
   - 该走哪条分析路径？
   - 路径选择的条件判断
   - 多路径并存的可能性

#### 步骤 2：创建 references/thinkflow.md 文档

**位置**：`llamareport-test/backend/references/`

**文件结构**：
```
references/
├── thinkflow/
│   ├── financial_analysis_thinkflow.md
│   ├── business_analysis_thinkflow.md
│   ├── visualization_thinkflow.md
│   └── dupont_analysis_thinkflow.md
└── examples/
    └── (示例数据)
```

**每个 thinkflow.md 包含**：
1. **Checklist**：执行前要制定的每一步checklist
   - 数据完整性检查
   - 前置条件验证
   - 资源准备

2. **Steps**：具体的执行步骤
   - 这是 Thinkflow 调用底层能力的接口
   - 每个步骤明确：输入、输出、调用的 Atomic Skill
   - 步骤之间的依赖关系

3. **Feedback Loops**：自我反思机制
   - 结果验证规则
   - 逻辑自洽性检查
   - 错误纠正机制

#### 步骤 3：重构 Atomic Skills

**目标**：将现有工具函数重构为边界清晰、行为确定的 Atomic Skill

**重构原则**：
1. **单一职责**：每个 Atomic Skill 只做一件事
2. **确定性**：输入确定，输出确定，行为确定
3. **边界清晰**：明确的输入输出接口，明确的错误处理

**Atomic Skills 分类**：

**A. 数据获取类**
- `retrieve_financial_data(query, filters) -> FinancialData`
- `retrieve_business_data(query, filters) -> BusinessData`
- `extract_table_data(document_id, table_id) -> TableData`
- `query_rag_engine(query, context) -> RAGResult`

**B. 内容处理类**
- `parse_financial_data(raw_data) -> StructuredFinancialData`
- `extract_visualization_data(text, sources) -> VisualizationData`
- `classify_question_type(query, answer) -> QuestionType`
- `validate_data_completeness(data) -> ValidationResult`

**C. 结构化写入类**
- `generate_financial_review(data) -> FinancialReview`
- `generate_business_guidance(data) -> BusinessGuidance`
- `generate_business_highlights(data) -> BusinessHighlights`
- `generate_profit_forecast(data) -> ProfitForecast`

**D. 可视化生成类**
- `generate_chart_config(data, chart_type) -> ChartConfig`
- `generate_timeline_data(events) -> TimelineData`
- `recommend_chart_type(data, question_type) -> ChartRecommendation`

#### 步骤 4：创建 Thinkflow 执行引擎

**位置**：`llamareport-test/backend/core/thinkflow_engine.py`

**功能**：
1. **加载 SKILL.md**：解析技能文档，提取 Scope、Knowledge、Routing
2. **加载 thinkflow.md**：解析执行步骤，提取 Checklist、Steps、Feedback
3. **执行 Thinkflow**：
   - 根据用户意图选择 SKILL
   - 根据 SKILL 的 Routing 选择 Thinkflow
   - 执行 Thinkflow 的 Steps（调用 Atomic Skills）
   - 执行 Feedback Loops（验证结果）

**核心方法**：
```python
class ThinkflowEngine:
    async def route_intent(self, user_query: str) -> Skill:
        """根据用户意图选择 SKILL"""
        
    async def select_thinkflow(self, skill: Skill, context: Dict) -> Thinkflow:
        """根据 SKILL 的 Routing 选择 Thinkflow"""
        
    async def execute_thinkflow(self, thinkflow: Thinkflow, context: Dict) -> Result:
        """执行 Thinkflow 的 Steps"""
        
    async def validate_result(self, result: Result, thinkflow: Thinkflow) -> ValidationResult:
        """执行 Feedback Loops"""
```

#### 步骤 5：重构现有 Agent

**目标**：将现有 Agent 改为基于 Thinkflow 的执行方式

**ReportAgent 重构**：
- 移除硬编码的 system_prompt
- 改为加载 SKILL.md 和 thinkflow.md
- 使用 ThinkflowEngine 执行

**VisualizationAgent 重构**：
- 将固定的 8 步流程改为 thinkflow.md 中的 Steps
- 将问题类型分类改为 SKILL.md 中的 Routing
- 添加 Feedback Loops 验证

#### 步骤 6：实现 Feedback Loops

**位置**：`llamareport-test/backend/core/feedback_loops.py`

**功能**：
1. **结果验证**：检查结果是否符合预期格式
2. **逻辑自洽性检查**：检查数据之间的逻辑关系
3. **错误纠正**：发现错误后自动纠正或提示

**示例**：
- 财务数据验证：检查数值是否合理（如利润率不能超过100%）
- 可视化数据验证：检查数据是否足够生成图表
- 文本生成验证：检查生成内容是否包含必要信息

---

## 三、具体改进内容

### 3.1 文件结构变更

**新增文件**：
```
llamareport-test/backend/
├── skills/                          # 新增：SKILL.md 文档目录
│   ├── __init__.py
│   ├── financial_analysis.md
│   ├── business_analysis.md
│   ├── visualization.md
│   ├── dupont_analysis.md
│   └── general_query.md
├── references/                      # 新增：thinkflow.md 文档目录
│   ├── thinkflow/
│   │   ├── financial_analysis_thinkflow.md
│   │   ├── business_analysis_thinkflow.md
│   │   ├── visualization_thinkflow.md
│   │   └── dupont_analysis_thinkflow.md
│   └── examples/
├── core/
│   ├── thinkflow_engine.py         # 新增：Thinkflow 执行引擎
│   └── feedback_loops.py            # 新增：Feedback Loops 实现
└── agents/
    ├── atomic_skills/               # 新增：Atomic Skills 目录
    │   ├── __init__.py
    │   ├── data_retrieval.py        # 数据获取类
    │   ├── content_processing.py   # 内容处理类
    │   ├── structured_generation.py # 结构化写入类
    │   └── visualization.py        # 可视化生成类
    ├── report_agent.py              # 重构：基于 Thinkflow
    └── visualization_agent.py      # 重构：基于 Thinkflow
```

### 3.2 代码重构内容

#### 3.2.1 重构 agents/report_tools.py

**现状**：工具函数混合了多个职责

**改进**：拆分为 Atomic Skills
- `retrieve_financial_data()` → `atomic_skills/data_retrieval.py::retrieve_financial_data()`
- `generate_financial_review()` → 拆分为：
  - `atomic_skills/data_retrieval.py::retrieve_financial_data()`
  - `atomic_skills/content_processing.py::parse_financial_data()`
  - `atomic_skills/structured_generation.py::generate_financial_review()`

#### 3.2.2 重构 agents/report_agent.py

**现状**：硬编码的 system_prompt，通过 FunctionAgent 自动选择工具

**改进**：
1. 移除硬编码的 system_prompt
2. 加载 SKILL.md（financial_analysis.md）获取 Scope、Knowledge、Routing
3. 使用 ThinkflowEngine 执行 Thinkflow
4. 根据 Thinkflow 的 Steps 调用 Atomic Skills

#### 3.2.3 重构 agents/visualization_agent.py

**现状**：固定的 8 步流程

**改进**：
1. 将 8 步流程提取到 `references/thinkflow/visualization_thinkflow.md`
2. 将问题类型分类逻辑提取到 `skills/visualization.md` 的 Routing 部分
3. 使用 ThinkflowEngine 执行 Thinkflow
4. 添加 Feedback Loops 验证

---

## 四、实施步骤（按优先级）

### 阶段 1：基础架构（优先级：高）

1. **创建目录结构**
   - 创建 `skills/` 目录
   - 创建 `references/thinkflow/` 目录
   - 创建 `agents/atomic_skills/` 目录

2. **创建 ThinkflowEngine 框架**
   - 实现文档加载（SKILL.md、thinkflow.md）
   - 实现基本的执行流程

3. **创建第一个 SKILL.md 示例**
   - 选择 `visualization.md`（因为流程最清晰）
   - 包含 Scope、Knowledge Injection、Adaptive Routing

4. **创建第一个 thinkflow.md 示例**
   - 选择 `visualization_thinkflow.md`
   - 包含 Checklist、Steps、Feedback Loops

### 阶段 2：Atomic Skills 重构（优先级：高）

1. **重构数据获取类**
   - 将 `retrieve_financial_data()` 等函数移到 `atomic_skills/data_retrieval.py`
   - 确保边界清晰、行为确定

2. **重构内容处理类**
   - 将 `parse_financial_data()` 等函数移到 `atomic_skills/content_processing.py`
   - 确保输入输出明确

3. **重构结构化写入类**
   - 将 `generate_financial_review()` 等函数移到 `atomic_skills/structured_generation.py`
   - 确保职责单一

4. **重构可视化生成类**
   - 将可视化相关函数移到 `atomic_skills/visualization.py`
   - 确保行为确定

### 阶段 3：Agent 重构（优先级：中）

1. **重构 VisualizationAgent**
   - 移除固定流程代码
   - 改为加载 `visualization_thinkflow.md` 执行
   - 添加 Feedback Loops

2. **重构 ReportAgent**
   - 移除硬编码 system_prompt
   - 改为加载 SKILL.md 和 thinkflow.md
   - 使用 ThinkflowEngine 执行

### 阶段 4：完善和优化（优先级：低）

1. **完善所有 SKILL.md**
   - 创建 financial_analysis.md
   - 创建 business_analysis.md
   - 创建 dupont_analysis.md
   - 创建 general_query.md

2. **完善所有 thinkflow.md**
   - 创建对应的 thinkflow 文档
   - 完善 Checklist、Steps、Feedback Loops

3. **实现 Feedback Loops**
   - 实现结果验证
   - 实现逻辑自洽性检查
   - 实现错误纠正

---

## 五、关键设计决策

### 5.1 SKILL.md 格式

**建议使用 Markdown + YAML Front Matter**：
```markdown
---
skill_id: visualization
skill_name: 可视化生成
version: 1.0.0
---

# 可视化生成技能

## Scope（意图识别）

### 这是哪一类问题？
- 需要生成图表的问题
- 包含数据展示需求的问题
- 需要可视化辅助理解的问题

### 能做 / 不能做
- ✅ 能：生成折线图、柱状图、饼图等
- ✅ 能：生成时间轴视图
- ❌ 不能：生成纯文本回答（应使用 general_query）
- ❌ 不能：生成合规类问题的视图

## Knowledge Injection（认知注入）

### 行业术语
- 财务指标：ROE、ROA、毛利率、净利率
- 业务术语：营收、利润、现金流

### 专家推理方式
- 趋势分析：优先使用折线图
- 对比分析：优先使用柱状图
- 占比分析：优先使用饼图

### 约束条件
- 数据完整性：至少需要 2 个数据点才能生成图表
- 时间范围：最多展示 5 年数据

## Adaptive Routing（路由决策）

### 路径选择条件
1. **问题类型 = process** → 走时间轴路径
2. **问题类型 = risk** → 走风险矩阵路径
3. **问题类型 = data** → 走数据图表路径
4. **问题类型 = compliance** → 不走可视化路径

### 多路径并存
- 可以同时生成时间轴 + 数据图表
- 可以同时生成多个数据图表（如趋势图 + 对比图）
```

### 5.2 thinkflow.md 格式

**建议使用 Markdown + YAML Front Matter**：
```markdown
---
thinkflow_id: visualization
thinkflow_name: 可视化生成流程
skill_id: visualization
version: 1.0.0
---

# 可视化生成流程

## Checklist（执行前检查）

- [ ] 用户查询是否包含可视化需求？
- [ ] 回答中是否包含数据？
- [ ] 问题类型是否不是 compliance？
- [ ] 数据来源是否可用？

## Steps（执行步骤）

### Step 1: 分析可视化需求
- **输入**：query, answer
- **输出**：needs_visualization (bool)
- **调用 Atomic Skill**：`classify_question_type(query, answer)`
- **判断条件**：如果问题类型是 compliance，返回 False

### Step 2: 提取数据
- **输入**：query, answer, sources, question_type
- **输出**：extracted_data (Dict)
- **调用 Atomic Skill**：
  - `extract_table_data(sources)` （优先）
  - `extract_visualization_data(text, sources)` （备选）
- **判断条件**：如果 has_data = False，终止流程

### Step 3: 推荐图表类型
- **输入**：query, data, answer, question_type
- **输出**：chart_recommendation (ChartRecommendation)
- **调用 Atomic Skill**：`recommend_chart_type(data, question_type)`

### Step 4: 生成图表配置
- **输入**：chart_type, data, query, question_type
- **输出**：chart_config (PlotlyChartConfig)
- **调用 Atomic Skill**：`generate_chart_config(data, chart_type)`

## Feedback Loops（自我反思）

### 验证规则 1：数据完整性
- **检查**：extracted_data.has_data == True
- **如果不满足**：返回无可视化响应

### 验证规则 2：图表配置有效性
- **检查**：chart_config.traces 不为空
- **如果不满足**：降级为简单图表或返回错误

### 验证规则 3：逻辑自洽性
- **检查**：图表数据与文本答案一致
- **如果不满足**：记录警告，但继续执行
```

### 5.3 ThinkflowEngine 设计

```python
class ThinkflowEngine:
    """Thinkflow 执行引擎"""
    
    def __init__(self):
        self.skills = {}  # skill_id -> Skill
        self.thinkflows = {}  # thinkflow_id -> Thinkflow
        self.atomic_skills = {}  # skill_name -> AtomicSkill
        
    async def load_skill(self, skill_path: str) -> Skill:
        """加载 SKILL.md"""
        
    async def load_thinkflow(self, thinkflow_path: str) -> Thinkflow:
        """加载 thinkflow.md"""
        
    async def register_atomic_skill(self, skill: AtomicSkill):
        """注册 Atomic Skill"""
        
    async def route_intent(self, user_query: str) -> Skill:
        """根据用户意图选择 SKILL"""
        # 1. 遍历所有 SKILL，检查 Scope
        # 2. 选择匹配的 SKILL
        
    async def select_thinkflow(self, skill: Skill, context: Dict) -> Thinkflow:
        """根据 SKILL 的 Routing 选择 Thinkflow"""
        # 1. 根据 Adaptive Routing 规则选择
        # 2. 支持多路径并存
        
    async def execute_thinkflow(self, thinkflow: Thinkflow, context: Dict) -> Result:
        """执行 Thinkflow 的 Steps"""
        # 1. 执行 Checklist
        # 2. 按顺序执行 Steps
        # 3. 每个 Step 调用对应的 Atomic Skill
        # 4. 执行 Feedback Loops
        
    async def validate_result(self, result: Result, thinkflow: Thinkflow) -> ValidationResult:
        """执行 Feedback Loops"""
        # 1. 执行所有验证规则
        # 2. 检查逻辑自洽性
        # 3. 返回验证结果
```

---

## 六、预期收益

### 6.1 可复用性提升
- **现状**：决策逻辑硬编码在代码中，无法复用
- **改进后**：决策逻辑沉淀在 SKILL.md 和 thinkflow.md 中，可以复用

### 6.2 可维护性提升
- **现状**：修改决策逻辑需要改代码
- **改进后**：修改决策逻辑只需修改文档，无需改代码

### 6.3 可扩展性提升
- **现状**：添加新功能需要修改 Agent 代码
- **改进后**：添加新功能只需添加新的 SKILL.md 和 thinkflow.md

### 6.4 可解释性提升
- **现状**：决策过程不透明
- **改进后**：决策过程完全可追溯（SKILL → Thinkflow → Atomic Skills）

### 6.5 灵活性提升
- **现状**：执行路径固定
- **改进后**：执行路径可以根据上下文动态选择，允许多路径并存

---

## 七、风险评估

### 7.1 技术风险
- **风险**：ThinkflowEngine 实现复杂度较高
- **缓解**：分阶段实施，先实现基础框架，再逐步完善

### 7.2 兼容性风险
- **风险**：重构可能影响现有功能
- **缓解**：保持 API 接口不变，内部重构

### 7.3 性能风险
- **风险**：文档加载和解析可能影响性能
- **缓解**：使用缓存机制，预加载常用 SKILL 和 Thinkflow

---

## 八、总结

### 8.1 核心改进点
1. **引入 SKILL.md**：沉淀"专家如何判断问题"的思维结构
2. **引入 thinkflow.md**：沉淀"在什么情况下，应该如何思考和权衡"
3. **重构 Atomic Skills**：确保边界清晰、行为确定
4. **实现 ThinkflowEngine**：支持动态路径选择和多路径并存
5. **实现 Feedback Loops**：校验结果的逻辑自洽性

### 8.2 实施建议
1. **先做基础架构**：创建目录结构、实现 ThinkflowEngine 框架
2. **先做示例**：选择一个流程清晰的技能（如 visualization）作为示例
3. **逐步迁移**：将现有功能逐步迁移到 Thinkflow 架构
4. **保持兼容**：在迁移过程中保持 API 接口不变

### 8.3 关键成功因素
1. **文档质量**：SKILL.md 和 thinkflow.md 的质量直接影响系统效果
2. **Atomic Skills 设计**：确保边界清晰、行为确定
3. **ThinkflowEngine 实现**：确保执行效率和灵活性
4. **Feedback Loops 设计**：确保能够发现和纠正错误

---

**注意**：本文档仅提供分析和改进方案，不包含具体代码实现。具体代码实现需要根据实际需求进行调整。


