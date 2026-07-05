#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIGC 后端全接口测试脚本（带本地缓存 + 智能重试）
覆盖所有接口，共 13 节 48 项。

用法：
    python tests/test_api.py                     # 首次运行 / 跳过已通过项
    python tests/test_api.py --refresh           # 清空缓存，重跑全量
    python tests/test_api.py --refresh 微课       # 仅重跑名称含"微课"的项
    python tests/test_api.py --base http://x:8000
    python tests/test_api.py --cache my.json     # 指定缓存文件路径

缓存机制：
    - 通过的测试结果（含响应 body）写入 JSON 缓存文件
    - 再次运行时，已通过项直接读缓存，不重发请求（对耗时 LLM 接口尤其有用）
    - --refresh 可强制全量或按关键字局部刷新

超时 & 重试策略：
    - T_FAST (30s) ：纯查询、CRUD
    - T_MED  (60s) ：上传、导出、重解析
    - T_AI  (240s) ：所有 LLM 生成接口，最多重试 2 次
    - 重试触发条件：网络超时 / 5xx / 429
    - 重试间隔：指数退避（5s → 10s → 20s）
"""

import argparse
import json
import os
import sys
import tempfile
import time

import requests
from requests.exceptions import Timeout, ConnectionError as ReqConnError

# ─── 命令行参数 ──────────────────────────────────────────────
parser = argparse.ArgumentParser()
_DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cache.json")

parser.add_argument("--base",  default="http://localhost:8000", help="后端地址")
parser.add_argument("--cache", default=_DEFAULT_CACHE,          help="缓存文件路径（默认与脚本同目录）")
parser.add_argument(
    "--refresh", nargs="?", const="ALL", default=None,
    help="清除缓存重跑；不加参数=全量；加关键字=仅匹配项",
)
args = parser.parse_args()
BASE       = args.base.rstrip("/")
CACHE_FILE = args.cache

# ─── 超时分级 ────────────────────────────────────────────────
T_FAST = 30    # 纯查询、CRUD
T_MED  = 60    # 上传、导出、重解析
T_AI   = 240   # LLM 生成接口

# ─── 缓存 I/O ────────────────────────────────────────────────
def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_cache(c: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)

cache = _load_cache()

if args.refresh == "ALL":
    cache = {}
    print(f"  🗑  已清空缓存（{CACHE_FILE}）")
elif args.refresh:
    kw      = args.refresh.lower()
    removed = [k for k in list(cache) if k != "_state" and kw in k.lower()]
    for k in removed:
        del cache[k]
    print(f"  🗑  已清除 {len(removed)} 条缓存（关键字: {kw}）")

# 跨测试的 ID 状态（持久化到缓存文件）
_state: dict = cache.get("_state", {})

def _save_state(**kv):
    _state.update({k: v for k, v in kv.items() if v})
    cache["_state"] = _state
    _save_cache(cache)

# ─── 输出符号 ────────────────────────────────────────────────
PASS  = "✅"
FAIL  = "❌"
HIT   = "📦"
RETRY = "↺"

_results: list[tuple[str, bool, bool]] = []   # (name, ok, from_cache)
_RETRY_CODES = {429, 500, 502, 503, 504}

# ─── 测试执行器 ──────────────────────────────────────────────
def test(
    name: str,
    method: str,
    url: str,
    *,
    no_cache: bool = False,
    timeout: int = T_FAST,
    retries: int = 0,
    **kwargs,
) -> tuple[dict, int]:
    """
    发送请求并记录结果。

    参数：
        timeout  - 单次请求超时秒数（建议用预定义常量 T_FAST / T_MED / T_AI）
        retries  - 超时或 5xx 时的最大重试次数（指数退避：5s, 10s, …）
        no_cache - 强制实际请求（上传、删除等幂等性差的接口）
    """
    full_url = f"{BASE}{url}"

    # ── 缓存命中 ──────────────────────────────────────────────
    if not no_cache and name in cache and cache[name].get("ok"):
        body = cache[name].get("body", {})
        code = cache[name].get("code", 200)
        print(f"  {HIT} [cached] {name}")
        _results.append((name, True, True))
        return body, code

    # ── 带重试的请求循环 ──────────────────────────────────────
    last_exc  = None
    last_code = 0
    last_body: dict = {}

    for attempt in range(retries + 1):
        if attempt > 0:
            wait = 5 * (2 ** (attempt - 1))   # 5s, 10s, 20s…
            print(f"    {RETRY} 第 {attempt} 次重试（等待 {wait}s）…")
            time.sleep(wait)

        try:
            resp = getattr(requests, method)(full_url, timeout=timeout, **kwargs)
            code = resp.status_code
            ct   = resp.headers.get("content-type", "")
            body = resp.json() if "application/json" in ct else {}

            if code in _RETRY_CODES and attempt < retries:
                print(f"    {RETRY} [{code}] 将重试…")
                last_code, last_body = code, body
                continue

            ok = code < 400
            suffix = f"（第 {attempt + 1} 次尝试）" if attempt > 0 else ""
            print(f"  {PASS if ok else FAIL} [{code}] {name}{suffix}")
            if not ok:
                print(f"       响应: {json.dumps(body, ensure_ascii=False)[:300]}")
            if ok:
                cache[name] = {"ok": True, "code": code, "body": body}
                _save_cache(cache)
            _results.append((name, ok, False))
            return body, code

        except Timeout as e:
            last_exc = e
            if attempt < retries:
                print(f"    {RETRY} 超时（{timeout}s），将重试…")
            continue
        except ReqConnError as e:
            last_exc = e
            if attempt < retries:
                print(f"    {RETRY} 连接失败，将重试…")
            continue
        except Exception as e:
            print(f"  {FAIL} {name}  →  异常: {e}")
            _results.append((name, False, False))
            return {}, 0

    # 所有重试耗尽
    if last_exc is not None:
        print(f"  {FAIL} {name}  →  超时（{retries + 1} 次尝试均失败，单次限制 {timeout}s）")
    else:
        print(f"  {FAIL} [{last_code}] {name}（重试耗尽）")
        print(f"       响应: {json.dumps(last_body, ensure_ascii=False)[:300]}")
    _results.append((name, False, False))
    return last_body, last_code


# ─── 辅助：从缓存或当前响应取 ID ────────────────────────────
def _id(key: str, body: dict, body_key: str) -> str:
    return (body.get(body_key)
            or _state.get(key)
            or cache.get(key, {}).get("body", {}).get(body_key)
            or "")

# ════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
print("  AIGC 后端全接口测试（缓存版 + 智能重试）")
print(f"  服务：{BASE}    缓存：{CACHE_FILE}")
print("=" * 62)

# ─────────────────────────────────────────────────────────────
# §1  系统
# ─────────────────────────────────────────────────────────────
print("\n【§1 系统健康检查】")
test("根路由",   "get", "/",           timeout=T_FAST)
test("健康检查", "get", "/api/health", timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §2  课程管理
# ─────────────────────────────────────────────────────────────
print("\n【§2 课程管理】")
b, _ = test("创建课程", "post", "/api/courses",
            timeout=T_FAST,
            json={"name": "高等数学", "description": "大学数学基础课程"})
course_id = _id("创建课程", b, "course_id")
_save_state(course_id=course_id)

test("获取课程列表",         "get", "/api/courses",                               timeout=T_FAST)
test("获取课程详情",         "get", f"/api/courses/{course_id}",                  timeout=T_FAST)
test("获取章节目录",         "get", f"/api/courses/{course_id}/chapters",         timeout=T_FAST)
test("获取课程知识点",       "get", f"/api/courses/{course_id}/knowledge-points", timeout=T_FAST)
test("获取课程学习计划列表", "get", f"/api/courses/{course_id}/study-plans",      timeout=T_FAST)
test("获取知识图谱",         "get", f"/api/courses/{course_id}/graph",            timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §3  文件上传与解析
# ─────────────────────────────────────────────────────────────
print("\n【§3 文件上传与解析】")

txt_path = os.path.join(tempfile.gettempdir(), "aigc_test_textbook.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("""\
第一章 函数与极限

1.1 函数

定义：设 x 和 y 是两个变量，D 是一个给定的实数集合。若对每个 x∈D，都有唯一确定的
y 与之对应，则称 y 是 x 的函数，记作 y=f(x)。

定理：若函数 f 在区间 [a,b] 上连续，则 f 在 [a,b] 上可积。

例题 1：求函数 f(x)=x²+2x+1 的导数。
解：f'(x)=2x+2

习题：计算极限 lim(x→0) sin(x)/x

1.2 极限

定义：设函数 f(x) 在点 x₀ 的某个去心邻域内有定义，如果存在常数 A，使得对任意 ε>0，
都存在 δ>0，使得当 0<|x-x₀|<δ 时，有 |f(x)-A|<ε，则称 A 为 f(x) 的极限。

重点：极限运算法则、等价无穷小替换
难点：极限存在性判断、左右极限
易错点：忽略定义域，左右极限不一致
""")

with open(txt_path, "rb") as f:
    b, _ = test("上传文档", "post", "/api/upload",
                no_cache=True, timeout=T_MED,
                files={"file": ("test_textbook.txt", f, "text/plain")},
                data={"course_id": course_id})
doc_id = _id("上传文档", b, "document_id")
_save_state(doc_id=doc_id)

if doc_id:
    print("  ⏳ 等待解析（3s）...")
    time.sleep(3)
    test("查询解析状态", "get",  f"/api/documents/{doc_id}/status",  timeout=T_FAST)
    test("获取解析报告", "get",  f"/api/documents/{doc_id}/report",  timeout=T_FAST)
    test("重新触发解析", "post", f"/api/documents/{doc_id}/reparse", timeout=T_MED)

test("获取文档列表", "get", f"/api/documents?course_id={course_id}", timeout=T_FAST)

b2, _ = test("取章节列表", "get", f"/api/courses/{course_id}/chapters", timeout=T_FAST)
chapters   = b2.get("chapters") or []
chapter_id = (chapters[0].get("id", "") if chapters else _state.get("chapter_id", ""))
_save_state(chapter_id=chapter_id)

if chapter_id:
    test("章节详情",   "get", f"/api/chapters/{chapter_id}",                 timeout=T_FAST)
    test("章节知识点", "get", f"/api/chapters/{chapter_id}/knowledge-points", timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §4  学习包
# ─────────────────────────────────────────────────────────────
print("\n【§4 学习包生成】")
b, _ = test("生成学习包", "post", "/api/learning-package/generate",
            timeout=T_AI, retries=2,
            json={"course_id": course_id, "chapter_name": "第一章 函数与极限",
                  "study_days": 7, "daily_minutes": 60, "student_level": "中等"})
plan_id = _id("生成学习包", b, "plan_id")

b2, _ = test("单独生成学习计划", "post", "/api/plan/generate",
             timeout=T_AI, retries=2,
             json={"course_id": course_id, "chapter_name": "第一章 函数与极限"})
plan_id = plan_id or _id("单独生成学习计划", b2, "plan_id")
_save_state(plan_id=plan_id)

if plan_id:
    test("获取学习计划详情", "get", f"/api/study-plans/{plan_id}", timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §5  智能讲解
# ─────────────────────────────────────────────────────────────
print("\n【§5 智能讲解】")
test("生成知识点讲解", "post", "/api/explanation/generate",
     timeout=T_AI, retries=2,
     json={"course_id": course_id, "knowledge_point": "极限的定义",
           "explanation_style": "zero_basic", "user_level": "初学者"})

# ─────────────────────────────────────────────────────────────
# §6  习题与答题
# ─────────────────────────────────────────────────────────────
print("\n【§6 习题与答题】")
b, _ = test("生成习题", "post", "/api/exercises/generate",
            timeout=T_AI, retries=2,
            json={"course_id": course_id, "knowledge_point": "极限",
                  "question_types": ["choice", "calc"],
                  "difficulty": "medium", "count": 3})
ex_ids = (b.get("exercise_ids")
          or cache.get("生成习题", {}).get("body", {}).get("exercise_ids")
          or [])
ex_id = ex_ids[0] if ex_ids else _state.get("ex_id", "")
_save_state(ex_id=ex_id)

if ex_id:
    test("获取题目详情",  "get",  f"/api/exercises/{ex_id}",          timeout=T_FAST)
    test("提交答案",      "post", "/api/exercises/submit",            timeout=T_MED,
         json={"exercise_id": ex_id, "student_answer": "A", "user_id": "test-user"})
    test("查看题目解析",  "post", f"/api/exercises/{ex_id}/explain",  timeout=T_AI, retries=1)
    test("习题生成变式题","post", f"/api/exercises/{ex_id}/variants", timeout=T_AI, retries=1)

test("作业辅导", "post", "/api/homework/tutor",
     timeout=T_AI, retries=2,
     json={"question": "求 lim(x→0) sin(x)/x",
           "student_answer": "我觉得是 0", "mode": "correction",
           "course_id": course_id})
test("作业诊断", "post", "/api/homework/diagnose",
     timeout=T_AI, retries=2,
     json={"question": "求导数 f(x)=x²", "student_answer": "f'(x)=2x+1",
           "course_id": course_id})

# ─────────────────────────────────────────────────────────────
# §7  错题本
# ─────────────────────────────────────────────────────────────
print("\n【§7 错题本】")
b, _ = test("获取错题列表", "get", "/api/mistakes?user_id=test-user", timeout=T_FAST)
mistake_list = b.get("mistakes") or []
mistake_id   = (mistake_list[0].get("id", "") if mistake_list
                else _state.get("mistake_id", ""))
_save_state(mistake_id=mistake_id)

if mistake_id:
    test("复习错题",       "post",  f"/api/mistakes/{mistake_id}/review",   timeout=T_AI, retries=1)
    test("错题生成变式题", "post",  f"/api/mistakes/{mistake_id}/variants",  timeout=T_AI, retries=1)
    test("标记错题已掌握", "patch", f"/api/mistakes/{mistake_id}/mastered",  timeout=T_FAST,
         json={"mastered": True})

# ─────────────────────────────────────────────────────────────
# §8  智能组卷
# ─────────────────────────────────────────────────────────────
print("\n【§8 智能组卷】")
b, _ = test("生成试卷", "post", "/api/exam/generate",
            timeout=T_AI, retries=2,
            json={"course_id": course_id, "exam_type": "单元测试",
                  "total_questions": 10, "duration_minutes": 60})
exam_id = _id("生成试卷", b, "exam_id")
_save_state(exam_id=exam_id)

if exam_id:
    test("获取试卷详情", "get",  f"/api/exam/{exam_id}",            timeout=T_FAST)
    test("重新生成试卷", "post", f"/api/exam/{exam_id}/regenerate", timeout=T_AI, retries=1)

# ─────────────────────────────────────────────────────────────
# §9  导出服务
# ─────────────────────────────────────────────────────────────
print("\n【§9 导出服务】")
if plan_id:
    test("导出学习计划 PDF",  "post", f"/api/export/study-plan/{plan_id}",
         timeout=T_MED, json={"format": "pdf"})
    test("导出学习计划 Word", "post", f"/api/export/study-plan/{plan_id}",
         timeout=T_MED, json={"format": "docx"})
    test("导出 Markdown",     "post", f"/api/export/markdown/{plan_id}",
         timeout=T_MED)
if exam_id:
    test("导出试卷（学生版）", "post", f"/api/export/exam/{exam_id}",
         timeout=T_MED, json={"format": "pdf", "version": "student"})
    test("导出试卷（教师版）", "post", f"/api/export/exam/{exam_id}",
         timeout=T_MED, json={"format": "pdf", "version": "teacher"})
test("导出习题集（教师版）", "post", f"/api/export/exercises/{course_id}",
     timeout=T_MED, json={"format": "pdf", "version": "teacher"})
test("导出习题集（学生版）", "post", f"/api/export/exercises/{course_id}",
     timeout=T_MED, json={"format": "pdf", "version": "student"})

# ─────────────────────────────────────────────────────────────
# §10  微课生成
# ─────────────────────────────────────────────────────────────
print("\n【§10 微课生成】")
b, _ = test("生成微课脚本", "post", "/api/micro-lesson/script",
            timeout=T_AI, retries=2,
            json={"course_id": course_id, "topic": "极限的直觉理解",
                  "style": "讲解式", "duration_seconds": 300})
lesson_id = _id("生成微课脚本", b, "lesson_id")
_save_state(lesson_id=lesson_id)

test("生成 PPT 内容", "post", "/api/micro-lesson/ppt",
     timeout=T_AI, retries=2,
     json={"course_id": course_id, "topic": "极限的直觉理解"})

# TTS / 视频：lesson_id 为 query param（FastAPI Query 字段）
_lid = lesson_id or _state.get("lesson_id", "") or "placeholder"
test("生成语音（占位）", "post", "/api/micro-lesson/tts",
     timeout=T_MED,
     params={"lesson_id": _lid},
     json={"voice": "female"})
test("合成视频（占位）", "post", "/api/micro-lesson/video",
     timeout=T_MED,
     params={"lesson_id": _lid})

if lesson_id:
    test("获取微课详情", "get", f"/api/micro-lesson/{lesson_id}",         timeout=T_FAST)
    test("微课下载链接", "get", f"/api/micro-lesson/{lesson_id}/download", timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §11  学习画像
# ─────────────────────────────────────────────────────────────
print("\n【§11 学习画像】")
test("获取学习画像",     "get",  "/api/profile/test-user",  timeout=T_FAST)
test("更新画像附加数据", "post", "/api/profile/update",     timeout=T_MED,
     json={"user_id": "test-user", "extra": {"preference": "visual"}})
test("记录学习行为",     "post", "/api/learning-log",       timeout=T_FAST,
     json={"user_id": "test-user", "action": "view_lesson",
           "course_id": course_id, "duration_sec": 300})

# ─────────────────────────────────────────────────────────────
# §12  数据看板
# ─────────────────────────────────────────────────────────────
print("\n【§12 数据看板】")
test("学生看板", "get", "/api/dashboard/student/test-user",    timeout=T_FAST)
test("教师看板", "get", f"/api/dashboard/teacher/{course_id}", timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# §13  清理（放最后，避免影响上面的测试）
# ─────────────────────────────────────────────────────────────
print("\n【§13 清理】")
if doc_id:
    test("删除文档", "delete", f"/api/documents/{doc_id}", no_cache=True, timeout=T_FAST)

# ─────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
total  = len(_results)
passed = sum(1 for _, ok, _  in _results if ok)
cached = sum(1 for _, ok, h  in _results if ok and h)
failed = total - passed
fresh  = passed - cached

print(f"  {PASS} {passed} 通过  "
      f"（{HIT} {cached} 读缓存 / ▶ {fresh} 新执行）")
print(f"  {FAIL} {failed} 失败   共 {total} 项")

if failed:
    print("\n  未通过项目：")
    for name, ok, _ in _results:
        if not ok:
            print(f"    {FAIL} {name}")

print("=" * 62 + "\n")
sys.exit(0 if failed == 0 else 1)
