<template>
  <Card title="可视化视图" icon="📊" :status="status" empty-text="暂无可视化数据">
    <template #default>
      <div class="visualization-panel-container">
        <!-- 浮动操作栏（当有卡片被选中时显示，包括仅选中杜邦分析） -->
        <div v-if="selectedViewsCount > 0" class="floating-action-bar" :style="{ display: 'block' }">
          <div class="action-bar-content">
            <!-- 第一行：选中卡片信息和生成按钮（右上角） -->
            <div class="action-bar-row-top">
              <div class="selected-cards-info">
                <div class="selected-badge">
                  <span class="selected-icon">✓</span>
                  <span class="selected-count-text">{{ selectedViewsCount }}</span>
                </div>
                <span class="selected-label">个视图已选中</span>
                <button class="clear-selection-btn" @click="clearSelection" title="清除选择">
                  <span class="clear-icon">×</span>
                </button>
              </div>
              
              <button 
                class="generate-btn-primary"
                @click="handleGenerateAnalysis"
                :disabled="generatingAnalysis"
              >
                <span v-if="generatingAnalysis" class="btn-loading">
                  <span class="loading-spinner"></span>
                  <span>生成中...</span>
                </span>
                <span v-else class="btn-content">
                  <span class="btn-icon">✨</span>
                  <span class="btn-text">{{ explorationQuestion.trim() ? '聚焦分析' : '综合分析' }}</span>
                </span>
              </button>
            </div>
            
            <!-- 第二行：探索问题输入区域和推荐问题标签 -->
            <div class="exploration-section">
              <div class="input-wrapper">
                <span class="input-icon">💡</span>
                <input
                  v-model="explorationQuestion"
                  type="text"
                  class="exploration-input"
                  placeholder="输入探索问题（可选，不输入则综合分析）"
                  @keyup.enter="handleGenerateAnalysis"
                />
                <div v-if="explorationQuestion" class="input-clear" @click="explorationQuestion = ''" title="清除">
                  ×
                </div>
              </div>
              
              <!-- 推荐问题标签（紧贴输入框） -->
              <div v-if="recommendedQuestions.length > 0" class="exploration-hints">
                <span class="hints-label">推荐：</span>
                <div class="hints-container">
                  <button
                    v-for="hint in recommendedQuestions" 
                    :key="hint"
                    class="hint-chip"
                    @click="explorationQuestion = hint"
                  >
                    <span class="hint-icon">💭</span>
                    <span class="hint-text">{{ hint }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 卡片列表容器 -->
        <div class="visualization-cards-list" v-if="hasAnyVisualization">
          <!-- 杜邦分析卡片 -->
          <div 
            v-if="dupontData && (dupontData.full_data || dupontData.roe)" 
            class="viz-card dupont-card"
            :class="{ 'selected': isDupontCardSelectedDisplay }"
            @click="handleDupontCardClick($event)"
          >
            <div class="viz-card-header">
              <div class="viz-card-title">
                <!-- 选中标记（直接选择模式） -->
                <span v-if="isDupontCardSelectedDisplay" class="selection-checkbox checked">
                  ✓
                </span>
                <span class="viz-card-icon">📊</span>
                <h3>杜邦分析树状视图</h3>
              </div>
              <div class="viz-card-header-right">
                <div v-if="dupontData.full_data" class="viz-card-meta">
                  <select
                    v-if="dupontYears.length > 1"
                    v-model="selectedDupontYear"
                    class="dupont-year-select"
                    title="切换年份"
                    @click.stop
                  >
                    <option v-for="year in dupontYears" :key="year" :value="year">{{ year }}</option>
                  </select>
                  <span v-else>{{ selectedDupontYear || dupontData.full_data.report_year || '未知年份' }}</span>
                </div>
                <div class="viz-card-actions">
                  <button class="viz-card-close" @click.stop="removeDupontCard" title="删除">×</button>
                </div>
              </div>
            </div>
            <div class="viz-card-content">
              <!-- 树状结构视图 -->
              <div v-if="dupontTreeData" class="dupont-tree-view-enhanced">
                <div class="dupont-diagram-container">
                  <svg class="dupont-connectors" v-if="dupontTreeData"></svg>
                  <DupontTreeNodeEnhanced :node="dupontTreeData" :level="1" />
                </div>
              </div>
              <!-- 层级视图 -->
              <div v-else-if="dupontData.full_data" class="dupont-level-view">
                <div class="level-section">
                  <h4>第一层：ROE分解</h4>
                  <div class="metrics-grid">
                    <div class="metric-card main">
                      <div class="metric-name">ROE (净资产收益率)</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level1', 'roe') }}</div>
                      <div class="metric-formula">{{ getMetricFormula(dupontData.full_data, 'level1', 'roe') }}</div>
                    </div>
                  </div>
                </div>
                <div class="level-section">
                  <h4>第二层：ROA和权益乘数</h4>
                  <div class="metrics-grid">
                    <div class="metric-card">
                      <div class="metric-name">ROA (资产净利率)</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level1', 'roa') }}</div>
                      <div class="metric-formula">{{ getMetricFormula(dupontData.full_data, 'level1', 'roa') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">权益乘数</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level1', 'equity_multiplier') }}</div>
                      <div class="metric-formula">{{ getMetricFormula(dupontData.full_data, 'level1', 'equity_multiplier') }}</div>
                    </div>
                  </div>
                </div>
                <div class="level-section">
                  <h4>第三层：底层指标</h4>
                  <div class="metrics-grid">
                    <div class="metric-card">
                      <div class="metric-name">营业净利润率</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level2', 'net_profit_margin') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">资产周转率</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level2', 'asset_turnover') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">净利润</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level3', 'net_income') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">营业收入</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level3', 'revenue') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">总资产</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level2', 'total_assets') }}</div>
                    </div>
                    <div class="metric-card">
                      <div class="metric-name">股东权益</div>
                      <div class="metric-value">{{ getMetricValue(dupontData.full_data, 'level2', 'shareholders_equity') }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 简单视图 -->
              <div v-else class="dupont-tree">
                <div class="dupont-item main">
                  <div class="dupont-label">ROE</div>
                  <div class="dupont-value">{{ dupontData.roe || '—' }}</div>
                </div>
                <div class="dupont-branches">
                  <div class="dupont-item">
                    <div class="dupont-label">ROA</div>
                    <div class="dupont-value">{{ dupontData.roa || '—' }}</div>
                  </div>
                  <div class="dupont-item">
                    <div class="dupont-label">权益乘数</div>
                    <div class="dupont-value">{{ dupontData.equity_multiplier || '—' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 分隔线（如果有联动生成的卡片） -->
          <div v-if="hasLinkageCards" class="cards-divider">
            <span class="divider-text">✨ 联动生成视图</span>
          </div>
          
          <!-- 普通查询可视化卡片列表（排除杜邦分析类型，因为杜邦分析通过dupontData显示） -->
          <div 
            v-for="card in displayCards" 
            :key="card.id || `card-${card.timestamp?.getTime() || Date.now()}`" 
            class="viz-card chart-card"
            :class="{ 
              'selected': isCardSelected(card.id), 
              'linkage-card': card.isLinkageGenerated,
              'investment-strategy-card': card.source === 'investment_strategy',
              [`linkage-type-${card.viewType}`]: card.isLinkageGenerated
            }"
            @click="handleCardClick(card.id, $event)"
          >
            <div class="viz-card-header">
              <div class="viz-card-title">
                <!-- 选中标记（直接选择模式） -->
                <span v-if="isCardSelected(card.id)" class="selection-checkbox checked">
                  ✓
                </span>
                <!-- 视图类型图标 -->
                <span class="viz-card-icon">{{ getViewTypeIcon(card.viewType) }}</span>
                <h3>{{ formatCardTitle(card.question || '数据可视化') }}</h3>
                <!-- 视图类型标签（联动生成的卡片） -->
                <span v-if="card.isLinkageGenerated && card.viewType" class="view-type-badge" :class="`badge-${card.viewType}`">
                  {{ getViewTypeLabel(card.viewType) }}
                </span>
                <!-- 数据质量标记（联动生成的卡片） -->
                <span v-if="card.isLinkageGenerated && card.dataQuality" class="data-quality-badge" :class="`quality-${card.dataQuality}`">
                  {{ getQualityLabel(card.dataQuality) }}
                </span>
              </div>
              <div class="viz-card-actions">
                <button class="viz-card-close" @click.stop="removeCard(card.id, $event)" title="删除">×</button>
              </div>
            </div>
            <div class="viz-card-content">
              <!-- 探索问题提示（联动生成的卡片） -->
              <div v-if="card.isLinkageGenerated && card.explorationQuestion" class="exploration-context">
                <span class="context-icon">🔍</span>
                <span class="context-label">回答：</span>
                <span class="context-question">{{ card.explorationQuestion }}</span>
              </div>
              
              <div v-if="card.data && card.data.has_visualization" class="chart-card-content">
                <!-- 视图部分 -->
                <div class="view-section">
                <!-- 财务表格 -->
                <div v-if="card.type === 'financial_table' && card.data.table" class="table-container" :class="{ 'table-container--auto': isKeyMetricsTable(card.data.table) }">
                  <table class="financial-table">
                    <thead>
                      <tr>
                        <th v-for="(header, hIdx) in card.data.table.headers" :key="hIdx">
                          {{ header }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rIdx) in card.data.table.rows" :key="rIdx">
                        <td v-for="(cell, cIdx) in row" :key="cIdx">
                          {{ cell }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="card.type === 'financial_table' && card.data.table && (card.data.table.insight_html || card.data.table.insight)" class="table-insight" v-html="card.data.table.insight_html || card.data.table.insight">
                </div>
                <div v-else-if="card.data?.type === 'insight_card'" class="insight-card">
                  <div class="insight-card-title">{{ card.data.title || '经营基调状态卡' }}</div>
                  <div v-if="card.data.headline" class="insight-card-headline">{{ card.data.headline }}</div>
                  <div v-if="card.data.contribution" class="insight-card-row">
                    <span class="insight-label">{{ card.data.meta_type === 'guidance_tone' ? '目标优先级：' : '贡献：' }}</span>
                    {{ card.data.meta_type === 'guidance_tone'
                      ? card.data.contribution.replace('目标优先级：', '')
                      : card.data.contribution }}
                  </div>
                </div>
                <!-- Timeline时间轴（纵向布局，紧凑型） -->
                <div v-else-if="card.data.visualization_type === 'timeline' && card.data.timeline_data" 
                     class="timeline-container">
                  <div class="custom-timeline">
                    <div 
                      v-for="(item, index) in card.data.timeline_data" 
                      :key="index"
                      class="timeline-item"
                      :class="{'timeline-item-left': index % 2 === 0, 'timeline-item-right': index % 2 === 1}">
                      <div class="timeline-dot" :style="{backgroundColor: getTimelineColor(item.color)}"></div>
                      <div class="timeline-content">
                        <div class="timeline-time" v-if="item.time">{{ item.time }}</div>
                        <div class="timeline-text">{{ item.content }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Plotly图表 -->
                <div v-else :id="'chart-' + card.id" class="chart-container-inline"></div>
                </div>
                <!-- 洞察部分（联动生成的卡片） -->
                <div v-if="card.isLinkageGenerated" class="insight-section">
                  <!-- 主要洞察 -->
                  <div v-if="card.insight" class="main-insight">
                    <div class="insight-header">
                      <span class="insight-icon">💡</span>
                      <span class="insight-title">洞察</span>
                      <span v-if="card.insight.confidence" class="confidence-badge" :class="`confidence-${card.insight.confidence}`">
                        {{ getConfidenceLabel(card.insight.confidence) }}
                      </span>
                    </div>
                    <div class="insight-content">
                      <!-- 只显示结论（不显示关键发现） -->
                      <div v-if="card.insight.conclusion" class="insight-conclusion">
                        <span v-html="formatInsightText(card.insight.conclusion)"></span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 图表说明 -->
                  <div v-if="card.data.recommendation" class="recommendation-box">
                    <div class="recommendation-header">
                      <span class="recommendation-icon">📈</span>
                      <span class="recommendation-title">图表说明</span>
                    </div>
                    <div class="recommendation-content">
                      <p><strong>图表类型：</strong>{{ getChartTypeName(getActualChartType(card.data)) }}</p>
                      <p v-if="card.data.recommendation.reason"><strong>推荐理由：</strong>{{ card.data.recommendation.reason }}</p>
                    </div>
                  </div>
                  
                  <!-- 数据洞察 -->
                  <div v-if="card.data.insights && card.data.insights.length > 0" class="data-insights">
                    <div class="data-insights-header">
                      <span class="data-insights-icon">📊</span>
                      <span class="data-insights-title">数据洞察</span>
                    </div>
                    <div class="data-insights-content">
                      <div 
                        v-for="(insight, index) in card.data.insights" 
                        :key="index" 
                        class="data-insight-item"
                      >
                        <span class="insight-type-icon">{{ getInsightIcon(insight.insight_type) }}</span>
                        <div class="insight-text" v-html="formatInsightText(insight.description)"></div>
                        <ul v-if="insight.key_findings && insight.key_findings.length > 0" class="insight-findings-list">
                          <li v-for="(finding, idx) in insight.key_findings" :key="idx" v-html="formatInsightText(finding)"></li>
                        </ul>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 关联信息（可展开） -->
                  <div v-if="card.relatedCards && card.relatedCards.length > 0" class="related-cards-info">
                    <button class="toggle-related-btn" @click="card.showRelated = !card.showRelated">
                      {{ card.showRelated ? '隐藏' : '显示' }}关联视图
                    </button>
                    <div v-if="card.showRelated" class="related-cards-list">
                      <span 
                        v-for="relatedId in card.relatedCards" 
                        :key="relatedId"
                        class="related-card-tag"
                      >
                        {{ getCardTitle(relatedId) }}
                      </span>
                    </div>
                  </div>
                </div>
                
                <!-- 原有洞察展示（非联动生成的卡片） -->
                <div v-else>
                  <!-- 综合能力分析文本 -->
                  <div v-if="card.data.analysis_text" class="analysis-text-box">
                    <div v-html="formatAnalysisText(card.data.analysis_text)"></div>
                  </div>
                  
                  <!-- 推荐说明 -->
                  <div v-if="card.data.recommendation && card.type !== 'financial_table'" class="recommendation-box">
                    <h4>📈 图表推荐</h4>
                    <p><strong>推荐图表类型:</strong> 
                      <span>{{ getChartTypeName(getActualChartType(card.data)) }}</span>
                    </p>
                    <p><strong>推荐理由:</strong> {{ card.data.recommendation.reason }}</p>
                  </div>
                  
                  <!-- 数据洞察 -->
                  <div v-if="card.data.insights && card.data.insights.length > 0 && card.type !== 'financial_table'" class="insights-box">
                    <h3>💡 数据洞察</h3>
                    <div 
                      v-for="(insight, index) in card.data.insights" 
                      :key="index" 
                      class="insight-item"
                    >
                      <h4>
                        <span class="insight-icon">{{ getInsightIcon(insight.insight_type) }}</span>
                        <span v-html="formatInsightText(insight.description)"></span>
                      </h4>
                      <ul v-if="insight.key_findings && insight.key_findings.length > 0">
                        <li v-for="(finding, idx) in insight.key_findings" :key="idx" v-html="formatInsightText(finding)"></li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else-if="card.data && card.data.error" class="error-message">
                <p>⚠️ 可视化生成失败: {{ card.data.error }}</p>
              </div>
            </div>
          </div>
          
          <!-- 当前查询的图表（向后兼容） -->
          <div v-if="chartData && chartData.has_visualization && !isCardInList(chartData)" class="viz-card chart-card">
            <div class="viz-card-header">
              <div class="viz-card-title">
                <span class="viz-card-icon">📊</span>
                <h3>数据可视化</h3>
              </div>
            </div>
            <div class="viz-card-content">
              <div id="visualizationChart" class="chart-container-inline"></div>
              
              <div v-if="hasRecommendation" class="recommendation-box">
                <h4>📈 图表推荐</h4>
                <p><strong>推荐图表类型:</strong> {{ getChartTypeName(chartData.recommendation.recommended_chart_type) }}</p>
                <p><strong>推荐理由:</strong> {{ chartData.recommendation.reason }}</p>
              </div>
              
              <div v-if="hasInsights" class="insights-box">
                <h3>💡 数据洞察</h3>
                <div 
                  v-for="(insight, index) in chartData.insights" 
                  :key="index" 
                  class="insight-item"
                >
                  <h4>
                    <span class="insight-icon">{{ getInsightIcon(insight.insight_type) }}</span>
                    <span v-html="formatInsightText(insight.description)"></span>
                  </h4>
                  <ul v-if="insight.key_findings && insight.key_findings.length > 0">
                    <li v-for="(finding, idx) in insight.key_findings" :key="idx" v-html="formatInsightText(finding)"></li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 空状态 -->
        <div v-else class="no-viz-message">
          <p>ℹ️ 暂无可视化数据。生成杜邦分析或进行包含数据的查询后，图表将在此显示。</p>
        </div>
      </div>
    </template>
  </Card>
</template>

<script>
import Card from './Card.vue'

// 递归树节点组件
const DupontTreeNode = {
  name: 'DupontTreeNode',
  props: {
    node: { type: Object, required: true },
    level: { type: Number, default: 1 }
  },
  template: `
    <div class="tree-node" :class="'level-' + level">
      <div class="node-content" :class="'level-' + level">
        <div class="node-name">{{ node.name }}</div>
        <div class="node-value">{{ node.formatted_value || node.value || '—' }}</div>
        <div v-if="node.formula" class="node-formula">{{ node.formula }}</div>
      </div>
      <div v-if="node.children && node.children.length > 0" class="node-children">
        <component 
          v-for="(child, index) in node.children" 
          :key="child.id || index"
          :is="'DupontTreeNode'"
          :node="child" 
          :level="level + 1"
        />
      </div>
    </div>
  `
}

DupontTreeNode.components = { DupontTreeNode }

const DupontTreeNodeEnhanced = {
  name: 'DupontTreeNodeEnhanced',
  props: {
    node: { type: Object, required: true },
    level: { type: Number, default: 1 },
    index: { type: Number, default: 0 },
    total: { type: Number, default: 1 }
  },
  template: `
    <div class="dupont-node-wrapper" :class="'level-' + level" :data-level="level" :data-index="index">
      <div class="dupont-node" :class="'level-' + level">
        <div class="dupont-node-header">
          <div class="dupont-node-name">{{ node.name }}</div>
        </div>
        <div class="dupont-node-value">{{ node.formatted_value || node.value || '—' }}</div>
        <div v-if="node.formula" class="dupont-node-formula">{{ node.formula }}</div>
      </div>
      <div v-if="node.children && node.children.length > 0" class="dupont-children-container">
        <div class="dupont-children-row">
          <component
            v-for="(child, idx) in node.children"
            :key="child.id || idx"
            :is="'DupontTreeNodeEnhanced'"
            :node="child"
            :level="level + 1"
            :index="idx"
            :total="node.children.length"
          />
        </div>
      </div>
    </div>
  `,
  components: {}
}

DupontTreeNodeEnhanced.components = { DupontTreeNodeEnhanced }

export default {
  name: 'VisualizationPanel',
  components: {
    Card,
    DupontTreeNode,
    DupontTreeNodeEnhanced
  },
  props: { 
    chartData: { type: Object, default: null }, 
    dupontData: { type: Object, default: null },
    visualizationCards: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false } 
  },
  emits: ['remove-card', 'remove-dupont-card', 'generate-comprehensive-analysis'],
  data() {
    return {
      selectedCards: [],
      selectedDupontCard: false,  // 杜邦分析卡片是否被选中
      dupontCardSelectionUnlocked: false,  // 仅当用户点击过该卡片后才允许显示选中样式，避免一生成就选中
      generatingAnalysis: false,
      selectedDupontYear: null,
      explorationQuestion: '',  // 探索问题
      recommendedQuestions: []  // 推荐问题（基于选中卡片）
    }
  },
  computed: {
    // 是否有联动生成的卡片
    hasLinkageCards() {
      return this.visualizationCards.some(card => card.isLinkageGenerated)
    },
    // 选中的视图数量（普通卡片 + 杜邦卡片若被选中则 +1）
    selectedViewsCount() {
      const cardCount = this.selectedCards.length
      const dupontCount = this.selectedDupontCard ? 1 : 0
      return cardCount + dupontCount
    },
    // 杜邦卡片是否显示为选中（用 computed 保证蓝色边框/勾选随点击响应更新）
    isDupontCardSelectedDisplay() {
      return this.selectedDupontCard && this.dupontCardSelectionUnlocked
    },
    status() {
      if (this.loading) return 'loading';
      if (this.hasAnyVisualization) return 'content';
      return 'empty';
    },
    hasAnyVisualization() {
      const hasChartData = this.chartData && this.chartData.has_visualization;
      const hasDupontData = this.dupontData && (this.dupontData.full_data || this.dupontData.roe);
      const hasDisplayCards = this.displayCards && this.displayCards.length > 0;
      
      // 添加调试日志
      console.log('🔍 hasAnyVisualization 检查:', {
        hasChartData,
        hasDupontData,
        hasDisplayCards,
        displayCardsCount: this.displayCards?.length || 0,
        visualizationCardsCount: this.visualizationCards?.length || 0,
        dupontData: !!this.dupontData
      });
      
      return hasChartData || hasDupontData || hasDisplayCards;
    },
    displayCards() {
      if (!Array.isArray(this.visualizationCards)) {
        console.warn('⚠️ visualizationCards 不是数组:', this.visualizationCards);
        return [];
      }
      
      console.log(`📊 displayCards 开始过滤: 原始卡片数量 ${this.visualizationCards.length}`);
      
      const filtered = this.visualizationCards.filter(card => {
        // 基本检查
        if (!card) {
          console.warn('⚠️ 发现空卡片，将被过滤');
          return false;
        }
        
        // 排除杜邦分析类型（杜邦分析通过dupontData显示）
        if (card.type === 'dupont') {
          console.log(`ℹ️ 卡片 ${card.id} 是杜邦分析类型，将被过滤`);
          return false;
        }
        
        // 检查卡片是否有可视化数据
        if (!card.data) {
          console.warn(`⚠️ 卡片 ${card.id} 没有 data 字段，将被过滤:`, {
            id: card.id,
            question: card.question,
            type: card.type
          });
          return false;
        }
        
        if (!card.data.has_visualization) {
          console.warn(`⚠️ 卡片 ${card.id} 没有可视化数据（has_visualization=false），将被过滤:`, {
            id: card.id,
            question: card.question,
            type: card.type,
            data: card.data
          });
          return false;
        }
        
        // 对于财务表格类型，检查是否被隐藏
        if (card.type === 'financial_table') {
          const title = card.data?.table?.title || card.question || '';
          const isHidden = this.isHiddenBusinessMetricTable(title);
          if (isHidden) {
            console.log(`ℹ️ 财务表格 "${title}" 被标记为隐藏，将被过滤`);
            return false;
          }
        }
        
        // 其他类型的卡片都显示
        console.log(`✅ 卡片 ${card.id} 通过过滤:`, {
          id: card.id,
          question: card.question,
          type: card.type,
          hasVisualization: card.data.has_visualization
        });
        return true;
      });
      
      console.log(`📊 displayCards 过滤完成: 原始 ${this.visualizationCards.length} 个，过滤后 ${filtered.length} 个`);
      if (filtered.length < this.visualizationCards.length) {
        const filteredIds = filtered.map(c => c.id);
        const allIds = this.visualizationCards.map(c => c.id);
        const removedIds = allIds.filter(id => !filteredIds.includes(id));
        console.log(`📋 被过滤的卡片ID:`, removedIds);
      }
      
      // ⭐按时间戳排序：新生成的放在最上面（降序）
      const sorted = filtered.sort((a, b) => {
        const timeA = a.timestamp instanceof Date ? a.timestamp.getTime() : (a.timestamp ? new Date(a.timestamp).getTime() : 0);
        const timeB = b.timestamp instanceof Date ? b.timestamp.getTime() : (b.timestamp ? new Date(b.timestamp).getTime() : 0);
        return timeB - timeA; // 降序：最新的在前
      });
      
      console.log(`📊 displayCards 排序完成: 按时间戳降序排列，最新视图在最上面`);
      
      return sorted;
    },
    hasInsights() {
      return this.chartData?.insights && this.chartData.insights.length > 0;
    },
    hasRecommendation() {
      return this.chartData?.recommendation != null;
    },
    confidenceScore() {
      return this.chartData?.confidence_score || 0;
    },
    dupontYears() {
      const metrics = this.dupontData?.metrics_json?.metrics || [];
      const years = [...new Set(metrics.map(m => m.year).filter(Boolean))];
      return years.sort((a, b) => b - a);
    },
    dupontTreeData() {
      if (!this.dupontData) return null;
      const metrics = this.dupontData.metrics_json?.metrics || [];
      if (metrics.length === 0) {
        return this.dupontData.full_data?.tree_structure || null;
      }
      const year = this.selectedDupontYear || this.dupontData.full_data?.report_year || this.dupontYears[0];
      return this.buildDupontTreeFromMetrics(metrics, year);
    }
  },
  methods: {
    formatCardTitle(title) {
      return String(title || '')
        .replace(/[`*_]+/g, '')
        .replace(/^#{1,6}\s*/g, '')
        .replace(/^[一二三四五六七八九十]+[、.]\s*/g, '')
        .replace(/^\d+\.\s*/g, '')
        .replace(/[|]/g, '')
        .replace(/\s{2,}/g, ' ')
        .trim();
    },
    isKeyMetricsTable(table) {
      const title = table?.title || ''
      return String(title).includes('关键业务指标')
    },
    isHiddenBusinessMetricTable(title = '') {
      const hiddenTitles = ['零售银行业务指标', '对公银行业务指标', '同业与资金业务指标'];
      const text = String(title || '');
      return hiddenTitles.some(item => text.includes(item));
    },
    buildDupontTreeFromMetrics(metrics, year) {
      const getMetric = (metricKey) => {
        return metrics.find(m => m.metric === metricKey && m.year === year) || null;
      };
      const formatPercent = (metric) => {
        if (!metric || metric.value === null || metric.value === undefined) return '—';
        const num = Number(metric.value);
        if (!Number.isFinite(num)) return '—';
        return `${num.toFixed(2)}%`;
      };
      const formatTimes = (metric) => {
        if (!metric || metric.value === null || metric.value === undefined) return '—';
        const num = Number(metric.value);
        if (!Number.isFinite(num)) return '—';
        return num.toFixed(2);
      };
      const formatAmount = (metric) => {
        if (!metric || metric.value === null || metric.value === undefined) return '—';
        const num = Number(metric.value);
        if (!Number.isFinite(num)) return '—';
        const display = Number.isInteger(num) ? String(num) : num.toFixed(2);
        return `${display}${metric.unit || ''}`;
      };

      const roe = getMetric('ROE');
      const roa = getMetric('ROA');
      const netProfit = getMetric('NetProfit');
      const revenue = getMetric('Revenue');
      const totalAssets = getMetric('TotalAssets');
      const equity = getMetric('Equity');
      const netProfitMargin = getMetric('NetProfitMargin');
      const assetTurnover = getMetric('AssetTurnover');
      const equityMultiplier = getMetric('EquityMultiplier');

      return {
        id: 'roe',
        name: '净资产收益率',
        formatted_value: formatPercent(roe),
        value: roe?.value ?? null,
        level: 1,
        children: [
          {
            id: 'roa',
            name: '资产净利率',
            formatted_value: formatPercent(roa),
            value: roa?.value ?? null,
            level: 1,
            children: [
              {
                id: 'net_profit_margin',
                name: '营业净利润率',
                formatted_value: formatPercent(netProfitMargin),
                value: netProfitMargin?.value ?? null,
                level: 2,
                children: [
                  {
                    id: 'net_income',
                    name: '净利润',
                    formatted_value: formatAmount(netProfit),
                    value: netProfit?.value ?? null,
                    level: 3,
                    children: []
                  },
                  {
                    id: 'revenue',
                    name: '营业收入',
                    formatted_value: formatAmount(revenue),
                    value: revenue?.value ?? null,
                    level: 3,
                    children: []
                  }
                ]
              },
              {
                id: 'asset_turnover',
                name: '资产周转率',
                formatted_value: formatTimes(assetTurnover),
                value: assetTurnover?.value ?? null,
                level: 2,
                children: []
              }
            ]
          },
          {
            id: 'equity_multiplier',
            name: '权益乘数',
            formatted_value: formatTimes(equityMultiplier),
            value: equityMultiplier?.value ?? null,
            level: 1,
            children: [
              {
                id: 'total_assets',
                name: '总资产',
                formatted_value: formatAmount(totalAssets),
                value: totalAssets?.value ?? null,
                level: 2,
                children: []
              },
              {
                id: 'shareholders_equity',
                name: '股东权益',
                formatted_value: formatAmount(equity),
                value: equity?.value ?? null,
                level: 2,
                children: []
              }
            ]
          }
        ],
        formula: 'ROE = ROA × 权益乘数'
      };
    },
    removeCard(cardId, event) {
      // 阻止事件冒泡，确保不会触发卡片选择
      if (event) {
        event.stopPropagation();
        event.preventDefault();
      }
      
      console.log('🗑️ 删除卡片:', cardId);
      
      // 如果卡片在选中列表中，先移除
      const index = this.selectedCards.indexOf(cardId);
      if (index > -1) {
        this.selectedCards.splice(index, 1);
        console.log('  从选中列表中移除');
      }
      
      // 清理Plotly图表实例（如果存在）
      if (window.Plotly) {
        try {
          const chartElement = document.getElementById(`chart-${cardId}`);
          if (chartElement) {
            window.Plotly.purge(chartElement);
            console.log('  清理图表实例成功');
          }
        } catch (error) {
          console.warn('清理图表失败:', error);
        }
      }
      
      // 触发删除事件，删除整个卡片
      console.log('  触发删除事件，删除整个视图卡片');
      this.$emit('remove-card', cardId);
    },
    removeDupontCard() {
      // 删除杜邦分析卡片：从cards中删除，并清空dupontData
      this.$emit('remove-dupont-card');
    },
    /** 重新渲染所有图表卡片（用于杜邦卡片出现导致 DOM 重排后，之前视图的图表容器被重建的情况） */
    rerenderAllChartCards() {
      const cards = this.displayCards || [];
      if (cards.length === 0) return;
      setTimeout(() => {
        cards.forEach(card => {
          if (!card.data || !card.data.has_visualization || card.type !== 'chart') return;
          const vizType = card.data.visualization_type || 'plotly';
          if (vizType === 'plotly' && card.data.chart_config) {
            this.renderChart(card.id, card.data);
          }
        });
      }, 250);
    },
    isCardInList(chartData) {
      // 检查当前chartData是否已经在cards列表中
      if (!chartData || !chartData.has_visualization) {
        return false;
      }
      
      return this.visualizationCards.some(card => {
        if (!card.data || !card.data.has_visualization) {
          return false;
        }
        
        // 对于Plotly类型，比较chart_config
        if (chartData.chart_config && card.data.chart_config) {
          try {
            return JSON.stringify(card.data.chart_config) === JSON.stringify(chartData.chart_config);
          } catch (e) {
            // 如果JSON比较失败，使用更简单的比较
            return card.data.chart_config.chart_type === chartData.chart_config.chart_type;
          }
        }
        
        // 如果都没有配置，比较其他唯一标识符（如query）
        // 这里可以根据实际需求调整
        return false;
      });
    },
    getMetricValue(data, level, metric) {
      if (!data || !data[level] || !data[level][metric]) return '—'
      const metricObj = data[level][metric]
      return metricObj.formatted_value || metricObj.value || '—'
    },
    getMetricFormula(data, level, metric) {
      if (!data || !data[level] || !data[level][metric]) return ''
      const metricObj = data[level][metric]
      return metricObj.formula || ''
    },
    renderChart(cardId, chartData) {
      if (chartData?.type === 'financial_table') {
        return;
      }
      // 如果是Timeline类型，不需要渲染（由Vue模板直接渲染）
      if (chartData?.visualization_type === 'timeline' && chartData?.timeline_data) {
        console.log(`🎨 Timeline类型，由Vue模板直接渲染: ${cardId}`);
        return;
      }
      
      // Plotly图表渲染
      if (!chartData?.chart_config || !window.Plotly) {
        if (!window.Plotly) {
          console.warn('Plotly未加载，无法渲染图表');
        }
        if (!chartData?.chart_config) {
          console.warn(`⚠️ 缺少chart_config，跳过Plotly渲染: ${cardId}`);
        }
        return;
      }
      this.$nextTick(() => {
        try {
          const chartConfig = chartData.chart_config;
          const chartElementId = cardId ? `chart-${cardId}` : 'visualizationChart';
          
          // 检查DOM元素是否存在
          const chartElement = document.getElementById(chartElementId);
          if (!chartElement) {
            console.warn(`图表容器不存在: ${chartElementId}，延迟重试...`);
            // 如果元素不存在，延迟重试
            setTimeout(() => {
              this.renderChart(cardId, chartData);
            }, 200);
            return;
          }
          
          // 处理雷达图
          if (chartConfig.chart_type === 'radar' || (chartConfig.traces && chartConfig.traces[0]?.type === 'scatterpolar')) {
            this.renderRadarChart(chartElementId, chartConfig);
            return;
          }
          
          // 处理桑基图（Sankey Diagram）
          if (chartConfig.config && chartConfig.config.sankey_data) {
            this.renderSankeyChart(chartElementId, chartConfig);
            return;
          }
          
          const traces = chartConfig.traces.map(trace => {
            const plotlyTrace = { 
              type: trace.type || 'scatter', 
              name: trace.name || '数据' 
            };
            if (trace.type === 'pie') {
              plotlyTrace.labels = trace.text || [];
              plotlyTrace.values = trace.y || [];
            } else if (trace.type === 'heatmap') {
              plotlyTrace.z = trace.z || [];
              plotlyTrace.x = trace.x || [];
              plotlyTrace.y = trace.y || [];
              if (trace.colorscale) plotlyTrace.colorscale = trace.colorscale;
              if (trace.zmin != null) plotlyTrace.zmin = trace.zmin;
              if (trace.zmax != null) plotlyTrace.zmax = trace.zmax;
            } else {
              plotlyTrace.x = trace.x || [];
              plotlyTrace.y = trace.y || [];
            }
            if (trace.mode) plotlyTrace.mode = trace.mode;
            if (trace.marker) plotlyTrace.marker = trace.marker;
            if (trace.line) plotlyTrace.line = trace.line;
            if (trace.type !== 'pie' && trace.text) plotlyTrace.text = trace.text;
            if (trace.textposition) plotlyTrace.textposition = trace.textposition;
            if (trace.hovertemplate) plotlyTrace.hovertemplate = trace.hovertemplate;
            return plotlyTrace;
          });
          const layout = {
            title: { 
              text: chartConfig.layout.title || '', 
              font: { size: 14, color: '#333' } 
            },
            xaxis: { 
              title: chartConfig.layout.xaxis_title || '', 
              gridcolor: '#e0e0e0' 
            },
            yaxis: { 
              title: chartConfig.layout.yaxis_title || '', 
              gridcolor: '#e0e0e0' 
            },
            height: chartConfig.layout.height || 320,
            template: chartConfig.layout.template || 'plotly_white',
            hovermode: chartConfig.layout.hovermode || 'closest',
            showlegend: chartConfig.layout.showlegend !== false,
            legend: chartConfig.layout.showlegend !== false ? {
              orientation: 'h',
              y: -0.42,
              yanchor: 'top',
              x: 0.5,
              xanchor: 'center',
              font: { size: 10 },
              itemwidth: 18,
              traceorder: 'normal'
            } : undefined,
            margin: { t: 40, r: 20, b: 118, l: 50 },  // 底部大边距：先横轴再图例，彻底避免遮挡
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            autosize: true
          };
          const config = { 
            responsive: true, 
            displayModeBar: true, 
            displaylogo: false, 
            modeBarButtonsToRemove: ['lasso2d', 'select2d'] 
          };
          if (window.Plotly && window.Plotly.newPlot) {
            // 如果图表已存在，先清理
            try {
              const existingChart = document.getElementById(chartElementId);
              if (existingChart && existingChart.data) {
                window.Plotly.purge(chartElementId);
              }
            } catch (e) {
              // 忽略清理错误
            }
            
            window.Plotly.newPlot(chartElementId, traces, layout, config);
            console.log(`✅ 图表渲染成功: ${chartElementId}`);
          } else {
            console.warn('Plotly未加载，无法渲染图表');
          }
        } catch (error) {
          console.error('渲染图表失败:', error);
          const chartDiv = document.getElementById(cardId ? `chart-${cardId}` : 'visualizationChart');
          if (chartDiv) {
            const errorMsg = error.message || '未知错误';
            chartDiv.innerHTML = '<div class="error-message"><p>图表渲染失败: ' + errorMsg + '</p></div>';
          }
        }
      });
    },
    renderSankeyChart(chartElementId, chartConfig) {
      try {
        const sankeyData = chartConfig.config.sankey_data;
        const nodes = sankeyData.nodes || {};
        const links = sankeyData.links || {};
        
        // 创建Plotly Sankey trace（优化节点大小以适配视图卡片）
        const trace = {
          type: 'sankey',
          node: {
            pad: 10,  // 进一步减小节点间距（原15改为10）
            thickness: 18,  // 进一步减小节点厚度（原20改为18）
            line: { color: 'black', width: 0.5 },
            label: nodes.label || [],
            color: nodes.color || [],
            labelpadding: 3,  // 进一步减小标签内边距
            labelsuffix: ''  // 移除标签后缀
          },
          link: {
            source: links.source || [],
            target: links.target || [],
            value: links.value || [],
            color: 'rgba(0,0,0,0.15)'
          }
        };
        
        const layout = {
          title: {
            text: chartConfig.layout.title || '桑基图',
            font: { size: 13, color: '#333' }
          },
          height: 300,
          font: { size: 10 },
          margin: { t: 45, r: 15, b: 15, l: 15 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          autosize: true  // 自动调整大小
        };
        
        const config = {
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['lasso2d', 'select2d']
        };
        
        if (window.Plotly && window.Plotly.newPlot) {
          try {
            const existingChart = document.getElementById(chartElementId);
            if (existingChart && existingChart.data) {
              window.Plotly.purge(chartElementId);
            }
          } catch (e) {
            // 忽略清理错误
          }
          
          window.Plotly.newPlot(chartElementId, [trace], layout, config);
          console.log(`✅ 桑基图渲染成功: ${chartElementId}`);
        } else {
          console.warn('Plotly未加载，无法渲染桑基图');
        }
      } catch (error) {
        console.error('渲染桑基图失败:', error);
        const chartDiv = document.getElementById(chartElementId);
        if (chartDiv) {
          const errorMsg = error.message || '未知错误';
          chartDiv.innerHTML = '<div class="error-message"><p>桑基图渲染失败: ' + errorMsg + '</p></div>';
        }
      }
    },
    renderRadarChart(chartElementId, chartConfig) {
      try {
        const trace = chartConfig.traces[0];
        const layout = chartConfig.layout || {};
        
        // 构建Plotly雷达图数据
        const plotlyTrace = {
          type: 'scatterpolar',
          r: trace.r || [],
          theta: trace.theta || [],
          fill: trace.fill || 'toself',
          mode: trace.mode || 'lines+markers',
          name: trace.name || '综合能力',
          line: trace.line || { color: 'rgb(55, 128, 191)', width: 2 },
          marker: trace.marker || { size: 6, color: 'rgb(55, 128, 191)' }
        };
        
        // 构建布局（优化大小和位置，适配卡片）
        const plotlyLayout = {
          polar: layout.polar || {
            radialaxis: {
              visible: true,
              range: [0, 100],
              tickmode: 'linear',
              tick0: 0,
              dtick: 20,
              tickfont: { size: 10 },
              gridcolor: '#e0e0e0',
              linecolor: '#999'
            },
            angularaxis: {
              rotation: 90,
              direction: 'counterclockwise',
              tickfont: { size: 11 }
            }
          },
          title: {
            text: layout.title || '综合能力分析雷达图',
            font: { size: 14, color: '#333' },
            x: 0.5,
            xanchor: 'center'
          },
          height: 360,
          margin: { t: 50, r: 50, b: 118, l: 50 },  // 底部大边距：横轴 + 图例，彻底避免遮挡
          showlegend: layout.showlegend !== false,
          legend: layout.showlegend !== false ? {
            orientation: 'h',
            y: -0.35,
            yanchor: 'top',
            x: 0.5,
            xanchor: 'center',
            font: { size: 10 },
            itemwidth: 18
          } : undefined,
          template: layout.template || 'plotly_white',
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)'
        };
        
        const config = {
          responsive: true,
          displayModeBar: false,  // 隐藏工具栏，节省空间
          displaylogo: false
        };
        
        // 清理旧图表
        try {
          const existingChart = document.getElementById(chartElementId);
          if (existingChart && existingChart.data) {
            window.Plotly.purge(chartElementId);
          }
        } catch (e) {
          // 忽略清理错误
        }
        
        window.Plotly.newPlot(chartElementId, [plotlyTrace], plotlyLayout, config);
        console.log(`✅ 雷达图渲染成功: ${chartElementId}`);
      } catch (error) {
        console.error('渲染雷达图失败:', error);
        const chartDiv = document.getElementById(chartElementId);
        if (chartDiv) {
          chartDiv.innerHTML = '<div class="error-message"><p>雷达图渲染失败: ' + error.message + '</p></div>';
        }
      }
    },
    getTimelineColor(color) {
      const colorMap = {
        'blue': '#1890ff',
        'green': '#52c41a',
        'red': '#ff4d4f',
        'gray': '#8c8c8c',
        'orange': '#fa8c16',
        'purple': '#722ed1'
      };
      return colorMap[color] || colorMap['blue'];
    },
    getInsightIcon(type) {
      const icons = {
        'trend': '📈',
        'comparison': '⚖️',
        'distribution': '📊',
        'correlation': '🔗',
        'anomaly': '⚠️'
      };
      return icons[type] || '💡';
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
        'box': '箱线图',
        'waterfall': '瀑布图',
        'funnel': '漏斗图',
        'gauge': '仪表盘',
        'table': '表格',
        'radar': '雷达图',
        'timeline': '时间轴',
        'sankey': '桑基图'
      };
      return names[type] || type;
    },
    // 获取实际图表类型（考虑特殊图表类型）
    getActualChartType(cardData) {
      // 检查是否是桑基图
      if (cardData?.chart_config?.config?.sankey_data) {
        return 'sankey';
      }
      // 检查是否是时间轴
      if (cardData?.visualization_type === 'timeline' || cardData?.timeline_data) {
        return 'timeline';
      }
      // 检查是否是雷达图
      if (cardData?.chart_config?.chart_type === 'radar' || 
          (cardData?.chart_config?.traces && cardData.chart_config.traces[0]?.type === 'scatterpolar')) {
        return 'radar';
      }
      // 返回推荐的图表类型
      return cardData?.recommendation?.recommended_chart_type || 'bar';
    },
    highlightInsightText(text = '') {
      let result = String(text)
      const metricKeywords = [
        '资产总额', '负债总额', '发放贷款及垫款', '个人贷款', '企业贷款',
        '投资类金融资产', '现金及存放央行款项', '存放同业款项',
        '吸收存款', '个人存款', '企业存款', '向央行借款',
        '同业负债', '已发行债务证券', '卖出回购金融资产',
        '营业收入合计', '利息净收入', '非利息净收入', '手续费及佣金净收入',
        '其他非利息净收入', '投资收益', '公允价值变动损益',
        '营业支出合计', '业务及管理费', '信用及其他资产减值损失', '税金及附加',
        '经营活动现金流', '投资活动现金流', '筹资活动现金流', '现金净变动额',
        '净利润', '归母净利润', '资产负债率', 'ROE', 'ROA',
        '营业收入', '营业利润', '利润总额', '毛利率', '净利率',
        '总资产', '总负债', '股东权益', '流动资产', '流动负债',
        '资产周转率', '权益乘数', '净资产收益率', '资产净利率',
        '成本收入比', '净息差', '不良贷款率', '拨备覆盖率',
        'EPS', '每股收益', '每股净资产', '分红率'
      ]
      // 先替换更长短语，避免「利息净收入」抢先匹配掉「非利息净收入」里的后半段
      const sortedKeywords = [...metricKeywords].sort((a, b) => b.length - a.length)
      sortedKeywords.forEach((keyword) => {
        result = result.replaceAll(keyword, `<span class="insight-key">${keyword}</span>`)
      })
      result = result.replace(/(-?\d{4,}(?:\.\d+)?%?|-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|-?\d{1,3}(?:\.\d+)?%?)(万亿元|亿元|万元|元)?/g, (match) => {
        return `<span class="insight-num">${match}</span>`
      })
      result = result.replace(/(增长|上升|提升|扩大|改善|增加|上行|回升)/g, '<span class="insight-up">$1</span>')
      result = result.replace(/(下降|下滑|收缩|减少|下行|走弱|压降|回落)/g, '<span class="insight-down">$1</span>')
      return result
    },
    formatInsightText(text = '') {
      if (!text) return ''
      return this.highlightInsightText(text).replace(/\n/g, '<br>')
    },
    formatAnalysisText(text) {
      if (!text) return '';
      // 将Markdown格式转换为HTML
      if (typeof marked !== 'undefined' && marked && marked.parse) {
        return marked.parse(text);
      }
      // 简单的文本格式化
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    },
    handleCardClick(cardId, event) {
      // 如果点击的是删除按钮，不处理选择逻辑
      if (event && event.target && (event.target.classList.contains('viz-card-close') || event.target.closest('.viz-card-close'))) {
        return
      }
      
      // 直接选择模式：点击卡片即可选择/取消选择
      const index = this.selectedCards.indexOf(cardId)
      if (index > -1) {
        this.selectedCards.splice(index, 1)
      } else {
        this.selectedCards.push(cardId)
      }
      
      // 更新推荐问题
      this.updateRecommendedQuestions()
    },
    // ⭐新增：处理杜邦分析卡片点击
    handleDupontCardClick(event) {
      // 如果点击的是删除按钮或年份选择器，不处理选择逻辑
      if (event && event.target && (
        event.target.classList.contains('viz-card-close') || 
        event.target.closest('.viz-card-close') ||
        event.target.classList.contains('dupont-year-select') ||
        event.target.closest('.dupont-year-select')
      )) {
        return
      }
      // 用户点击后才允许显示选中/未选中状态（可正常切换）
      this.dupontCardSelectionUnlocked = true
      this.selectedDupontCard = !this.selectedDupontCard
      this.updateRecommendedQuestions()
    },
    clearSelection() {
      this.selectedCards = []
      this.selectedDupontCard = false  // ⭐新增：清除杜邦分析卡片选择
      this.explorationQuestion = ''
      this.recommendedQuestions = []
    },
    updateRecommendedQuestions() {
      // 根据选中的卡片生成推荐问题（包括杜邦分析卡片）
      const selected = this.visualizationCards.filter(card => 
        this.selectedCards.includes(card.id)
      )
      
      // ⭐新增：如果杜邦分析卡片被选中，也加入推荐问题生成
      const hasDupontSelected = this.selectedDupontCard
      
      if (selected.length === 0 && !hasDupontSelected) {
        this.recommendedQuestions = []
        return
      }
      
      const questions = []
      
      // 单卡片推荐
      if (selected.length === 1) {
        const card = selected[0]
        const title = card.question || ''
        
        if (title.includes('营收') || title.includes('收入')) {
          questions.push('营收增长的主要原因是什么？')
          questions.push('营收趋势未来如何？')
        }
        if (title.includes('利润') || title.includes('ROE')) {
          questions.push('利润变化的主要原因是什么？')
          questions.push('ROE下降的原因是什么？')
        }
        if (title.includes('资产') || title.includes('负债')) {
          questions.push('资产结构如何？')
          questions.push('负债率是否合理？')
        }
      }
      
      // 多卡片推荐
      if (selected.length > 1) {
        questions.push('这些指标之间有什么关联？')
        questions.push('这些视图反映了什么趋势？')
        questions.push('哪些因素影响了这些指标？')
      }
      
      this.recommendedQuestions = questions.slice(0, 3)
    },
    handleGenerateAnalysis() {
      // ⭐修改：检查是否有选中的卡片（包括杜邦分析卡片）
      if (this.selectedCards.length === 0 && !this.selectedDupontCard) {
        return
      }
      
      this.generatingAnalysis = true
      try {
        // 获取选中的卡片数据
        const selectedCardsData = this.visualizationCards.filter(card => 
          this.selectedCards.includes(card.id)
        )
        
        // ⭐新增：如果杜邦分析卡片被选中，添加杜邦分析数据
        if (this.selectedDupontCard && this.dupontData) {
          selectedCardsData.push({
            id: 'dupont-analysis-card',
            question: '杜邦分析',
            timestamp: new Date(),
            data: {
              has_visualization: true,
              type: 'dupont',
              dupont_data: this.dupontData
            },
            type: 'dupont',
            isDupontCard: true
          })
        }
        
        // 触发事件，传递选中的卡片数据和探索问题
        this.$emit('generate-comprehensive-analysis', selectedCardsData, this.explorationQuestion.trim() || null)
      } catch (error) {
        console.error('生成总分析失败:', error)
        this.generatingAnalysis = false
      }
    },
    isCardSelected(cardId) {
      return this.selectedCards.includes(cardId)
    },
    isDupontCardSelected() {
      return this.selectedDupontCard
    },
    // 已移除，使用handleGenerateAnalysis替代
    resetSelection() {
      // 重置选择状态（由父组件调用）
      this.selectedCards = []
      this.explorationQuestion = ''
      this.generatingAnalysis = false
      this.recommendedQuestions = []
    },
    // 获取视图类型图标
    getViewTypeIcon(viewType) {
      const icons = {
        'verify': '✓',
        'explain': '🔍',
        'navigate': '🧭',
        'comprehensive': '💡'
      }
      return icons[viewType] || '📊'
    },
    // 获取视图类型标签
    getViewTypeLabel(viewType) {
      const labels = {
        'verify': '验证',
        'explain': '解释',
        'navigate': '导航',
        'comprehensive': '综合'
      }
      return labels[viewType] || viewType
    },
    // 获取数据质量标签
    getQualityLabel(quality) {
      const labels = {
        'high': '高质量',
        'medium': '中等',
        'low': '低质量'
      }
      return labels[quality] || quality
    },
    // 获取置信度标签
    getConfidenceLabel(confidence) {
      const labels = {
        'high': '高置信度',
        'medium': '中置信度',
        'low': '低置信度'
      }
      return labels[confidence] || confidence
    },
    // 获取卡片标题（根据ID）
    getCardTitle(cardId) {
      const card = this.visualizationCards.find(c => c.id === cardId)
      return card ? (card.question || '未知视图') : '未知视图'
    }
  },
  mounted() {
    // 监听重置选择事件
    window.addEventListener('reset-viz-selection', this.resetSelection)
    // 杜邦数据已存在时（如从父组件传入），强制不显示为选中，必须点击后才选中
    if (this.dupontData && (this.dupontData.full_data || this.dupontData.roe)) {
      this.selectedDupontCard = false
      this.dupontCardSelectionUnlocked = false
    }
  },
  beforeUnmount() {
    // 清理事件监听
    window.removeEventListener('reset-viz-selection', this.resetSelection)
  },
  watch: {
    chartData: { 
      handler() { 
        if (this.chartData && this.chartData.has_visualization) {
          // 使用$nextTick确保DOM已更新
          this.$nextTick(() => {
            setTimeout(() => {
              this.renderChart(null, this.chartData);
            }, 100);
          });
        }
      }, 
      deep: true 
    },
    visualizationCards: {
      handler(newCards, oldCards) {
        // 为每个卡片渲染图表
        console.log('📊 visualizationCards变化:', {
          oldCount: oldCards?.length || 0,
          newCount: newCards?.length || 0,
          cards: newCards.map(c => ({ id: c.id, type: c.type, question: c.question, hasViz: c.data?.has_visualization }))
        });
        
        // 使用$nextTick确保DOM已更新
        this.$nextTick(() => {
          // 为所有图表类型的卡片渲染图表
          newCards.forEach(card => {
            if (card.data && card.data.has_visualization && card.type === 'chart') {
              // 延迟渲染，确保DOM元素已创建
              setTimeout(() => {
                const vizType = card.data.visualization_type || 'plotly';
                console.log(`🎨 渲染图表卡片: ${card.id} - ${card.question} (类型: ${vizType})`);
                // 根据可视化类型决定渲染方式
                if (vizType === 'timeline' && card.data.timeline_data) {
                  // Timeline类型，由Vue模板直接渲染，不需要手动渲染
                  console.log(`✅ Timeline类型，由Vue模板渲染: ${card.id}`);
                } else if (vizType === 'plotly' && card.data.chart_config) {
                  // Plotly类型，只渲染Plotly
                  this.renderChart(card.id, card.data);
                } else {
                  console.warn(`⚠️ 卡片 ${card.id} 的可视化类型或数据不完整，跳过渲染`);
                }
              }, 200);
            }
          });
        });
      },
      deep: true,
      immediate: true  // 立即执行一次
    },
    dupontData: {
      immediate: true,
      deep: true,
      handler() {
        this.selectedDupontCard = false;
        // 新数据到达：不允许显示选中样式，直到用户点击卡片（避免一生成就选中，且点击后可正常选中/取消）
        this.dupontCardSelectionUnlocked = false;
        if (this.dupontYears.length > 0) {
          const preferredYear = Number(this.dupontData?.full_data?.report_year);
          if (preferredYear && this.dupontYears.includes(preferredYear)) {
            this.selectedDupontYear = preferredYear;
          } else {
            this.selectedDupontYear = this.dupontYears[0];
          }
        }
        this.$nextTick(() => {
          this.rerenderAllChartCards();
          this.selectedDupontCard = false;
          this.dupontCardSelectionUnlocked = false; // 再次确保新数据到达后不显示选中，必须点击才选中
        });
      }
    }
  }
}
</script>

<style scoped>
.viz-controls {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  padding: 4px 6px;
  background: #f9fafb;
  border-radius: 4px;
  border: 1px solid #e5e7eb;
}

.toggle-select-btn {
  padding: 4px 10px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.75rem;
  color: #374151;
  transition: all 0.2s;
  line-height: 1.2;
}

.toggle-select-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.toggle-select-btn.active {
  background: #0284c7;
  color: white;
  border-color: #0284c7;
}

.generate-analysis-btn {
  padding: 4px 10px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  transition: all 0.2s;
  line-height: 1.2;
}

.generate-analysis-btn:hover:not(:disabled) {
  background: #059669;
}

.generate-analysis-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 卡片直接选择（无需切换模式） */
.viz-card {
  cursor: pointer;
  transition: all 0.2s;
}

.viz-card:hover {
  border-color: #0284c7;
  box-shadow: 0 2px 8px rgba(2, 132, 199, 0.15);
}

.viz-card.selected {
  border: 2px solid #0284c7;
  background: #f0f9ff;
  box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
  position: relative;
}

.viz-card.selected::before {
  content: '✓';
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: #0284c7;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  z-index: 10;
  font-size: 14px;
}

/* 杜邦卡片选中态（与普通 viz-card 一致，确保蓝色边框与勾选随点击更新） */
.viz-card.dupont-card.selected {
  border: 2px solid #0284c7;
  background: #f0f9ff;
  box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
}

/* 联动生成的卡片样式 */
.viz-card.linkage-card {
  border-left: 4px solid #007bff;
  background: #fafbfc;
}

.viz-card.linkage-type-verify {
  border-left-color: #28a745;
}

.viz-card.linkage-type-explain {
  border-left-color: #17a2b8;
}

.viz-card.linkage-type-navigate {
  border-left-color: #ffc107;
}

.viz-card.linkage-type-comprehensive {
  border-left-color: #6f42c1;
}

/* 视图类型标签 */
.view-type-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  margin-left: 8px;
}

.badge-verify {
  background: #d4edda;
  color: #155724;
}

.badge-explain {
  background: #d1ecf1;
  color: #0c5460;
}

.badge-navigate {
  background: #fff3cd;
  color: #856404;
}

.badge-comprehensive {
  background: #e2d9f3;
  color: #6f42c1;
}

/* 数据质量标记 */
.data-quality-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-left: 6px;
}

.quality-high {
  background: #d4edda;
  color: #155724;
}

.quality-medium {
  background: #fff3cd;
  color: #856404;
}

.quality-low {
  background: #f8d7da;
  color: #721c24;
}

/* 分隔线 */
.cards-divider {
  margin: 24px 0 16px 0;
  padding: 12px 0;
  border-top: 2px dashed #e0e0e0;
  text-align: center;
}

.divider-text {
  background: #fff;
  padding: 0 16px;
  color: #666;
  font-size: 13px;
  font-weight: 500;
}

.selection-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 2px solid #d1d5db;
  border-radius: 4px;
  margin-right: 8px;
  background: white;
  transition: all 0.2s;
}

.selection-checkbox.checked {
  background: #0284c7;
  border-color: #0284c7;
  color: white;
  font-weight: bold;
}

.analysis-text-box {
  margin-top: 16px;
  padding: 12px;
  background: #f0f9ff;
  border-left: 4px solid #0284c7;
  border-radius: 6px;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #0c4a6e;
}

.insight-card {
  padding: 12px 14px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}

.insight-card-title {
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
}

.insight-card-headline {
  font-size: 0.95rem;
  color: #1e293b;
  margin-bottom: 6px;
}

.insight-card-row {
  font-size: 0.85rem;
  color: #334155;
}

.insight-label {
  color: #64748b;
  margin-right: 4px;
}

.timeline-container {
  width: 100%;
  padding: 12px 20px;
  background: #fff;
  border-radius: 8px;
  overflow-x: auto;
}

/* 纵向时间轴布局（紧凑型） */
.custom-timeline {
  position: relative;
  padding: 10px 0;
  min-height: 100px;
}

.custom-timeline::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e8e8e8;
  transform: translateX(-50%);
}

.timeline-item {
  position: relative;
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
  width: 50%;
  min-height: 40px;
}

.timeline-item:last-child {
  margin-bottom: 0;
}

.timeline-item-left {
  left: 0;
  flex-direction: row;
  padding-right: 35px;
  text-align: right;
}

.timeline-item-right {
  left: 50%;
  flex-direction: row-reverse;
  padding-left: 35px;
  text-align: left;
}

.timeline-dot {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #1890ff;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #e8e8e8;
  z-index: 2;
  flex-shrink: 0;
}

.timeline-item-left .timeline-dot {
  right: -5px;
  top: 2px;
}

.timeline-item-right .timeline-dot {
  left: -5px;
  top: 2px;
}

.timeline-content {
  flex: 1;
  min-width: 0;
  word-wrap: break-word;
  word-break: break-word;
}

.timeline-time {
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 4px;
  font-size: 12px;
  line-height: 1.3;
}

.timeline-item-left .timeline-time {
  text-align: right;
}

.timeline-item-right .timeline-time {
  text-align: left;
}

.timeline-text {
  color: #333;
  line-height: 1.4;
  font-size: 12px;
  word-wrap: break-word;
  word-break: break-word;
}

.timeline-item-left .timeline-text {
  text-align: right;
}

.timeline-item-right .timeline-text {
  text-align: left;
}

/* 响应式优化：在小屏幕上调整布局 */
@media (max-width: 768px) {
  .timeline-item {
    width: 100%;
    margin-bottom: 15px;
  }
  
  .timeline-item-left,
  .timeline-item-right {
    left: 0;
    flex-direction: row;
    padding-left: 35px;
    padding-right: 0;
    text-align: left;
  }
  
  .timeline-item-left .timeline-dot,
  .timeline-item-right .timeline-dot {
    left: 15px;
    right: auto;
  }
  
  .custom-timeline::before {
    left: 20px;
  }
  
  .timeline-item-left .timeline-time,
  .timeline-item-right .timeline-time,
  .timeline-item-left .timeline-text,
  .timeline-item-right .timeline-text {
    text-align: left;
  }
}


.analysis-text-box :deep(strong) {
  color: #0284c7;
  font-weight: 600;
}

.analysis-text-box :deep(ul) {
  margin: 8px 0;
  padding-left: 20px;
}

.analysis-text-box :deep(li) {
  margin: 4px 0;
}

/* 浮动操作栏 - 优化后的现代化设计（紧凑型） */
.floating-action-bar {
  position: relative;
  background: #ffffff;
  border: 2px solid #e5e7eb;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.03);
  z-index: 100;
  margin: 16px 0;
  background: rgba(255, 255, 255, 1);
  width: 100%;
  box-sizing: border-box;
  overflow: visible;
  border-radius: 10px;
  display: block !important;
  visibility: visible !important;
}

.action-bar-content {
  max-width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
}

/* 第一行：选中信息和生成按钮 */
.action-bar-row-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  flex-wrap: nowrap;
  position: relative;
}

/* 左侧：选中卡片信息 */
.selected-cards-info {
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
  flex: 0 0 auto;
  flex-shrink: 0;
}

.selected-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 10px;
  border-radius: 16px;
  font-weight: 600;
  font-size: 12px;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.25);
}

.selected-icon {
  font-size: 12px;
  line-height: 1;
}

.selected-count-text {
  font-size: 13px;
  font-weight: 700;
}

.selected-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.clear-selection-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s;
  padding: 0;
}

.clear-selection-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  transform: scale(1.1);
}

.clear-icon {
  font-size: 16px;
  color: #6b7280;
  line-height: 1;
  font-weight: 300;
}

.clear-selection-btn:hover .clear-icon {
  color: #dc2626;
}

/* 探索问题输入区域和推荐问题（合并在一起） */
.exploration-section {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background: #ffffff;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  transition: all 0.3s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.input-wrapper:focus-within {
  border-color: #667eea;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1), 0 1px 4px rgba(102, 126, 234, 0.12);
}

.input-icon {
  padding: 0 12px;
  font-size: 16px;
  color: #9ca3af;
  flex-shrink: 0;
}

.exploration-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 10px 8px;
  font-size: 13px;
  color: #111827;
  background: transparent;
  min-width: 0;
}

.exploration-input::placeholder {
  color: #9ca3af;
  font-size: 13px;
}

.input-clear {
  padding: 0 12px;
  font-size: 18px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1;
  font-weight: 300;
}

.input-clear:hover {
  color: #6b7280;
  transform: scale(1.15);
}

/* 推荐问题标签 */
.exploration-hints {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  width: 100%;
  box-sizing: border-box;
}

.hints-label {
  font-size: 11px;
  color: #6b7280;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.hints-container {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.hint-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 16px;
  font-size: 11px;
  color: #0369a1;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.hint-chip:hover {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-color: #60a5fa;
  transform: translateY(-1px);
  box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
}

.hint-icon {
  font-size: 12px;
  line-height: 1;
}

.hint-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
  line-height: 1.3;
}

.hint-chip:hover {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-color: #60a5fa;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.2);
}

.hint-icon {
  font-size: 14px;
  line-height: 1;
}


/* 生成按钮（缩小版，右上角） */
.generate-btn-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.35);
  min-width: 100px;
  flex: 0 0 auto;
  flex-shrink: 0;
  height: 32px;
  margin-left: auto;
  order: 2;
}

.generate-btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 3px 12px rgba(102, 126, 234, 0.45);
  background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
}

.generate-btn-primary:active:not(:disabled) {
  transform: translateY(0);
}

.generate-btn-primary:disabled {
  background: #d1d5db;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.btn-loading {
  display: flex;
  align-items: center;
  gap: 6px;
}

.loading-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-icon {
  font-size: 14px;
  line-height: 1;
}

.btn-text {
  line-height: 1.3;
  font-size: 12px;
}

/* 探索问题提示 */
.exploration-context {
  padding: 12px 16px;
  background: #e7f3ff;
  border-left: 3px solid #007bff;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.context-icon {
  font-size: 16px;
}

.context-label {
  font-weight: 500;
  color: #666;
}

.context-question {
  color: #333;
  font-style: italic;
}

/* 视图部分 */
.view-section {
  padding: 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

/* 洞察部分 */
.insight-section {
  padding: 16px;
  background: #fff;
}

.main-insight {
  margin-bottom: 16px;
  padding: 10px 12px;  /* ⭐减小内边距 */
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #007bff;
}

.insight-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-weight: 600;
  color: #333;
  font-size: 13px;  /* ⭐缩小标题字体 */
}

.insight-conclusion {
  margin-bottom: 12px;
  line-height: 1.5;
  font-size: 12px;  /* ⭐缩小字体 */
  color: #555;  /* ⭐稍微降低颜色对比度 */
}

.insight-findings {
  margin-top: 12px;
}

.insight-findings ul {
  margin: 8px 0 0 20px;
  padding: 0;
}

.insight-findings li {
  margin-bottom: 6px;
  line-height: 1.5;
}

.confidence-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-left: auto;
}

.confidence-high {
  background: #d4edda;
  color: #155724;
}

.confidence-medium {
  background: #fff3cd;
  color: #856404;
}

.confidence-low {
  background: #f8d7da;
  color: #721c24;
}

/* 推荐说明（联动卡片） */
.recommendation-box {
  margin-top: 16px;
  padding: 12px;
  background: #f0f7ff;
  border-radius: 6px;
  border-left: 3px solid #17a2b8;
}

.recommendation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 500;
}

.recommendation-content p {
  margin: 4px 0;
  font-size: 13px;
}

/* 数据洞察（联动卡片） */
.data-insights {
  margin-top: 16px;
  padding: 12px;
  background: #fffbf0;
  border-radius: 6px;
  border-left: 3px solid #ffc107;
}

.data-insights-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 500;
}

.data-insight-item {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e0e0e0;
}

.data-insight-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

/* 数据洞察完整展示：不截断，自动换行，展示 80–100 字完整内容 */
.data-insight-item .insight-text,
.insights-box .insight-item h4,
.insights-box .insight-item h4 span {
  white-space: normal;
  word-break: normal;
  overflow: visible;
  max-height: none;
}
.data-insight-item .insight-text {
  display: block;
  line-height: 1.5;
}
.insights-box .insight-item h4 {
  flex-wrap: wrap;
  line-height: 1.5;
}

.insight-findings-list {
  margin: 8px 0 0 20px;
  padding: 0;
}

.insight-findings-list li {
  margin-bottom: 4px;
  line-height: 1.4;
}

/* 关联信息 */
.related-cards-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e0e0e0;
}

.toggle-related-btn {
  padding: 6px 12px;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-related-btn:hover {
  background: #e0e0e0;
}

.related-cards-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.related-card-tag {
  padding: 4px 10px;
  background: #e9ecef;
  border-radius: 12px;
  font-size: 12px;
  color: #666;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .floating-action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 16px;
    border-radius: 16px 16px 0 0;
  }
  
  .action-bar-content {
    gap: 14px;
  }
  
  .action-bar-row-top {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  
  .selected-cards-info {
    justify-content: space-between;
  }
  
  .generate-btn-primary {
    width: 100%;
    padding: 12px 24px;
    font-size: 13px;
    border-radius: 10px;
  }
  
  .selected-badge {
    padding: 5px 10px;
    font-size: 12px;
  }
  
  .selected-label {
    font-size: 12px;
  }
  
  .input-wrapper {
    border-radius: 10px;
  }
  
  .exploration-input {
    padding: 12px 10px;
    font-size: 13px;
  }
  
  .hint-chip {
    padding: 5px 12px;
    font-size: 11px;
  }
  
  .hint-text {
    max-width: 150px;
  }
  
  .hints-label {
    font-size: 11px;
  }
}
</style>
