#ifndef INHERITANCE_H
#define INHERITANCE_H

#include <string>
#include <vector>

class Shape {
public:
    Shape();
    virtual ~Shape() = default;
    virtual double area() const = 0;
    virtual double perimeter() const = 0;
    virtual std::string type() const;
};

class Circle : public Shape {
public:
    explicit Circle(double radius);
    double area() const override;
    double perimeter() const override;
    std::string type() const override { return "Circle"; }
    double getRadius() const { return radius_; }

private:
    double radius_;
};

class Rectangle : public Shape {
public:
    Rectangle(double width, double height);
    double area() const override;
    double perimeter() const override;
    std::string type() const override;

private:
    double width_;
    double height_;
};

// Multiple inheritance
class Square : public Rectangle, public Printable {
public:
    explicit Square(double side);
    void print() const override;
};

#endif // INHERITANCE_H
