#include "rampd/interval.hpp"
#include <mpfr.h>
#ifdef __FAST_MATH__
#error "fast-math is forbidden for validated interval arithmetic"
#endif
#include <algorithm>
#include <cmath>
#include <limits>
#if defined(__SSE__)
#include <xmmintrin.h>
#endif
namespace rampd {
namespace {
constexpr mpfr_prec_t precision=192;
struct MP {
    mpfr_t v;
    MP(){ mpfr_init2(v,precision); }
    ~MP(){ mpfr_clear(v); }
    MP(const MP&)=delete;
    MP& operator=(const MP&)=delete;
};
using Binary=int(*)(mpfr_ptr,mpfr_srcptr,mpfr_srcptr,mpfr_rnd_t);
using Unary=int(*)(mpfr_ptr,mpfr_srcptr,mpfr_rnd_t);
double binary(double a,double b,Binary op,mpfr_rnd_t r) {
    MP x,y,z;
    mpfr_set_d(x.v,a,MPFR_RNDN); mpfr_set_d(y.v,b,MPFR_RNDN);
    op(z.v,x.v,y.v,r);
    return mpfr_get_d(z.v,r);
}
double unary(double a,Unary op,mpfr_rnd_t r) {
    MP x,z; mpfr_set_d(x.v,a,MPFR_RNDN); op(z.v,x.v,r);
    return mpfr_get_d(z.v,r);
}
/* All arithmetic paths use MPFR, including conversion back to double. */
I finite_result(double lo,double hi) {
    if (!std::isfinite(lo)||!std::isfinite(hi)||lo>hi)
        throw NumericError("non-finite/invalid interval result");
    return I(lo,hi);
}
I trig(I x,bool is_sin) {
    /* Deliberately conservative for huge arguments. No unvalidated reduction. */
    if (std::max(std::abs(x.lo),std::abs(x.hi))>1.e6) return I(-1,1);
    const auto fn=is_sin ? mpfr_sin : mpfr_cos;
    double lo=std::min(unary(x.lo,fn,MPFR_RNDD),unary(x.hi,fn,MPFR_RNDD));
    double hi=std::max(unary(x.lo,fn,MPFR_RNDU),unary(x.hi,fn,MPFR_RNDU));
    /* Possible critical points: sin at pi/2+k*pi; cos at k*pi.
       Interval quotient encloses the TRUE pi; false positives only widen. */
    I q=x/pi();
    if (is_sin) q=q-I(0.5);
    const double first=std::ceil(q.lo), last=std::floor(q.hi);
    if (first<=last) {
        if (last-first>=1.0) return I(-1,1);
        const long k=static_cast<long>(first); // bounded by argument threshold
        if (k%2==0) hi=1.0; else lo=-1.0;
    }
    return finite_result(lo,hi);
}
}
I::I(double a):I(a,a){}
I::I(double a,double b):lo(a),hi(b) {
    if (!std::isfinite(a)||!std::isfinite(b)||a>b)
        throw std::invalid_argument("invalid finite interval endpoints");
}
void check_environment() {
    static_assert(std::numeric_limits<double>::is_iec559 &&
                  std::numeric_limits<double>::digits==53,
                  "IEEE binary64 double required");
    if (mpfr_get_emin()>-10000 || mpfr_get_emax()<10000)
        throw NumericError("MPFR exponent range was narrowed by external code");
#if defined(__SSE__)
    if ((_mm_getcsr() & ((1u<<15)|(1u<<6)))!=0)
        throw NumericError("disable SSE flush-to-zero/denormals-are-zero (FTZ/DAZ)");
#endif
}
I operator+(I a,I b) {
    return finite_result(binary(a.lo,b.lo,mpfr_add,MPFR_RNDD),
                         binary(a.hi,b.hi,mpfr_add,MPFR_RNDU));
}
I operator-(I a,I b) {
    return finite_result(binary(a.lo,b.hi,mpfr_sub,MPFR_RNDD),
                         binary(a.hi,b.lo,mpfr_sub,MPFR_RNDU));
}
I operator*(I a,I b) {
    double lo=std::numeric_limits<double>::infinity(), hi=-lo;
    for (double x:{a.lo,a.hi}) for(double y:{b.lo,b.hi}) {
        lo=std::min(lo,binary(x,y,mpfr_mul,MPFR_RNDD));
        hi=std::max(hi,binary(x,y,mpfr_mul,MPFR_RNDU));
    }
    return finite_result(lo,hi);
}
I operator/(I a,I b) {
    if (b.lo<=0 && b.hi>=0) throw DomainError("division interval contains zero");
    double lo=std::numeric_limits<double>::infinity(), hi=-lo;
    for (double x:{a.lo,a.hi}) for(double y:{b.lo,b.hi}) {
        lo=std::min(lo,binary(x,y,mpfr_div,MPFR_RNDD));
        hi=std::max(hi,binary(x,y,mpfr_div,MPFR_RNDU));
    }
    return finite_result(lo,hi);
}
I square(I a) {
    double lo=(a.lo<=0 && a.hi>=0) ? 0.0 :
        std::min(unary(a.lo,mpfr_sqr,MPFR_RNDD),unary(a.hi,mpfr_sqr,MPFR_RNDD));
    return finite_result(lo,std::max(unary(a.lo,mpfr_sqr,MPFR_RNDU),
                                    unary(a.hi,mpfr_sqr,MPFR_RNDU)));
}
I pi() {
    MP l,r; mpfr_const_pi(l.v,MPFR_RNDD); mpfr_const_pi(r.v,MPFR_RNDU);
    return finite_result(mpfr_get_d(l.v,MPFR_RNDD),mpfr_get_d(r.v,MPFR_RNDU));
}
I decimal(const char* s) {
    if (!s || !*s) throw std::invalid_argument("empty decimal string");
    MP l,r; char *end1=nullptr,*end2=nullptr;
    mpfr_strtofr(l.v,s,&end1,10,MPFR_RNDD);
    mpfr_strtofr(r.v,s,&end2,10,MPFR_RNDU);
    if (end1==s||*end1!='\0'||end2==s||*end2!='\0')
        throw std::invalid_argument("invalid decimal string");
    return finite_result(mpfr_get_d(l.v,MPFR_RNDD),mpfr_get_d(r.v,MPFR_RNDU));
}
I sin(I x){return trig(x,true);}
I cos(I x){return trig(x,false);}
I tan(I x) {
    if (std::max(std::abs(x.lo),std::abs(x.hi))>1.e6)
        throw DomainError("tan argument outside supported reduction range");
    const I q=x/pi()-I(0.5);
    if (std::ceil(q.lo)<=std::floor(q.hi))
        throw DomainError("tan interval may contain a pole");
    return finite_result(unary(x.lo,mpfr_tan,MPFR_RNDD),
                         unary(x.hi,mpfr_tan,MPFR_RNDU));
}
I hull(I a,I b){return I(std::min(a.lo,b.lo),std::max(a.hi,b.hi));}
bool subset(I a,I b){return b.lo<=a.lo && a.hi<=b.hi;}
bool interior(I a,I b){return b.lo<a.lo && a.hi<b.hi;}
I inflate(I a,double absolute,double relative) {
    I width=I(a.hi)-I(a.lo);
    I pad=I(absolute)+I(relative)*width;
    return a+I(-pad.hi,pad.hi);
}
void require_bicycle_domain(const Box& x,double L) {
    if (!std::isfinite(L)||L<=0) throw std::invalid_argument("wheelbase must be finite and positive");
    const double inner_half_pi=(pi()/I(2.0)).lo;
    if (!(x[5].lo>-inner_half_pi && x[5].hi<inner_half_pi))
        throw DomainError("steering box not proved inside (-pi/2,pi/2)");
}
Box rhs(const Box& x,const Control& u,const Box& w,double L) {
    require_bicycle_domain(x,L);
    return {x[3]*cos(x[2])+w[0], x[3]*sin(x[2])+w[1],
            x[3]*tan(x[5])/I(L)+w[2], x[4]+w[3],u[0]+w[4],u[1]+w[5]};
}
I friction(const Box& x,double L,double mu,double g) {
    require_bicycle_domain(x,L);
    if (!std::isfinite(mu)||!std::isfinite(g)||mu<=0||g<=0)
        throw std::invalid_argument("mu and gravity must be finite and positive");
    const I scale=I(mu)*I(g); // Never construct I(mu*g): that loses error.
    return square(x[4]/scale)+square((square(x[3])*tan(x[5]))/(I(L)*scale));
}
}
