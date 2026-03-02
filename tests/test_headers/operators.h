#pragma once

#include <iostream>
#include <string>

class Vector2D {
public:
    Vector2D() : x_(0), y_(0) {}
    Vector2D(double x, double y) : x_(x), y_(y) {}

    // Arithmetic operators
    Vector2D operator+(const Vector2D& other) const;
    Vector2D operator-(const Vector2D& other) const;
    Vector2D operator*(double scalar) const;
    Vector2D& operator+=(const Vector2D& other);
    Vector2D& operator-=(const Vector2D& other);
    Vector2D& operator*=(double scalar);

    // Comparison operators
    bool operator==(const Vector2D& other) const {
        return x_ == other.x_ && y_ == other.y_;
    }
    bool operator!=(const Vector2D& other) const {
        return !(*this == other);
    }

    // Subscript operator
    double& operator[](int index);
    const double& operator[](int index) const;

    // Stream operators
    friend std::ostream& operator<<(std::ostream& os, const Vector2D& v);
    friend std::istream& operator>>(std::istream& is, Vector2D& v);

    // Type conversion
    explicit operator bool() const { return x_ != 0 || y_ != 0; }

    // Function call operator
    double operator()(int index) const;

    double getX() const { return x_; }
    double getY() const { return y_; }

private:
    double x_;
    double y_;
};
