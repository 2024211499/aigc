# AIGC 智能学习资源生成平台

> 面向大学生学习与教师备课的 AI 辅助平台。上传教材 PDF/Word/PPT，自动解析建库，生成个性化学习包、分层讲解、习题、试卷、微课脚本等内容。

---

## 目录

- [项目结构](#项目结构)
- [四模块架构](#四模块架构)
- [快速开始](#快速开始)
- [环境变量配置](#环境变量配置)
- [API 接口总览](#api-接口总览)
- [数据库表说明](#数据库表说明)
- [已知问题与待办](#已知问题与待办)

---

## 项目结构

```
aigc-platform/
├── rag/                        # 1号模块：文档解析 & RAG 检索
│   ├── config.py               # 分块/提取/检索配置类（根目录）
│   ├── exceptions.py           # 统一异常体系（根目录）
│   ├── models.py               # 数据模型 CleanStats / PageParseResult / RetrievalHit（根目录）
│   ├── processing/             # 文本清洗、章节结构识别、分块、分片
│   │   ├── cleaners.py         #   清洗函数（OCR 去噪、数学符号规整）
│   │   ├── structure.py        #   章节检测、块分类、课程目录构建
│   │   ├── splitter.py         #   文本分片（结构感知）
│   │   └── chunking.py         #   分块元数据构建
│   ├── knowledge/              # 知识点抽取与标注
│   │   └── extractor.py        #   知识点/公式/例题/难度抽取
│   ├── storage/                # 持久化
│   │   ├── sqlite.py           #   CourseDB（SQLite 课程库）
│   │   ├── vector_store.py     #   ChromaDB 向量库封装
│   │   └── course_index.py     #   向量索引管理（CRUD）
│   ├── parsing/                # 多格式文档解析 & OCR
│   │   ├── document_parser.py  #   统一解析入口（PDF/DOCX/PPTX/图片）
│   │   ├── pdf_parser.py       #   PDF 专项（含 OCR 回退）
│   │   ├── docx_parser.py      #   Word 解析
│   │   ├── pptx_parser.py      #   PPT 解析
│   │   ├── image_parser.py     #   图片解析
│   │   ├── ocr_backends.py     #   OCR 后端适配（本地/在线）
│   │   ├── ocr_cache.py        #   OCR 缓存
│   │   ├── ocr_helper.py       #   OCR 工具函数
│   │   └── image_preprocess.py #   图像预处理
│   ├── retrieval/              # 向量检索 & 混合召回
│   │   ├── embeddings.py       #   Embedding 提供者（本地/OpenAI/GTE）
│   │   ├── retriever.py        #   混合检索器（向量 + 关键词）
│   │   ├── rag.py              #   retrieve / hybrid_search / rerank
│   │   └── reranker.py         #   重排序
│   ├── graph/                  # 知识图谱
│   │   └── graph.py
│   ├── pipeline/               # 文档入库流水线
│   │   ├── pipeline.py         #   index_document / reparse / delete
│   │   └── index_manager.py    #   IndexManager（兼容旧调用方式）
│   ├── reporting/              # 解析报告
│   │   ├── reporting.py
│   │   └── export.py
│   ├── utils/                  # 工具
│   │   ├── llm_client.py
│   │   ├── study_plan.py
│   │   └── download_model.py
│   └── tests/                  # 单元/集成测试
│
├── agents/                     # 2号模块：14个智能体 + 编排层
│   ├── __init__.py
│   ├── agents/
│   │   ├── orchestrator_agent.py       # 编排总控（含意图识别）
│   │   ├── planner_agent.py
│   │   ├── keypoint_agent.py
│   │   ├── explanation_agent.py
│   │   ├── exercise_agent.py
│   │   ├── exam_agent.py
│   │   ├── mistake_diagnosis_agent.py
│   │   ├── profile_agent.py
│   │   ├── micro_lesson_agent.py
│   │   ├── ppt_agent.py
│   │   ├── homework_tutor_agent.py
│   │   ├── knowledge_graph_agent.py
│   │   ├── adaptive_path_agent.py
│   │   ├── course_structure_agent.py
│   │   └── quality_review_agent.py
│   └── core/
│       ├── llm_client.py       # LLM 调用封装（DeepSeek/OpenAI 兼容）
│       ├── models.py           # Pydantic 数据模型
│       ├── memory_manager.py
│       └── crew_config.py
│
├── backend/                    # 3号模块：FastAPI 后端服务
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py     # SQLAlchemy 模型（17张表）
│   │   │   ├── exceptions.py
│   │   │   └── logger.py
│   │   ├── api/
│   │   │   ├── upload.py
│   │   │   ├── courses.py
│   │   │   ├── learning_package.py
│   │   │   ├── explanation.py
│   │   │   ├── exercises.py
│   │   │   ├── mistakes.py
│   │   │   ├── exam.py
│   │   │   ├── export.py       # 导出（PDF/Word/Markdown，含中文渲染）
│   │   │   ├── micro_lesson.py
│   │   │   ├── profile.py
│   │   │   └── dashboard.py
│   │   ├── agents/
│   │   │   └── bridge.py       # 2号模块桥接层（含降级 LLM 直调）
│   │   └── rag/
│   │       └── bridge.py       # 1号模块桥接层（含降级关键词检索）
│   ├── tests/
│   │   └── test_api.py         # 全接口集成测试（缓存 + 智能重试）
│   └── run.py
│
└── frontend/                   # 4号模块：Vue 3 前端（纯 UI，待联调）
    ├── src/
    │   ├── views/
    │   │   ├── Home.vue            # 首页（功能介绍 + 使用流程）
    │   │   ├── Library.vue         # 资料库（文档上传 + 列表 + 解析状态）
    │   │   ├── Learning.vue        # 学习中心（章节目录 + 知识点展示）
    │   │   ├── Exercise.vue        # 习题/错题本（双路由复用）
    │   │   ├── Profile.vue         # 学习画像（ECharts 雷达图 + 薄弱点）
    │   │   ├── AnalysisReport.vue  # AI 解析报告
    │   │   ├── KnowledgeGraph.vue  # 知识图谱（ECharts 关系图）
    │   │   ├── Exam.vue            # 智能组卷（占位，待实现）
    │   │   └── Dashboard.vue       # 教师看板（占位，待实现）
    │   ├── api/
    │   │   └── index.js            # fetch 封装（自动处理 JSON/Blob，统一报错）
    │   ├── utils/
    │   │   └── storage.js          # localStorage 工具（course/doc/plan/exam ID）
    │   ├── router/
    │   │   └── index.js            # Vue Router 路由表
    │   ├── App.vue
    │   └── main.js
    ├── index.html
    ├── vite.config.js              # 开发代理：/api → http://localhost:8000
    └── package.json
```

---

## 四模块架构

```
┌─────────────────────────────────────────────────────────────┐
│           Vue 3 前端（4号）· localhost:5173                  │
│  Home / Library / Learning / Exercise / Profile / …         │
│  vite proxy: /api  →  localhost:8000                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP /api/*
┌──────────────────────────▼──────────────────────────────────┐
│                  FastAPI 后端（3号）                          │
│  /api/*  →  api/  →  agents/bridge  →  agents/（2号）       │
│                  →  rag/bridge     →  rag/（1号）            │
│                  →  database（SQLite）                       │
└─────────────────────────────────────────────────────────────┘
         ↑ 降级策略：2号/1号不可用时均有内置 LLM/关键词兜底
```

- **1号 RAG 模块**：文档解析 → 结构感知分块 → ChromaDB 向量化 → 混合检索
- **2号 Agent 模块**：OrchestratorAgent 按意图路由到对应功能智能体，每个智能体独立调用 LLM
- **3号 后端模块**：FastAPI + SQLite，负责持久化、接口聚合、桥接 1号与 2号
- **4号 前端模块**：Vue 3 + Vite + Vue Router + ECharts，纯 UI 已完成，待与后端联调

---

## 快速开始

### 前置要求

- Python **3.10 – 3.12**（Agent 模块部分依赖尚不支持 3.13+，推荐使用 3.12）
- pip

### 一键建立虚拟环境

项目提供两个脚本，会自动完成：创建 `.venv` → 升级 pip → 安装 `requirements.txt`。

**Windows（PowerShell）**

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**Linux / macOS / WSL**

```bash
bash setup.sh
```

脚本执行完毕后按提示激活环境，再进行后续步骤。

> **手动方式**（如需精细控制，请确认 `python` 指向 3.10–3.12）
>
> ```bash
> python -m venv .venv
> # Windows
> .venv\Scripts\activate
> # Linux / macOS
> source .venv/bin/activate
>
> pip install --upgrade pip
> pip install -r requirements.txt
> ```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY 等
```

### 启动后端

```bash
# 确保虚拟环境已激活
cd backend
python run.py
# 或
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 `http://localhost:8000/docs` 查看 Swagger 文档。

### 启动前端

> **前置要求**：Node.js 18+

```bash
cd frontend
npm install      # 首次安装依赖
npm run dev      # 启动开发服务器
```

访问 `http://localhost:5173` 查看前端页面。

前端通过 Vite 的开发代理将 `/api/*` 转发到 `http://localhost:8000`，**需要同时启动后端**才能完成联调。

> **当前状态**：前端 UI 已实现（使用 mock 数据），尚未全面对接后端接口。各页面的后端联调进度见下方[前端页面说明](#前端页面说明)。

---

## 环境变量配置

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```ini
# ── LLM（DeepSeek / 任意 OpenAI 兼容接口）────────────────────
OPENAI_API_KEY=sk-xxxx
OPENAI_API_BASE=https://api.deepseek.com   # 不要加 /v1，bridge.py 会自动补全
LLM_MODEL_NAME=deepseek-v4-flash

# ── Embedding（SiliconFlow BAAI/bge-m3）──────────────────────
EMBEDDING_API_KEY=sk-xxxx
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3

# ── 数据库 ────────────────────────────────────────────────────
# 默认使用 backend/data/aigc.db（SQLite），无需修改

# ── 文件上传 ──────────────────────────────────────────────────
MAX_UPLOAD_SIZE=104857600   # 100MB

# ── CORS（生产环境必须配置）──────────────────────────────────
# CORS_ORIGINS=http://localhost:3000,http://your-frontend.com
```

---

## API 接口总览

基础路径：`/api`

### 📁 文件上传与解析

| 方法     | 路径                        | 说明                            |
|--------|---------------------------|-------------------------------|
| POST   | `/upload`                 | 上传文档（PDF/Word/PPT/TXT），触发后台解析 |
| GET    | `/documents/{id}/status`  | 查询解析状态                        |
| GET    | `/documents/{id}/report`  | 获取解析报告                        |
| POST   | `/documents/{id}/reparse` | 重新触发解析                        |
| DELETE | `/documents/{id}`         | 删除文档及关联数据                     |
| GET    | `/documents`              | 获取文档列表（可按课程筛选）                |

**解析状态流转：** `uploaded → parsing → chunking → embedding → completed / failed`

### 📚 课程与章节

| 方法   | 路径                                | 说明            |
|------|-----------------------------------|---------------|
| GET  | `/courses`                        | 获取课程列表        |
| POST | `/courses`                        | 创建课程          |
| GET  | `/courses/{id}`                   | 获取课程详情（含章节列表） |
| GET  | `/courses/{id}/chapters`          | 获取章节目录        |
| GET  | `/courses/{id}/knowledge-points`  | 获取全课知识点       |
| GET  | `/courses/{id}/study-plans`       | 获取课程学习计划列表    |
| GET  | `/courses/{id}/graph`             | 获取知识图谱        |
| GET  | `/chapters/{id}`                  | 章节详情          |
| GET  | `/chapters/{id}/knowledge-points` | 章节下的知识点       |

### 🎓 学习包生成

| 方法   | 路径                           | 说明                    |
|------|------------------------------|-----------------------|
| POST | `/learning-package/generate` | 生成完整学习包（计划 + 重点 + 习题） |
| POST | `/plan/generate`             | 单独生成学习计划              |
| GET  | `/study-plans/{id}`          | 获取学习计划详情              |

### 💡 智能讲解

| 方法   | 路径                      | 说明        |
|------|-------------------------|-----------|
| POST | `/explanation/generate` | 生成知识点分层讲解 |

支持讲解风格：`zero_basic` / `textbook` / `exam` / `derivation` / `analogy` / `blackboard` / `lecture_script`

### 📝 习题与答题

| 方法   | 路径                         | 说明                |
|------|----------------------------|-------------------|
| POST | `/exercises/generate`      | 生成习题集             |
| GET  | `/exercises/{id}`          | 获取题目详情            |
| POST | `/exercises/submit`        | 提交答案（自动判题 + 错题诊断） |
| POST | `/exercises/{id}/explain`  | 查看题目解析            |
| POST | `/exercises/{id}/variants` | 生成变式题             |
| POST | `/homework/tutor`          | 作业辅导（逐步引导）        |
| POST | `/homework/diagnose`       | 上传解答并诊断           |

### ❌ 错题本

| 方法    | 路径                        | 说明                     |
|-------|---------------------------|------------------------|
| GET   | `/mistakes`               | 获取错题列表（`?user_id=xxx`） |
| POST  | `/mistakes/{id}/review`   | 复习错题                   |
| POST  | `/mistakes/{id}/variants` | 生成变式题                  |
| PATCH | `/mistakes/{id}/mastered` | 标记已掌握                  |

### 📋 智能组卷

| 方法   | 路径                      | 说明     |
|------|-------------------------|--------|
| POST | `/exam/generate`        | 生成试卷   |
| GET  | `/exam/{id}`            | 获取试卷详情 |
| POST | `/exam/{id}/regenerate` | 重新生成试卷 |

### 📤 导出服务

| 方法   | 路径                              | 说明                                      |
|------|---------------------------------|-----------------------------------------|
| POST | `/export/study-plan/{id}`       | 导出学习计划（`format: pdf/docx`）              |
| POST | `/export/exam/{id}`             | 导出试卷（`version: student/teacher`，教师版含答案） |
| POST | `/export/exercises/{course_id}` | 导出课程习题集                                 |
| POST | `/export/markdown/{plan_id}`    | 导出学习计划为 Markdown                        |

> 导出内容全部使用中文标签渲染，不含 JSON 原始字段名。

### 🎬 微课生成

| 方法   | 路径                            | 说明                                 |
|------|-------------------------------|------------------------------------|
| POST | `/micro-lesson/script`        | 生成微课脚本                             |
| POST | `/micro-lesson/ppt`           | 生成 PPT 内容结构                        |
| POST | `/micro-lesson/tts`           | 生成语音（占位）；`lesson_id` 为 query param |
| POST | `/micro-lesson/video`         | 合成视频（占位）；`lesson_id` 为 query param |
| GET  | `/micro-lesson/{id}`          | 获取微课详情                             |
| GET  | `/micro-lesson/{id}/download` | 获取微课文件下载链接                         |

### 👤 学习画像

| 方法   | 路径                   | 说明        |
|------|----------------------|-----------|
| GET  | `/profile/{user_id}` | 获取/生成学习画像 |
| POST | `/profile/update`    | 更新画像附加数据  |
| POST | `/learning-log`      | 记录学习行为    |

### 📊 数据看板

| 方法  | 路径                               | 说明    |
|-----|----------------------------------|-------|
| GET | `/dashboard/student/{user_id}`   | 学生端看板 |
| GET | `/dashboard/teacher/{course_id}` | 教师端看板 |

---

## 数据库表说明

共 17 张表（SQLite，路径：`backend/data/aigc.db`）：

| 表名                 | 说明       | 写入时机                                |
|--------------------|----------|-------------------------------------|
| `users`            | 用户表      | ⚠️ 暂无注册接口，当前 user_id 均为 "anonymous" |
| `courses`          | 课程表      | 上传文档时自动创建，或手动 POST /courses         |
| `documents`        | 文档表      | 上传文档时创建                             |
| `chapters`         | 章节表      | 文档解析完成后自动写入                         |
| `knowledge_points` | 知识点表     | 文档解析完成后写入                           |
| `fragments`        | RAG 文本片段 | 文档解析分块后写入                           |
| `study_plans`      | 学习计划     | 调用学习包/学习计划生成接口后写入                   |
| `exercises`        | 习题表      | 调用习题生成接口后写入                         |
| `answer_records`   | 答题记录     | 提交答案时写入                             |
| `mistakes`         | 错题表      | 答题错误时自动写入                           |
| `exam_papers`      | 试卷表      | 调用组卷接口后写入                           |
| `video_lessons`    | 微课表      | 调用微课脚本接口后写入                         |
| `export_files`     | 导出文件记录   | 每次导出时写入                             |
| `learning_logs`    | 学习行为日志   | 调用 /learning-log 接口时写入              |
| `parse_tasks`      | 解析异步任务   | ⚠️ 表已定义，暂未使用                        |
| `generate_tasks`   | 生成异步任务   | ⚠️ 表已定义，暂未使用                        |
| `user_profiles`    | 学习画像     | 调用画像接口时写入/更新                        |

---

## 已知问题与待办

### 🔴 已修复

| 问题                                                       | 位置                                                  | 修复说明                                                                      |
|----------------------------------------------------------|-----------------------------------------------------|---------------------------------------------------------------------------|
| `VectorStore` 构造函数参数错误                                   | `backend/app/rag/bridge.py`                         | 改用 `VectorStoreConfig` 对象传参                                               |
| `generate_profile` 传入空数据                                 | `backend/app/agents/bridge.py`                      | 聚合统计字段映射为 profile_agent 所需格式                                              |
| CORS `allow_origins=["*"]` + `allow_credentials=True` 冲突 | `backend/app/main.py`                               | 改为 `CORS_ORIGINS` 环境变量控制                                                  |
| 2号 Agent 模块相对导入报错                                        | `agents/__init__.py`、`backend/app/agents/bridge.py` | 创建 `agents/__init__.py`，bridge.py 改全路径导入                                  |
| AI 生成接口全部超时                                              | `backend/app/agents/bridge.py`                      | `_call_llm()` 加 `timeout=50.0`；max_tokens 降至 800–900                      |
| `knowledge_points` 表不写入                                  | `backend/app/api/upload.py`                         | 解析后自动保存知识点行                                                               |
| 缺少 `/api/export/exercises` 接口                            | `backend/app/api/export.py`                         | 新增课程习题集导出                                                                 |
| 缺少课程级知识点查询接口                                             | `backend/app/api/courses.py`                        | 新增 `GET /courses/{id}/knowledge-points`                                   |
| 删除/重解析文档未清理 KP 数据                                        | `backend/app/api/upload.py`                         | delete / reparse 均先删 KnowledgePoint 再删 Chapter                            |
| `generate_student_profile()` 参数名全部错误                     | `agents/agents/orchestrator_agent.py`               | 修正 3 处调用点的 kwargs 与函数签名一致                                                 |
| `generate_exercises()` 参数名全部错误                           | `agents/agents/orchestrator_agent.py`               | 修正 2 处调用点，`student_level/weak_points` → `student_profile/wrong_questions` |
| `HomeworkTutorResponse.error_analysis` Pydantic 验证失败     | `agents/core/models.py`                             | `ErrorAnalysis` → `Optional[ErrorAnalysis]`                               |
| 1号 RAG 模块启动报 `No module named 'rag.processing.models'`   | `rag/processing/cleaners.py`                        | `from .models` → `from ..models`                                          |
| 1号 RAG 模块启动报 `No module named 'rag.parsing.exceptions'`  | `rag/parsing/ocr_backends.py`                       | `from .exceptions` → `from ..exceptions`                                  |
| `processing/structure.py` 导入 `storage` 失败                | `rag/processing/structure.py`                       | `from .storage` → `from ..storage.sqlite`                                 |
| 导出文件包含 JSON 原始字段名和 JSON 数据块                              | `backend/app/api/export.py`                         | 统一 `_KEY_LABELS` 中文映射 + `_flatten_to_lines` 递归展开，彻底消除 `json.dumps` 输出     |
| 微课 TTS/视频接口 422（`lesson_id` 参数位置错误）                      | `backend/tests/test_api.py`                         | 改为 `params={"lesson_id": ...}` 传 query string                             |

### 🟡 待修复（已知问题）

| 优先级 | 问题                                                 | 位置                                | 建议                                         |
|-----|----------------------------------------------------|-----------------------------------|--------------------------------------------|
| 高   | 无用户认证，所有接口公开                                       | 全局                                | 添加 JWT 认证；`POST /register` / `POST /login` |
| 中   | `StaticPool` 与后台线程共用一个 SQLite 连接，高并发可能死锁           | `backend/app/core/database.py`    | 改为 `NullPool` 或换用 PostgreSQL               |
| 中   | `parse_tasks` / `generate_tasks` 表未使用，长时任务无法跟踪进度   | `backend/app/api/upload.py`       | 改用 Celery / ARQ                            |
| 中   | 知识点写入用正则，语义不准                                      | `backend/app/api/upload.py`       | 接入 1号 `knowledge.extractor`                |
| 中   | 分块仍为固定 800 字切割，未利用章节边界                             | `backend/app/api/upload.py`       | 调用 `rag.processing.splitter` 结构感知分块        |
| 低   | `UserProfile` `unique=True` 约束，并发可能 IntegrityError | `backend/app/api/profile.py`      | 改用 upsert                                  |
| 低   | TTS / 视频合成为占位实现                                    | `backend/app/api/micro_lesson.py` | 接入 Edge-TTS、Azure TTS 或讯飞                  |
| 低   | 无 LLM 调用频率限制                                       | `backend/app/agents/bridge.py`    | 添加 token bucket 或 tenacity 限速              |

### 🟢 后续扩展方向

- **用户系统**：注册/登录/权限（学生/教师角色隔离）
- **前端联调**：Vue 前端 UI 已就绪，需将 mock 数据替换为真实 API 调用（优先级：Library → Learning → Exercise → Profile）
- **异步任务队列**：Celery + Redis，解决长时生成任务阻塞
- **流式输出**：LLM 生成时 SSE 推送进度
- **向量检索升级**：将 Embedding 切换到 SiliconFlow BAAI/bge-m3（openai v1.x API）
- **生产部署**：换 PostgreSQL + pgvector

---

## 前端页面说明

技术栈：**Vue 3 + Vite 8 + Vue Router 4 + ECharts 6**，端口 `5173`，通过 Vite proxy 对接后端。

| 路由               | 组件              | 功能                       | 联调状态   |
|------------------|-----------------|--------------------------|--------|
| `/`              | `Home.vue`      | 首页（平台介绍、使用流程引导）          | —      |
| `/library`       | `Library.vue`   | 资料库：文档上传、解析状态轮询、文档列表     | 🔧 待联调 |
| `/learning`      | `Learning.vue`  | 学习中心：章节目录侧边栏、知识点展示       | 🔧 待联调 |
| `/microlesson`   | `Learning.vue`  | 微课入口（暂复用学习页）             | 🔧 待联调 |
| `/exercise`      | `Exercise.vue`  | 题库与辅导（mock 数据占位）         | 🔧 待联调 |
| `/mistakes`      | `Exercise.vue`  | 错题本（与题库复用同一组件，路由区分）      | 🔧 待联调 |
| `/profile`       | `Profile.vue`   | 学习画像（ECharts 雷达图、薄弱点进度条） | 🔧 待联调 |
| `/exam`          | `Exam.vue`      | 智能组卷（空壳，待实现）             | ⬜ 未开始  |
| `/teacher-board` | `Dashboard.vue` | 教师看板（空壳，待实现）             | ⬜ 未开始  |

`src/api/index.js` 已封装统一 `fetch` 请求层（自动区分 JSON/文件流响应）；`src/utils/storage.js` 提供 `course_id / doc_id / plan_id / exam_id` 的 localStorage 快捷读写。

---

## 开发说明

### IDE 导入配置（VS Code / Cursor / PyCharm）

#### Python 后端（1–3号模块）

项目根目录提供 `pyrightconfig.json`，覆盖 `agents/`、`rag/`、`backend/` 三个 Python 子包，并显式排除前端与虚拟环境目录：

```json
{
  "pythonVersion": "3.12",
  "include": ["agents", "rag", "backend"],
  "exclude": [".venv", "frontend", "**/node_modules", "**/__pycache__"],
  "extraPaths": ["."],
  "reportMissingImports": false,
  "reportMissingModuleSource": false
}
```

> `extraPaths: ["."]` 使三个模块可以互相用绝对路径导入（如 `from rag.config import ...`），无需在每个子包再配置 sys.path。

#### Vue 前端（4号模块）

`frontend/` 目录提供 `jsconfig.json`，为 VS Code / Cursor 提供路径别名解析与 Vue 单文件组件支持：

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] },
    "jsx": "preserve",
    "jsxImportSource": "vue",
    "moduleResolution": "bundler"
  },
  "include": ["src/**/*.js", "src/**/*.vue", "vite.config.js"],
  "exclude": ["node_modules", "dist"]
}
```

> Vite 运行时的路径别名需在 `vite.config.js` 中同步配置 `resolve.alias`（如需使用 `@/` 前缀）。

### 运行测试

`backend/tests/test_api.py` 是全接口集成测试脚本，**需要先启动服务**再运行：

```bash
# 第一步：启动后端服务
cd backend
python run.py

# 第二步：另开终端运行测试
cd backend
python tests/test_api.py                      # 首次运行（LLM 接口结果写入缓存）
python tests/test_api.py                      # 再次运行（已通过项读缓存，秒级完成）
python tests/test_api.py --refresh            # 清空缓存，强制全量重跑
python tests/test_api.py --refresh 微课        # 仅重跑名称含"微课"的项
python tests/test_api.py --base http://x:8000 # 指定非默认地址
```

> 测试缓存文件默认落在 `backend/tests/test_cache.json`（与脚本同目录），不受 `cd` 路径影响。

**超时分级：**

| 常量       | 值    | 适用接口                       |
|----------|------|----------------------------|
| `T_FAST` | 30s  | 纯查询、CRUD                   |
| `T_MED`  | 60s  | 上传、导出、重解析                  |
| `T_AI`   | 240s | 所有 LLM 生成接口（最多重试 2 次，指数退避） |

> ⚠️ 不要用 `pytest` 直接运行此文件，它是独立可执行脚本，不是 pytest 格式。

### 查看 API 文档

启动服务后访问：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 1号 RAG 模块子包结构

`rag/` 已从扁平结构重组为子包，各子包职责独立，内部使用相对导入（`from ..config import ...`）：
- 根目录仅保留 `config.py`、`exceptions.py`、`models.py` 三个跨包公共文件
- 垫片文件（`rag/cleaners.py` 等）已删除，后端通过 `rag.processing.cleaners` 等子包路径直接引用
- 如升级后出现 `ModuleNotFoundError`，在项目根目录执行 `cleanup_rag_shims.ps1` 清理旧 `__pycache__`

---

## 团队分工

| 模块                     | 负责人  | 主要技术                                                                |
|------------------------|------|---------------------------------------------------------------------|
| 1号 RAG 模块（`rag/`）      | 1号队员 | PyMuPDF · pdfplumber · PaddleOCR · ChromaDB · sentence-transformers |
| 2号 Agent 模块（`agents/`） | 2号队员 | DeepSeek · OpenAI API · Pydantic · 多 Agent 编排                       |
| 3号 后端模块（`backend/`）    | 3号队员 | FastAPI · SQLAlchemy · SQLite · python-docx · reportlab             |
| 4号 前端模块（`frontend/`）   | 4号队员 | Vue 3 · Vite · Vue Router · ECharts                                 |
