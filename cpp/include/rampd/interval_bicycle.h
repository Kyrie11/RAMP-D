#pragma once
#ifdef __cplusplus
extern "C" {
#endif
/* ABI 3. Endpoints are finite binary64 values, interpreted exactly as reals.
   rc=0: completed; rc!=0: error, output is NOT to be consumed.
   Error text is thread-local. All arrays have the sizes documented below. */
int rampd_abi_version(void);
const char *rampd_last_error(void);
const char *rampd_interval_backend(void);
const char *rampd_build_info(void);
int rampd_interval_add(double,double,double,double,double*,double*);
int rampd_interval_sub(double,double,double,double,double*,double*);
int rampd_interval_mul(double,double,double,double,double*,double*);
int rampd_interval_div(double,double,double,double,double*,double*);
int rampd_interval_square(double,double,double*,double*);
int rampd_interval_sqrt(double,double,double*,double*);
int rampd_interval_sin(double,double,double*,double*);
int rampd_interval_cos(double,double,double*,double*);
/* tan rejects intervals possibly containing any pole. */
int rampd_interval_tan(double,double,double*,double*);
int rampd_interval_decimal(const char*,double*,double*);
int rampd_interval_pi(double*,double*);
/* x[6]=(px,py,psi,v,a,delta); u[2]=(j,omega_delta).
   w[6] is an explicitly supplied additive DERIVATIVE disturbance box.
   Nominal paper model: w=0. Vehicle steering is in (-pi/2,pi/2).
   No velocity clipping, state/input-limit check or collision check is done. */
int rampd_bicycle_rhs(const double*,const double*,const double*,const double*,
                      const double*,const double*,double,double*,double*);
int rampd_friction_lhs(const double*,const double*,double,double,double,double*,double*);

typedef struct {
    int max_iterations;
    double relative_inflation;
    double absolute_inflation[6];
} RampdPicardOptions;

typedef struct {
    /* 0=VALIDATED, 1=UNKNOWN_ITERATION_LIMIT, 2=UNKNOWN_DOMAIN,
       3=UNKNOWN_NUMERICS. Only status=0 carries a witness. */
    int status;
    int iterations;
    double tube_lo[6], tube_hi[6];
    double field_lo[6], field_hi[6];
    double picard_lo[6], picard_hi[6];
    double endpoint_lo[6], endpoint_hi[6];
    double inclusion_margin_lo[6];
} RampdPicardOutput;

/* One constant-control-image substep; h is an exact positive binary64 duration.
   Success requires STRICT componentwise Picard self-inclusion, a conservative
   strengthening of the paper's non-strict inclusion predicate. */
int rampd_picard_step(const double *xl,const double *xh,
                     const double *ul,const double *uh,
                     const double *wl,const double *wh,double wheelbase,double h,
                     const RampdPicardOptions*,RampdPicardOutput*);
#ifdef __cplusplus
}
#endif
