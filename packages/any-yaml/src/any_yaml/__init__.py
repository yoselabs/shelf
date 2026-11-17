"""Read, write and append YAML that people and Git merge, without caring how ruamel is configured."""

from ruamel.yaml.error import YAMLError
from yaml_merge import MergeConflictError

from any_yaml.append import append_item, append_item_file
from any_yaml.flow import flow_lines
from any_yaml.read import load, read
from any_yaml.write import dump, merge3_text, merge_text, write

__all__ = [
    "MergeConflictError",
    "YAMLError",
    "append_item",
    "append_item_file",
    "dump",
    "flow_lines",
    "load",
    "merge3_text",
    "merge_text",
    "read",
    "write",
]
