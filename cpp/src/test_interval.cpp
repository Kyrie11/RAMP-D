#include "rampd/interval_bicycle.h"
#include "test_support.hpp"
#include <cfenv>
#include <cmath>
#include <limits>
int main(){
    double lo=0,hi=0;
    CHECK(rampd_interval_add(1,2,3,4,&lo,&hi)==0 && lo==4 && hi==6);
    CHECK(rampd_interval_sub(1,2,3,4,&lo,&hi)==0 && lo==-3 && hi==-1);
    CHECK(rampd_interval_mul(-2,3,4,5,&lo,&hi)==0 && lo==-10 && hi==15);
    CHECK(rampd_interval_square(-2,3,&lo,&hi)==0 && lo==0 && hi==9);
    CHECK(rampd_interval_div(1,2,-1,1,&lo,&hi)!=0);
    CHECK(rampd_interval_sin(-2,2,&lo,&hi)==0 && lo==-1 && hi==1);
    CHECK(rampd_interval_cos(-4,4,&lo,&hi)==0 && lo==-1 && hi==1);
    CHECK(rampd_interval_tan(1.5,1.7,&lo,&hi)!=0);
    CHECK(rampd_interval_sin(1.e20,1.e20,&lo,&hi)==0 && lo==-1 && hi==1);
    const double tiny=std::numeric_limits<double>::denorm_min();
    CHECK(rampd_interval_mul(tiny,tiny,.5,.5,&lo,&hi)==0 && lo==0 && hi==tiny);
    CHECK(rampd_interval_decimal("0.1",&lo,&hi)==0 && lo<hi);
    const int previous=std::fegetround();
    for(int mode:{FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO}){
        CHECK(std::fesetround(mode)==0);
        CHECK(rampd_interval_sin(.1,.2,&lo,&hi)==0);
        CHECK(std::fegetround()==mode);
        CHECK(rampd_interval_mul(.1,.2,.3,.4,&lo,&hi)==0);
        CHECK(std::fegetround()==mode);
    }
    CHECK(std::fesetround(previous)==0);
    std::cout<<"PASS interval and unchanged hardware rounding mode\n";
}
