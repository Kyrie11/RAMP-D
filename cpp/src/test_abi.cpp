#include "rampd/interval_bicycle.h"
#include "test_support.hpp"
#include <limits>
#include <cstring>
int main(){
    double lo=0,hi=0;
    CHECK(rampd_abi_version()==2);
    CHECK(std::strstr(rampd_interval_backend(),"MPFR")!=nullptr);
    CHECK(rampd_interval_add(1,2,3,4,nullptr,&hi)!=0);
    CHECK(rampd_interval_add(2,1,3,4,&lo,&hi)!=0);
    CHECK(std::strlen(rampd_last_error())>0);
    CHECK(rampd_interval_square(std::numeric_limits<double>::infinity(),1,&lo,&hi)!=0);
    CHECK(rampd_bicycle_rhs(nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,2.8,&lo,&hi)!=0);
    CHECK(rampd_interval_add(1,1,2,2,&lo,&hi)==0);
    CHECK(std::strlen(rampd_last_error())==0);
    std::cout<<"PASS ABI/error guard (checks remain active in Release)\n";
}
