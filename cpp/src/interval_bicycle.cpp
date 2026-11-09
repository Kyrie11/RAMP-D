#include "rampd/interval_bicycle.h"
#include "api_internal.hpp"
#include <mpfr.h>
#include <sstream>
namespace rampd {thread_local std::string last_error;}
using namespace rampd;
extern "C" {
int rampd_abi_version(void){return 3;}
const char* rampd_last_error(void){return last_error.c_str();}
const char* rampd_interval_backend(void){return "MPFR-192/directed-binary64/ABI3";}
const char* rampd_build_info(void){
    static const std::string value=[](){std::ostringstream s;
        s<<"compiler="<<__VERSION__<<";mpfr_runtime="<<mpfr_get_version()
         <<";precision_bits=192;abi=3;api=0.4.0";
#ifdef MPFR_VERSION_STRING
        s<<";mpfr_header="<<MPFR_VERSION_STRING;
#else
        s<<";mpfr_header=bootstrap_public_API_declarations";
#endif
        return s.str();}();
    return value.c_str();
}
#define BINARY(NAME,OP) int rampd_interval_##NAME(double al,double ah,double bl,double bh,double* l,double* h){return api([&]{write(I(al,ah) OP I(bl,bh),l,h);});}
BINARY(add,+) BINARY(sub,-) BINARY(mul,*) BINARY(div,/)
#undef BINARY
#define UNARY(NAME) int rampd_interval_##NAME(double a,double b,double* l,double* h){return api([&]{write(rampd::NAME(I(a,b)),l,h);});}
UNARY(square) UNARY(sqrt) UNARY(sin) UNARY(cos) UNARY(tan)
#undef UNARY
int rampd_interval_pi(double* l,double* h){return api([&]{write(pi(),l,h);});}
int rampd_interval_decimal(const char* s,double* l,double* h){return api([&]{write(decimal(s),l,h);});}
int rampd_bicycle_rhs(const double* xl,const double* xh,const double* ul,const double* uh,
                     const double* wl,const double* wh,double L,double* l,double* h){
    return api([&]{auto f=rhs(read<6>(xl,xh),read<2>(ul,uh),read<6>(wl,wh),L);write(f,l,h);});
}
int rampd_friction_lhs(const double* xl,const double* xh,double L,double mu,double g,double* l,double* h){
    return api([&]{write(friction(read<6>(xl,xh),L,mu,g),l,h);});
}
}
