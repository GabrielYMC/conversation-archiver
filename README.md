# Conversation Archiver

**對話封存服務——把任意對話串轉換成結構化 Markdown 知識資產**

```
conversation-archiver/
├── SKILL.md                          ← Hermes/Claude Code skill 進入點
├── README.md
├── references/
│   └── archive-schema.md            ← 封存格式快速參考
└── scripts/
    ├── archiver.py                  ← 主要封存腳本
    └── validate_archive.py          ← 格式驗證（不需要 LLM）
```

## 這是什麼？

輸入任意對話串（文字、JSON、Markdown），輸出結構化的 .md 封存檔。

每份封存檔包含：
- **摘要**（~800 字）：frontmatter + 脈絡 + 發展軌跡 + 關鍵概念 + 決議 + 產出物 + 關鍵字
- **對話全文**：折疊收納在 `<details>` 裡，需要時展開

對話太長時自動偵測斷點、建議拆分、生成多份檔案。

## 快速開始

```bash
# 安裝依賴
pip install httpx

# 確保 Ollama 正在運行且有模型
ollama pull gemma4:31b    # 或你有的任何模型

# 封存一串對話
python scripts/archiver.py --input my-conversation.txt

# 指定模型和輸出目錄
python scripts/archiver.py --input chat.json --model gemma4:e4b --output ./archives/

# 只看建議的斷點，不生成檔案
python scripts/archiver.py --input chat.txt --dry-run

# 驗證已生成的封存檔
python scripts/validate_archive.py ./archives/*.md
```

## 輸入格式

支援三種格式，自動偵測：

**H:/A: 格式（最常見）**
```
H: 你好，我想討論架構設計
A: 好的，讓我們從需求開始...
```

**JSON 格式（Claude/Hermes 匯出）**
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

**Markdown 格式**
```
**User:** 你好
**Assistant:** 好的...
```

## 模型選擇

| 你有的資源 | 建議用法 |
|---|---|
| Ollama + Gemma 4 31B | 最佳選擇。31B 夠強、context 夠長 |
| Ollama + Gemma 4 E4B | 短對話可以。長對話可能受 context 限制 |
| Google AI Studio (免費) | 透過 API 呼叫，設定 `LLM_API_BASE` 環境變數 |
| 其他 Ollama 模型 | 任何 instruction-following 模型都行，`--model 模型名` |

## 與 agent-commons 的關係

本 skill 實作了 [agent-commons](link) 的 `conversation-archive` protocol。
`references/archive-schema.md` 是該 protocol 的操作指南版本。

## 授權

MIT
