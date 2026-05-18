# Evidence Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal "claim-evidence-page" mapping to Agent query responses and display it in the analysis UI.

**Architecture:** Extend the backend Agent response assembly step to derive a compact `evidence_mapping` array from the final answer text and retrieved sources, then expose that field through the API without changing the existing `answer` contract. Render the returned mappings in the frontend analysis page as a simple evidence card section below the answer.

**Tech Stack:** Python, FastAPI, LlamaIndex, Vue

---

### Task 1: Plan the backend response shape

**Files:**
- Modify: `backend/agents/report_agent.py`
- Modify: `backend/api/agent.py`
- Test: `backend/tests/test_evidence_mapping.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_evidence_mapping_uses_claims_and_source_pages():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_evidence_mapping.py -v`
Expected: FAIL because helpers/field do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
result["evidence_mapping"] = self._build_evidence_mapping(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_evidence_mapping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/report_agent.py backend/api/agent.py backend/tests/test_evidence_mapping.py
git commit -m "feat: add agent evidence mappings"
```

### Task 2: Show evidence mappings in the analysis UI

**Files:**
- Modify: `frontend/components/AgentAnalysisPage.vue`

- [ ] **Step 1: Add a minimal view model for evidence mappings**

```javascript
evidenceMappings: []
```

- [ ] **Step 2: Populate it from the Agent query response**

```javascript
this.evidenceMappings = Array.isArray(result.evidence_mapping) ? result.evidence_mapping : []
```

- [ ] **Step 3: Render a simple card list below the answer**

```html
<section v-if="evidenceMappings.length">...</section>
```

- [ ] **Step 4: Verify the page still renders existing answer content**

Run: app smoke check in the existing frontend flow
Expected: answer still appears; mappings appear only when returned.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/AgentAnalysisPage.vue
git commit -m "feat: show evidence mappings in agent analysis"
```
