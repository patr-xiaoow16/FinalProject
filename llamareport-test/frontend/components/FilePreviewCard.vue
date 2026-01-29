<template>
  <Card title="文件预览" icon="📁" status="content" empty-text="请上传PDF或Excel文件">
    <template #default>
      <div class="file-actions">
        <button class="btn-small" @click="processSelectedFiles" :disabled="selectedFiles.length === 0 || processingFiles.length > 0 || files.length === 0">
          {{ processingFiles.length > 0 ? '处理中...' : '🔄 处理选中文件' }}
        </button>
        <button class="btn-small btn-danger" @click="clearAllFiles" :disabled="files.length === 0">🗑️ 清空所有</button>
      </div>
      <div :class="['upload-zone', { dragover: isDragging }]" @dragover.prevent="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop" @click="$refs.fileInput.click()">
        <input ref="fileInput" type="file" class="file-input" accept=".pdf,.xlsx,.xls" multiple @change="handleFileSelect">
        <p>点击或拖拽上传文件</p>
        <p class="upload-hint">支持格式：PDF、Excel (.xlsx, .xls)</p>
      </div>
      <div v-if="files.length > 0" class="file-list">
        <div v-for="file in files" :key="file.filename" :class="['file-item', { active: isFileSelected(file.filename), processing: isFileProcessing(file.filename), completed: isFileCompleted(file.filename) }]" @click="toggleFileSelection(file)">
          <div class="file-checkbox">
            <input type="checkbox" :checked="isFileSelected(file.filename)" @click.stop="toggleFileSelection(file)" />
          </div>
          <div class="file-info">
            <span class="file-icon">{{ getFileIcon(file.file_type) }}</span>
            <div class="file-details">
              <div class="file-name">{{ file.filename }}</div>
              <div class="file-meta">
                <span class="file-size">{{ formatFileSize(file.file_size) }}</span>
                <span v-if="isExcelFile(file.file_type)" class="file-type-badge excel-badge">Excel</span>
                <span v-else-if="isPdfFile(file.file_type)" class="file-type-badge pdf-badge">PDF</span>
                <span v-if="isFileProcessing(file.filename)" class="file-type-badge processing-badge">处理中...</span>
                <span v-else-if="isFileCompleted(file.filename)" class="file-type-badge completed-badge">完成</span>
              </div>
            </div>
          </div>
          <div class="file-actions-right">
            <button class="file-preview-btn" @click.stop="openPreview(file)" :title="isPdfFile(file.file_type) ? '预览PDF' : '预览Excel'">📑</button>
            <button class="file-delete-btn" @click.stop="deleteFile(file.filename, $event)" title="删除文件">×</button>
          </div>
        </div>
      </div>
      
      <!-- 文件预览模态框 -->
      <div v-if="showPreview && previewFile" class="pdf-preview-modal" @click.self="closePreview">
        <div class="pdf-preview-container">
          <div class="pdf-preview-header">
            <h3>{{ getPreviewIcon(previewFile.file_type) }} {{ previewFile.filename }}</h3>
            <button class="close-preview-btn" @click="closePreview">×</button>
          </div>
          <div class="pdf-preview-content">
            <iframe 
              :src="getPreviewUrl(previewFile.filename)" 
              class="pdf-preview-iframe"
              frameborder="0"
            ></iframe>
          </div>
        </div>
      </div>
    </template>
  </Card>
</template>

<script>
import Card from './Card.vue'

export default {
  name: 'FilePreviewCard',
  components: {
    Card
  },
  props: { 
    files: { type: Array, default: () => [] } 
  },
  emits: ['file-selected', 'file-uploaded', 'file-deleted', 'show-message', 'file-process', 'file-process-multiple', 'files-processed'],
  data() {
    return { 
      isDragging: false, 
      selectedFile: null,  // 保留用于向后兼容
      selectedFiles: [],   // 多选文件列表
      processingFiles: [], // 正在处理的文件列表
      completedFiles: [],  // 已处理完成的文件列表
      previewFile: null,
      showPreview: false
    };
  },
  mounted() {
    // 监听文件处理完成事件
    window.addEventListener('files-processing-complete', this.handleFilesProcessingComplete)
    window.addEventListener('file-processing-complete', this.handleFileProcessingComplete)
    window.addEventListener('file-processing-failed', this.handleFileProcessingFailed)
  },
  beforeUnmount() {
    // 移除事件监听器
    window.removeEventListener('files-processing-complete', this.handleFilesProcessingComplete)
    window.removeEventListener('file-processing-complete', this.handleFileProcessingComplete)
    window.removeEventListener('file-processing-failed', this.handleFileProcessingFailed)
  },
  methods: {
    handleFilesProcessingComplete(event) {
      // 批量处理完成
      const { filenames } = event.detail || {}
      if (filenames && Array.isArray(filenames)) {
        this.markFilesCompleted(filenames)
      }
    },
    handleFileProcessingComplete(event) {
      // 单个文件处理完成
      const { filename } = event.detail || {}
      if (filename) {
        this.markFileCompleted(filename)
      }
    },
    handleFileProcessingFailed(event) {
      // 文件处理失败，清除处理中状态
      const { filename } = event.detail || {}
      if (filename) {
        const processingIndex = this.processingFiles.indexOf(filename)
        if (processingIndex > -1) {
          this.processingFiles.splice(processingIndex, 1)
        }
      }
    },
    handleDragOver(e) { e.preventDefault(); this.isDragging = true; },
    handleDragLeave() { this.isDragging = false; },
    async handleDrop(e) {
      e.preventDefault();
      this.isDragging = false;
      await this.uploadFiles(Array.from(e.dataTransfer.files));
    },
    handleFileSelect(e) { this.uploadFiles(Array.from(e.target.files)); },
    async uploadFiles(files) {
      if (files.length > 1) {
        await this.batchUploadFiles(files);
      } else {
        for (const file of files) {
          await this.uploadSingleFile(file);
        }
      }
    },
    async uploadSingleFile(file) {
      // 检查文件类型
      const fileExt = this.getFileExtension(file.name);
      if (!this.isSupportedFileType(fileExt)) {
        this.$emit('show-message', 'error', `文件 ${file.name} 不支持。支持格式：PDF、Excel (.xlsx, .xls)`);
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      try {
        const response = await fetch('/upload/file', { method: 'POST', body: formData });
        const result = await response.json();
        if (response.ok) {
          this.$emit('file-uploaded');
          this.$emit('show-message', 'success', `文件 ${result.filename} 上传成功`);
        } else {
          this.$emit('show-message', 'error', `上传失败: ${result.detail}`);
        }
      } catch (error) {
        this.$emit('show-message', 'error', `上传失败: ${error.message}`);
      }
    },
    async batchUploadFiles(files) {
      const formData = new FormData();
      files.forEach(file => {
        const fileExt = this.getFileExtension(file.name);
        if (this.isSupportedFileType(fileExt)) {
          formData.append('files', file);
        }
      });
      try {
        const response = await fetch('/upload/files', { method: 'POST', body: formData });
        const result = await response.json();
        if (response.ok) {
          this.$emit('file-uploaded');
          this.$emit('show-message', 'success', result.message);
        } else {
          this.$emit('show-message', 'error', result.detail);
        }
      } catch (error) {
        this.$emit('show-message', 'error', `批量上传失败: ${error.message}`);
      }
    },
    selectFile(file) { 
      this.selectedFile = file; 
      // 同时添加到多选列表
      if (!this.isFileSelected(file.filename)) {
        this.selectedFiles.push(file.filename);
      }
      this.$emit('file-selected', file); 
    },
    toggleFileSelection(file) {
      const index = this.selectedFiles.indexOf(file.filename);
      if (index > -1) {
        this.selectedFiles.splice(index, 1);
        if (this.selectedFile?.filename === file.filename) {
          this.selectedFile = null;
        }
      } else {
        this.selectedFiles.push(file.filename);
        this.selectedFile = file;
      }
      this.$emit('file-selected', file);
    },
    isFileSelected(filename) {
      return this.selectedFiles.includes(filename);
    },
    isFileProcessing(filename) {
      return this.processingFiles.includes(filename);
    },
    isFileCompleted(filename) {
      return this.completedFiles.includes(filename);
    },
    markFileCompleted(filename) {
      // 从处理中列表移除
      const processingIndex = this.processingFiles.indexOf(filename);
      if (processingIndex > -1) {
        this.processingFiles.splice(processingIndex, 1);
      }
      // 添加到完成列表
      if (!this.completedFiles.includes(filename)) {
        this.completedFiles.push(filename);
      }
    },
    markFilesCompleted(filenames) {
      // 批量标记文件为完成状态
      filenames.forEach(filename => {
        this.markFileCompleted(filename);
      });
    },
    selectAllFiles() {
      this.selectedFiles = this.files.map(f => f.filename);
      if (this.files.length > 0) {
        this.selectedFile = this.files[0];
      }
    },
    clearSelection() {
      this.selectedFiles = [];
      this.selectedFile = null;
    },
    async deleteFile(filename, e) {
      e.stopPropagation();
      if (!confirm(`确定要删除文件 "${filename}" 吗？`)) return;
      try {
        const response = await fetch(`/upload/file/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        const result = await response.json();
        if (response.ok) {
          this.$emit('file-deleted');
          this.$emit('show-message', 'success', `文件 ${filename} 删除成功`);
          // 从选中列表中移除
          const index = this.selectedFiles.indexOf(filename);
          if (index > -1) {
            this.selectedFiles.splice(index, 1);
          }
          if (this.selectedFile?.filename === filename) this.selectedFile = null;
        } else {
          this.$emit('show-message', 'error', `删除失败: ${result.detail}`);
        }
      } catch (error) {
        this.$emit('show-message', 'error', `删除失败: ${error.message}`);
      }
    },
    async clearAllFiles() {
      if (!confirm('确定要清空所有上传的文件吗？此操作不可恢复！')) return;
      try {
        const response = await fetch('/upload/clear', { method: 'DELETE' });
        const result = await response.json();
        if (response.ok) {
          this.$emit('file-deleted');
          this.$emit('show-message', 'success', result.message);
          this.selectedFile = null;
        } else {
          this.$emit('show-message', 'error', result.detail);
        }
      } catch (error) {
        this.$emit('show-message', 'error', `清空失败: ${error.message}`);
      }
    },
    async processFile(filename) {
      // 单个文件处理（向后兼容）
      if (!filename) {
        this.$emit('show-message', 'error', '请先选择文件');
        return;
      }
      this.selectedFiles = [filename];
      await this.processSelectedFiles();
    },
    async processSelectedFiles() {
      if (this.selectedFiles.length === 0) {
        this.$emit('show-message', 'error', '请先选择要处理的文件');
        return;
      }
      
      const selectedFileObjects = this.files.filter(f => this.selectedFiles.includes(f.filename));
      const hasExcel = selectedFileObjects.some(f => this.isExcelFile(f.file_type));
      const hasPdf = selectedFileObjects.some(f => this.isPdfFile(f.file_type));
      
      let processDesc = `将处理 ${this.selectedFiles.length} 个文件：\n`;
      if (hasExcel) {
        processDesc += `- Excel文件：解析、识别财务报表类型、提取表格数据\n`;
      }
      if (hasPdf) {
        processDesc += `- PDF文件：解析文档、提取表格数据\n`;
      }
      processDesc += `- 构建RAG索引\n\n这可能需要几分钟时间。`;
      
      if (!confirm(`确定要处理选中的 ${this.selectedFiles.length} 个文件吗？\n\n${processDesc}`)) {
        return;
      }
      
      // 设置处理状态
      this.processingFiles = [...this.selectedFiles];
      
      // 发送处理事件
      if (this.selectedFiles.length === 1) {
        // 单个文件，使用原有接口
        this.$emit('file-process', this.selectedFiles[0]);
      } else {
        // 多个文件，使用批量处理接口
        this.$emit('file-process-multiple', this.selectedFiles);
      }
      
      // 注意：processingFiles 会在处理完成后由父组件清除，或者在这里设置超时清除
      // 这里先不清除，让父组件在处理完成后清除
    },
    formatFileSize(bytes) { return (bytes / 1024 / 1024).toFixed(2) + ' MB'; },
    getFileExtension(filename) {
      const parts = filename.split('.');
      return parts.length > 1 ? '.' + parts[parts.length - 1].toLowerCase() : '';
    },
    isSupportedFileType(fileExt) {
      return ['.pdf', '.xlsx', '.xls'].includes(fileExt.toLowerCase());
    },
    isPdfFile(fileType) {
      return fileType === '.pdf';
    },
    isExcelFile(fileType) {
      return ['.xlsx', '.xls'].includes(fileType?.toLowerCase() || '');
    },
    getFileIcon(fileType) {
      if (this.isExcelFile(fileType)) {
        return '📊';
      } else if (this.isPdfFile(fileType)) {
        return '📄';
      }
      return '📁';
    },
    openPreview(file) {
      // PDF和Excel文件都支持预览
      this.previewFile = file;
      this.showPreview = true;
    },
    closePreview() {
      this.showPreview = false;
      this.previewFile = null;
    },
    getPreviewUrl(filename) {
      const file = this.files.find(f => f.filename === filename);
      const fileType = file?.file_type || this.getFileExtension(filename);
      
      // PDF和Excel都使用同一个预览接口
      return `/upload/file/${encodeURIComponent(filename)}`;
    },
    getPreviewIcon(fileType) {
      if (this.isExcelFile(fileType)) {
        return '📊';
      } else if (this.isPdfFile(fileType)) {
        return '📄';
      }
      return '📁';
    }
  }
}
</script>

<style scoped>
.upload-hint {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #9ca3af;
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
}

.file-type-badge {
  display: inline-block;
  padding: 2px 6px;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 500;
}

.excel-badge {
  background: #dcfce7;
  color: #166534;
}

.pdf-badge {
  background: #fee2e2;
  color: #991b1b;
}
</style>

