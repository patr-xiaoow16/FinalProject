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
            <button 
              class="quick-btn profit-forecast" 
              @click="handleQuickAnalysis('profit_forecast')"
              :disabled="loading"
              title="生成盈利预测分析"
            >
              <span class="btn-icon">📈</span>
              <span class="btn-text">盈利预测</span>
            </button>
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
      hoveredMessageIndex: null
    }; 
  },
  methods: {
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
      return typeof marked !== 'undefined' ? marked.parse(text) : text; 
    },
    deleteMessage(index) {
      this.$emit('delete-message', index);
    },
    handleDupontAnalysis() {
      this.$emit('dupont-analysis');
    },
    async handleQuickAnalysis(analysisType) {
      if (this.loading) return;
      
      // 特殊处理：杜邦分析 - 直接使用上方的杜邦分析按钮逻辑（沿用相同的视图）
      if (analysisType === 'dupont_analysis') {
        // 直接调用上方的杜邦分析方法，使用相同的API和视图
        this.$emit('dupont-analysis');
        return;
      }
      
      // 分析类型映射
      const typeMap = {
        'financial_review': '财务点评',
        'business_guidance': '业绩指引',
        'business_highlights': '业务亮点',
        'profit_forecast': '盈利预测和估值',
        'dupont_analysis': '杜邦分析'
      };
      
      const typeName = typeMap[analysisType] || analysisType;
      
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
          typeName
        });
      } else {
        // 触发agent-query事件（无法拆解出公司/年份时回退）
        this.$emit('agent-query', question);
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

