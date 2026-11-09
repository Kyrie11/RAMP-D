#include "rampd/interval_bicycle.h"
#include "api_internal.hpp"
#include <algorithm>
#include <cmath>
using namespace rampd;
extern "C" int rampd_picard_step(const double* xl,const double* xh,const double* ul,const double* uh,
    const double* wl,const double* wh,double L,double h,const RampdPicardOptions* opt,RampdPicardOutput* out){
    return api([&]{
        require(opt);require(out);
        const auto x=read<6>(xl,xh), w=read<6>(wl,wh);
        const auto u=read<2>(ul,uh);
        if(!std::isfinite(h)||h<=0||!std::isfinite(L)||L<=0)
            throw std::invalid_argument("h and wheelbase must be finite and positive");
        if(opt->max_iterations<1||opt->max_iterations>1000||
           !std::isfinite(opt->relative_inflation)||opt->relative_inflation<0)
            throw std::invalid_argument("invalid Picard options");
        for(double a:opt->absolute_inflation) if(!std::isfinite(a)||a<=0)
            throw std::invalid_argument("absolute inflations must be finite and positive");
        RampdPicardOutput result{};result.status=1;
        try {
            Box z=x;
            for(int i=0;i<6;++i) z[i]=inflate(z[i],opt->absolute_inflation[i],opt->relative_inflation);
            for(int n=1;n<=opt->max_iterations;++n){
                result.iterations=n;
                const auto f=rhs(z,u,w,L);
                Box p,e; bool success=true;
                for(int i=0;i<6;++i){
                    p[i]=x[i]+I(0,h)*f[i]; e[i]=x[i]+I(h)*f[i];
                    success=success && interior(p[i],z[i]) && subset(e[i],z[i]);
                }
                if(success){
                    result.status=0;write(z,result.tube_lo,result.tube_hi);
                    write(f,result.field_lo,result.field_hi);write(p,result.picard_lo,result.picard_hi);
                    write(e,result.endpoint_lo,result.endpoint_hi);
                    for(int i=0;i<6;++i) result.inclusion_margin_lo[i]=std::min(
                        (I(p[i].lo)-I(z[i].lo)).lo,(I(z[i].hi)-I(p[i].hi)).lo);
                    *out=result;return;
                }
                if(n<opt->max_iterations) for(int i=0;i<6;++i) {
                    // Inflate only failing components. Inflating already-valid
                    // heading/steering components can make lateral bounds chase
                    // the same artificial uncertainty indefinitely. Recheck ALL
                    // components after every update. This changes search only.
                    if (!interior(p[i],z[i]))
                        z[i]=inflate(hull(z[i],p[i]),opt->absolute_inflation[i],opt->relative_inflation);
                }
            }
        }catch(const DomainError&){result.status=2;}
         catch(const NumericError&){result.status=3;}
        *out=result; // Failed candidate boxes are deliberately not exported.
    });
}
