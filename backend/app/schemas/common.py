# -*- coding: utf-8 -*-
"""通用响应结构"""

from pydantic import BaseModel
from typing import Any, Optional


class SuccessResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    message: str = ""


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str = "ERROR"
