#include "rampd/interval_bicycle.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

static bool contains(double lo,double hi,double x) { return lo<=x && x<=hi; }
int main() {
    double lo=0,hi=0;
    assert(rampd_interval_add(1,2,3,4,&lo,&hi)==0);
    assert(lo<=4 && hi>=6);
    assert(rampd_interval_mul(-2,3,4,5,&lo,&hi)==0);
    assert(lo<=-10 && hi>=15);
    assert(rampd_interval_div(1,2,0,1,&lo,&hi)!=0);
    assert(rampd_interval_sin(-1.5707963267948966,1.5707963267948966,&lo,&hi)==0);
    assert(lo<=0 && hi>=1);
    assert(rampd_interval_cos(0,3.1415926535897932,&lo,&hi)==0);
    assert(lo<=0 && hi>=1);
    assert(rampd_interval_tan(-0.2,0.2,&lo,&hi)==0);
    assert(lo<=std::tan(-0.2) && hi>=std::tan(0.2));

    double xl[6]={0,0,0.2,10,1,0.1}, xh[6]={0,0,0.3,11,2,0.2};
    double ul[2]={-1,-0.1}, uh[2]={1,0.1};
    double wl[6]={0,0,0,0,0,0}, wh[6]={0,0,0,0,0,0};
    double fl[6],fh[6];
    assert(rampd_bicycle_rhs(xl,xh,ul,uh,wl,wh,2.8,fl,fh)==0);
    for (int i=0;i<6;++i) assert(fl[i]<=fh[i]);
    assert(contains(fl[3],fh[3],1.5));
    assert(contains(fl[4],fh[4],0.0));
    double ql,qh;
    assert(rampd_friction_lhs(xl,xh,2.8,0.9,9.81,&ql,&qh)==0);
    assert(ql<=qh && ql>=0);
    std::cout << "PASS backend=" << rampd_interval_backend() << "\n";
}
