<template>
  <Card title="附注与风险" icon="⚠️" :status="status" empty-text="暂无附注与风险信息">
    <template #default>
      <div class="notes-risks-content">
        <div v-if="data?.notes" class="section">
          <h4>重要附注</h4>
          <div v-html="parseMarkdown(data.notes)"></div>
        </div>
        <div v-if="data?.risks" class="section">
          <h4>风险提示</h4>
          <div v-html="parseMarkdown(data.risks)"></div>
        </div>
        <div v-if="!data" class="action-buttons">
          <button class="btn-primary" @click="generateSection">📝 生成附注与风险</button>
        </div>
        <div v-if="!data" class="placeholder-text">附注与风险信息将在此显示</div>
      </div>
    </template>
  </Card>
</template>

<script>
import Card from './Card.vue'

export default {
  name: 'NotesAndRisks',
  components: {
    Card
  },
  props: { 
    data: { type: Object, default: null }, 
    loading: { type: Boolean, default: false } 
  },
  emits: ['generate-section'],
  computed: {
    status() {
      if (this.loading) return 'loading';
      if (!this.data) return 'empty';
      return 'content';
    }
  },
  methods: {
    async generateSection() {
      this.$emit('generate-section', 'financial_review');
    },
    parseMarkdown(text) {
      if (!text) return '';
      if (typeof marked !== 'undefined' && marked && marked.parse) {
        return marked.parse(text);
      }
      return text;
    }
  }
}
</script>




