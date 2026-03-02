#pragma once

#include <vector>
#include <string>
#include <functional>

template <typename T>
class Stack {
public:
    Stack();
    explicit Stack(size_t capacity);
    ~Stack();

    void push(const T& value);
    void push(T&& value);
    T pop();
    const T& top() const;
    bool empty() const { return data_.empty(); }
    size_t size() const { return data_.size(); }

    template <typename U>
    bool contains(const U& value) const;

private:
    std::vector<T> data_;
    size_t capacity_;
};

template <typename K, typename V>
class SimpleMap {
public:
    void insert(const K& key, const V& value);
    V& get(const K& key);
    const V& get(const K& key) const;
    bool has(const K& key) const { return find(key) != nullptr; }
    size_t size() const;

private:
    const V* find(const K& key) const;
    std::vector<std::pair<K, V>> entries_;
};
