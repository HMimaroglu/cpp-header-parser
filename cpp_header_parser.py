"""
C++ Header File Parser

Parses C++ header files to extract class definitions, methods, and arguments.
Identifies whether each method is implemented inline (in the header) or in a
separate .cpp file. Can generate .cpp skeleton files from parsed declarations.
"""

from __future__ import annotations

import re
import os
import sys
import json
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class AccessSpecifier(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"


class ImplementationLocation(Enum):
    HEADER = "header"
    CPP = "cpp"
    DECLARATION_ONLY = "declaration_only"


@dataclass
class CppArgument:
    """Represents a single argument of a C++ method."""

    arg_type: str
    name: str
    default_value: Optional[str] = None

    def __str__(self) -> str:
        result = f"{self.arg_type} {self.name}" if self.name else self.arg_type
        if self.default_value is not None:
            result += f" = {self.default_value}"
        return result

    def declaration_str(self) -> str:
        """String for use in a declaration (includes default value)."""
        return str(self)

    def definition_str(self) -> str:
        """String for use in a definition (no default value)."""
        result = f"{self.arg_type} {self.name}" if self.name else self.arg_type
        return result

    def to_dict(self) -> dict:
        return {
            "type": self.arg_type,
            "name": self.name,
            "default_value": self.default_value,
        }


@dataclass
class CppMethod:
    """Represents a C++ class method."""

    name: str
    return_type: str
    arguments: list[CppArgument] = field(default_factory=list)
    access: AccessSpecifier = AccessSpecifier.PRIVATE
    is_virtual: bool = False
    is_pure_virtual: bool = False
    is_static: bool = False
    is_const: bool = False
    is_override: bool = False
    is_final: bool = False
    is_noexcept: bool = False
    is_explicit: bool = False
    is_inline: bool = False
    is_constexpr: bool = False
    is_constructor: bool = False
    is_destructor: bool = False
    is_operator: bool = False
    is_friend: bool = False
    is_delete: bool = False
    is_default: bool = False
    template_params: Optional[str] = None
    implementation_location: ImplementationLocation = ImplementationLocation.DECLARATION_ONLY
    body: Optional[str] = None
    initializer_list: Optional[str] = None

    def signature(self, class_name: Optional[str] = None, for_definition: bool = False) -> str:
        """Build the method signature string."""
        parts = []

        if self.template_params and for_definition:
            parts.append(f"template <{self.template_params}>")
            parts.append("\n")

        if not for_definition:
            if self.is_explicit:
                parts.append("explicit")
            if self.is_static:
                parts.append("static")
            if self.is_virtual:
                parts.append("virtual")
            if self.is_inline and not for_definition:
                parts.append("inline")
            if self.is_constexpr:
                parts.append("constexpr")

        if self.is_friend and not for_definition:
            parts.append("friend")

        if self.return_type and not self.is_constructor and not self.is_destructor:
            parts.append(self.return_type)

        if for_definition and class_name:
            qualified_name = f"{class_name}::{self.name}"
        else:
            qualified_name = self.name

        if for_definition:
            arg_str = ", ".join(a.definition_str() for a in self.arguments)
        else:
            arg_str = ", ".join(str(a) for a in self.arguments)

        parts.append(f"{qualified_name}({arg_str})")

        if self.is_const:
            parts.append("const")
        if self.is_noexcept:
            parts.append("noexcept")
        if not for_definition:
            if self.is_override:
                parts.append("override")
            if self.is_final:
                parts.append("final")

        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "arguments": [a.to_dict() for a in self.arguments],
            "access": self.access.value,
            "is_virtual": self.is_virtual,
            "is_pure_virtual": self.is_pure_virtual,
            "is_static": self.is_static,
            "is_const": self.is_const,
            "is_override": self.is_override,
            "is_final": self.is_final,
            "is_noexcept": self.is_noexcept,
            "is_explicit": self.is_explicit,
            "is_inline": self.is_inline,
            "is_constexpr": self.is_constexpr,
            "is_constructor": self.is_constructor,
            "is_destructor": self.is_destructor,
            "is_operator": self.is_operator,
            "is_friend": self.is_friend,
            "is_delete": self.is_delete,
            "is_default": self.is_default,
            "template_params": self.template_params,
            "implementation_location": self.implementation_location.value,
            "body": self.body,
            "initializer_list": self.initializer_list,
        }


@dataclass
class CppClass:
    """Represents a C++ class or struct."""

    name: str
    is_struct: bool = False
    base_classes: list[tuple[str, str]] = field(default_factory=list)  # (access, class_name)
    methods: list[CppMethod] = field(default_factory=list)
    nested_classes: list[CppClass] = field(default_factory=list)
    template_params: Optional[str] = None
    namespace: Optional[str] = None

    def get_methods_by_access(self, access: AccessSpecifier) -> list[CppMethod]:
        return [m for m in self.methods if m.access == access]

    def get_header_implemented(self) -> list[CppMethod]:
        return [m for m in self.methods if m.implementation_location == ImplementationLocation.HEADER]

    def get_cpp_implemented(self) -> list[CppMethod]:
        return [m for m in self.methods if m.implementation_location == ImplementationLocation.CPP]

    def get_declaration_only(self) -> list[CppMethod]:
        return [m for m in self.methods if m.implementation_location == ImplementationLocation.DECLARATION_ONLY]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "is_struct": self.is_struct,
            "base_classes": [{"access": a, "name": n} for a, n in self.base_classes],
            "methods": [m.to_dict() for m in self.methods],
            "nested_classes": [c.to_dict() for c in self.nested_classes],
            "template_params": self.template_params,
            "namespace": self.namespace,
        }

    def summary(self, indent: int = 0) -> str:
        """Human-readable summary of the class."""
        pad = "  " * indent
        lines = []
        tpl = f"template <{self.template_params}> " if self.template_params else ""
        keyword = "struct" if self.is_struct else "class"
        base_str = ""
        if self.base_classes:
            base_str = " : " + ", ".join(f"{a} {n}" for a, n in self.base_classes)
        ns = f"(namespace: {self.namespace}) " if self.namespace else ""
        lines.append(f"{pad}{ns}{tpl}{keyword} {self.name}{base_str}")

        for access in AccessSpecifier:
            methods = self.get_methods_by_access(access)
            if methods:
                lines.append(f"{pad}  {access.value}:")
                for m in methods:
                    loc = m.implementation_location.value
                    lines.append(f"{pad}    [{loc:17s}] {m.signature()}")

        for nested in self.nested_classes:
            lines.append(f"{pad}  nested:")
            lines.append(nested.summary(indent + 2))

        return "\n".join(lines)


def _strip_comments(source: str) -> str:
    """Remove C and C++ style comments from source code."""
    result = []
    i = 0
    in_string = False
    string_char = None

    while i < len(source):
        # Handle string literals
        if not in_string and source[i] in ('"', "'"):
            in_string = True
            string_char = source[i]
            result.append(source[i])
            i += 1
            continue
        if in_string:
            if source[i] == "\\" and i + 1 < len(source):
                result.append(source[i])
                result.append(source[i + 1])
                i += 2
                continue
            if source[i] == string_char:
                in_string = False
            result.append(source[i])
            i += 1
            continue

        # Single-line comment
        if source[i : i + 2] == "//":
            while i < len(source) and source[i] != "\n":
                i += 1
            result.append(" ")
            continue

        # Multi-line comment
        if source[i : i + 2] == "/*":
            i += 2
            while i < len(source) and source[i - 1 : i + 1] != "*/":
                i += 1
            i += 1
            result.append(" ")
            continue

        result.append(source[i])
        i += 1

    return "".join(result)


def _strip_preprocessor(source: str) -> str:
    """Remove preprocessor directives (keep the newlines for position tracking)."""
    lines = source.split("\n")
    result = []
    continuation = False
    for line in lines:
        stripped = line.strip()
        if continuation:
            if stripped.endswith("\\"):
                result.append("")
            else:
                continuation = False
                result.append("")
            continue
        if stripped.startswith("#"):
            if stripped.endswith("\\"):
                continuation = True
            result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def _find_matching_brace(source: str, start: int) -> int:
    """Find the index of the closing brace matching the opening brace at `start`."""
    depth = 0
    i = start
    in_string = False
    string_char = None

    while i < len(source):
        ch = source[i]

        if not in_string and ch in ('"', "'"):
            in_string = True
            string_char = ch
            i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < len(source):
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _parse_arguments(arg_string: str) -> list[CppArgument]:
    """Parse a comma-separated argument list string into CppArgument objects."""
    arg_string = arg_string.strip()
    if not arg_string or arg_string == "void":
        return []

    arguments = []
    # Split by commas, respecting template angle brackets and parentheses
    depth_angle = 0
    depth_paren = 0
    current = []
    for ch in arg_string:
        if ch == "<":
            depth_angle += 1
        elif ch == ">":
            depth_angle -= 1
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "," and depth_angle == 0 and depth_paren == 0:
            arguments.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        arguments.append("".join(current).strip())

    result = []
    for arg in arguments:
        if not arg:
            continue
        result.append(_parse_single_argument(arg))
    return result


def _parse_single_argument(arg: str) -> CppArgument:
    """Parse a single argument string like 'const std::string& name = ""'."""
    # Check for default value
    default_value = None
    # Find '=' not inside angle brackets or parens
    depth_angle = 0
    depth_paren = 0
    eq_pos = -1
    for i, ch in enumerate(arg):
        if ch == "<":
            depth_angle += 1
        elif ch == ">":
            depth_angle -= 1
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "=" and depth_angle == 0 and depth_paren == 0:
            eq_pos = i
            break

    if eq_pos >= 0:
        default_value = arg[eq_pos + 1 :].strip()
        arg = arg[:eq_pos].strip()

    # Split type and name
    # The name is the last token that looks like an identifier
    # But handle cases like: const int*, const int&, int[], std::function<void(int)>
    arg = arg.strip()

    # Handle function pointer arguments: void (*callback)(int, int)
    fp_match = re.match(r"(.+?)\(\s*\*\s*(\w+)\s*\)\s*\(.*\)", arg)
    if fp_match:
        return CppArgument(arg_type=arg, name=fp_match.group(2), default_value=default_value)

    # Try to find the name: last identifier token
    # Work backwards from the end
    tokens = arg.split()
    if not tokens:
        return CppArgument(arg_type=arg, name="", default_value=default_value)

    last = tokens[-1]
    # If last token ends with & or *, it's part of the type (unnamed param)
    if last in ("&", "&&", "*") or last.endswith("&") or last.endswith("*"):
        return CppArgument(arg_type=arg, name="", default_value=default_value)

    # If last token contains < or > it's a template type, no name
    if "<" in last or ">" in last:
        return CppArgument(arg_type=arg, name="", default_value=default_value)

    # Check if last token is a valid identifier (the name)
    # Strip trailing & or * from the beginning that might be attached
    name_candidate = last.lstrip("&*")
    if re.match(r"^[a-zA-Z_]\w*$", name_candidate):
        # Everything before is the type
        type_part = arg[: arg.rfind(last)].strip()
        # If type_part is empty, the whole thing is just a type name (like 'int')
        if not type_part:
            return CppArgument(arg_type=arg, name="", default_value=default_value)
        # Re-attach any leading &/* from the name to the type or keep on name
        prefix = last[: len(last) - len(name_candidate)]
        if prefix:
            type_part = type_part + prefix
        return CppArgument(arg_type=type_part, name=name_candidate, default_value=default_value)

    return CppArgument(arg_type=arg, name="", default_value=default_value)


def _extract_template_params(source: str, pos: int) -> tuple[Optional[str], int]:
    """If there's a template<...> before class/struct at pos, extract params."""
    # Look backwards from pos for 'template'
    before = source[:pos].rstrip()
    match = re.search(r"template\s*<(.*)>\s*$", before, re.DOTALL)
    if match:
        return match.group(1).strip(), match.start()
    return None, pos


def _parse_method_qualifiers(after_paren: str) -> dict:
    """Parse qualifiers after the closing paren of a method signature."""
    qualifiers = {
        "is_const": False,
        "is_noexcept": False,
        "is_override": False,
        "is_final": False,
        "is_pure_virtual": False,
        "is_delete": False,
        "is_default": False,
    }
    text = after_paren.strip()
    if "const" in text.split():
        qualifiers["is_const"] = True
    if "noexcept" in text:
        qualifiers["is_noexcept"] = True
    if "override" in text:
        qualifiers["is_override"] = True
    if "final" in text:
        qualifiers["is_final"] = True
    if re.search(r"=\s*0", text):
        qualifiers["is_pure_virtual"] = True
    if re.search(r"=\s*delete", text):
        qualifiers["is_delete"] = True
    if re.search(r"=\s*default", text):
        qualifiers["is_default"] = True
    return qualifiers


class HeaderParser:
    """Parses C++ header files and extracts class/struct definitions."""

    def __init__(self):
        self.classes: list[CppClass] = []
        self._cpp_implementations: dict[str, set[str]] = {}  # class_name -> set of method names

    def parse_header(self, header_path: str, cpp_path: Optional[str] = None) -> list[CppClass]:
        """Parse a header file and optionally cross-reference with a .cpp file."""
        header_path = str(Path(header_path).resolve())
        with open(header_path, "r") as f:
            source = f.read()

        if cpp_path:
            cpp_path = str(Path(cpp_path).resolve())
            with open(cpp_path, "r") as f:
                cpp_source = f.read()
            self._parse_cpp_implementations(cpp_source)
        else:
            # Try to find matching .cpp automatically
            base = os.path.splitext(header_path)[0]
            for ext in (".cpp", ".cc", ".cxx", ".c++"):
                candidate = base + ext
                if os.path.isfile(candidate):
                    with open(candidate, "r") as f:
                        cpp_source = f.read()
                    self._parse_cpp_implementations(cpp_source)
                    break

        cleaned = _strip_comments(source)
        cleaned = _strip_preprocessor(cleaned)

        # Detect namespaces
        self.classes = []
        self._parse_classes(cleaned, namespace=None)

        # Cross-reference with cpp implementations
        self._cross_reference_cpp()

        return self.classes

    def parse_header_string(
        self, header_source: str, cpp_source: Optional[str] = None
    ) -> list[CppClass]:
        """Parse header content from strings (useful for testing)."""
        if cpp_source:
            self._parse_cpp_implementations(cpp_source)
        else:
            self._cpp_implementations = {}

        cleaned = _strip_comments(header_source)
        cleaned = _strip_preprocessor(cleaned)

        self.classes = []
        self._parse_classes(cleaned, namespace=None)
        self._cross_reference_cpp()

        return self.classes

    def _parse_cpp_implementations(self, cpp_source: str) -> None:
        """Scan a .cpp file for ClassName::MethodName patterns to find implementations."""
        cleaned = _strip_comments(cpp_source)
        cleaned = _strip_preprocessor(cleaned)
        self._cpp_implementations = {}

        # Match patterns like: ReturnType ClassName::MethodName(...)
        # Also handle: ClassName::ClassName(...) for constructors
        # And: ClassName::~ClassName(...) for destructors
        # And nested: Outer::Inner::MethodName(...)
        pattern = re.compile(
            r"(?:[\w:*&<>\s]+?\s+)?(\w[\w:]*?)::(\~?\w+)\s*\([^)]*\)"
        )
        for match in pattern.finditer(cleaned):
            class_name = match.group(1)
            method_name = match.group(2)
            # Handle nested classes - take the last part as the class
            if "::" in class_name:
                parts = class_name.split("::")
                class_name = parts[-1]
            if class_name not in self._cpp_implementations:
                self._cpp_implementations[class_name] = set()
            self._cpp_implementations[class_name].add(method_name)

    def _cross_reference_cpp(self) -> None:
        """Update methods that are implemented in .cpp files."""
        for cls in self.classes:
            if cls.name in self._cpp_implementations:
                impl_methods = self._cpp_implementations[cls.name]
                for method in cls.methods:
                    if method.implementation_location == ImplementationLocation.DECLARATION_ONLY:
                        if method.name in impl_methods:
                            method.implementation_location = ImplementationLocation.CPP
            # Recurse into nested classes
            for nested in cls.nested_classes:
                self._cross_reference_nested(nested)

    def _cross_reference_nested(self, cls: CppClass) -> None:
        if cls.name in self._cpp_implementations:
            impl_methods = self._cpp_implementations[cls.name]
            for method in cls.methods:
                if method.implementation_location == ImplementationLocation.DECLARATION_ONLY:
                    if method.name in impl_methods:
                        method.implementation_location = ImplementationLocation.CPP
        for nested in cls.nested_classes:
            self._cross_reference_nested(nested)

    def _parse_classes(self, source: str, namespace: Optional[str]) -> None:
        """Find and parse all class/struct definitions in source."""
        # Find namespace blocks first
        ns_pattern = re.compile(r"\bnamespace\s+(\w+)\s*\{")
        class_pattern = re.compile(
            r"\b(class|struct)\s+(\w+)\s*((?:final\s+)?(?::\s*(?:[^{;]*))?)\s*\{"
        )

        # Track namespace regions so we don't double-process classes inside them
        namespace_regions = []  # list of (start, end) ranges

        # Process namespaces (only top-level ones, not nested inside other namespaces)
        for ns_match in ns_pattern.finditer(source):
            # Skip if this namespace is inside another namespace we already found
            ns_pos = ns_match.start()
            inside_existing = False
            for ns_start, ns_end in namespace_regions:
                if ns_start < ns_pos < ns_end:
                    inside_existing = True
                    break
            if inside_existing:
                continue

            ns_name = ns_match.group(1)
            brace_start = source.index("{", ns_match.start())
            brace_end = _find_matching_brace(source, brace_start)
            if brace_end < 0:
                continue
            namespace_regions.append((ns_match.start(), brace_end))
            ns_body = source[brace_start + 1 : brace_end]
            full_ns = f"{namespace}::{ns_name}" if namespace else ns_name
            self._parse_classes(ns_body, full_ns)

        # Process classes/structs (only those NOT inside a namespace region)
        for match in class_pattern.finditer(source):
            # Skip if this match is inside a namespace we already processed
            match_pos = match.start()
            inside_namespace = False
            for ns_start, ns_end in namespace_regions:
                if ns_start < match_pos < ns_end:
                    inside_namespace = True
                    break
            if inside_namespace:
                continue

            keyword = match.group(1)
            class_name = match.group(2)
            inheritance_str = match.group(3).strip()

            brace_start = source.index("{", match.start())
            brace_end = _find_matching_brace(source, brace_start)
            if brace_end < 0:
                continue

            # Check for template params
            template_params, _ = _extract_template_params(source, match.start())

            # Parse base classes
            base_classes = []
            if inheritance_str:
                # Remove 'final' keyword if present before the colon
                inheritance_str = re.sub(r"^final\s*", "", inheritance_str).strip()
                if inheritance_str.startswith(":"):
                    bases_str = inheritance_str[1:].strip()
                    base_classes = self._parse_base_classes(bases_str)

            class_body = source[brace_start + 1 : brace_end]

            cpp_class = CppClass(
                name=class_name,
                is_struct=(keyword == "struct"),
                base_classes=base_classes,
                template_params=template_params,
                namespace=namespace,
            )

            self._parse_class_body(class_body, cpp_class)
            self.classes.append(cpp_class)

    def _parse_base_classes(self, bases_str: str) -> list[tuple[str, str]]:
        """Parse inheritance list like 'public Base1, private Base2'."""
        result = []
        # Split by comma, respecting templates
        depth = 0
        current = []
        for ch in bases_str:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0:
                result.append(self._parse_single_base("".join(current).strip()))
                current = []
                continue
            current.append(ch)
        if current:
            result.append(self._parse_single_base("".join(current).strip()))
        return result

    def _parse_single_base(self, base_str: str) -> tuple[str, str]:
        """Parse a single base class like 'public Base' or just 'Base'."""
        base_str = base_str.strip()
        for access in ("public", "protected", "private"):
            if base_str.startswith(access):
                name = base_str[len(access) :].strip()
                return (access, name)
        return ("private", base_str)

    def _parse_class_body(self, body: str, cpp_class: CppClass) -> None:
        """Parse the body of a class definition to extract methods."""
        default_access = AccessSpecifier.PUBLIC if cpp_class.is_struct else AccessSpecifier.PRIVATE
        current_access = default_access

        # Find nested classes first and remove them from body to avoid confusion
        nested_class_pattern = re.compile(
            r"\b(class|struct)\s+(\w+)\s*((?:final\s+)?(?::\s*(?:[^{;]*))?)\s*\{"
        )
        clean_body = body

        # Parse nested classes
        for match in nested_class_pattern.finditer(body):
            brace_start = body.index("{", match.start())
            brace_end = _find_matching_brace(body, brace_start)
            if brace_end < 0:
                continue

            nested_keyword = match.group(1)
            nested_name = match.group(2)
            nested_inheritance = match.group(3).strip()
            nested_body = body[brace_start + 1 : brace_end]

            template_params, _ = _extract_template_params(body, match.start())

            base_classes = []
            if nested_inheritance:
                nested_inheritance = re.sub(r"^final\s*", "", nested_inheritance).strip()
                if nested_inheritance.startswith(":"):
                    base_classes = self._parse_base_classes(nested_inheritance[1:].strip())

            nested_class = CppClass(
                name=nested_name,
                is_struct=(nested_keyword == "struct"),
                base_classes=base_classes,
                template_params=template_params,
                namespace=cpp_class.namespace,
            )
            self._parse_class_body(nested_body, nested_class)
            cpp_class.nested_classes.append(nested_class)

            # Blank out the nested class in clean_body
            full_nested = body[match.start() : brace_end + 1]
            clean_body = clean_body.replace(full_nested, " " * len(full_nested), 1)

        # Now parse methods and access specifiers from clean_body
        # Split into statements
        self._parse_members(clean_body, cpp_class, current_access)

    def _parse_members(
        self, body: str, cpp_class: CppClass, current_access: AccessSpecifier
    ) -> None:
        """Parse members (methods) from a class body string."""
        i = 0
        while i < len(body):
            # Skip whitespace
            while i < len(body) and body[i] in " \t\n\r":
                i += 1
            if i >= len(body):
                break

            # Check for access specifier
            access_match = re.match(r"(public|private|protected)\s*:", body[i:])
            if access_match:
                current_access = AccessSpecifier(access_match.group(1))
                i += access_match.end()
                continue

            # Find the next statement (ending in ; or { for inline implementation)
            stmt_start = i
            stmt, end_pos, has_body, body_content, init_list = self._extract_statement(body, i)
            if stmt is None:
                break
            i = end_pos

            stmt = stmt.strip()
            if not stmt:
                continue

            # Skip friend class declarations
            if re.match(r"friend\s+class\s+", stmt):
                continue

            # Skip using declarations
            if stmt.startswith("using "):
                continue

            # Skip typedef
            if stmt.startswith("typedef "):
                continue

            # Skip pure data members (no parentheses)
            if "(" not in stmt:
                continue

            # Try to parse as a method
            method = self._parse_method_declaration(stmt, current_access, has_body, body_content, init_list)
            if method:
                cpp_class.methods.append(method)

    def _extract_statement(
        self, body: str, start: int
    ) -> tuple[Optional[str], int, bool, Optional[str], Optional[str]]:
        """Extract the next statement, handling braces for inline methods.

        Returns (statement_text, end_position, has_body, body_content, initializer_list).
        """
        i = start
        depth_paren = 0
        depth_angle = 0
        found_paren = False
        in_string = False
        string_char = None

        while i < len(body):
            ch = body[i]

            if not in_string and ch in ('"', "'"):
                in_string = True
                string_char = ch
                i += 1
                continue
            if in_string:
                if ch == "\\" and i + 1 < len(body):
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
                i += 1
                continue

            if ch == "(":
                depth_paren += 1
                found_paren = True
            elif ch == ")":
                depth_paren -= 1
            elif ch == "<" and depth_paren == 0:
                depth_angle += 1
            elif ch == ">" and depth_paren == 0:
                depth_angle -= 1

            if ch == ";" and depth_paren == 0 and depth_angle <= 0:
                stmt_text = body[start:i]
                return (stmt_text, i + 1, False, None, None)

            if ch == "{" and depth_paren == 0 and depth_angle <= 0 and found_paren:
                # This is an inline implementation
                stmt_text = body[start:i]

                # Check for initializer list (constructors)
                init_list = None
                # Look for : before { after the closing )
                paren_section = stmt_text
                colon_match = re.search(r"\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?\s*:\s*(.+)$", paren_section, re.DOTALL)
                if colon_match:
                    init_list = colon_match.group(1).strip()
                    stmt_text = stmt_text[:colon_match.start()] + stmt_text[colon_match.start():colon_match.start() + paren_section[colon_match.start():].index(":")]

                brace_end = _find_matching_brace(body, i)
                if brace_end < 0:
                    return (None, len(body), False, None, None)
                body_content = body[i + 1 : brace_end].strip()

                # Skip past the closing brace and optional semicolon
                end = brace_end + 1
                while end < len(body) and body[end] in " \t\n\r":
                    end += 1
                if end < len(body) and body[end] == ";":
                    end += 1

                return (stmt_text, end, True, body_content, init_list)

            i += 1

        # End of body reached
        remaining = body[start:].strip()
        if remaining:
            return (remaining, len(body), False, None, None)
        return (None, len(body), False, None, None)

    def _parse_method_declaration(
        self,
        stmt: str,
        access: AccessSpecifier,
        has_body: bool,
        body_content: Optional[str],
        init_list: Optional[str],
    ) -> Optional[CppMethod]:
        """Parse a method declaration string into a CppMethod."""
        original_stmt = stmt

        # Check for template
        template_params = None
        tmpl_match = re.match(r"template\s*<(.+?)>\s*", stmt, re.DOTALL)
        if tmpl_match:
            template_params = tmpl_match.group(1).strip()
            stmt = stmt[tmpl_match.end() :]

        # Extract qualifiers from the beginning
        is_virtual = False
        is_static = False
        is_explicit = False
        is_inline = False
        is_constexpr = False
        is_friend = False

        prefix_keywords = {
            "virtual": "is_virtual",
            "static": "is_static",
            "explicit": "is_explicit",
            "inline": "is_inline",
            "constexpr": "is_constexpr",
            "friend": "is_friend",
        }

        while True:
            found = False
            for kw, attr in prefix_keywords.items():
                pattern = re.compile(rf"^{kw}\s+")
                m = pattern.match(stmt)
                if m:
                    locals()[attr] = True
                    if attr == "is_virtual":
                        is_virtual = True
                    elif attr == "is_static":
                        is_static = True
                    elif attr == "is_explicit":
                        is_explicit = True
                    elif attr == "is_inline":
                        is_inline = True
                    elif attr == "is_constexpr":
                        is_constexpr = True
                    elif attr == "is_friend":
                        is_friend = True
                    stmt = stmt[m.end() :]
                    found = True
                    break
            if not found:
                break

        # Find the argument list - find the last matching () pair
        paren_start = -1
        paren_end = -1
        depth = 0
        for idx in range(len(stmt) - 1, -1, -1):
            if stmt[idx] == ")":
                if paren_end == -1:
                    paren_end = idx
                depth += 1
            elif stmt[idx] == "(":
                depth -= 1
                if depth == 0:
                    paren_start = idx
                    break

        if paren_start < 0 or paren_end < 0:
            return None

        arg_string = stmt[paren_start + 1 : paren_end]
        after_paren = stmt[paren_end + 1 :].strip()
        before_paren = stmt[:paren_start].strip()

        # Parse post-paren qualifiers
        qualifiers = _parse_method_qualifiers(after_paren)

        # Parse arguments
        arguments = _parse_arguments(arg_string)

        # Determine method name and return type from before_paren
        # before_paren could be: "void doSomething", "int getValue", "MyClass", "~MyClass",
        # "operator+", "operator<<", "std::string getName", etc.

        is_constructor = False
        is_destructor = False
        is_operator = False
        return_type = ""
        name = ""

        # Check for operator overloading
        op_match = re.match(r"(.+?)\s+(operator\s*(?:\S+|(?:\(\s*\))))\s*$", before_paren)
        if op_match:
            return_type = op_match.group(1).strip()
            name = op_match.group(2).strip()
            is_operator = True
        elif before_paren.startswith("~"):
            # Destructor
            name = before_paren
            is_destructor = True
        else:
            # Split into return type + name
            # Last token is the name (could be preceded by * or &)
            tokens = before_paren.rsplit(None, 1)
            if len(tokens) == 1:
                # Could be a constructor (just the name, no return type)
                name = tokens[0]
                is_constructor = True
            else:
                return_type = tokens[0]
                name = tokens[1]

        if not name:
            return None

        # Determine implementation location
        if has_body:
            impl_location = ImplementationLocation.HEADER
        elif qualifiers["is_pure_virtual"]:
            impl_location = ImplementationLocation.DECLARATION_ONLY
        elif qualifiers["is_delete"] or qualifiers["is_default"]:
            impl_location = ImplementationLocation.DECLARATION_ONLY
        else:
            impl_location = ImplementationLocation.DECLARATION_ONLY

        method = CppMethod(
            name=name,
            return_type=return_type,
            arguments=arguments,
            access=access,
            is_virtual=is_virtual,
            is_pure_virtual=qualifiers["is_pure_virtual"],
            is_static=is_static,
            is_const=qualifiers["is_const"],
            is_override=qualifiers["is_override"],
            is_final=qualifiers["is_final"],
            is_noexcept=qualifiers["is_noexcept"],
            is_explicit=is_explicit,
            is_inline=is_inline,
            is_constexpr=is_constexpr,
            is_constructor=is_constructor,
            is_destructor=is_destructor,
            is_operator=is_operator,
            is_friend=is_friend,
            is_delete=qualifiers["is_delete"],
            is_default=qualifiers["is_default"],
            template_params=template_params,
            implementation_location=impl_location,
            body=body_content,
            initializer_list=init_list,
        )

        return method


class CppFileGenerator:
    """Generates .cpp implementation files from parsed class structures."""

    def generate_cpp(
        self,
        classes: list[CppClass],
        header_filename: str,
        include_existing_bodies: bool = True,
    ) -> str:
        """Generate a .cpp file with method implementations.

        Args:
            classes: Parsed class list.
            header_filename: The header file name to #include.
            include_existing_bodies: If True, copy inline bodies from the header.
        """
        lines = []
        lines.append(f'#include "{header_filename}"')
        lines.append("")

        for cls in classes:
            self._generate_class_methods(cls, lines, include_existing_bodies)

        return "\n".join(lines)

    def _generate_class_methods(
        self,
        cls: CppClass,
        lines: list[str],
        include_existing_bodies: bool,
        outer_class: Optional[str] = None,
    ) -> None:
        """Generate method definitions for a class."""
        class_name = f"{outer_class}::{cls.name}" if outer_class else cls.name

        if cls.namespace:
            lines.append(f"namespace {cls.namespace} {{")
            lines.append("")

        for method in cls.methods:
            # Skip pure virtual, deleted, and defaulted methods
            if method.is_pure_virtual or method.is_delete or method.is_default:
                continue

            # Skip friend functions (they're not class members)
            if method.is_friend:
                continue

            # For declaration-only methods, generate empty stubs
            # For header-implemented methods, optionally copy the body
            if method.implementation_location == ImplementationLocation.CPP:
                # Already in cpp, skip unless we want to regenerate
                continue

            sig = method.signature(class_name=class_name, for_definition=True)

            if method.initializer_list and (method.is_constructor or method.is_destructor):
                lines.append(f"{sig}")
                lines.append(f"    : {method.initializer_list}")
            else:
                lines.append(sig)

            if include_existing_bodies and method.body:
                lines.append("{")
                for body_line in method.body.split("\n"):
                    lines.append(f"    {body_line.strip()}" if body_line.strip() else "")
                lines.append("}")
            else:
                lines.append("{")
                if method.return_type and method.return_type != "void":
                    lines.append("    // TODO: implement")
                    default_returns = {
                        "int": "    return 0;",
                        "bool": "    return false;",
                        "float": "    return 0.0f;",
                        "double": "    return 0.0;",
                        "size_t": "    return 0;",
                    }
                    lines.append(default_returns.get(method.return_type, "    return {};"))
                else:
                    lines.append("    // TODO: implement")
                lines.append("}")
            lines.append("")

        # Process nested classes
        for nested in cls.nested_classes:
            self._generate_class_methods(nested, lines, include_existing_bodies, class_name)

        if cls.namespace:
            lines.append(f"}} // namespace {cls.namespace}")
            lines.append("")


def parse_and_display(header_path: str, cpp_path: Optional[str] = None) -> list[CppClass]:
    """Parse a header file and print a summary."""
    parser = HeaderParser()
    classes = parser.parse_header(header_path, cpp_path)

    print(f"Parsed {len(classes)} class(es) from {header_path}")
    print("=" * 60)
    for cls in classes:
        print(cls.summary())
        print("-" * 60)

    return classes


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python cpp_header_parser.py <header_file> [cpp_file] [--generate-cpp] [--json]")
        print()
        print("Options:")
        print("  --generate-cpp    Generate a .cpp file with method stubs")
        print("  --json            Output parsed structure as JSON")
        sys.exit(1)

    header_path = sys.argv[1]
    cpp_path = None
    generate_cpp = "--generate-cpp" in sys.argv
    output_json = "--json" in sys.argv

    # Find cpp_path from args (not a flag)
    for arg in sys.argv[2:]:
        if not arg.startswith("--"):
            cpp_path = arg
            break

    if not os.path.isfile(header_path):
        print(f"Error: File not found: {header_path}")
        sys.exit(1)

    parser = HeaderParser()
    classes = parser.parse_header(header_path, cpp_path)

    if output_json:
        print(json.dumps([c.to_dict() for c in classes], indent=2))
    else:
        print(f"Parsed {len(classes)} class(es) from {header_path}")
        print("=" * 60)
        for cls in classes:
            print(cls.summary())
            print("-" * 60)

    if generate_cpp:
        generator = CppFileGenerator()
        header_filename = os.path.basename(header_path)
        cpp_output = generator.generate_cpp(classes, header_filename)
        output_path = os.path.splitext(header_path)[0] + "_generated.cpp"
        with open(output_path, "w") as f:
            f.write(cpp_output)
        print(f"\nGenerated: {output_path}")


if __name__ == "__main__":
    main()
