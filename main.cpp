#include "gum-builtins.hpp"
using namespace GumCpp;


int main(int argc, char *argv[]) {
    DictPtr d = static_cast<DictPtr>([&](){ DictPtr __d = std::make_shared<Dict>();  return __d; }());
    print("=== Empty ===");
    print(d);
    print("\n=== Insert ===");
    (*d)["name"] = "Ayaan";
    (*d)["age"] = 10;
    (*d)["pi"] = 3.14159;
    (*d)["cool"] = true;
    print(d);
    print("\n=== Read ===");
    std::string name = static_cast<std::string>((*d)["name"]);
    int age = static_cast<int>((*d)["age"]);
    double pi = static_cast<double>((*d)["pi"]);
    bool cool = static_cast<bool>((*d)["cool"]);
    print(name);
    print(age);
    print(pi);
    print(cool);
    print("\n=== Modify ===");
    (*d)["age"] = (age + 1);
    (*d)["name"] = "Bob";
    print(d);
    print("\n=== Read Again ===");
    print((*d)["name"]);
    print((*d)["age"]);
    print("\n=== Overwrite Types ===");
    (*d)["test"] = 123;
    print((*d)["test"]);
    (*d)["test"] = "hello";
    print((*d)["test"]);
    (*d)["test"] = false;
    print((*d)["test"]);
    print("\n=== Expression ===");
    int x = static_cast<int>(((*d)["age"] + 5));
    print(x);
    print("\n=== Done ===");
}