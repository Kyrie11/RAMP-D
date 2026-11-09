#pragma once
#include <array>
#include <stdexcept>
namespace rampd {
struct DomainError : std::domain_error { using std::domain_error::domain_error; };
struct NumericError : std::runtime_error { using std::runtime_error::runtime_error; };
struct I {
    double lo=0.0, hi=0.0;
    I()=default;
    explicit I(double a);
    I(double a,double b);
};
void check_environment();
I operator+(I,I); I operator-(I,I); I operator*(I,I); I operator/(I,I);
I square(I); I sqrt(I); I sin(I); I cos(I); I tan(I); I pi(); I decimal(const char*);
I hull(I,I); I inflate(I,double,double);
bool subset(I,I); bool interior(I,I);
using Box=std::array<I,6>;
using Control=std::array<I,2>;
Box rhs(const Box&,const Control&,const Box&,double);
I friction(const Box&,double,double,double);
void require_bicycle_domain(const Box&,double);
}
