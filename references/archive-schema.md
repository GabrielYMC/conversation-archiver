# Archive Schema Reference

本文件是 `agent-commons/protocols/conversation-archive.md` 的操作指南版本，
供 archiver 在生成封存檔案時直接參照。完整的設計哲學和理由見原始 protocol。

## 檔案結構

每份封存 .md 檔包含兩個部分：**摘要**（給人和 RAG 看）和**對話全文**（原始材料）。

```
┌─ Frontmatter (YAML) ─┐
├─ # 標題              │
├─ ## 脈絡             │  摘要區塊
├─ ## 發展軌跡         │  （~800 字軟上限）
├─ ## 關鍵概念         │
├─ ## 決議             │
├─ ## 產出物           │
├─ ## 關鍵字           │
├────────────────────────
├─ ## 對話全文         │  原始材料
│  <details>...</details>│ （折疊收納）
└────────────────────────
```

## Frontmatter

```yaml
---
type: conversation-archive
status: archived          # 或 checkpoint（對話仍在進行中）
domain: {{主要領域}}
created: {{對話開始日期 YYYY-MM-DD}}
archived: {{封存日期 YYYY-MM-DD}}
part: {{N/M}}             # 僅多段時使用，如 1/3
tags: [tag1, tag2, ...]
source: {{平台}}          # claude-ai, hermes-discord, hermes-cli, slack, etc.
related_domains: [domain1, domain2]
related_conversations:    # 同一叢集的其他封存檔標題或 ID
  - {{相關封存檔 1}}
  - {{相關封存檔 2}}
---
```

## 各區塊規範

### 脈絡（~50 字）
1-2 句話。這串對話在幹嘛、從什麼問題出發。

### 發展軌跡（~300 字，唯一允許彈性的區塊）
用 A → B → C 箭頭連接概念節點。寫「怎麼走的」，不只是「走到哪」。
這是整份摘要裡資訊密度最高的區塊——結論可以從產出物看到，推導過程只存在這裡。

不好的：「討論了 kanban 系統。」
好的：「從 Paperclip 的 heartbeat 模式出發 → 發現輪詢太耗 token →
引入 event-driven 的 Monitor 機制 → 映射到 Hook/Monitor/Scheduled 三種觸發類型。」

### 關鍵概念（~150 字）
只記錄這串對話裡**誕生的**新概念，不記錄**引用的**既有概念。
格式：`- **概念名稱**：一句話定義`

### 決議（~100 字）
明確的決策。用「決定了」而非「討論了」。
格式：`- 決定 X`

### 產出物（~100 字）
最終版檔案的壓縮列表。不列中間版本。不用樹狀結構。
格式：`- 檔案名 — 一句話說明用途`

### 關鍵字（~50 字）
扁平的 tag 列表，覆蓋主要概念。RAG embedding 的主要匹配面。

### 對話全文
```markdown
## 對話全文

<details>
<summary>展開原始對話（本段範圍）</summary>

H: 使用者的訊息...

A: Agent 的回應...

H: ...

</details>
```

## 生成規則

1. **整體摘要不超過 ~800 字。** 超過表示應該做 session split。
2. **產出物用壓縮列表，不用樹狀結構。** 字數是稀缺資源。
3. **關鍵概念只列「誕生的」不列「引用的」。** 如果 BDD 是使用者帶進來的既有概念，不列。
4. **決議用肯定句。** 「決定用 Textual 做 TUI」而非「討論了 Textual 框架」。
5. **對話全文放在 `<details>` 折疊裡。** RAG 只 embed 摘要，全文作為 deep retrieval 備用。
6. **多段封存時，每份的 related_conversations 互相指向。** 形成可導航的對話叢集。

## 格式驗證檢查清單

生成完成後，用以下清單驗證（可自動化為腳本）：

- [ ] frontmatter 是否有完整的 YAML 語法？
- [ ] type 是否為 `conversation-archive`？
- [ ] tags 是否為陣列格式？
- [ ] 是否包含所有 6 個必要區塊（脈絡、軌跡、概念、決議、產出物、關鍵字）？
- [ ] 對話全文是否被 `<details>` 包裹？
- [ ] 多段時 part 欄位是否正確（N/M 格式）？
- [ ] 多段時 related_conversations 是否互相指向？
