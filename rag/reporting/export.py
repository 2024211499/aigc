"""旧版导出接口兼容层。

历史代码可能从 `rag.export_retrieval_results` 导入 `Retriever` 或
`RetrievalResult`。正式实现已经迁移到 `rag.retrieve` 和
`rag.retriever.Retriever`，这里仅保留轻包装，不维护第二套检索逻辑。
"""

from ..retrieval.retriever import RetrievalResult, Retriever
from ..retrieval.rag import retrieve

__all__ = ["Retriever", "RetrievalResult", "retrieve"]
