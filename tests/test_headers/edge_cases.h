#pragma once

#include <string>
#include <map>

// Edge case: Comments in tricky places
class /* inline comment */ Tricky {
public:
    // Constructor with initializer list
    Tricky(int a, int b) : a_(a), b_(b) {}

    // Method with multi-line signature
    void longMethod(
        const std::string& param1,
        int param2,
        double param3 = 3.14,
        bool param4 = true
    );

    // Const and non-const overloads
    int& getValue();
    const int& getValue() const;

    // Default and deleted
    Tricky() = default;
    Tricky(const Tricky&) = delete;
    Tricky& operator=(const Tricky&) = delete;
    Tricky(Tricky&&) = default;

    // Method with function pointer argument
    void setCallback(void (*callback)(int, int));

    // Method returning pointer
    int* getData();
    const int* getData() const;

    // Method with complex template return type
    std::map<std::string, int> getMapping() const;

    // Constexpr method
    constexpr int sum() const { return a_ + b_; }

    // Static constexpr
    static constexpr int MAX_VALUE = 100;

private:
    int a_;
    int b_;
};

// Empty class
class Empty {};

// Struct with all public by default
struct Point {
    double x;
    double y;

    Point() : x(0), y(0) {}
    Point(double x, double y) : x(x), y(y) {}

    double distanceTo(const Point& other) const;
    Point operator+(const Point& other) const {
        return Point(x + other.x, y + other.y);
    }
};
