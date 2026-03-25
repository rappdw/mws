"""Parse OpenAPI spec into a command tree data structure."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Map HTTP methods to operation names
HTTP_METHOD_TO_OP: dict[str, str] = {
    "get": "list",  # GET on collection = list, GET on item = get (determined by path)
    "post": "create",
    "patch": "update",
    "put": "replace",
    "delete": "delete",
}


@dataclass
class Parameter:
    """A single parameter for an API method."""

    name: str
    location: str  # "path", "query", "header"
    required: bool = False
    param_type: str = "string"
    description: str = ""
    enum: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "location": self.location,
            "required": self.required,
            "type": self.param_type,
        }
        if self.description:
            d["description"] = self.description
        if self.enum:
            d["enum"] = self.enum
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Parameter:
        return cls(
            name=d["name"],
            location=d["location"],
            required=d.get("required", False),
            param_type=d.get("type", "string"),
            description=d.get("description", ""),
            enum=d.get("enum"),
        )


@dataclass
class MethodNode:
    """A single API operation (e.g., GET /me/messages)."""

    operation_name: str  # e.g., "list", "get", "create"
    http_method: str  # e.g., "GET", "POST"
    path_template: str  # e.g., "/me/messages/{message-id}"
    parameters: list[Parameter] = field(default_factory=list)
    request_body_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    summary: str = ""
    has_request_body: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "operation": self.operation_name,
            "httpMethod": self.http_method,
            "path": self.path_template,
            "summary": self.summary,
            "hasRequestBody": self.has_request_body,
        }
        if self.parameters:
            d["parameters"] = [p.to_dict() for p in self.parameters]
        if self.request_body_schema:
            d["requestBody"] = self.request_body_schema
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MethodNode:
        return cls(
            operation_name=d["operation"],
            http_method=d["httpMethod"],
            path_template=d["path"],
            summary=d.get("summary", ""),
            has_request_body=d.get("hasRequestBody", False),
            parameters=[Parameter.from_dict(p) for p in d.get("parameters", [])],
            request_body_schema=d.get("requestBody"),
        )


@dataclass
class ResourceNode:
    """A resource in the command tree (e.g., 'messages' under 'me')."""

    name: str
    children: dict[str, ResourceNode] = field(default_factory=dict)
    methods: dict[str, MethodNode] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.methods:
            d["methods"] = {k: v.to_dict() for k, v in self.methods.items()}
        if self.children:
            d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResourceNode:
        node = cls(name=d["name"])
        for k, v in d.get("methods", {}).items():
            node.methods[k] = MethodNode.from_dict(v)
        for k, v in d.get("children", {}).items():
            node.children[k] = ResourceNode.from_dict(v)
        return node


@dataclass
class CommandTree:
    """Root of the command tree."""

    children: dict[str, ResourceNode] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in self.children.items()}

    @classmethod
    def from_index(cls, data: dict[str, Any]) -> CommandTree:
        tree = cls()
        for k, v in data.items():
            tree.children[k] = ResourceNode.from_dict(v)
        return tree

    def resolve_path(self, path_segments: list[str]) -> ResourceNode | MethodNode | None:
        """Walk the tree by path segments, returning the deepest match."""
        if not path_segments:
            return None

        current: ResourceNode | None = self.children.get(path_segments[0])
        if current is None:
            return None

        for segment in path_segments[1:]:
            if segment in current.methods:
                return current.methods[segment]
            if segment in current.children:
                current = current.children[segment]
            else:
                return None
        return current

    def list_top_level(self) -> list[str]:
        """Return sorted list of top-level resource group names."""
        return sorted(self.children.keys())


def _normalize_segment(segment: str) -> str:
    """Normalize a path segment for use as a command name.

    - Strip braces from path params: {message-id} -> message-id (but these are skipped)
    - Convert camelCase to kebab-case for resource names
    """
    # Convert camelCase/PascalCase to kebab-case
    s = re.sub(r"([a-z])([A-Z])", r"\1-\2", segment)
    return s.lower()


def _is_path_param(segment: str) -> bool:
    """Check if a path segment is a parameter placeholder like {id}."""
    return segment.startswith("{") and segment.endswith("}")


def _determine_operation_name(http_method: str, path: str) -> str:
    """Determine the operation name based on HTTP method and path structure.

    GET on a collection path → list
    GET on an item path (ends with {param}) → get
    """
    method_lower = http_method.lower()
    if method_lower == "get":
        # If path ends with a path param, it's a "get"; otherwise "list"
        parts = path.rstrip("/").split("/")
        if parts and _is_path_param(parts[-1]):
            return "get"
        return "list"
    return HTTP_METHOD_TO_OP.get(method_lower, method_lower)


def _extract_parameters(
    path_params: list[dict[str, Any]],
    operation_params: list[dict[str, Any]],
) -> list[Parameter]:
    """Extract parameters from OpenAPI path item and operation."""
    seen: set[str] = set()
    result: list[Parameter] = []

    for params_list in [operation_params, path_params]:
        for p in params_list:
            name = p.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            schema = p.get("schema", {})
            result.append(
                Parameter(
                    name=name,
                    location=p.get("in", "query"),
                    required=p.get("required", False),
                    param_type=schema.get("type", "string"),
                    description=p.get("description", "")[:200],
                    enum=schema.get("enum"),
                )
            )
    return result


def _extract_request_body(
    operation: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None]:
    """Extract request body schema from an OpenAPI operation."""
    request_body = operation.get("requestBody")
    if not request_body:
        return False, None
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema")
    return True, schema


def build_command_tree(spec: dict[str, Any]) -> CommandTree:
    """Parse an OpenAPI spec into a CommandTree.

    Decomposes paths like /me/messages/{message-id}/attachments into:
        me → messages → attachments
    with path parameters captured on the MethodNode.
    """
    tree = CommandTree()
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        # Split path into segments, filtering empty strings
        segments = [s for s in path.split("/") if s]

        # Extract resource segments (skip path parameters)
        resource_segments = [_normalize_segment(s) for s in segments if not _is_path_param(s)]

        if not resource_segments:
            continue

        path_level_params = path_item.get("parameters", [])

        # Process each HTTP method in the path item
        for http_method in ["get", "post", "put", "patch", "delete"]:
            operation = path_item.get(http_method)
            if not operation or not isinstance(operation, dict):
                continue

            op_name = _determine_operation_name(http_method, path)
            params = _extract_parameters(path_level_params, operation.get("parameters", []))
            has_body, body_schema = _extract_request_body(operation)

            method_node = MethodNode(
                operation_name=op_name,
                http_method=http_method.upper(),
                path_template=path,
                parameters=params,
                request_body_schema=body_schema,
                summary=operation.get("summary", "")[:200],
                has_request_body=has_body,
            )

            # Walk/create resource tree to the leaf
            current_children = tree.children
            for i, seg in enumerate(resource_segments):
                if seg not in current_children:
                    current_children[seg] = ResourceNode(name=seg)

                if i == len(resource_segments) - 1:
                    # Leaf — add method. Handle name conflicts by appending http method
                    node = current_children[seg]
                    method_key = op_name
                    if method_key in node.methods:
                        method_key = f"{op_name}-{http_method}"
                    node.methods[method_key] = method_node
                else:
                    current_children = current_children[seg].children

    return tree


def command_tree_to_index(tree: CommandTree) -> dict[str, Any]:
    """Serialize a CommandTree to a compact dict for JSON caching."""
    return tree.to_dict()
