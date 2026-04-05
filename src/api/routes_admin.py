from fastapi import APIRouter, Cookie, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import os
import json
import secrets
from typing import Optional
from core.database import DatabaseManager

router = APIRouter()

# 我们需要在 server.py 中将 db_manager, templates 等注入或导入
# 为了简单，我们可以延迟导入或从一个依赖模块导入
