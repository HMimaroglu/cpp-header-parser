#include "basic.h"
#include <iostream>

Animal::Animal() : name_(""), age_(0) {}

Animal::Animal(const std::string& name, int age)
    : name_(name), age_(age) {}

Animal::~Animal() {}

std::string Animal::getName() const {
    return name_;
}

void Animal::setName(const std::string& name) {
    name_ = name;
}

void Animal::move() {
    std::cout << name_ << " is moving." << std::endl;
}

void Animal::breathe() {
    // breathing
}

void Animal::digest() {
    // digesting
}
