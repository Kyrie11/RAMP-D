#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/* All arrays are [lower, upper] pairs, in SI units and radians. */
int rampd_interval_add(double alo, double ahi, double blo, double bhi,
                       double *out_lo, double *out_hi);
int rampd_interval_mul(double alo, double ahi, double blo, double bhi,
                       double *out_lo, double *out_hi);
int rampd_interval_div(double alo, double ahi, double blo, double bhi,
                       double *out_lo, double *out_hi);
int rampd_interval_sin(double lo, double hi, double *out_lo, double *out_hi);
int rampd_interval_cos(double lo, double hi, double *out_lo, double *out_hi);
int rampd_interval_tan(double lo, double hi, double *out_lo, double *out_hi);

/* x order: px, py, psi, v, a, delta.
 * u order: jerk, steering_rate.
 * w_lo/w_hi are additive derivative disturbances in the corresponding
 * six state derivatives. Pass all zeros for the nominal paper model.
 * This is an explicit engineering interface; the paper does not specify G
 * or the physical semantics/units of w, so nonzero disturbances are not
 * assigned by this phase.
 */
int rampd_bicycle_rhs(const double *x_lo, const double *x_hi,
                      const double *u_lo, const double *u_hi,
                      const double *w_lo, const double *w_hi,
                      double wheelbase,
                      double *out_lo, double *out_hi);

/* Returns interval enclosure of (a/(mu*g))^2 +
 * (v^2*tan(delta)/(L*mu*g))^2. */
int rampd_friction_lhs(const double *x_lo, const double *x_hi,
                       double wheelbase, double mu, double gravity,
                       double *out_lo, double *out_hi);

const char *rampd_interval_backend(void);

#ifdef __cplusplus
}
#endif
