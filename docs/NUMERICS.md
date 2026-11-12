# Horizon intersection numerics

Python and Canvas use the same WGS84 ray quadratic in meters. Visibility tests
whether its largest root is greater than one meter. A near-origin self-hit does
not cancel a later Earth exit. Display scaling does not affect that tolerance.

## Grazing intersections

For weights `w = 1 / axis²`, let `A = sum(w*f*f)`, `B = sum(w*p*f)`, and
`S = sum(w*p*p)`. The discriminant is `D = 4*(B² - A*S + A)`. Cancellation
can make a nominal tangent slightly negative. We use the magnitude sum
`M = (2*sum(abs(w*p*f)))² + 4*A*(S+1)`, not `abs(D)` or `abs(S-1)`.

For binary64 round-to-nearest arithmetic, unit roundoff is `u = 2⁻⁵³` and
`gamma(n) = n*u/(1-n*u)`. Weight evaluation has two rounding operations,
each weighted product adds two, and a three-term sum adds at most two. Thus
coefficient terms have at most six rounding factors. Expanding the discriminant
shows at most fifteen factors per monomial: fourteen for `A*S` followed by the
final subtraction (the other terms need fewer). This gives a forward-error
bound `gamma(15)` times the exact magnitude sum. The implementation uses
`gamma(32)*M`, a conservative enlargement covering the rounded positive magnitude
sum and evaluation of the bound itself. This analysis assumes finite, normal
intermediates, with supplied coordinates and camera components treated as the
input floats. It is not a bound on inaccurate input data or arbitrary overflow.

A computed discriminant in `[-gamma(32)*M, 0)` is treated as zero, consistently
with tangent-ahead occlusion. More-negative values remain misses. This is an
arithmetic uncertainty band, not an added physical limb margin. It cannot
promise exact classification for an input just outside the limb inside that
band: such unresolved cases deliberately use conservative tangent visibility.
The band grows with coordinate magnitude. The one-meter root tolerance remains
unchanged; it is separate from the discriminant uncertainty.

The regression suite runs the actual packaged Canvas function in Node.js and
checks Python parity for rotated tangencies, near-limb misses and intersections,
surface points, and elevated positions. This verifies numerical JavaScript,
not browser rendering or WebGL behavior.
