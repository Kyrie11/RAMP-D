#include "rampd/interval_bicycle.h"

#include <boost/numeric/interval.hpp>
#include <boost/numeric/interval/rounded_transc.hpp>
#include <boost/numeric/interval/detail/c99_rounding_control.hpp>
#include <array>
#include <cmath>
#include <exception>
#include <limits>
#include <stdexcept>

namespace bn = boost::numeric;
struct DirectedRounding : bn::interval_lib::rounded_transc_std<double,
    bn::interval_lib::rounded_arith_std<double,
        bn::interval_lib::rounded_math<double>>> {
    /* Keep the complete arithmetic + transcendental API when Boost's
       unprotect helper removes the outer state guard. */
    using unprotected_rounding = DirectedRounding;
};
using Interval = bn::interval<double,
    bn::interval_lib::policies<DirectedRounding,
                              bn::interval_lib::checking_strict<double>>>;

namespace {
int write_interval(const Interval &v, double *lo, double *hi) {
    if (!lo || !hi) return 2;
    *lo = v.lower();
    *hi = v.upper();
    return (!std::isfinite(*lo) || !std::isfinite(*hi) || *lo > *hi) ? 3 : 0;
}
Interval make_interval(double lo, double hi) {
    if (!std::isfinite(lo) || !std::isfinite(hi) || lo > hi)
        throw std::invalid_argument("invalid interval endpoints");
    return Interval(lo, hi);
}
}

extern "C" {
int rampd_interval_add(double alo,double ahi,double blo,double bhi,double *ol,double *oh) {
    try { return write_interval(make_interval(alo,ahi)+make_interval(blo,bhi),ol,oh); }
    catch (...) { return 1; }
}
int rampd_interval_mul(double alo,double ahi,double blo,double bhi,double *ol,double *oh) {
    try { return write_interval(make_interval(alo,ahi)*make_interval(blo,bhi),ol,oh); }
    catch (...) { return 1; }
}
int rampd_interval_div(double alo,double ahi,double blo,double bhi,double *ol,double *oh) {
    try { if (blo <= 0.0 && bhi >= 0.0) return 4; return write_interval(make_interval(alo,ahi)/make_interval(blo,bhi),ol,oh); }
    catch (...) { return 1; }
}
int rampd_interval_sin(double lo,double hi,double *ol,double *oh) {
    try { return write_interval(bn::sin(make_interval(lo,hi)),ol,oh); }
    catch (...) { return 1; }
}
int rampd_interval_cos(double lo,double hi,double *ol,double *oh) {
    try { return write_interval(bn::cos(make_interval(lo,hi)),ol,oh); }
    catch (...) { return 1; }
}
int rampd_interval_tan(double lo,double hi,double *ol,double *oh) {
    try { return write_interval(bn::tan(make_interval(lo,hi)),ol,oh); }
    catch (...) { return 1; }
}

int rampd_bicycle_rhs(const double *xl,const double *xh,
                      const double *ul,const double *uh,
                      const double *wl,const double *wh,
                      double L,double *ol,double *oh) {
    try {
        if (!xl||!xh||!ul||!uh||!wl||!wh||!ol||!oh||!std::isfinite(L)||L<=0) return 2;
        std::array<Interval,6> x;
        std::array<Interval,2> u;
        std::array<Interval,6> w;
        for (int i=0;i<6;++i) { x[i]=make_interval(xl[i],xh[i]); w[i]=make_interval(wl[i],wh[i]); }
        for (int i=0;i<2;++i) u[i]=make_interval(ul[i],uh[i]);
        const Interval px_dot = x[3]*bn::cos(x[2]) + w[0];
        const Interval py_dot = x[3]*bn::sin(x[2]) + w[1];
        const Interval psi_dot = x[3]*bn::tan(x[5])/Interval(L) + w[2];
        const Interval v_dot = x[4] + w[3];
        const Interval a_dot = u[0] + w[4];
        const Interval delta_dot = u[1] + w[5];
        const std::array<Interval,6> f{px_dot,py_dot,psi_dot,v_dot,a_dot,delta_dot};
        for (int i=0;i<6;++i) { ol[i]=f[i].lower(); oh[i]=f[i].upper(); }
        return 0;
    } catch (...) { return 1; }
}

int rampd_friction_lhs(const double *xl,const double *xh,
                       double L,double mu,double g,double *ol,double *oh) {
    try {
        if (!xl||!xh||!ol||!oh||!std::isfinite(L)||!std::isfinite(mu)||!std::isfinite(g)||L<=0||mu<=0||g<=0) return 2;
        const Interval v=make_interval(xl[3],xh[3]);
        const Interval a=make_interval(xl[4],xh[4]);
        const Interval delta=make_interval(xl[5],xh[5]);
        const Interval scale(mu*g);
        const Interval longitudinal=a/scale;
        const Interval lateral=(bn::square(v)*bn::tan(delta))/(Interval(L)*scale);
        return write_interval(bn::square(longitudinal)+bn::square(lateral),ol,oh);
    } catch (...) { return 1; }
}
const char *rampd_interval_backend(void) { return "Boost.Numeric.Interval<double>/rounded_transc_std"; }
}
