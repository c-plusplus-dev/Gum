#pragma once
#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <vector>
#include <cstddef>
#include <stdexcept>
#include <variant>
#include <sstream>
#include <memory>
#include <utility>
#include <type_traits>

#if defined(__APPLE__)
#include <crt_externs.h>  // for _NSGetArgc / _NSGetArgv -- macOS has no global argc/argv
#endif


namespace GumCpp {
    class Value;

    class Dict;
    class List;

    using ListPtr = std::shared_ptr<List>;
    using DictPtr = std::shared_ptr<Dict>;

    enum class ValueType {
        Null,
        Int,
        Double,
        Bool,
        String,
        List,
        Dict
    };

    class Value {
    public:
        using Variant = std::variant<
            std::monostate,
            int,
            double,
            bool,
            std::string,
            ListPtr,
            DictPtr
        >;

    private:
        Variant data;

    public:
        Value() : data(std::monostate{}) {}
        Value(int v) : data(v) {}
        Value(double v) : data(v) {}
        Value(bool v) : data(v) {}
        Value(const char* s) : data(std::string(s)) {}
        Value(const std::string& s) : data(s) {}
        Value(const ListPtr& l) : data(l) {}
        Value(const DictPtr& d) : data(d) {}

        template<typename T>
        [[nodiscard]] bool is() const {
            return std::holds_alternative<T>(data);
        }

        template<typename T>
        T& as() {
            return std::get<T>(data);
        }

        template<typename T>
        const T& as() const {
            return std::get<T>(data);
        }

        [[nodiscard]]
        ValueType type() const noexcept {
            return static_cast<ValueType>(data.index());
        }

        [[nodiscard]]
        bool isNumeric() const noexcept {
            switch (type()) {
            case ValueType::Int:
            case ValueType::Double:
            case ValueType::Bool:
                return true;
            default:
                return false;
            }
        }

        [[nodiscard]]
        bool isFloating() const noexcept {
            return type() == ValueType::Double;
        }

        [[nodiscard]]
        bool isIntegral() const noexcept {
            return type() == ValueType::Int ||
                   type() == ValueType::Bool;
        }

        [[nodiscard]]
        double asNumber() const {
            switch (type()) {

            case ValueType::Int:
                return std::get<int>(data);

            case ValueType::Double:
                return std::get<double>(data);

            case ValueType::Bool:
                return std::get<bool>(data);

            default:
                throw std::runtime_error("Expected numeric value");
            }
        }

        [[nodiscard]]
        int asInteger() const {
            switch (type()) {

            case ValueType::Int:
                return std::get<int>(data);

            case ValueType::Bool:
                return std::get<bool>(data);

            default:
                throw std::runtime_error("Expected integral value");
            }
        }

        friend bool operator==(const Value& a,
                       const Value& b)
        {
            return a.data == b.data;
        }

        friend std::ostream& operator<<(std::ostream& os, const Value& value);

        [[nodiscard]] int toInt() const {
            return std::visit([](const auto& value) -> int {
                using T = std::decay_t<decltype(value)>;

                if constexpr (std::is_same_v<T, int>)
                    return value;

                else if constexpr (std::is_same_v<T, double>)
                    return static_cast<int>(value);

                else if constexpr (std::is_same_v<T, bool>)
                    return value ? 1 : 0;

                else if constexpr (std::is_same_v<T, std::string>) {
                    try {
                        size_t pos;
                        int v = std::stoi(value, &pos);
                        if (pos != value.size())
                            throw std::runtime_error("");
                        return v;
                    } catch (...) {
                        throw std::runtime_error("Cannot convert string \"" + value + "\" to int");
                    }
                }

                else
                    throw std::runtime_error("Value cannot be converted to int");
            }, data);
        }

        [[nodiscard]] double toDouble() const {
            return std::visit([](const auto& value) -> double {
                using T = std::decay_t<decltype(value)>;

                if constexpr (std::is_same_v<T, int>)
                    return static_cast<double>(value);

                else if constexpr (std::is_same_v<T, double>)
                    return value;

                else if constexpr (std::is_same_v<T, bool>)
                    return value ? 1.0 : 0.0;

                else if constexpr (std::is_same_v<T, std::string>) {
                    try {
                        size_t pos;
                        double v = std::stod(value, &pos);
                        if (pos != value.size())
                            throw std::runtime_error("");
                        return v;
                    } catch (...) {
                        throw std::runtime_error("Cannot convert string \"" + value + "\" to float");
                    }
                }

                else
                    throw std::runtime_error("Value cannot be converted to float");
            }, data);
        }

        [[nodiscard]] bool toBool() const;

        [[nodiscard]] std::string toString() const;

        [[nodiscard]] ListPtr toList() const {
            if (!std::holds_alternative<ListPtr>(data))
                throw std::runtime_error("Value is not a list");
            return std::get<ListPtr>(data);
        }

        [[nodiscard]] DictPtr toDict() const {
            if (!std::holds_alternative<DictPtr>(data))
                throw std::runtime_error("Value is not a dict");
            return std::get<DictPtr>(data);
        }

        explicit operator int() const {
            return toInt();
        }

        explicit operator double() const {
            return toDouble();
        }

        explicit operator bool() const {
            return toBool();
        }

        explicit operator std::string() const {
            return toString();
        }

        explicit operator ListPtr() const {
            return toList();
        }

        explicit operator DictPtr() const {
            return toDict();
        }

        template<typename IntOp, typename DoubleOp>
        static Value numericOp(
            const Value& a,
            const Value& b,
            IntOp intOp,
            DoubleOp doubleOp)
        {
            if (!a.isNumeric() || !b.isNumeric())
                throw std::runtime_error("Expected numbers");

            if (a.isFloating() || b.isFloating())
                return doubleOp(a.toDouble(), b.toDouble());

            return intOp(a.toInt(), b.toInt());
        }

        friend Value operator+(const Value& a, const Value& b)
        {
            if (a.is<std::string>() || b.is<std::string>())
                return a.toString() + b.toString();

            return numericOp(
                a,
                b,
                [](int x, int y) { return x + y; },
                [](double x, double y) { return x + y; }
            );
        }
    };


    class List {
        std::vector<Value> data;

    public:
        List() = default;

        List(std::initializer_list<Value> init) : data(init) {}

        void append(const Value& value) {
            data.push_back(value);
        }

        Value& operator[](std::size_t index) {
            if (index >= data.size()) throw std::out_of_range("Index out of range");
            return data[index];
        }

        const Value& operator[](std::size_t index) const {
            if (index >= data.size()) throw std::out_of_range("Index out of range");
            return data[index];
        }

        [[nodiscard]] std::size_t length() const {
            return data.size();
        }

        [[nodiscard]] const std::vector<Value>& raw() const {
            return data;
        }

        auto begin() { return data.begin(); }
        auto end() { return data.end(); }

        [[nodiscard]] auto begin() const { return data.begin(); }
        [[nodiscard]] auto end() const { return data.end(); }

        friend std::ostream& operator<<(std::ostream& os, const List& list) {
            os << "[";
            for (std::size_t i = 0; i < list.data.size(); ++i) {
                os << list.data[i];
                if (i + 1 < list.data.size()) os << ", ";
            }
            os << "]";
            return os;
        }
    };

    class Dict {
        std::vector<std::pair<Value, Value>> data;

    public:
        Dict() = default;

        void set(const Value& key, const Value& value) {
            for (auto& entry : data) {
                if (entry.first == key) { entry.second = value; return; }
            }
            data.emplace_back(key, value);
        }

        Value& operator[](const Value& key) {
            for (auto& entry : data) {
                if (entry.first == key) return entry.second;
            }
            data.emplace_back(key, Value{});
            return data.back().second;
        }

        [[nodiscard]] bool has(const Value& key) const {
            for (auto& entry : data)
                if (entry.first == key) return true;
            return false;
        }

        void erase(const Value& key) {
            for (auto it = data.begin(); it != data.end(); ++it) {
                if (it->first == key) { data.erase(it); return; }
            }
        }

        [[nodiscard]] std::size_t length() const { return data.size(); }

        auto begin() { return data.begin(); }
        auto end() { return data.end(); }
        [[nodiscard]] auto begin() const { return data.begin(); }
        [[nodiscard]] auto end() const { return data.end(); }

        friend std::ostream& operator<<(std::ostream& os, const Dict& dict) {
            os << "{";

            if (!dict.data.empty()) {
                os << '\n';

                for (std::size_t i = 0; i < dict.data.size(); ++i) {
                    os << "    ";
                    os << dict.data[i].first;
                    os << ": ";
                    os << dict.data[i].second;

                    if (i + 1 < dict.data.size())
                        os << ",\n";
                }

                os << '\n';
            }

            os << "}";

            return os;
        }
    };

    inline std::ostream& operator<<(std::ostream& os, const DictPtr& ptr)
    {
        if (ptr)
            os << *ptr;
        else
            os << "null";
        return os;
    }

    inline std::ostream& operator<<(std::ostream& os, const ListPtr& ptr)
    {
        if (ptr)
            os << *ptr;
        else
            os << "null";
        return os;
    }

    inline std::string Value::toString() const {
        return std::visit([](const auto& value) -> std::string {
            using T = std::decay_t<decltype(value)>;

            if constexpr (std::is_same_v<T, std::string>)
                return value;

            else if constexpr (std::is_same_v<T, int>)
                return std::to_string(value);

            else if constexpr (std::is_same_v<T, double>) {
                std::ostringstream out;
                out << value;
                return out.str();
            }

            else if constexpr (std::is_same_v<T, bool>)
                return value ? "true" : "false";

            else if constexpr (std::is_same_v<T, std::monostate>)
                return "null";

            else {
                std::ostringstream out;
                if (value == nullptr) {
                    throw std::runtime_error("Cannot convert null pointer to string");
                }
                out << *value;
                return out.str();
            }
        }, data);
    }

    inline bool Value::toBool() const {
        return std::visit([](const auto& value) -> bool {
            using T = std::decay_t<decltype(value)>;

            if constexpr (std::is_same_v<T, bool>)
                return value;

            else if constexpr (std::is_same_v<T, int>)
                return value != 0;

            else if constexpr (std::is_same_v<T, double>)
                return value != 0.0;

            else if constexpr (std::is_same_v<T, std::string>) {
                if (value == "true")
                    return true;
                if (value == "false")
                    return false;
                throw std::runtime_error("Cannot convert string \"" + value + "\" to bool");
            }

            else if constexpr (std::is_same_v<T, ListPtr>)
                return value && value->length() != 0;

            else if constexpr (std::is_same_v<T, DictPtr>)
                return value && value->length() != 0;

            else
                return false;
        }, data);
    }

    inline std::ostream& operator<<(std::ostream& os, const Value& value)
    {
        std::visit([&]<typename T0>(T0&& arg)
        {
            using T = std::decay_t<T0>;

            if constexpr (std::is_same_v<T, std::monostate>)
                os << "null";

            else if constexpr (std::is_same_v<T, ListPtr>)
                os << *arg;

            else if constexpr (std::is_same_v<T, DictPtr>)
                os << *arg;

            else
                os << arg;

        }, value.data);

        return os;
    }

    inline std::size_t len(const DictPtr& d) { return d->length(); }

    inline void print() {
        std::cout << std::endl;
    }

    template<typename T, typename... Rest>
    void print(const T& first, const Rest&... rest) {
        std::cout << first;
        if constexpr (sizeof...(rest) > 0) std::cout << " ";
        print(rest...);
    }

    inline void sleep(double seconds) {
        std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
    }

    inline int floor(double value) {
        int i = static_cast<int>(value);
        return (value < 0 && value != i) ? i - 1 : i;
    }

    template<typename T, typename U>
    auto max(const T& a, const U& b) {
        return a > b ? a : b;
    }

    template<typename T, typename U>
    auto min(const T& a, const U& b) {
        return a < b ? a : b;
    }

    inline ListPtr range(int start, int end, bool inclusive = false) {
        ListPtr result = std::make_shared<List>();
        if (start <= end) {
            for (int i = start; i < end + (inclusive ? 1 : 0); ++i) result->append(i);
        } else {
            for (int i = start; i > end - (inclusive ? 1 : 0); --i) result->append(i);
        }
        return result;
    }

    inline std::size_t len(const ListPtr& vec) {
        return vec->length();
    }

    template<typename T>
    std::string to_string_any(const T& value) {
        std::ostringstream out;
        out << value;
        return out.str();
    }

    inline std::string fmt(const std::string& format) {
        return format;
    }

    template<typename T, typename... Rest>
    std::string fmt(const std::string& format, const T& value, const Rest&... rest) {
        std::string result = format;

        size_t open = result.find('{');
        if (open != std::string::npos) {
            size_t close = result.find('}', open);

            if (close != std::string::npos) {
                std::string spec = result.substr(open + 1, close - open - 1);

                std::string replacement = to_string_any(value);

                // Supports {:02}, {:03}, {:10}, ...
                if (spec.size() >= 3 &&
                    spec[0] == ':' &&
                    spec[1] == '0')
                {
                    try {
                        int width = std::stoi(spec.substr(2));

                        if (replacement.size() < static_cast<size_t>(width)) {
                            replacement.insert(
                                0,
                                width - replacement.size(),
                                '0'
                            );
                        }
                    }
                    catch (...) {
                        // Invalid format specifier, leave unformatted.
                    }
                }

                result.replace(
                    open,
                    close - open + 1,
                    replacement
                );
            }
        }

        if constexpr (sizeof...(rest) > 0) {
            return fmt(result, rest...);
        }

        return result;
    }

    // --- Command-line argument access -------------------------------------
    // Gum's generated main() takes (argc, argv) as C++ locals, which aren't
    // reachable from free functions declared here. On macOS there's no
    // global argc/argv (unlike Linux's `environ`), so we go through
    // _NSGetArgc()/_NSGetArgv() from <crt_externs.h> instead -- this reads
    // the process's actual argv regardless of where it's called from, with
    // no changes needed to the transpiler or generated main signature.

    inline int argCount() {
#if defined(__APPLE__)
        return *_NSGetArgc();
#else
        throw std::runtime_error("argCount(): only supported on macOS in this build");
#endif
    }

    inline std::string arg(int index) {
#if defined(__APPLE__)
        char** argv = *_NSGetArgv();
        int count = *_NSGetArgc();
        if (index < 0 || index >= count) {
            throw std::out_of_range(
                "arg: index " + std::to_string(index) +
                " out of range (argc=" + std::to_string(count) + ")");
        }
        return {argv[index]};
#else
        throw std::runtime_error("arg(): only supported on macOS in this build");
#endif
    }

    inline std::string readLine() {
        std::string line;
        if (!std::getline(std::cin, line)) {
            // stdin closed = the host process is tearing this worker down
            std::exit(0);
        }
        return line;
    }
}
