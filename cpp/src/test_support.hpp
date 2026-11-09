#pragma once
#include <cstdlib>
#include <iostream>
#define CHECK(x) do {if(!(x)){std::cerr<<__FILE__<<":"<<__LINE__<<" CHECK failed: " #x "\n";std::exit(1);}} while(false)
