<template>
  <Card title="财务概况" icon="🏢" :status="status" empty-text="暂无财务概况数据">
    <template #default>
      <div class="company-overview-container">
        <!-- 未选中文件时提示 -->
        <div v-if="!selectedFile" class="overview-placeholder">
          <p class="placeholder-text">请在左侧文件列表中选择文件以查看财务概况</p>
        </div>
        <!-- 已选文件但未处理：提示先处理 -->
        <div v-else-if="selectedFile && !loading && (overviewForFilename !== selectedFile.filename || !overviewData)" class="overview-placeholder">
          <p class="placeholder-text">请先点击「处理」按钮处理选中的文件，处理完成后将自动展示财务概况</p>
        </div>
        <!-- 一句话结论 - 处理完成后展示 -->
        <div v-else-if="overviewData?.verdict" class="verdict-container">
          <div class="verdict-label">
            <span class="verdict-icon">📊</span>
            <span>核心结论</span>
          </div>
          <div class="verdict-text" v-html="formatVerdict(overviewData.verdict)"></div>
          
          <!-- 只保留风险级别标签 -->
          <div class="verdict-tags">
            <div v-if="overviewData.risk_level" :class="['verdict-tag', getRiskClass(overviewData.risk_level)]">
              <span class="tag-icon">{{ getRiskIcon(overviewData.risk_level) }}</span>
              <span class="tag-label">风险级别</span>
              <span class="tag-value">{{ overviewData.risk_level }}</span>
            </div>
          </div>
        </div>
        
        <!-- 无结论时显示 -->
        <div v-else-if="selectedFile && overviewForFilename === selectedFile.filename && !overviewData?.verdict" class="no-verdict">
          <p class="no-verdict-text">暂无财务概况结论</p>
        </div>
        
        <!-- 核心指标：仅当当前选中的文件已处理并加载了概况时展示 -->
        <div v-if="selectedFile && overviewForFilename === selectedFile.filename && overviewData" class="core-metrics-wrap">
          <div class="core-metrics-title">{{ overviewData.year ? overviewData.year + '年核心指标' : '核心指标' }}</div>
          <div class="metrics-cards metrics-cards-2col">
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.revenue) }" @click="hasMetricData(overviewData.revenue) && handleMetricClick('营业收入', overviewData.revenue)">
              <div class="metric-name">{{ metricLabel('revenue') }}</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.revenue) }}</div>
              <div v-if="getMetricChange(overviewData.revenue)" :class="['metric-change', getChangeClassInverted(overviewData.revenue)]">
                {{ getMetricChangeWithArrow(overviewData.revenue) }}
              </div>
            </div>
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.net_profit) }" @click="hasMetricData(overviewData.net_profit) && handleMetricClick('净利润', overviewData.net_profit)">
              <div class="metric-name">{{ metricLabel('net_profit') }}</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.net_profit) }}</div>
              <div v-if="getMetricChange(overviewData.net_profit)" :class="['metric-change', getChangeClassInverted(overviewData.net_profit)]">
                {{ getMetricChangeWithArrow(overviewData.net_profit) }}
              </div>
            </div>
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.total_assets) }" @click="hasMetricData(overviewData.total_assets) && handleMetricClick('总资产', overviewData.total_assets)">
              <div class="metric-name">{{ metricLabel('total_assets') }}</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.total_assets) }}</div>
              <div v-if="getMetricChange(overviewData.total_assets)" :class="['metric-change', getChangeClassInverted(overviewData.total_assets)]">
                {{ getMetricChangeWithArrow(overviewData.total_assets) }}
              </div>
            </div>
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.roe) }" @click="hasMetricData(overviewData.roe) && handleMetricClick('ROE', overviewData.roe)">
              <div class="metric-name">ROE</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.roe) }}</div>
              <div v-if="getMetricChange(overviewData.roe)" :class="['metric-change', getChangeClassInverted(overviewData.roe)]">
                {{ getMetricChangeWithArrow(overviewData.roe) }}
              </div>
            </div>
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.net_interest_margin) }" @click="hasMetricData(overviewData.net_interest_margin) && handleMetricClick('净息差', overviewData.net_interest_margin)">
              <div class="metric-name">净息差</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.net_interest_margin) }}</div>
              <div v-if="getMetricChange(overviewData.net_interest_margin)" :class="['metric-change', getChangeClassInverted(overviewData.net_interest_margin)]">
                {{ getMetricChangeWithArrow(overviewData.net_interest_margin) }}
              </div>
            </div>
            <div class="metric-card core-metric" :class="{ clickable: hasMetricData(overviewData.npl_ratio) }" @click="hasMetricData(overviewData.npl_ratio) && handleMetricClick('不良率', overviewData.npl_ratio)">
              <div class="metric-name">不良率</div>
              <div class="metric-value">{{ formatMetricValue(overviewData.npl_ratio) }}</div>
              <div v-if="getMetricChange(overviewData.npl_ratio)" :class="['metric-change', getChangeClassInverted(overviewData.npl_ratio)]">
                {{ getMetricChangeWithArrow(overviewData.npl_ratio) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script>
import Card from './Card.vue'

export default {
  name: 'CompanyOverview',
  components: {
    Card
  },
  props: { 
    data: { type: Object, default: null }, 
    loading: { type: Boolean, default: false },
    overviewData: { type: Object, default: null },
    selectedFile: { type: Object, default: null },
    /** 当前概况对应的文件名（仅在处理该文件成功后有值） */
    overviewForFilename: { type: String, default: null }
  },
  emits: ['generate-report', 'metric-click'],
  data() { 
    return { 
      activeTab: 'basic'
    }; 
  },
  computed: {
    status() {
      if (!this.selectedFile) return 'empty';
      if (this.loading) return 'loading';
      if (!this.overviewData && !this.data) return 'empty';
      return 'content';
    },
    hasMetrics() {
      return this.overviewData && (
        this.hasMetricData(this.overviewData.roe) ||
        this.hasMetricData(this.overviewData.revenue) ||
        this.hasMetricData(this.overviewData.net_profit) ||
        this.hasMetricData(this.overviewData.total_assets) ||
        this.hasMetricData(this.overviewData.net_interest_margin) ||
        this.hasMetricData(this.overviewData.cost_income_ratio) ||
        this.hasMetricData(this.overviewData.npl_ratio)
      );
    }
  },
  methods: {
    hasMetricData(metric) {
      // 检查指标是否有有效数据（不是缺失的）
      if (!metric) return false;
      if (typeof metric === 'string') return metric && metric !== '—';
      if (typeof metric === 'object') {
        // 如果是缺失的，返回false
        if (metric.is_missing) return false;
        // 如果有值且不是'—'，返回true
        const value = metric.value;
        return value && value !== '—' && value !== 'N/A';
      }
      return false;
    },
    async generateReport() {
      this.$emit('generate-report');
    },
    parseMarkdown(text) {
      if (!text) return '';
      if (typeof marked !== 'undefined' && marked && marked.parse) {
        return marked.parse(text);
      }
      return text;
    },
    getStageClass(stage) {
      if (stage === '增长') return 'tag-stage-growth';
      if (stage === '下行') return 'tag-stage-decline';
      return 'tag-stage-stable';
    },
    getStageIcon(stage) {
      if (stage === '增长') return '📈';
      if (stage === '下行') return '📉';
      return '➡️';
    },
    getRiskClass(risk) {
      if (risk === '低') return 'tag-risk-low';
      if (risk === '高') return 'tag-risk-high';
      return 'tag-risk-medium';
    },
    getRiskIcon(risk) {
      if (risk === '低') return '✅';
      if (risk === '高') return '⚠️';
      return '⚡';
    },
    formatVerdict(text) {
      if (!text) return '';
      // 高亮关键信息：阶段、赚钱质量、风险级别
      let formatted = text
        .replace(/(增长|稳态|下行)/g, '<strong class="highlight-stage">$1</strong>')
        .replace(/(风险级别[：:]\s*)(低|中|高)/g, '$1<strong class="highlight-risk">$2</strong>')
        .replace(/(利润质量|现金质量)([^，,。、]+)/g, '<strong class="highlight-quality">$1$2</strong>');
      return formatted;
    },
    formatProfitQuality(quality) {
      if (!quality) return '—';
      // 如果太长，截断
      if (quality.length > 15) {
        return quality.substring(0, 15) + '...';
      }
      return quality;
    },
    formatMetricValue(metric) {
      if (!metric) return '—';
      if (typeof metric === 'string') return metric;
      if (typeof metric === 'object') {
        if (metric.is_missing) return '—';
        return metric.value || '—';
      }
      return '—';
    },
    /** 统一规范化趋势字符串（如将 Unicode 减号 − 转为 ASCII -），便于判断涨跌 */
    normalizeChangeRate(str) {
      if (str == null || typeof str !== 'string') return str;
      return str.replace(/\u2212/g, '-').trim();
    },
    getMetricChange(metric) {
      if (!metric || typeof metric !== 'object') return null;
      if (metric.is_missing) return null;
      const changeRate = metric.change_rate;
      const direction = metric.change_direction;
      const isFlat = direction === '持平' || direction === '不变';
      if (isFlat) return '—';
      if (changeRate) {
        return this.normalizeChangeRate(changeRate) || changeRate;
      }
      if (direction) {
        return direction === '增长' ? '↑' : direction === '下降' ? '↓' : '—';
      }
      return null;
    },
    getChangeClass(metric) {
      if (!metric || typeof metric !== 'object') return '';
      const changeRate = this.normalizeChangeRate(metric.change_rate);
      const direction = metric.change_direction;
      
      if (changeRate) {
        if (changeRate.includes('+') || changeRate.includes('增长')) {
          return 'change-positive';
        } else if (changeRate.includes('-') || changeRate.includes('下降')) {
          return 'change-negative';
        }
      }
      
      if (direction === '增长') return 'change-positive';
      if (direction === '下降') return 'change-negative';
      
      return '';
    },
    /** 核心指标区：上升为红色、下降为绿色、不变为黑色— */
    getChangeClassInverted(metric) {
      if (!metric || typeof metric !== 'object') return '';
      const changeRate = this.normalizeChangeRate(metric.change_rate);
      const direction = metric.change_direction;
      if (direction === '持平' || direction === '不变') return 'change-flat';
      const isUp = (changeRate && (changeRate.includes('+') || changeRate.includes('增长'))) || direction === '增长';
      const isDown = (changeRate && (changeRate.includes('-') || changeRate.includes('下降'))) || direction === '下降';
      if (isUp) return 'change-up-red';
      if (isDown) return 'change-down-green';
      return '';
    },
    /** 带箭头的趋势文案：▲ 3.3% 或 ▼ 10.9% 或 —（不变） */
    getMetricChangeWithArrow(metric) {
      const direction = metric && typeof metric === 'object' ? metric.change_direction : null;
      if (direction === '持平' || direction === '不变') return '—';
      const change = this.getMetricChange(metric);
      if (!change) return '';
      const normalized = this.normalizeChangeRate(String(change));
      const isUp = (normalized && (normalized.includes('+') || normalized.includes('增长'))) || direction === '增长';
      const isDown = (normalized && (normalized.includes('-') || normalized.includes('下降'))) || direction === '下降';
      const arrow = isUp ? '▲ ' : isDown ? '▼ ' : '';
      const rate = String(change).replace(/增长|下降|持平|不变/g, '').trim().replace(/\u2212/g, '-');
      return rate ? arrow + rate : change;
    },
    metricLabel(key) {
      const labels = {
        revenue: '营业收入(亿)',
        net_profit: '净利润(亿)',
        total_assets: '总资产(亿)'
      };
      return labels[key] || key;
    },
    handleMetricClick(metricName, metricData) {
      // 触发事件，传递指标名称和数据
      this.$emit('metric-click', {
        metricName: metricName,
        metricData: metricData
      });
    }
  }
}
</script>

<style scoped>
.company-overview-container {
  position: relative;
  padding: 12px;
  width: 100%;
  max-width: 100%;
}

.missing-fields-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #fef3c7;
  border-radius: 12px;
  cursor: help;
  font-size: 0.75rem;
  z-index: 10;
}

.missing-dot {
  font-size: 0.875rem;
}

.missing-count {
  background: #fbbf24;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 600;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.info-row:hover {
  background: #f3f4f6;
}

.info-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  min-width: 140px;
  flex-shrink: 0;
}

.info-icon {
  font-size: 1rem;
}

.info-value {
  flex: 1;
  text-align: right;
  font-size: 0.875rem;
  color: #111827;
  font-weight: 500;
  word-break: break-word;
}

.info-value.missing {
  color: #9ca3af;
  font-style: italic;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 600px;
  overflow-y: auto;
}

.news-item {
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  border-left: 3px solid #4facfe;
  transition: all 0.2s;
}

.news-item:hover {
  background: #f3f4f6;
  border-left-color: #0284c7;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.news-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.news-type {
  font-size: 0.75rem;
  color: #4facfe;
  background: #e0f2fe;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.news-date {
  font-size: 0.75rem;
  color: #6b7280;
}

.news-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #111827;
  margin-bottom: 6px;
  line-height: 1.4;
}

.news-content {
  font-size: 0.8125rem;
  color: #4b5563;
  line-height: 1.5;
}

.no-news {
  padding: 40px 20px;
  text-align: center;
}

.no-news-text {
  color: #9ca3af;
  font-size: 0.875rem;
  font-style: italic;
}

.verdict-container {
  padding: 10px 8px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 8px;
  border: 1px solid #bae6fd;
  margin: 0 -4px 16px -4px;
  width: calc(100% + 8px);
  max-width: calc(100% + 8px);
}

.verdict-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #0369a1;
}

.verdict-icon {
  font-size: 0.875rem;
}

.verdict-text {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: #0c4a6e;
  font-weight: 400;
  margin-bottom: 12px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border-left: 4px solid #0284c7;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.verdict-text :deep(.highlight-stage) {
  color: #dc2626;
  font-weight: 700;
  padding: 2px 4px;
  background: #fee2e2;
  border-radius: 3px;
}

.verdict-text :deep(.highlight-quality) {
  color: #7c3aed;
  font-weight: 600;
}

.verdict-text :deep(.highlight-risk) {
  color: #dc2626;
  font-weight: 700;
}

.verdict-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.verdict-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
}

.tag-icon {
  font-size: 0.875rem;
}

.tag-label {
  color: #6b7280;
  font-size: 0.7rem;
}

.tag-value {
  font-weight: 600;
}

.tag-stage-growth {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.tag-stage-stable {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde047;
}

.tag-stage-decline {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

.tag-profit {
  background: #e0e7ff;
  color: #3730a3;
  border: 1px solid #a5b4fc;
}

.tag-risk-low {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.tag-risk-medium {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde047;
}

.tag-risk-high {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

.overview-placeholder {
  padding: 40px 20px;
  text-align: center;
}

.placeholder-text {
  color: #9ca3af;
  font-size: 0.9rem;
}

.no-verdict {
  padding: 40px 20px;
  text-align: center;
}

.no-verdict-text {
  color: #9ca3af;
  font-size: 0.875rem;
  font-style: italic;
}

/* 核心指标区域：与核心结论外围同宽，白底、每行2个，不超出 */
.core-metrics-wrap {
  background: #ffffff;
  border-radius: 10px;
  padding: 14px 12px;
  margin: 0 -4px 16px -4px;
  width: calc(100% + 8px);
  max-width: calc(100% + 8px);
  border: 1px solid #e5e7eb;
  overflow: hidden;
  min-width: 0;
  box-sizing: border-box;
}

.core-metrics-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #b45309;
  margin-bottom: 12px;
  padding-left: 2px;
}

/* 核心指标区强制每行 2 个，缩小两列间距以增加每卡宽度，不超出容器 */
.core-metrics-wrap .metrics-cards.metrics-cards-2col,
.metrics-cards-2col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 8px;
  min-width: 0;
}

/* 核心指标单卡：不超出外围 */
.core-metric.metric-card {
  padding: 10px 12px;
  min-width: 0;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.core-metric .metric-name {
  font-size: 0.7rem;
  color: #6b7280;
  margin-bottom: 6px;
}

.core-metric .metric-value {
  font-size: 1rem;
  font-weight: 700;
  color: #111827;
  margin-bottom: 4px;
}

/* 趋势：上升红色、下降绿色 */
.metric-change.change-up-red {
  color: #dc2626;
  font-size: 0.75rem;
  font-weight: 500;
}

.metric-change.change-down-green {
  color: #16a34a;
  font-size: 0.75rem;
  font-weight: 500;
}

/* 趋势不变：黑色 — */
.metric-change.change-flat {
  color: #111827;
  font-size: 0.75rem;
  font-weight: 500;
}

/* 关键指标卡片样式（兼容旧布局） */
.metrics-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  transition: all 0.2s;
}

.metric-card.clickable {
  cursor: pointer;
  position: relative;
}

.metric-card.clickable:hover {
  background: #f0f9ff;
  border-color: #0284c7;
  box-shadow: 0 2px 8px rgba(2, 132, 199, 0.15);
  transform: translateY(-2px);
}

.metric-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.metric-icon {
  font-size: 1rem;
}

.metric-name {
  font-size: 0.7rem;
  color: #6b7280;
  font-weight: 500;
}

.metric-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
  word-break: break-word;
}

.metric-change {
  font-size: 0.7rem;
  font-weight: 500;
  margin-top: 4px;
}

.metric-change.change-positive {
  color: #16a34a;
}

.metric-change.change-negative {
  color: #dc2626;
}

.metric-hint {
  font-size: 0.65rem;
  color: #6b7280;
  position: absolute;
  bottom: 8px;
  left: 0;
  right: 0;
  opacity: 0;
  transition: opacity 0.2s;
  text-align: center;
  pointer-events: none;
}

.metric-card.clickable:hover .metric-hint {
  opacity: 1;
}

</style>

