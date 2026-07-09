## **From Euler to AI: Unifying Formulas for** **Mathematical Constants**

**Tomer Raz** **Michael Shalyt** **Elyasheev Leibtag** **Rotem Kalisch**
**Shachar Weinbaum** **Yaron Hadad** **Ido Kaminer** _[∗]_
Technion – Israel Institute of Technology,

Haifa 3200003, Israel


**Abstract**


The constant _π_ has fascinated scholars throughout the centuries, inspiring numerous
formulas for its evaluation, such as infinite sums and continued fractions. Despite
their individual significance, many of the underlying connections among formulas
remain unknown, missing unifying theories that could unveil deeper understanding.
The absence of a unifying theory reflects a broader challenge across math and
science: knowledge is typically accumulated through isolated discoveries, while
deeper connections often remain hidden. In this work, we present an automated
framework for the unification of mathematical formulas. Our system combines
large language models (LLMs) for systematic formula harvesting, an LLM-code
feedback loop for validation, and a novel symbolic algorithm for clustering and
eventual unification. We demonstrate this methodology on the hallmark case of
_π_, an ideal testing ground for symbolic unification. Applying this approach to
455,050 arXiv papers, we validate 385 distinct formulas for _π_ and prove relations
between 360 (94%) of them, of which 166 (43%) can be derived from a single
mathematical object—linking canonical formulas by Euler, Gauss, Brouncker,
and newer ones from algorithmic discoveries by the Ramanujan Machine. Our
method generalizes to other constants, including _e_, _ζ_ (3), and Catalan’s constant,
demonstrating the potential of AI-assisted mathematics to uncover hidden structures
and unify knowledge across domains.


**1** **Introduction**


The earliest rigorous approximation for _π_ dates back to Archimedes around 250 BCE, who established
the bounds [223] 71 _[<]_ _[π]_ _[<]_ [22] 7 [[][16][].] [Modern] _[ π]_ [approximations employ more sophisticated formulas.]

For example, the Chudnovsky algorithm [15], derived from a formula by Ramanujan [48], remains
instrumental for precision records. Similarly, the BBP formula [6] is notable for enabling computation
of specific _π_ digits without requiring prior digits. Such breakthroughs inspired fundamental advances
in computer science, such as high-precision arithmetic [7], evolutionary optimization [35], and elliptic
curve cryptography [39]. Recent efforts led to the development of computer algorithms capable
of generating numerous formula hypotheses and sometimes proofs for mathematical constants

[9, 17, 46].


_∗_ Corresponding author: kaminer@technion.ac.il

Project repository: [https://github.com/RamanujanMachine/euler2ai](https://github.com/RamanujanMachine/euler2ai)


39th Conference on Neural Information Processing Systems (NeurIPS 2025).


**2** **Mathematical background**


**2.1** **Recurrences as universal representations of formulas for mathematical constants**


A wide range of formulas—including infinite sums, products, and continued fractions—can be
converted into recurrences, providing a cohesive framework for unification. A function _un_ satisfies a
recurrence of order _m_ if _un_ = _a_ 1 _,nun−_ 1 + _a_ 2 _,nun−_ 2 + _. . ._ + _am,nun−m_, which can be represented
via the associated companion matrix:



CM( _n_ ) :=



0 0 _. . ._ 0 _am,n_

1 0 _. . ._ 0 _am−_ 1 _,n_
0 1 _. . ._ 0 _am−_ 2 _,n_

 ... ... ... ... ...

0 0 _. . ._ 1 _a_ 1 _,n_







 (1)





By incrementally multiplying the companion matrix over _n_ steps, we get the matrix:




- _n_
_i_ =1 [CM(] _[i]_ [) =]



 _p_ 1 _,n−m_ _. . ._ _p_ 1 _,n−_ 1 _p_ 1 _,n_

 _p_ 2 _,n−m_ _. . ._ _p_ 2 _,n−_ 1 _p_ 2 _,n_
 _p_ 3 _,n−m_ _. . ._ _p_ 3 _,n−_ 1 _p_ 3 _,n_

 ... ... ... ...

_pm,n−m_ _. . ._ _pm,n−_ 1 _pm,n_







 (2)





_p_ 1 _,n, . . . pm,n_ are solutions to the recurrence for the initial conditions _pi,j_ = _δi_ _[j]_ [.] [Other solutions for]

different initial conditions can be written as linear combinations of these.



Recurrences evaluate a desired constant _L_ either directly lim _n→∞_ _un_ = _L_ (e.g., for infinite sums), or
as ratios lim _n→∞_ _pqnn_ [=] _[ L]_ [ with] _[ p][n]_ [and] _[ q][n]_ [being two solutions for the recurrence (e.g., for continued]

fractions). In the special case of a second-order recurrence, _un_ = _anun−_ 1 + _bnun−_ 2, and any pair of
solutions is associated with a formula in the form of a continued fraction:



_b_ 1



= _[p]_ _qn_ _[n]_ (3)



= _[p][n]_



_a_ 1 + _b_ 2
... + _bn_

_an_



When the functions _an_ = _a_ ( _n_ ) and _bn_ = _b_ ( _n_ ) are polynomials, the formula above is known as a
Polynomial Continued Fraction (PCF), denoted by PCF ( _a_ ( _n_ ) _, b_ ( _n_ )). See details in Appendix E.


**2.2** **The dynamical metrics describing each formula**


A formula of a mathematical constant _L_ provides a converging sequence of rational numbers _[p]_ _qn_ _[n]_

(known as a _Diophantine approximation_ ). The formula can be characterized by _dynamical metrics_
capturing properties such as its convergence rate. A recent paper [52] proposed using such metrics
for formula discovery and clustering. Here we use the metrics of _convergence rate_ and _irrationality_
_measure_ . The _convergence rate_ is defined as:



(4)
����



_r_ = lim

_n→∞_



1
_n_ [log]



_pn_
_L −_
���� _qn_



When examining the connection of two candidate formulas, the ratio of their _r_ values can hint
whether one is a transformation of a subsequence of the other (see Appendix E.5 for an example).
The _irrationality measure_ of _[p]_ _qn_ _[n]_ [is defined as the limit] _[ δ]_ [= lim] _[n][→∞]_ _[δ][n]_ [, where]



log



��




_δn_ = _−_ 1 _−_



(5)
log _|qn|_



��� _L −_ _pqnn_



We found that two formulas sharing the same _δ_ is the strongest indication of a possible relation, since
_δ_ is invariant under many transformations and choice of subsequences. Below, our UMAPS algorithm
is used to derive and prove a relation once a pair of formulas share the same _r_ and _δ_ .


**2.3** **Conservative Matrix Fields (CMFs)**


The CMF is the mathematical structure that generalizes formulas of a particular constant, originally
found by generalizing PCFs [21], and later realized to be more general (Appendix G). To exemplify the


3


concept, we focus on the CMF of _π_ . This CMF is 3D, i.e., consisting of three matrices _M_ **x** _, M_ **y** _, M_ **z**
with rational function entries in the variables ( _x, y, z_ ), satisfying:


_M_ **x** ( _x, y, z_ ) _M_ **y** ( _x_ + 1 _, y, z_ ) = _M_ **y** ( _x, y, z_ ) _M_ **x** ( _x, y_ + 1 _, z_ )

_M_ **x** ( _x, y, z_ ) _M_ **z** ( _x_ + 1 _, y, z_ ) = _M_ **z** ( _x, y, z_ ) _M_ **x** ( _x, y, z_ + 1)
_M_ **y** ( _x, y, z_ ) _M_ **z** ( _x, y_ + 1 _, z_ ) = _M_ **z** ( _x, y, z_ ) _M_ **y** ( _x, y, z_ + 1)


This property describes the path-independence of the transition between two points in a 3D lattice
(lattice illustrated in Fig. 5b), in analogy to a conservative vector field. The CMF satisfies the
properties of a discrete flat connection [11]. For an explanation of how formulas reside as directions
within the CMF, see Appendix G.1. A notable feature of the CMF is that pairs of formulas found to
be parallel trajectories with different initial points correspond to two matrices that are coboundary
equivalent.


Many of the known _π_ formulas will be shown to reside within a single CMF (details in Appendix G.2):







�1 _x_
1 _x_ +2 _y−_
_y_ _y_



_y_




- _z_ ( _−x−y_ + _z_ )
( _y−z_ )( _x−z_ )



_z_ ( _−x−y_ + _z_ ) _zxy_
( _y−z_ )( _x−z_ ) ( _y−z_ )( _x−z_ )

_z_ _−z_ [2]
( _y−z_ )( _x−z_ ) ( _y−z_ )( _x−z_ )



_−z_ [2]
( _y−z_ )( _x−z_ )




_M_ **y** =



_M_ **x** =



�1 _y_
1 2 _x_ + _y−_ 2 _z_ +2
_x_ _x_



_x_ +2 _y−_ 2 _z_ +2




_M_ **z** =



(6)



**3** **Methodology for symbolic unification of formulas**


**3.1** **Harvesting:** **large-scale retrieval of formulas from the literature**



The first challenge lies in the natural language processing of formulas.
We analyze the L [A] TEX source code of
455,050 arXiv articles by combining
regular expressions and LLMs, extracting all mathematical expressions,
resulting in 278,242,506 strings. Filtering for expressions containing the
_π_ symbol retrieves 121,662 _π_ -related
equations. The widespread use of the
symbol _π_ in scientific literature means
that most occurrences are unrelated to
calculating the constant itself. To address this, and keeping in mind that
there is a priori very little data on
what successful formulas’ L [A] TEX looks
like, each potential formula is classified as computing _π_ or not, using
GPT-4o mini [41] (chosen for its costeffectiveness), reducing the number of
candidates to 3367. Next, GPT-4o categorizes formulas by type: series, continued fraction, or neither—resulting
in 1656 formula candidates.


**3.2** **Harvesting:**
**extraction and validation**

The extraction and validation stages
rely on an LLM-code feedback loop
that feeds a PSLQ algorithm. Each
equation, represented as a L [A] TEX
string, must then be parsed into a
Computer Algebra System (CAS) for
further manipulations (in our case,
SymPy [38]). Automatically extracting algebraic forms from L [A] TEX strings
is especially complicated due to varied L [A] TEX patterns, which are difficult



|Harvesting scheme|Example|
|---|---|
||`Guillera, Jesús. "Bilateral sums related to Ramanujan-like series."`_`arXiv`_<br>_`preprint`_` arXiv:1610.04839 (2016).`|
|articles<br>455,050|articles<br>455,050|
|scraping<br>||
|278,242,506<br>equations|278,242,506<br>equations|
|retrieval<br><br>|`"\sum_{n = 0}^{\infty} (-1)^n \frac{(\frac12)_n (\frac14)_n`<br>`(\frac34)_n}{(1)_n^3} \frac{21460n + 1123}{882^{2n}} = \frac{3528}{\pi}."`|
|equations<br>121,662|equations<br>121,662|
|computes π?<br>series or<br>continued<br>fraction?|`True`|
|computes π?<br>series or<br>continued<br>fraction?|`series`|
|equations<br>1656|equations<br>1656|
|extract|`term: (-1)**n * RisingFactorial(1/2, n) * RisingFactorial(1/4, n)`<br>`* RisingFactorial(3/4, n) / (RisingFactorial(1, n)**3) * (21460*n + 1123) / 882**(2*n)`<br>`start: 0`<br>`variable: n`|
|formulas<br>660|formulas<br>660|
|validate<br>via PSLQ|`1122.99727845641348 == 3528 /`π|
|formulas<br>385|formulas<br>385|
|to recurrence<br>|`(-14681/1695923712 - (1946417*n)/89035994880 - (1366829*n^2)/66776996160 - (46871*n^3)/5564749680`<br>`- n^4/777924)*f[n] + (-71386776899/8479618560 - (1836628904911*n)/89035994880`<br>`- (1222951171699*n^2)/66776996160 - (39244403773*n^3)/5564749680 - (777923*n^4)/777924)*f[1 + n]`<br>`+ (45166/5365 + (110669*n)/5365 + (196509*n^2)/10730 + (151343*n^3)/21460 + n^4)*f[2 + n] = 0`|
|formulas<br>385|formulas<br>385|


Figure 3: **Pipeline for automated harvesting of mathemat-**
**ical formulas (left), exemplified using one of the analyzed**
_π_ **formulas (right)** . (a) Equations are scraped from papers
on arXiv. (b) Regular expressions on the L [A] TEX strings retrieve series and continued fraction patterns that contain _π_
as the only irrational number (see Appendix I.3). (c) Zeroshot classification using OpenAI’s GPT-4o mini identifies
formulas calculating the constant _π_ . Then, OpenAI’s GPT-4o
identifies the formula type (series, continued fraction, or neither). (d) Extraction of the series’ summand or the continued
fraction’s partial numerator and partial denominator, using
GPT-4o. The formula is then converted to code. (e) Formulas
are computed and validated using the integer relation finder
algorithm PSLQ. (f) The formulas are converted to canonical
recurrences using RISC’s tool for fitting recurrences [33].


4


















to systematically convert to executable code using a predefined logic. LLMs help us overcome these
obstacles by processing text contextually and attending to relevant parts of the text, solving the
natural language processing task that may have required elaborate rules [14, 47]. Specifically, we
use OpenAI’s GPT-4o to translate relevant L [A] TEX into executable mathematical code [22, 43, 61] (see
Appendix I for the exact prompts used). To correct for (common) mistakes in the LLM-generated
formula code, we apply an LLM-code feedback loop for code validation: errors are sent back to the
LLM along with the faulty code to correct it, up to three times (see Appendix I.6.3).


We validate that each extracted formula computes the constant _π_ by running the formula code to get a
numerical approximation and then applying PSLQ, an integer relation algorithm [26]. Limit values
are not extracted directly from the L [A] TEX string for validation, since we found that GPT-4o got them
wrong in some cases (see Table 14). Instead, the PSLQ approach fixes these critical GPT mistakes
and reproduces the intended formulas. Out of the 660 candidates, 385 were validated as _π_ formulas
and passed on for canonicalization (details in Appendix I.5).


**3.3** **Clustering:** **using the canonical form**


The first unification step is converting each formula to its canonical form: the simplest linear
recurrence with polynomial coefficients (Appendix E.4.1). Automated algebraic capabilities are
unpredictable in solving such tasks. Thus, we use a computational method for converting the formulas
to polynomial recurrences: a Mathematica package by RISC [33] that fits polynomial-coefficient
linear recurrences to each sequence of rational numbers. The resulting recurrences are validated
numerically and passed to a Maple package to guarantee order minimality [57, 60], thus finding the
provably minimal polynomial recurrence. Out of the 385 validated formulas (Section 3.1), 380 are
found to have representations as order-2 recurrences, and 5 as order-3 recurrences, which can also be
addressed as we show in Appendix B.6 and Appendix C.3.


The same canonical form captures a wide range of formulas, continued fractions and infinite sums.
Thus, the conversion to canonical forms automatically unifies different formulas, yielding 149
different order-2 canonical forms and 4 order-3 canonical forms for _π_, 153 in total, from 385 formulas
(selected examples in Table 1).


Table 1: **Canonical** **form** **representation** . Converting formulas to their canonical forms shows
equivalence of different-looking expressions (e.g. 1,2), leaving the less-trivial connections for the
later steps of the algorithm. Additional details in Appendix C.4.


Formula Value arXiv source Canonical form (CF) CF value Initial conditions



1 - _∞n_ =0



_n_ !

- _n_
_i_ =1 [(2] _[i]_ [+1)]



_π_ 2 1806.03346 PCF(3 _n_ + 1 _, n_ (1 _−_ 2 _n_ )) _π_ 2


_π_ 2 2010.05610 PCF(3 _n_ + 1 _, n_ (1 _−_ 2 _n_ )) _π_ 2



2 - _∞n_ =1


3 - _∞n_ =0



2 _[n]_

_n_ (2 _nn_ [)]



(2 _−n_ 1)+1 _[n]_ _π_ 4 2404.15210 PCF(2 _,_ (2 _n −_ 1) [2] ) 1 + _π_ [4]



�0 1�
1 1

�0 1�
1 1

�0 1�
1 1

�0 1�
1 6



4 - _∞n_ =1



_n_ ( _n_ (+1)(2 _−_ 1) _[n]_ [+1] _n_ +1) _π −_ 3 2206.07174 PCF(6 _,_ (2 _n_ + 1) [2] ) _π−_ 1 3



5 - _∞n_ =1



4 _[n]_ (12 _n−_ 5)
(2 _n−_ 1)(42 _nn_ [)]



425) _nn_ [)] 3 _π_ 2+4 2204.08275 - _−_ 423 _ππ_ +4 _−_ 196



3 _π_ +4




- 0 70�

_−_ 1 15




- PCF(240 _n_ [3] + 164 _n_ [2] _−_ 54 _n −_ 29 _, −_ 9216 _n_ [6] + 12288 _n_ [5] + 11264 _n_ [4] _−_ 15520 _n_ [3] _−_ 764 _n_ [2] + 3802 _n −_ 714)



**3.4** **Clustering:** **using the dynamical metrics**


The clustering stage is a heuristic to guide which formulas should be attempted to be proven equal
using UMAPS. Formulas with the same metrics are likely to be related to the same constant [52].
The metrics also indicate a more intricate connection, enabling the unification of formulas in a
systematic way that proves an analytical transformation between them. Canonical-form formulas are
first compared to each other using the irrationality measure _δ_ (Fig. 4a), which is the most reliable
indicator for a potential equivalence. Every new formula is first evaluated relative to directions in the
CMF corresponding to recurrences with the same _δ_ . This search can be improved by using gradient
descent on the direction parameters, because _δ_ is found to be continuous [21].


5


We found that _δ_ is not sufficient to imply equivalence, and thus we complement it using the ratio of
convergence rates _rA_ : _rB_ . Canonical form A is _folded_ (Appendix E.5) by _rB_ and canonical form
B is folded by _rA_ (Fig. 4b), making them converge at the same rate. The next step is finding their
precise algebraic relation using UMAPS.


**3.5** **Unification:** **using the UMAPS algorithm for coboundary equivalence**


Our algorithm for unification via mapping
across symbolic structures (UMAPS) relies on
the established concept of coboundary equivalence (Appendix E.4), however, no specialized
coboundary solver existed prior to this work.


_A_ ( _n_ ) _, B_ ( _n_ ) _∈_ PGL _m_ (Q( _n_ )) are _coboundary_
_equivalent_ if there exist a matrix _U_ ( _n_ ) such that



_A_ ( _n_ ) _· U_ ( _n_ + 1) = _U_ ( _n_ ) _· B_ ( _n_ ) (7)

This definition carries to recur rences when
their companion matrices (Eq. (1)) are
coboundary equivalent (F ig. 5a,d) and then:



( [�] _[n]_




_[n]_

_i_ =1 _[A]_ [(] _[i]_ [))] _[ ·][ U]_ [(] _[n]_ [ + 1) =] _[ U]_ [(1)] _[ ·]_ [ (][�] _i_ _[n]_



Figure 4: **The matching algorithm:** **connecting**
**polynomial linear recurrences.** This algorithm is
demonstrated here for polynomial continued fractions (PCFs) but can be generalized to any linear
polynomial recurrence. (a) Compute the dynamical metrics [52] for the two PCFs (irrationality
measures _δA_, _δB_ and the convergence rates ratio
_rA/rB_ ). The _δ_ metrics are used to identify possible connections, as only if _δA_ = _δB_, the PCFs
can be related via coboundary (in practice, we test
for them to be within 0 _._ 06 of each other). (b) _Fold_
PCF _A_ by _rB_ and PCF _B_ by _rA_ (Appendix E.5).
**UMAPS (c)-(e):** (c) Solve for a general Möbius
transform (a 2 _×_ 2 matrix _U_ (1)) that once applied to
the limit of PCF _B_ equates it to the limit of PCF _A_ .
(d) Representing the PCFs in matrix form ( _A_ ( _n_ )
and _B_ ( _n_ )), propagate the coboundary matrix via
the relation _U_ ( _n_ + 1) = _A_ ( _n_ ) _[−]_ [1] _· U_ ( _n_ ) _· B_ ( _n_ ) up
to _U_ ( _N_ ) ( _N_ = 40 was sufficient for our runs, see
Appendix D). (e) Assume the general form of _U_ ( _n_ )
to have rational-function entries with polynomial
degree up to - _N_ 2 _−_ 1 - and solve for their coefficients

using normalized _U_ (1 _, . . ., N_ ). If such a solution
is found and validated, the PCFs are coboundaryrelated. See Appendix C for more details.



( [�] _i_ =1 _[A]_ [(] _[i]_ [))] _[ ·][ U]_ [(] _[n]_ [ + 1) =] _[ U]_ [(1)] _[ ·]_ [ (][�] _i_ =1 _[B]_ [(] _[i]_ [))][ .]

Since any matrix with rational function coefficients can be scaled to have polynomial coefficient s, we can write th at _A_ ( _n_ ) _, B_ ( _n_ ) _∈_
GL _m_ (Q[ _n_ ]) are _coboundary equivalent_ if there
exist a matrix _U_ ( _n_ ) _∈_ GL _m_ (Q[ _n_ ]) and polynomials _pA_ ( _n_ ) _, pB_ ( _n_ ) _∈_ Q[ _n_ ] such that


_pA_ ( _n_ ) _· A_ ( _n_ ) _· U_ ( _n_ + 1) = _pB_ ( _n_ ) _· U_ ( _n_ ) _· B_ ( _n_ ) (8)


Finding a coboundary between two polynomial
matrices is inherentl y a non-lin ear problem d ue
to the product of unknown polynomials _pA_
and _pB_ with unknown coboundary m atrix _U_ .
Moreover, the degree of each polynomial is not
known. De spite the non-linea rit y, we found a
coboundary sol ver algorithm for general order
_m_ (Appendix C .3).


UMAPS finds the solution without solving nonlinear equations, instead leveraging the recurrence limits to compute a sequence of empirical
coboundary matrices, whose elements are fitted
to rational functions [53]. The algorithm relies
on the following lemma:

**Lemma** **1.** _(A_ _necessary_ _condition_ _on_
_the_ _coboundary_ _equivalence_ _matrix.)_ _Let_
_LA_ = lim [(] _[a]_ [(] _[n]_ [)] _[, b]_ [(] _[n]_ [))] _[and][ L][B]_ =
_n→∞_ _[PCF]_

lim [(] _[c]_ [(] _[n]_ [)] _[, d]_ [(] _[n]_ [))] _[be]_ _[converging]_ _[PCFs]_
_n→∞_ _[PCF]_
_with_ _associated_ _companion_ _matrices_
_A_ ( _n_ ) _, B_ ( _n_ ) _∈_ PGL2 (Q( _n_ )) _._ _If_ _A_ ( _n_ ) _is_
_coboundary_ _to_ _B_ ( _n_ ) _,_ _then_ _LA_ _and_ _LB_ _are_ _re-_
_lated through a rational Möbius transformation._
_Moreover,_ _if_ _U_ ( _n_ ) _is_ _the_ _coboundary_ _matrix,_
_then_ _LA_ = _U_ (1)( _LB_ ) _(U_ (1) _applied to LB_
_as a Möbius transformation)._



A proof and generalization to higher-order recurrences (Lemma 4), as well as a proof of the uniqueness
of the coboundary matrix (Lemma 5), are detailed in Appendix F. These combine to show that UMAPS
is sufficient to solve for the coboundary matrix, as stated in Corollary 1 (proof in Appendix C.3).


6


Figure 5: **Coboundary equivalence** : the mathematical framework connecting different formulas
once cast into their canonical forms. (a) The coboundary condition _A_ ( _n_ ) _· U_ ( _n_ + 1) = _U_ ( _n_ ) _·_
_B_ ( _n_ ) recasts formulas as (b,c) parallel trajectories in a CMF. (d) Example of two coboundaryequivalent formulas, presenting their coboundary matrices and limits, which constitute proof of a
novel equivalence.


**Corollary 1.** _(Sufficiency of UMAPS.) If a coboundary matrix exists for two matrices and every_
_rational-function entry of the coboundary matrix has polynomials of degree at most d, then running_
_UMAPS with N_ _≥_ 2 _d_ + 1 _suffices to recover the coboundary matrix._


Fig. 4 summarizes the flow of matching two canonical form formulas. Using this method, we
find that formulas 1,2 and 5 from Table 1 are equivalent and that formulas 3,4 are also equivalent.
Refer to Appendix B.1 for descriptions of how the algorithm is applied to these formulas, and refer
to Appendix C for a listing of the algorithms involved. A study of the algorithms’ sensitivity to
hyperparameters is provided in Appendix D. The same procedure is applied to each canonical form
formula, measuring its _δ_ value and relying on its continuity as a function of direction in the CMF
to locate worthy directions that yield potential formula pairs for the coboundary algorithm. The
matching algorithm is then applied between formulas and representative recurrences from the CMF.
Finding a match between a formula and a CMF representative proves the formula is generated by the
CMF. The full list of results is provided in Appendix J. Selected results for _π_ are detailed in Section 5.


**4** **Benchmarking**


**4.1** **Comparison to other methods for symbolic unification**


Our work is the first to address the problem of symbolic unification at scale, thus there are no standard
benchmarks for performance comparison. Leading LLMs are generally unable to address the full
challenge. As an example, we compare our equivalence detection and proving capabilities to those
of LLMs: We tasked 2 leading LLMs—GPT-4o and Gemini 2.5 Pro Preview—with identifying and
proving 10 formula-pair equivalences proven by our algorithm (Table 2). The formulas are chosen
such that each pair has equal dynamical metrics ( _r, δ_ ) after folding, which is the simpler situation to
prove (parallel trajectories in the CMF). Even with these simpler tasks, the LLMs exhibit only limited
success. We did not find cases in which any LLM succeeded in finding relations between a pair of
formulas without equal dynamical metrics.


**4.2** **Comparison of LLM model performance**


We utilize LLMs for classification and extraction in two different ways. Table 3 compares the
performance of three choices for the extractor LLM, which we found to be the more sensitive choice,
as it is used for the more advanced LLM-code feedback loop. A ground truth is established by
merging the validated formulas (Section 3.2) found by the three compared LLMs.


7


Table 2: LLM performance when detecting and proving equivalence in a random set of 10 formula
pairs of equal dynamical parameters (Appendix H). All LLM proofs were validated manually.


LLM Successful detections Correct proofs


GPT-4o 1/10 2/10
Gemini 2.5 Pro Preview 8/10 5/10


Table 3: Performance of different extractor LLM choices in terms of successfully harvested formulas.
The LLM errors are split to “faulty code" for code that did not run, and “symbolic mistake" for
incorrect identification of some of the formula constituents like continued fraction polynomials. The
bold row marks the choice of LLMs used for all the rest of the results in this paper.


LLM classifier LLM extractor Successful extractions Faulty code Symbolic mistake


**GPT-4o mini** **GPT-4o** **289** ( **97** _._ **6** %) **2** ( **0** _._ **7** %) **5** ( **1** _._ **7** %)
GPT-4o mini Claude 3.7 Sonnet 266 (89 _._ 9%) 21 (7 _._ 1%) 9 (3 _._ 0%)
GPT-4o mini GPT-4o mini 206 (69 _._ 6%) 70 (23 _._ 6%) 20 (6 _._ 8%)


**5** **Results**


**5.1** **Example equivalences among famous formulas**


Our automated system proves previously unknown equivalences between formulas. Among the
formulas connected are famous examples, such as one of Ramanujan’s 1914 formulas, as well as
Lord Brouncker’s, Euler’s, and Gauss’s PCFs from the 17 [th], 18 [th], and 19 [th] centuries [23, 28, 42]. For
example, the following series found by Ramanujan in 1914 [48],




[(] [1] 2
_k_ _[∞]_ =0 [(] _[−]_ [1)] _[k]_




[3] _kk_ 4 _k_ _·_ (1123 + 21460 _k_ ) _·_ - 8821 �2 _k_ +1 (9)



4
_π_ [=][ �] _k_ _[∞]_




[1] 2 [)] _k_ [(] [1] 4 [)] _k_ [(] [3] 4 [)] _k_

(1) [3]



was proven equivalent (Appendix B.4) to a newer series from a paper published in 2020 [54]:



�1424799848 _k_ [2] + 1533506502 _k_ + 1086885699� (10)



341446000 _π_ = [�] _k_ _[∞]_ =0



(2 _kk_ [)] 2(42 _kk_ [)]

( _k_ +1)(2 _k−_ 1)(4 _k−_ 1)( _−_ 2 [10] 21 [4] ) _[k]_ _[·]_



(



2 _k_
_k_ [)]



This equivalence demonstrates how two previously distinct mathematical expressions, discovered
over a century apart, are now proven to be equivalent by an automated process.


Fig. 5d proves the equivalence of another pair of famous formulas: (1) PCF(2 _n_ +3 _, n_ ( _n_ +2)), one of
the first computer-discovered _π_ formulas from 2021 [46]. (2) PCF(2 _n_ + 1 _, n_ [2] ), published by Gauss
in 1813 [28] and provided at the time an especially efficient way to calculate digits of _π_ .


**5.2** **Formulas unified by a Conservative Matrix Field (CMF)**


The CMF of _π_, Eq. (6), captures most of the harvested formulas (Table 4), with selected examples
presented graphically in Fig. 6 along with their corresponding trajectories.


Table 4: **Summary of unification results**, among all validated formulas (left columns) and among
the canonical forms (right columns). Formulas are harvested from 140 arXiv papers (Table 15), of
which 137/140 (98%) have at least one formula proved connected by UMAPS and 70/140 (50%)
have a formula residing in the same CMF.


Found relation Same CMF Found relation (canonical) Same CMF (canonical)
360/385 (94%) 166/385 (43%) 136/153 (89%) 81/153 (53%)


The full list of canonical forms captured by the CMF appears in Table 16. Improvements in UMAPS
are likely to connect additional formulas (Table 17) to the same CMF.


**5.3** **Unification of formulas beyond** _π_


Going beyond _π_, we automatically identified equivalent formulas for _e_, _ζ_ (3), and Catalan’s constant—demonstrating the generality of the approach. Consider these two formulas for Apéry’s
constant, the Riemann zeta function value _ζ_ (3):


8


Figure 6: **Formula unification by a Conservative Matrix Field (CMF)** . Numerous _π_ formulas
harvested from the literature are automatically arranged as trajectories in a 3D CMF. These formulas
include famous ones by Gauss, Euler, and Lord Brouncker. The full list of unified formulas and
their canonical forms is available in Table 16. Each cluster (large dashed circles) denotes formulas
connected by coboundary, representing parallel trajectories or overlapping trajectories. The number
at each cluster center is the _δ_ of all formulas in that cluster. Arrows show trajectory directions. Note
that multiple formula clusters can have the same _δ_ value without being coboundary, showing that
sharing _δ_ is necessary but not sufficient for formulas being coboundary-related.



_∞_



_n_ =2



1
(11)
_n_ [3] ( _n_ [2] _−_ 1)



5
4 _[−]_ _[ζ]_ [(3) =]



_ζ_ (3) =



_∞_



_n_ =1



1
_n_ [3]



The second formula [36] has faster convergence compared to the classical definition of _ζ_ (3), though
both converge polynomially. Our automatic procedure proves their equivalence by the coboundary
transform and unifies them in the _ζ_ (3) CMF (detailed in Appendix B.2).


As another example, the following two PCFs for Catalan’s constant [13] are also proven equivalent
by UMAPS (Appendix B.5).



1 2 [2]
2 _−_ 2 _G_ [= 3 +]



2 [2]
1 +



1 [1] 1 [2]
2 _G −_ 1 [=] 2 [+]



(12)



4 [2]
3 +



1 1 _·_ 2
2 [+]



1 + [4][2]



1 2 [2]
2 [+]




_· · ·_



12 [+] [2] _· · ·_ _[ ·]_ [ 3]



A natural next step is to conduct exhaustive searches for other well-known constants, and fundamental
mathematical structures in fields such as physics and computer science. See Appendix B.3 for _e_
examples.


**5.4** **Formulas generated via a Conservative Matrix Field (CMF)**


A sample of 1693 distinct _π_ formulas was generated from the _π_ -CMF (per Appendix C.5). The
CMF permits a new method of comparing between formulas, using the _normalized convergence rate_,
defined _r/ℓ_ [1] ( _t_ ), where _r_ is the convergence rate from Eq. (4), _t_ is a trajectory and _ℓ_ [1] is the _ℓ_ [1] -norm.
57 of the formulas generated in our runs shared the best normalized _r_ of 1.76, such as the formula


9


10 _−_ 81
4 _−π_ [= 12 +]




_−_ 6500
238 +




_−_ 67473
968 +
... + _n_ [2] ( _−_ 64 _n_ [4] _−_ 96 _n_ [3] + 12 _n_ [2] + 52 _n_ + 15)



48 _n_ [3] + 108 _n_ [2] + 70 _n_ + 12 + [..] .



arising from trajectory ( _−_ 1 _, −_ 1 _,_ 0). By comparison, the best pre-existing formula unified by our CMF
has normalized convergence of 0.88 (the (1 _,_ 1 _,_ 2) direction, see Table 16). Details in Appendix G.6.


**6** **Discussion**


**6.1** **Limitations**


Currently, the harvesting step relies on the LLM’s ability to interpret and contextualize mathematical
L [A] TEX strings. This step likely introduces data loss and false negatives in formula classification.
Improvements in prompt engineering and in validation techniques will enhance the robustness of this
LLM use. As more advanced LLMs become available, this step will become increasingly reliable.


Formulas often include additional symbols other than summation indices, like variables defined in
the text surrounding the formula, which should be extracted and substituted into formula evaluation.
We made several such substitutions manually to test the rest of the pipeline for these special cases.
Future improvements of the unification pipeline can address this limitation by more advanced use of
LLMs and automated validation.


Most formulas analyzed in this work are series or continued fractions. However, UMAPS and all the
other steps in our harvesting and clustering processes are applicable more broadly (to any formula
that generates a sequence of rational approximations for a given constant, e.g., deeper recurrences).
Expanding the system to accommodate additional cases is a promising direction for future work.


The same unification pipeline shown here could apply to the vast family of constants derived from
D-finite functions by finding their corresponding CMFs [58].


**6.2** **Outlook**


Increasing the dimension and rank of the _π_ -CMF, along with further improvements to UMAPS [2], is
likely to yield a higher percentage of unified formulas in the near future. A planned future study will
employ the CMF to systematically search for fast-converging and irrationality-proving formulas.


Looking forward, the same approach of collection, analysis, and organization of mathematical
knowledge could help establish rigorous connections between different branches of mathematics.
The methodology presented in this work could help develop more general frameworks for identifying
connections between different scientific theories through their mathematical representations. As the
volume of information grows at an accelerating pace, finding automated ways to unify knowledge
will become increasingly essential, especially with the goal of providing more intuitive understanding
on complex concepts.


Pairing LLMs with pre-existing and novel tools for symbolic and numerical mathematics enabled the
automated discoveries in this paper. We believe this LLM–tool integration scheme will continue to
advance AI for mathematics and science in the coming years.


10


[19] Saber Elaydi. _An Introduction to Difference Equations_ . Undergraduate Texts in Mathematics.

Springer Nature, New York, third edition, 2006.


[20] Rotem Elimelech, Ofir David, Carlos De la Cruz Mengual, Rotem Kalisch, Wolfgang Berndt,

Michael Shalyt, Mark Silberstein, Yaron Hadad, and Ido Kaminer. Algorithm-assisted discovery
of an intrinsic order among mathematical constants. _arXiv preprint arXiv:2308.11829_, 2023.


[21] Rotem Elimelech, Ofir David, Carlos De la Cruz Mengual, Rotem Kalisch, Wolfgang Berndt,

Michael Shalyt, Mark Silberstein, Yaron Hadad, and Ido Kaminer. Algorithm-assisted discovery
of an intrinsic order among mathematical constants. _Proceedings of the National Academy of_
_Sciences (PNAS)_, 121(25):e2321440121, 2024.


[22] Hasan Ferit Eniser, Hanliang Zhang, Cristina David, Meng Wang, Maria Christakis, Brandon

Paulsen, Joey Dodds, and Daniel Kroening. Towards translating real-world code with llms: A
study of translating to rust. _arXiv preprint arXiv:2405.11514_, 2024.


[23] Leonhard Euler. Introductio in analysin infinitorum, volume 2. 1748.


[24] Siemion Fajtlowicz. On conjectures of graffiti. In J. Akiyama, Y. Egawa, and H. Enomoto,

editors, _Graph Theory and Applications_, volume 38 of _Annals of Discrete Mathematics_, pages
113–118. Elsevier, 1988.


[25] Alhussein Fawzi et al. Discovering faster matrix multiplication algorithms with reinforcement

learning. _Nature_, 610:47–53, 2022.


[26] Helaman R. P. Ferguson, David H. Bailey, and Paul Kutler. _A Polynomial Time, Numerically_

_Stable Integer Relation Algorithm_ . Ames Research Center, 1998.


[27] Luyu Gao et al. PAL: Program-aided language models. In _Proceedings of the 40th International_

_Conference on Machine Learning (ICML)_, volume 202 of _Proceedings of Machine Learning_
_Research_, pages 10764–10799. PMLR, 23–29 Jul 2023.


[28] Carl Friedrich Gauss. Werke, vol. 3, 1813.


[29] Zhibin Gou, Zhihong Shao, Yeyun Gong, Yelong Shen, Yujiu Yang, Minlie Huang, Nan Duan,

and Weizhu Chen. ToRA: A tool-integrated reasoning agent for mathematical problem solving.
In _International Conference on Learning Representations (ICLR)_, 2024.


[30] Jesus Guillera. History of the formulas and algorithms for pi. _arXiv preprint arXiv:0807.0872_,

2008.


[31] Milad Hashemi et al. Can transformers do enumerative geometry? In _International Conference_

_on Learning Representations (ICLR)_, 2025.


[32] Pierre-Alexandre Kamienny, Stéphane d’Ascoli, Guillaume Lample, and François Charton. End
to-end symbolic regression with transformers. In _Advances in Neural Information Processing_
_Systems (NeurIPS)_, volume 35, pages 10269–10281. Curran Associates, Inc., 2022.


[33] Manuel Kauers and Christoph Koutschan. Guessing with little data. In _Proceedings of the 2022_

_International Symposium on Symbolic and Algebraic Computation_, ISSAC ’22, page 83–90.
ACM, July 2022.


[34] Walter G. Kelley and Allan C. Peterson. _Difference equations: An introduction with applications_ .

Harcourt/Academic Press, San Diego, CA, second edition, 2000.


[35] John R. Koza. Genetic programming as a means for programming computers by natural

selection. _Statistics and Computing_, 4:87–112, 1994.


[36] Ernst Eduard Kummer. _Eine neue Methode, die numerischen Summen langsam convergirender_

_Reihen zu berechnen._ Walter de Gruyter, Berlin/New York, 1837.


[37] L. J. Lange. An elegant continued fraction for _π_ . _American_ _Mathematical_ _Monthly_, 106:

456–458, 1999.


12


