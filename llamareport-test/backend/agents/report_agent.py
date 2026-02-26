"""
年报分析 Agent 主配置
使用 FunctionAgent 协调各个工具生成完整报告
"""

import logging
import re
import warnings
from typing import Dict, Any, Optional
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.core import Settings
from llama_index.core.llms import ChatMessage

# 忽略Pydantic JSON schema警告（query_engine参数通过partial绑定，不需要序列化）
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.json_schema")
from models.report_models import AnnualReportAnalysis
from agents.financial_review import generate_financial_review
from agents.business_guidance import generate_business_guidance
from agents.business_highlights import generate_business_highlights
from agents.report_tools import generate_profit_forecast_and_valuation
from agents.report_common import retrieve_financial_data, retrieve_business_data
from agents.visualization_agent import generate_visualization_for_query
from agents.dupont_tools import generate_dupont_analysis

logger = logging.getLogger(__name__)


class ReportAgent:
    """年报分析 Agent"""

    def __init__(self, query_engine):
        """
        初始化 Agent

        Args:
            query_engine: LlamaIndex 查询引擎
        """
        self.query_engine = query_engine
        self.agent = None
        self._setup_agent()

    def _serialize_tool_output(self, tool_output) -> Any:
        """
        将ToolOutput对象转换为可JSON序列化的格式

        Args:
            tool_output: ToolOutput对象或其他类型

        Returns:
            可序列化的数据（dict, str, list等）
        """
        try:
            # 如果是字符串，检查是否是JSON字符串，如果是则解析
            if isinstance(tool_output, str):
                # 如果字符串看起来像JSON，尝试解析
                if tool_output.strip().startswith(('{', '[')):
                    try:
                        import json
                        parsed = json.loads(tool_output)
                        # 递归处理解析后的内容
                        return self._serialize_tool_output(parsed)
                    except (json.JSONDecodeError, ValueError):
                        pass
                # 普通字符串直接返回
                return tool_output

            # 处理 Decimal 类型（转换为 float 以便 JSON 序列化）
            try:
                from decimal import Decimal
                if isinstance(tool_output, Decimal):
                    return float(tool_output)
            except ImportError:
                pass
            
            # 如果是数字、布尔值、None，直接返回
            if isinstance(tool_output, (int, float, bool, type(None))):
                return tool_output

            # 如果是列表或元组，递归序列化每个元素
            if isinstance(tool_output, (list, tuple)):
                return [self._serialize_tool_output(item) for item in tool_output]

            # 如果是字典，递归序列化每个值
            if isinstance(tool_output, dict):
                return {key: self._serialize_tool_output(value) for key, value in tool_output.items()}

            # 如果有dict()方法（Pydantic模型等）
            if hasattr(tool_output, 'dict'):
                try:
                    return tool_output.dict()
                except Exception as e:
                    logger.debug(f"Failed to call dict() on {type(tool_output)}: {e}")
                    pass

            # 如果有model_dump()方法（Pydantic v2）
            if hasattr(tool_output, 'model_dump'):
                try:
                    return tool_output.model_dump()
                except Exception as e:
                    logger.debug(f"Failed to call model_dump() on {type(tool_output)}: {e}")
                    pass

            # 如果有model_dump_json()方法，先转换为JSON字符串再解析
            if hasattr(tool_output, 'model_dump_json'):
                try:
                    import json
                    json_str = tool_output.model_dump_json()
                    return json.loads(json_str)
                except Exception as e:
                    logger.debug(f"Failed to call model_dump_json() on {type(tool_output)}: {e}")
                    pass

            # 如果有__dict__属性
            if hasattr(tool_output, '__dict__'):
                try:
                    return {k: self._serialize_tool_output(v) for k, v in tool_output.__dict__.items() if not k.startswith('_')}
                except Exception as e:
                    logger.debug(f"Failed to access __dict__ on {type(tool_output)}: {e}")
                    pass

            # 最后尝试转换为字符串
            return str(tool_output)

        except Exception as e:
            logger.warning(f"Failed to serialize tool_output: {str(e)}, converting to string")
            return str(tool_output)
    
    def _setup_agent(self):
        """设置 Agent 和工具"""
        try:
            # 1. 创建 QueryEngineTool (用于基础数据检索)
            query_tool = QueryEngineTool.from_defaults(
                query_engine=self.query_engine,
                name="annual_report_query",
                description=(
                    "用于从年报中检索基础信息的工具。"
                    "可以查询财务数据、业务数据、公司信息等。"
                    "输入应该是一个自然语言查询。"
                )
            )
            
            # 2. 创建专门的章节生成工具
            # 注意: 这些工具需要 query_engine 参数,我们使用 partial 来绑定
            from functools import partial
            
            financial_review_tool = FunctionTool.from_defaults(
                fn=partial(generate_financial_review, query_engine=self.query_engine),
                name="generate_financial_review",
                description=(
                    "生成财务点评章节。"
                    "需要参数: company_name(公司名称), year(年份)。"
                    "返回包含财务图表、业绩速览、业绩对比、指标归因的结构化数据。"
                )
            )
            
            business_guidance_tool = FunctionTool.from_defaults(
                fn=partial(generate_business_guidance, query_engine=self.query_engine),
                name="generate_business_guidance",
                description=(
                    "生成业绩指引章节。"
                    "需要参数: company_name(公司名称), year(年份)。"
                    "返回包含业绩预告、经营计划、风险提示的结构化数据。"
                )
            )
            
            business_highlights_tool = FunctionTool.from_defaults(
                fn=partial(generate_business_highlights, query_engine=self.query_engine),
                name="generate_business_highlights",
                description=(
                    "生成业务亮点章节。"
                    "需要参数: company_name(公司名称), year(年份)。"
                    "返回各业务板块的亮点和成就。"
                )
            )
            
            profit_forecast_tool = FunctionTool.from_defaults(
                fn=partial(generate_profit_forecast_and_valuation, query_engine=self.query_engine),
                name="generate_profit_forecast_and_valuation",
                description=(
                    "生成投资策略章节（包含相关性分析、聚类分析和因子分析）。"
                    "需要参数: company_name(公司名称), year(年份)。"
                    "返回指标抽取、相关性分析、因子分析、聚类分析与投资策略结论的结构化数据。"
                )
            )
            
            # 3. 创建数据检索辅助工具
            financial_data_tool = FunctionTool.from_defaults(
                fn=partial(retrieve_financial_data, query_engine=self.query_engine),
                name="retrieve_financial_data",
                description=(
                    "检索特定的财务数据。"
                    "需要参数: company_name(公司名称), year(年份), "
                    "metric_type(指标类型: revenue/profit/cash_flow/balance_sheet)。"
                )
            )
            
            business_data_tool = FunctionTool.from_defaults(
                fn=partial(retrieve_business_data, query_engine=self.query_engine),
                name="retrieve_business_data",
                description=(
                    "检索业务相关数据。"
                    "需要参数: company_name(公司名称), year(年份), business_type(业务类型)。"
                )
            )

            # 可视化生成工具
            visualization_tool = FunctionTool.from_defaults(
                fn=generate_visualization_for_query,
                name="generate_visualization",
                description=(
                    "为查询和回答生成可视化图表。"
                    "需要参数: query(用户查询), answer(文本回答)。"
                    "可选参数: data(原始数据), sources(数据来源)。"
                    "返回包含图表配置的可视化响应。"
                )
            )

            # 杜邦分析工具（新增）
            dupont_analysis_tool = FunctionTool.from_defaults(
                fn=partial(generate_dupont_analysis, query_engine=self.query_engine),
                name="generate_dupont_analysis",
                description=(
                    "生成杜邦分析报告。"
                    "杜邦分析将净资产收益率(ROE)分解为资产净利率、资产周转率和权益乘数，"
                    "帮助深入理解公司盈利能力的驱动因素。"
                    "需要参数: company_name(公司名称), year(年份)。"
                    "返回包含ROE分解、各层级指标、可视化图表的结构化数据。"
                )
            )

            # 4. 组装所有工具
            tools = [
                query_tool,
                financial_review_tool,
                business_guidance_tool,
                business_highlights_tool,
                profit_forecast_tool,
                financial_data_tool,
                business_data_tool,
                visualization_tool,  # 可视化工具
                dupont_analysis_tool  # 杜邦分析工具（新增）
            ]
            
            # 5. 创建 FunctionAgent
            system_prompt = """
你是一个资深的财务分析专家和年报分析师，拥有20年以上的行业经验。你的任务是生成高质量、专业、深入的年报分析报告。

## 查询模式说明
系统支持两种查询模式：
1. **通用查询模式**（输入框输入）：用户通过输入框提问，优先使用 `annual_report_query` 工具进行基础查询，快速回答用户问题。只有在用户明确要求生成完整章节时，才调用生成工具。
2. **章节生成模式**（按钮点击）：用户点击特定按钮（如"财务点评"、"业绩指引"等），直接调用对应的生成工具生成完整章节。

## 核心职责
1. **深度理解用户需求**：准确理解用户的分析意图，识别关键分析维度
2. **精准数据检索**：使用工具从年报中提取准确、完整的财务和业务数据
3. **专业分析生成**：基于真实数据生成客观、专业、有洞察力的分析报告
4. **智能可视化**：在适当时机生成图表，直观展示数据趋势和对比
5. **深度财务分析**：当涉及盈利能力分析时，使用杜邦分析工具进行ROE分解

## 报告结构（标准五部分）
一、**财务点评** (使用 generate_financial_review 工具)
   - 财务点评总结：覆盖资产、负债、利润、现金流关键变化
   - 可视化表格：资产结构表、负债结构表、营业收入结构表、营业支出结构表、现金流量明细

二、**业绩指引** (使用 generate_business_guidance 工具)
   - 业绩预告期间和预期
   - 各业务板块的具体指引
   - 风险提示和不确定性说明

三、**业务亮点** (使用 generate_business_highlights 工具)
   - 各业务类型的核心亮点
   - 主要成就和里程碑
   - 业务创新和突破

四、**投资策略** (使用 generate_profit_forecast_and_valuation 工具)
   - 指标自动识别与输入变量表
   - 相关性分析
   - 因子分析
   - 聚类分析模型（客群-标的适配分组）
   - 综合投资策略结论与风险提示

五、**综合总结**
   - 基于前四部分生成综合性的投资建议
   - 突出核心观点和关键洞察
   - 提供风险提示和机会分析

## 工作流程（智能执行 - 严格遵循）
⚠️ **关键原则：每个工具内部已经包含了数据检索，不要重复调用检索工具！**

### 🚫 禁止的操作（避免重复检索）
1. **不要**在调用生成工具前先调用 `annual_report_query` 或 `retrieve_financial_data`
2. **不要**在调用 `generate_financial_review` 前先调用 `retrieve_financial_data`（工具内部已包含）
3. **不要**在调用 `generate_business_guidance` 前先调用 `annual_report_query`（工具内部已包含）
4. **不要**为了简单问题调用所有生成工具

### ✅ 正确的调用方式

#### 通用查询模式（输入框输入 - 快速响应）
- **优先使用** `annual_report_query` 工具进行基础查询，快速回答用户问题
- 如果用户只是询问基本信息（如"公司名称"、"报告年份"、"基本财务数据"、"收入情况"等），**只调用** `annual_report_query` 工具
- **不要**自动调用生成工具（generate_*），除非用户明确要求生成完整章节（如"生成财务点评"、"生成业绩指引"等）
- 这样可以保持快速响应（5-10秒内完成），避免不必要的长时间等待

#### 特定分析需求（按需调用 - 30-60秒）
- **财务分析相关**：**只调用** `generate_financial_review`（工具内部会自动检索数据，无需额外调用）
- **业绩指引相关**：**只调用** `generate_business_guidance`（工具内部会自动检索数据）
- **业务亮点相关**：**只调用** `generate_business_highlights`（工具内部会自动检索数据）
- **投资策略相关**：**只调用** `generate_profit_forecast_and_valuation`（工具内部会自动检索数据）
- **杜邦分析相关**：**只调用** `generate_dupont_analysis`（工具内部会自动检索数据）
- **可视化需求**：在生成分析后，**只调用** `generate_visualization`

#### 完整报告需求（按顺序调用 - 最多调用4个工具）
**只有在用户明确要求"完整报告"、"生成所有章节"、"全面分析"时，才按以下顺序调用：**
1. **直接调用生成工具**（不要先调用 annual_report_query）：
   - `generate_financial_review` → 自动检索并生成财务点评
   - `generate_business_guidance` → 自动检索并生成业绩指引
   - `generate_business_highlights` → 自动检索并生成业务亮点
   - `generate_profit_forecast_and_valuation` → 自动检索并生成投资策略
2. **可选增强**：
   - 如涉及盈利能力，调用 `generate_dupont_analysis`
   - 识别数值数据，调用 `generate_visualization`

### ⚡ 性能优化原则（严格执行）
- ✅ **直接调用生成工具**：每个生成工具内部已包含数据检索，无需额外调用
- ✅ **避免重复检索**：不要先调用 annual_report_query 再调用生成工具
- ✅ **按需调用**：只调用与用户问题直接相关的工具
- ✅ **快速响应**：简单问题只调用 annual_report_query（5秒内完成）
- ❌ **禁止过度调用**：避免为了简单问题调用所有工具（会增加400秒+的响应时间）
- ❌ **禁止重复调用**：不要重复调用相同工具或检索相同数据

## 可视化策略
- **趋势分析**：折线图或面积图（时间序列数据）
- **对比分析**：柱状图或分组柱状图（多维度对比）
- **占比分析**：饼图或堆叠柱状图（结构分析）
- **财务指标**：分组柱状图（多指标对比）
- **聚类分析**：分组对比图（客群-标的适配分组）

## 质量要求（严格执行）
1. **数据准确性**
   - 所有数据必须来源于年报原文
   - 数据引用需标注来源和页码
   - 对缺失数据明确说明，不编造

2. **分析专业性**
   - 使用专业财务术语和分析方法
   - 提供数据支撑的结论，避免主观臆断
   - 识别关键财务风险和机会

3. **内容完整性**
   - 覆盖所有关键分析维度
   - 提供充分的背景信息和上下文
   - 确保逻辑清晰、结构完整

4. **表达清晰性**
   - 使用结构化的格式（标题、列表、表格）
   - 关键数据用数字和百分比明确表达
   - 复杂概念用通俗语言解释

5. **洞察深度**
   - 不仅描述数据，更要分析原因和影响
   - 提供前瞻性的判断和建议
   - 识别数据背后的业务逻辑

## 错误处理
- 如果某个工具调用失败，记录错误但继续执行其他部分
- 如果数据缺失，明确说明并基于可用数据进行分析
- 如果分析遇到困难，使用 annual_report_query 获取更多上下文

## 输出格式
- 使用Markdown格式，包含标题、列表、表格等
- 关键数据用**粗体**或数字突出显示
- 使用emoji增强可读性（但不过度使用）
- 确保输出可以直接用于报告或演示
"""
            
            self.agent = FunctionAgent(
                tools=tools,
                llm=Settings.llm,
                system_prompt=system_prompt,
                name="annual_report_analyst",
                verbose=True
            )
            
            logger.info("✅ ReportAgent 初始化成功")
            
        except Exception as e:
            logger.error(f"❌ ReportAgent 初始化失败: {str(e)}")
            raise
    
    async def generate_report(
        self,
        company_name: str,
        year: str,
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成完整的年报分析报告
        
        Args:
            company_name: 公司名称
            year: 年份
            user_query: 用户的自定义查询(可选)
        
        Returns:
            完整的年报分析报告
        """
        try:
            logger.info(f"开始生成年报分析: {company_name} {year}年")
            
            # 构建查询
            if user_query:
                query = user_query
            else:
                query = f"请生成{company_name} {year}年的完整年报分析报告,包括财务点评、业绩指引、业务亮点、投资策略（包含相关性分析、聚类分析和因子分析）、以及总结。"
            
            # 运行 Agent
            response = await self.agent.run(query)
            
            logger.info(f"✅ 年报分析生成成功")
            
            return {
                "status": "success",
                "company_name": company_name,
                "year": year,
                "report": str(response),
                "structured_response": response.structured_response if hasattr(response, 'structured_response') else None
            }
            
        except Exception as e:
            logger.error(f"❌ 生成年报分析失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "company_name": company_name,
                "year": year
            }
    
    async def generate_section(
        self,
        section_name: str,
        company_name: str,
        year: str,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成单个章节
        
        Args:
            section_name: 章节名称 (financial_review, business_guidance, business_highlights, profit_forecast)
            company_name: 公司名称
            year: 年份
        
        Returns:
            章节内容
        """
        try:
            logger.info(f"开始生成章节: {section_name}")
            
            section_map = {
                "financial_review": "财务点评",
                "business_guidance": "业绩指引",
                "business_highlights": "业务亮点",
                "profit_forecast": "投资策略（包含相关性分析、聚类分析、因子分析和盈利预测）"
            }
            
            section_chinese = section_map.get(section_name, section_name)
            query = f"请生成{company_name} {year}年的{section_chinese}章节。"
            if section_name == "profit_forecast" and model_type:
                query = f"{query} 优先使用{model_type}模型。"
            
            # 投资策略支持模型选择，直接调用工具避免模型参数丢失
            # 默认使用 "all" 执行所有分析（相关性、聚类、因子分析）
            if section_name == "profit_forecast":
                effective_model_type = model_type or "all"
                tool_output = await generate_profit_forecast_and_valuation(
                    company_name=company_name,
                    year=year,
                    query_engine=self.query_engine,
                    model_type=effective_model_type
                )
                summary_text = None
                if isinstance(tool_output, dict):
                    # 盈利预测模式：直接返回完整预测报告
                    if effective_model_type == "earnings_forecast":
                        earnings_report = tool_output.get("earnings_forecast_report")
                        if isinstance(earnings_report, str) and earnings_report.strip():
                            summary_text = earnings_report.strip()
                        else:
                            summary_text = tool_output.get("notes") or ""

                    # 非盈利预测模式：按投资策略结果组装摘要
                    if effective_model_type != "earnings_forecast":
                        # 优先使用综合洞察
                        comprehensive_insight = tool_output.get("comprehensive_insight")
                        if comprehensive_insight:
                            summary_text = comprehensive_insight
                        else:
                        # 如果没有综合洞察，使用策略结论（保持分段格式，便于前端展示）
                            conclusion = tool_output.get("strategy_conclusion") or {}
                            parts = []
                            short_term = conclusion.get("short_term")
                            long_term = conclusion.get("long_term")
                            risk_control = conclusion.get("risk_control")
                            key_signals = conclusion.get("key_signals") or []
                            if short_term:
                                parts.append(f"**短期配置：**\n{short_term}")
                            if long_term:
                                parts.append(f"**长期配置：**\n{long_term}")
                            if risk_control:
                                parts.append(f"**风险管控：**\n{risk_control}")
                            if isinstance(key_signals, list) and key_signals:
                                lines = "\n".join(f"- {s}" for s in key_signals if s)
                                parts.append(f"**关键信号：**\n{lines}")
                            # 如果有因子分析结果：优先展示完整报告（含数据表、载荷表、方差表、得分表、第四步洞察），否则展示因子+方差+解读摘要
                            factor_analysis = tool_output.get("factor_analysis") or {}
                            if factor_analysis:
                                full_report = factor_analysis.get("full_report")
                                if isinstance(full_report, str) and full_report.strip():
                                    text = full_report.strip()
                                    # 1. 去掉末尾 JSON 块，不在界面展示
                                    # 1a. 去掉末尾 ```json ... ``` 或 ```\n{...} 代码块
                                    text = re.sub(
                                        r"\n\s*```\s*json\s*\n[\s\S]*?\"factor_analysis\"[\s\S]*?```\s*$",
                                        "",
                                        text,
                                        count=1,
                                    )
                                    text = re.sub(
                                        r"\n\s*```\s*\n\s*\{[\s\S]*?\"factor_analysis\"[\s\S]*?\}\s*```\s*$",
                                        "",
                                        text,
                                        count=1,
                                    )
                                    text = text.rstrip()
                                    # 1b. 从最后一次“换行+{”起，若其后为 factor_analysis JSON，则截断
                                    for m in reversed(list(re.finditer(r"\n\s*\{", text))):
                                        tail = text[m.start() :]
                                        if '"factor_analysis"' in tail and "factor_data_sufficiency" in tail:
                                            text = text[: m.start()].rstrip()
                                            break
                                    # 1c. 若仍以 } 结尾且含 factor_analysis，从最后一个 { 前截断（兜底）
                                    if text.rstrip().endswith("}") and '"factor_analysis"' in text:
                                        last_open = text.rfind("{")
                                        if last_open != -1:
                                            tail = text[last_open:]
                                            if "factor_data_sufficiency" in tail:
                                                text = text[:last_open].rstrip()
                                    # 1d. 去掉末尾“JSON输出：”等提示，不在界面展示
                                    text = re.sub(r"\n\s*JSON输出：\s*$", "", text)
                                    text = text.rstrip()
                                    # 2. 四步标题改为简短展示
                                    text = re.sub(r"第一步：构建指标数据矩阵", "构建指标数据矩阵", text)
                                    text = re.sub(r"第二步：执行因子分析", "因子分析", text)
                                    text = re.sub(r"第三步：计算年度因子得分", "因子得分", text)
                                    text = re.sub(r"第四步：生成因子洞察报告", "因子洞察报告", text)
                                    # 3. 删去开场白（兼容：遵循/按照、对XX的指标数据/基于…对XX进行 因子分析）
                                    text = re.sub(
                                        r"^好的，作为专业投资分析师，我将严格(?:遵循|按照)您要求的四步流程[^。]*因子分析。\s*",
                                        "",
                                        text,
                                        count=1,
                                    )
                                    text = text.strip()
                                    if text:
                                        parts.append(text)
                                else:
                                    factors = factor_analysis.get("factors") or []
                                    if isinstance(factors, list) and factors:
                                        parts.append(f"**因子：**\n" + "、".join(str(f) for f in factors if f))
                                    var_exp = factor_analysis.get("variance_explained") or {}
                                    if isinstance(var_exp, dict) and var_exp:
                                        var_lines = [f"- {k}：{v}" for k, v in var_exp.items()]
                                        parts.append(f"**方差解释：**\n" + "\n".join(var_lines))
                                    interp = factor_analysis.get("interpretation")
                                    if isinstance(interp, str) and interp.strip():
                                        parts.append(f"**解读：**\n{interp.strip()}")
                            # 如果有聚类分析结果，加入聚类定位、核心发现、风险提示与分组摘要
                            clustering = tool_output.get("clustering_model") or {}
                            if clustering:
                                clustering_conclusion = clustering.get("conclusion") if isinstance(clustering, dict) else None
                                if isinstance(clustering_conclusion, dict) and clustering_conclusion.get("current_position"):
                                    parts.append(f"**聚类定位：**\n{clustering_conclusion.get('current_position')}")
                                core_insights = clustering.get("core_insights") or []
                                if isinstance(core_insights, list) and core_insights:
                                    lines = "\n".join(f"- {s}" for s in core_insights if s)
                                    parts.append(f"**核心发现：**\n{lines}")
                                risk_notes = clustering.get("risk_notes") or []
                                if isinstance(risk_notes, list) and risk_notes:
                                    lines = "\n".join(f"- {s}" for s in risk_notes if s)
                                    parts.append(f"**风险提示：**\n{lines}")
                                clusters = clustering.get("clusters") or []
                                if isinstance(clusters, list) and clusters:
                                    cluster_lines = []
                                    for c in clusters:
                                        if isinstance(c, dict):
                                            name = c.get("name") or "未命名"
                                            imp = c.get("strategy_implication") or c.get("characteristics") or ""
                                            cluster_lines.append(f"- **{name}**：{imp}")
                                    if cluster_lines:
                                        parts.append(f"**聚类分组：**\n" + "\n".join(cluster_lines))
                            summary_text = "\n\n".join(p for p in parts if p)
                return {
                    "status": "success",
                    "section_name": section_name,
                    "content": summary_text or "",
                    "structured_response": {"profit_forecast_and_valuation": tool_output},
                    "visualization": None,
                    "tool_calls": []
                }

            # 使用query管线，确保可视化与精简输出一致
            result = await self.query(query)

            # 业绩指引：如果没有可视化，则基于分析文本补充可视化（图文结合）
            if section_name == "business_guidance" and not result.get("visualization"):
                answer_text = result.get("answer") or result.get("content") or ""
                if isinstance(answer_text, str) and answer_text.strip():
                    try:
                        import asyncio
                        visualization = await asyncio.wait_for(
                            generate_visualization_for_query(
                                query=query,
                                answer=answer_text
                            ),
                            timeout=25.0
                        )
                        if isinstance(visualization, dict) and visualization.get("has_visualization"):
                            result["visualization"] = visualization
                            logger.info("✅ 业绩指引已补充可视化")
                    except Exception as viz_error:
                        logger.warning(f"⚠️ 业绩指引可视化补充失败: {viz_error}")

            # 业务亮点：如果没有可视化，则基于分析文本补充可视化（图文结合）
            if section_name == "business_highlights" and not result.get("visualization"):
                answer_text = result.get("answer") or result.get("content") or ""
                if isinstance(answer_text, str) and answer_text.strip():
                    try:
                        import asyncio
                        visualization = await asyncio.wait_for(
                            generate_visualization_for_query(
                                query=query,
                                answer=answer_text
                            ),
                            timeout=25.0
                        )
                        if isinstance(visualization, dict) and visualization.get("has_visualization"):
                            result["visualization"] = visualization
                            logger.info("✅ 业务亮点已补充可视化")
                    except Exception as viz_error:
                        logger.warning(f"⚠️ 业务亮点可视化补充失败: {viz_error}")
            
            logger.info(f"✅ 章节生成成功: {section_name}")
            
            return {
                "status": "success",
                "section_name": section_name,
                "content": result.get("answer", ""),
                "structured_response": result.get("structured_response"),
                "visualization": result.get("visualization"),
                "tool_calls": result.get("tool_calls", [])
            }
            
        except Exception as e:
            logger.error(f"❌ 生成章节失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "section_name": section_name
            }
    
    async def query(self, question: str, query_type: str = "general") -> Dict[str, Any]:
        """
        通用查询接口

        Args:
            question: 用户问题
            query_type: 查询类型，'general' (通用查询，输入框输入) 或 'section' (章节生成，按钮点击)

        Returns:
            查询结果（包含可视化数据）
        """
        import time
        query_start_time = time.time()
        try:
            logger.info(f"[Agent Query] 🚀 Starting query (type: {query_type}): {question[:100]}...")

            # 导入必要的事件类型
            from llama_index.core.agent.workflow import (
                ToolCallResult,
                ToolCall,
                AgentStream
            )
            logger.info("[Agent Query] Successfully imported event types")

            # 根据 query_type 调整查询策略
            if query_type == "general":
                # 通用查询：优先使用 annual_report_query，避免自动调用生成工具
                # 在问题前添加提示，引导 Agent 使用通用查询工具
                enhanced_question = (
                    f"【通用查询模式】用户通过输入框提问，请优先使用 annual_report_query 工具进行基础查询。"
                    f"只有在用户明确要求生成完整章节（如'生成财务点评'、'生成业绩指引'等）时，才调用对应的生成工具。"
                    f"用户问题：{question}"
                )
                logger.info(f"[Agent Query] 使用通用查询模式，增强问题提示")
            else:
                # 章节生成模式：保持原有逻辑
                enhanced_question = question
                logger.info(f"[Agent Query] 使用章节生成模式")

            # 运行 Agent 并捕获事件
            handler = self.agent.run(enhanced_question)
            logger.info("[Agent Query] Got handler, starting event stream")

            # 收集工具调用结果
            visualization_data = None
            tool_results = []
            financial_summary_override = None
            summary_override = None
            sources = []  # 收集数据来源

            # 流式处理事件以捕获工具调用结果 - 添加性能监控
            import time
            query_start_time = time.time()
            tool_call_times = {}  # 记录每个工具调用的时间
            
            try:
                async for event in handler.stream_events():
                    event_time = time.time() - query_start_time
                    logger.info(f"[Agent Query] [{event_time:.2f}s] Got event: {type(event).__name__}")

                    if isinstance(event, ToolCall):
                        tool_start_time = time.time()
                        tool_call_times[event.tool_name] = {
                            "start": tool_start_time,
                            "kwargs": event.tool_kwargs
                        }
                        logger.info(f"[Agent Query] [{event_time:.2f}s] 🔧 Tool call: {event.tool_name} with {event.tool_kwargs}")

                    elif isinstance(event, ToolCallResult):
                        tool_end_time = time.time()
                        tool_name = event.tool_name
                        
                        # 计算工具执行时间
                        if tool_name in tool_call_times:
                            tool_duration = tool_end_time - tool_call_times[tool_name]["start"]
                            logger.info(f"[Agent Query] [{event_time:.2f}s] ✅ Tool result: {tool_name} (耗时: {tool_duration:.2f}秒)")
                            
                            # 如果工具执行时间过长，发出警告
                            if tool_duration > 30.0:
                                logger.warning(f"⚠️ [{event_time:.2f}s] 工具 {tool_name} 执行时间过长: {tool_duration:.2f}秒，可能影响整体性能")
                        else:
                            logger.info(f"[Agent Query] [{event_time:.2f}s] ✅ Tool result: {tool_name}")

                        # 从工具输出中提取 sources（特别是 annual_report_query 工具）
                        if tool_name == "annual_report_query":
                            try:
                                tool_output_obj = event.tool_output
                                # 如果 tool_output 是 Response 对象，提取 source_nodes
                                if hasattr(tool_output_obj, 'source_nodes'):
                                    for node in tool_output_obj.source_nodes:
                                        source_info = {
                                            'text': node.text[:200] + "..." if len(node.text) > 200 else node.text,
                                            'metadata': getattr(node, 'metadata', {}),
                                            'score': getattr(node, 'score', 0.0)
                                        }
                                        sources.append(source_info)
                                    logger.info(f"[Agent Query] 从 {tool_name} 工具提取到 {len(tool_output_obj.source_nodes)} 个数据来源")
                            except Exception as source_extract_error:
                                logger.warning(f"[Agent Query] 从 {tool_name} 工具提取 sources 时出错: {str(source_extract_error)}")

                        try:
                            # 将ToolOutput转换为可序列化的格式
                            serialize_start = time.time()
                            
                            # 先尝试直接序列化
                            try:
                                tool_output_serializable = self._serialize_tool_output(event.tool_output)
                            except Exception as serialize_error:
                                logger.warning(f"⚠️ [{event_time:.2f}s] 工具 {tool_name} 序列化失败，使用备用方法: {str(serialize_error)}")
                                # 备用序列化方法
                                if hasattr(event.tool_output, '__dict__'):
                                    tool_output_serializable = {k: str(v) for k, v in event.tool_output.__dict__.items() if not k.startswith('_')}
                                else:
                                    tool_output_serializable = {"raw_output": str(event.tool_output), "serialization_error": str(serialize_error)}
                            
                            serialize_duration = time.time() - serialize_start
                            
                            if serialize_duration > 1.0:
                                logger.warning(f"⚠️ [{event_time:.2f}s] 工具 {tool_name} 序列化耗时: {serialize_duration:.2f}秒")

                            # 调试：输出工具输出的详细信息
                            logger.info(f"🔍 [Agent Query] 工具 {tool_name} 输出类型: {type(tool_output_serializable).__name__}")
                            if isinstance(tool_output_serializable, dict):
                                logger.info(f"🔍 [Agent Query] 工具 {tool_name} 输出键: {list(tool_output_serializable.keys())[:10]}")
                                if "error" in tool_output_serializable:
                                    logger.error(f"❌ [{event_time:.2f}s] 工具 {tool_name} 返回错误: {tool_output_serializable.get('error', '未知错误')}")
                                elif "status" in tool_output_serializable and tool_output_serializable.get("status") == "error":
                                    logger.error(f"❌ [{event_time:.2f}s] 工具 {tool_name} 执行失败: {tool_output_serializable.get('error', '未知错误')}")
                            elif isinstance(tool_output_serializable, str):
                                logger.info(f"🔍 [Agent Query] 工具 {tool_name} 输出字符串长度: {len(tool_output_serializable)}")
                                if len(tool_output_serializable) > 0:
                                    logger.info(f"🔍 [Agent Query] 工具 {tool_name} 输出字符串（前200字符）: {tool_output_serializable[:200]}")

                            # 如果是财务点评工具，提取可视化表格并精简输出
                            if tool_name == "generate_financial_review" and isinstance(tool_output_serializable, dict):
                                raw_output = tool_output_serializable.get("raw_output", tool_output_serializable)
                                if isinstance(raw_output, str):
                                    try:
                                        import json
                                        raw_output = json.loads(raw_output)
                                    except Exception:
                                        raw_output = {}
                                if isinstance(raw_output, dict):
                                    summary = raw_output.get("summary")
                                    tables = raw_output.get("visualization_tables")
                                else:
                                    summary = None
                                    tables = None
                                if tables:
                                    visualization_data = {
                                        "has_visualization": True,
                                        "type": "financial_tables",
                                        "visualization_type": "table",
                                        "tables": [
                                            tables.get("balance_sheet_assets") if isinstance(tables, dict) else None,
                                            tables.get("balance_sheet_liabilities") if isinstance(tables, dict) else None,
                                            tables.get("income_statement_revenue") if isinstance(tables, dict) else None,
                                            tables.get("income_statement_expense") if isinstance(tables, dict) else None,
                                            tables.get("cash_flow") if isinstance(tables, dict) else None
                                        ]
                                    }
                                if summary:
                                    financial_summary_override = summary
                                    summary_override = summary
                                    tool_output_serializable = {"summary": summary}
                            elif tool_name in {
                                "generate_business_guidance",
                                "generate_business_highlights",
                                "generate_profit_forecast_and_valuation",
                                "generate_dupont_analysis"
                            } and isinstance(tool_output_serializable, dict):
                                raw_output = tool_output_serializable.get("raw_output", tool_output_serializable)
                                if isinstance(raw_output, str):
                                    try:
                                        import json
                                        raw_output = json.loads(raw_output)
                                    except Exception:
                                        raw_output = {}
                                if hasattr(raw_output, "model_dump"):
                                    try:
                                        raw_output = raw_output.model_dump()
                                    except Exception:
                                        raw_output = {}
                                if not isinstance(raw_output, dict):
                                    raw_output = {}
                                summary_text = None
                                if tool_name == "generate_business_guidance":
                                    guidance_period = raw_output.get("guidance_period")
                                    expected_performance = raw_output.get("expected_performance")
                                    parent_profit = raw_output.get("parent_net_profit_range")
                                    parent_profit_growth = raw_output.get("parent_net_profit_growth_range")
                                    non_recurring_profit = raw_output.get("non_recurring_profit_range")
                                    eps_range = raw_output.get("eps_range")
                                    revenue_range = raw_output.get("revenue_range")
                                    business_guidance = raw_output.get("business_specific_guidance") or []
                                    key_metrics = raw_output.get("key_metrics") or []
                                    risk_warnings = raw_output.get("risk_warnings") or []

                                    what_parts = []
                                    if guidance_period:
                                        what_parts.append(f"期间：{guidance_period}")
                                    if expected_performance:
                                        what_parts.append(expected_performance)
                                    what_text = "；".join(what_parts) if what_parts else "未披露"

                                    metrics = []
                                    if parent_profit:
                                        metrics.append(f"归母净利润：{parent_profit}")
                                    if parent_profit_growth:
                                        metrics.append(f"归母净利润增长率：{parent_profit_growth}")
                                    if non_recurring_profit:
                                        metrics.append(f"扣非净利润：{non_recurring_profit}")
                                    if eps_range:
                                        metrics.append(f"基本每股收益：{eps_range}")
                                    if revenue_range:
                                        metrics.append(f"营业收入：{revenue_range}")
                                    combined_metrics = []
                                    if metrics:
                                        combined_metrics.extend(metrics)
                                    if key_metrics:
                                        for metric in key_metrics:
                                            if metric not in combined_metrics:
                                                combined_metrics.append(metric)
                                    if combined_metrics:
                                        watch_text = "；".join(combined_metrics[:8])
                                    elif expected_performance:
                                        watch_text = "年报未明确量化口径，可关注收入、利润及资产质量等表述线索"
                                    else:
                                        watch_text = "年报未明确量化口径，可关注收入、利润及资产质量等关键指标"

                                    how_text = "；".join(business_guidance[:5]) if business_guidance else "未明确"
                                    risk_text = "；".join(risk_warnings[:5]) if risk_warnings else "未明确"

                                    summary_text = "\n".join([
                                        f"- ① 经营目标方向：{what_text}",
                                        f"- ② 核心指标锚点：{watch_text}",
                                        f"- ③ 关键执行路径：{how_text}",
                                        f"- ④ 不确定性与边界：{risk_text}"
                                    ])
                                elif tool_name == "generate_business_highlights":
                                    overall_summary = raw_output.get("overall_summary")
                                    segment_tables = raw_output.get("segment_tables") or []
                                    if segment_tables:
                                        tables = []
                                        for segment in segment_tables:
                                            table = segment.get("table") if isinstance(segment, dict) else None
                                            if not isinstance(table, dict):
                                                continue
                                            if not table.get("insight"):
                                                conclusion = segment.get("conclusion")
                                                if conclusion:
                                                    table["insight"] = conclusion
                                            tables.append(table)
                                        if tables:
                                            visualization_data = {
                                                "has_visualization": True,
                                                "type": "financial_tables",
                                                "visualization_type": "table",
                                                "tables": tables
                                            }
                                    if overall_summary:
                                        summary_text = overall_summary
                                    else:
                                        highlights = raw_output.get("highlights") or []
                                        snippet_list = []
                                        for item in highlights[:3]:
                                            if isinstance(item, dict):
                                                business_type = item.get("business_type", "业务板块")
                                                highlights_text = item.get("highlights", "")
                                                if highlights_text:
                                                    snippet_list.append(f"{business_type}：{highlights_text}")
                                        if snippet_list:
                                            summary_text = "；".join(snippet_list)
                                elif tool_name == "generate_profit_forecast_and_valuation":
                                    conclusions = raw_output.get("strategy_conclusion") or {}
                                    clustering_model = raw_output.get("clustering_model") or {}

                                    parts = []
                                    short_term = conclusions.get("short_term")
                                    long_term = conclusions.get("long_term")
                                    risk_control = conclusions.get("risk_control")
                                    if short_term:
                                        parts.append(f"短期配置：{short_term}")
                                    if long_term:
                                        parts.append(f"长期配置：{long_term}")
                                    if risk_control:
                                        parts.append(f"风险管控：{risk_control}")

                                    # 聚类分析结果摘要
                                    if clustering_model and isinstance(clustering_model, dict):
                                        group_results = clustering_model.get("group_results") or []
                                        if group_results:
                                            group_names = [g.get("group_name", "") for g in group_results if isinstance(g, dict)]
                                            if group_names:
                                                parts.append(f"聚类分组：{', '.join(group_names)}")

                                    if isinstance(data_sufficiency, dict) and data_sufficiency.get("is_sufficient") is False:
                                        reason = data_sufficiency.get("reason") or "样本不足"
                                        parts.append(f"数据不足：{reason}")

                                    summary_text = "；".join([p for p in parts if p])
                                elif tool_name == "generate_dupont_analysis":
                                    level1 = raw_output.get("level1") or {}
                                    roe = None
                                    roa = None
                                    equity_multiplier = None
                                    if isinstance(level1, dict):
                                        roe = (level1.get("roe") or {}).get("formatted_value") if isinstance(level1.get("roe"), dict) else None
                                        roa = (level1.get("roa") or {}).get("formatted_value") if isinstance(level1.get("roa"), dict) else None
                                        equity_multiplier = (level1.get("equity_multiplier") or {}).get("formatted_value") if isinstance(level1.get("equity_multiplier"), dict) else None
                                    parts = []
                                    if roe:
                                        parts.append(f"ROE：{roe}")
                                    if roa:
                                        parts.append(f"ROA：{roa}")
                                    if equity_multiplier:
                                        parts.append(f"权益乘数：{equity_multiplier}")
                                    insights = raw_output.get("insights") or []
                                    if insights:
                                        parts.append("洞察：" + "；".join(insights[:2]))
                                    summary_text = "；".join([p for p in parts if p])
                                if summary_text:
                                    if tool_name == "generate_business_highlights":
                                        # 业务亮点保留完整正文，不使用 summary 覆盖
                                        if isinstance(tool_output_serializable, dict):
                                            tool_output_serializable.setdefault("summary", summary_text)
                                    elif tool_name == "generate_business_guidance":
                                        # 保留结构化数据，summary 只用于聊天区展示
                                        summary_override = summary_text
                                        if isinstance(tool_output_serializable, dict):
                                            tool_output_serializable.setdefault("summary", summary_text)
                                    else:
                                        summary_override = summary_text
                                        tool_output_serializable = {"summary": summary_text}

                            # 确保工具输出是可序列化的字典格式
                            tool_result = {
                                "tool_name": tool_name,
                                "tool_kwargs": event.tool_kwargs,
                                "tool_output": tool_output_serializable,
                                "execution_time": tool_call_times.get(tool_name, {}).get("duration", None)
                            }
                            
                            if tool_name in tool_call_times:
                                tool_result["execution_time"] = tool_end_time - tool_call_times[tool_name]["start"]
                            
                            # 业务亮点工具输出可能嵌套在 raw_output 中，展开常用字段便于前端消费
                            if (
                                tool_name == "generate_business_highlights"
                                and isinstance(tool_output_serializable, dict)
                            ):
                                raw_output = tool_output_serializable.get("raw_output")
                                if isinstance(raw_output, dict):
                                    if "segment_tables" in raw_output and "segment_tables" not in tool_output_serializable:
                                        tool_output_serializable["segment_tables"] = raw_output.get("segment_tables")
                                    if "overall_summary" in raw_output and "overall_summary" not in tool_output_serializable:
                                        tool_output_serializable["overall_summary"] = raw_output.get("overall_summary")
                                    if "key_metrics_summary" in raw_output and "key_metrics_summary" not in tool_output_serializable:
                                        tool_output_serializable["key_metrics_summary"] = raw_output.get("key_metrics_summary")
                            # 业绩指引工具输出可能嵌套在 raw_output 中，展开常用字段便于前端消费
                            if (
                                tool_name == "generate_business_guidance"
                                and isinstance(tool_output_serializable, dict)
                            ):
                                raw_output = tool_output_serializable.get("raw_output")
                                if isinstance(raw_output, str):
                                    try:
                                        import json
                                        raw_output = json.loads(raw_output)
                                    except Exception:
                                        raw_output = {}
                                if isinstance(raw_output, dict):
                                    for key, value in raw_output.items():
                                        tool_output_serializable.setdefault(key, value)

                            tool_results.append(tool_result)
                            
                            logger.info(f"✅ [Agent Query] [{event_time:.2f}s] 工具 {tool_name} 结果已添加到tool_results，当前总数: {len(tool_results)}")

                            # 如果是可视化工具，保存其输出
                            if tool_name == "generate_visualization":
                                logger.info(f"[Agent Query] [{event_time:.2f}s] Found visualization tool call")
                                visualization_data = tool_output_serializable
                        except Exception as serialize_error:
                            error_time = time.time() - query_start_time
                            logger.error(f"❌ [{error_time:.2f}s] Failed to serialize tool output for {tool_name}: {str(serialize_error)}")
                            import traceback
                            logger.error(f"[Agent Query] 序列化错误堆栈:\n{traceback.format_exc()}")
                            # 即使序列化失败，也记录工具调用
                            tool_result = {
                                "tool_name": tool_name,
                                "tool_kwargs": event.tool_kwargs,
                                "tool_output": f"序列化失败: {str(serialize_error)}",
                                "error": str(serialize_error),
                                "error_location": "tool_output_serialization"
                            }
                            tool_results.append(tool_result)

                    elif isinstance(event, AgentStream):
                        # 流式输出（可选）
                        pass

            except Exception as stream_error:
                stream_error_time = time.time() - query_start_time
                logger.error(f"❌ [{stream_error_time:.2f}s] Error during event streaming: {str(stream_error)}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[Agent Query] 事件流错误堆栈:\n{error_traceback}")
                
                # 记录已完成的工具调用
                logger.error(f"[Agent Query] 已完成 {len(tool_results)} 个工具调用:")
                for i, tool_result in enumerate(tool_results, 1):
                    logger.error(f"  {i}. {tool_result.get('tool_name', 'unknown')} - {tool_result.get('execution_time', 'N/A')}秒")
                
                # 重新抛出异常，但包含更多上下文
                raise Exception(f"事件流处理错误（耗时: {stream_error_time:.2f}秒，已完成{len(tool_results)}个工具调用）: {str(stream_error)}")

            # 获取最终响应 - 添加超时保护（1.5分钟，留出缓冲时间）
            logger.info("[Agent Query] Waiting for final response")
            import time
            response_start_time = time.time()
            try:
                import asyncio
                # 设置超时（1.5分钟，给Agent足够时间但不超过总体2分钟限制）
                timeout_seconds = 90.0  # 1.5分钟
                response = await asyncio.wait_for(handler, timeout=timeout_seconds)
                response_elapsed = time.time() - response_start_time
                logger.info(f"[Agent Query] Got final response type: {type(response)}, 耗时: {response_elapsed:.2f}秒")
            except asyncio.TimeoutError:
                response_elapsed = time.time() - response_start_time
                logger.error(f"[Agent Query] Timeout waiting for final response ({timeout_seconds/60:.1f} minutes), 实际耗时: {response_elapsed:.2f}秒")
                raise Exception(f"Agent响应超时（超过{int(timeout_seconds/60)}分钟，实际耗时: {response_elapsed:.2f}秒），请简化查询或使用普通查询模式")
            except Exception as e:
                response_elapsed = time.time() - response_start_time
                logger.error(f"[Agent Query] Error waiting for final response (耗时: {response_elapsed:.2f}秒): {str(e)}")
                import traceback
                logger.error(f"[Agent Query] 错误堆栈:\n{traceback.format_exc()}")
                raise

            # 提取回答内容 - 增强版本，支持更多响应格式
            answer_text = ""
            try:
                if hasattr(response, 'message'):
                    if hasattr(response.message, 'content'):
                        answer_text = str(response.message.content)
                    elif hasattr(response.message, 'text'):
                        answer_text = str(response.message.text)
                    else:
                        answer_text = str(response.message)
                elif hasattr(response, 'content'):
                    answer_text = str(response.content)
                elif hasattr(response, 'response'):
                    answer_text = str(response.response)
                elif hasattr(response, 'text'):
                    answer_text = str(response.text)
                elif hasattr(response, 'answer'):
                    answer_text = str(response.answer)
                else:
                    # 尝试直接转换为字符串
                    answer_text = str(response)
                
                # 如果提取的内容为空，尝试从工具结果中生成总结
                if not answer_text or answer_text.strip() == "":
                    logger.warning("[Agent Query] 响应内容为空，尝试从工具结果生成总结")
                    if tool_results:
                        # 尝试从工具输出中提取文本
                        for tool_result in tool_results:
                            tool_output = tool_result.get("tool_output", {})
                            if isinstance(tool_output, dict):
                                # 查找可能的文本字段
                                for key in ['answer', 'content', 'text', 'summary', 'report']:
                                    if key in tool_output and tool_output[key]:
                                        answer_text = str(tool_output[key])
                                        break
                                if answer_text:
                                    break
            except Exception as extract_error:
                logger.warning(f"[Agent Query] 提取回答内容时出错: {str(extract_error)}，使用默认处理")
                answer_text = str(response) if response else ""

            if summary_override:
                answer_text = summary_override
            
            # 过滤掉 answer 中的 "assistant:" 前缀和类似的开头
            if answer_text:
                # 移除常见的 assistant 前缀模式
                import re
                # 匹配 "assistant:"、"assistant："、"Assistant:" 等开头
                answer_text = re.sub(r'^(assistant|Assistant|ASSISTANT)[：:]\s*', '', answer_text, flags=re.IGNORECASE)
                # 移除 "基于检索到的信息"、"根据检索到的信息" 等常见开头
                answer_text = re.sub(r'^(基于|根据|通过).*?[，,：:]\s*', '', answer_text)
                # 移除开头的空白字符
                answer_text = answer_text.strip()
            
            # 如果没有回答内容，但有工具调用结果，生成一个总结
            if not answer_text or answer_text.strip() == "":
                if tool_results:
                    tool_names = [t.get("tool_name", "未知工具") for t in tool_results]
                    answer_text = f"✅ Agent分析完成！\n\n已执行以下工具：\n" + "\n".join([f"- {name}" for name in tool_names])
                    if len(tool_results) > 0:
                        answer_text += f"\n\n共执行了 {len(tool_results)} 个工具调用，请查看下方的结构化数据卡片获取详细分析结果。"
                else:
                    answer_text = "✅ Agent分析完成，但未返回详细内容。"
            
            # 如果从工具调用中没找到 sources，尝试从 response 中提取
            if not sources:
                try:
                    if hasattr(response, 'source_nodes'):
                        for node in response.source_nodes:
                            source_info = {
                                'text': node.text[:200] + "..." if len(node.text) > 200 else node.text,
                                'metadata': getattr(node, 'metadata', {}),
                                'score': getattr(node, 'score', 0.0)
                            }
                            sources.append(source_info)
                        logger.info(f"[Agent Query] 从 response 中提取到 {len(sources)} 个数据来源")
                except Exception as response_sources_error:
                    logger.warning(f"[Agent Query] 从 response 提取 sources 时出错: {str(response_sources_error)}")
            
            logger.info(f"[Agent Query] 总共提取到 {len(sources)} 个数据来源")
            
            # 如果 answer 中没有数据来源信息，但 sources 存在，自动在 answer 末尾添加数据来源
            if sources and len(sources) > 0:
                # 检查 answer 中是否已经包含数据来源信息
                has_source_in_answer = any(keyword in answer_text for keyword in ['数据来源', '来源', '参考', '参考来源', '资料来源'])
                
                if not has_source_in_answer:
                    # 从 sources 中提取页码信息
                    page_numbers = []
                    for source in sources:
                        metadata = source.get('metadata', {})
                        # 尝试从多个字段提取页码
                        page_num = None
                        
                        # 方法1: 直接从 metadata 中获取页码字段
                        page_num = metadata.get('page_number') or metadata.get('page') or metadata.get('page_label')
                        
                        # 方法2: 从 source 字段中提取（格式如 "filename_page_11"）
                        if not page_num:
                            source_str = metadata.get('source') or ''
                            if source_str and '_page_' in source_str:
                                import re
                                page_match = re.search(r'_page_(\d+)', source_str)
                                if page_match:
                                    page_num = page_match.group(1)
                        
                        # 方法3: 从文件名中提取（如果文件名包含页码信息）
                        if not page_num:
                            file_name = metadata.get('file_name') or metadata.get('filename') or metadata.get('source_file') or ''
                            if file_name and '_page_' in file_name:
                                import re
                                page_match = re.search(r'_page_(\d+)', file_name)
                                if page_match:
                                    page_num = page_match.group(1)
                        
                        if page_num:
                            page_numbers.append(str(page_num))
                    
                    # 如果有页码信息，构建数据来源文本
                    if page_numbers:
                        # 去重并排序
                        unique_pages = sorted(set(page_numbers), key=lambda x: int(x) if x.isdigit() else 999)
                        # 合并连续页码（如 24, 25 -> 24-25）
                        page_ranges = []
                        i = 0
                        while i < len(unique_pages):
                            if unique_pages[i].isdigit():
                                start = int(unique_pages[i])
                                end = start
                                # 查找连续页码
                                while i + 1 < len(unique_pages) and unique_pages[i + 1].isdigit() and int(unique_pages[i + 1]) == end + 1:
                                    end = int(unique_pages[i + 1])
                                    i += 1
                                if start == end:
                                    page_ranges.append(str(start))
                                else:
                                    page_ranges.append(f"{start}-{end}")
                            else:
                                page_ranges.append(unique_pages[i])
                            i += 1
                        
                        # 尝试从 sources 中提取公司名和年份
                        company_name = None
                        year = None
                        for source in sources:
                            metadata = source.get('metadata', {})
                            if not company_name:
                                company_name = metadata.get('company_name') or metadata.get('company')
                            if not year:
                                year = metadata.get('year') or metadata.get('report_year')
                            if company_name and year:
                                break
                        
                        # 如果从 metadata 中没提取到，尝试从文件名中提取
                        if not company_name or not year:
                            for source in sources:
                                metadata = source.get('metadata', {})
                                file_name = metadata.get('file_name') or metadata.get('filename') or metadata.get('source_file') or ''
                                if file_name:
                                    import re
                                    # 从文件名中提取年份（4位数字）
                                    if not year:
                                        year_match = re.search(r'(\d{4})', file_name)
                                        if year_match:
                                            year = year_match.group(1)
                                    # 从文件名中提取公司名（移除常见后缀）
                                    if not company_name:
                                        # 移除文件扩展名
                                        name_without_ext = file_name.replace('.pdf', '').replace('.PDF', '').replace('.xlsx', '').replace('.xls', '')
                                        # 移除年份
                                        name_without_year = re.sub(r'\d{4}年?', '', name_without_ext)
                                        # 移除常见的报表类型关键词
                                        name_clean = re.sub(r'(利润表|资产负债表|现金流量表|年报|年度报告|报告|财务报表|财务报告|合并报表|母公司报表)', '', name_without_year, flags=re.IGNORECASE)
                                        name_clean = name_clean.strip()
                                        # 验证公司名长度（2-30个字符）
                                        if len(name_clean) >= 2 and len(name_clean) <= 30:
                                            company_name = name_clean
                                    if company_name and year:
                                        break
                        
                        # 如果还是没有提取到，尝试从 question 中提取
                        if not company_name or not year:
                            import re
                            # 尝试从问题中提取公司名和年份
                            if not company_name:
                                # 匹配"分析XX公司"或"XX公司2024年"等模式
                                company_match = re.search(r'(?:分析|查询|查看)([^0-9请帮]+?)(?:\d{4}|年|的)', question)
                                if company_match:
                                    company_name = company_match.group(1).strip()
                                # 如果没有匹配到，尝试匹配"XX公司"模式
                                if not company_name:
                                    company_match = re.search(r'([^请帮分析查询查看]+?)(?:\d{4}|年)', question)
                                    if company_match:
                                        potential_name = company_match.group(1).strip()
                                        # 验证公司名长度
                                        if len(potential_name) >= 2 and len(potential_name) <= 30:
                                            company_name = potential_name
                            if not year:
                                year_match = re.search(r'(\d{4})', question)
                                if year_match:
                                    year = year_match.group(1)
                        
                        # 构建数据来源文本
                        source_text = f"\n\n数据来源："
                        if company_name and year:
                            source_text += f"{company_name}{year}年年报"
                        elif year:
                            source_text += f"{year}年年报"
                        elif company_name:
                            source_text += f"{company_name}年报"
                        else:
                            source_text += "年报"
                        source_text += f"第{', '.join(page_ranges)}页"
                        
                        # 添加到 answer 末尾
                        answer_text = answer_text.rstrip() + source_text
                        logger.info(f"[Agent Query] 自动在 answer 末尾添加数据来源信息: {source_text}")
                    else:
                        # 如果没有页码，但仍然有 sources，至少显示来源信息
                        # 尝试从文件名中提取信息
                        file_names = set()
                        for source in sources:
                            metadata = source.get('metadata', {})
                            file_name = metadata.get('file_name') or metadata.get('filename') or metadata.get('source') or ''
                            if file_name:
                                # 移除文件扩展名
                                file_name = file_name.replace('.pdf', '').replace('.PDF', '').replace('.xlsx', '').replace('.xls', '')
                                file_names.add(file_name)
                        
                        if file_names:
                            # 使用第一个文件名作为来源
                            source_file = list(file_names)[0]
                            source_text = f"\n\n数据来源：{source_file}"
                            answer_text = answer_text.rstrip() + source_text
                            logger.info(f"[Agent Query] 自动在 answer 末尾添加数据来源信息（基于文件名）: {source_text}")
                        else:
                            # 如果连文件名都没有，至少显示有数据来源
                            source_text = f"\n\n数据来源：年报相关章节"
                            answer_text = answer_text.rstrip() + source_text
                            logger.info(f"[Agent Query] 自动在 answer 末尾添加通用数据来源信息")
            
            result = {
                "status": "success",
                "question": question,
                "answer": answer_text,
                "sources": sources,  # 添加 sources 字段
                "structured_response": response.structured_response if hasattr(response, 'structured_response') else None,
                "tool_calls": tool_results if tool_results else []  # 确保是列表
            }

            # 如果有可视化数据，添加到响应中
            if visualization_data:
                logger.info("[Agent Query] Adding visualization data to response")
                result["visualization"] = visualization_data
            # 在通用查询模式下，如果 answer 包含数据但没有可视化，尝试自动生成可视化
            elif query_type == "general" and answer_text and len(answer_text.strip()) > 50:
                # 检查是否需要生成可视化
                import re
                # 1. 检查 answer 是否包含数据（数字、表格等）
                has_numbers = bool(re.search(r'\d+[万亿千百十]?[元%]?', answer_text))
                has_table_markers = bool(re.search(r'[|：:]\s*\d+', answer_text))
                # 2. 检查问题是否包含财务分析相关的关键词
                financial_keywords = ['分析', '财务', '情况', '数据', '指标', '趋势', '对比', '营收', '利润', '资产', '负债', '现金流']
                question_lower = question.lower()
                has_financial_query = any(keyword in question_lower for keyword in financial_keywords)
                # 3. 检查回答中是否包含财务相关关键词
                answer_lower = answer_text.lower()
                has_financial_content = any(keyword in answer_lower for keyword in ['营业收入', '净利润', '资产', '负债', 'ROE', 'ROA', '毛利率', '净利率', '现金流'])
                
                # 如果满足任一条件，尝试生成可视化
                should_generate_viz = has_numbers or has_table_markers or (has_financial_query and has_financial_content)
                
                if should_generate_viz:
                    logger.info(f"[Agent Query] 通用查询模式下检测到数据/财务内容，尝试自动生成可视化")
                    logger.info(f"[Agent Query] 检测结果: has_numbers={has_numbers}, has_table_markers={has_table_markers}, has_financial_query={has_financial_query}, has_financial_content={has_financial_content}")
                    try:
                        # 异步调用可视化生成工具
                        from agents.visualization_agent import generate_visualization_for_query
                        import asyncio
                        # 设置较短的超时（15秒），避免影响整体响应时间
                        viz_result = await asyncio.wait_for(
                            generate_visualization_for_query(
                                query=question,
                                answer=answer_text,
                                data=None,
                                sources=sources if sources else None
                            ),
                            timeout=15.0
                        )
                        if viz_result and viz_result.get("has_visualization"):
                            result["visualization"] = viz_result
                            logger.info("[Agent Query] ✅ 自动生成可视化成功")
                        else:
                            logger.info("[Agent Query] 可视化生成工具返回无可视化结果")
                            logger.debug(f"[Agent Query] 可视化结果: {viz_result}")
                    except asyncio.TimeoutError:
                        logger.warning("[Agent Query] 可视化生成超时（15秒），跳过")
                    except Exception as viz_error:
                        logger.warning(f"[Agent Query] 自动生成可视化失败: {str(viz_error)}")
                        import traceback
                        logger.debug(f"[Agent Query] 可视化生成错误详情: {traceback.format_exc()}")
                        # 不影响主流程，继续返回结果
                else:
                    logger.info(f"[Agent Query] 未检测到需要生成可视化的条件，跳过自动生成")
            
            # 添加详细的调试日志，确保数据正确传递
            logger.info(f"[Agent Query] 返回结果摘要: status={result['status']}, answer_length={len(answer_text)}, tool_calls_count={len(tool_results)}, sources_count={len(sources)}, has_visualization={bool(visualization_data)}")
            
            # 输出每个工具调用的详细信息
            if tool_results:
                logger.info(f"[Agent Query] 工具调用详情:")
                for i, tool_result in enumerate(tool_results, 1):
                    tool_name = tool_result.get('tool_name', 'unknown')
                    tool_output = tool_result.get('tool_output', {})
                    output_type = type(tool_output).__name__
                    output_size = len(str(tool_output)) if tool_output else 0
                    logger.info(f"  [{i}] {tool_name}: 输出类型={output_type}, 输出大小={output_size}字符")
                    if isinstance(tool_output, dict):
                        logger.info(f"      输出键: {list(tool_output.keys())[:10]}")
                    elif isinstance(tool_output, str):
                        logger.info(f"      输出预览: {tool_output[:200]}")
            
            # 确保tool_calls是列表且不为空
            if not tool_results:
                logger.warning("⚠️ [Agent Query] tool_results为空，但查询已完成")
            else:
                logger.info(f"✅ [Agent Query] 准备返回 {len(tool_results)} 个工具调用结果")

            total_time = time.time() - query_start_time
            logger.info(f"✅ [Agent Query] Query completed successfully in {total_time:.2f}秒 with {len(tool_results)} tool calls")
            
            # 添加性能统计
            if tool_results:
                total_tool_time = sum(t.get("execution_time", 0) for t in tool_results if t.get("execution_time"))
                logger.info(f"[Agent Query] 工具调用总耗时: {total_tool_time:.2f}秒，平均每个工具: {total_tool_time/len(tool_results):.2f}秒")
            
            result["performance"] = {
                "total_seconds": total_time,
                "tool_calls_count": len(tool_results),
                "tool_calls_time": total_tool_time if tool_results else 0
            }
            
            return result

        except Exception as e:
            import time
            total_time = time.time() - query_start_time if 'query_start_time' in locals() else 0
            logger.error(f"❌ [Agent Query] Query failed (总耗时: {total_time:.2f}秒): {str(e)}")
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[Agent Query] 完整错误堆栈:\n{error_traceback}")
            
            # 提取错误位置信息
            error_location = "unknown"
            error_type = type(e).__name__
            
            # 从堆栈中提取关键信息
            if "timeout" in str(e).lower() or "Timeout" in error_type:
                error_location = "timeout"
            elif "serialize" in str(e).lower():
                error_location = "serialization"
            elif "tool" in str(e).lower():
                error_location = "tool_execution"
            elif "stream" in str(e).lower():
                error_location = "event_streaming"
            
            return {
                "status": "error",
                "error": str(e),
                "error_type": error_type,
                "error_location": error_location,
                "question": question,
                "elapsed_seconds": total_time,
                "completed_tool_calls": len(tool_results) if 'tool_results' in locals() else 0,
                "tool_calls": tool_results if 'tool_results' in locals() else []
            }
