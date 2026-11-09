#include "rampd/interval_bicycle.h"
#include "test_support.hpp"
#include <cmath>
int main(){
    double x[6]={0,0,0,8,0,0},u[2]={0,0},w[6]={0,0,0,0,0,0};
    RampdPicardOptions opts{};opts.max_iterations=16;opts.relative_inflation=.125;
    for(double& a:opts.absolute_inflation)a=1.e-9;
    RampdPicardOutput out{};
    CHECK(rampd_picard_step(x,x,u,u,w,w,2.8,.125,&opts,&out)==0);
    CHECK(out.status==0 && out.iterations>0);
    for(int i=0;i<6;++i){
        CHECK(out.tube_lo[i]<out.picard_lo[i]);
        CHECK(out.picard_hi[i]<out.tube_hi[i]);
        CHECK(out.inclusion_margin_lo[i]>0);
    }
    CHECK(out.endpoint_lo[0]<=1 && out.endpoint_hi[0]>=1);
    CHECK(out.endpoint_lo[3]<=8 && out.endpoint_hi[3]>=8);
    opts.max_iterations=1;
    CHECK(rampd_picard_step(x,x,u,u,w,w,2.8,.125,&opts,&out)==0 && out.status==1);
    x[5]=1.6;opts.max_iterations=16;
    CHECK(rampd_picard_step(x,x,u,u,w,w,2.8,.125,&opts,&out)==0 && out.status==2);
    CHECK(rampd_picard_step(x,x,u,u,w,w,2.8,-1,&opts,&out)!=0);
    std::cout<<"PASS Picard inclusion, endpoint and failure semantics\n";
}
