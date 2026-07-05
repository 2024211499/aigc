# -*- coding: utf-8 -*-
"""自定义异常"""


class AppException(Exception):
    def __init__(self, message: str, code: str = "ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str):
        super().__init__(f"{resource} 不存在", "NOT_FOUND", 404)


class ParseError(AppException):
    def __init__(self, msg: str):
        super().__init__(msg, "PARSE_ERROR", 422)


class FileTooLargeError(AppException):
    def __init__(self):
        super().__init__("文件超过大小限制", "FILE_TOO_LARGE", 413)


class UnsupportedFileType(AppException):
    def __init__(self, ext: str):
        super().__init__(f"不支持的文件类型: {ext}", "UNSUPPORTED_TYPE", 415)


class LLMError(AppException):
    def __init__(self, msg: str):
        super().__init__(f"AI 生成失败: {msg}", "LLM_ERROR", 502)
