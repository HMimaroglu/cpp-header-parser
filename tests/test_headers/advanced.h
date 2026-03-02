#pragma once

#include <string>
#include <memory>
#include <functional>

namespace game {
namespace engine {

class Entity {
public:
    Entity();
    Entity(const std::string& name);
    Entity(const Entity& other) = delete;
    Entity& operator=(const Entity& other) = delete;
    Entity(Entity&& other) noexcept;
    Entity& operator=(Entity&& other) noexcept;
    virtual ~Entity() = default;

    int getId() const { return id_; }
    const std::string& getName() const { return name_; }
    void setName(const std::string& name);

    virtual void update(float deltaTime) = 0;
    virtual void render() const;

    // Static factory method
    static std::unique_ptr<Entity> create(const std::string& type);

protected:
    virtual void onActivate();
    virtual void onDeactivate();

    int id_;
    std::string name_;

private:
    static int nextId_;

    // Nested class
    class ComponentList {
    public:
        void add(int componentId);
        void remove(int componentId);
        bool has(int componentId) const;
        size_t count() const { return count_; }

    private:
        int* components_;
        size_t count_;
        size_t capacity_;
    };

    ComponentList components_;
};

class Player final : public Entity {
public:
    Player(const std::string& name, int health = 100);
    ~Player() override;

    void update(float deltaTime) override;
    void render() const override final;

    int getHealth() const noexcept { return health_; }
    void takeDamage(int amount) noexcept;
    bool isAlive() const noexcept { return health_ > 0; }

    // Callback registration
    void onDeath(std::function<void(const Player&)> callback);

private:
    int health_;
    std::function<void(const Player&)> deathCallback_;
};

} // namespace engine
} // namespace game
