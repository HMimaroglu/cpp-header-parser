# cpp-header-parser

A Python tool that parses C++ header files to extract class definitions, methods, and their arguments. It identifies whether each method is implemented inline in the header file or in a separate `.cpp` file, and can generate `.cpp` skeleton files from parsed declarations.

## Features

- Parses classes, structs, and their methods from `.h` / `.hpp` files
- Detects **inline implementations** (method body in the header) vs **declaration-only** methods
- Cross-references with a `.cpp` file to identify which declarations have external implementations
- Handles:
  - Single and multiple inheritance
  - Template classes and template member functions
  - Operator overloading (`+`, `<<`, `==`, `()`, `[]`, etc.)
  - Access specifiers (`public`, `private`, `protected`)
  - Virtual, pure virtual, override, and final methods
  - Static, const, constexpr, noexcept, explicit, and inline qualifiers
  - Deleted (`= delete`) and defaulted (`= default`) methods
  - Constructors, destructors, and initializer lists
  - Nested classes
  - Namespaces (including nested)
  - Friend functions
  - Default argument values
  - Function pointer arguments
  - Complex template return types (e.g. `std::map<std::string, int>`)
  - Move semantics (`&&`)
  - Comments (single-line `//` and multi-line `/* */`) and preprocessor directives
- Outputs a human-readable summary, JSON, or generates a `.cpp` implementation file

## Requirements

- Python 3.7+
- No external dependencies for the parser itself
- `pytest` for running tests

## Usage

### Command Line

```bash
# Parse a header file and display a summary
python cpp_header_parser.py myclass.h

# Parse with a corresponding .cpp file to identify implementation locations
python cpp_header_parser.py myclass.h myclass.cpp

# Output as JSON
python cpp_header_parser.py myclass.h --json

# Generate a .cpp file with method stubs
python cpp_header_parser.py myclass.h --generate-cpp
```

### As a Library

```python
from cpp_header_parser import HeaderParser, CppFileGenerator, AccessSpecifier, ImplementationLocation

# Parse a header file
parser = HeaderParser()
classes = parser.parse_header("myclass.h", "myclass.cpp")

for cls in classes:
    print(cls.summary())

    # Access methods by visibility
    for method in cls.get_methods_by_access(AccessSpecifier.PUBLIC):
        print(f"  {method.name}: {method.implementation_location.value}")

    # Get only header-implemented methods
    for method in cls.get_header_implemented():
        print(f"  Inline: {method.name}")

    # Get only cpp-implemented methods
    for method in cls.get_cpp_implemented():
        print(f"  External: {method.name}")

# Generate a .cpp file
generator = CppFileGenerator()
cpp_content = generator.generate_cpp(classes, "myclass.h")
print(cpp_content)

# Serialize to JSON
import json
print(json.dumps([c.to_dict() for c in classes], indent=2))
```

### Parsing from Strings (useful for testing)

```python
from cpp_header_parser import HeaderParser

header_code = """
class Calculator {
public:
    Calculator();
    int add(int a, int b);
    int multiply(int a, int b) { return a * b; }
};
"""

cpp_code = """
#include "calculator.h"
Calculator::Calculator() {}
int Calculator::add(int a, int b) { return a + b; }
"""

parser = HeaderParser()
classes = parser.parse_header_string(header_code, cpp_code)

for cls in classes:
    for method in cls.methods:
        print(f"{method.name}: {method.implementation_location.value}")
# Output:
#   Calculator: cpp
#   add: cpp
#   multiply: header
```

## Data Model

| Class | Description |
|-------|-------------|
| `CppArgument` | A single method argument (type, name, default value) |
| `CppMethod` | A class method with all its qualifiers and metadata |
| `CppClass` | A class/struct with its methods, base classes, and nested classes |
| `HeaderParser` | Reads `.h` files and builds the class structure |
| `CppFileGenerator` | Generates `.cpp` files from parsed class structures |

### Implementation Location

Each method is tagged with one of:

| Value | Meaning |
|-------|---------|
| `header` | Method body is defined inline in the header file |
| `cpp` | Method is implemented in the corresponding `.cpp` file |
| `declaration_only` | Method is only declared (no implementation found, or pure virtual / deleted / defaulted) |

## Running Tests

```bash
pytest tests/test_parser.py -v
```

The test suite covers 81 test cases across these categories:

- Comment and preprocessor stripping
- Argument parsing (templates, defaults, pointers, function pointers)
- Brace matching
- Basic class parsing with `.cpp` cross-referencing
- Access specifiers, constructors, destructors, virtual methods
- Single and multiple inheritance
- Template classes and member templates
- Operator overloading and friend functions
- Namespaces (single and nested)
- Nested classes
- Deleted/defaulted/constexpr/noexcept methods
- Edge cases (empty classes, structs, complex return types)
- Code generation
- JSON serialization

## Limitations

- This is a regex/heuristic-based parser, not a full C++ grammar parser. It handles the vast majority of common header patterns but may not handle every exotic C++ construct.
- Macros that expand to class/method definitions are not evaluated.
- `#if` / `#ifdef` conditional compilation blocks are stripped rather than evaluated.
- Enum classes and standalone functions outside classes are not parsed.

## License

MIT
