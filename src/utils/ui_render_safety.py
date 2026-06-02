"""Backward-compatible re-export — canonical module is src.services.ui_render_safety."""

from src.services.ui_render_safety import (  # noqa: F401
    assert_template_render_safe,
    contains_js_leak_fragment,
    contains_object_object_leak,
    find_js_leaks_in_file,
    format_visible_value,
    sanitize_visible_text,
)
