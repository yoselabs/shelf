"""Write values back into the YAML document a human wrote, and merge two edits of one, keeping its comments.

``merge_into`` carries a payload's values into an existing document; ``merge3``
merges two edits of a document against their common ancestor.
"""

from yaml_merge.three_way import MergeConflictError, merge3
from yaml_merge.two_way import merge_into

__all__ = ["MergeConflictError", "merge3", "merge_into"]
