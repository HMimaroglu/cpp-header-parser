#include "advanced.h"
#include <iostream>

namespace game {
namespace engine {

int Entity::nextId_ = 0;

Entity::Entity() : id_(nextId_++), name_("unnamed") {}

Entity::Entity(const std::string& name) : id_(nextId_++), name_(name) {}

Entity::Entity(Entity&& other) noexcept
    : id_(other.id_), name_(std::move(other.name_)) {}

Entity& Entity::operator=(Entity&& other) noexcept {
    if (this != &other) {
        id_ = other.id_;
        name_ = std::move(other.name_);
    }
    return *this;
}

void Entity::setName(const std::string& name) {
    name_ = name;
}

void Entity::render() const {
    std::cout << "Rendering entity: " << name_ << std::endl;
}

std::unique_ptr<Entity> Entity::create(const std::string& type) {
    return nullptr; // placeholder
}

void Entity::onActivate() {}
void Entity::onDeactivate() {}

// ComponentList methods
void Entity::ComponentList::add(int componentId) {}
void Entity::ComponentList::remove(int componentId) {}
bool Entity::ComponentList::has(int componentId) const { return false; }

// Player methods
Player::Player(const std::string& name, int health)
    : Entity(name), health_(health) {}

Player::~Player() {}

void Player::update(float deltaTime) {
    // update logic
}

void Player::render() const {
    std::cout << "Rendering player: " << getName() << std::endl;
}

void Player::takeDamage(int amount) noexcept {
    health_ -= amount;
    if (health_ <= 0 && deathCallback_) {
        deathCallback_(*this);
    }
}

void Player::onDeath(std::function<void(const Player&)> callback) {
    deathCallback_ = callback;
}

} // namespace engine
} // namespace game
