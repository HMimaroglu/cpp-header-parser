#pragma once

class Animal {
public:
    Animal();
    Animal(const std::string& name, int age);
    virtual ~Animal();

    std::string getName() const;
    void setName(const std::string& name);
    int getAge() const { return age_; }
    void setAge(int age) { age_ = age; }

    virtual void speak() = 0;
    virtual void move();

protected:
    void breathe();

private:
    std::string name_;
    int age_;
    void digest();
};
