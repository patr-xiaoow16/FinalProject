import { createApp } from 'vue'
import { ref, reactive, onMounted } from 'vue'

// 导入组件
import Card from './components/Card.vue'
import FilePreviewCard from './components/FilePreviewCard.vue'
import ChatArea from './components/ChatArea.vue'
import CompanyOverview from './components/CompanyOverview.vue'
import NotesAndRisks from './components/NotesAndRisks.vue'
import VisualizationPanel from './components/VisualizationPanel.vue'
import MessageToast from './components/MessageToast.vue'
import AgentAnalysisPage from './components/AgentAnalysisPage.vue'

// 导入样式
import './style.css'

// 主应用组件
const App = {
  setup() {
    const systemStatus = ref('检查中...')
    const currentPage = ref('main')  // 'main' 或 'agent-analysis'
    const files = ref([])
    const selectedFile = ref(null)
    const chatMessages = ref([])
    const queryLoading = ref(false)
    const message = reactive({ type: '', text: '' })
    const companyOverviewData = ref(null)
    const companyOverviewLoading = ref(false)
    const quickOverviewData = ref(null)
    const notesAndRisksData = ref(null)
    const notesAndRisksLoading = ref(false)
    const dupontData = ref(null)
    const dupontLoading = ref(false)
    const visualizationData = ref(null)
    const visualizationLoading = ref(false)
    const visualizationCards = ref([])  // 存储所有可视化卡片
    const processStatus = ref(null)
    const suggestions = ref([])
    
    const checkSystemStatus = async () => {
      try {
        const response = await fetch('/health')
        const data = await response.json()
        systemStatus.value = data.status === 'healthy' ? '✅ 系统正常运行' : '⚠️ 系统状态异常'
      } catch (error) {
        systemStatus.value = '❌ 无法连接到服务器'
      }
    }
    
    const loadFileList = async () => {
      try {
        const response = await fetch('/upload/list')
        const data = await response.json()
        files.value = data.files || []
      } catch (error) {
        console.error('加载文件列表失败:', error)
      }
    }
    
    const showMessage = (type, text) => {
      message.type = type
      message.text = text
      setTimeout(() => { message.type = ''; message.text = '' }, 3000)
    }
    
    const handleFileSelected = (file) => { selectedFile.value = file }
    const handleFileUploaded = () => { 
      loadFileList()
      setTimeout(() => checkIndexStatus(), 500)
    }
    const handleFileDeleted = () => {
      loadFileList()
      if (selectedFile.value && !files.value.find(f => f.filename === selectedFile.value.filename)) {
        selectedFile.value = null
      }
    }
    
    const handleFileProcess = async (filename) => {
      if (!filename) {
        showMessage('error', '请先选择文件')
        return
      }
      try {
        showMessage('loading', '正在处理文件，这可能需要几分钟...')
        const response = await fetch('/process/file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename, build_index: true })
        })
        const result = await response.json()
        if (response.ok) {
          const indexBuilt = result.processing_summary?.index_info?.index_built
          if (indexBuilt) {
            showMessage('success', '✅ 文件处理完成！索引已构建，可以开始问答了。')
            // 自动获取快速概况
            setTimeout(() => {
              if (typeof loadQuickOverview === 'function') {
                loadQuickOverview()
              }
            }, 500)
          } else {
            showMessage('success', '⚠️ 文件处理完成，但索引构建失败，请检查日志。')
          }
          processStatus.value = result
          
          // 通知FilePreviewCard组件更新文件状态
          window.dispatchEvent(new CustomEvent('file-processing-complete', {
            detail: { filename: filename }
          }))
          
          chatMessages.value.push({
            type: 'assistant',
            content: `✅ 文件 "${filename}" 处理完成！\n\n- 页数: ${result.processing_summary?.document_info?.page_count || 'N/A'}\n- 表格数: ${result.processing_summary?.table_info?.total_tables || 'N/A'}\n- 索引状态: ${indexBuilt ? '✅ 已构建' : '❌ 未构建'}\n\n现在可以开始提问了！`,
            timestamp: new Date()
          })
        } else {
          showMessage('error', result.detail || '处理失败')
          // 处理失败时，清除处理中状态
          window.dispatchEvent(new CustomEvent('file-processing-failed', {
            detail: { filename: filename }
          }))
        }
      } catch (error) {
        console.error('处理文件错误:', error)
        showMessage('error', `处理失败: ${error.message}`)
        // 处理失败时，清除处理中状态
        window.dispatchEvent(new CustomEvent('file-processing-failed', {
          detail: { filename: filename }
        }))
      }
    }
    
    const handleFileProcessMultiple = async (filenames) => {
      if (!filenames || filenames.length === 0) {
        showMessage('error', '请先选择要处理的文件')
        return
      }
      try {
        showMessage('loading', `正在处理 ${filenames.length} 个文件，这可能需要几分钟...`)
        const response = await fetch('/process/files', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filenames, build_index: true })
        })
        const result = await response.json()
        if (response.ok) {
          const indexBuilt = result.processing_summary?.index_info?.index_built
          const successCount = result.success_count || 0
          const totalCount = result.total_files || filenames.length
          const errorCount = result.error_count || 0
          
          if (indexBuilt) {
            showMessage('success', `✅ ${successCount}/${totalCount} 个文件处理完成！索引已构建，可以开始问答了。`)
            // 自动获取快速概况
            setTimeout(() => {
              if (typeof loadQuickOverview === 'function') {
                loadQuickOverview()
              }
            }, 500)
          } else {
            showMessage('warning', `⚠️ ${successCount}/${totalCount} 个文件处理完成，但索引构建失败，请检查日志。`)
          }
          
          processStatus.value = result
          
          // 显示处理结果摘要
          let summary = `✅ 批量处理完成！\n\n`
          summary += `- 成功: ${successCount}/${totalCount} 个文件`
          if (errorCount > 0) {
            summary += `，失败: ${errorCount} 个文件`
          }
          summary += `\n`
          
          if (result.processing_summary?.document_info) {
            const pageCount = result.processing_summary.document_info.page_count || 0
            if (pageCount > 0) {
              summary += `- 总页数/工作表数: ${pageCount}\n`
            }
            const tableCount = result.processing_summary.table_info?.total_tables || 0
            if (tableCount > 0) {
              summary += `- 总表格数: ${tableCount}\n`
            }
          }
          summary += `- 索引状态: ${indexBuilt ? '✅ 已构建' : '❌ 未构建'}\n\n`
          summary += `现在可以开始提问了！`
          
          chatMessages.value.push({
            type: 'assistant',
            content: summary,
            timestamp: new Date()
          })
          
          // 显示失败的文件（如果有）
          if (result.failed_files && result.failed_files.length > 0) {
            chatMessages.value.push({
              type: 'assistant',
              content: `❌ 以下文件处理失败：\n${result.failed_files.map(f => `- ${f.filename}: ${f.error || f.message || '未知错误'}`).join('\n')}`,
              timestamp: new Date()
            })
            // 通知FilePreviewCard组件清除失败文件的处理中状态
            result.failed_files.forEach(failedFile => {
              window.dispatchEvent(new CustomEvent('file-processing-failed', {
                detail: { filename: failedFile.filename }
              }))
            })
          }
          
          // 显示成功的文件详情（如果有）
          if (result.file_results && result.file_results.length > 0) {
            const successFiles = result.file_results.filter(r => r.status === 'success')
            if (successFiles.length > 0 && successFiles.length <= 5) {
              // 只显示前5个成功文件的详情
              const filesDetail = successFiles.map(f => {
                const summary = f.summary || {}
                return `- ${f.filename}: ${summary.page_count || 0}页, ${summary.table_count || 0}个表格`
              }).join('\n')
              chatMessages.value.push({
                type: 'assistant',
                content: `📋 处理成功的文件：\n${filesDetail}`,
                timestamp: new Date()
              })
            }
            
            // 通知FilePreviewCard组件更新文件状态
            const successFilenames = successFiles.map(f => f.filename)
            // 通过emit事件通知子组件
            if (successFilenames.length > 0) {
              // 触发自定义事件，让FilePreviewCard监听
              window.dispatchEvent(new CustomEvent('files-processing-complete', {
                detail: { filenames: successFilenames }
              }))
            }
          }
        } else {
          showMessage('error', result.detail || '批量处理失败')
          // 批量处理失败时，清除所有文件的处理中状态
          filenames.forEach(filename => {
            window.dispatchEvent(new CustomEvent('file-processing-failed', {
              detail: { filename: filename }
            }))
          })
        }
      } catch (error) {
        console.error('批量处理文件错误:', error)
        showMessage('error', `批量处理失败: ${error.message}`)
        // 批量处理失败时，清除所有文件的处理中状态
        filenames.forEach(filename => {
          window.dispatchEvent(new CustomEvent('file-processing-failed', {
            detail: { filename: filename }
          }))
        })
      }
    }
    
    const handleSendMessage = async (question) => {
      // 统一使用 Agent 查询接口，让 Agent 自动选择工具
      return await handleAgentQuery(question)
    }
    
    const handleAgentQuery = async (question) => {
      chatMessages.value.push({ type: 'user', content: question, timestamp: new Date() })
      queryLoading.value = true
      
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000) // 10分钟超时
        
        const response = await fetch('/agent/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question }),
          signal: controller.signal
        })
        
        clearTimeout(timeoutId)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
          const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
          chatMessages.value.push({ 
            type: 'assistant', 
            content: `❌ Agent查询失败: ${errorMsg}\n\n提示：请确保已上传并处理文档，索引已构建完成。`, 
            timestamp: new Date() 
          })
          showMessage('error', errorMsg)
          return
        }
        
        const result = await response.json()
        
        if (result.status === 'error') {
          const errorMsg = result.error || result.detail || '查询失败'
          chatMessages.value.push({ 
            type: 'assistant', 
            content: `❌ ${errorMsg}\n\n提示：请确保已上传并处理文档，索引已构建完成。`, 
            timestamp: new Date() 
          })
          showMessage('error', errorMsg)
          return
        }
        
        // 处理成功响应
        if (result.status === 'success') {
          // 添加文本回答
          if (result.answer) {
            chatMessages.value.push({ 
              type: 'assistant', 
              content: result.answer, 
              sources: result.sources || [], 
              timestamp: new Date() 
            })
          }
          
          // 处理可视化
          if (result.visualization && result.visualization.has_visualization) {
            if (result.visualization.type === 'financial_tables' && Array.isArray(result.visualization.tables)) {
              result.visualization.tables
                .filter(table => table)
                .forEach((table, idx) => {
                  visualizationCards.value.push({
                    id: `${Date.now().toString()}-${idx}`,
                    question: table.title || '财务表格',
                    timestamp: new Date(),
                    data: {
                      has_visualization: true,
                      type: 'financial_table',
                      table
                    },
                    type: 'financial_table'
                  })
                })
            } else {
              const cardId = Date.now().toString()
              visualizationCards.value.push({
                id: cardId,
                question: question,
                timestamp: new Date(),
                data: result.visualization,
                type: 'chart'
              })
            }
            visualizationLoading.value = false
          }
          
          // 显示工具调用信息（可选）
          const toolCallsCount = result.tool_calls?.length || 0
          if (toolCallsCount > 0) {
            const toolNames = result.tool_calls.map(tc => tc.tool_name).join('、')
            showMessage('success', `✅ Agent分析完成，使用了 ${toolCallsCount} 个工具：${toolNames}`)
          }
        } else {
          chatMessages.value.push({ 
            type: 'assistant', 
            content: '⚠️ 未收到有效回答，请重试。', 
            timestamp: new Date() 
          })
        }
      } catch (error) {
        console.error('Agent查询错误:', error)
        
        let errorMsg = '网络错误或请求超时'
        if (error.name === 'AbortError') {
          errorMsg = '请求超时（超过10分钟），Agent查询可能需要更长时间，请稍后重试'
        } else if (error.message) {
          errorMsg = error.message
        }
        
        chatMessages.value.push({ 
          type: 'assistant', 
          content: `❌ Agent查询失败: ${errorMsg}\n\n可能的原因：\n1. 网络连接问题\n2. 服务器未响应\n3. 索引未构建完成\n\n请检查网络连接，确保已处理文档。`, 
          timestamp: new Date() 
        })
        showMessage('error', errorMsg)
      } finally {
        queryLoading.value = false
      }
    }

    const highlightInsightText = (text = '') => {
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
      metricKeywords.forEach((keyword) => {
        result = result.replaceAll(keyword, `<span class="insight-key">${keyword}</span>`)
      })
      result = result.replace(/(-?\d{4,}(?:\.\d+)?%?|-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|-?\d{1,3}(?:\.\d+)?%?)(万亿元|亿元|万元|元)?/g, (match) => {
        return `<span class="insight-num">${match}</span>`
      })
      result = result.replace(/(增长|上升|提升|扩大|改善|增加|上行|回升)/g, '<span class="insight-up">$1</span>')
      result = result.replace(/(下降|下滑|收缩|减少|下行|走弱|压降|回落)/g, '<span class="insight-down">$1</span>')
      return result
    }

    const formatSummaryList = (summary = '') => {
      const lines = String(summary).split(/\n+/).map(line => line.trim()).filter(Boolean)
      if (lines.length === 0) return summary
      const items = lines.map((line) => {
        const parts = line.split('：')
        if (parts.length >= 2) {
          const label = parts.shift()
          const content = parts.join('：')
          return `<li><span class="insight-label">${label}</span>：${highlightInsightText(content)}</li>`
        }
        return `<li>${highlightInsightText(line)}</li>`
      })
      return `<ul class="summary-list">${items.join('')}</ul>`
    }

    const formatFinancialReviewSummary = (summary = '') => {
      const text = String(summary).replace(/\n+/g, ' ').trim()
      if (!text) return ''
      const labelRegex = /(资产负债表(?:数据)?|利润表(?:数据)?|现金流量表(?:数据)?|综合判断|总体判断|总体评价|综合评价)[：:\s]*/g
      const matches = Array.from(text.matchAll(labelRegex))
      if (matches.length === 0) {
        return formatSummaryList(summary)
      }
      
      const sections = {}
      const normalizeLabel = (label = '') => {
        if (label.includes('资产负债表')) return '资产负债表'
        if (label.includes('利润表')) return '利润表'
        if (label.includes('现金流量表')) return '现金流量表'
        return '综合判断'
      }
      
      matches.forEach((match, idx) => {
        const rawLabel = match[1] || ''
        const start = (match.index || 0) + match[0].length
        const end = idx + 1 < matches.length ? (matches[idx + 1].index || text.length) : text.length
        const content = text.slice(start, end).trim()
        const label = normalizeLabel(rawLabel)
        if (content) {
          sections[label] = content
        }
      })
      
      const orderedLabels = ['资产负债表', '利润表', '现金流量表', '综合判断']
      const items = orderedLabels
        .filter(label => sections[label])
        .map(label => (
          `<div class="summary-item"><span class="summary-label">${label}</span><div class="summary-text">${highlightInsightText(sections[label])}</div></div>`
        ))
      
      if (items.length === 0) {
        return formatSummaryList(summary)
      }
      
      return `<div class="summary-block">${items.join('')}</div>`
    }

    const extractBusinessGuidancePayload = (result) => {
      if (!result || typeof result !== 'object') return null
      const structured = result.structured_response || {}
      if (structured.business_guidance) return structured.business_guidance
      const toolCall = Array.isArray(result.tool_calls)
        ? result.tool_calls.find(tc => tc.tool_name === 'generate_business_guidance')
        : null
      if (!toolCall) return null
      let output = toolCall.tool_output || toolCall.output || null
      if (output && output.raw_output) output = output.raw_output
      if (typeof output === 'string') {
        try {
          output = JSON.parse(output)
        } catch (e) {
          return null
        }
      }
      return output && typeof output === 'object' ? output : null
    }

    const formatBusinessGuidanceSummary = (payload = {}) => {
      if (!payload || typeof payload !== 'object') return ''
      const guidancePeriod = payload.guidance_period || payload.guidancePeriod
      const expectedPerformance = payload.expected_performance || payload.expectedPerformance
      const parentProfit = payload.parent_net_profit_range || payload.parentNetProfitRange
      const parentProfitGrowth = payload.parent_net_profit_growth_range || payload.parentNetProfitGrowthRange
      const nonRecurringProfit = payload.non_recurring_profit_range || payload.nonRecurringProfitRange
      const epsRange = payload.eps_range || payload.epsRange
      const revenueRange = payload.revenue_range || payload.revenueRange
      const keyMetrics = payload.key_metrics || payload.keyMetrics || []
      const businessGuidance = payload.business_specific_guidance || payload.businessSpecificGuidance || []
      const riskWarnings = payload.risk_warnings || payload.riskWarnings || []

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
      const watchList = metricParts.length ? metricParts : (Array.isArray(keyMetrics) ? keyMetrics : [])
      const watchText = watchList.length ? watchList.join('；') : '年报未明确量化口径'

      const howText = Array.isArray(businessGuidance) && businessGuidance.length
        ? businessGuidance.join('；')
        : '未明确'
      const riskText = Array.isArray(riskWarnings) && riskWarnings.length
        ? riskWarnings.join('；')
        : '未明确'

      const items = [
        { label: '① 经营目标方向', text: whatText },
        { label: '② 核心指标锚点', text: watchText },
        { label: '③ 关键执行路径', text: howText },
        { label: '④ 不确定性与边界', text: riskText }
      ].map(item => (
        `<div class="summary-item"><span class="summary-label">${item.label}</span><div class="summary-text">${highlightInsightText(item.text)}</div></div>`
      ))

      if (!items.length) {
        return ''
      }
      return `<div class="summary-block">${items.join('')}</div>`
    }

    const formatTableInsight = (insight = '') => {
      const text = String(insight)
      if (!text) return ''
      const parts = text.split('：')
      if (parts.length >= 2) {
        const label = parts.shift()
        const content = parts.join('：')
        return `<span class="insight-label">${label}</span>：${highlightInsightText(content)}`
      }
      return highlightInsightText(text)
    }

    const hiddenBusinessMetricTables = ['零售银行业务指标', '对公银行业务指标', '同业与资金业务指标']
    const isHiddenBusinessMetricTable = (title = '') => hiddenBusinessMetricTables
      .some(item => String(title || '').includes(item))

    const stripMarkdownText = (text = '') => String(text)
      .replace(/[`*_]+/g, '')
      .replace(/\[[^\]]+\]\([^)]+\)/g, '')
      .replace(/<[^>]+>/g, '')
      .trim()

    const sanitizeCardTitle = (title = '') => stripMarkdownText(title)
      .replace(/^#{1,6}\s*/g, '')
      .replace(/^[一二三四五六七八九十]+[、.]\s*/g, '')
      .replace(/^[\d]+\.\s*/g, '')
      .replace(/^【|】$/g, '')
      .replace(/\s{2,}/g, ' ')
      .trim()

    const extractKeyMetricsTable = (text = '') => {
      if (!text) return null
      const lines = String(text).split(/\r?\n/).map(line => line.trim()).filter(Boolean)
      const keywordList = ['关键业务指标汇总', '关键业务指标', '关键指标']
      const startIndex = lines.findIndex(line => keywordList.some(keyword => line.includes(keyword)))
      if (startIndex < 0) return null

      const titleLine = lines[startIndex]
      const title = keywordList.find(keyword => titleLine.includes(keyword)) || '关键业务指标'

      const tableLines = []
      for (let i = startIndex + 1; i < lines.length; i += 1) {
        const line = lines[i]
        if (/^[#]|^[🧾📊📈🔍⚠️🎯🏦]/.test(line)) break
        tableLines.push(line)
      }

      if (!tableLines.length) return null

      const rows = []
      tableLines.forEach((line) => {
        const cleanedLine = stripMarkdownText(line)
        if (cleanedLine.includes('指标') && cleanedLine.includes('同比')) return
        if (line.includes('|')) {
          const pipeCells = line.split('|').map(cell => stripMarkdownText(cell)).filter(cell => cell)
          if (pipeCells.length >= 4 && !pipeCells.every(cell => /^-+$/.test(cell))) {
            rows.push(pipeCells.slice(0, 5))
          }
          return
        }
        const byGap = line.split(/\t+| {2,}/).filter(Boolean)
        if (byGap.length >= 5) {
          rows.push(byGap.slice(0, 5).map(cell => stripMarkdownText(cell)))
          return
        }
        const tokens = line.split(/\s+/).filter(Boolean)
        const yoyIndex = tokens.findIndex(token => token.includes('%') || token.includes('百分点'))
        if (yoyIndex >= 3) {
          const metric = stripMarkdownText(tokens.slice(0, yoyIndex - 2).join(''))
          const current = tokens[yoyIndex - 2]
          const previous = tokens[yoyIndex - 1]
          const yoy = tokens[yoyIndex]
          const meaning = stripMarkdownText(tokens.slice(yoyIndex + 1).join(''))
          if (metric && current && previous && yoy && meaning) {
            rows.push([metric, current, previous, yoy, meaning])
          }
        }
      })

      if (!rows.length) return null

      return {
        title: sanitizeCardTitle(title),
        headers: ['指标', '2024年', '2023年', '同比变动', '业务意义'],
        rows: rows.map(row => row.map(cell => stripMarkdownText(cell)))
      }
    }

    const normalizeToolOutput = (toolOutput) => {
      if (toolOutput && typeof toolOutput === 'object' && toolOutput.raw_output !== undefined) {
        return toolOutput.raw_output
      }
      return toolOutput
    }

    const extractBusinessHighlightsPayload = (result) => {
      const structured = result?.structured_response || {}
      if (structured.business_highlights) return structured.business_highlights
      if (structured.businessHighlights) return structured.businessHighlights
      const toolCalls = Array.isArray(result?.tool_calls) ? result.tool_calls : []
      const toolCall = toolCalls.find(tc => tc?.tool_name === 'generate_business_highlights')
      const output = normalizeToolOutput(toolCall?.tool_output)
      return output && typeof output === 'object' ? output : null
    }

    const buildBusinessHighlightsInsightTable = (payload) => {
      const report = payload?.business_performance_report || payload?.businessPerformanceReport || {}
      const segmentInsights = Array.isArray(report.segment_insights)
        ? report.segment_insights
        : []
      if (!segmentInsights.length) return null
      const toText = (value) => {
        if (Array.isArray(value)) return value.filter(Boolean).join('；')
        return value ? String(value) : '—'
      }
      const rows = segmentInsights.map(insight => ([
        insight.segment_name || insight.segment_id || '—',
        insight.headline || '—',
        toText(insight.contribution),
        toText(insight.drivers),
        toText(insight.strategy_link),
        toText(insight.risks_and_watchlist)
      ]))
      return {
        title: sanitizeCardTitle('业务亮点洞察（分业务）'),
        headers: ['业务板块', '一句话结论', '贡献', '驱动', '战略联动', '风险关注'],
        rows
      }
    }

    const appendBusinessHighlightsTables = (payload) => {
      const segmentTables = Array.isArray(payload?.segment_tables) ? payload.segment_tables : []
      segmentTables.forEach((segment, idx) => {
        const table = segment?.table
        if (!table) return
        if (isHiddenBusinessMetricTable(table.title || segment.segment_name)) return
        const normalizedTable = {
          ...table,
          insight_html: formatTableInsight(table.insight)
        }
        visualizationCards.value.push({
          id: `${Date.now().toString()}-biz-${idx}`,
          question: sanitizeCardTitle(table.title || `${segment.segment_name || segment.segment_id || '业务'}指标`),
          timestamp: new Date(),
          data: {
            has_visualization: true,
            type: 'financial_table',
            table: normalizedTable
          },
          type: 'financial_table'
        })
      })
    }

    const isMeaningfulTable = (table) => {
      const rows = table?.rows || []
      if (!rows.length) return false
      return rows.some(row => row?.some(cell => {
        const text = String(cell ?? '').trim()
        return text && !['/', '-', '—', '暂无'].includes(text)
      }))
    }

    const ensureKeyMetricsSummaryTable = (payload, fallbackText = '') => {
      if (!payload || typeof payload !== 'object') return
      const summaryTable = payload.key_metrics_summary
      const preferredTable = summaryTable && isMeaningfulTable(summaryTable)
        ? summaryTable
        : extractKeyMetricsTable(fallbackText)
      if (!preferredTable || !preferredTable.rows) return
      const title = sanitizeCardTitle(preferredTable.title || '关键业务指标汇总')
      if (isHiddenBusinessMetricTable(title)) return
      const exists = visualizationCards.value.some(card => {
        const cardTitle = card?.data?.table?.title || card?.question || ''
        return card.type === 'financial_table' && cardTitle === title
      })
      if (exists) return
      visualizationCards.value.push({
        id: `${Date.now().toString()}-biz-key-metrics-summary`,
        question: title,
        timestamp: new Date(),
        data: {
          has_visualization: true,
          type: 'financial_table',
          table: preferredTable
        },
        type: 'financial_table'
      })
    }

    const handleQuickAnalysis = async ({ sectionName, companyName, year, question, typeName }) => {
      if (!sectionName) {
        showMessage('error', '缺少分析类型，无法生成快捷分析')
        return
      }
      
      // 如果缺少公司/年份，回退到 Agent 查询，保证按钮可用
      if (!companyName || !year) {
        const fallbackQuestion = question || `请生成${typeName || '财务点评'}分析`
        return await handleAgentQuery(fallbackQuestion)
      }
      
      chatMessages.value.push({ type: 'user', content: question, timestamp: new Date() })
      queryLoading.value = true
      
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000) // 10分钟超时
        
        const response = await fetch('/agent/generate-section', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            section_name: sectionName,
            company_name: companyName,
            year
          }),
          signal: controller.signal
        })
        
        clearTimeout(timeoutId)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
          const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
          chatMessages.value.push({
            type: 'assistant',
            content: `❌ ${typeName || sectionName}生成失败: ${errorMsg}`,
            timestamp: new Date()
          })
          showMessage('error', errorMsg)
          return
        }
        
        const result = await response.json()
        
        if (result.status === 'error') {
          const errorMsg = result.error || result.detail || '查询失败'
          chatMessages.value.push({
            type: 'assistant',
            content: `❌ ${typeName || sectionName}生成失败: ${errorMsg}`,
            timestamp: new Date()
          })
          showMessage('error', errorMsg)
          return
        }
        
        if (result.status === 'success') {
          let answerText = result.content || ''
          const visualization = result.visualization
          const getTableSourceLabel = (title = '') => {
            if (title.includes('资产') || title.includes('负债')) return '资产负债表'
            if (title.includes('营业收入') || title.includes('营业支出') || title.includes('收入') || title.includes('支出') || title.includes('利润')) return '利润表'
            if (title.includes('现金流')) return '现金流量表'
            return '财务报表'
          }
          const formatTableTitle = (title) => {
            const base = title || (sectionName === 'business_highlights' ? '业务板块指标' : '财务表格')
            if (sectionName === 'business_highlights') {
              return base
            }
            return `${base}（${getTableSourceLabel(base)}）`
          }
          
          if (sectionName === 'financial_review') {
            const structured = result.structured_response || {}
            const financialReview = structured.summary
              ? structured
              : (structured.financial_review || structured.financialReview || null)
            const summary = financialReview?.summary
            const tables = financialReview?.visualization_tables
            const toolSummary = result.tool_calls?.find(tc => tc.tool_name === 'generate_financial_review')
              ?.tool_output?.summary
            
            if (summary) {
              answerText = formatFinancialReviewSummary(summary)
            } else if (toolSummary) {
              answerText = formatFinancialReviewSummary(toolSummary)
            }
            
            if (tables) {
              const tableList = [
                tables.balance_sheet_assets,
                tables.balance_sheet_liabilities,
                tables.income_statement_revenue,
                tables.income_statement_expense,
                tables.cash_flow
              ].filter(Boolean)
              
              tableList.forEach((table, idx) => {
                const normalizedTable = {
                  ...table,
                  insight_html: formatTableInsight(table.insight)
                }
                visualizationCards.value.push({
                  id: `${Date.now().toString()}-${idx}`,
                  question: formatTableTitle(table.title),
                  timestamp: new Date(),
                  data: {
                    has_visualization: true,
                    type: 'financial_table',
                    table: normalizedTable
                  },
                  type: 'financial_table'
                })
              })
            }
          }

          if (sectionName === 'business_guidance') {
            const payload = extractBusinessGuidancePayload(result)
            if (payload) {
              const formatted = formatBusinessGuidanceSummary(payload)
              if (formatted) {
                answerText = formatted
              }
            }
          }

          if (sectionName === 'business_highlights') {
            const businessPayload = extractBusinessHighlightsPayload(result)
            if (businessPayload) {
              appendBusinessHighlightsTables(businessPayload)
              ensureKeyMetricsSummaryTable(businessPayload, answerText)
              const insightTable = buildBusinessHighlightsInsightTable(businessPayload)
              if (insightTable && !isHiddenBusinessMetricTable(insightTable.title)) {
                visualizationCards.value.push({
                  id: `${Date.now().toString()}-biz-insight-table`,
                  question: insightTable.title,
                  timestamp: new Date(),
                  data: {
                    has_visualization: true,
                    type: 'financial_table',
                    table: insightTable
                  },
                  type: 'financial_table'
                })
              }
            } else {
              const keyMetricsTable = extractKeyMetricsTable(answerText)
              if (keyMetricsTable && !isHiddenBusinessMetricTable(keyMetricsTable.title)) {
                visualizationCards.value.push({
                  id: `${Date.now().toString()}-biz-key-metrics`,
                  question: keyMetricsTable.title,
                  timestamp: new Date(),
                  data: {
                    has_visualization: true,
                    type: 'financial_table',
                    table: keyMetricsTable
                  },
                  type: 'financial_table'
                })
              }
            }

            if (answerText && !visualizationCards.value.some(card => card.source === 'text_viz')) {
              try {
                const vizResponse = await fetch('/agent/visualize-text', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    query: question || '业务亮点分析',
                    answer: answerText,
                    max_views: 3
                  })
                })
                if (vizResponse.ok) {
                  const textViz = await vizResponse.json()
                  if (textViz && textViz.visualizations && Array.isArray(textViz.visualizations)) {
                    textViz.visualizations.forEach((viz, idx) => {
                      if (!viz || !viz.has_visualization) return
                      visualizationCards.value.push({
                        id: `${Date.now().toString()}-biz-text-viz-${idx}`,
                        question: sanitizeCardTitle(viz.display_title || viz.query || question || '业务亮点分析可视化'),
                        timestamp: new Date(),
                        data: viz,
                        type: 'chart',
                        source: 'text_viz'
                      })
                    })
                  } else if (textViz && textViz.has_visualization) {
                    visualizationCards.value.push({
                      id: `${Date.now().toString()}-biz-text-viz`,
                      question: sanitizeCardTitle(textViz.display_title || textViz.query || question || '业务亮点分析可视化'),
                      timestamp: new Date(),
                      data: textViz,
                      type: 'chart',
                      source: 'text_viz'
                    })
                  }
                } else {
                  console.warn('⚠️ 业务亮点文本可视化请求失败:', vizResponse.status)
                }
              } catch (error) {
                console.warn('⚠️ 业务亮点文本可视化请求异常:', error)
              }
            }
          }
          
          if (visualization && visualization.type === 'financial_tables' && Array.isArray(visualization.tables)) {
            visualization.tables
              .filter(table => table)
              .forEach((table, idx) => {
                const normalizedTable = {
                  ...table,
                  insight_html: formatTableInsight(table.insight)
                }
                visualizationCards.value.push({
                  id: `${Date.now().toString()}-${idx}`,
                  question: formatTableTitle(table.title),
                  timestamp: new Date(),
                  data: {
                    has_visualization: true,
                    type: 'financial_table',
                    table: normalizedTable
                  },
                  type: 'financial_table'
                })
              })
          } else if (visualization && visualization.has_visualization) {
            visualizationCards.value.push({
              id: Date.now().toString(),
              question: question,
              timestamp: new Date(),
              data: visualization,
              type: 'chart'
            })
          }
          
          const answerHeader = `<div class="summary-title">以下是${typeName || sectionName}：</div>`
          if (answerText) {
            chatMessages.value.push({
              type: 'assistant',
              content: `${answerHeader}\n\n${answerText}`,
              timestamp: new Date()
            })
          } else {
            chatMessages.value.push({
              type: 'assistant',
              content: answerHeader,
              timestamp: new Date()
            })
          }
        }
      } catch (error) {
        let errorMsg = '网络错误或请求超时'
        if (error.name === 'AbortError') {
          errorMsg = '请求超时（超过10分钟），请稍后重试'
        } else if (error.message) {
          errorMsg = error.message
        }
        chatMessages.value.push({
          type: 'assistant',
          content: `❌ ${typeName || sectionName}生成失败: ${errorMsg}`,
          timestamp: new Date()
        })
        showMessage('error', errorMsg)
      } finally {
        queryLoading.value = false
      }
    }
    
    // handleAgentQuery 已经在上面定义，用于普通查询
    // 这个函数保留用于跳转到Agent分析页面的场景（如果需要）
    const handleAgentQueryPage = async (question) => {
      // 切换到Agent分析页面
      currentPage.value = 'agent-analysis'
      
      // 等待页面切换完成后再执行查询
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // 触发Agent分析页面的查询
      // 这个函数会被AgentAnalysisPage组件调用
      return await executeAgentQuery(question)
    }
    
    const executeAgentQuery = async (question) => {
      queryLoading.value = true
      
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000)
        
        const response = await fetch('/agent/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question }),
          signal: controller.signal
        })
        
        clearTimeout(timeoutId)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
          const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
          showMessage('error', errorMsg)
          return {
            status: 'error',
            error: errorMsg
          }
        }
        
        const result = await response.json()
        
        // 添加调试日志
        console.log('🔍 [main.js] Agent查询响应:', {
          status: result.status,
          hasAnswer: !!result.answer,
          answerLength: result.answer?.length || 0,
          toolCallsCount: result.tool_calls?.length || 0,
          hasVisualization: !!result.visualization,
          hasStructuredResponse: !!result.structured_response,
          performance: result.performance
        })
        
        if (result.status === 'success') {
          const toolCallsCount = result.tool_calls?.length || 0
          const totalTime = result.performance?.total_seconds || 0
          showMessage('success', `Agent分析完成！执行了 ${toolCallsCount} 个工具调用，耗时 ${totalTime.toFixed(1)} 秒`)
        } else {
          const errorMsg = result.error || result.detail || '查询失败'
          showMessage('error', errorMsg)
        }
        
        return result
      } catch (error) {
        console.error('Agent查询错误:', error)
        
        let errorMsg = '网络错误或请求超时'
        if (error.name === 'AbortError') {
          errorMsg = '请求超时（超过10分钟），Agent查询可能需要更长时间，请稍后重试或使用普通查询模式'
        } else if (error.message) {
          errorMsg = error.message
        }
        
        showMessage('error', errorMsg)
        return {
          status: 'error',
          error: errorMsg
        }
      } finally {
        queryLoading.value = false
      }
    }
    
    const goToAgentAnalysis = () => {
      currentPage.value = 'agent-analysis'
    }
    
    const goBackToMain = () => {
      currentPage.value = 'main'
    }

    const stripDupontAssetsNodes = (analysis) => {
      if (!analysis || !analysis.tree_structure) return

      const stripNodes = (node) => {
        if (!node || !Array.isArray(node.children)) return
        node.children = node.children.filter(child => (
          child?.id !== 'current_assets' && child?.id !== 'non_current_assets'
        ))
        node.children.forEach(stripNodes)
      }

      stripNodes(analysis.tree_structure)
    }
    
    const handleDupontAnalysis = async () => {
      chatMessages.value.push({ 
        type: 'user', 
        content: '📊 请求杜邦分析', 
        timestamp: new Date() 
      })
      queryLoading.value = true
      dupontLoading.value = true
      
      const progressIndex = chatMessages.value.length
      chatMessages.value.push({ 
        type: 'assistant', 
        content: '📊 正在生成杜邦分析，这可能需要30秒-2分钟，请耐心等待...\n\n正在执行：\n- 提取财务数据\n- 计算杜邦指标\n- 生成分析报告', 
        timestamp: new Date(),
        isProgress: true
      })
      
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 15 * 60 * 1000) // 15分钟超时
        
        const response = await fetch('/query/dupont-analysis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: null,  // 自动提取
            year: null,  // 自动提取
            filename: selectedFile.value?.filename || null  // 传递选中的文件名
          }),
          signal: controller.signal
        })
        
        clearTimeout(timeoutId)
        
        const progressMsgIndex = chatMessages.value.findIndex(msg => msg.isProgress)
        if (progressMsgIndex >= 0) {
          chatMessages.value.splice(progressMsgIndex, 1)
        }
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
          const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
          chatMessages.value.push({ 
            type: 'assistant', 
            content: `❌ 杜邦分析失败: ${errorMsg}\n\n提示：请确保已上传并处理文档，索引已构建完成。`, 
            timestamp: new Date() 
          })
          showMessage('error', errorMsg)
          dupontLoading.value = false
          return
        }
        
        const result = await response.json()
        
        if (result.status === 'success' && result.analysis) {
          // 保存杜邦分析数据，转换为组件需要的格式
          // 注意：杜邦分析按钮生成的视图只设置dupontData，不添加到visualizationCards
          const analysis = result.analysis
          stripDupontAssetsNodes(analysis)
          const level1 = analysis.level1 || {}
          dupontData.value = {
            roe: level1.roe?.formatted_value || level1.roe?.value || '—',
            roa: level1.roa?.formatted_value || level1.roa?.value || '—',
            equity_multiplier: level1.equity_multiplier?.formatted_value || level1.equity_multiplier?.value || '—',
            // 保存完整数据以便后续使用
            full_data: analysis,
            metrics_json: analysis.metrics_json || null
          }
          // 不添加到visualizationCards，因为杜邦分析按钮生成的视图应该通过dupontData显示
          dupontLoading.value = false
          
          // 生成友好的显示文本
          const roe = level1.roe?.formatted_value || 'N/A'
          const roa = level1.roa?.formatted_value || 'N/A'
          const equityMultiplier = level1.equity_multiplier?.formatted_value || 'N/A'
          
          let content = `✅ 杜邦分析生成成功！\n\n`
          content += `**公司**: ${result.company_name || '未知'}\n`
          content += `**年份**: ${result.year || '未知'}\n\n`
          content += `**核心指标**:\n`
          content += `- 净资产收益率(ROE): ${roe}\n`
          content += `- 资产净利率(ROA): ${roa}\n`
          content += `- 权益乘数: ${equityMultiplier}\n\n`
          
          if (analysis.insights && analysis.insights.length > 0) {
            content += `**分析洞察**:\n`
            analysis.insights.forEach(insight => {
              content += `- ${insight}\n`
            })
            content += `\n`
          }
          
          if (analysis.strengths && analysis.strengths.length > 0) {
            content += `**优势**:\n`
            analysis.strengths.forEach(strength => {
              content += `- ✅ ${strength}\n`
            })
            content += `\n`
          }
          
          if (analysis.weaknesses && analysis.weaknesses.length > 0) {
            content += `**劣势**:\n`
            analysis.weaknesses.forEach(weakness => {
              content += `- ⚠️ ${weakness}\n`
            })
            content += `\n`
          }
          
          if (analysis.recommendations && analysis.recommendations.length > 0) {
            content += `**改进建议**:\n`
            analysis.recommendations.forEach(rec => {
              content += `- 💡 ${rec}\n`
            })
          }
          
          chatMessages.value.push({ 
            type: 'assistant', 
            content: content, 
            timestamp: new Date() 
          })
          
          showMessage('success', '杜邦分析生成成功！结果已显示在右侧面板。')
        } else {
          const errorMsg = result.error || result.detail || '分析失败'
          chatMessages.value.push({ 
            type: 'assistant', 
            content: `❌ 杜邦分析失败: ${errorMsg}`, 
            timestamp: new Date() 
          })
          showMessage('error', errorMsg)
          dupontLoading.value = false
        }
      } catch (error) {
        console.error('杜邦分析错误:', error)
        
        const progressMsgIndex = chatMessages.value.findIndex(msg => msg.isProgress)
        if (progressMsgIndex >= 0) {
          chatMessages.value.splice(progressMsgIndex, 1)
        }
        
        let errorMsg = '网络错误或请求超时'
        if (error.name === 'AbortError') {
          errorMsg = '请求超时（超过5分钟），请稍后重试'
        } else if (error.message) {
          errorMsg = error.message
        }
        
        chatMessages.value.push({ 
          type: 'assistant', 
          content: `❌ 杜邦分析失败: ${errorMsg}\n\n可能的原因：\n1. 网络连接问题\n2. 索引未构建完成\n3. 文档中缺少必要的财务数据\n\n建议：\n- 检查网络连接\n- 确保已处理文档并构建索引\n- 确保文档包含完整的财务报表数据`, 
          timestamp: new Date() 
        })
        showMessage('error', errorMsg)
        dupontLoading.value = false
      } finally {
        queryLoading.value = false
      }
    }
    
    const handleGetSuggestions = async () => {
      try {
        const response = await fetch('/query/suggestions')
        const data = await response.json()
        suggestions.value = data.suggestions || []
      } catch (error) {
        showMessage('error', `获取建议失败: ${error.message}`)
      }
    }
    
    const handleGenerateReport = async () => {
      companyOverviewLoading.value = true
      try {
        const response = await fetch('/agent/generate-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: '公司名称',
            year: '2023',
            save_to_file: false
          })
        })
        const result = await response.json()
        if (response.ok && result.status === 'success') {
          companyOverviewData.value = { company_name: result.company_name, year: result.year }
          showMessage('success', '财务概况生成成功')
        } else {
          showMessage('error', result.error || '生成失败')
        }
      } catch (error) {
        showMessage('error', `生成失败: ${error.message}`)
      } finally {
        companyOverviewLoading.value = false
      }
    }
    
    const handleGenerateSection = async (sectionName) => {
      notesAndRisksLoading.value = true
      try {
        const response = await fetch('/agent/generate-section', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            section_name: sectionName,
            company_name: '公司名称',
            year: '2023'
          })
        })
        const result = await response.json()
        if (response.ok && result.status === 'success') {
          notesAndRisksData.value = { notes: result.content, risks: '' }
          showMessage('success', '附注与风险生成成功')
        } else {
          showMessage('error', result.error || '生成失败')
        }
      } catch (error) {
        showMessage('error', `生成失败: ${error.message}`)
      } finally {
        notesAndRisksLoading.value = false
      }
    }
    
    const handleClearChat = () => {
      chatMessages.value = []
      visualizationData.value = null
      visualizationCards.value = []  // 清空所有可视化卡片
    }
    
    const handleDeleteMessage = (index) => {
      if (index >= 0 && index < chatMessages.value.length) {
        chatMessages.value.splice(index, 1)
      }
    }
    
    const loadQuickOverview = async () => {
      companyOverviewLoading.value = true
      try {
        const response = await fetch('/query/quick-overview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        const result = await response.json()
        if (response.ok && result.status === 'success') {
          quickOverviewData.value = result.overview
          showMessage('success', '✅ 财务概况已生成')
        } else {
          console.warn('快速概况生成失败:', result)
        }
      } catch (error) {
        console.error('加载快速概况失败:', error)
        // 不显示错误，静默失败
      } finally {
        companyOverviewLoading.value = false
      }
    }
    
    const checkIndexStatus = async () => {
      try {
        const response = await fetch('/process/status')
        if (!response.ok) {
          console.warn('获取处理状态失败，可能索引未初始化')
          return
        }
        const data = await response.json()
        processStatus.value = data
        
        if (data.index_status) {
          const indexBuilt = data.index_status.index_built === true || data.index_status.status === 'ready'
          if (!indexBuilt && files.value.length > 0) {
            console.log('提示：请先处理文档以构建索引')
          }
        }
      } catch (error) {
        console.warn('检查索引状态失败（这是正常的，如果索引未初始化）:', error.message)
      }
    }
    
    onMounted(() => {
      checkSystemStatus()
      loadFileList()
      checkIndexStatus()
    })
    
    return {
      currentPage, systemStatus, files, selectedFile, chatMessages, queryLoading, message,
      companyOverviewData, companyOverviewLoading, notesAndRisksData, notesAndRisksLoading,
      dupontData, dupontLoading, visualizationData, visualizationLoading, visualizationCards, processStatus, suggestions,
      quickOverviewData,
      showMessage, handleFileSelected, handleFileUploaded, handleFileDeleted, handleFileProcess, handleFileProcessMultiple,
      handleSendMessage, handleAgentQuery, executeAgentQuery, handleDupontAnalysis, handleGetSuggestions, handleQuickAnalysis,
      handleGenerateReport, handleGenerateSection, handleClearChat, checkIndexStatus, loadQuickOverview,
      handleDeleteMessage, goToAgentAnalysis, goBackToMain,
      handleRemoveVizCard: (cardId) => {
        // 删除整个卡片（包括图表、推荐说明、数据洞察等所有内容）
        console.log('🗑️ 处理删除卡片请求:', cardId);
        console.log('  删除前卡片数量:', visualizationCards.value.length);
        
        const index = visualizationCards.value.findIndex(card => card.id === cardId)
        if (index > -1) {
          const removedCard = visualizationCards.value[index];
          console.log('  找到卡片:', removedCard.question || removedCard.id);
          visualizationCards.value.splice(index, 1);
          console.log('  删除后卡片数量:', visualizationCards.value.length);
          showMessage('success', `✅ 已删除视图卡片: ${removedCard.question || '可视化卡片'}`)
        } else {
          console.warn('  未找到要删除的卡片:', cardId);
        }
        
        // 如果删除的是当前显示的图表，也清空visualizationData
        if (visualizationData.value && visualizationCards.value.length === 0) {
          visualizationData.value = null
          console.log('  所有卡片已删除，清空visualizationData');
        }
      },
      handleRemoveDupontCard: () => {
        // 删除杜邦分析卡片：从cards中删除所有杜邦分析类型的卡片，并清空dupontData
        visualizationCards.value = visualizationCards.value.filter(card => card.type !== 'dupont')
        dupontData.value = null
      },
      handleGenerateComprehensiveAnalysis: async (selectedCards) => {
        // 处理生成总分析请求
        showMessage('loading', '正在生成总分析雷达图...')
        visualizationLoading.value = true
        
        try {
          const response = await fetch('/query/comprehensive-analysis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              selected_cards: selectedCards.map(card => ({
                id: card.id,
                question: card.question,
                data: card.data
              })),
              overview_data: quickOverviewData.value,  // 传递财务概况数据
              context_filter: selectedFile.value ? {
                filename: selectedFile.value.filename
              } : null
            })
          })
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
            const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
            showMessage('error', `生成总分析失败: ${errorMsg}`)
            visualizationLoading.value = false
            // 重置选择状态
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
            return
          }
          
          const result = await response.json()
          
          if (result.status === 'success' && result.visualization) {
            // 添加总分析雷达图卡片
            const cardId = Date.now().toString()
            visualizationCards.value.push({
              id: cardId,
              question: '综合能力分析雷达图',
              timestamp: new Date(),
              data: result.visualization,
              type: 'chart'
            })
            showMessage('success', '✅ 总分析雷达图已生成')
            visualizationLoading.value = false
            
            // 重置选择状态，允许再次选择
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
          } else {
            const errorMsg = result.error || result.detail || '生成失败'
            showMessage('error', `生成总分析失败: ${errorMsg}`)
            visualizationLoading.value = false
            // 重置选择状态
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
          }
        } catch (error) {
          console.error('生成总分析错误:', error)
          const errorMsg = error.message || '网络错误或服务器无响应'
          showMessage('error', `生成总分析失败: ${errorMsg}`)
          visualizationLoading.value = false
          // 重置选择状态
          window.dispatchEvent(new CustomEvent('reset-viz-selection'))
        }
      },
      handleMetricClick: async (metricInfo) => {
        // 处理指标点击事件，生成可视化
        const { metricName, metricData } = metricInfo
        const metricValue = typeof metricData === 'object' ? metricData.value : metricData
        
        // 构建查询问题（针对不同指标优化查询）
        let question = ''
        if (metricName === 'ROE') {
          question = `请展示${metricName}（加权平均净资产收益率）的可视化图表，当前值为${metricValue}。请提供最近3-5年的ROE数据用于绘制趋势图。`
        } else if (metricName === '营业收入') {
          question = `请展示${metricName}的可视化图表，当前值为${metricValue}。请提供最近3-5年的营业收入数据，包括各年度的具体数值，用于绘制趋势图或柱状图。`
        } else if (metricName === '净利润') {
          question = `请展示${metricName}的可视化图表，当前值为${metricValue}。请提供最近3-5年的净利润数据，包括各年度的具体数值，用于绘制趋势图。`
        } else if (metricName === '资产总额') {
          question = `请展示${metricName}的可视化图表，当前值为${metricValue}。请提供最近3-5年的资产总额数据，包括各年度的具体数值，用于绘制趋势图。`
        } else {
          question = `请展示${metricName}的可视化图表，当前值为${metricValue}。请提供最近3-5年的历史数据，包括各年度的具体数值，用于绘制图表。`
        }
        
        // 显示加载提示
        showMessage('loading', `正在生成${metricName}的可视化图表...`)
        visualizationLoading.value = true
        
        try {
          // 构建context_filter：如果有选中的文件，使用文件名过滤
          const context_filter = selectedFile.value ? {
            filename: selectedFile.value.filename
          } : null
          
          const response = await fetch('/query/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              question: question, 
              enable_visualization: true,
              context_filter: context_filter
            })
          })
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
            const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}: ${response.statusText}`
            showMessage('error', `生成${metricName}可视化失败: ${errorMsg}`)
            visualizationLoading.value = false
            return
          }
          
          const result = await response.json()
          
          if (result.error) {
            const errorMsg = result.answer || result.error || '查询失败'
            showMessage('error', `生成${metricName}可视化失败: ${errorMsg}`)
            visualizationLoading.value = false
            return
          }
          
          // 如果成功生成可视化，添加到可视化卡片列表
          if (result.visualization && result.visualization.has_visualization) {
            const cardId = Date.now().toString()
            visualizationCards.value.push({
              id: cardId,
              question: `${metricName}可视化`,
              timestamp: new Date(),
              data: result.visualization,
              type: 'chart'
            })
            showMessage('success', `✅ ${metricName}可视化图表已生成`)
            visualizationLoading.value = false
          } else {
            showMessage('warning', `⚠️ 未能为${metricName}生成可视化图表`)
            visualizationLoading.value = false
          }
        } catch (error) {
          console.error('生成指标可视化错误:', error)
          const errorMsg = error.message || '网络错误或服务器无响应'
          showMessage('error', `生成${metricName}可视化失败: ${errorMsg}`)
          visualizationLoading.value = false
        }
      }
    }

          if (sectionName === 'business_highlights') {
            const keyMetricsTable = extractKeyMetricsTable(answerText)
            if (keyMetricsTable) {
              visualizationCards.value.push({
                id: `biz-key-metrics-${Date.now().toString()}`,
                question: keyMetricsTable.title,
                timestamp: new Date(),
                data: {
                  has_visualization: true,
                  type: 'financial_table',
                  table: keyMetricsTable
                },
                type: 'financial_table'
              })
            }
          }
  },
  template: `
    <div class="app-container">
      <!-- Agent分析页面 -->
      <AgentAnalysisPage 
        v-if="currentPage === 'agent-analysis'"
        :on-back="goBackToMain"
        :on-query="executeAgentQuery"
      />
      
      <!-- 主页面 -->
      <template v-else>
        <header class="app-header">
          <div class="header-content">
            <h1 class="app-title">🚀 FinDecipher</h1>
          </div>
          <div class="header-status">
            <span class="status-text">{{ systemStatus }}</span>
          </div>
        </header>
        <main class="app-main">
          <aside class="left-panel">
            <FilePreviewCard ref="filePreviewCard" :files="files" @file-selected="handleFileSelected" @file-uploaded="handleFileUploaded" @file-deleted="handleFileDeleted" @file-process="handleFileProcess" @file-process-multiple="handleFileProcessMultiple" @show-message="showMessage" @files-processed="handleFilesProcessed" />
            <CompanyOverview :data="companyOverviewData" :loading="companyOverviewLoading" :overview-data="quickOverviewData" @generate-report="handleGenerateReport" @metric-click="handleMetricClick" />
          </aside>
          <section class="middle-panel">
            <ChatArea :messages="chatMessages" :loading="queryLoading" :suggestions="suggestions" :selected-file="selectedFile" :dupont-data="dupontData" @send-message="handleSendMessage" @agent-query="handleAgentQuery" @quick-analysis="handleQuickAnalysis" @agent-analysis="goToAgentAnalysis" @dupont-analysis="handleDupontAnalysis" @get-suggestions="handleGetSuggestions" @clear-chat="handleClearChat" @delete-message="handleDeleteMessage" />
          </section>
          <aside class="right-panel">
            <VisualizationPanel :chart-data="visualizationData" :dupont-data="dupontData" :visualization-cards="visualizationCards" :loading="visualizationLoading || dupontLoading" @remove-card="handleRemoveVizCard" @remove-dupont-card="handleRemoveDupontCard" @generate-comprehensive-analysis="handleGenerateComprehensiveAnalysis" />
          </aside>
        </main>
        <MessageToast :message="message" />
      </template>
    </div>
  `
}

// 创建并挂载应用
const app = createApp(App)

// 注册组件
app.component('Card', Card)
app.component('FilePreviewCard', FilePreviewCard)
app.component('ChatArea', ChatArea)
app.component('CompanyOverview', CompanyOverview)
app.component('NotesAndRisks', NotesAndRisks)
app.component('VisualizationPanel', VisualizationPanel)
app.component('MessageToast', MessageToast)
app.component('AgentAnalysisPage', AgentAnalysisPage)

// 挂载应用
app.mount('#app')

console.log('✅ Vue应用已加载')

