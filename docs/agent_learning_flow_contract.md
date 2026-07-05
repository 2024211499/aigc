# AIGC 教学助手统一学习流协议

## 目标

所有 Agent 和接口围绕同一条学习闭环输出数据：

`资料解析 -> 学情评估 -> 学习路径 -> 讲义图解 -> 当前答疑 -> 练习讲解 -> 测评复盘 -> 学习画像`

前端不要再为每个 Agent 单独猜字段。后端尽量统一返回下面这些结构。

## 课程学习包

用于课程模式首页和学习空间。

```json
{
  "assessment_questions": [
    {
      "id": "foundation",
      "question": "你是否已经掌握组合逻辑基础？",
      "options": ["已熟练掌握", "了解基本概念，但不熟练", "完全没有接触过"]
    }
  ],
  "learning_units": [
    {
      "unit_id": "unit-2",
      "day": 2,
      "title": "NOR 门 SR 锁存器",
      "short_title": "SR 锁存器",
      "type": "lecture",
      "summary": "理解交叉耦合 NOR 门、保持、置位、复位和非法状态。",
      "estimated_minutes": 45,
      "status": "active",
      "lecture_sections": [],
      "quiz": {}
    }
  ],
  "learning_actions": [
    {
      "title": "资料变课程",
      "description": "解析上传材料，拆出章节、知识点和先修关系。"
    }
  ]
}
```

## 讲义内容

用于学习空间正文。

```json
{
  "lecture_sections": [
    {
      "title": "精准定义",
      "type": "text",
      "content": "SR 锁存器是一种最基本的异步时序电路。"
    },
    {
      "title": "结构图",
      "type": "diagram",
      "diagram_kind": "logic_circuit",
      "content": {
        "nodes": [],
        "edges": []
      }
    },
    {
      "title": "功能真值表",
      "type": "table",
      "headers": ["S", "R", "Q 当前", "Q 下一状态", "说明"],
      "rows": [
        ["0", "0", "0/1", "保持", "状态不变"]
      ]
    }
  ],
  "references": [
    {
      "source": "上传课件",
      "page": 12,
      "quote": "锁存器由两个交叉耦合门构成。"
    }
  ]
}
```

## 当前内容答疑

用于学习空间右侧或底部答疑。

```json
{
  "answer": {
    "summary": "先看输入条件，再用 NOR 门规则推导输出。",
    "steps": ["判断 S/R 输入", "代入 NOR 规则", "检查 Q 与 Q' 是否互补"],
    "diagram_hint": "可生成 SR 锁存器状态转移图",
    "common_mistakes": ["把保持状态误认为输出为 0", "忽略 S=R=1 的非法状态"]
  },
  "followups": ["没听懂", "继续", "功能真值表是什么？", "帮我生成同类题"]
}
```

## 练习与测评

用于题库、错题、组卷。

```json
{
  "practice_set": {
    "unit_id": "unit-2",
    "questions": [
      {
        "id": "q1",
        "type": "choice",
        "stem": "SR 锁存器在 S=1, R=0 时输出 Q 为多少？",
        "options": ["0", "1", "保持", "非法"],
        "answer": "1",
        "explanation": "S=1 会强制置位，因此 Q=1。",
        "knowledge_points": ["SR 锁存器", "置位"]
      }
    ]
  }
}
```

## 学习画像

用于“我的学习”。

```json
{
  "profile": {
    "mastery": 72,
    "weak_points": [
      {
        "name": "SR 锁存器非法状态",
        "mastery": 45,
        "next_action": "复习功能真值表并完成 3 道同类题"
      }
    ],
    "today_actions": ["复盘 3 道错题", "完成当前单元测验", "追问一个没听懂的点"]
  }
}
```

## Agent 分工建议

- RAG：负责材料解析、引用来源、检索片段。
- 课程结构 Agent：负责章节和学习单元。
- 学习计划 Agent：负责每日任务和节奏。
- 讲解 Agent：负责讲义、图解、表格、公式推导。
- 答疑 Agent：负责带上下文追问。
- 习题 Agent：负责练习题和解析。
- 测评 Agent：负责组卷、评分、知识点覆盖。
- 画像 Agent：负责薄弱点、复习建议和下一步行动。
- 质量审核 Agent：负责检查字段完整性、难度是否匹配、是否有引用。
