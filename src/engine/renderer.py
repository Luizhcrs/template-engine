from __future__ import annotations

import shutil
from datetime import date
from typing import TYPE_CHECKING

import structlog
from docx import Document

from engine.render_ops import OP_HANDLERS

if TYPE_CHECKING:
    from pathlib import Path

    from engine.preset_schemas import PresetBundle

log = structlog.get_logger(__name__)


class RenderError(Exception):
    pass


def render(preset: PresetBundle, content: dict, output_path: Path) -> Path:
    """Apply preset's template + LLM content + deterministic ops to produce output .docx."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(preset.template_docx_path, output_path)
    doc = Document(output_path)

    ctx = {
        "doc": doc,
        "content": content,
        "preset": preset,
        "today": date.today(),
    }

    for op in preset.render_ops.operations:
        handler = OP_HANDLERS.get(op.op)
        if handler is None:
            raise RenderError(f"operação desconhecida: {op.op}")
        log.info("render.op", op=op.op, params=list(op.params.keys()))
        handler(ctx, op.params)

    doc.save(output_path)
    return output_path
