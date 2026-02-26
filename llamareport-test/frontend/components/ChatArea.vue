<template>
  <Card title="智能问答" icon="💬" status="content" empty-text="开始对话，提出问题">
    <template #default>
      <div class="chat-container">
        <!-- 快捷分析按钮组 -->
        <div class="quick-analysis-buttons">
          <div class="buttons-grid">
            <button 
              class="quick-btn financial-review" 
              @click="handleQuickAnalysis('financial_review')"
              :disabled="loading"
              title="生成财务点评分析"
            >
              <span class="btn-icon">💰</span>
              <span class="btn-text">财务点评</span>
            </button>
            <button 
              class="quick-btn dupont-analysis" 
              @click="handleQuickAnalysis('dupont_analysis')"
              :disabled="loading"
              title="生成杜邦分析"
            >
              <span class="btn-icon">📊</span>
              <span class="btn-text">杜邦分析</span>
            </button>
            <button 
              class="quick-btn business-guidance" 
              @click="handleQuickAnalysis('business_guidance')"
              :disabled="loading"
              title="生成业绩指引分析"
            >
              <span class="btn-icon">🎯</span>
              <span class="btn-text">业绩指引</span>
            </button>
            <button 
              class="quick-btn business-highlights" 
              @click="handleQuickAnalysis('business_highlights')"
              :disabled="loading"
              title="生成业务亮点分析"
            >
              <span class="btn-icon">⭐</span>
              <span class="btn-text">业务亮点</span>
            </button>
            <div class="profit-forecast-group">
              <button 
                class="quick-btn profit-forecast" 
                @click.stop="toggleProfitForecastSubButtons"
                :disabled="loading"
                :title="showProfitForecastSubButtons ? '收起子菜单' : '点击展开：相关性分析、聚类分析、因子分析、盈利预测、综合投资策略'"
              >
                <span class="btn-icon">📈</span>
                <span class="btn-text">投资策略</span>
                <span class="sub-arrow">{{ showProfitForecastSubButtons ? '▼' : '▶' }}</span>
              </button>
              <div v-show="showProfitForecastSubButtons" class="profit-forecast-sub-buttons">
                <button 
                  class="quick-btn sub-btn" 
                  @click="handleQuickAnalysis('profit_forecast', 'correlation_only')"
                  :disabled="loading"
                  title="仅生成相关性分析"
                >相关性分析</button>
                <button 
                  class="quick-btn sub-btn" 
                  @click="handleQuickAnalysis('profit_forecast', 'clustering')"
                  :disabled="loading"
                  title="仅生成聚类分析"
                >聚类分析</button>
                <button 
                  class="quick-btn sub-btn" 
                  @click="handleQuickAnalysis('profit_forecast', 'factor_only')"
                  :disabled="loading"
                  title="仅生成因子分析"
                >因子分析</button>
                <button 
                  class="quick-btn sub-btn" 
                  @click="handleQuickAnalysis('profit_forecast', 'earnings_forecast')"
                  :disabled="loading"
                  title="生成盈利预测（三情景）"
                >盈利预测</button>
                <button 
                  class="quick-btn sub-btn" 
                  @click="handleQuickAnalysis('profit_forecast', 'all')"
                  :disabled="loading"
                  title="生成综合投资策略（相关性、聚类、因子分析+综合洞察）"
                >综合投资策略</button>
              </div>
            </div>
          </div>
        </div>
        <div class="chat-messages" ref="messagesContainer">
          <div v-for="(msg, index) in messages" :key="index" :class="['chat-message', msg.type, { 'processing-summary': isProcessingSummary(msg.content) }]" @mouseenter="hoveredMessageIndex = index" @mouseleave="hoveredMessageIndex = null">
            <div class="message-content-wrapper">
              <button 
                v-if="hoveredMessageIndex === index" 
                class="message-delete-btn" 
                @click.stop="deleteMessage(index)" 
                title="删除消息"
              >
                ×
              </button>
              <div v-if="msg.type === 'user'" class="message-content">{{ msg.content }}</div>
              <div v-else class="message-content" v-html="parseMarkdown(msg.content)"></div>
            </div>
            <div v-if="msg.sources && msg.sources.length > 0" class="message-sources">
              <div v-for="(source, idx) in msg.sources" :key="idx" class="source-item">{{ source.text.substring(0, 100) }}...</div>
            </div>
          </div>
          <div v-if="loading" class="chat-message assistant loading">
            <div class="spinner"></div>
            <span>正在思考...</span>
          </div>
        </div>
        <div v-if="showSuggestions" class="suggestions-panel">
          <div class="suggestions-header">
            <span>💡 查询建议</span>
            <button class="btn-close" @click="showSuggestions = false" title="收起">×</button>
          </div>
          <div v-if="suggestions.length === 0" class="suggestions-loading">
            <div class="spinner-small"></div>
            <span>正在加载建议...</span>
          </div>
          <div v-else class="suggestions-container">
            <div v-for="(category, catIndex) in suggestions" :key="catIndex" class="suggestion-category">
              <div class="category-title">{{ category.category }}</div>
              <div class="suggestion-questions">
                <button 
                  v-for="(question, qIndex) in category.questions" 
                  :key="qIndex" 
                  class="suggestion-btn"
                  @click="useSuggestion(question); showSuggestions = false"
                >
                  {{ question }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="chat-input-area">
          <div class="chat-actions">
            <button :class="['btn-icon', { active: showSuggestions }]" @click="loadSuggestions" title="获取建议">💡</button>
            <button class="btn-icon" @click="clearChat" title="清空对话">🗑️</button>
          </div>
          <div class="chat-input-wrapper">
            <textarea ref="input" v-model="inputText" class="chat-input" placeholder="输入问题，Agent会根据问题自动选择分析工具（如：请分析XX公司2023年的业绩指引）" rows="1"></textarea>
            <button class="send-btn" @click="sendMessage" :disabled="!inputText.trim() || loading">发送</button>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script>
import Card from './Card.vue'

export default {
  name: 'ChatArea',
  components: {
    Card
  },
  props: { 
    messages: { type: Array, default: () => [] }, 
    loading: { type: Boolean, default: false },
    suggestions: { type: Array, default: () => [] },
    selectedFile: { type: Object, default: null },
    dupontData: { type: Object, default: null }
  },
  emits: ['send-message', 'clear-chat', 'agent-query', 'agent-analysis', 'dupont-analysis', 'get-suggestions', 'delete-message', 'quick-analysis'],
  data() { 
    return { 
      inputText: '', 
      showSuggestions: false,
      hoveredMessageIndex: null,
      showProfitForecastSubButtons: false
    }; 
  },
  methods: {
    toggleProfitForecastSubButtons() {
      this.showProfitForecastSubButtons = !this.showProfitForecastSubButtons;
    },
    sendMessage() {
      if (!this.inputText.trim() || this.loading) return;
      const question = this.inputText.trim();
      this.inputText = '';
      // 统一使用 agent-query，让 Agent 自动选择工具
      this.$emit('agent-query', question);
    },
    clearChat() { this.$emit('clear-chat'); },
    async loadSuggestions() {
      if (this.showSuggestions) {
        this.showSuggestions = false;
      } else {
        this.showSuggestions = true;
        if (!this.suggestions || this.suggestions.length === 0) {
          this.$emit('get-suggestions');
        }
      }
    },
    useSuggestion(question) {
      this.inputText = question;
    },
    parseMarkdown(text) {
      if (text == null) return '';
      const raw = typeof text === 'string' ? text : String(text);
      // 先规范化表格，避免“竖排/断行”导致列错位
      let out = raw;
      try {
        const hasMarkdownTable = /\|[^\n]+\|\s*\n\s*\|[\s\-:|]+\|/m.test(raw);
        out = hasMarkdownTable ? this.normalizeFactorTables(raw) : raw;
      } catch (error) {
        console.error('❌ [ChatArea] normalizeFactorTables failed:', error);
        out = raw;
      }
      // 去掉会触发代码块渲染的多余缩进（保留普通段落），避免黑白代码条
      out = out.split('\n').map((line) => {
        if (/^\s{4,}(\*|-|\d+\.)\s+/.test(line)) return line.replace(/^\s{4,}/, '');
        return line;
      }).join('\n');
      // 1. 仅处理“行首编号列表”，避免误伤表格中的小数（如 398.2 / 2.05）
      out = out.split('\n').map((line) => {
        const trimmed = line.trim();
        // Markdown 表格行跳过
        if (trimmed.startsWith('|') && trimmed.endsWith('|')) return line;
        return line.replace(/^(\s*)(\d+)\.\s+/g, '$1$2. ');
      }).join('\n');
      // 2. 按中文序号换行：在“一、”“二、”“三、”等前插入换行（非行首时）
      out = out.replace(/([^\n])([一二三四五六七八九十]+、)/g, '$1\n$2');
      // 按加粗小节标题换行
      out = out.replace(/([^\n])(\*\*(?:长期|风险|关键|短期)[^*]*\*\*)/g, '$1\n$2');
      return typeof marked !== 'undefined' && marked && marked.parse ? marked.parse(out) : out;
    },
    /**
     * 规范化因子分析等报告中的表格，使 Markdown 能正确渲染：
     * 1) 制表符行转为管道表格行
     * 1b) 将“每行仅一个非空单元格”的连续行按表头列数合并为一行（解决 LLM 竖排输出）
     * 2) 方差贡献表：因子名+三行数值 竖排合并
     * 3/3b) 因子得分、指标矩阵：年份+多列数值 竖排合并
     * 4) 因子载荷：指标名+3/4 个数值行 合并
     * 5) 表头后补充分隔行
     */
    normalizeFactorTables(text) {
      if (!text || typeof text !== 'string') return text;
      let out = text;
      const tableHeaderLike = /年份|项目|指标|因子|特征值|方差|贡献|得分|共同度|净息差|ROE|ROA|不良|拨备|成本收入比|信贷成本|有效税率|营收|净利润|EPS/;
      // 1. 制表符行 -> 管道表格行
      out = out.split('\n').map(line => {
        if (line.indexOf('\t') === -1) return line;
        const cells = line.split('\t').map(c => c.trim());
        return '| ' + cells.join(' | ') + ' |';
      }).join('\n');

      // 注意：不再把普通文本行自动转为表格行，避免误伤“资本/分红展望”“主要风险”等正文。

      // 1b. 合并“单列竖排”：每行只有第一个单元格非空（或整行只有一个非空）的连续 N 行 -> 一行 N 列（N=最近表头列数）
      out = this.collapseSingleCellPipeRows(out);

      // 2. 方差贡献分析：因子N：xxx + 三行（特征值、方差贡献率、累计贡献率）合并为一行
      out = out.replace(
        /(?:^\|\s*)?(因子\d+：[^\n|]+?)\s*\|?\s*\n\s*([\d.]+)\s*\n\s*([\d.]+%)\s*\n\s*([\d.]+%)/gm,
        (_, name, v1, v2, v3) => `| ${name.trim()} | ${v1} | ${v2} | ${v3} |`
      );

      // 3. 因子得分表：年份（4 位）+ 三行数值 合并为一行
      // 3b. 指标数据矩阵：年份 + 5～10 个数值行 合并为一行（先做多列，再做 3 列）
      for (let cols = 10; cols >= 5; cols--) {
        const numPart = Array(cols).fill('([-\\d.]+)').join('\\s*\\n\\s*');
        const re = new RegExp('(?:^\\|\\s*)?(\\d{4})\\s*\\|?\\s*\\n\\s*' + numPart, 'gm');
        out = out.replace(re, (m, year, ...vals) => '| ' + year + ' | ' + vals.slice(0, cols).join(' | ') + ' |');
      }
      out = out.replace(
        /(?:^\|\s*)?(\d{4})\s*\|?\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)/gm,
        (_, year, s1, s2, s3) => `| ${year} | ${s1} | ${s2} | ${s3} |`
      );

      // 4. 因子载荷/指标矩阵：指标名（短且非句子）+ 3 或 4 个数值行 合并为一行
      out = out.replace(
        /(?:^\|\s*)?([^\n|]{1,30}?)\s*\|?\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)\s*\n\s*([-\d.]+)(?:\s*\n\s*([-\d.]+))?/gm,
        (m, name, n1, n2, n3, n4) => {
          const nameTrim = name.trim();
          if (!nameTrim || /^[\d.]+$/.test(nameTrim)) return m;
          if (/[。，、]/.test(nameTrim) || nameTrim.length > 25) return m;
          if (n4 !== undefined) return `| ${nameTrim} | ${n1} | ${n2} | ${n3} | ${n4} |`;
          return `| ${nameTrim} | ${n1} | ${n2} | ${n3} |`;
        }
      );

      // 5. 所有管道表：表头后若无分隔行则插入（仅当首行像表头：含 年份/指标/因子/特征值/方差/贡献/得分/共同度 等）
      out = out.replace(
        /(^\|[^\n]+\|)\s*\n(\s*)(^\|[^\n]+\|)/gm,
        (m, header, mid, dataRow) => {
          if (!tableHeaderLike.test(header)) return m;
          if (/^\|[\s\-:|]+\|$/.test(header.trim())) return m;
          if (/^\|[\s\-:|]+\|$/.test(dataRow.trim())) return m;
          const colCount = (header.match(/\|/g) || []).length - 1;
          if (colCount < 2) return m;
          const sep = '|' + Array(colCount).fill('---').join('|') + '|';
          return header + '\n' + sep + '\n' + mid + dataRow;
        }
      );
      return out;
    },
    /**
     * 将“每行仅一个非空单元格”的连续管道行按最近表头列数合并为多列一行。
     * 解决 LLM 输出为「表头+每列竖排」时的错位（如 年份|空|空 + 2.75|空|空 + ...）。
     */
    collapseSingleCellPipeRows(text) {
      const headerLike = /年份|指标|因子|特征值|方差|贡献|得分|共同度|净息差|ROE|ROA|不良|拨备|成本|资本|平均|信贷/;
      const lines = text.split('\n');
      const result = [];
      let buffer = [];
      let colCount = 0;
      /** 因子载荷等：前两格有值的一行 + 后续 (colCount-2) 个单格行，合并为一行 */
      let rowPrefix = [];
      let needRest = 0;
      let rawCellBuffer = [];
      /** 单列表格竖排转横排：表头+多行单格 -> 一行多列 */
      let transposeBuffer = [];

      function isPipeLine(line) {
        const t = line.trim();
        return t.startsWith('|') && t.endsWith('|');
      }
      function isSeparatorLine(line) {
        const t = line.trim();
        return /^\|[\s\-:|]+\|$/.test(t);
      }
      function isHeaderLike(line) {
        return headerLike.test(line) && !isSeparatorLine(line);
      }
      /** 整行只有一个非空单元格时返回该值，否则返回 null */
      function singleCellValue(line) {
        const cells = line.split('|').map(c => c.trim()).filter(c => c.length > 0);
        return cells.length === 1 ? cells[0] : null;
      }
      /** 前两格非空、其余空时返回 [first, second]，否则 null（用于因子载荷等） */
      function firstTwoCells(line) {
        const cells = line.split('|').map(c => c.trim());
        const nonEmpty = cells.filter(c => c.length > 0);
        return nonEmpty.length === 2 ? nonEmpty : null;
      }
      function isRawCellLine(line) {
        const t = line.trim();
        return t.length > 0 && !t.startsWith('|') && (/^\d{4}$/.test(t) || /^-?[\d.]+%?$/.test(t));
      }

      function flushBuffer() {
        if (colCount >= 2 && buffer.length === colCount) {
          const vals = buffer.map(ln => singleCellValue(ln));
          if (vals.every(v => v !== null)) result.push('| ' + vals.join(' | ') + ' |');
          else buffer.forEach(l => result.push(l));
        } else buffer.forEach(l => result.push(l));
        buffer = [];
      }
      function flushRowPrefix() {
        if (rowPrefix.length > 0) {
          result.push('| ' + rowPrefix.join(' | ') + ' |');
          rowPrefix = [];
          needRest = 0;
        }
      }
      function flushRawCellBuffer() {
        if (colCount >= 2 && rawCellBuffer.length === colCount) {
          result.push('| ' + rawCellBuffer.join(' | ') + ' |');
        } else rawCellBuffer.forEach(l => result.push(l));
        rawCellBuffer = [];
      }
      function flushTransposeBuffer() {
        if (!transposeBuffer.length) return;
        // 将“单列表头 + 多个单值行”合并为一行多列，避免竖排错位
        if (transposeBuffer.length >= 2) {
          result.push('| ' + transposeBuffer.join(' | ') + ' |');
        } else {
          result.push(transposeBuffer[0]);
        }
        transposeBuffer = [];
        if (colCount === 1) colCount = 0;
      }

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (!isPipeLine(line)) {
          flushBuffer();
          flushRowPrefix();
          flushTransposeBuffer();
          if (isRawCellLine(line) && colCount >= 2) {
            rawCellBuffer.push(line.trim());
            if (rawCellBuffer.length === colCount) {
              result.push('| ' + rawCellBuffer.join(' | ') + ' |');
              rawCellBuffer = [];
            }
          } else {
            flushRawCellBuffer();
            colCount = 0;
            result.push(line);
          }
          continue;
        }
        if (isSeparatorLine(line)) {
          flushBuffer();
          flushRowPrefix();
          flushRawCellBuffer();
          flushTransposeBuffer();
          result.push(line);
          continue;
        }
        const twoCell = firstTwoCells(line);
        const single = singleCellValue(line) !== null;
        if (isHeaderLike(line)) {
          flushBuffer();
          flushRowPrefix();
          flushRawCellBuffer();
          const n = (line.match(/\|/g) || []).length - 1;
          if (n >= 2) {
            flushTransposeBuffer();
            colCount = n;
            result.push(line);
          } else if (n === 1) {
            flushTransposeBuffer();
            const headerCell = singleCellValue(line);
            if (headerCell !== null) {
              transposeBuffer = [headerCell];
              colCount = 1;
            } else {
              result.push(line);
            }
          } else {
            result.push(line);
          }
          continue;
        }
        if (single && colCount === 1) {
          const v = singleCellValue(line);
          if (v !== null) {
            transposeBuffer.push(v);
            continue;
          }
        }
        if (twoCell !== null && colCount >= 2) {
          flushBuffer();
          const rest = colCount - 2;
          if (rest <= 0) {
            result.push(line);
            continue;
          }
          rowPrefix = [...twoCell];
          needRest = rest;
          continue;
        }
        if (single && needRest > 0) {
          const v = singleCellValue(line);
          rowPrefix.push(v);
          needRest--;
          if (needRest === 0) {
            result.push('| ' + rowPrefix.join(' | ') + ' |');
            rowPrefix = [];
          }
          continue;
        }
        if (single && colCount >= 2) {
          flushRowPrefix();
          buffer.push(line);
          if (buffer.length === colCount) {
            const vals = buffer.map(ln => singleCellValue(ln));
            if (vals.every(v => v !== null)) result.push('| ' + vals.join(' | ') + ' |');
            else buffer.forEach(l => result.push(l));
            buffer = [];
          }
          continue;
        }
        flushBuffer();
        flushRowPrefix();
        colCount = 0;
        result.push(line);
      }
      flushBuffer();
      flushRowPrefix();
      flushRawCellBuffer();
      flushTransposeBuffer();
      return result.join('\n');
    },
    deleteMessage(index) {
      this.$emit('delete-message', index);
    },
    handleDupontAnalysis() {
      this.$emit('dupont-analysis');
    },
    async handleQuickAnalysis(analysisType, modelType = null) {
      if (this.loading) return;
      
      // 特殊处理：杜邦分析 - 直接使用上方的杜邦分析按钮逻辑（沿用相同的视图）
      if (analysisType === 'dupont_analysis') {
        // 直接调用上方的杜邦分析方法，使用相同的API和视图
        this.$emit('dupont-analysis');
        return;
      }
      
      // 分析类型映射（投资策略子类型优先）
      const typeMap = {
        'financial_review': '财务点评',
        'business_guidance': '业绩指引',
        'business_highlights': '业务亮点',
        'profit_forecast': '投资策略',
        'dupont_analysis': '杜邦分析'
      };
      const profitForecastSubMap = {
        'correlation_only': '相关性分析',
        'clustering': '聚类分析',
        'factor_only': '因子分析',
        'earnings_forecast': '盈利预测',
        'all': '综合投资策略'
      };
      const typeName = (analysisType === 'profit_forecast' && modelType && profitForecastSubMap[modelType])
        ? profitForecastSubMap[modelType]
        : (typeMap[analysisType] || analysisType);
      
      // 构建问题 - 改进的提取逻辑
      let companyName = '';
      let year = '';
      
      // 如果有选中的文件，尝试从文件名提取公司名和年份
      // 参考后端 /api/query.py 中的提取逻辑
      if (this.selectedFile && this.selectedFile.filename) {
        const filename = this.selectedFile.filename;
        
        // 改进的年份提取（验证年份合理性，参考后端逻辑）
        const yearMatch = filename.match(/(\d{4})/);
        if (yearMatch) {
          const candidateYear = parseInt(yearMatch[1]);
          // 验证年份在合理范围内（2000-2030），参考后端验证逻辑
          if (candidateYear >= 2000 && candidateYear <= 2030) {
            year = yearMatch[1];
          }
        }
        
        // 改进的公司名提取（完全参考后端逻辑）
        // 1. 移除文件扩展名
        let nameWithoutExt = filename.replace(/\.[^.]+$/, '');
        
        // 2. 移除常见的报表类型关键词（参考后端完整列表）
        nameWithoutExt = nameWithoutExt.replace(/(利润表|资产负债表|现金流量表|年报|年度报告|报告|财务报表|财务报告|合并报表|母公司报表)/gi, '');
        
        // 3. 移除年份（4位数字，在移除年份之前先提取）
        nameWithoutExt = nameWithoutExt.replace(/\d{4}年?/g, '');
        
        // 4. 移除"年度"和后面的数字（如"年度60"）
        nameWithoutExt = nameWithoutExt.replace(/年度\d+/g, '');
        
        // 5. 移除多余的分隔符和空格（参考后端逻辑）
        nameWithoutExt = nameWithoutExt.replace(/[_\-\s\.]+/g, '').trim();
        
        // 6. 验证公司名长度（2-30个字符，参考后端验证）
        if (nameWithoutExt.length >= 2 && nameWithoutExt.length <= 30) {
          companyName = nameWithoutExt;
        }
      }
      
      // 如果提取失败，尝试从后端API获取（通过quick-overview接口）
      if ((!companyName || !year) && this.selectedFile && this.selectedFile.filename) {
        try {
          const response = await fetch('/query/quick-overview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          
          if (response.ok) {
            const result = await response.json();
            // quick-overview接口会在处理过程中提取公司名和年份
            // 但这里我们只是尝试，如果失败就继续使用前端提取的结果
            // 注意：这个接口可能比较慢，所以我们只在提取失败时尝试
          }
        } catch (error) {
          // 静默失败，继续使用前端提取的结果
          console.debug('从后端提取公司信息失败，使用前端提取结果:', error);
        }
      }
      
      // 构建问题 - 使用更明确的指令让Agent提取
      // 参考后端逻辑，使用更标准的问题格式
      let question = '';
      if (companyName && year) {
        // 有公司名和年份，直接使用（最准确）
        question = `请分析${companyName}${year}年的${typeName}`;
      } else if (companyName) {
        // 只有公司名，让Agent先查询年份
        question = `请查询${companyName}的报告年份，然后分析${companyName}的${typeName}`;
      } else if (year) {
        // 只有年份，让Agent先查询公司名
        question = `请查询${year}年的公司名称，然后分析${year}年的${typeName}`;
      } else {
        // 都没有，让Agent先查询公司名和年份
        // 使用自然语言，让Agent自己判断需要先获取信息
        question = `请从文档中提取公司名称和报告年份，然后生成${typeName}分析`;
      }
      
      if (companyName && year) {
        this.$emit('quick-analysis', {
          sectionName: analysisType,
          companyName,
          year,
          question,
          typeName,
          modelType
        });
      } else {
        // 触发agent-query事件（无法拆解出公司/年份时回退）
        const modelHint = modelType && analysisType === 'profit_forecast'
          ? `（使用${modelType}模型）`
          : '';
        this.$emit('agent-query', `${question}${modelHint}`);
      }
    },
    isProcessingSummary(content) {
      if (!content) return false;
      const text = typeof content === 'string' ? content : '';
      return text.includes('批量处理完成') || text.includes('处理成功的文件') || text.includes('处理失败');
    }
  },
  watch: {
    suggestions: {
      handler(newVal) {
        if (newVal && newVal.length > 0 && this.showSuggestions) {
          this.$nextTick(() => {});
        }
      },
      immediate: true
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.$refs.input?.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') this.sendMessage();
      });
    });
  }
}
</script>
