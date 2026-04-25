from engine.render_ops.header import set_header_field
from engine.render_ops.migration import write_auto_migration
from engine.render_ops.sections import (
    write_list,
    write_section,
    write_steps,
    write_table,
)

OP_HANDLERS = {
    "set_header_field": set_header_field,
    "write_section": write_section,
    "write_list": write_list,
    "write_table": write_table,
    "write_steps": write_steps,
    "write_auto_migration": write_auto_migration,
}
