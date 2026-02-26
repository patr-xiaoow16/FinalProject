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
    /** 当前财务概况对应的文件名（仅在处理该文件成功后才有值） */
    const overviewForFilename = ref(null)
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
    
    const handleFileSelected = (file) => {
      selectedFile.value = file
      if (!file?.filename) {
        quickOverviewData.value = null
        overviewForFilename.value = null
      } else if (file.filename !== overviewForFilename.value) {
        // 选中的不是当前已加载概况的文件，清空概况区域，提示先处理
        quickOverviewData.value = null
      }
    }
    const handleFileUploaded = () => { 
      loadFileList()
      setTimeout(() => checkIndexStatus(), 500)
    }
    const handleFileDeleted = () => {
      loadFileList()
      if (selectedFile.value && !files.value.find(f => f.filename === selectedFile.value.filename)) {
        selectedFile.value = null
        quickOverviewData.value = null
        overviewForFilename.value = null
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
            // 处理完成后自动拉取该文件的财务概况
            setTimeout(() => loadQuickOverview(filename), 500)
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
            // 处理完成后：若当前选中文件在成功列表中则拉取其概况，否则拉取第一个成功文件
            const successFilenames = (result.file_results || []).filter(r => r.status === 'success').map(f => f.filename)
            const toLoad = selectedFile.value && successFilenames.includes(selectedFile.value.filename)
              ? selectedFile.value.filename
              : successFilenames[0]
            if (toLoad) setTimeout(() => loadQuickOverview(toLoad), 500)
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
          body: JSON.stringify({ 
            question,
            query_type: 'general'  // 输入框输入使用通用查询模式
          }),
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
          let hasVisualization = false
          if (result.visualization && result.visualization.has_visualization) {
            hasVisualization = true
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
              // 检查是否有多个视图
              if (result.visualization.visualizations && Array.isArray(result.visualization.visualizations) && result.visualization.visualizations.length > 0) {
                // 多个视图：为每个视图创建一个卡片
                result.visualization.visualizations.forEach((viz, idx) => {
                  const cardId = `${Date.now().toString()}-${idx}`
                  visualizationCards.value.push({
                    id: cardId,
                    question: viz.title || question + (result.visualization.visualizations.length > 1 ? ` (${idx + 1})` : ''),
                    timestamp: new Date(),
                    data: {
                      has_visualization: true,
                      chart_config: viz.chart_config,
                      timeline_data: viz.timeline_data,
                      visualization_type: viz.visualization_type || 'plotly',
                      recommendation: viz.recommendation,
                      insights: viz.insights,
                      description: viz.description
                    },
                    type: 'chart'
                  })
                })
                console.log(`✅ 添加了 ${result.visualization.visualizations.length} 个可视化视图`)
              } else {
                // 单个视图（向后兼容）
                const cardId = Date.now().toString()
                visualizationCards.value.push({
                  id: cardId,
                  question: question,
                  timestamp: new Date(),
                  data: result.visualization,
                  type: 'chart'
                })
              }
            }
            visualizationLoading.value = false
          }
          
          // 如果Agent查询没有生成可视化，自动调用 /query/ask 接口强制生成可视化
          if (!hasVisualization && result.answer && result.answer.length > 50) {
            console.log('📊 Agent查询未返回可视化，尝试自动生成可视化...')
            visualizationLoading.value = true
            
            try {
              const context_filter = selectedFile.value ? {
                filename: selectedFile.value.filename
              } : null
              
              const vizResponse = await fetch('/query/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                  question: question, 
                  enable_visualization: true,
                  context_filter: context_filter
                })
              })
              
              if (vizResponse.ok) {
                const vizResult = await vizResponse.json()
                
                if (vizResult.visualization && vizResult.visualization.has_visualization) {
                  // 检查是否有多个视图
                  if (vizResult.visualization.visualizations && Array.isArray(vizResult.visualization.visualizations) && vizResult.visualization.visualizations.length > 0) {
                    // 多个视图：为每个视图创建一个卡片
                    vizResult.visualization.visualizations.forEach((viz, idx) => {
                      const cardId = `auto-viz-${Date.now()}-${idx}`
                      visualizationCards.value.push({
                        id: cardId,
                        question: viz.title || question + (vizResult.visualization.visualizations.length > 1 ? ` (${idx + 1})` : ''),
                        timestamp: new Date(),
                        data: {
                          has_visualization: true,
                          chart_config: viz.chart_config,
                          timeline_data: viz.timeline_data,
                          visualization_type: viz.visualization_type || 'plotly',
                          recommendation: viz.recommendation,
                          insights: viz.insights,
                          description: viz.description
                        },
                        type: 'chart'
                      })
                    })
                    console.log(`✅ 自动生成了 ${vizResult.visualization.visualizations.length} 个可视化视图`)
                  } else {
                    // 单个视图
                    const cardId = `auto-viz-${Date.now()}`
                    visualizationCards.value.push({
                      id: cardId,
                      question: question,
                      timestamp: new Date(),
                      data: vizResult.visualization,
                      type: 'chart'
                    })
                    console.log('✅ 自动生成了可视化视图')
                  }
                } else {
                  console.log('⚠️ 自动生成可视化失败：无可视化结果')
                }
              } else {
                console.warn('⚠️ 自动生成可视化请求失败:', vizResponse.status)
              }
            } catch (vizError) {
              console.warn('⚠️ 自动生成可视化时出错:', vizError)
              // 不影响主流程，静默失败
            } finally {
              visualizationLoading.value = false
            }
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
      const labelRegex = /(资产负债表(?:数据|分析)?|利润表(?:数据|分析)?|现金流量表(?:数据|分析)?|综合判断|总体判断|总体评价|综合评价|综合三表总结|综合三表分析|总体结论|综合结论)[：:\s]*/g
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

    const stripHtmlTags = (text = '') => String(text).replace(/<[^>]*>/g, '')

    const escapeMarkdownCell = (value) => String(value ?? '—')
      .replace(/\r?\n/g, '<br>')
      .replace(/\|/g, '\\|')

    const toMarkdownTable = (headers = [], rows = [], maxRows = 6) => {
      if (!Array.isArray(headers) || !Array.isArray(rows) || headers.length === 0) return ''
      const normalizedRows = rows
        .filter(row => Array.isArray(row) && row.some(cell => String(cell ?? '').trim()))
        .slice(0, maxRows)
        .map(row => row.slice(0, headers.length))
      if (normalizedRows.length === 0) return ''
      const headerLine = `| ${headers.map(escapeMarkdownCell).join(' | ')} |`
      const divider = `| ${headers.map(() => '---').join(' | ')} |`
      const bodyLines = normalizedRows
        .map(row => `| ${row.map(escapeMarkdownCell).join(' | ')} |`)
      return [headerLine, divider, ...bodyLines].join('\n')
    }

    const normalizeInsightText = (text = '') => stripHtmlTags(text)
      .replace(/\s+/g, '')
      .replace(/[：:、，,.;。；]/g, '')
      .trim()

    const appendFinancialReviewSupplement = (base = '', supplement = '') => {
      const trimmed = String(supplement).trim()
      if (!trimmed || trimmed.startsWith('{') || trimmed.startsWith('[')) return base
      const baseText = normalizeInsightText(base)
      const supplementText = normalizeInsightText(trimmed)
      if (!supplementText) return base
      if (baseText && (baseText.includes(supplementText) || supplementText.includes(baseText))) return base
      const formatted = formatSummaryList(trimmed)
      const title = '<div class="summary-title">补充说明</div>'
      return `${base || ''}${base ? '<br>' : ''}${title}${formatted}`
    }

    const buildFinancialReviewMarkdown = ({
      companyName,
      year,
      payload,
      rawContent,
      toolSummary
    }) => {
      const titleCompany = companyName || '公司'
      const titleYear = year ? `${year}年` : ''
      const title = `${titleCompany}${titleYear}财务点评分析`
      const summarySource = payload?.summary || toolSummary || {}
      const getSummaryText = (value) => {
        if (!value) return ''
        if (typeof value === 'string') return value.trim()
        return ''
      }
      const summary = {
        balance_sheet: getSummaryText(summarySource.balance_sheet || summarySource.balanceSheet),
        income_statement: getSummaryText(summarySource.income_statement || summarySource.incomeStatement),
        cash_flow: getSummaryText(summarySource.cash_flow || summarySource.cashFlow),
        overall: getSummaryText(summarySource.overall)
      }
      const tables = payload?.visualization_tables || {}
      const tableList = [
        tables.balance_sheet_assets,
        tables.balance_sheet_liabilities,
        tables.income_statement_revenue,
        tables.income_statement_expense,
        tables.cash_flow
      ].filter(table => table && isMeaningfulTable(table))

      const toMetricBullets = (table, maxRows = 4) => {
        if (!table) return ''
        const headers = Array.isArray(table.headers) ? table.headers : []
        const rows = Array.isArray(table.rows) ? table.rows : []
        const pickedRows = rows.filter(row => Array.isArray(row)).slice(0, maxRows)
        if (!pickedRows.length || headers.length < 2) return ''
        return pickedRows.map((row) => {
          const metric = row[0] || '指标'
          const parts = []
          for (let i = 1; i < Math.min(row.length, headers.length); i += 1) {
            const label = headers[i]
            const value = row[i]
            if (value !== undefined && value !== null && String(value).trim() !== '') {
              parts.push(`${label}：${value}`)
            }
          }
          const detail = parts.length ? `（${parts.join('；')}）` : ''
          return `- ${metric}${detail}`
        }).join('\n')
      }

      const toBulletParagraphs = (text = '') => {
        const cleaned = String(text || '').trim()
        if (!cleaned) return ''
        if (/^\s*[-*]\s+/m.test(cleaned)) return cleaned
        const parts = cleaned
          .split(/[。；]\s*/g)
          .map(item => item.trim())
          .filter(Boolean)
        if (parts.length <= 1) return cleaned
        return parts.map(item => `- ${item}`).join('\n')
      }

      const sectionBlocks = []
      if (summary.balance_sheet) {
        sectionBlocks.push(`## **资产负债表**\n${toBulletParagraphs(summary.balance_sheet)}`)
      }
      if (summary.income_statement) {
        sectionBlocks.push(`## **利润表**\n${toBulletParagraphs(summary.income_statement)}`)
      }
      if (summary.cash_flow) {
        sectionBlocks.push(`## **现金流量表**\n${toBulletParagraphs(summary.cash_flow)}`)
      }
      if (summary.overall) {
        sectionBlocks.push(`## **综合判断**\n${toBulletParagraphs(summary.overall)}`)
      }

      const metricsBlocks = tableList.map((table) => {
        const titleText = sanitizeCardTitle(table.title || '关键指标')
        const bullets = toMetricBullets(table, 4)
        if (!bullets) return ''
        return `#### ${titleText}\n${bullets}`
      }).filter(Boolean)

      const supplement = rawContent && typeof rawContent === 'string'
        ? rawContent.trim()
        : ''

      const parts = [`## ${title}`]
      if (sectionBlocks.length) parts.push(sectionBlocks.join('\n\n'))
      if (metricsBlocks.length) parts.push(`## **关键指标速览**\n${metricsBlocks.join('\n\n')}`)
      if (supplement && !supplement.startsWith('{') && !supplement.startsWith('[')) {
        parts.push(`${supplement}`)
      }
      return parts.join('\n\n')
    }

    const buildBusinessGuidanceMarkdown = ({
      companyName,
      year,
      payload
    }) => {
      if (!payload || typeof payload !== 'object') return ''
      const titleCompany = companyName || '公司'
      const titleYear = year ? `${year}年` : ''
      const title = `${titleCompany}${titleYear}业绩指引分析`
      const guidancePeriod = payload.guidance_period || payload.guidancePeriod || `${year || ''}年度`
      const expectedPerformance = payload.expected_performance || payload.expectedPerformance || ''
      const metricHighlights = []
      const parentProfit = payload.parent_net_profit_range || payload.parentNetProfitRange
      const parentProfitGrowth = payload.parent_net_profit_growth_range || payload.parentNetProfitGrowthRange
      const nonRecurringProfit = payload.non_recurring_profit_range || payload.nonRecurringProfitRange
      const epsRange = payload.eps_range || payload.epsRange
      const revenueRange = payload.revenue_range || payload.revenueRange
      if (parentProfit) metricHighlights.push(`归母净利润：${parentProfit}`)
      if (parentProfitGrowth) metricHighlights.push(`归母净利润增长率：${parentProfitGrowth}`)
      if (nonRecurringProfit) metricHighlights.push(`扣非净利润：${nonRecurringProfit}`)
      if (epsRange) metricHighlights.push(`基本每股收益：${epsRange}`)
      if (revenueRange) metricHighlights.push(`营业收入：${revenueRange}`)

      const keyMetrics = Array.isArray(payload.key_metrics || payload.keyMetrics)
        ? (payload.key_metrics || payload.keyMetrics)
        : []
      const businessGuidance = Array.isArray(payload.business_specific_guidance || payload.businessSpecificGuidance)
        ? (payload.business_specific_guidance || payload.businessSpecificGuidance)
        : []
      const riskWarnings = Array.isArray(payload.risk_warnings || payload.riskWarnings)
        ? (payload.risk_warnings || payload.riskWarnings)
        : []

      const listBlock = (items = [], fallback = '未明确') => {
        const list = items.filter(Boolean)
        if (!list.length) return `- ${fallback}`
        return list.map(item => `- ${item}`).join('\n')
      }

      const parts = [`## **${title}**`]
      parts.push(`**指引期间**：${guidancePeriod || '未明确'}`)
      parts.push(`## **一、经营目标方向**\n${expectedPerformance ? expectedPerformance : '未明确'}`)
      parts.push(`## **二、核心指标锚点**\n${listBlock(metricHighlights.length ? metricHighlights : keyMetrics)}`)
      parts.push(`## **三、关键执行路径**\n${listBlock(businessGuidance)}`)
      parts.push(`## **四、不确定性与边界**\n${listBlock(riskWarnings)}`)
      return parts.join('\n\n')
    }

    const buildDupontMarkdown = ({
      companyName,
      year,
      analysis
    }) => {
      if (!analysis || typeof analysis !== 'object') return ''
      const titleCompany = companyName || '公司'
      const titleYear = year ? `${year}年` : ''
      const title = `${titleCompany}${titleYear}杜邦分析`
      const level1 = analysis.level1 || {}
      const level2 = analysis.level2 || {}
      const level3 = analysis.level3 || {}
      const metricValue = (source, key) => (
        source?.[key]?.formatted_value
        || source?.[key]?.value
        || source?.[key]
        || '—'
      )
      const roe = metricValue(level1, 'roe')
      const roa = metricValue(level1, 'roa')
      const equityMultiplier = metricValue(level1, 'equity_multiplier')
      const netProfitMargin = metricValue(level2, 'net_profit_margin')
      const assetTurnover = metricValue(level2, 'asset_turnover')
      const netIncome = metricValue(level3, 'net_income')
      const revenue = metricValue(level3, 'revenue')
      const totalAssets = metricValue(level2, 'total_assets')
      const shareholdersEquity = metricValue(level2, 'shareholders_equity')

      const listBlock = (items = []) => {
        const list = Array.isArray(items) ? items.filter(Boolean) : []
        if (!list.length) return ''
        return list.map(item => `- ${item}`).join('\n')
      }

      const parts = [`## **${title}**`]
      parts.push(`**关键指标**：ROE ${roe}；ROA ${roa}；权益乘数 ${equityMultiplier}；净利率 ${netProfitMargin}；资产周转率 ${assetTurnover}；净利润 ${netIncome}；营业收入 ${revenue}；总资产 ${totalAssets}；股东权益 ${shareholdersEquity}`)

      const insightsBlock = listBlock(analysis.insights)
      if (insightsBlock) parts.push(`## **一、分析洞察**\n${insightsBlock}`)

      const strengths = Array.isArray(analysis.strengths) ? analysis.strengths : []
      const weaknesses = Array.isArray(analysis.weaknesses) ? analysis.weaknesses : []
      const mergedSW = [...strengths, ...weaknesses].filter(Boolean)
      const mergedBlock = listBlock(mergedSW)
      if (mergedBlock) parts.push(`## **二、优势劣势**\n${mergedBlock}`)

      const recommendationsBlock = listBlock(analysis.recommendations)
      if (recommendationsBlock) parts.push(`## **三、改进建议**\n${recommendationsBlock}`)

      return parts.join('\n\n')
    }

    const extractFinancialReviewPayload = (result) => {
      if (!result || typeof result !== 'object') return null
      const structured = result.structured_response || {}
      if (structured.summary && structured.visualization_tables) return structured
      if (structured.financial_review) return structured.financial_review
      if (structured.financialReview) return structured.financialReview

      const toolCall = Array.isArray(result.tool_calls)
        ? result.tool_calls.find(tc => tc.tool_name === 'generate_financial_review')
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
      if (output && (output.summary || output.visualization_tables)) {
        return output
      }
      return null
    }

    const formatFinancialReviewTableInsights = (tables) => {
      if (!tables) return ''
      const tableList = [
        tables.balance_sheet_assets,
        tables.balance_sheet_liabilities,
        tables.income_statement_revenue,
        tables.income_statement_expense,
        tables.cash_flow
      ].filter(Boolean)
      const items = tableList
        .filter(table => table?.insight)
        .map(table => (
          `<div class="summary-item"><span class="summary-label">${table.title || '表格洞察'}</span><div class="summary-text">${formatTableInsight(table.insight)}</div></div>`
        ))
      if (items.length === 0) return ''
      return `<div class="summary-title">表格洞察</div><div class="summary-block">${items.join('')}</div>`
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
      let rawOutput = output && output.raw_output !== undefined ? output.raw_output : null
      if (typeof rawOutput === 'string') {
        try {
          rawOutput = JSON.parse(rawOutput)
        } catch (e) {
          rawOutput = null
        }
      }
      if (rawOutput && typeof rawOutput === 'object') {
        const merged = { ...rawOutput }
        if (output && typeof output === 'object') {
          Object.keys(output).forEach(key => {
            if (merged[key] === undefined) {
              merged[key] = output[key]
            }
          })
        }
        return merged
      }
      if (output && typeof output === 'object') return output
      if (typeof output === 'string') {
        try {
          const parsed = JSON.parse(output)
          return parsed && typeof parsed === 'object' ? parsed : null
        } catch (e) {
          return null
        }
      }
      return null
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

    const buildGuidanceToneCard = (payload = {}) => {
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
    }

    const parseNumericValue = (value = '') => {
      const text = String(value).replace(/,/g, '').trim()
      const match = text.match(/-?\d+(\.\d+)?/)
      if (!match) return null
      return Number(match[0])
    }

    const buildGuidanceInsights = (description, findings = []) => {
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
    }

    const getGuidanceInsights = (payload = {}, key) => {
      const insightsRoot = payload.visualization_insights || payload.visualizationInsights || {}
      const section = insightsRoot && typeof insightsRoot === 'object' ? insightsRoot[key] : null
      if (!section) return null
      if (Array.isArray(section)) return section
      if (Array.isArray(section.insights)) return section.insights
      return null
    }

    const filterGuidanceInsights = (insights = [], allowedItems = []) => {
      if (!Array.isArray(insights)) return null
      const allowed = new Set(allowedItems.map(item => String(item || '').trim()).filter(Boolean))
      if (!allowed.size) return insights.length ? insights : null
      const filtered = insights.filter(insight => {
        const related = Array.isArray(insight?.related_items) ? insight.related_items : []
        if (!related.length) return false
        return related.some(item => allowed.has(String(item || '').trim()))
      })
      return filtered.length ? filtered : null
    }

    const buildGuidanceVisualizationCards = (payload = {}, question = '') => {
      if (!payload || typeof payload !== 'object') return []
      const spec = payload.visualization_spec || payload.visualizationSpec || {}
      if (!spec || typeof spec !== 'object') return []
      const cards = []

      const operatingGoal = spec.operating_goal || spec.operatingGoal || {}
      if (operatingGoal.chart_type === 'status_card') {
        const toneCard = buildGuidanceToneCard(payload)
        if (toneCard) {
          cards.push({
            id: `${Date.now().toString()}-guidance-tone`,
            question: sanitizeCardTitle(toneCard.title || '经营基调状态卡'),
            timestamp: new Date(),
            data: {
              has_visualization: true,
              type: 'insight_card',
              meta_type: 'guidance_tone',
              title: toneCard.title,
              headline: toneCard.headline,
              contribution: toneCard.contribution
            },
            type: 'insight_card',
            source: 'guidance_tone'
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
          const valueNum = parseNumericValue(item?.value)
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
          const modelInsights = filterGuidanceInsights(
            getGuidanceInsights(payload, 'key_metrics'),
            labels
          )
          const insightDescription = notes.filter(Boolean).slice(0, 2).join('；')
            || `核心指标集中在 ${labels.slice(0, 3).join('、')}`
          cards.push({
            id: `${Date.now().toString()}-guidance-metrics`,
            question: sanitizeCardTitle('核心指标锚点'),
            timestamp: new Date(),
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || buildGuidanceInsights(insightDescription, findings),
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
            },
            type: 'chart',
            source: 'guidance_metrics'
          })
        }
      }

      const executionPath = spec.execution_path || spec.executionPath || {}
      if (executionPath.chart_type === 'structure_change' && Array.isArray(executionPath.items)) {
        const labels = []
        const values = []
        const findings = []
        executionPath.items.forEach(item => {
          const valueNum = parseNumericValue(item?.evidence)
          if (valueNum === null || !item?.action) return
          labels.push(String(item.action))
          values.push(valueNum)
          findings.push(`${item.action}：${item.evidence || valueNum}`)
        })
        if (labels.length >= 2) {
          const modelInsights = filterGuidanceInsights(
            getGuidanceInsights(payload, 'execution_path'),
            labels
          )
          const insightDescription = `关键执行路径聚焦在 ${labels.slice(0, 3).join('、')}`
          cards.push({
            id: `${Date.now().toString()}-guidance-execution`,
            question: sanitizeCardTitle('关键执行路径'),
            timestamp: new Date(),
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || buildGuidanceInsights(insightDescription, findings),
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
            },
            type: 'chart',
            source: 'guidance_execution'
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
          const modelInsights = filterGuidanceInsights(
            getGuidanceInsights(payload, 'uncertainty'),
            risks
          )
          const insightDescription = `关注风险：${risks.slice(0, 3).join('、')}`
          cards.push({
            id: `${Date.now().toString()}-guidance-risk`,
            question: sanitizeCardTitle('不确定性与边界'),
            timestamp: new Date(),
            data: {
              has_visualization: true,
              visualization_type: 'plotly',
              insights: modelInsights || buildGuidanceInsights(insightDescription, findings),
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
            },
            type: 'chart',
            source: 'guidance_risk'
          })
        }
      }

      return cards
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

    const handleQuickAnalysis = async ({ sectionName, companyName, year, question, typeName, modelType }) => {
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
            year,
            model_type: modelType || undefined
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
            const rawContent = result.content || ''
            const financialReview = extractFinancialReviewPayload(result)
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
              
              const insightSummary = formatFinancialReviewTableInsights(tables)
              if (insightSummary) {
                answerText = `${answerText || ''}${answerText ? '<br>' : ''}${insightSummary}`
              }
              
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

            const fullMarkdown = buildFinancialReviewMarkdown({
              companyName,
              year,
              payload: financialReview,
              rawContent,
              toolSummary
            })
            if (fullMarkdown) {
              answerText = fullMarkdown
            } else {
              answerText = appendFinancialReviewSupplement(answerText, rawContent)
            }
          }

          if (sectionName === 'business_guidance') {
            const payload = extractBusinessGuidancePayload(result)
            if (payload) {
              const fullMarkdown = buildBusinessGuidanceMarkdown({
                companyName,
                year,
                payload
              })
              if (fullMarkdown) {
                answerText = fullMarkdown
              } else {
                const formatted = formatBusinessGuidanceSummary(payload)
                if (formatted) {
                  answerText = formatted
                }
              }
              if (answerText && !visualizationCards.value.some(card => card.source === 'guidance_text_viz')) {
                try {
                  const vizResponse = await fetch('/agent/visualize-text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      query: question || '业绩指引分析',
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
                          id: `${Date.now().toString()}-guidance-text-viz-${idx}`,
                          question: sanitizeCardTitle(viz.display_title || viz.query || question || '业绩指引分析可视化'),
                          timestamp: new Date(),
                          data: viz,
                          type: 'chart',
                          source: 'guidance_text_viz'
                        })
                      })
                    } else if (textViz && textViz.has_visualization) {
                      visualizationCards.value.push({
                        id: `${Date.now().toString()}-guidance-text-viz`,
                        question: sanitizeCardTitle(textViz.display_title || textViz.query || question || '业绩指引分析可视化'),
                        timestamp: new Date(),
                        data: textViz,
                        type: 'chart',
                        source: 'guidance_text_viz'
                      })
                    }
                  } else {
                    console.warn('⚠️ 业绩指引文本可视化请求失败:', vizResponse.status)
                  }
                } catch (error) {
                  console.warn('⚠️ 业绩指引文本可视化请求异常:', error)
                }
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

          // 投资策略（相关性/因子/聚类）：将后端返回的可视化数据以卡片形式加入可视化视图界面，并附带数据洞察
          if (sectionName === 'profit_forecast') {
            const toolOutput = result.structured_response?.profit_forecast_and_valuation
            if (toolOutput && typeof toolOutput === 'object') {
              const maxInsightLen = 80
              const truncate = (s) => (s && typeof s === 'string') ? (s.length > maxInsightLen ? s.slice(0, maxInsightLen) + '…' : s) : ''
              const buildStrategyInsights = (c, cardInsights) => {
                if (cardInsights && cardInsights.correlation_summary) {
                  return [{ insight_type: 'trend', description: cardInsights.correlation_summary }]
                }
                if (!c || typeof c !== 'object') return []
                const list = []
                if (c.short_term) list.push({ insight_type: 'trend', description: truncate(`短期配置：${c.short_term}`) })
                if (c.long_term) list.push({ insight_type: 'trend', description: truncate(`长期配置：${c.long_term}`) })
                if (c.risk_control) list.push({ insight_type: 'risk', description: truncate(`风险管控：${c.risk_control}`) })
                const signals = c.key_signals
                if (Array.isArray(signals) && signals.length) list.push({ insight_type: 'signal', description: '关键信号', key_findings: signals.map(s => truncate(String(s))) })
                return list
              }
              const buildFactorInsights = (fa, cardInsights) => {
                if (cardInsights && cardInsights.factor_summary) {
                  return [{ insight_type: 'trend', description: cardInsights.factor_summary }]
                }
                if (!fa || typeof fa !== 'object') return []
                const list = []
                if (fa.interpretation && typeof fa.interpretation === 'string' && fa.interpretation.trim()) {
                  list.push({ insight_type: 'trend', description: truncate(fa.interpretation.trim()) })
                }
                const factors = fa.factors || []
                const varianceExplained = fa.variance_explained || {}
                if (factors.length && Object.keys(varianceExplained).length) {
                  const summary = factors.slice(0, 3).map(f => `${f}（${typeof varianceExplained[f] === 'number' ? (varianceExplained[f] * 100).toFixed(1) : varianceExplained[f]}%）`).join('；')
                  if (summary) list.push({ insight_type: 'distribution', description: truncate(`因子方差解释：${summary}`) })
                }
                return list
              }
              const buildClusteringInsights = (cm, cardInsights) => {
                if (cardInsights && cardInsights.clustering_summary) {
                  return [{ insight_type: 'trend', description: cardInsights.clustering_summary }]
                }
                if (!cm || typeof cm !== 'object') return []
                const list = []
                const conclusion = cm.conclusion
                if (conclusion && typeof conclusion === 'object' && conclusion.current_position) {
                  list.push({ insight_type: 'trend', description: truncate(`聚类定位：${conclusion.current_position}`) })
                }
                const coreInsights = cm.core_insights || []
                if (coreInsights.length) list.push({ insight_type: 'signal', description: '核心发现', key_findings: coreInsights.map(s => truncate(String(s))) })
                const riskNotes = cm.risk_notes || []
                if (riskNotes.length) list.push({ insight_type: 'risk', description: '风险提示', key_findings: riskNotes.map(s => truncate(String(s))) })
                return list
              }
              const cardInsights = toolOutput.card_insights || {}
              const cardsToAdd = []
              if (toolOutput.correlation_visualization && toolOutput.correlation_visualization.has_visualization) {
                cardsToAdd.push({
                  id: `investment-strategy-correlation-${Date.now()}`,
                  question: '相关性分析结果',
                  source: 'investment_strategy',
                  timestamp: new Date(),
                  type: 'chart',
                  data: {
                    has_visualization: true,
                    visualization_type: toolOutput.correlation_visualization.visualization_type || 'plotly',
                    chart_config: toolOutput.correlation_visualization.chart_config,
                    insights: buildStrategyInsights(toolOutput.strategy_conclusion, cardInsights)
                  }
                })
              } else if (Array.isArray(toolOutput.correlation_results) && toolOutput.correlation_results.length > 0) {
                const correlationData = toolOutput.correlation_results
                const labels = correlationData.map(r => `${r.target_metric} vs ${r.driver_metric}`)
                const correlations = correlationData.map(r => r.correlation || 0)
                cardsToAdd.push({
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
                        marker: { color: correlations.map(c => c >= 0 ? '#10b981' : '#ef4444') }
                      }],
                      layout: {
                        title: '相关性分析结果',
                        xaxis_title: '指标对',
                        yaxis_title: '相关系数',
                        yaxis: { range: [-1, 1] }
                      }
                    },
                    insights: buildStrategyInsights(toolOutput.strategy_conclusion, cardInsights)
                  }
                })
              }
              if (toolOutput.factor_analysis && toolOutput.factor_analysis.factors && toolOutput.factor_analysis.factors.length > 0) {
                const factorAnalysis = toolOutput.factor_analysis
                const factors = factorAnalysis.factors || []
                const varianceExplained = factorAnalysis.variance_explained || {}
                const varianceValues = factors.map(f => varianceExplained[f] || 0)
                cardsToAdd.push({
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
                    insights: buildFactorInsights(toolOutput.factor_analysis, cardInsights)
                  }
                })
              }
              if (toolOutput.clustering_model && toolOutput.clustering_model.group_results) {
                const clustering = toolOutput.clustering_model
                const groups = clustering.group_results || []
                const groupNames = groups.map(g => g.group_name || '未知组')
                cardsToAdd.push({
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
                    insights: buildClusteringInsights(toolOutput.clustering_model, cardInsights)
                  }
                })
              }
              cardsToAdd.forEach(card => visualizationCards.value.push(card))
              if (cardsToAdd.length > 0) {
                showMessage('success', `✅ 已添加 ${cardsToAdd.length} 个投资策略视图到可视化面板`)
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
              timestamp: new Date(),
              sectionName: sectionName
            })
          } else {
            chatMessages.value.push({
              type: 'assistant',
              content: answerHeader,
              timestamp: new Date(),
              sectionName: sectionName
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
          body: JSON.stringify({ 
            question,
            query_type: 'general'  // 输入框输入使用通用查询模式
          }),
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
        
        // 优先使用选中的文件，以便洞察与 PDF 年份一致；未选中时使用第一个已上传文件
        const filenameToUse = selectedFile.value?.filename || (files.value?.length ? files.value[0].filename : null)
        if (!filenameToUse) {
          showMessage('warning', '请先上传并选择要分析的文档，以便使用正确的报告年份')
        }
        const response = await fetch('/query/dupont-analysis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: null,  // 自动提取
            year: null,  // 自动提取
            filename: filenameToUse  // 与 PDF 对齐：仅从该文件提取年份与数据
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
          
          let content = buildDupontMarkdown({
            companyName: result.company_name,
            year: result.year,
            analysis
          })
          if (!content) {
            content = `✅ 杜邦分析生成成功！\n\n`
            content += `**公司**: ${result.company_name || '未知'}\n`
            content += `**年份**: ${result.year || '未知'}\n\n`
            content += `**核心指标**:\n`
            content += `- 净资产收益率(ROE): ${roe}\n`
            content += `- 资产净利率(ROA): ${roa}\n`
            content += `- 权益乘数: ${equityMultiplier}\n\n`
          }
          if (result.year_from_document === false && result.year) {
            content += `\n⚠️ 未从当前文档中识别到报告年份，已使用 ${result.year} 年；若与 PDF 年份不一致，请先选择对应报告文件再生成杜邦分析。\n`
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
    
    const loadQuickOverview = async (filename) => {
      if (!filename) return
      companyOverviewLoading.value = true
      try {
        const body = JSON.stringify({ filename })
        const response = await fetch('/query/quick-overview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body
        })
        const result = await response.json()
        if (response.ok && result.status === 'success') {
          quickOverviewData.value = result.overview
          overviewForFilename.value = filename
          showMessage('success', '✅ 财务概况已生成')
        } else {
          console.warn('快速概况生成失败:', result)
        }
      } catch (error) {
        console.error('加载快速概况失败:', error)
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
      quickOverviewData, overviewForFilename,
      showMessage, handleFileSelected, handleFileUploaded, handleFileDeleted, handleFileProcess, handleFileProcessMultiple,
      handleSendMessage, handleAgentQuery, executeAgentQuery, handleDupontAnalysis, handleGetSuggestions, handleQuickAnalysis,
      handleGenerateReport, handleGenerateSection, handleClearChat, checkIndexStatus, loadQuickOverview,
      handleDeleteMessage, goToAgentAnalysis, goBackToMain,
      handleAddVisualizationCards: (cards) => {
        if (!Array.isArray(cards) || cards.length === 0) return
        cards.forEach(card => {
          if (card && card.data && card.data.has_visualization) {
            visualizationCards.value.push({
              ...card,
              timestamp: card.timestamp || new Date()
            })
          }
        })
        if (cards.length > 0) {
          showMessage('success', `✅ 已添加 ${cards.length} 个投资策略视图到可视化面板`)
        }
      },
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
      handleGenerateComprehensiveAnalysis: async (selectedCards, explorationQuestion = null) => {
        // 处理生成综合分析请求（基于视图联动方案，支持探索问题）
        const cardCount = selectedCards.length
        const loadingMsg = explorationQuestion
          ? `正在聚焦分析：${explorationQuestion.substring(0, 30)}...`
          : (cardCount === 1 
            ? '正在分析视图并生成关联视图...' 
            : `正在分析${cardCount}个视图的关系并生成综合分析...`)
        showMessage('loading', loadingMsg)
        visualizationLoading.value = true
        
        try {
          const response = await fetch('/query/comprehensive-analysis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              selected_cards: selectedCards.map(card => {
                // ⭐修复：处理杜邦分析卡片
                if (card.isDupontCard && card.type === 'dupont') {
                  return {
                id: card.id,
                question: card.question,
                    data: {
                      has_visualization: true,
                      type: 'dupont',
                      dupont_data: card.data.dupont_data || dupontData.value
                    }
                  }
                }
                return {
                  id: card.id,
                  question: card.question,
                  data: card.data || {}
                }
              }),
              exploration_question: explorationQuestion || null,  // ⭐新增：探索问题
              overview_data: quickOverviewData.value,  // 传递财务概况数据
              context_filter: selectedFile.value ? {
                filename: selectedFile.value.filename
              } : null
            })
          })
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
            const errorMsg = errorData.detail || errorData.error || `HTTP ${response.status}`
            showMessage('error', `生成综合分析失败: ${errorMsg}`)
            visualizationLoading.value = false
            // 重置选择状态
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
            return
          }
          
          const result = await response.json()
          
          if (result.status === 'success') {
            let addedCount = 0
            
            // ⭐新增：在智能问答界面展示问题和洞察
            // 构建问题文本
            let questionText = ''
            if (explorationQuestion && explorationQuestion.trim()) {
              questionText = explorationQuestion.trim()
            } else {
              // 综合分析模式：显示"综合分析xxx"，xxx为卡片名字
              const cardNames = selectedCards.map(card => {
                const title = card.question || '未知视图'
                // 提取标题的前20个字符作为卡片名字
                return title.length > 20 ? title.substring(0, 20) + '...' : title
              })
              questionText = `综合分析：${cardNames.join('、')}`
            }
            
            // 添加用户问题到聊天界面
            chatMessages.value.push({
              type: 'user',
              content: questionText,
              timestamp: new Date()
            })
            
            // 构建洞察文本（只显示关键发现和置信度，不显示结论）
            let insightText = ''
            if (result.synthesis_insight) {
              insightText = `## 💡 分析洞察\n\n`
              
              // ⭐只显示关键发现（不显示结论）
              if (result.synthesis_insight.key_findings && result.synthesis_insight.key_findings.length > 0) {
                insightText += `**关键发现：**\n`
                result.synthesis_insight.key_findings.forEach((finding, idx) => {
                  insightText += `${idx + 1}. ${finding}\n`
                })
                insightText += `\n`
              }
              
              // ⭐显示置信度
              if (result.synthesis_insight.confidence) {
                const confidenceLabels = {
                  'high': '高置信度',
                  'medium': '中置信度',
                  'low': '低置信度'
                }
                const confidenceLabel = confidenceLabels[result.synthesis_insight.confidence] || result.synthesis_insight.confidence
                insightText += `**置信度：** ${confidenceLabel}\n\n`
              }
            }
            
            // 添加洞察到聊天界面
            if (insightText) {
              chatMessages.value.push({
                type: 'assistant',
                content: insightText,
                timestamp: new Date()
              })
            }
            
            // 优先使用新格式（new_views）- 一体化卡片（视图+洞察）
            console.log('📊 收到响应:', {
              hasNewViews: !!(result.new_views && result.new_views.length > 0),
              newViewsCount: result.new_views?.length || 0,
              hasSynthesisInsight: !!(result.synthesis_insight && result.synthesis_insight.conclusion),
              newViews: result.new_views
            })
            
            if (result.new_views && result.new_views.length > 0) {
              // 添加多个新视图卡片（一体化：视图+洞察）
              result.new_views.forEach((view, index) => {
                console.log(`📊 处理视图 ${index + 1}:`, {
                  view_id: view.view_id,
                  view_type: view.view_type,
                  description: view.description,
                  hasVisualization: view.visualization?.has_visualization,
                  visualizationType: view.visualization?.visualization_type,
                  hasInsight: !!view.insight
                })
                const cardId = `linkage_${Date.now()}_${index}`
                
                // 提取洞察信息
                const insight = view.insight || (result.synthesis_insight ? {
                  conclusion: result.synthesis_insight.conclusion,
                  key_findings: result.synthesis_insight.key_findings || [],
                  confidence: result.synthesis_insight.confidence || 'medium'
                } : null)
                
                // 构建一体化卡片
                // 确保data有has_visualization字段
                const cardData = view.visualization || {}
                if (!cardData.has_visualization && (cardData.chart_config || cardData.timeline_data || cardData.table)) {
                  cardData.has_visualization = true
                  if (!cardData.visualization_type) {
                    if (cardData.chart_config) cardData.visualization_type = 'plotly'
                    else if (cardData.timeline_data) cardData.visualization_type = 'timeline'
                    else if (cardData.table) cardData.visualization_type = 'table'
                    else cardData.visualization_type = 'plotly'
                  }
                }
                
                visualizationCards.value.push({
                  id: cardId,
                  question: view.description || `视图 ${index + 1}`,
                  timestamp: new Date(),
                  data: cardData,
                  type: 'chart',
                  // 联动生成标记
                  isLinkageGenerated: true,
                  viewType: view.view_type,
                  dataQuality: view.data_quality,
                  relatedCards: view.related_cards || [],
                  explorationQuestion: explorationQuestion,  // 探索问题
                  insight: insight,  // 洞察信息
                  showRelated: false  // UI状态
                })
                addedCount++
              })
              
              // 如果只有综合洞察但没有视图，创建一个洞察卡片
              if (result.synthesis_insight && result.synthesis_insight.conclusion && result.new_views.length === 0) {
                const insightCardId = `insight_${Date.now()}`
                visualizationCards.value.push({
                  id: insightCardId,
                  question: '综合洞察',
                  timestamp: new Date(),
                  data: {
                    has_visualization: false
                  },
                  type: 'insight',
                  isLinkageGenerated: true,
                  viewType: 'comprehensive',
                  explorationQuestion: explorationQuestion,
                  insight: {
                    conclusion: result.synthesis_insight.conclusion,
                    key_findings: result.synthesis_insight.key_findings || [],
                    confidence: result.synthesis_insight.confidence || 'medium'
                  },
                  showRelated: false
                })
                addedCount++
              }
              
              showMessage('success', `✅ 已生成${addedCount}个关联视图`)
            }
            // 兼容原有格式（单一视图）
            else if (result.visualization) {
            const cardId = Date.now().toString()
            visualizationCards.value.push({
              id: cardId,
                question: '综合分析',
              timestamp: new Date(),
              data: result.visualization,
              type: 'chart'
            })
              showMessage('success', '✅ 综合分析已生成')
              addedCount = 1
            }
            // 如果没有视图，显示提示
            else {
              showMessage('warning', '⚠️ 未生成新视图，请检查选中的卡片是否有有效的视图数据')
            }
            
            visualizationLoading.value = false
            
            // 重置选择状态，允许再次选择
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
          } else {
            const errorMsg = result.error || result.detail || '生成失败'
            showMessage('error', `生成综合分析失败: ${errorMsg}`)
            visualizationLoading.value = false
            // 重置选择状态
            window.dispatchEvent(new CustomEvent('reset-viz-selection'))
          }
        } catch (error) {
          console.error('生成综合分析错误:', error)
          const errorMsg = error.message || '网络错误或服务器无响应'
          showMessage('error', `生成综合分析失败: ${errorMsg}`)
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
        :on-add-visualization-cards="handleAddVisualizationCards"
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
            <CompanyOverview :data="companyOverviewData" :loading="companyOverviewLoading" :overview-data="quickOverviewData" :selected-file="selectedFile" :overview-for-filename="overviewForFilename" @generate-report="handleGenerateReport" @metric-click="handleMetricClick" />
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

