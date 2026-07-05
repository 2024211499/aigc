"""统一异常体系：所有自定义异常均继承自 DataLayerError。"""


class DataLayerError(Exception):
    """数据底座异常基类。"""


class ConfigurationError(DataLayerError):
    """配置参数错误。"""


class DocumentParseError(DataLayerError):
    """通用文档解析异常。"""


class PDFExtractionError(DocumentParseError):
    """PDF 提取异常。"""


class EncryptedPDFError(PDFExtractionError):
    """PDF 已加密且无法解密。"""


class DamagedPDFError(PDFExtractionError):
    """PDF 损坏或结构异常。"""


class PageExtractionError(PDFExtractionError):
    """单页解析失败。"""


class OCRDependencyError(PDFExtractionError):
    """OCR 依赖缺失或初始化失败。"""


class OCRRuntimeError(PDFExtractionError):
    """OCR 运行时失败。"""


class OCRConfigurationError(OCRDependencyError):
    """OCR 配置不完整或未显式启用。"""


class OCRTimeoutError(OCRRuntimeError):
    """OCR 单页超时。"""


class OCRCacheError(OCRRuntimeError):
    """OCR 缓存读写异常。"""


class StorageError(DataLayerError):
    """SQLite 存储异常。"""


class EmbeddingError(DataLayerError):
    """Embedding 生成失败。"""


class VectorStoreError(DataLayerError):
    """向量库读写失败。"""


class RetrievalError(DataLayerError):
    """检索失败。"""


class EmptyIndexError(RetrievalError):
    """课程索引为空。"""
