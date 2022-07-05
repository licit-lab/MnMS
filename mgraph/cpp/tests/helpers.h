
#include <string>
#include <iostream>
#include <stdexcept>

#pragma once

inline void assertTrue(bool test, std::string message) {
    if(!test) {
        throw std::runtime_error(message);
    }
}



