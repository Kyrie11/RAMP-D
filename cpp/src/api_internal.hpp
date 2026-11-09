#pragma once
#include "rampd/interval.hpp"
#include <string>
namespace rampd {
extern thread_local std::string last_error;
template<class Fn> int api(Fn&& fn) noexcept {
    try { last_error.clear(); check_environment(); fn(); return 0; }
    catch (const std::invalid_argument& e){ last_error=e.what(); return 2; }
    catch (const DomainError& e){ last_error=e.what(); return 4; }
    catch (const std::exception& e){ last_error=e.what(); return 3; }
    catch (...){ last_error="unknown native error"; return 3; }
}
inline void require(const void* p){if(!p) throw std::invalid_argument("null pointer");}
template<size_t N> std::array<I,N> read(const double* l,const double* h) {
    require(l);require(h); std::array<I,N> out;
    for(size_t i=0;i<N;++i) out[i]=I(l[i],h[i]);
    return out;
}
inline void write(I x,double* l,double* h){require(l);require(h); *l=x.lo;*h=x.hi;}
inline void write(const Box& x,double* l,double* h){
    require(l);require(h);for(int i=0;i<6;++i){l[i]=x[i].lo;h[i]=x[i].hi;}
}
}
