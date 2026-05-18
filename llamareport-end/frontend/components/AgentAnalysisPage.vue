<template>
  <div class="agent-analysis-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <button class="back-btn" @click="goBack" title="返回主页">
        <span>←</span> 返回
      </button>
      <div class="page-title">
        <span class="page-icon">🤖</span>
        <h1>Agent 智能分析</h1>
      </div>
    </div>

    <!-- 问题输入区域 -->
    <div class="query-section">
      <div class="query-input-wrapper">
        <textarea 
          v-model="inputText" 
          class="query-input" 
          placeholder="输入您的问题，Agent将进行深度分析并生成完整报告..."
          rows="2"
          @keydown.ctrl.enter="handleSubmit"
        ></textarea>
        <button 
          class="submit-btn" 
          @click="handleSubmit" 
          :disabled="!inputText.trim() || loading"
        >
          <span v-if="!loading">🚀 开始分析</span>
          <span v-else class="loading-text">
            <span class="spinner-small"></span> 分析中...
          </span>
        </button>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="content-area" ref="contentArea">
          <!-- 加载状态 -->
          <div v-if="loading" class="loading-container">
        <div class="loading-card">
          <div class="spinner-large"></div>
          <h3>Agent 正在分析中...</h3>
          <p>这可能需要1-3分钟，请耐心等待</p>
          <div class="progress-steps">
            <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
              <span class="step-icon">🔍</span>
              <span class="step-text">检索相关数据</span>
            </div>
            <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
              <span class="step-icon">⚙️</span>
              <span class="step-text">调用工具分析</span>
            </div>
            <div class="step" :class="{ active: currentStep >= 3, completed: currentStep > 3 }">
              <span class="step-icon">📊</span>
              <span class="step-text">生成结构化回答</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && !hasContent" class="empty-container">
        <div class="empty-card">
          <div class="empty-icon">🤖</div>
          <h2>开始您的智能分析</h2>
          <p>输入问题，Agent将为您生成完整的分析报告</p>
          <div class="suggestions">
            <div class="suggestion-title">💡 推荐问题：</div>
            <button 
              v-for="(suggestion, idx) in defaultSuggestions" 
              :key="idx"
              class="suggestion-btn"
              @click="useSuggestion(suggestion)"
            >
              {{ suggestion }}
            </button>
          </div>
        </div>
      </div>

            <!-- 内容展示区域 -->
            <div v-if="!loading && hasContent" class="results-container">
              <!-- 调试信息（开发环境） -->
              <div v-if="false" class="debug-info" style="background: #f0f0f0; padding: 10px; margin-bottom: 20px; font-size: 12px;">
                <strong>调试信息:</strong><br>
                hasContent: {{ hasContent }}<br>
                hasAnswer: {{ !!answer }}<br>
                answerLength: {{ answer?.length || 0 }}<br>
                visualizationsCount: {{ visualizations.length }}<br>
                hasFinancialReview: {{ !!structuredData.financialReview }}<br>
                hasBusinessHighlights: {{ !!structuredData.businessHighlights }}<br>
                hasBusinessGuidance: {{ !!structuredData.businessGuidance }}<br>
                hasDupontAnalysis: {{ !!structuredData.dupontAnalysis }}
              </div>
              
              <!-- 问题卡片 -->
              <div v-if="currentQuestion" class="question-card">
                <div class="question-header">
                  <span class="question-icon">❓</span>
                  <h3>分析问题</h3>
                </div>
                <div class="question-content">{{ currentQuestion }}</div>
              </div>

              <!-- 文本回答 -->
              <div v-if="answer" class="answer-card">
                <div class="answer-header">
                  <div class="answer-header-left">
                    <span class="answer-icon">📝</span>
                    <h3>分析结果</h3>
                  </div>
                  <div class="answer-header-actions">
                    <button class="action-btn" @click="copyAnswer" title="复制内容">
                      <span>📋</span> 复制
                    </button>
                    <button class="action-btn" @click="exportReport" title="导出报告">
                      <span>💾</span> 导出
                    </button>
                  </div>
                </div>
                <div class="answer-content" v-html="parseMarkdown(answer)"></div>
              </div>

              <div v-if="evidenceMappings.length > 0" class="evidence-card">
                <div class="evidence-header">
                  <div class="evidence-header-left">
                    <span class="evidence-icon">🔎</span>
                    <h3>结论证据映射</h3>
                  </div>
                  <span class="evidence-count">{{ evidenceMappings.length }}</span>
                </div>
                <div class="evidence-list">
                  <div
                    v-for="(item, idx) in evidenceMappings"
                    :key="`${idx}-${item.claim}`"
                    class="evidence-item"
                  >
                    <div class="evidence-item-label">关键结论</div>
                    <div class="evidence-item-claim">{{ item.claim }}</div>
                    <div class="evidence-item-label">证据摘录</div>
                    <div class="evidence-item-text">{{ item.evidence }}</div>
                    <div class="evidence-item-meta">
                      <span v-if="item.source_page">页码：第{{ item.source_page }}页</span>
                      <span v-if="item.source_file">{{ item.source_file }}</span>
                    </div>
                  </div>
                </div>
              </div>

        <!-- 可视化图表区域 -->
        <div v-if="filteredVisualizations.length > 0" class="visualizations-section">
          <div class="section-header">
            <span class="section-icon">📊</span>
            <h2>数据可视化</h2>
            <span class="section-count">{{ filteredVisualizations.length }}</span>
          </div>
          <div class="visualizations-grid">
            <div 
              v-for="(viz, idx) in filteredVisualizations" 
              :key="viz.id || idx"
              class="visualization-card"
            >
              <div class="viz-card-header">
                <h4>{{ viz.question || '数据图表' }}</h4>
                <button class="viz-close-btn" @click="removeVisualization(viz)" title="删除">×</button>
              </div>
              <div class="viz-card-content">
                <div v-if="viz.data?.type === 'financial_table' && viz.data?.table" class="table-container" :class="{ 'table-container--auto': isKeyMetricsTable(viz.data.table) }">
                  <table class="financial-table">
                    <thead>
                      <tr>
                        <th v-for="(header, hIdx) in viz.data.table.headers" :key="hIdx">
                          {{ header }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rIdx) in viz.data.table.rows" :key="rIdx">
                        <td v-for="(cell, cIdx) in row" :key="cIdx">
                          {{ cell }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="viz.data?.type === 'financial_table' && (viz.data?.table?.insight_html || viz.data?.table?.insight)" class="table-insight" v-html="viz.data.table.insight_html || viz.data.table.insight">
                </div>
                <div v-if="viz.data?.type === 'financial_table' && viz.data?.summary" class="table-insight">
                  {{ viz.data.summary }}
                </div>
                <div v-if="viz.data?.type === 'insight_card'" class="insight-card">
                  <div class="insight-card-title">{{ viz.data.title || '业务亮点洞察' }}</div>
                  <div v-if="viz.data.headline" class="insight-card-headline">{{ viz.data.headline }}</div>
                <div v-if="viz.data.contribution" class="insight-card-row">
                  <span class="insight-label">{{ viz.data.meta_type === 'guidance_tone' ? '目标优先级：' : '贡献：' }}</span>
                  {{ viz.data.meta_type === 'guidance_tone'
                    ? viz.data.contribution.replace('目标优先级：', '')
                    : viz.data.contribution }}
                </div>
                  <div v-if="viz.data.drivers && viz.data.drivers.length" class="insight-card-row">
                    <span class="insight-label">驱动：</span>{{ viz.data.drivers.join('；') }}
                  </div>
                  <div v-if="viz.data.strategy_link && viz.data.strategy_link.length" class="insight-card-row">
                    <span class="insight-label">策略：</span>{{ viz.data.strategy_link.join('；') }}
                  </div>
                  <div v-if="viz.data.risks_and_watchlist && viz.data.risks_and_watchlist.length" class="insight-card-row">
                    <span class="insight-label">风险：</span>{{ viz.data.risks_and_watchlist.join('；') }}
                  </div>
                </div>
                <div v-else :id="'agent-viz-' + (viz.id || idx)" class="chart-container"></div>
                
                <!-- 推荐说明 -->
                <div v-if="viz.data?.recommendation && viz.data?.type !== 'financial_table'" class="recommendation-box">
                  <h5>📈 图表推荐</h5>
                  <p><strong>类型:</strong> {{ getChartTypeName(viz.data.recommendation.recommended_chart_type) }}</p>
                  <p><strong>理由:</strong> {{ viz.data.recommendation.reason }}</p>
                </div>
                
                <!-- 数据洞察 -->
                <div v-if="viz.data?.insights && viz.data.insights.length > 0 && viz.data?.type !== 'financial_table'" class="insights-box">
                  <h5>💡 数据洞察</h5>
                  <div 
                    v-for="(insight, i) in viz.data.insights" 
                    :key="i" 
                    class="insight-item"
                  >
                    <h6>
                      {{ getInsightIcon(insight.insight_type) }} 
                      {{ insight.description }}
                    </h6>
                    <ul v-if="insight.key_findings && insight.key_findings.length > 0">
                      <li v-for="(finding, j) in insight.key_findings" :key="j">
                        {{ finding }}
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 结构化数据区域 -->
        <div v-if="hasStructuredData" class="structured-data-section">
          <div class="section-header">
            <span class="section-icon">📋</span>
            <h2>结构化分析</h2>
          </div>
          <div class="structured-grid">
            <!-- 财务点评 -->
            <div v-if="structuredData.financialReview" class="data-card financial-review">
              <div class="data-card-header">
                <span class="data-icon">💰</span>
                <h3>财务点评</h3>
              </div>
              <div class="data-card-content" v-html="parseMarkdown(structuredData.financialReview)"></div>
            </div>

            <!-- 业务亮点 -->
            <div v-if="structuredData.businessHighlights" class="data-card business-highlights">
              <div class="data-card-header">
                <span class="data-icon">⭐</span>
                <h3>业务亮点</h3>
              </div>
              <div class="data-card-content" v-html="parseMarkdown(structuredData.businessHighlights)"></div>
            </div>

            <!-- 业绩指引 -->
            <div v-if="structuredData.businessGuidance" class="data-card business-guidance">
              <div class="data-card-header">
                <span class="data-icon">🎯</span>
                <h3>业绩指引</h3>
              </div>
              <div class="data-card-content" v-html="parseMarkdown(structuredData.businessGuidance)"></div>
            </div>

            <!-- 杜邦分析 -->
            <div v-if="structuredData.dupontAnalysis" class="data-card dupont-analysis">
              <div class="data-card-header">
                <span class="data-icon">📊</span>
                <h3>杜邦分析</h3>
              </div>
              <div class="data-card-content">
                <div v-if="structuredData.dupontAnalysis.full_data" class="dupont-content">
                  <div class="dupont-metrics">
                    <div class="metric-item">
                      <span class="metric-label">ROE</span>
                      <span class="metric-value">{{ getDupontValue(structuredData.dupontAnalysis, 'roe') }}</span>
                    </div>
                    <div class="metric-item">
                      <span class="metric-label">ROA</span>
                      <span class="metric-value">{{ getDupontValue(structuredData.dupontAnalysis, 'roa') }}</span>
                    </div>
                    <div class="metric-item">
                      <span class="metric-label">权益乘数</span>
                      <span class="metric-value">{{ getDupontValue(structuredData.dupontAnalysis, 'equity_multiplier') }}</span>
                    </div>
                  </div>
                  <div v-if="structuredData.dupontAnalysis.full_data?.insights" class="dupont-insights">
                    <h4>分析洞察</h4>
                    <ul>
                      <li v-for="(insight, i) in structuredData.dupontAnalysis.full_data.insights" :key="i">
                        {{ insight }}
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-else class="dupont-simple">
                  <p>ROE: {{ structuredData.dupontAnalysis.roe || '—' }}</p>
                  <p>ROA: {{ structuredData.dupontAnalysis.roa || '—' }}</p>
                  <p>权益乘数: {{ structuredData.dupontAnalysis.equity_multiplier || '—' }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AgentAnalysisPage',
  props: {
    onBack: { type: Function, required: true },
    onQuery: { type: Function, required: true },
    onAddVisualizationCards: { type: Function, default: null }
  },
  data() {
    return {
      inputText: '',
      loading: false,
      currentQuestion: '',
      answer: '',
      evidenceMappings: [],
      visualizations: [],
      structuredData: {
        financialReview: null,
        businessHighlights: null,
        businessGuidance: null,
        dupontAnalysis: null
      },
      currentStep: 0,
      defaultSuggestions: [
        '请生成完整的年报分析报告，包括财务点评、业绩指引、业务亮点和投资策略',
        '分析这家公司的财务状况和盈利能力',
        '进行杜邦分析，深入分析ROE的驱动因素',
        '对比分析近三年的财务指标变化趋势',
        '分析公司的业务亮点和主要成就',
        '评估公司的投资策略和估值水平'
      ],
      showExportMenu: false
    }
  },
  computed: {
    hasContent() {
      const hasAnswer = this.answer && this.answer.trim().length > 0
      const hasEvidenceMappings = this.evidenceMappings && this.evidenceMappings.length > 0
      const hasViz = this.visualizations && this.visualizations.length > 0
      const hasStructured = this.hasStructuredData
      
      const result = hasAnswer || hasEvidenceMappings || hasViz || hasStructured
      
      // 调试日志（只在状态变化时输出，避免过多日志）
      if (result && !this._lastHasContent) {
        console.log('✅ [AgentAnalysisPage] hasContent 变为 true:', {
          hasAnswer,
          hasViz,
          hasStructured,
          answerLength: this.answer?.length || 0,
          visualizationsCount: this.visualizations?.length || 0,
          structuredDataKeys: Object.keys(this.structuredData).filter(k => this.structuredData[k])
        })
      }
      this._lastHasContent = result
      
      return result
    },
    hasStructuredData() {
      return this.structuredData.financialReview || 
             this.structuredData.businessHighlights || 
             this.structuredData.businessGuidance || 
             this.structuredData.dupontAnalysis
    },
    filteredVisualizations() {
      return this.visualizations.filter(viz => !this.isHiddenBusinessMetricTable(viz))
    }
  },
  methods: {
    goBack() {
      this.onBack()
    },
    isBusinessGuidanceObject(data) {
      return data && typeof data === 'object' && !Array.isArray(data)
    },
    /** 将业绩指引列表项（字符串或对象）转为可读字符串数组，与 main.js normalizeGuidanceList 一致 */
    normalizeGuidanceList(items, kind) {
      if (items == null) return []
      if (!Array.isArray(items)) {
        if (typeof items === 'string') return items.trim() ? [items.trim()] : []
        return []
      }
      const out = []
      for (const item of items) {
        if (typeof item === 'string') {
          const t = item.trim()
          if (t) out.push(t)
          continue
        }
        if (item == null || typeof item !== 'object') continue
        if (kind === 'key_metrics') {
          const name = item['指标名'] ?? item.metric ?? item.name ?? '指标'
          const val = item['数值'] ?? item.value ?? '—'
          const chg = item['变化'] ?? item.change
          const interp = item['解读'] ?? item.interpretation
          const parts = [`${name}：${val}`]
          if (chg != null && String(chg).trim()) parts.push(`变化${chg}`)
          if (interp != null && String(interp).trim()) parts.push(String(interp))
          out.push(parts.join('，'))
        } else if (kind === 'business_specific_guidance') {
          const action = item['执行动作'] ?? item.action ?? '执行动作'
          const evidence = item['证据'] ?? item.evidence
          const impact = item['影响'] ?? item.impact
          const parts = [String(action)]
          if (evidence != null && String(evidence).trim()) parts.push(`证据：${evidence}`)
          if (impact != null && String(impact).trim()) parts.push(`影响：${impact}`)
          out.push(parts.join('；'))
        } else if (kind === 'risk_warnings') {
          const risk = item['风险名称'] ?? item.risk ?? '风险'
          const impactObj = item['影响对象'] ?? item.impact
          const metric = item['指标变化'] ?? item.metric_change
          const prob = item['概率'] ?? item.probability
          const parts = [String(risk)]
          if (impactObj != null && String(impactObj).trim()) parts.push(`影响对象：${impactObj}`)
          if (metric != null && String(metric).trim()) parts.push(`指标变化：${metric}`)
          if (prob != null && String(prob).trim()) parts.push(`概率：${prob}`)
          out.push(parts.join('；'))
        } else {
          const s = String(item).trim()
          if (s) out.push(s)
        }
      }
      return out
    },
    buildBusinessGuidanceSections(data) {
      if (!data || typeof data !== 'object' || Array.isArray(data)) return []
      // 支持完整报告结构：{ business_guidance, ... }
      const payload = data.business_guidance != null ? data.business_guidance : data
      if (!this.isBusinessGuidanceObject(payload)) return []

      const guidancePeriod = payload.guidance_period || payload.guidancePeriod
      const expectedPerformance = payload.expected_performance || payload.expectedPerformance
      const keyMetricsNormalized = this.normalizeGuidanceList(
        payload.key_metrics || payload.keyMetrics,
        'key_metrics'
      )
      const parentProfit = payload.parent_net_profit_range || payload.parentNetProfitRange
      const parentProfitGrowth = payload.parent_net_profit_growth_range || payload.parentNetProfitGrowthRange
      const nonRecurringProfit = payload.non_recurring_profit_range || payload.nonRecurringProfitRange
      const epsRange = payload.eps_range || payload.epsRange
      const revenueRange = payload.revenue_range || payload.revenueRange
      const businessGuidanceNormalized = this.normalizeGuidanceList(
        payload.business_specific_guidance || payload.businessSpecificGuidance,
        'business_specific_guidance'
      )
      const riskWarningsNormalized = this.normalizeGuidanceList(
        payload.risk_warnings || payload.riskWarnings,
        'risk_warnings'
      )

      const whatParts = []
      if (guidancePeriod) whatParts.push(`期间：${guidancePeriod}`)
      if (expectedPerformance) whatParts.push(expectedPerformance)
      const whatText = whatParts.length ? whatParts.join('；') : '未明确'

      const metricParts = []
      if (parentProfit) metricParts.push(`归母净利润：${parentProfit}`)
      if (parentProfitGrowth) metricParts.push(`归母净利润增长率：${parentProfitGrowth}`)
      if (nonRecurringProfit) metricParts.push(`扣非净利润：${nonRecurringProfit}`)
      if (epsRange) metricParts.push(`基本每股收益：${epsRange}`)
      if (revenueRange) metricParts.push(`营业收入：${revenueRange}`)
      const watchList = metricParts.length ? metricParts : keyMetricsNormalized
      const watchContent = watchList.length ? watchList : '年报未明确量化口径'

      const howContent = businessGuidanceNormalized.length ? businessGuidanceNormalized : '未明确'
      const riskContent = riskWarningsNormalized.length ? riskWarningsNormalized : '未明确'

      return [
        { title: '① 经营目标方向', content: whatText },
        { title: '② 核心指标锚点', content: watchContent },
        { title: '③ 关键执行路径', content: howContent },
        { title: '④ 不确定性与边界', content: riskContent }
      ]
    },
    formatGuidanceSectionContent(content) {
      if (Array.isArray(content)) {
        return content.join('；')
      }
      return content || '—'
    },
    parseMetricValue(value) {
      if (value === null || value === undefined) return null
      if (typeof value === 'number') return value
      const text = String(value).replace(/,/g, '').trim()
      if (!text || text === '/' || text === '-') return null
      const percent = text.includes('%')
      const match = text.match(/-?\d+(\.\d+)?/)
      if (!match) return null
      let num = Number(match[0])
      if (Number.isNaN(num)) return null
      if (text.includes('万亿')) num *= 1e12
      else if (text.includes('亿')) num *= 1e8
      else if (text.includes('万')) num *= 1e4
      if (percent) return num
      return num
    },
    isKeyMetricsTable(table) {
      const title = table?.title || ''
      return String(title).includes('关键业务指标')
    },
    isHiddenBusinessMetricTable(viz) {
      if (!viz || viz.data?.type !== 'financial_table') return false
      const title = viz.data?.table?.title || viz.question || ''
      const hiddenTitles = ['零售银行业务指标', '对公银行业务指标', '同业与资金业务指标']
      return hiddenTitles.some(item => String(title).includes(item))
    },
    parseNumericValue(value = '') {
      const text = String(value).replace(/,/g, '').trim()
      const match = text.match(/-?\d+(\.\d+)?/)
      if (!match) return null
      return Number(match[0])
    },
    buildGuidanceToneCard(payload) {
      if (!payload || typeof payload !== 'object') return null
      const spec = payload.visualization_spec || payload.visualizationSpec || {}
      const operatingGoal = spec.operating_goal || spec.operatingGoal || {}
      const expectedPerformance = payload.expected_performance || payload.expectedPerformance || ''
      const stageMatch = String(expectedPerformance).match(/(进攻|防守|转型|稳健)/)
      const stageText = stageMatch ? stageMatch[0] : (operatingGoal.stage || operatingGoal.focus || '—')
      const priorityText = Array.isArray(operatingGoal.key_elements)
        ? operatingGoal.key_elements.join(' > ')
        : (operatingGoal.priority || operatingGoal.purpose || '—')
      return {
        title: '经营基调状态卡',
        headline: `经营阶段：${stageText || '—'}`,
        contribution: `目标优先级：${priorityText || '—'}`
      }
    },
    buildGuidanceInsights(description, findings = []) {
      const cleanFindings = Array.isArray(findings)
        ? findings.map(item => String(item || '').trim()).filter(Boolean)
        : []
      const cleanDescription = String(description || '').trim()
      if (!cleanDescription && cleanFindings.length === 0) return []
      return [
        {
          insight_type: 'comparison',
          description: cleanDescription || cleanFindings[0] || '要点概览',
          key_findings: cleanFindings.length > 0
            ? cleanFindings
            : (cleanDescription ? [cleanDescription] : [])
        }
      ]
    },
    getGuidanceInsights(payload = {}, key) {
      const insightsRoot = payload.visualization_insights || payload.visualizationInsights || {}
      const section = insightsRoot && typeof insightsRoot === 'object' ? insightsRoot[key] : null
      if (!section) return null
      if (Array.isArray(section)) return section
      if (Array.isArray(section.insights)) return section.insights
      return null
    },
    filterGuidanceInsights(insights = [], allowedItems = []) {
      if (!Array.isArray(insights)) return null
      const allowed = new Set(allowedItems.map(item => String(item || '').trim()).filter(Boolean))
      if (!allowed.size) return insights.length ? insights : null
      const filtered = insights.filter(insight => {
        const related = Array.isArray(insight?.related_items) ? insight.related_items : []
        if (!related.length) return false
        return related.some(item => allowed.has(String(item || '').trim()))
      })
      return filtered.length ? filtered : null
    },
    buildGuidanceVisualizationCards(payload) {
      if (!payload || typeof payload !== 'object') return []
      const spec = payload.visualization_spec || payload.visualizationSpec || {}
      if (!spec || typeof spec !== 'object') return []
      const cards = []

      const operatingGoal = spec.operating_goal || spec.operatingGoal || {}
      if (operatingGoal.chart_type === 'status_card') {
        const toneCard = this.buildGuidanceToneCard(payload)
        if (toneCard) {
          cards.push({
            id: 'guidance-tone-card',
            question: toneCard.title || '经营基调状态卡',
            source: 'guidance_tone',
            data: {
              has_visualization: true,
              type: 'insight_card',
              meta_type: 'guidance_tone',
              title: toneCard.title,
              headline: toneCard.headline,
              contribution: toneCard.contribution
            }
          })
        }
      }

      const keyMetrics = spec.key_metrics || spec.keyMetrics || {}
      if (keyMetrics.chart_type === 'status_bar' && Array.isArray(keyMetrics.items)) {
        const labels = []
        const values = []
        const notes = []
        const findings = []
        keyMetrics.items.forEach(item => {
          const valueNum = this.parseNumericValue(item?.value)
          if (valueNum === null || !item?.name) return
          labels.push(String(item.name))
          values.push(valueNum)
          const noteText = String(item?.note || '').trim()
          notes.push(noteText)
          if (noteText) {
            findings.push(`${item.name}：${noteText}`)
          } else {
            findings.push(`${item.name}：${item.value || valueNum}`)
          }
        })
        if (labels.length >= 2) {
          const modelInsights = this.filterGuidanceInsights(
            this.getGuidanceInsights(payload, 'key_metrics'),
            labels
          )
          const insightDescription = notes.filter(Boolean).slice(0, 2).join('；')
            || `核心指标集中在 ${labels.slice(0, 3).join('、')}`
          cards.push({
            id: 'guidance-metrics-chart',
            question: '核心指标锚点',
            source: 'guidance_metrics',
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || this.buildGuidanceInsights(insightDescription, findings),
              chart_config: {
                chart_type: 'bar',
                traces: [
                  {
                    name: '核心指标',
                    type: 'bar',
                    x: labels,
                    y: values,
                    text: notes,
                    hovertemplate: '%{x}<br>%{y}<extra></extra>'
                  }
                ],
                layout: {
                  title: '核心指标锚点',
                  xaxis_title: '指标',
                  yaxis_title: '数值'
                }
              }
            }
          })
        }
      }

      const executionPath = spec.execution_path || spec.executionPath || {}
      if (executionPath.chart_type === 'structure_change' && Array.isArray(executionPath.items)) {
        const labels = []
        const values = []
        const findings = []
        executionPath.items.forEach(item => {
          const valueNum = this.parseNumericValue(item?.evidence)
          if (valueNum === null || !item?.action) return
          labels.push(String(item.action))
          values.push(valueNum)
          findings.push(`${item.action}：${item.evidence || valueNum}`)
        })
        if (labels.length >= 2) {
          const modelInsights = this.filterGuidanceInsights(
            this.getGuidanceInsights(payload, 'execution_path'),
            labels
          )
          const insightDescription = `关键执行路径聚焦在 ${labels.slice(0, 3).join('、')}`
          cards.push({
            id: 'guidance-execution-chart',
            question: '关键执行路径',
            source: 'guidance_execution',
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || this.buildGuidanceInsights(insightDescription, findings),
              chart_config: {
                chart_type: 'bar',
                traces: [
                  {
                    name: '执行路径',
                    type: 'bar',
                    x: labels,
                    y: values
                  }
                ],
                layout: {
                  title: '关键执行路径',
                  xaxis_title: '执行动作',
                  yaxis_title: '证据数值'
                }
              }
            }
          })
        }
      }

      const uncertainty = spec.uncertainty || {}
      if (uncertainty.chart_type === 'risk_matrix' && Array.isArray(uncertainty.items)) {
        const probLabels = []
        const impactLabels = []
        const risks = []
        const findings = []
        uncertainty.items.forEach(item => {
          if (!item?.risk || !item?.impact || !item?.probability) return
          probLabels.push(String(item.probability))
          impactLabels.push(String(item.impact))
          const riskName = String(item.risk)
          risks.push(riskName)
          findings.push(`${riskName}：概率${item.probability}，影响${item.impact}`)
        })
        if (probLabels.length >= 2) {
          const modelInsights = this.filterGuidanceInsights(
            this.getGuidanceInsights(payload, 'uncertainty'),
            risks
          )
          const insightDescription = `关注风险：${risks.slice(0, 3).join('、')}`
          cards.push({
            id: 'guidance-risk-chart',
            question: '不确定性与边界',
            source: 'guidance_risk',
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || this.buildGuidanceInsights(insightDescription, findings),
              chart_config: {
                chart_type: 'scatter',
                traces: [
                  {
                    name: '风险矩阵',
                    type: 'scatter',
                    mode: 'markers+text',
                    x: probLabels,
                    y: impactLabels,
                    text: risks,
                    textposition: 'top center'
                  }
                ],
                layout: {
                  title: '不确定性与边界',
                  xaxis_title: '概率',
                  yaxis_title: '影响对象'
                }
              }
            }
          })
        }
      }

      return cards
    },
    appendBusinessGuidanceVisualTables(payload) {
      const cards = this.buildGuidanceVisualizationCards(payload)
      cards.forEach(card => {
        const existingIndex = this.visualizations.findIndex(viz => viz.id === card.id)
        if (existingIndex >= 0) {
          this.$set(this.visualizations, existingIndex, card)
          return
        }
        this.visualizations.push(card)
      })
    },
    async appendBusinessGuidanceTextVisualizations(answerText, question) {
      if (!answerText || typeof answerText !== 'string') return
      if (this.visualizations.some(viz => viz.source === 'guidance_text_viz')) return
      try {
        const response = await fetch('/agent/visualize-text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: question || '业绩指引分析',
            answer: answerText,
            max_views: 3
          })
        })
        if (!response.ok) {
          console.warn('⚠️ [AgentAnalysisPage] 业绩指引文本可视化请求失败:', response.status)
          return
        }
        const textViz = await response.json()
        if (textViz && Array.isArray(textViz.visualizations)) {
          textViz.visualizations.forEach((viz, idx) => {
            if (!viz || !viz.has_visualization) return
            this.visualizations.push({
              id: `${Date.now().toString()}-guidance-text-viz-${idx}`,
              question: viz.display_title || viz.query || question || '业绩指引分析可视化',
              source: 'guidance_text_viz',
              data: viz
            })
          })
        } else if (textViz && textViz.has_visualization) {
          this.visualizations.push({
            id: `${Date.now().toString()}-guidance-text-viz`,
            question: textViz.display_title || textViz.query || question || '业绩指引分析可视化',
            source: 'guidance_text_viz',
            data: textViz
          })
        }
      } catch (error) {
        console.warn('⚠️ [AgentAnalysisPage] 业绩指引文本可视化请求异常:', error)
      }
    },
    appendBusinessHighlightsSpecTables(toolOutput) {
      if (!toolOutput || typeof toolOutput !== 'object') return false
      const spec = toolOutput.visualization_spec || toolOutput.visualizationSpec || {}
      const metricAnchor = spec.metric_anchor || spec.metricAnchor || {}
      if (!metricAnchor || typeof metricAnchor !== 'object') return false

      const appendTableCard = (vizId, question, table, summary = '') => {
        if (!table || typeof table !== 'object') return
        const exists = this.visualizations.some(viz => viz.id === vizId)
        if (exists) return
        this.visualizations.push({
          id: vizId,
          question,
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'financial_table',
            table,
            summary
          }
        })
      }

      const summaryTable = metricAnchor.key_metrics_summary_table || metricAnchor.keyMetricsSummaryTable
      if (summaryTable && typeof summaryTable === 'object') {
        appendTableCard(
          'biz-table-summary-v2',
          summaryTable.title || metricAnchor.summary_title || metricAnchor.summaryTitle || '关键业务指标汇总',
          summaryTable,
          '关键业务指标汇总'
        )
      }

      const segmentTables = Array.isArray(metricAnchor.segment_tables)
        ? metricAnchor.segment_tables
        : (Array.isArray(metricAnchor.segmentTables) ? metricAnchor.segmentTables : [])
      segmentTables.forEach((segment, idx) => {
        const segmentId = segment.segment_id || segment.segmentId || `segment-${idx}`
        const segmentName = segment.segment_name || segment.segmentName || segmentId
        const table = segment.table
        appendTableCard(
          `biz-table-v2-${segmentId}`,
          `${segmentName}指标`,
          table,
          segment.conclusion || ''
        )
      })

      return !!(summaryTable || segmentTables.length)
    },
    appendBusinessHighlightsTables(toolOutput) {
      if (!toolOutput || typeof toolOutput !== 'object') return
      const hasSpecTables = this.appendBusinessHighlightsSpecTables(toolOutput)
      if (hasSpecTables) return
      const segmentTables = Array.isArray(toolOutput.segment_tables) ? toolOutput.segment_tables : []
      const performanceReport = toolOutput.business_performance_report || toolOutput.businessPerformanceReport || {}
      const segmentInsights = Array.isArray(performanceReport.segment_insights)
        ? performanceReport.segment_insights
        : []

      const insightMap = new Map()
      segmentInsights.forEach(insight => {
        if (!insight || !insight.segment_id) return
        insightMap.set(insight.segment_id, insight)
      })

      const buildInsightSummary = (insight) => {
        if (!insight) return ''
        const parts = []
        if (insight.headline) parts.push(insight.headline)
        if (Array.isArray(insight.drivers) && insight.drivers.length > 0) {
          parts.push(`驱动：${insight.drivers.slice(0, 2).join('；')}`)
        }
        if (Array.isArray(insight.strategy_link) && insight.strategy_link.length > 0) {
          parts.push(`策略：${insight.strategy_link.slice(0, 2).join('；')}`)
        }
        if (Array.isArray(insight.risks_and_watchlist) && insight.risks_and_watchlist.length > 0) {
          parts.push(`风险：${insight.risks_and_watchlist.slice(0, 2).join('；')}`)
        }
        return parts.join(' | ')
      }

      segmentTables.forEach((segment, idx) => {
        const segmentId = segment.segment_id || `segment-${idx}`
        const vizId = `biz-table-${segmentId}`
        const exists = this.visualizations.some(viz => viz.id === vizId)
        if (exists) return

        const insight = insightMap.get(segmentId)
        const reportSummary = buildInsightSummary(insight)
        const tableSummary = segment.conclusion || segment.table?.insight || ''
        const summary = reportSummary || tableSummary

        if (segment.table && summary && !segment.table.insight) {
          segment.table.insight = summary
        }

        this.visualizations.push({
          id: vizId,
          question: `${segment.segment_name || segmentId}指标`,
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'financial_table',
            table: segment.table,
            summary
          }
        })
      })
    },
    appendBusinessHighlightsInsights(toolOutput) {
      if (!toolOutput || typeof toolOutput !== 'object') return
      const spec = toolOutput.visualization_spec || toolOutput.visualizationSpec || {}
      const growthEngine = spec.growth_engine || spec.growthEngine || {}
      const growthItems = Array.isArray(growthEngine.items) ? growthEngine.items : []
      if (growthItems.length > 0) {
        growthItems.forEach((item, idx) => {
          if (!item) return
          const segmentId = item.segment_id || item.segmentId || `segment-${idx}`
          const vizId = `biz-insight-v2-${segmentId}`
          const exists = this.visualizations.some(viz => viz.id === vizId)
          if (exists) return
          this.visualizations.push({
            id: vizId,
            question: `${item.segment_name || item.segmentName || segmentId}洞察`,
            source: 'business_highlights',
            data: {
              has_visualization: true,
              type: 'insight_card',
              title: item.segment_name || item.segmentName || segmentId,
              headline: item.headline || '',
              contribution: item.contribution || ''
            }
          })
        })
        return
      }
      const performanceReport = toolOutput.business_performance_report || toolOutput.businessPerformanceReport || {}
      const segmentInsights = Array.isArray(performanceReport.segment_insights)
        ? performanceReport.segment_insights
        : []
      if (!segmentInsights.length) return

      segmentInsights.forEach((insight, idx) => {
        if (!insight) return
        const segmentId = insight.segment_id || `segment-${idx}`
        const vizId = `biz-insight-${segmentId}`
        const exists = this.visualizations.some(viz => viz.id === vizId)
        if (exists) return

        this.visualizations.push({
          id: vizId,
          question: `${insight.segment_name || segmentId}洞察`,
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'insight_card',
            title: insight.segment_name || segmentId,
            headline: insight.headline || '',
            contribution: Array.isArray(insight.contribution) ? insight.contribution.join('；') : (insight.contribution || ''),
            drivers: Array.isArray(insight.drivers) ? insight.drivers : [],
            strategy_link: Array.isArray(insight.strategy_link) ? insight.strategy_link : [],
            risks_and_watchlist: Array.isArray(insight.risks_and_watchlist) ? insight.risks_and_watchlist : []
          }
        })
      })
    },
    appendBusinessHighlightsCharts(toolOutput) {
      if (!toolOutput || typeof toolOutput !== 'object') return
      const segmentTables = Array.isArray(toolOutput.segment_tables) ? toolOutput.segment_tables : []
      const performanceReport = toolOutput.business_performance_report || toolOutput.businessPerformanceReport || {}
      const segmentInsights = Array.isArray(performanceReport.segment_insights)
        ? performanceReport.segment_insights
        : []

      const metricPriority = [
        '营业收入', '收入', '净利润', '利润', '贷款余额',
        'AUM', '原保费收入', '成交额', '产品收入', 'MAU'
      ]
      const pickMetricRow = (rows = []) => {
        for (const keyword of metricPriority) {
          const found = rows.find(row => row && row[0] && String(row[0]).includes(keyword))
          if (found) return found
        }
        return rows.find(row => row && this.parseMetricValue(row[1]) !== null)
      }

      const segmentNames = []
      const segmentValues = []
      const segmentMetricLabels = []
      const segmentNameMap = {}
      segmentTables.forEach(segment => {
        const segmentId = segment.segment_id
        const segmentName = segment.segment_name || segmentId
        if (segmentId) segmentNameMap[segmentId] = segmentName
        const rows = segment?.table?.rows || []
        const row = pickMetricRow(rows)
        if (!row) return
        const value = this.parseMetricValue(row[1])
        if (value === null) return
        segmentNames.push(segmentName)
        segmentValues.push(value)
        segmentMetricLabels.push(row[0])
      })

      if (segmentNames.length >= 2) {
        this.visualizations.push({
          id: `biz-segment-compare-${Date.now()}`,
          question: '业务板块核心指标对比',
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'chart',
            chart_config: {
              traces: [{
                type: 'bar',
                name: '当前年度',
                x: segmentNames,
                y: segmentValues,
                text: segmentMetricLabels,
                textposition: 'auto'
              }],
              layout: {
                title: '业务板块核心指标对比',
                xaxis_title: '业务板块',
                yaxis_title: '指标值'
              }
            }
          }
        })
      }

      segmentTables.forEach((segment, idx) => {
        const rows = segment?.table?.rows || []
        const metrics = rows
          .map(row => ({
            name: row?.[0],
            value: this.parseMetricValue(row?.[1])
          }))
          .filter(item => item.name && item.value !== null)
          .slice(0, 6)
        if (metrics.length < 3) return

        this.visualizations.push({
          id: `biz-segment-metrics-${segment.segment_id || idx}`,
          question: `${segment.segment_name || segment.segment_id} 指标对比`,
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'chart',
            chart_config: {
              traces: [{
                type: 'bar',
                name: segment.segment_name || segment.segment_id,
                x: metrics.map(m => m.name),
                y: metrics.map(m => m.value),
                textposition: 'auto'
              }],
              layout: {
                title: `${segment.segment_name || segment.segment_id} 指标对比`,
                xaxis_title: '指标',
                yaxis_title: '指标值'
              }
            }
          }
        })
      })

      const segmentShareLabels = []
      const segmentShareValues = []
      segmentTables.forEach(segment => {
        const rows = segment?.table?.rows || []
        const shareRow = rows.find(row => row && row[0] && String(row[0]).includes('占比'))
        if (!shareRow) return
        const value = this.parseMetricValue(shareRow[1])
        if (value === null) return
        segmentShareLabels.push(segment.segment_name || segment.segment_id)
        segmentShareValues.push(value)
      })

      if (segmentShareLabels.length >= 2) {
        const shareTraces = segmentShareLabels.map((label, idx) => ({
          type: 'bar',
          name: label,
          x: ['业务结构'],
          y: [segmentShareValues[idx]]
        }))
        this.visualizations.push({
          id: `biz-structure-share-${Date.now()}`,
          question: '业务结构占比对比',
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'chart',
            chart_config: {
              traces: shareTraces,
              layout: {
                title: '业务结构占比对比',
                barmode: 'stack',
                xaxis_title: '',
                yaxis_title: '占比(%)'
              }
            }
          }
        })
      } else if (segmentNames.length >= 2) {
        this.visualizations.push({
          id: `biz-structure-treemap-${Date.now()}`,
          question: '业务结构分布',
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'chart',
            chart_config: {
              traces: [{
                type: 'treemap',
                labels: segmentNames,
                parents: segmentNames.map(() => ''),
                values: segmentValues
              }],
              layout: {
                title: '业务结构分布'
              }
            }
          }
        })
      }

      if (segmentInsights.length >= 2) {
        const dimensions = ['规模增长', '客户增长', '结构优化', '数字化渗透', '风险改善']
        const keywords = {
          '规模增长': ['规模', '增长', '提升', '扩张', '收入', '贷款', '放款', '投放'],
          '客户增长': ['客户', '用户', 'AUM', '户', '客户数', '注册'],
          '结构优化': ['结构', '优化', '转型', '调整', '质量', '组合'],
          '数字化渗透': ['数字', '科技', '平台', '线上', 'AI', '智能', '系统'],
          '风险改善': ['风险', '不良', '减值', '资产质量', '风控', '拨备']
        }
        const negativeKeywords = ['上升', '恶化', '压力', '增加', '攀升']
        const scoreInsight = (insight, dimension) => {
          const textParts = [
            insight.headline,
            ...(Array.isArray(insight.contribution) ? insight.contribution : []),
            ...(Array.isArray(insight.drivers) ? insight.drivers : []),
            ...(Array.isArray(insight.strategy_link) ? insight.strategy_link : []),
            ...(Array.isArray(insight.risks_and_watchlist) ? insight.risks_and_watchlist : [])
          ]
          const text = textParts.filter(Boolean).join(' ')
          let hits = 0
          keywords[dimension].forEach(word => {
            if (text.includes(word)) hits += 1
          })
          let score = Math.min(5, 2 + hits)
          if (dimension === '风险改善') {
            negativeKeywords.forEach(word => {
              if (text.includes(word)) score = Math.max(1, score - 1)
            })
          }
          return score
        }

        const traces = segmentInsights.map((insight, idx) => {
          const segmentId = insight.segment_id || `segment-${idx}`
          const name = insight.segment_name || segmentNameMap[segmentId] || segmentId
          const values = dimensions.map(dim => scoreInsight(insight, dim))
          return {
            type: 'scatterpolar',
            name,
            r: values,
            theta: dimensions,
            fill: 'toself'
          }
        })

        this.visualizations.push({
          id: `biz-segment-radar-${Date.now()}`,
          question: '业务板块能力雷达',
          source: 'business_highlights',
          data: {
            has_visualization: true,
            type: 'chart',
            chart_config: {
              traces,
              layout: {
                title: '业务板块能力雷达',
                polar: { radialaxis: { visible: true, range: [0, 5] } }
              }
            }
          }
        })
      }
    },
    formatBusinessHighlightsReport(payload) {
      if (!payload || typeof payload !== 'object') return ''
      const highlights = Array.isArray(payload.highlights) ? payload.highlights : []
      const performanceReport = payload.business_performance_report || payload.businessPerformanceReport || {}
      const segmentInsights = Array.isArray(performanceReport.segment_insights)
        ? performanceReport.segment_insights
        : []
      const segmentMap = new Map()

      highlights.forEach(item => {
        if (!item) return
        const key = item.business_type || '业务板块'
        segmentMap.set(key, { name: key, highlight: item })
      })

      segmentInsights.forEach((insight, idx) => {
        if (!insight) return
        const key = insight.segment_name || insight.segment_id || `业务板块${idx + 1}`
        const entry = segmentMap.get(key) || { name: key }
        entry.insight = insight
        segmentMap.set(key, entry)
      })

      if (segmentMap.size === 0) return ''

      const sections = []
      if (payload.overall_summary) {
        sections.push(`### 总体结论\n${payload.overall_summary}`)
      }
      segmentMap.forEach(entry => {
        const lines = [`### ${entry.name}`]
        if (entry.highlight?.highlights) {
          lines.push(`- 业务亮点：${entry.highlight.highlights}`)
        }
        if (Array.isArray(entry.highlight?.achievements) && entry.highlight.achievements.length) {
          lines.push(`- 主要成就：${entry.highlight.achievements.join('；')}`)
        }
        const insight = entry.insight
        if (insight?.headline) {
          lines.push(`- 一句话结论：${insight.headline}`)
        }
        if (insight?.contribution) {
          const text = Array.isArray(insight.contribution) ? insight.contribution.join('；') : insight.contribution
          if (text) lines.push(`- 贡献：${text}`)
        }
        if (insight?.drivers) {
          const text = Array.isArray(insight.drivers) ? insight.drivers.join('；') : insight.drivers
          if (text) lines.push(`- 驱动：${text}`)
        }
        if (insight?.strategy_link) {
          const text = Array.isArray(insight.strategy_link) ? insight.strategy_link.join('；') : insight.strategy_link
          if (text) lines.push(`- 战略联动：${text}`)
        }
        if (insight?.risks_and_watchlist) {
          const text = Array.isArray(insight.risks_and_watchlist)
            ? insight.risks_and_watchlist.join('；')
            : insight.risks_and_watchlist
          if (text) lines.push(`- 风险关注：${text}`)
        }
        sections.push(lines.join('\n'))
      })

      return sections.join('\n\n')
    },
    formatBusinessGuidanceReport(payload) {
      if (!payload || typeof payload !== 'object') return ''
      // 支持后端返回的完整报告结构：{ business_guidance, extracted_data, ... }
      let resolved = payload.business_guidance != null ? payload.business_guidance : payload
      // 若顶层无列表数据，尝试从 raw_output 取完整 payload（LlamaIndex 等包装格式）
      const hasListData = (p) => {
        if (!p || typeof p !== 'object') return false
        const km = p.key_metrics || p.keyMetrics
        const bg = p.business_specific_guidance || p.businessSpecificGuidance
        const rw = p.risk_warnings || p.riskWarnings
        return (Array.isArray(km) && km.length > 0) ||
          (Array.isArray(bg) && bg.length > 0) ||
          (Array.isArray(rw) && rw.length > 0)
      }
      if (!hasListData(resolved) && payload.raw_output != null) {
        let raw = payload.raw_output
        if (typeof raw === 'string') {
          try {
            raw = JSON.parse(raw)
          } catch (e) {
            const m = raw.match(/\{[\s\S]*\}/)
            if (m) try { raw = JSON.parse(m[0]) } catch (e2) { raw = null }
          }
        }
        if (raw && typeof raw === 'object' && hasListData(raw)) {
          resolved = raw
        }
      }
      const payload_ = resolved

      const guidancePeriod = payload_.guidance_period || payload_.guidancePeriod || ''
      const expectedPerformance = payload_.expected_performance || payload_.expectedPerformance || ''
      const keyMetrics = Array.isArray(payload_.key_metrics || payload_.keyMetrics)
        ? (payload_.key_metrics || payload_.keyMetrics)
        : []
      const businessGuidance = Array.isArray(payload_.business_specific_guidance || payload_.businessSpecificGuidance)
        ? (payload_.business_specific_guidance || payload_.businessSpecificGuidance)
        : []
      const riskWarnings = Array.isArray(payload_.risk_warnings || payload_.riskWarnings)
        ? (payload_.risk_warnings || payload_.riskWarnings)
        : []

      // 将对象项转为可读字符串（兼容 指标名/数值/变化/解读、执行动作/证据/影响、风险名称/影响对象 等结构）
      const itemToText = (item) => {
        if (item == null) return ''
        if (typeof item === 'string') return item
        if (typeof item !== 'object') return String(item)
        const name = item['指标名'] ?? item.metric_name ?? item.name ?? item.执行动作 ?? item.action ?? item.风险名称 ?? item.risk_name ?? item.risk ?? ''
        const value = item['数值'] ?? item.value ?? item.证据 ?? item.evidence ?? item.影响 ?? item.impact ?? ''
        const change = item['变化'] ?? item.change ?? ''
        const desc = item['解读'] ?? item.description ?? item.影响 ?? item.impact ?? ''
        const parts = [name]
        if (value !== '' && value != null) parts.push(String(value))
        if (change !== '' && change != null) parts.push(`（${change}）`)
        if (desc !== '' && desc != null && desc !== value) parts.push(desc)
        return parts.filter(Boolean).join(' ')
      }

      // 提取额外的指标数据
      const parentProfit = payload_.parent_net_profit_range || payload_.parentNetProfitRange
      const parentProfitGrowth = payload_.parent_net_profit_growth_range || payload_.parentNetProfitGrowthRange
      const nonRecurringProfit = payload_.non_recurring_profit_range || payload_.nonRecurringProfitRange
      const epsRange = payload_.eps_range || payload_.epsRange
      const revenueRange = payload_.revenue_range || payload_.revenueRange

      const sections = []

      // 一、经营目标方向
      if (guidancePeriod || expectedPerformance) {
        const lines = ['### 一、经营目标方向']
        if (guidancePeriod) {
          lines.push(`**指引期间**：${guidancePeriod}`)
        }
        if (expectedPerformance) {
          lines.push(`\n${expectedPerformance}`)
        }
        sections.push(lines.join('\n'))
      }

      // 二、核心指标锚点
      const metricItems = []
      if (parentProfit) metricItems.push(`归母净利润：${parentProfit}`)
      if (parentProfitGrowth) metricItems.push(`归母净利润增长率：${parentProfitGrowth}`)
      if (nonRecurringProfit) metricItems.push(`扣非净利润：${nonRecurringProfit}`)
      if (epsRange) metricItems.push(`基本每股收益：${epsRange}`)
      if (revenueRange) metricItems.push(`营业收入：${revenueRange}`)

      const allMetrics = metricItems.length > 0 ? metricItems : keyMetrics.map(itemToText).filter(Boolean)
      if (allMetrics.length > 0) {
        const lines = ['### 二、核心指标锚点']
        allMetrics.forEach(metric => {
          if (metric) {
            lines.push(`- ${metric}`)
          }
        })
        sections.push(lines.join('\n'))
      }

      // 三、关键执行路径
      const guidanceLines = businessGuidance.map(itemToText).filter(Boolean)
      if (guidanceLines.length > 0) {
        const lines = ['### 三、关键执行路径']
        guidanceLines.forEach(g => {
          if (g) lines.push(`- ${g}`)
        })
        sections.push(lines.join('\n'))
      }

      // 四、不确定性与边界
      const riskLines = riskWarnings.map(itemToText).filter(Boolean)
      if (riskLines.length > 0) {
        const lines = ['### 四、不确定性与边界']
        riskLines.forEach(r => {
          if (r) lines.push(`- ${r}`)
        })
        sections.push(lines.join('\n'))
      }

      return sections.join('\n\n')
    },
    async handleSubmit() {
      if (!this.inputText.trim() || this.loading) return
      
      const question = this.inputText.trim()
      this.inputText = ''
      this.currentQuestion = question
      this.loading = true
      this.currentStep = 0
      
      // 清空之前的结果
      this.answer = ''
      this.evidenceMappings = []
      this.visualizations = []
      this.structuredData = {
        financialReview: null,
        businessHighlights: null,
        businessGuidance: null,
        dupontAnalysis: null
      }
      
      // 模拟进度步骤 - 更智能的进度更新
      const stepInterval = setInterval(() => {
        if (this.currentStep < 3) {
          this.currentStep++
        }
      }, 3000)  // 每3秒更新一次，更符合实际处理时间
      
      try {
        const result = await this.onQuery(question)
        
        clearInterval(stepInterval)
        this.currentStep = 3
        
        // 添加调试日志
        console.log('🔍 [AgentAnalysisPage] 收到响应:', {
          status: result.status,
          hasAnswer: !!result.answer,
          answerLength: result.answer?.length || 0,
          toolCallsCount: result.tool_calls?.length || 0,
          hasVisualization: !!result.visualization,
          hasStructuredResponse: !!result.structured_response
        })
        
        if (result.status === 'success') {
          this.evidenceMappings = Array.isArray(result.evidence_mapping) ? result.evidence_mapping : []

          // 设置文本回答 - 确保有内容
          if (result.answer && result.answer.trim()) {
            this.answer = result.answer
            console.log('✅ [AgentAnalysisPage] 设置文本回答，长度:', this.answer.length)
          } else {
            // 如果没有answer，尝试从工具调用中提取
            if (result.tool_calls && result.tool_calls.length > 0) {
              this.answer = `✅ Agent分析完成，共执行了 ${result.tool_calls.length} 个工具调用。\n\n请查看下方的结构化数据卡片。`
              console.log('⚠️ [AgentAnalysisPage] 没有answer，使用默认提示')
            } else {
              this.answer = '✅ Agent分析完成，但未返回详细内容。'
            }
          }
          
          // 处理可视化
          if (result.visualization && result.visualization.has_visualization) {
            console.log('📊 [AgentAnalysisPage] 添加可视化数据')
            if (result.visualization.type === 'financial_tables' && Array.isArray(result.visualization.tables)) {
              const getTableSourceLabel = (title = '') => {
                if (title.includes('资产') || title.includes('负债')) return '资产负债表'
                if (title.includes('营业收入') || title.includes('营业支出') || title.includes('收入') || title.includes('支出') || title.includes('利润')) return '利润表'
                if (title.includes('现金流')) return '现金流量表'
                return '财务报表'
              }
              const formatTableTitle = (title) => {
                const base = title || '财务表格'
                return `${base}（${getTableSourceLabel(base)}）`
              }
              result.visualization.tables
                .filter(table => table)
                .forEach((table, idx) => {
                  this.visualizations.push({
                    id: `${Date.now().toString()}-${idx}`,
                    question: formatTableTitle(table.title),
                    data: {
                      has_visualization: true,
                      type: 'financial_table',
                      table
                    }
                  })
                })
            } else {
              this.visualizations.push({
                id: Date.now().toString(),
                question: question,
                data: result.visualization
              })
            }
          }
          
          // 处理工具调用结果 - 优先处理
          if (result.tool_calls && Array.isArray(result.tool_calls)) {
            console.log(`🔧 [AgentAnalysisPage] 处理 ${result.tool_calls.length} 个工具调用`)
            result.tool_calls.forEach((toolCall, index) => {
              const toolName = toolCall.tool_name
              // 从工具调用中提取实际输出（可能是 raw_output 字段）
              let toolOutput = toolCall.tool_output
              
              // 如果 tool_output 含 raw_output，优先解析为对象并与外层字段合并，避免前端直接展示原始JSON字符串
              if (toolOutput && typeof toolOutput === 'object' && toolOutput.raw_output !== undefined) {
                const rawOutput = toolOutput.raw_output
                let parsedRaw = rawOutput
                if (typeof rawOutput === 'string') {
                  try {
                    parsedRaw = JSON.parse(rawOutput)
                  } catch (e) {
                    parsedRaw = null
                  }
                }
                if (parsedRaw && typeof parsedRaw === 'object' && !Array.isArray(parsedRaw)) {
                  toolOutput = { ...parsedRaw, ...toolOutput }
                  delete toolOutput.raw_output
                  console.log(`  [${index + 1}] 从 tool_output.raw_output 解析并合并对象`)
                } else if (typeof rawOutput === 'string' && toolName !== 'generate_business_guidance') {
                  toolOutput = rawOutput
                  console.log(`  [${index + 1}] 使用 tool_output.raw_output 字符串`)
                }
              }
              
              console.log(`  [${index + 1}] 工具: ${toolName}`, {
                hasOutput: !!toolOutput,
                outputType: typeof toolOutput,
                hasError: !!(toolOutput && toolOutput.error)
              })
              
              // 跳过错误输出
              if (toolOutput && toolOutput.error) {
                console.warn(`⚠️ 工具 ${toolName} 执行失败:`, toolOutput.error)
                return
              }
              
              // 处理各种工具的输出
              // 辅助函数：从工具输出中提取文本内容
              const extractTextFromToolOutput = (output) => {
                if (!output) return null
                
                // 如果是字符串，直接返回
                if (typeof output === 'string') {
                  return output
                }
                
                // 如果是对象，尝试提取文本字段
                if (typeof output === 'object') {
                  // 优先查找常见的文本字段
                  if (output.raw_output && typeof output.raw_output === 'string') {
                    return output.raw_output
                  }
                  if (output.content && typeof output.content === 'string') {
                    return output.content
                  }
                  if (output.text && typeof output.text === 'string') {
                    return output.text
                  }
                  if (output.answer && typeof output.answer === 'string') {
                    return output.answer
                  }
                  // 如果有 summary 或 report 字段
                  if (output.summary && typeof output.summary === 'string') {
                    return output.summary
                  }
                  if (output.report && typeof output.report === 'string') {
                    return output.report
                  }
                  // 如果是包含 blocks 的对象（LlamaIndex 格式）
                  if (output.blocks && Array.isArray(output.blocks)) {
                    return output.blocks.map(block => {
                      if (typeof block === 'string') return block
                      if (block.text) return block.text
                      if (block.content) return block.content
                      return JSON.stringify(block)
                    }).join('\n\n')
                  }
                  // 最后尝试 JSON 序列化（用于调试）
                  console.warn('⚠️ [AgentAnalysisPage] 无法从工具输出中提取文本，使用 JSON 格式:', output)
                  return JSON.stringify(output, null, 2)
                }
                
                // 其他类型转换为字符串
                return String(output)
              }
              
              if (toolName === 'generate_dupont_analysis' && toolOutput) {
                // 杜邦分析保持为对象（需要特殊处理）
                this.structuredData.dupontAnalysis = toolOutput
                console.log('✅ [AgentAnalysisPage] 设置杜邦分析数据')
              } else if (toolName === 'generate_financial_review' && toolOutput) {
                // 提取文本内容
                const textContent = extractTextFromToolOutput(toolOutput)
                this.structuredData.financialReview = textContent || toolOutput
                console.log('✅ [AgentAnalysisPage] 设置财务点评数据', typeof textContent === 'string' ? `(文本，长度: ${textContent.length})` : '(对象)')
              } else if (toolName === 'generate_business_highlights' && toolOutput) {
                this.appendBusinessHighlightsTables(toolOutput)
                this.appendBusinessHighlightsInsights(toolOutput)
                this.appendBusinessHighlightsCharts(toolOutput)
                const summary = toolOutput?.overall_summary ? `**总体结论：** ${toolOutput.overall_summary}` : ''
                const formattedReport = this.formatBusinessHighlightsReport(toolOutput)
                const textContent = extractTextFromToolOutput(toolOutput)
                this.structuredData.businessHighlights = formattedReport || summary || textContent || toolOutput
                console.log('✅ [AgentAnalysisPage] 设置业务亮点数据')
              } else if (toolName === 'generate_business_guidance' && toolOutput) {
                // 后端可能返回完整报告 { business_guidance, ... } 或包装 { raw_output, summary, ... }；formatBusinessGuidanceReport 内会优先用 raw_output
                const formattedReport = this.formatBusinessGuidanceReport(toolOutput)
                this.structuredData.businessGuidance = formattedReport || extractTextFromToolOutput(toolOutput) || ''
                this.appendBusinessGuidanceVisualTables(toolOutput)
                // 若主回答是简短 summary 且包含「未明确」，用完整报告替换主内容区，避免二、三、四显示未明确
                if (formattedReport && formattedReport.length > 200 && this.answer && /未明确|年报未明确/.test(this.answer)) {
                  this.answer = formattedReport
                }
                console.log('✅ [AgentAnalysisPage] 设置业绩指引数据')
              } else if (toolName === 'generate_visualization' && toolOutput && toolOutput.has_visualization) {
                this.visualizations.push({
                  id: Date.now().toString() + '-' + this.visualizations.length,
                  question: question,
                  data: toolOutput
                })
                console.log('✅ [AgentAnalysisPage] 添加可视化数据（从工具调用）')
              } else if (toolName === 'generate_profit_forecast_and_valuation' && toolOutput) {
                // 处理投资策略数据（包含相关性分析、多元线性回归、聚类、因子分析）
                console.log('✅ [AgentAnalysisPage] 收到投资策略数据')
                
                // 提取综合洞察文本，显示在智能问答界面
                const comprehensiveInsight = toolOutput.comprehensive_insight || toolOutput.strategy_conclusion
                if (comprehensiveInsight) {
                  let insightText = ''
                  if (typeof comprehensiveInsight === 'string') {
                    insightText = comprehensiveInsight
                  } else if (typeof comprehensiveInsight === 'object') {
                    // 如果是对象，格式化显示
                    const parts = []
                    if (comprehensiveInsight.short_term) parts.push(`**短期配置：** ${comprehensiveInsight.short_term}`)
                    if (comprehensiveInsight.long_term) parts.push(`**长期配置：** ${comprehensiveInsight.long_term}`)
                    if (comprehensiveInsight.risk_control) parts.push(`**风险管控：** ${comprehensiveInsight.risk_control}`)
                    if (Array.isArray(comprehensiveInsight.key_signals) && comprehensiveInsight.key_signals.length > 0) {
                      parts.push(`**关键信号：**\n${comprehensiveInsight.key_signals.map(s => `- ${s}`).join('\n')}`)
                    }
                    insightText = parts.join('\n\n')
                  }
                  
                  // 将洞察添加到answer中
                  if (insightText && this.answer) {
                    this.answer = `${this.answer}\n\n## 投资策略综合洞察\n\n${insightText}`
                  } else if (insightText) {
                    this.answer = `## 投资策略分析\n\n${insightText}`
                  }
                }
                
                // 生成可视化视图（与洞察同时生成），以卡片形式放入可视化视图界面
                const cardInsights = toolOutput.card_insights || {}
                const buildCardInsight = (summary) => {
                  if (summary && typeof summary === 'string' && summary.trim()) {
                    return [{ insight_type: 'trend', description: summary.trim() }]
                  }
                  return []
                }
                // 1. 相关性分析可视化
                let correlationCard = null
                if (toolOutput.correlation_visualization && toolOutput.correlation_visualization.has_visualization) {
                  correlationCard = {
                    id: `investment-strategy-correlation-${Date.now()}`,
                    question: '相关性分析结果',
                    source: 'investment_strategy',
                    timestamp: new Date(),
                    type: 'chart',
                    data: {
                      has_visualization: true,
                      visualization_type: toolOutput.correlation_visualization.visualization_type || 'plotly',
                      chart_config: toolOutput.correlation_visualization.chart_config,
                      insights: buildCardInsight(cardInsights.correlation_summary)
                    }
                  }
                  this.visualizations.push(correlationCard)
                } else if (toolOutput.correlation_results && Array.isArray(toolOutput.correlation_results) && toolOutput.correlation_results.length > 0) {
                  const correlationData = toolOutput.correlation_results
                  const labels = correlationData.map(r => `${r.target_metric} vs ${r.driver_metric}`)
                  const correlations = correlationData.map(r => r.correlation || 0)
                  correlationCard = {
                    id: `investment-strategy-correlation-${Date.now()}`,
                    question: '相关性分析结果',
                    source: 'investment_strategy',
                    timestamp: new Date(),
                    type: 'chart',
                    data: {
                      has_visualization: true,
                      visualization_type: 'plotly',
                      chart_config: {
                        chart_type: 'bar',
                        traces: [{
                          type: 'bar',
                          name: '相关系数',
                          x: labels,
                          y: correlations,
                          marker: {
                            color: correlations.map(c => c >= 0 ? '#10b981' : '#ef4444')
                          }
                        }],
                        layout: {
                          title: '相关性分析结果',
                          xaxis_title: '指标对',
                          yaxis_title: '相关系数',
                          yaxis: { range: [-1, 1] }
                        }
                      },
                      insights: buildCardInsight(cardInsights.correlation_summary)
                    }
                  }
                  this.visualizations.push(correlationCard)
                }
                
                // 2. 因子分析可视化
                let factorCard = null
                if (toolOutput.factor_analysis && toolOutput.factor_analysis.factors && toolOutput.factor_analysis.factors.length > 0) {
                  const factorAnalysis = toolOutput.factor_analysis
                  const factors = factorAnalysis.factors || []
                  const varianceExplained = factorAnalysis.variance_explained || {}
                  const varianceValues = factors.map(f => varianceExplained[f] || 0)
                  factorCard = {
                    id: `investment-strategy-factor-${Date.now()}`,
                    question: '因子分析结果',
                    source: 'investment_strategy',
                    timestamp: new Date(),
                    type: 'chart',
                    data: {
                      has_visualization: true,
                      visualization_type: 'plotly',
                      chart_config: {
                        chart_type: 'bar',
                        traces: [{
                          type: 'bar',
                          name: '解释方差比例',
                          x: factors,
                          y: varianceValues,
                          marker: { color: '#764ba2' }
                        }],
                        layout: {
                          title: '因子分析 - 解释方差比例',
                          xaxis_title: '因子',
                          yaxis_title: '解释方差比例',
                          yaxis: { tickformat: '.1%' }
                        }
                      },
                      insights: buildCardInsight(cardInsights.factor_summary)
                    }
                  }
                  this.visualizations.push(factorCard)
                }
                
                // 4. 聚类分析可视化（如果存在）
                let clusteringCard = null
                if (toolOutput.clustering_model && toolOutput.clustering_model.group_results) {
                  const clustering = toolOutput.clustering_model
                  const groups = clustering.group_results || []
                  const groupNames = groups.map(g => g.group_name || '未知组')
                  clusteringCard = {
                    id: `investment-strategy-clustering-${Date.now()}`,
                    question: '聚类分析结果',
                    source: 'investment_strategy',
                    timestamp: new Date(),
                    type: 'chart',
                    data: {
                      has_visualization: true,
                      visualization_type: 'plotly',
                      chart_config: {
                        chart_type: 'bar',
                        traces: [{
                          type: 'bar',
                          name: '分组',
                          x: groupNames,
                          y: groups.map((_, i) => i + 1),
                          marker: { color: '#f59e0b' }
                        }],
                        layout: {
                          title: '聚类分析 - 投资组合分组',
                          xaxis_title: '分组',
                          yaxis_title: '组别编号'
                        }
                      },
                      insights: buildCardInsight(cardInsights.clustering_summary)
                    }
                  }
                  this.visualizations.push(clusteringCard)
                }
                const cardsToSync = [correlationCard, factorCard, clusteringCard].filter(Boolean)
                if (cardsToSync.length > 0 && typeof this.onAddVisualizationCards === 'function') {
                  this.onAddVisualizationCards(cardsToSync)
                }
              }
            })
          }
          
          // 处理结构化响应（备用）
          if (result.structured_response) {
            console.log('📋 [AgentAnalysisPage] 处理结构化响应')
            const structured = result.structured_response
            if (structured.dupont_analysis) {
              this.structuredData.dupontAnalysis = structured.dupont_analysis
            }
            if (structured.financial_review) {
              this.structuredData.financialReview = structured.financial_review
            }
            if (structured.business_highlights) {
              this.appendBusinessHighlightsTables(structured.business_highlights)
              this.appendBusinessHighlightsInsights(structured.business_highlights)
              this.appendBusinessHighlightsCharts(structured.business_highlights)
              const summary = structured.business_highlights?.overall_summary
                ? `**总体结论：** ${structured.business_highlights.overall_summary}`
                : ''
              const formattedReport = this.formatBusinessHighlightsReport(structured.business_highlights)
              this.structuredData.businessHighlights = formattedReport || summary || structured.business_highlights
            }
            if (structured.business_guidance) {
              const formattedReport = this.formatBusinessGuidanceReport(structured)
              this.structuredData.businessGuidance = formattedReport || ''
              this.appendBusinessGuidanceVisualTables(structured)
            }
          }

          if (this.structuredData.businessGuidance && this.answer) {
            await this.appendBusinessGuidanceTextVisualizations(this.answer, question)
          }
          
          // 先设置loading为false，确保UI能切换到结果视图
          this.loading = false
          
          // 确保数据已设置完成
          console.log('📋 [AgentAnalysisPage] 数据设置完成，准备渲染:', {
            answer: this.answer?.substring(0, 100),
            visualizationsCount: this.visualizations.length,
            structuredData: Object.keys(this.structuredData).filter(k => this.structuredData[k])
          })
          
          // 强制触发响应式更新
          this.$forceUpdate()
          
          // 渲染图表
          this.$nextTick(() => {
            console.log('🎨 [AgentAnalysisPage] 开始渲染图表')
            this.renderAllCharts()
            
            // 检查最终状态
            console.log('📊 [AgentAnalysisPage] 最终状态:', {
              loading: this.loading,
              hasAnswer: !!this.answer,
              answerLength: this.answer?.length || 0,
              visualizationsCount: this.visualizations.length,
              hasFinancialReview: !!this.structuredData.financialReview,
              hasBusinessHighlights: !!this.structuredData.businessHighlights,
              hasBusinessGuidance: !!this.structuredData.businessGuidance,
              hasDupontAnalysis: !!this.structuredData.dupontAnalysis,
              hasStructuredData: this.hasStructuredData,
              hasContent: this.hasContent
            })
            
            // 如果还是没有内容，再次检查
            if (!this.hasContent) {
              console.warn('⚠️ [AgentAnalysisPage] 警告：数据已设置但hasContent仍为false')
              console.warn('数据详情:', {
                answer: this.answer,
                structuredData: this.structuredData,
                visualizations: this.visualizations
              })
            }
          })
        } else {
          const errorMsg = result.error || result.detail || '未知错误'
          this.answer = `❌ 分析失败: ${errorMsg}`
          this.loading = false
          console.error('❌ [AgentAnalysisPage] 分析失败:', errorMsg)
        }
      } catch (error) {
        clearInterval(stepInterval)
        const errorMsg = error.message || '网络错误'
        this.answer = `❌ 分析失败: ${errorMsg}`
        this.loading = false
        console.error('❌ [AgentAnalysisPage] 异常:', error)
      } finally {
        // 确保loading被设置为false
        if (this.loading) {
          this.loading = false
        }
        this.currentStep = 0
        console.log('🏁 [AgentAnalysisPage] 查询完成，loading设置为false')
        
        // 最终检查
        this.$nextTick(() => {
          console.log('🔍 [AgentAnalysisPage] finally后的状态检查:', {
            loading: this.loading,
            hasContent: this.hasContent,
            hasAnswer: !!this.answer,
            hasStructuredData: this.hasStructuredData
          })
        })
      }
    },
    useSuggestion(suggestion) {
      this.inputText = suggestion
      this.$nextTick(() => {
        const textarea = this.$el.querySelector('.query-input')
        if (textarea) {
          textarea.focus()
        }
      })
    },
    parseMarkdown(text) {
      // 确保输入是字符串类型
      if (!text) {
        return ''
      }
      
      // 如果是对象，尝试转换为字符串
      if (typeof text === 'object') {
        console.warn('⚠️ [AgentAnalysisPage] parseMarkdown 收到对象类型，尝试转换:', text)
        try {
          // 尝试提取可能的文本字段
          if (text.answer) {
            text = text.answer
          } else if (text.content) {
            text = text.content
          } else if (text.text) {
            text = text.text
          } else {
            // 如果都没有，尝试 JSON 序列化（仅用于调试）
            text = JSON.stringify(text, null, 2)
          }
        } catch (e) {
          console.error('❌ [AgentAnalysisPage] 对象转换失败:', e)
          text = String(text)
        }
      }
      
      // 确保是字符串
      if (typeof text !== 'string') {
        text = String(text)
      }
      // 表格规范化：修复因子分析等报告里“表头+竖排数据”或制表符导致的表格错位（与 ChatArea 一致）
      text = this.normalizeFactorTables(text)
      // 加粗/样式规范化：** 与文字间空格（含全角、不间断空格）、单星号小节/因子改为双星号；单星号斜体去空格
      text = text.replace(/\*\*[\s\u3000\u00a0]+/g, '**').replace(/[\s\u3000\u00a0]+(\*\*)/g, '$1')
      text = text.replace(/\*([一二三四五六七八九十]+、)\*/g, '**$1**')
      text = text.replace(/\*(因子\d+[^*\n]*?)\*/g, '**$1**')
      text = text.replace(/(?<!\*)\*[\s\u3000\u00a0]+/g, '*').replace(/[\s\u3000\u00a0]+\*(?!\*)/g, '*')
      // 使用 marked 解析
      if (typeof marked !== 'undefined' && marked && marked.parse) {
        try {
          return marked.parse(text)
        } catch (e) {
          console.error('❌ [AgentAnalysisPage] marked.parse 失败:', e, '输入类型:', typeof text, '输入长度:', text.length)
          // 如果 marked 解析失败，返回原始文本（转义 HTML）
          return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
        }
      } else {
        // 如果 marked 不可用，返回转义后的文本
        return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
      }
    },
    /** 与 ChatArea 一致：规范化因子分析等报告中的表格，便于 Markdown 正确渲染 */
    normalizeFactorTables(text) {
      if (!text || typeof text !== 'string') return text
      let out = text
      out = out.split('\n').map(line => {
        if (line.indexOf('\t') === -1) return line
        const cells = line.split('\t').map(c => c.trim())
        return '| ' + cells.join(' | ') + ' |'
      }).join('\n')
      out = this.collapseSingleCellPipeRows(out)
      out = out.replace(
        /(?:^\|\s*)?(因子\d+：[^\n|]+?)\s*\|?\s*\n\s*([\d.]+)\s*\n\s*([\d.]+%)\s*\n\s*([\d.]+%)/gm,
        (_, name, v1, v2, v3) => `| ${name.trim()} | ${v1} | ${v2} | ${v3} |`
      )
      for (let cols = 10; cols >= 5; cols--) {
        const numPart = Array(cols).fill('([-\\d.]+)').join('\\s*\\n\\s*')
        const re = new RegExp('(?:^\\|\\s*)?(\\d{4})\\s*\\|?\\s*\\n\\s*' + numPart, 'gm')
        out = out.replace(re, (m, year, ...vals) => '| ' + year + ' | ' + vals.slice(0, cols).join(' | ') + ' |')
      }
      out = out.replace(
        /(?:^\|\s*)?(\d{4})\s*\|?\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)/gm,
        (_, year, s1, s2, s3) => `| ${year} | ${s1} | ${s2} | ${s3} |`
      )
      out = out.replace(
        /(?:^\|\s*)?([^\n|]{1,30}?)\s*\|?\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)(?:\s*\n\s*([-\d.]+))?/gm,
        (m, name, n1, n2, n3, n4) => {
          const nameTrim = name.trim()
          if (!nameTrim || /^[\d.]+$/.test(nameTrim)) return m
          if (/[。，、]/.test(nameTrim) || nameTrim.length > 25) return m
          if (n4 !== undefined) return `| ${nameTrim} | ${n1} | ${n2} | ${n3} | ${n4} |`
          return `| ${nameTrim} | ${n1} | ${n2} | ${n3} |`
        }
      )
      const headerLike = /年份|指标|因子|特征值|方差|贡献|得分|共同度|净息差|ROE|ROA|不良|拨备|成本|资本/
      out = out.replace(
        /(^\|[^\n]+\|)\s*\n(\s*)(^\|[^\n]+\|)/gm,
        (m, header, mid, dataRow) => {
          if (!headerLike.test(header)) return m
          if (/^\|[\s\-:|]+\|$/.test(header.trim())) return m
          if (/^\|[\s\-:|]+\|$/.test(dataRow.trim())) return m
          const colCount = (header.match(/\|/g) || []).length - 1
          if (colCount < 2) return m
          const sep = '|' + Array(colCount).fill('---').join('|') + '|'
          return header + '\n' + sep + '\n' + mid + dataRow
        }
      )
      // 移除表格中的“伪数据分隔行”（|---|---|...|），仅保留表头下第一条分隔线
      const lines = out.split('\n')
      const cleaned = []
      let inTable = false
      let dividerSeen = false
      const isPipe = (line) => {
        const t = (line || '').trim()
        return t.startsWith('|') && t.endsWith('|')
      }
      const isDivider = (line) => /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|$/.test((line || '').trim())
      for (const line of lines) {
        if (!isPipe(line)) {
          inTable = false
          dividerSeen = false
          cleaned.push(line)
          continue
        }
        if (!inTable) {
          inTable = true
          dividerSeen = false
          cleaned.push(line)
          continue
        }
        if (isDivider(line)) {
          if (!dividerSeen) {
            cleaned.push(line)
            dividerSeen = true
          }
          continue
        }
        cleaned.push(line)
      }
      out = cleaned.join('\n')
      return out
    },
    collapseSingleCellPipeRows(text) {
      const headerLike = /年份|指标|因子|特征值|方差|贡献|得分|共同度|净息差|ROE|ROA|不良|拨备|成本|资本|平均|信贷/
      const lines = text.split('\n')
      const result = []
      let buffer = []
      let colCount = 0
      let rowPrefix = []
      let needRest = 0
      let rawCellBuffer = []
      function isPipeLine(line) {
        const t = line.trim()
        return t.startsWith('|') && t.endsWith('|')
      }
      function isSeparatorLine(line) {
        const t = line.trim()
        return /^\|[\s\-:|]+\|$/.test(t)
      }
      function isHeaderLike(line) {
        return headerLike.test(line) && !isSeparatorLine(line)
      }
      function singleCellValue(line) {
        const cells = line.split('|').map(c => c.trim()).filter(c => c.length > 0)
        return cells.length === 1 ? cells[0] : null
      }
      function firstTwoCells(line) {
        const cells = line.split('|').map(c => c.trim())
        const nonEmpty = cells.filter(c => c.length > 0)
        return nonEmpty.length === 2 ? nonEmpty : null
      }
      function isRawCellLine(line) {
        const t = line.trim()
        return t.length > 0 && !t.startsWith('|') && (/^\d{4}$/.test(t) || /^-?[\d.]+%?$/.test(t))
      }
      function flushBuffer() {
        if (colCount >= 2 && buffer.length === colCount) {
          const vals = buffer.map(ln => singleCellValue(ln))
          if (vals.every(v => v !== null)) result.push('| ' + vals.join(' | ') + ' |')
          else buffer.forEach(l => result.push(l))
        } else buffer.forEach(l => result.push(l))
        buffer = []
      }
      function flushRowPrefix() {
        if (rowPrefix.length > 0) {
          result.push('| ' + rowPrefix.join(' | ') + ' |')
          rowPrefix = []
          needRest = 0
        }
      }
      function flushRawCellBuffer() {
        if (colCount >= 2 && rawCellBuffer.length === colCount) {
          result.push('| ' + rawCellBuffer.join(' | ') + ' |')
        } else rawCellBuffer.forEach(l => result.push(l))
        rawCellBuffer = []
      }
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        if (!isPipeLine(line)) {
          flushBuffer()
          flushRowPrefix()
          if (isRawCellLine(line) && colCount >= 2) {
            rawCellBuffer.push(line.trim())
            if (rawCellBuffer.length === colCount) {
              result.push('| ' + rawCellBuffer.join(' | ') + ' |')
              rawCellBuffer = []
            }
          } else {
            flushRawCellBuffer()
            colCount = 0
            result.push(line)
          }
          continue
        }
        if (isSeparatorLine(line)) {
          flushBuffer()
          flushRowPrefix()
          flushRawCellBuffer()
          result.push(line)
          continue
        }
        const twoCell = firstTwoCells(line)
        const single = singleCellValue(line) !== null
        if (isHeaderLike(line)) {
          flushBuffer()
          flushRowPrefix()
          flushRawCellBuffer()
          const n = (line.match(/\|/g) || []).length - 1
          if (n >= 2) colCount = n
          result.push(line)
          continue
        }
        if (twoCell !== null && colCount >= 2) {
          flushBuffer()
          const rest = colCount - 2
          if (rest <= 0) {
            result.push(line)
            continue
          }
          rowPrefix = [...twoCell]
          needRest = rest
          continue
        }
        if (single && needRest > 0) {
          rowPrefix.push(singleCellValue(line))
          needRest--
          if (needRest === 0) {
            result.push('| ' + rowPrefix.join(' | ') + ' |')
            rowPrefix = []
          }
          continue
        }
        if (single && colCount >= 2) {
          flushRowPrefix()
          buffer.push(line)
          if (buffer.length === colCount) {
            const vals = buffer.map(ln => singleCellValue(ln))
            if (vals.every(v => v !== null)) result.push('| ' + vals.join(' | ') + ' |')
            else buffer.forEach(l => result.push(l))
            buffer = []
          }
          continue
        }
        flushBuffer()
        flushRowPrefix()
        colCount = 0
        result.push(line)
      }
      flushBuffer()
      flushRowPrefix()
      flushRawCellBuffer()
      return result.join('\n')
    },
    removeVisualization(index) {
      const resolvedIndex = typeof index === 'number'
        ? index
        : this.visualizations.findIndex(viz => viz.id === index?.id)
      if (resolvedIndex < 0) return
      const viz = this.visualizations[resolvedIndex]
      if (viz?.data?.chart_config && window.Plotly) {
        try {
          const chartElement = document.getElementById(`agent-viz-${viz.id || resolvedIndex}`)
          if (chartElement) {
            window.Plotly.purge(chartElement)
          }
        } catch (error) {
          console.warn('清理图表失败:', error)
        }
      }
      this.visualizations.splice(resolvedIndex, 1)
    },
    renderAllCharts() {
      this.visualizations.forEach((viz, idx) => {
        if (
          viz.data &&
          viz.data.has_visualization &&
          viz.data.type !== 'financial_table' &&
          viz.data.type !== 'insight_card'
        ) {
          setTimeout(() => {
            this.renderChart(viz.id || idx, viz.data)
          }, 100 * (idx + 1))
        }
      })
    },
    renderChart(cardId, chartData) {
      if (!chartData?.chart_config || !window.Plotly) {
        return
      }
      
      this.$nextTick(() => {
        try {
          const chartConfig = chartData.chart_config
          const chartElementId = `agent-viz-${cardId}`
          const chartElement = document.getElementById(chartElementId)
          
          if (!chartElement) {
            setTimeout(() => {
              this.renderChart(cardId, chartData)
            }, 200)
            return
          }
          
          const traces = chartConfig.traces.map(trace => {
            const plotlyTrace = { 
              type: trace.type || 'scatter', 
              name: trace.name || '数据' 
            }
            if (trace.type === 'pie') {
              plotlyTrace.labels = trace.text || []
              plotlyTrace.values = trace.y || []
            } else if (trace.type === 'treemap') {
              plotlyTrace.labels = trace.labels || []
              plotlyTrace.parents = trace.parents || []
              plotlyTrace.values = trace.values || []
            } else if (trace.type === 'sankey') {
              plotlyTrace.node = trace.node || {}
              plotlyTrace.link = trace.link || {}
            } else if (trace.type === 'scatterpolar') {
              plotlyTrace.r = trace.r || []
              plotlyTrace.theta = trace.theta || []
              plotlyTrace.fill = trace.fill
            } else if (trace.type === 'heatmap') {
              plotlyTrace.z = trace.z || []
              plotlyTrace.x = trace.x || []
              plotlyTrace.y = trace.y || []
              if (trace.colorscale) plotlyTrace.colorscale = trace.colorscale
              if (trace.zmin != null) plotlyTrace.zmin = trace.zmin
              if (trace.zmax != null) plotlyTrace.zmax = trace.zmax
            } else {
              plotlyTrace.x = trace.x || []
              plotlyTrace.y = trace.y || []
            }
            if (trace.mode) plotlyTrace.mode = trace.mode
            if (trace.marker) plotlyTrace.marker = trace.marker
            if (trace.line) plotlyTrace.line = trace.line
            if (trace.type !== 'pie' && trace.text) plotlyTrace.text = trace.text
            if (trace.textposition) plotlyTrace.textposition = trace.textposition
            if (trace.hovertemplate) plotlyTrace.hovertemplate = trace.hovertemplate
            return plotlyTrace
          })
          
          const layout = {
            title: { 
              text: chartConfig.layout.title || '', 
              font: { size: 16, color: '#333' } 
            },
            xaxis: { 
              title: chartConfig.layout.xaxis_title || '', 
              gridcolor: '#e0e0e0' 
            },
            yaxis: { 
              title: chartConfig.layout.yaxis_title || '', 
              gridcolor: '#e0e0e0' 
            },
            height: chartConfig.layout.height || 400,
            template: chartConfig.layout.template || 'plotly_white',
            hovermode: chartConfig.layout.hovermode || 'closest',
            showlegend: chartConfig.layout.showlegend !== false,
            margin: { t: 50, r: 30, b: 60, l: 60 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            autosize: true
          }
          
          const config = { 
            responsive: true, 
            displayModeBar: true, 
            displaylogo: false, 
            modeBarButtonsToRemove: ['lasso2d', 'select2d'] 
          }
          
          if (window.Plotly && window.Plotly.newPlot) {
            try {
              window.Plotly.purge(chartElementId)
            } catch (e) {}
            
            window.Plotly.newPlot(chartElementId, traces, layout, config)
          }
        } catch (error) {
          console.error('渲染图表失败:', error)
        }
      })
    },
    getChartTypeName(type) {
      const names = {
        'bar': '柱状图',
        'line': '折线图',
        'pie': '饼图',
        'scatter': '散点图',
        'area': '面积图',
        'multi_line': '多折线图',
        'grouped_bar': '分组柱状图',
        'stacked_bar': '堆叠柱状图',
        'heatmap': '热力图',
        'box': '箱线图'
      }
      return names[type] || type
    },
    getInsightIcon(type) {
      const icons = {
        'trend': '📈',
        'comparison': '⚖️',
        'distribution': '📊',
        'correlation': '🔗',
        'anomaly': '⚠️'
      }
      return icons[type] || '💡'
    },
    getDupontValue(data, metric) {
      if (!data) return '—'
      if (data.full_data && data.full_data.level1 && data.full_data.level1[metric]) {
        const metricObj = data.full_data.level1[metric]
        return metricObj.formatted_value || metricObj.value || '—'
      }
      return data[metric] || '—'
    },
    copyAnswer() {
      if (!this.answer) return
      
      // 创建临时文本区域
      const textarea = document.createElement('textarea')
      textarea.value = this.answer.replace(/<[^>]*>/g, '') // 移除HTML标签
      document.body.appendChild(textarea)
      textarea.select()
      
      try {
        document.execCommand('copy')
        this.showToast('已复制到剪贴板', 'success')
      } catch (err) {
        this.showToast('复制失败', 'error')
      }
      
      document.body.removeChild(textarea)
    },
    exportReport() {
      if (!this.hasContent) {
        this.showToast('没有可导出的内容', 'warning')
        return
      }
      
      // 构建报告内容
      let reportContent = `# ${this.currentQuestion || 'Agent分析报告'}\n\n`
      reportContent += `生成时间: ${new Date().toLocaleString('zh-CN')}\n\n`
      
      if (this.answer) {
        reportContent += `## 分析结果\n\n${this.answer.replace(/<[^>]*>/g, '')}\n\n`
      }
      
      if (this.structuredData.financialReview) {
        reportContent += `## 财务点评\n\n${JSON.stringify(this.structuredData.financialReview, null, 2)}\n\n`
      }
      
      if (this.structuredData.businessHighlights) {
        reportContent += `## 业务亮点\n\n${JSON.stringify(this.structuredData.businessHighlights, null, 2)}\n\n`
      }
      
      if (this.structuredData.businessGuidance) {
        const bg = this.structuredData.businessGuidance
        reportContent += `## 业绩指引\n\n${typeof bg === 'string' ? bg : JSON.stringify(bg, null, 2)}\n\n`
      }
      
      if (this.structuredData.dupontAnalysis) {
        reportContent += `## 杜邦分析\n\n${JSON.stringify(this.structuredData.dupontAnalysis, null, 2)}\n\n`
      }
      
      // 创建Blob并下载
      const blob = new Blob([reportContent], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `Agent分析报告_${new Date().getTime()}.md`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      
      this.showToast('报告导出成功', 'success')
    },
    showToast(message, type = 'info') {
      // 简单的toast提示
      const toast = document.createElement('div')
      toast.className = `agent-toast agent-toast-${type}`
      toast.textContent = message
      document.body.appendChild(toast)
      
      setTimeout(() => {
        toast.classList.add('show')
      }, 10)
      
      setTimeout(() => {
        toast.classList.remove('show')
        setTimeout(() => {
          document.body.removeChild(toast)
        }, 300)
      }, 2000)
    }
  }
}
</script>

<style scoped>
.agent-analysis-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

/* 页面头部 */
.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 32px;
  display: flex;
  align-items: center;
  gap: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  flex-shrink: 0;
}

.back-btn {
  background: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.3);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.back-btn:hover {
  background: rgba(255,255,255,0.3);
  transform: translateX(-2px);
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-icon {
  font-size: 28px;
}

.page-title h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

/* 问题输入区域 */
.query-section {
  padding: 24px 32px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.query-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.query-input {
  flex: 1;
  padding: 14px 18px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  font-size: 15px;
  font-family: inherit;
  resize: none;
  transition: all 0.3s ease;
  line-height: 1.5;
}

.query-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.submit-btn {
  padding: 14px 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 8px;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-text {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 内容区域 */
.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  min-height: 0;
}

/* 加载状态 */
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.loading-card {
  background: white;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  max-width: 600px;
  width: 100%;
}

.spinner-large {
  width: 64px;
  height: 64px;
  border: 4px solid #e5e7eb;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 24px;
}

.loading-card h3 {
  font-size: 20px;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.loading-card p {
  color: #6b7280;
  margin: 0 0 32px 0;
}

.progress-steps {
  display: flex;
  justify-content: space-around;
  gap: 16px;
  margin-top: 32px;
}

.step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  opacity: 0.4;
  transition: opacity 0.3s ease;
}

.step.active {
  opacity: 1;
  transform: scale(1.05);
}

.step.completed .step-icon {
  background: #10b981;
  color: white;
}

.step.active .step-icon {
  background: #667eea;
  color: white;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.step-icon {
  font-size: 24px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f3f4f6;
  transition: all 0.3s ease;
}

.step-text {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
}

/* 空状态 */
.empty-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.empty-card {
  background: white;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  max-width: 600px;
  width: 100%;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 24px;
}

.empty-card h2 {
  font-size: 24px;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.empty-card p {
  color: #6b7280;
  margin: 0 0 32px 0;
}

.suggestions {
  text-align: left;
}

.suggestion-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
}

.suggestion-btn {
  display: block;
  width: 100%;
  padding: 12px 16px;
  margin-bottom: 8px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  color: #374151;
}

.suggestion-btn:hover {
  background: #f3f4f6;
  border-color: #667eea;
  transform: translateX(4px);
}

/* 结果容器 */
.results-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

/* 问题卡片 */
.question-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  border-left: 4px solid #667eea;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.question-icon {
  font-size: 20px;
}

.question-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.question-content {
  font-size: 16px;
  color: #374151;
  line-height: 1.6;
}

/* 回答卡片 */
.answer-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.answer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f3f4f6;
}

.answer-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.answer-header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-btn:hover {
  background: #e5e7eb;
  border-color: #667eea;
  color: #667eea;
  transform: translateY(-1px);
}

.answer-icon {
  font-size: 24px;
}

.answer-header h3 {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.answer-content {
  font-size: 15px;
  color: #374151;
  line-height: 1.8;
}

.answer-content :deep(h1),
.answer-content :deep(h2),
.answer-content :deep(h3) {
  color: #1f2937;
  margin-top: 24px;
  margin-bottom: 12px;
}

.answer-content :deep(p) {
  margin-bottom: 12px;
}

.answer-content :deep(ul),
.answer-content :deep(ol) {
  margin-left: 24px;
  margin-bottom: 12px;
}

.answer-content :deep(li) {
  margin-bottom: 6px;
}

/* 证据映射卡片 */
.evidence-card {
  background: white;
  border-radius: 16px;
  padding: 24px 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 2px solid #f3f4f6;
}

.evidence-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.evidence-icon {
  font-size: 22px;
}

.evidence-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.evidence-count {
  min-width: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}

.evidence-list {
  display: grid;
  gap: 16px;
}

.evidence-item {
  padding: 18px 20px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fafafa;
}

.evidence-item-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #6b7280;
  margin-bottom: 6px;
}

.evidence-item-claim {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 12px;
}

.evidence-item-text {
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
}

.evidence-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  font-size: 12px;
  color: #6b7280;
}

/* 可视化区域 */
.visualizations-section {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f3f4f6;
}

.section-icon {
  font-size: 24px;
}

.section-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  flex: 1;
}

.section-count {
  background: #667eea;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.visualizations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 24px;
}

.visualization-card {
  background: #f9fafb;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e5e7eb;
}

.viz-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.viz-card-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.viz-close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.viz-close-btn:hover {
  background: #fee2e2;
  color: #ef4444;
}

.chart-container {
  width: 100%;
  height: 400px;
  margin-bottom: 16px;
}

.recommendation-box,
.insights-box {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.recommendation-box h5,
.insights-box h5 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.recommendation-box p {
  font-size: 13px;
  color: #6b7280;
  margin: 8px 0;
}

.insight-item {
  margin-bottom: 16px;
}

.insight-item h6 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.insight-item ul {
  margin-left: 20px;
  margin-top: 8px;
}

.insight-item li {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 4px;
}

/* 结构化数据区域 */
.structured-data-section {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.structured-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.data-card {
  background: #f9fafb;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

.data-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.data-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e5e7eb;
}

.data-icon {
  font-size: 20px;
}

.data-card-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.data-card-content {
  font-size: 14px;
  color: #374151;
  line-height: 1.7;
}

.data-card-content :deep(p) {
  margin-bottom: 12px;
}

.data-card-content :deep(ul),
.data-card-content :deep(ol) {
  margin-left: 20px;
  margin-bottom: 12px;
}

/* 业绩指引使用 summary-block 样式对齐财务点评 */

/* 杜邦分析特殊样式 */
.dupont-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dupont-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.metric-item {
  background: white;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  border: 1px solid #e5e7eb;
}

.metric-label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.metric-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: #667eea;
}

.dupont-insights {
  background: white;
  border-radius: 8px;
  padding: 16px;
}

.dupont-insights h4 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.dupont-insights ul {
  margin: 0;
  padding-left: 20px;
}

.dupont-insights li {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}

.dupont-simple p {
  margin: 8px 0;
  font-size: 14px;
  color: #374151;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Toast 提示 */
.agent-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: #667eea;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  z-index: 10000;
  opacity: 0;
  transform: translateX(100%);
  transition: all 0.3s ease;
}

.agent-toast.show {
  opacity: 1;
  transform: translateX(0);
}

.agent-toast-success {
  background: #10b981;
}

.agent-toast-error {
  background: #ef4444;
}

.agent-toast-warning {
  background: #f59e0b;
}

.agent-toast-info {
  background: #667eea;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .visualizations-grid {
    grid-template-columns: 1fr;
  }
  
  .structured-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 16px 20px;
  }
  
  .query-section {
    padding: 16px 20px;
  }
  
  .content-area {
    padding: 20px;
  }
  
  .query-input-wrapper {
    flex-direction: column;
  }
  
  .submit-btn {
    width: 100%;
  }
}
</style>
