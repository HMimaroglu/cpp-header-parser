"""Comprehensive tests for the C++ header parser."""

from __future__ import annotations

import os
import sys
import json
import pytest
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cpp_header_parser import (
    HeaderParser,
    CppFileGenerator,
    CppClass,
    CppMethod,
    CppArgument,
    AccessSpecifier,
    ImplementationLocation,
    _strip_comments,
    _strip_preprocessor,
    _parse_arguments,
    _find_matching_brace,
)

HEADERS_DIR = os.path.join(os.path.dirname(__file__), "test_headers")


# ── Helper ──────────────────────────────────────────────────────────────────


def parse(header: str, cpp: Optional[str] = None) -> list[CppClass]:
    return HeaderParser().parse_header_string(header, cpp)


def find_class(classes: list[CppClass], name: str) -> CppClass:
    for c in classes:
        if c.name == name:
            return c
    raise ValueError(f"Class '{name}' not found")


def find_method(cls: CppClass, name: str) -> CppMethod:
    for m in cls.methods:
        if m.name == name:
            return m
    raise ValueError(f"Method '{name}' not found in class '{cls.name}'")


# ── Comment stripping ───────────────────────────────────────────────────────


class TestStripComments:
    def test_single_line_comment(self):
        result = _strip_comments("int x; // comment\nint y;")
        assert "comment" not in result
        assert "int x;" in result
        assert "int y;" in result

    def test_multi_line_comment(self):
        result = _strip_comments("int x; /* multi\nline */ int y;")
        assert "multi" not in result
        assert "int x;" in result
        assert "int y;" in result

    def test_string_with_slashes(self):
        result = _strip_comments('std::string s = "http://example.com";')
        assert "http://example.com" in result

    def test_string_with_comment_chars(self):
        result = _strip_comments('const char* s = "/* not a comment */";')
        assert "not a comment" in result

    def test_escaped_quote_in_string(self):
        result = _strip_comments(r'const char* s = "he said \"hi\""; // comment')
        assert "comment" not in result
        assert "he said" in result


class TestStripPreprocessor:
    def test_include(self):
        result = _strip_preprocessor('#include <iostream>\nint x;')
        assert "include" not in result
        assert "int x;" in result

    def test_multiline_macro(self):
        result = _strip_preprocessor('#define FOO \\\n  bar\nint x;')
        assert "FOO" not in result
        assert "bar" not in result
        assert "int x;" in result

    def test_pragma_once(self):
        result = _strip_preprocessor('#pragma once\nclass Foo {};')
        assert "pragma" not in result
        assert "class Foo" in result


# ── Argument parsing ────────────────────────────────────────────────────────


class TestParseArguments:
    def test_empty(self):
        assert _parse_arguments("") == []

    def test_void(self):
        assert _parse_arguments("void") == []

    def test_single_int(self):
        args = _parse_arguments("int x")
        assert len(args) == 1
        assert args[0].arg_type == "int"
        assert args[0].name == "x"

    def test_const_ref(self):
        args = _parse_arguments("const std::string& name")
        assert len(args) == 1
        assert args[0].arg_type == "const std::string&"
        assert args[0].name == "name"

    def test_default_value(self):
        args = _parse_arguments("int x = 42")
        assert len(args) == 1
        assert args[0].arg_type == "int"
        assert args[0].name == "x"
        assert args[0].default_value == "42"

    def test_multiple_args(self):
        args = _parse_arguments("int a, double b, const std::string& c")
        assert len(args) == 3
        assert args[0].name == "a"
        assert args[1].name == "b"
        assert args[2].name == "c"

    def test_template_arg(self):
        args = _parse_arguments("std::map<std::string, int> mapping")
        assert len(args) == 1
        assert "map" in args[0].arg_type
        assert args[0].name == "mapping"

    def test_pointer_arg(self):
        args = _parse_arguments("int* ptr")
        assert len(args) == 1
        assert args[0].name == "ptr"

    def test_unnamed_arg(self):
        args = _parse_arguments("int")
        assert len(args) == 1
        assert args[0].name == ""

    def test_complex_default(self):
        args = _parse_arguments('const std::string& name = "default"')
        assert len(args) == 1
        assert args[0].default_value == '"default"'

    def test_function_pointer(self):
        args = _parse_arguments("void (*callback)(int, int)")
        assert len(args) == 1
        assert args[0].name == "callback"


# ── Brace matching ──────────────────────────────────────────────────────────


class TestBraceMatching:
    def test_simple(self):
        assert _find_matching_brace("{ }", 0) == 2

    def test_nested(self):
        assert _find_matching_brace("{ { } }", 0) == 6

    def test_with_string(self):
        assert _find_matching_brace('{ "}" }', 0) == 6

    def test_no_match(self):
        assert _find_matching_brace("{ ", 0) == -1


# ── Basic class parsing ────────────────────────────────────────────────────


class TestBasicParsing:
    def test_parse_basic_header_file(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "basic.h"))
        assert len(classes) == 1

        animal = classes[0]
        assert animal.name == "Animal"
        assert not animal.is_struct
        assert len(animal.methods) > 0

    def test_basic_with_cpp(self):
        parser = HeaderParser()
        classes = parser.parse_header(
            os.path.join(HEADERS_DIR, "basic.h"),
            os.path.join(HEADERS_DIR, "basic.cpp"),
        )
        animal = classes[0]

        # Methods implemented in cpp
        get_name = find_method(animal, "getName")
        assert get_name.implementation_location == ImplementationLocation.CPP

        set_name = find_method(animal, "setName")
        assert set_name.implementation_location == ImplementationLocation.CPP

        # Methods inline in header
        get_age = find_method(animal, "getAge")
        assert get_age.implementation_location == ImplementationLocation.HEADER

        set_age = find_method(animal, "setAge")
        assert set_age.implementation_location == ImplementationLocation.HEADER

        # Pure virtual
        speak = find_method(animal, "speak")
        assert speak.is_pure_virtual
        assert speak.implementation_location == ImplementationLocation.DECLARATION_ONLY

    def test_access_specifiers(self):
        parser = HeaderParser()
        classes = parser.parse_header(
            os.path.join(HEADERS_DIR, "basic.h"),
            os.path.join(HEADERS_DIR, "basic.cpp"),
        )
        animal = classes[0]

        public_methods = animal.get_methods_by_access(AccessSpecifier.PUBLIC)
        protected_methods = animal.get_methods_by_access(AccessSpecifier.PROTECTED)
        private_methods = animal.get_methods_by_access(AccessSpecifier.PRIVATE)

        public_names = {m.name for m in public_methods}
        assert "getName" in public_names
        assert "setName" in public_names
        assert "speak" in public_names

        protected_names = {m.name for m in protected_methods}
        assert "breathe" in protected_names

        private_names = {m.name for m in private_methods}
        assert "digest" in private_names

    def test_constructor_destructor(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "basic.h"))
        animal = classes[0]

        constructors = [m for m in animal.methods if m.is_constructor]
        assert len(constructors) >= 1

        destructors = [m for m in animal.methods if m.is_destructor]
        assert len(destructors) == 1
        assert destructors[0].is_virtual

    def test_virtual_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "basic.h"))
        animal = classes[0]

        speak = find_method(animal, "speak")
        assert speak.is_virtual
        assert speak.is_pure_virtual

        move = find_method(animal, "move")
        assert move.is_virtual
        assert not move.is_pure_virtual

    def test_const_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "basic.h"))
        animal = classes[0]

        get_name = find_method(animal, "getName")
        assert get_name.is_const


# ── Inheritance ─────────────────────────────────────────────────────────────


class TestInheritance:
    def test_single_inheritance(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "inheritance.h"))

        circle = find_class(classes, "Circle")
        assert len(circle.base_classes) == 1
        assert circle.base_classes[0] == ("public", "Shape")

    def test_multiple_inheritance(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "inheritance.h"))

        square = find_class(classes, "Square")
        assert len(square.base_classes) == 2
        base_names = [b[1] for b in square.base_classes]
        assert "Rectangle" in base_names
        assert "Printable" in base_names

    def test_override(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "inheritance.h"))

        circle = find_class(classes, "Circle")
        area = find_method(circle, "area")
        assert area.is_override
        assert area.is_const

    def test_explicit_constructor(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "inheritance.h"))

        circle = find_class(classes, "Circle")
        constructors = [m for m in circle.methods if m.is_constructor]
        assert any(c.is_explicit for c in constructors)

    def test_inline_override(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "inheritance.h"))

        circle = find_class(classes, "Circle")
        type_method = find_method(circle, "type")
        assert type_method.is_override
        assert type_method.implementation_location == ImplementationLocation.HEADER


# ── Templates ───────────────────────────────────────────────────────────────


class TestTemplates:
    def test_class_template(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "templates.h"))

        stack = find_class(classes, "Stack")
        assert stack.template_params is not None
        assert "T" in stack.template_params

    def test_multi_param_template(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "templates.h"))

        simple_map = find_class(classes, "SimpleMap")
        assert simple_map.template_params is not None
        assert "K" in simple_map.template_params
        assert "V" in simple_map.template_params

    def test_template_class_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "templates.h"))

        stack = find_class(classes, "Stack")
        push_methods = [m for m in stack.methods if m.name == "push"]
        assert len(push_methods) == 2  # const& and && overloads

    def test_inline_template_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "templates.h"))

        stack = find_class(classes, "Stack")
        empty = find_method(stack, "empty")
        assert empty.implementation_location == ImplementationLocation.HEADER

    def test_member_template(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "templates.h"))

        stack = find_class(classes, "Stack")
        contains = find_method(stack, "contains")
        assert contains.template_params is not None
        assert "U" in contains.template_params


# ── Operator overloading ────────────────────────────────────────────────────


class TestOperators:
    def test_arithmetic_operators(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "operators.h"))

        vec = find_class(classes, "Vector2D")
        operators = [m for m in vec.methods if m.is_operator]
        op_names = [m.name for m in operators]

        assert any("+" in n for n in op_names)
        assert any("-" in n for n in op_names)
        assert any("*" in n for n in op_names)

    def test_comparison_operators_inline(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "operators.h"))

        vec = find_class(classes, "Vector2D")
        eq_ops = [m for m in vec.methods if m.is_operator and "==" in m.name]
        assert len(eq_ops) >= 1
        assert eq_ops[0].implementation_location == ImplementationLocation.HEADER

    def test_friend_operators(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "operators.h"))

        vec = find_class(classes, "Vector2D")
        friend_methods = [m for m in vec.methods if m.is_friend]
        assert len(friend_methods) >= 1

    def test_constructor_inline(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "operators.h"))

        vec = find_class(classes, "Vector2D")
        constructors = [m for m in vec.methods if m.is_constructor]
        inline_constructors = [
            c for c in constructors if c.implementation_location == ImplementationLocation.HEADER
        ]
        assert len(inline_constructors) >= 1


# ── Advanced features ───────────────────────────────────────────────────────


class TestAdvancedFeatures:
    def test_namespace(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        assert entity.namespace is not None
        assert "engine" in entity.namespace

    def test_nested_class(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        assert len(entity.nested_classes) >= 1
        comp_list = entity.nested_classes[0]
        assert comp_list.name == "ComponentList"
        assert len(comp_list.methods) > 0

    def test_deleted_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        deleted = [m for m in entity.methods if m.is_delete]
        assert len(deleted) >= 2  # copy ctor and copy assignment

    def test_defaulted_methods(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        defaulted = [m for m in entity.methods if m.is_default]
        assert len(defaulted) >= 1  # virtual ~Entity() = default

    def test_noexcept(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        move_ctor = None
        for m in entity.methods:
            if m.is_constructor and m.is_noexcept:
                move_ctor = m
                break
        assert move_ctor is not None

    def test_static_method(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        entity = find_class(classes, "Entity")
        create = find_method(entity, "create")
        assert create.is_static

    def test_final_class(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        player = find_class(classes, "Player")
        assert player is not None

    def test_default_arguments(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        player = find_class(classes, "Player")
        constructors = [m for m in player.methods if m.is_constructor]
        assert any(
            any(a.default_value is not None for a in c.arguments)
            for c in constructors
        )

    def test_cpp_cross_reference(self):
        parser = HeaderParser()
        classes = parser.parse_header(
            os.path.join(HEADERS_DIR, "advanced.h"),
            os.path.join(HEADERS_DIR, "advanced.cpp"),
        )

        entity = find_class(classes, "Entity")
        set_name = find_method(entity, "setName")
        assert set_name.implementation_location == ImplementationLocation.CPP

        render = find_method(entity, "render")
        assert render.implementation_location == ImplementationLocation.CPP

        # Inline stays header
        get_id = find_method(entity, "getId")
        assert get_id.implementation_location == ImplementationLocation.HEADER

    def test_cpp_cross_reference_player(self):
        parser = HeaderParser()
        classes = parser.parse_header(
            os.path.join(HEADERS_DIR, "advanced.h"),
            os.path.join(HEADERS_DIR, "advanced.cpp"),
        )

        player = find_class(classes, "Player")
        update = find_method(player, "update")
        assert update.implementation_location == ImplementationLocation.CPP

        get_health = find_method(player, "getHealth")
        assert get_health.implementation_location == ImplementationLocation.HEADER

    def test_callback_argument(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "advanced.h"))

        player = find_class(classes, "Player")
        on_death = find_method(player, "onDeath")
        assert len(on_death.arguments) == 1
        assert "function" in on_death.arguments[0].arg_type


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_deleted_and_defaulted(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        deleted = [m for m in tricky.methods if m.is_delete]
        assert len(deleted) >= 1

        defaulted = [m for m in tricky.methods if m.is_default]
        assert len(defaulted) >= 1

    def test_constexpr_method(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        sum_method = find_method(tricky, "sum")
        assert sum_method.is_constexpr
        assert sum_method.is_const

    def test_default_argument_values(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        long_method = find_method(tricky, "longMethod")
        assert len(long_method.arguments) == 4

        # Check default values
        defaults = [a.default_value for a in long_method.arguments]
        assert defaults[0] is None
        assert defaults[1] is None
        assert defaults[2] is not None  # 3.14
        assert defaults[3] is not None  # true

    def test_pointer_return(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        get_data_methods = [m for m in tricky.methods if m.name == "getData"]
        assert len(get_data_methods) >= 1

    def test_empty_class(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        empty = find_class(classes, "Empty")
        assert len(empty.methods) == 0

    def test_struct_default_public(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        point = find_class(classes, "Point")
        assert point.is_struct

        # Struct members should default to public
        for method in point.methods:
            assert method.access == AccessSpecifier.PUBLIC

    def test_complex_template_return(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        get_mapping = find_method(tricky, "getMapping")
        assert "map" in get_mapping.return_type

    def test_inline_constructor_with_init_list(self):
        parser = HeaderParser()
        classes = parser.parse_header(os.path.join(HEADERS_DIR, "edge_cases.h"))

        tricky = find_class(classes, "Tricky")
        constructors = [m for m in tricky.methods if m.is_constructor]
        inline_ctors = [
            c for c in constructors
            if c.implementation_location == ImplementationLocation.HEADER
        ]
        assert len(inline_ctors) >= 1


# ── String-based tests (no files) ──────────────────────────────────────────


class TestStringParsing:
    def test_simple_class(self):
        header = """
        class Foo {
        public:
            void bar();
            int baz() const { return 42; }
        };
        """
        classes = parse(header)
        assert len(classes) == 1
        assert classes[0].name == "Foo"
        assert len(classes[0].methods) == 2

    def test_struct(self):
        header = """
        struct Data {
            int getValue();
            void setValue(int v);
        };
        """
        classes = parse(header)
        assert len(classes) == 1
        assert classes[0].is_struct
        # Struct methods default to public
        for m in classes[0].methods:
            assert m.access == AccessSpecifier.PUBLIC

    def test_multiple_classes(self):
        header = """
        class A {
        public:
            void foo();
        };

        class B {
        public:
            void bar();
        };
        """
        classes = parse(header)
        assert len(classes) == 2
        names = {c.name for c in classes}
        assert names == {"A", "B"}

    def test_cpp_cross_reference_string(self):
        header = """
        class Calc {
        public:
            int add(int a, int b);
            int subtract(int a, int b);
            int multiply(int a, int b) { return a * b; }
        };
        """
        cpp = """
        #include "calc.h"
        int Calc::add(int a, int b) { return a + b; }
        int Calc::subtract(int a, int b) { return a - b; }
        """
        classes = parse(header, cpp)
        calc = classes[0]

        add = find_method(calc, "add")
        assert add.implementation_location == ImplementationLocation.CPP

        subtract = find_method(calc, "subtract")
        assert subtract.implementation_location == ImplementationLocation.CPP

        multiply = find_method(calc, "multiply")
        assert multiply.implementation_location == ImplementationLocation.HEADER

    def test_namespace(self):
        header = """
        namespace mylib {
            class Widget {
            public:
                void draw();
            };
        }
        """
        classes = parse(header)
        assert len(classes) == 1
        assert classes[0].namespace == "mylib"

    def test_nested_namespace(self):
        header = """
        namespace outer {
        namespace inner {
            class Item {
            public:
                void process();
            };
        }
        }
        """
        classes = parse(header)
        assert len(classes) == 1
        assert "inner" in classes[0].namespace

    def test_move_semantics(self):
        header = """
        class Buffer {
        public:
            Buffer(Buffer&& other) noexcept;
            Buffer& operator=(Buffer&& other) noexcept;
        };
        """
        classes = parse(header)
        buf = classes[0]
        move_ctor = [m for m in buf.methods if m.is_constructor and m.is_noexcept]
        assert len(move_ctor) == 1

    def test_method_with_no_args(self):
        header = """
        class Timer {
        public:
            void start();
            void stop();
            double elapsed() const;
        };
        """
        classes = parse(header)
        timer = classes[0]
        for m in timer.methods:
            assert len(m.arguments) == 0

    def test_overloaded_methods(self):
        header = """
        class Logger {
        public:
            void log(const char* msg);
            void log(const std::string& msg);
            void log(int level, const char* msg);
        };
        """
        classes = parse(header)
        logger = classes[0]
        log_methods = [m for m in logger.methods if m.name == "log"]
        assert len(log_methods) == 3

    def test_comments_preserved_outside_methods(self):
        header = """
        class Documented {
        public:
            // This method does something
            void doSomething();
            /* Multi-line
               comment */
            void doOther();
        };
        """
        classes = parse(header)
        assert len(classes[0].methods) == 2


# ── Code generation ─────────────────────────────────────────────────────────


class TestCodeGeneration:
    def test_generate_stubs(self):
        header = """
        class Calculator {
        public:
            Calculator();
            ~Calculator();
            int add(int a, int b);
            void reset();
        };
        """
        classes = parse(header)
        gen = CppFileGenerator()
        output = gen.generate_cpp(classes, "calculator.h")

        assert '#include "calculator.h"' in output
        assert "Calculator::Calculator()" in output
        assert "Calculator::~Calculator()" in output
        assert "Calculator::add(" in output
        assert "Calculator::reset()" in output

    def test_skip_pure_virtual(self):
        header = """
        class Base {
        public:
            virtual void doIt() = 0;
        };
        """
        classes = parse(header)
        gen = CppFileGenerator()
        output = gen.generate_cpp(classes, "base.h")

        assert "Base::doIt" not in output

    def test_skip_deleted(self):
        header = """
        class NoCopy {
        public:
            NoCopy(const NoCopy&) = delete;
            void work();
        };
        """
        classes = parse(header)
        gen = CppFileGenerator()
        output = gen.generate_cpp(classes, "nocopy.h")

        assert "NoCopy::work" in output
        # Deleted methods should not be in cpp
        lines = output.split("\n")
        assert not any("NoCopy(const NoCopy&)" in line for line in lines)

    def test_todo_comments(self):
        header = """
        class Service {
        public:
            int getValue();
            void doWork();
        };
        """
        classes = parse(header)
        gen = CppFileGenerator()
        output = gen.generate_cpp(classes, "service.h", include_existing_bodies=False)

        assert "TODO" in output

    def test_copy_inline_body(self):
        header = """
        class Quick {
        public:
            int answer() { return 42; }
        };
        """
        classes = parse(header)
        gen = CppFileGenerator()
        output = gen.generate_cpp(classes, "quick.h", include_existing_bodies=True)

        assert "return 42" in output


# ── Serialization ───────────────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict(self):
        header = """
        class Simple {
        public:
            void foo(int x, double y = 1.0);
        };
        """
        classes = parse(header)
        d = classes[0].to_dict()

        assert d["name"] == "Simple"
        assert len(d["methods"]) == 1
        assert d["methods"][0]["name"] == "foo"
        assert len(d["methods"][0]["arguments"]) == 2

    def test_json_roundtrip(self):
        header = """
        class Config {
        public:
            Config();
            void load(const std::string& path);
            bool save() const;
        };
        """
        classes = parse(header)
        json_str = json.dumps([c.to_dict() for c in classes])
        data = json.loads(json_str)

        assert len(data) == 1
        assert data[0]["name"] == "Config"
        assert len(data[0]["methods"]) == 3


# ── Summary / display ──────────────────────────────────────────────────────


class TestSummary:
    def test_summary_output(self):
        header = """
        class Demo {
        public:
            void publicMethod();
        private:
            void privateMethod();
        protected:
            void protectedMethod();
        };
        """
        classes = parse(header)
        summary = classes[0].summary()

        assert "Demo" in summary
        assert "public" in summary
        assert "private" in summary
        assert "protected" in summary

    def test_summary_shows_location(self):
        header = """
        class Mixed {
        public:
            void declared();
            void inlined() { }
        };
        """
        cpp = """
        void Mixed::declared() {}
        """
        classes = parse(header, cpp)
        summary = classes[0].summary()

        assert "header" in summary
        assert "cpp" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
