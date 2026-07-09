| From     | Euler |               | to  | AI: | Unifying         | Formulas |              |     | for |
| -------- | ----- | ------------- | --- | --- | ---------------- | -------- | ------------ | --- | --- |
|          |       | Mathematical  |     |     | Constants        |          |              |     |     |
| TomerRaz |       | MichaelShalyt |     |     | ElyasheevLeibtag |          | RotemKalisch |     |     |
IdoKaminer∗
|     | ShacharWeinbaum |     |     |     | YaronHadad |     |     |     |     |
| --- | --------------- | --- | --- | --- | ---------- | --- | --- | --- | --- |
Technion–IsraelInstituteofTechnology,
6202 raM 71  ]OH.htam[  4v33571.2052:viXra Haifa3200003,Israel
Abstract
Theconstantπhasfascinatedscholarsthroughoutthecenturies,inspiringnumerous
| formulasforitsevaluation,suchasinfinitesumsandcontinuedfractions. |     |     |     |     |     |     |     |     | Despite |
| ----------------------------------------------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | ------- |
theirindividualsignificance,manyoftheunderlyingconnectionsamongformulas
remainunknown,missingunifyingtheoriesthatcouldunveildeeperunderstanding.
| The absence | of  | a unifying | theory | reflects | a broader | challenge |     | across math | and |
| ----------- | --- | ---------- | ------ | -------- | --------- | --------- | --- | ----------- | --- |
science: knowledgeistypicallyaccumulatedthroughisolateddiscoveries,while
| deeperconnectionsoftenremainhidden.               |     |     |     |     | Inthiswork,wepresentanautomated |     |                   |     |     |
| ------------------------------------------------- | --- | --- | --- | --- | ------------------------------- | --- | ----------------- | --- | --- |
| frameworkfortheunificationofmathematicalformulas. |     |     |     |     |                                 |     | Oursystemcombines |     |     |
largelanguagemodels(LLMs)forsystematicformulaharvesting,anLLM-code
feedbackloopforvalidation,andanovelsymbolicalgorithmforclusteringand
| eventualunification. |         | Wedemonstratethismethodologyonthehallmarkcaseof |     |          |              |          |     |               |     |
| -------------------- | ------- | ----------------------------------------------- | --- | -------- | ------------ | -------- | --- | ------------- | --- |
| π, an ideal          | testing | ground                                          | for | symbolic | unification. | Applying |     | this approach | to  |
455,050arXivpapers,wevalidate385distinctformulasforπandproverelations
| between      | 360(94%)       | of               | them, | ofwhich     | 166 (43%)can |                  | be derived | from       | asingle |
| ------------ | -------------- | ---------------- | ----- | ----------- | ------------ | ---------------- | ---------- | ---------- | ------- |
| mathematical | object—linking |                  |       | canonical   | formulas     | by Euler,        | Gauss,     | Brouncker, |         |
| and newer    | ones           | from algorithmic |       | discoveries |              | by the Ramanujan |            | Machine.   | Our     |
methodgeneralizestootherconstants,includinge,ζ(3),andCatalan’sconstant,
demonstratingthepotentialofAI-assistedmathematicstouncoverhiddenstructures
andunifyknowledgeacrossdomains.
1 Introduction
TheearliestrigorousapproximationforπdatesbacktoArchimedesaround250BCE,whoestablished
thebounds 223 < π < 22 [16]. Modernπ approximationsemploymoresophisticatedformulas.
| 71  |     | 7   |     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Forexample,theChudnovskyalgorithm[15],derivedfromaformulabyRamanujan[48],remains
instrumentalforprecisionrecords.Similarly,theBBPformula[6]isnotableforenablingcomputation
ofspecificπdigitswithoutrequiringpriordigits. Suchbreakthroughsinspiredfundamentaladvances
incomputerscience,suchashigh-precisionarithmetic[7],evolutionaryoptimization[35],andelliptic
curve cryptography [39]. Recent efforts led to the development of computer algorithms capable
of generating numerous formula hypotheses and sometimes proofs for mathematical constants
[9,17,46].
∗Correspondingauthor:kaminer@technion.ac.il
Projectrepository:https://github.com/RamanujanMachine/euler2ai
39thConferenceonNeuralInformationProcessingSystems(NeurIPS2025).

2 Mathematicalbackground
2.1 Recurrencesasuniversalrepresentationsofformulasformathematicalconstants
A wide range of formulas—including infinite sums, products, and continued fractions—can be
convertedintorecurrences,providingacohesiveframeworkforunification. Afunctionu satisfiesa
n
recurrenceofordermifu =a u +a u +...+a u ,whichcanberepresented
|     | n   | 1,n n−1 |     | 2,n n−2 |     | m,n | n−m |     |
| --- | --- | ------- | --- | ------- | --- | --- | --- | --- |
viatheassociatedcompanionmatrix:
|     |     |     | 0  | 0 ... | 0   | a  |     |     |
| --- | --- | --- | --- | ----- | --- | --- | --- | --- |
m,n
|     |     |         |     | 1 0 ...     | 0 a |         |     |     |
| --- | --- | ------- | --- | ----------- | --- | ------- | --- | --- |
|     |     |         |    |             |     | m−1,n  |     |     |
|     |     | CM(n):= |    | 0 1 ...     | 0 a |        |     | (1) |
|     |     |         |    |             |     | m−2,n  |     |     |
|     |     |         |    | . . . . ... | . . | . .    |     |     |
|     |     |         |    | . .         | .   | .      |     |     |
|     |     |         |     | 0 0 ...     | 1   | a 1,n   |     |     |
Byincrementallymultiplyingthecompanionmatrixovernsteps,wegetthematrix:
|     |     |                  | p  |       | ... p       | p   |      |     |
| --- | --- | ---------------- | --- | ----- | ----------- | --- | ----- | --- |
|     |     |                  |     | 1,n−m | 1,n−1       |     | 1,n   |     |
|     |     |                  | p   |       | ... p       | p   |       |     |
|     |     |                  |    | 2,n−m | 2,n−1       |     | 2,n  |     |
|     |     | (cid:81)n CM(i)= |  p | 3,n−m | ... p 3,n−1 | p   | 3,n  | (2) |
|     |     | i=1              |    |       |             |     |      |     |
|     |     |                  |    | . .   | ...         | . . | . .  |     |
|     |     |                  |    | .     |             | .   | .    |     |
|     |     |                  | p   | m,n−m | ... p m,n−1 | p   | m,n   |     |
p ,...p aresolutionstotherecurrencefortheinitialconditionsp =δj. Othersolutionsfor
| 1,n m,n |     |     |     |     |     |     | i,j i |     |
| ------- | --- | --- | --- | --- | --- | --- | ----- | --- |
differentinitialconditionscanbewrittenaslinearcombinationsofthese.
RecurrencesevaluateadesiredconstantLeitherdirectlylim n→∞ u n =L(e.g.,forinfinitesums),or
pn
asratioslim =Lwithp andq beingtwosolutionsfortherecurrence(e.g.,forcontinued
| n→∞ qn |     | n   | n   |     |     |     |     |     |
| ------ | --- | --- | --- | --- | --- | --- | --- | --- |
fractions). Inthespecialcaseofasecond-orderrecurrence,u =a u +b u ,andanypairof
|     |     |     |     |     |     | n   | n n−1 n n−2 |     |
| --- | --- | --- | --- | --- | --- | --- | ----------- | --- |
solutionsisassociatedwithaformulaintheformofacontinuedfraction:
b
|     |     |     |     | 1   | pn  |     |     | (3) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
= qn
b 2
|     |     |     | a 1 + |     |     |     |     |     |
| --- | --- | --- | ----- | --- | --- | --- | --- | --- |
...+ b n
a
n
Whenthefunctionsa = a(n)andb = b(n)arepolynomials,theformulaaboveisknownasa
|     | n   |     | n   |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
PolynomialContinuedFraction(PCF),denotedbyPCF(a(n),b(n)). SeedetailsinAppendixE.
2.2 Thedynamicalmetricsdescribingeachformula
AformulaofamathematicalconstantLprovidesaconvergingsequenceofrationalnumbers pn
qn
(knownasaDiophantineapproximation). Theformulacanbecharacterizedbydynamicalmetrics
capturingpropertiessuchasitsconvergencerate. Arecentpaper[52]proposedusingsuchmetrics
forformuladiscoveryandclustering. Hereweusethemetricsofconvergencerateandirrationality
measure. Theconvergencerateisdefinedas:
|     |     |     |       |     | (cid:12)   | (cid:12)    |     |     |
| --- | --- | --- | ----- | --- | ---------- | ----------- | --- | --- |
|     |     |     |       | 1   | (cid:12)   | p n(cid:12) |     |     |
|     |     | r   | = lim | log | (cid:12)L− | (cid:12)    |     | (4) |
|     |     |     | n→∞n  |     |            | q           |     |     |
|     |     |     |       |     | (cid:12)   | n (cid:12)  |     |     |
When examining the connection of two candidate formulas, the ratio of their r values can hint
whetheroneisatransformationofasubsequenceoftheother(seeAppendixE.5foranexample).
| Theirrationalitymeasureof |     | pn isdefinedasthelimitδ |      |               | =lim     |             | δ ,where |     |
| ------------------------- | --- | ----------------------- | ---- | ------------- | -------- | ----------- | -------- | --- |
|                           |     | qn                      |      |               |          | n→∞         | n        |     |
|                           |     |                         |      |               | (cid:12) | (cid:12)    |          |     |
|                           |     |                         |      | log(cid:12)L− |          | pn(cid:12)  |          |     |
|                           |     |                         |      |               | (cid:12) | qn (cid:12) |          |     |
|                           |     | δ                       | =−1− |               |          |             |          | (5) |
|                           |     |                         | n    |               | log|q    | |           |          |     |
n
Wefoundthattwoformulassharingthesameδisthestrongestindicationofapossiblerelation,since
δisinvariantundermanytransformationsandchoiceofsubsequences. Below,ourUMAPSalgorithm
isusedtoderiveandprovearelationonceapairofformulassharethesamerandδ.
2.3 ConservativeMatrixFields(CMFs)
TheCMFisthemathematicalstructurethatgeneralizesformulasofaparticularconstant,originally
foundbygeneralizingPCFs[21],andlaterrealizedtobemoregeneral(AppendixG).Toexemplifythe
3

concept,wefocusontheCMFofπ. ThisCMFis3D,i.e.,consistingofthreematricesM ,M ,M
x y z
withrationalfunctionentriesinthevariables(x,y,z),satisfying:
|     |     | M   | (x,y,z)M | (x+1,y,z)=M   |     | (x,y,z)M   | (x,y+1,z)   |     |     |
| --- | --- | --- | -------- | ------------- | --- | ---------- | ----------- | --- | --- |
|     |     | x   |          | y             |     | y          | x           |     |     |
|     |     | M   | (x,y,z)M | (x+1,y,z)=M   |     | (x,y,z)M   | (x,y,z+1)   |     |     |
|     |     | x   |          | z             |     | z          | x           |     |     |
|     |     | M y | (x,y,z)M | z (x,y+1,z)=M |     | z (x,y,z)M | y (x,y,z+1) |     |     |
Thispropertydescribesthepath-independenceofthetransitionbetweentwopointsina3Dlattice
(lattice illustrated in Fig. 5b), in analogy to a conservative vector field. The CMF satisfies the
propertiesofadiscreteflatconnection[11]. Foranexplanationofhowformulasresideasdirections
withintheCMF,seeAppendixG.1. AnotablefeatureoftheCMFisthatpairsofformulasfoundto
beparalleltrajectorieswithdifferentinitialpointscorrespondtotwomatricesthatarecoboundary
equivalent.
ManyoftheknownπformulaswillbeshowntoresidewithinasingleCMF(detailsinAppendixG.2):
(cid:18) (cid:19) (cid:18)1 (cid:19) (cid:32)z(−x−y+z) zxy (cid:33)
|     | 1           | y   |     |     | x           |     |            |       |                   |
| --- | ----------- | --- | --- | --- | ----------- | --- | ---------- | ----- | ----------------- |
| M = |             |     |     | M = |             |     | M = (y−z)  | (x−z) | (y−z ) (x −z) (6) |
| x   | 1 2x+y−2z+2 |     |     | y   | 1 x+2y−2z+2 |     | z          | z     | − z 2             |
|     | x           | x   |     |     | y y         |     |            |       |                   |
|     |             |     |     |     |             |     | (y−z)(x−z) |       | (y−z)(x−z)        |
3 Methodologyforsymbolicunificationofformulas
| 3.1 Harvesting: |            | large-scaleretrievalofformulasfromtheliterature |              |       |                   |     |     |         |     |
| --------------- | ---------- | ----------------------------------------------- | ------------ | ----- | ----------------- | --- | --- | ------- | --- |
| The first       | challenge  | lies                                            | in the       | natu- |                   |     |     |         |     |
|                 |            |                                                 |              |       | Harvesting scheme |     |     | Example |     |
| ral language    | processing |                                                 | of formulas. |       |                   |     |     |         |     |
WeanalyzetheLATEXsourcecodeof
455,050arXivarticlesbycombining Guillera, Jesús. "Bi p l r a e t p e r r i a n l t     s a u r m X s i   v r : e 1 l 6 a 1 t 0 e . d 0   4 t 8 o 3   9 R   a ( m 2 a 0 n 1 u 6 j ) a . n-like series." arXiv
| regular expressions |     | and | LLMs, | ex- |         |          |     |     |     |
| ------------------- | --- | --- | ----- | --- | ------- | -------- | --- | --- | --- |
|                     |     |     |       |     | 455,050 | articles |     |     |     |
tractingallmathematicalexpressions,
| resultingin278,242,506strings.    |     |     |     | Fil- | scraping    |           |     |     |     |
| --------------------------------- | --- | --- | --- | ---- | ----------- | --------- | --- | --- | --- |
| teringforexpressionscontainingthe |     |     |     |      | 278,242,506 | equations |     |     |     |
πsymbolretrieves121,662π-related retrieval "\sum_{n = 0}^{\infty} (-1)^n \frac{(\frac12)_n (\frac14)_n
(\frac34)_n}{(1)_n^3} \frac{21460n + 1123}{882^{2n}} = \frac{3528}{\pi}."
| equations. | Thewidespreaduseofthe |     |     |     |         |           |     |     |     |
| ---------- | --------------------- | --- | --- | --- | ------- | --------- | --- | --- | --- |
|            |                       |     |     |     | 121,662 | equations |     |     |     |
symbolπinscientificliteraturemeans
| thatmostoccurrencesareunrelatedto |     |     |     |     | computes π? |     |     | True |     |
| --------------------------------- | --- | --- | --- | --- | ----------- | --- | --- | ---- | --- |
series or
| calculatingtheconstantitself. |     |     |     | Toad- |     |     |     |     |     |
| ----------------------------- | --- | --- | --- | ----- | --- | --- | --- | --- | --- |
continued
| dress this, | and keeping |      | in mind     | that | fraction? |           |     | series |     |
| ----------- | ----------- | ---- | ----------- | ---- | --------- | --------- | --- | ------ | --- |
| there is    | a priori    | very | little data | on   |           |           |     |        |     |
|             |             |      |             |      | 1656      | equations |     |        |     |
whatsuccessfulformulas’LATEXlooks
* RisingFactorial(3/4, n) / (RisingFactorial(1, n)**3) * (21460*n + 1123) / 882**(2*n) term: (-1)**n * RisingFactorial(1/2, n) * RisingFactorial(1/4, n)
| like, each | potential | formula |     | is clas- | extract |     |     | start: 0 |     |
| ---------- | --------- | ------- | --- | -------- | ------- | --- | --- | -------- | --- |
variable: n
| sified as                        | computing | π   | or not, | using |          |          |     |                                 |     |
| -------------------------------- | --------- | --- | ------- | ----- | -------- | -------- | --- | ------------------------------- | --- |
|                                  |           |     |         |       | 660      | formulas |     |                                 |     |
| GPT-4omini[41](chosenforitscost- |           |     |         |       | validate |          |     |                                 |     |
|                                  |           |     |         |       | via PSLQ |          |     | 1122.99727845641348 == 3528 / π |     |
effectiveness),reducingthenumberof
| candidatesto3367. |     | Next,GPT-4ocat- |     |     | 385 | formulas |     |     |     |
| ----------------- | --- | --------------- | --- | --- | --- | -------- | --- | --- | --- |
egorizesformulasbytype:series,con- to recurrence (-14681/1695923712 - (1946417*n)/89035994880 - (1366829*n^2)/66776996160 - (46871*n^3)/5564749680  - n^4/777924)*f[n] + (-71386776899/8479618560 - (1836628904911*n)/89035994880
- (1222951171699*n^2)/66776996160 - (39244403773*n^3)/5564749680 - (777923*n^4)/777924)*f[1 + n]
tinuedfraction,orneither—resulting + (45166/5365 + (110669*n)/5365 + (196509*n^2)/10730 + (151343*n^3)/21460 + n^4)*f[2 + n] = 0
|     |     |     |     |     | 385 | formulas |     |     |     |
| --- | --- | --- | --- | --- | --- | -------- | --- | --- | --- |
in1656formulacandidates. Figure3: Pipelineforautomatedharvestingofmathemat-
icalformulas(left),exemplifiedusingoneoftheanalyzed
3.2 Harvesting:
|     |     |     |     |     | πformulas(right). |     | (a)Equationsarescrapedfrompapers |     |     |
| --- | --- | --- | --- | --- | ----------------- | --- | -------------------------------- | --- | --- |
extractionandvalidation on arXiv. (b) Regular expressions on the LATEX strings re-
The extraction and validation stages trieveseriesandcontinuedfractionpatternsthatcontainπ
relyonanLLM-codefeedbackloop astheonlyirrationalnumber(seeAppendixI.3). (c)Zero-
that feeds a PSLQ algorithm. Each shot classification using OpenAI’s GPT-4o mini identifies
equation, represented as a LATEX formulascalculatingtheconstantπ.Then,OpenAI’sGPT-4o
string, must then be parsed into a identifiestheformulatype(series,continuedfraction,ornei-
ComputerAlgebraSystem(CAS)for ther). (d)Extractionoftheseries’summandorthecontinued
further manipulations (in our case, fraction’spartialnumeratorandpartialdenominator,using
SymPy[38]). Automaticallyextract- GPT-4o.Theformulaisthenconvertedtocode.(e)Formulas
ingalgebraicformsfromLATEXstrings arecomputedandvalidatedusingtheintegerrelationfinder
isespeciallycomplicatedduetovar- algorithmPSLQ.(f)Theformulasareconvertedtocanonical
iedLATEXpatterns,whicharedifficult recurrencesusingRISC’stoolforfittingrecurrences[33].
4

tosystematicallyconverttoexecutablecodeusingapredefinedlogic. LLMshelpusovercomethese
obstacles by processing text contextually and attending to relevant parts of the text, solving the
naturallanguageprocessingtaskthatmayhaverequiredelaboraterules[14,47]. Specifically,we
useOpenAI’sGPT-4ototranslaterelevantLATEXintoexecutablemathematicalcode[22,43,61](see
AppendixIfortheexactpromptsused). Tocorrectfor(common)mistakesintheLLM-generated
formulacode,weapplyanLLM-codefeedbackloopforcodevalidation: errorsaresentbacktothe
LLMalongwiththefaultycodetocorrectit,uptothreetimes(seeAppendixI.6.3).
Wevalidatethateachextractedformulacomputestheconstantπbyrunningtheformulacodetogeta
numericalapproximationandthenapplyingPSLQ,anintegerrelationalgorithm[26]. Limitvalues
arenotextracteddirectlyfromtheLATEXstringforvalidation,sincewefoundthatGPT-4ogotthem
wronginsomecases(seeTable14). Instead,thePSLQapproachfixesthesecriticalGPTmistakes
andreproducestheintendedformulas. Outofthe660candidates,385werevalidatedasπformulas
andpassedonforcanonicalization(detailsinAppendixI.5).
| 3.3 Clustering: | usingthecanonicalform |     |     |     |     |     |
| --------------- | --------------------- | --- | --- | --- | --- | --- |
The first unification step is converting each formula to its canonical form: the simplest linear
recurrence with polynomial coefficients (Appendix E.4.1). Automated algebraic capabilities are
unpredictableinsolvingsuchtasks.Thus,weuseacomputationalmethodforconvertingtheformulas
topolynomialrecurrences: aMathematicapackagebyRISC[33]thatfitspolynomial-coefficient
linearrecurrencesto eachsequenceofrational numbers. Theresultingrecurrencesare validated
numericallyandpassedtoaMaplepackagetoguaranteeorderminimality[57,60],thusfindingthe
provablyminimalpolynomialrecurrence. Outofthe385validatedformulas(Section3.1),380are
foundtohaverepresentationsasorder-2recurrences,and5asorder-3recurrences,whichcanalsobe
addressedasweshowinAppendixB.6andAppendixC.3.
Thesamecanonicalformcapturesawiderangeofformulas,continuedfractionsandinfinitesums.
Thus, the conversion to canonical forms automatically unifies different formulas, yielding 149
differentorder-2canonicalformsand4order-3canonicalformsforπ,153intotal,from385formulas
(selectedexamplesinTable1).
Table 1: Canonical form representation. Converting formulas to their canonical forms shows
equivalenceofdifferent-lookingexpressions(e.g. 1,2),leavingtheless-trivialconnectionsforthe
| laterstepsofthealgorithm. |     | AdditionaldetailsinAppendixC.4. |     |     |     |     |
| ------------------------- | --- | ------------------------------- | --- | --- | --- | --- |
Formula Value arXivsource Canonicalform(CF) CFvalue Initialconditions
(cid:20) (cid:21)
0 1
| 1   | (cid:80)∞ n !        | π 1806.03346 | PCF(3n+1,n(1−2n)) |     | 2   |     |
| --- | -------------------- | ------------ | ----------------- | --- | --- | --- |
|     | n=0(cid:81)n (2 i+1) | 2            |                   |     | π   | 1 1 |
i=1
(cid:20) 0 1 (cid:21)
| 2   | (cid:80)∞ 2n | π 2010.05610 | PCF(3n+1,n(1−2n)) |     | 2   |     |
| --- | ------------ | ------------ | ----------------- | --- | --- | --- |
|     | n=1n(2n)     | 2            |                   |     | π   | 1 1 |
n
(cid:20) 0 1 (cid:21)
|     | (cid:80)∞ (−1)n | π            | PCF(2,(2n−1)2) |     | 1+ 4 |     |
| --- | --------------- | ------------ | -------------- | --- | ---- | --- |
| 3   | n=0 2n+1        | 4 2404.15210 |                |     | π    | 1 1 |
(cid:20) (cid:21)
| (cid:80)∞ | (−1)n+1         |                | PCF(6,(2n+1)2) |     | 1   | 0 1 |
| --------- | --------------- | -------------- | -------------- | --- | --- | --- |
| 4         |                 | π−3 2206.07174 |                |     |     |     |
|           | n=1n(n+1)(2n+1) |                |                |     | π−3 | 1 6 |
(cid:20) (cid:21)
|     | (cid:80)∞ 4n(12n−5) | 3π+4       |     |     | −42π−196 | 0 70  |
| --- | ------------------- | ---------- | --- | --- | -------- | ----- |
| 5   |                     | 2204.08275 |     | *   |          |       |
|     | n=1(2n−1)(4n)       | 2          |     |     | 3π+4     | −1 15 |
2n
*PCF(240n3+164n2−54n−29,−9216n6+12288n5+11264n4−15520n3−764n2+3802n−714)
| 3.4 Clustering: | usingthedynamicalmetrics |     |     |     |     |     |
| --------------- | ------------------------ | --- | --- | --- | --- | --- |
Theclusteringstageisaheuristictoguidewhichformulasshouldbeattemptedtobeprovenequal
usingUMAPS.Formulaswiththesamemetricsarelikelytoberelatedtothesameconstant[52].
The metrics also indicate a more intricate connection, enabling the unification of formulas in a
systematicwaythatprovesananalyticaltransformationbetweenthem. Canonical-formformulasare
firstcomparedtoeachotherusingtheirrationalitymeasureδ (Fig.4a),whichisthemostreliable
indicatorforapotentialequivalence. Everynewformulaisfirstevaluatedrelativetodirectionsinthe
CMFcorrespondingtorecurrenceswiththesameδ. Thissearchcanbeimprovedbyusinggradient
descentonthedirectionparameters,becauseδisfoundtobecontinuous[21].
5

Wefoundthatδisnotsufficienttoimplyequivalence,andthuswecomplementitusingtheratioof
convergenceratesr :r . CanonicalformAisfolded(AppendixE.5)byr andcanonicalform
|     |     | A   | B   |     |     |     |     |     | B   |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Bisfoldedbyr (Fig.4b),makingthemconvergeatthesamerate. Thenextstepisfindingtheir
A
precisealgebraicrelationusingUMAPS.
| 3.5 Unification: |     | usingtheUMAPSalgorithmforcoboundaryequivalence |     |     |     |           |     |             |     |             |     |
| ---------------- | --- | ---------------------------------------------- | --- | --- | --- | --------- | --- | ----------- | --- | ----------- | --- |
|                  |     |                                                |     |     | Our | algorithm | for | unification |     | via mapping |     |
acrosssymbolicstructures(UMAPS)relieson
theestablishedconceptofcoboundaryequiva-
lence(AppendixE.4),however,nospecialized
coboundarysolverexistedpriortothiswork.
|     |     |     |     |     | A(n),B(n) |     | ∈ PGL | (Q(n)) |     | are coboundary |     |
| --- | --- | --- | --- | --- | --------- | --- | ----- | ------ | --- | -------------- | --- |
m
equivalentifthereexistamatrixU(n)suchthat
|     |     |     |     |     |             | A(n)·U(n+1)=U(n)·B(n) |            |               |                |                  | (7)   |
| --- | --- | --- | --- | --- | ----------- | --------------------- | ---------- | ------------- | -------------- | ---------------- | ----- |
|     |     |     |     |     | This        | definition            | carries    |               | to recurrences |                  | when  |
|     |     |     |     |     | their       | companion             |            | matrices      |                | (Eq. (1))        | are   |
|     |     |     |     |     | coboundary  |                       | equivalent |               | (Fig.          | 5a,d) and        | then: |
|     |     |     |     |     | ( (cid:81)n | A(i))·U(n+1)=U(1)·(   |            |               |                | (cid:81)n B(i)). |       |
|     |     |     |     |     |             | i=1                   |            |               |                | i=1              |       |
|     |     |     |     |     | Since       | any                   | matrix     | with rational |                | function         | coef- |
|     |     |     |     |     | ficients    | can                   | be scaled  | to            | have           | polynomial       | co-   |
|     |     |     |     |     | efficients, |                       | we can     | write         | that           | A(n),B(n)        | ∈     |
(Q[n])arecoboundaryequivalentifthere
|     |     |     |     |     | GL  | m   |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
(Q[n])andpolyno-
existamatrixU(n)∈GL
m
|     |     |     |     |     | mialsp | (n),p | (n)∈Q[n]suchthat |     |     |     |     |
| --- | --- | --- | --- | --- | ------ | ----- | ---------------- | --- | --- | --- | --- |
|     |     |     |     |     |        | A     | B                |     |     |     |     |
(8)
|     |     |     |     |     | p   | A (n)·A(n)·U(n+1)=p |     |     | B (n)·U(n)·B(n) |     |     |
| --- | --- | --- | --- | --- | --- | ------------------- | --- | --- | --------------- | --- | --- |
Figure4: Thematchingalgorithm: connecting Findingacoboundarybetweentwopolynomial
polynomiallinearrecurrences. Thisalgorithmis matricesisinherentlyanon-linearproblemdue
demonstratedhereforpolynomialcontinuedfrac- to the product of unknown polynomials p
A
tions(PCFs)butcanbegeneralizedtoanylinear
|     |     |     |     |     | and | p B with | unknown | coboundary |     | matrix | U.  |
| --- | --- | --- | --- | --- | --- | -------- | ------- | ---------- | --- | ------ | --- |
polynomialrecurrence. (a)Computethedynam- Moreover,thedegreeofeachpolynomialisnot
ical metrics [52] for the two PCFs (irrationality known. Despite the non-linearity, we found a
measuresδ ,δ andtheconvergenceratesratio coboundarysolveralgorithmforgeneralorder
A B
| r /r ). | The | δ metrics | are used to identify | pos- | m(AppendixC.3). |     |     |     |     |     |     |
| ------- | --- | --------- | -------------------- | ---- | --------------- | --- | --- | --- | --- | --- | --- |
A B
| sibleconnections, |     | asonlyifδ | = δ , | thePCFs |     |     |     |     |     |     |     |
| ----------------- | --- | --------- | ----- | ------- | --- | --- | --- | --- | --- | --- | --- |
A B
canberelatedviacoboundary(inpractice,wetest UMAPSfindsthesolutionwithoutsolvingnon-
|                                    |     |     |     |         | linear | equations, | instead |     | leveraging | the | recur- |
| ---------------------------------- | --- | --- | --- | ------- | ------ | ---------- | ------- | --- | ---------- | --- | ------ |
| forthemtobewithin0.06ofeachother). |     |     |     | (b)Fold |        |            |         |     |            |     |        |
rencelimitstocomputeasequenceofempirical
| PCF           | by r | and PCF                   | by r (Appendix | E.5). |                                           |     |     |     |                    |     |     |
| ------------- | ---- | ------------------------- | -------------- | ----- | ----------------------------------------- | --- | --- | --- | ------------------ | --- | --- |
| A             | B    |                           | B A            |       | coboundarymatrices,whoseelementsarefitted |     |     |     |                    |     |     |
| UMAPS(c)-(e): |      | (c)SolveforageneralMöbius |                |       |                                           |     |     |     |                    |     |     |
|               |      |                           |                |       | torationalfunctions[53].                  |     |     |     | Thealgorithmrelies |     |     |
transform(a2×2matrixU(1))thatonceappliedto
onthefollowinglemma:
| thelimitofPCF |     | equatesittothelimitofPCF |     |     | .     |     |       |           |     |           |     |
| ------------- | --- | ------------------------ | --- | --- | ----- | --- | ----- | --------- | --- | --------- | --- |
|               |     | B                        |     |     | A     |     |       |           |     |           |     |
|               |     |                          |     |     | Lemma |     | 1. (A | necessary |     | condition | on  |
(d)RepresentingthePCFsinmatrixform(A(n)
andB(n)),propagatethecoboundarymatrixvia the coboundary equivalence matrix.) Let
therelationU(n+1)=A(n)−1·U(n)·B(n)up L = lim PCF (a(n),b(n)) andL =
|          |                                |     |     |     | A   | n→∞ |             |     |               |     | B    |
| -------- | ------------------------------ | --- | --- | --- | --- | --- | ----------- | --- | ------------- | --- | ---- |
| toU(N)(N | =40wassufficientforourruns,see |     |     |     |     |     |             |     |               |     |      |
|          |                                |     |     |     | lim | PCF | (c(n),d(n)) |     | be converging |     | PCFs |
AppendixD).(e)AssumethegeneralformofU(n)
n→∞
tohaverational-functionentrieswithpolynomial with associated companion matrices
|                            | (cid:4)N−1(cid:5) |                              |                 |     | A(n),B(n)  |     | ∈ PGL    |      | (Q(n)). | If A(n) | is      |
| -------------------------- | ----------------- | ---------------------------- | --------------- | --- | ---------- | --- | -------- | ---- | ------- | ------- | ------- |
| degreeupto                 |                   | andsolvefortheircoefficients |                 |     |            |     |          | 2    |         |         |         |
|                            |                   | 2                            |                 |     | coboundary |     | to B(n), | then | L       | and L   | are re- |
| usingnormalizedU(1,...,N). |                   |                              | Ifsuchasolution |     |            |     |          |      | A       | B       |         |
latedthrougharationalMöbiustransformation.
isfoundandvalidated,thePCFsarecoboundary-
related. SeeAppendixCformoredetails. Moreover, if U(n) is the coboundary matrix,
|     |     |     |     |     | then | L   | = U(1)(L | )   | (U(1)appliedtoL |     |     |
| --- | --- | --- | --- | --- | ---- | --- | -------- | --- | --------------- | --- | --- |
|     |     |     |     |     |      | A   |          | B   |                 |     | B   |
asaMöbiustransformation).
Aproofandgeneralizationtohigher-orderrecurrences(Lemma4),aswellasaproofoftheuniqueness
ofthecoboundarymatrix(Lemma5),aredetailedinAppendixF.ThesecombinetoshowthatUMAPS
issufficienttosolveforthecoboundarymatrix,asstatedinCorollary1(proofinAppendixC.3).
6

Figure5: Coboundaryequivalence: themathematicalframeworkconnectingdifferentformulas
once cast into their canonical forms. (a) The coboundary condition A(n)·U(n+1) = U(n)·
B(n) recasts formulas as (b,c) parallel trajectories in a CMF. (d) Example of two coboundary-
equivalentformulas,presentingtheircoboundarymatricesandlimits,whichconstituteproofofa
novelequivalence.
Corollary 1. (Sufficiency of UMAPS.) If a coboundary matrix exists for two matrices and every
rational-functionentryofthecoboundarymatrixhaspolynomialsofdegreeatmostd,thenrunning
UMAPSwithN ≥2d+1sufficestorecoverthecoboundarymatrix.
Fig. 4 summarizes the flow of matching two canonical form formulas. Using this method, we
findthatformulas1,2and5fromTable1areequivalentandthatformulas3,4arealsoequivalent.
RefertoAppendixB.1fordescriptionsofhowthealgorithmisappliedtotheseformulas,andrefer
to Appendix C for a listing of the algorithms involved. A study of the algorithms’ sensitivity to
hyperparametersisprovidedinAppendixD.Thesameprocedureisappliedtoeachcanonicalform
formula,measuringitsδ valueandrelyingonitscontinuityasafunctionofdirectionintheCMF
to locate worthy directions that yield potential formula pairs for the coboundary algorithm. The
matchingalgorithmisthenappliedbetweenformulasandrepresentativerecurrencesfromtheCMF.
FindingamatchbetweenaformulaandaCMFrepresentativeprovestheformulaisgeneratedbythe
CMF.ThefulllistofresultsisprovidedinAppendixJ.SelectedresultsforπaredetailedinSection5.
4 Benchmarking
4.1 Comparisontoothermethodsforsymbolicunification
Ourworkisthefirsttoaddresstheproblemofsymbolicunificationatscale,thustherearenostandard
benchmarksforperformancecomparison. LeadingLLMsaregenerallyunabletoaddressthefull
challenge. Asanexample,wecompareourequivalencedetectionandprovingcapabilitiestothose
ofLLMs: Wetasked2leadingLLMs—GPT-4oandGemini2.5ProPreview—withidentifyingand
proving10formula-pairequivalencesprovenbyouralgorithm(Table2). Theformulasarechosen
suchthateachpairhasequaldynamicalmetrics(r,δ)afterfolding,whichisthesimplersituationto
prove(paralleltrajectoriesintheCMF).Evenwiththesesimplertasks,theLLMsexhibitonlylimited
success. WedidnotfindcasesinwhichanyLLMsucceededinfindingrelationsbetweenapairof
formulaswithoutequaldynamicalmetrics.
4.2 ComparisonofLLMmodelperformance
We utilize LLMs for classification and extraction in two different ways. Table 3 compares the
performanceofthreechoicesfortheextractorLLM,whichwefoundtobethemoresensitivechoice,
as it is used for the more advanced LLM-code feedback loop. A ground truth is established by
mergingthevalidatedformulas(Section3.2)foundbythethreecomparedLLMs.
7

Table2: LLMperformancewhendetectingandprovingequivalenceinarandomsetof10formula
pairsofequaldynamicalparameters(AppendixH).AllLLMproofswerevalidatedmanually.
|     |     |                     | LLM    |     | Successfuldetections |      | Correctproofs |     |     |     |
| --- | --- | ------------------- | ------ | --- | -------------------- | ---- | ------------- | --- | --- | --- |
|     |     |                     | GPT-4o |     |                      | 1/10 | 2/10          |     |     |     |
|     |     | Gemini2.5ProPreview |        |     |                      | 8/10 | 5/10          |     |     |     |
Table3: PerformanceofdifferentextractorLLMchoicesintermsofsuccessfullyharvestedformulas.
The LLM errors are split to “faulty code" for code that did not run, and “symbolic mistake" for
incorrectidentificationofsomeoftheformulaconstituentslikecontinuedfractionpolynomials. The
boldrowmarksthechoiceofLLMsusedforalltherestoftheresultsinthispaper.
LLMclassifier LLMextractor Successfulextractions Faultycode Symbolicmistake
| GPT-4omini |     |                 | GPT-4o |     | 289(97.6%) |     | 2(0.7%)   |     | 5(1.7%)  |     |
| ---------- | --- | --------------- | ------ | --- | ---------- | --- | --------- | --- | -------- | --- |
| GPT-4omini |     | Claude3.7Sonnet |        |     | 266(89.9%) |     | 21(7.1%)  |     | 9(3.0%)  |     |
| GPT-4omini |     | GPT-4omini      |        |     | 206(69.6%) |     | 70(23.6%) |     | 20(6.8%) |     |
5 Results
5.1 Exampleequivalencesamongfamousformulas
Our automated system proves previously unknown equivalences between formulas. Among the
formulasconnectedarefamousexamples,suchasoneofRamanujan’s1914formulas,aswellas
LordBrouncker’s,Euler’s,andGauss’sPCFsfromthe17th,18th,and19thcenturies[23,28,42]. For
example,thefollowingseriesfoundbyRamanujanin1914[48],
|     |     |     | (cid:80)∞ | (1 ) | ( 1) ( | 3)                  | (cid:0) | (cid:1)2k+1 |     |     |
| --- | --- | --- | --------- | ---- | ------ | ------------------- | ------- | ----------- | --- | --- |
|     |     | 4   | = (−1)k   | 2    | k 4 k  | 4 k ·(1123+21460k)· | 1       |             |     | (9) |
|     |     | π   | k=0       |      | (1)3   |                     | 882     |             |     |     |
k
wasprovenequivalent(AppendixB.4)toanewerseriesfromapaperpublishedin2020[54]:
|           | (cid:80)∞ |                                 | (2 k)2(4 | k ) |     | (cid:0)                               |     |     |     | (cid:1) |
| --------- | --------- | ------------------------------- | -------- | --- | --- | ------------------------------------- | --- | --- | --- | ------- |
| 341446000 | =         |                                 | k        | 2 k |     | · 1424799848k2+1533506502k+1086885699 |     |     |     | (10)    |
| π         |           | k=0 (k+1)(2k−1)(4k−1)(−210214)k |          |     |     |                                       |     |     |     |         |
Thisequivalencedemonstrateshowtwopreviouslydistinctmathematicalexpressions,discovered
overacenturyapart,arenowproventobeequivalentbyanautomatedprocess.
Fig.5dprovestheequivalenceofanotherpairoffamousformulas:(1)PCF(2n+3,n(n+2)),oneof
thefirstcomputer-discoveredπformulasfrom2021[46]. (2)PCF(2n+1,n2),publishedbyGauss
in1813[28]andprovidedatthetimeanespeciallyefficientwaytocalculatedigitsofπ.
5.2 FormulasunifiedbyaConservativeMatrixField(CMF)
TheCMFofπ,Eq.(6),capturesmostoftheharvestedformulas(Table4),withselectedexamples
presentedgraphicallyinFig.6alongwiththeircorrespondingtrajectories.
Table4: Summaryofunificationresults,amongallvalidatedformulas(leftcolumns)andamong
thecanonicalforms(rightcolumns). Formulasareharvestedfrom140arXivpapers(Table15),of
which137/140(98%)haveatleastoneformulaprovedconnectedbyUMAPSand70/140(50%)
haveaformularesidinginthesameCMF.
Foundrelation SameCMF Foundrelation(canonical) SameCMF(canonical)
| 360/385(94%) |     | 166/385(43%) |     |     |     | 136/153(89%) |     | 81/153(53%) |     |     |
| ------------ | --- | ------------ | --- | --- | --- | ------------ | --- | ----------- | --- | --- |
ThefulllistofcanonicalformscapturedbytheCMFappearsinTable16. ImprovementsinUMAPS
arelikelytoconnectadditionalformulas(Table17)tothesameCMF.
5.3 Unificationofformulasbeyondπ
Going beyond π, we automatically identified equivalent formulas for e, ζ(3), and Catalan’s con-
stant—demonstrating the generality of the approach. Consider these two formulas for Apéry’s
constant,theRiemannzetafunctionvalueζ(3):
8

Figure6: FormulaunificationbyaConservativeMatrixField(CMF).Numerousπ formulas
harvestedfromtheliteratureareautomaticallyarrangedastrajectoriesina3DCMF.Theseformulas
includefamousonesby Gauss, Euler, and LordBrouncker. Thefull listofunified formulasand
theircanonicalformsisavailableinTable16. Eachcluster(largedashedcircles)denotesformulas
connectedbycoboundary,representingparalleltrajectoriesoroverlappingtrajectories. Thenumber
ateachclustercenteristheδofallformulasinthatcluster. Arrowsshowtrajectorydirections. Note
thatmultipleformulaclusterscanhavethesameδ
valuewithoutbeingcoboundary,showingthat
sharingδisnecessarybutnotsufficientforformulasbeingcoboundary-related.
| ∞          |        | ∞          |      |
| ---------- | ------ | ---------- | ---- |
| (cid:88) 1 | 5      | (cid:88) 1 | (11) |
| ζ(3)=      | −ζ(3)= |            |      |
| n3         | 4      | n3(n2−1)   |      |
| n=1        |        | n=2        |      |
Thesecondformula[36]hasfasterconvergencecomparedtotheclassicaldefinitionofζ(3),though
bothconvergepolynomially. Ourautomaticprocedureprovestheirequivalencebythecoboundary
transformandunifiesthemintheζ(3)CMF(detailedinAppendixB.2).
Asanotherexample,thefollowingtwoPCFsforCatalan’sconstant[13]arealsoprovenequivalent
byUMAPS(AppendixB.5).
22
| 1      | 1 1    | 12     | (12) |
| ------ | ------ | ------ | ---- |
| =3+ 22 | =      | +      |      |
| 2−2G   | 2G−1 2 | 1+ 1·2 |      |
1+ 42 2 22
1 +
3+ 2 2 · 3
42 1 +
1+ 2 · ··
···
Anaturalnextstepistoconductexhaustivesearchesforotherwell-knownconstants,andfundamental
mathematicalstructuresinfieldssuchasphysicsandcomputerscience. SeeAppendixB.3fore
examples.
5.4 FormulasgeneratedviaaConservativeMatrixField(CMF)
A sample of 1693 distinct π formulas was generated from the π-CMF (per Appendix C.5). The
CMFpermitsanewmethodofcomparingbetweenformulas,usingthenormalizedconvergencerate,
definedr/ℓ1(t),whereristheconvergenceratefromEq.(4),tisatrajectoryandℓ1istheℓ1-norm.
57oftheformulasgeneratedinourrunssharedthebestnormalizedrof1.76,suchastheformula
9

−81
10 =12+
4−π −6500
238+
−67473
968+
...+ n2(−64n4−96n3+12n2+52n+15)
48n3+108n2+70n+12+
...
arisingfromtrajectory(−1,−1,0).Bycomparison,thebestpre-existingformulaunifiedbyourCMF
hasnormalizedconvergenceof0.88(the(1,1,2)direction,seeTable16). DetailsinAppendixG.6.
6 Discussion
6.1 Limitations
Currently,theharvestingstepreliesontheLLM’sabilitytointerpretandcontextualizemathematical
LATEX strings. This step likely introduces data loss and false negatives in formula classification.
Improvementsinpromptengineeringandinvalidationtechniqueswillenhancetherobustnessofthis
LLMuse. AsmoreadvancedLLMsbecomeavailable,thisstepwillbecomeincreasinglyreliable.
Formulasoftenincludeadditionalsymbolsotherthansummationindices,likevariablesdefinedin
thetextsurroundingtheformula,whichshouldbeextractedandsubstitutedintoformulaevaluation.
Wemadeseveralsuchsubstitutionsmanuallytotesttherestofthepipelineforthesespecialcases.
Futureimprovementsoftheunificationpipelinecanaddressthislimitationbymoreadvanceduseof
LLMsandautomatedvalidation.
Mostformulasanalyzedinthisworkareseriesorcontinuedfractions. However,UMAPSandallthe
otherstepsinourharvestingandclusteringprocessesareapplicablemorebroadly(toanyformula
thatgeneratesasequenceofrationalapproximationsforagivenconstant,e.g.,deeperrecurrences).
Expandingthesystemtoaccommodateadditionalcasesisapromisingdirectionforfuturework.
Thesameunificationpipelineshownherecouldapplytothevastfamilyofconstantsderivedfrom
D-finitefunctionsbyfindingtheircorrespondingCMFs[58].
6.2 Outlook
Increasingthedimensionandrankoftheπ-CMF,alongwithfurtherimprovementstoUMAPS[2],is
likelytoyieldahigherpercentageofunifiedformulasinthenearfuture. Aplannedfuturestudywill
employtheCMFtosystematicallysearchforfast-convergingandirrationality-provingformulas.
Looking forward, the same approach of collection, analysis, and organization of mathematical
knowledgecouldhelpestablishrigorousconnectionsbetweendifferentbranchesofmathematics.
Themethodologypresentedinthisworkcouldhelpdevelopmoregeneralframeworksforidentifying
connectionsbetweendifferentscientifictheoriesthroughtheirmathematicalrepresentations. Asthe
volumeofinformationgrowsatanacceleratingpace,findingautomatedwaystounifyknowledge
willbecomeincreasinglyessential,especiallywiththegoalofprovidingmoreintuitiveunderstanding
oncomplexconcepts.
PairingLLMswithpre-existingandnoveltoolsforsymbolicandnumericalmathematicsenabledthe
automateddiscoveriesinthispaper. WebelievethisLLM–toolintegrationschemewillcontinueto
advanceAIformathematicsandscienceinthecomingyears.
10

[19] SaberElaydi. AnIntroductiontoDifferenceEquations. UndergraduateTextsinMathematics.
SpringerNature,NewYork,thirdedition,2006.
[20] RotemElimelech,OfirDavid,CarlosDelaCruzMengual,RotemKalisch,WolfgangBerndt,
MichaelShalyt,MarkSilberstein,YaronHadad,andIdoKaminer. Algorithm-assisteddiscovery
ofanintrinsicorderamongmathematicalconstants. arXivpreprintarXiv:2308.11829,2023.
[21] RotemElimelech,OfirDavid,CarlosDelaCruzMengual,RotemKalisch,WolfgangBerndt,
MichaelShalyt,MarkSilberstein,YaronHadad,andIdoKaminer. Algorithm-assisteddiscovery
ofanintrinsicorderamongmathematicalconstants. ProceedingsoftheNationalAcademyof
Sciences(PNAS),121(25):e2321440121,2024.
[22] HasanFeritEniser,HanliangZhang,CristinaDavid,MengWang,MariaChristakis,Brandon
Paulsen,JoeyDodds,andDanielKroening. Towardstranslatingreal-worldcodewithllms: A
studyoftranslatingtorust. arXivpreprintarXiv:2405.11514,2024.
[23] LeonhardEuler. Introductioinanalysininfinitorum,volume2. 1748.
[24] SiemionFajtlowicz. Onconjecturesofgraffiti. InJ.Akiyama, Y.Egawa, andH.Enomoto,
editors,GraphTheoryandApplications,volume38ofAnnalsofDiscreteMathematics,pages
113–118.Elsevier,1988.
[25] AlhusseinFawzietal. Discoveringfastermatrixmultiplicationalgorithmswithreinforcement
learning. Nature,610:47–53,2022.
[26] HelamanR.P.Ferguson,DavidH.Bailey,andPaulKutler. APolynomialTime,Numerically
StableIntegerRelationAlgorithm. AmesResearchCenter,1998.
[27] LuyuGaoetal. PAL:Program-aidedlanguagemodels. InProceedingsofthe40thInternational
ConferenceonMachineLearning(ICML),volume202ofProceedingsofMachineLearning
Research,pages10764–10799.PMLR,23–29Jul2023.
[28] CarlFriedrichGauss. Werke,vol.3,1813.
[29] ZhibinGou,ZhihongShao,YeyunGong,YelongShen,YujiuYang,MinlieHuang,NanDuan,
andWeizhuChen. ToRA:Atool-integratedreasoningagentformathematicalproblemsolving.
InInternationalConferenceonLearningRepresentations(ICLR),2024.
[30] JesusGuillera. Historyoftheformulasandalgorithmsforpi. arXivpreprintarXiv:0807.0872,
2008.
[31] MiladHashemietal. Cantransformersdoenumerativegeometry? InInternationalConference
onLearningRepresentations(ICLR),2025.
[32] Pierre-AlexandreKamienny,Stéphaned’Ascoli,GuillaumeLample,andFrançoisCharton.End-
to-endsymbolicregressionwithtransformers. InAdvancesinNeuralInformationProcessing
Systems(NeurIPS),volume35,pages10269–10281.CurranAssociates,Inc.,2022.
[33] ManuelKauersandChristophKoutschan. Guessingwithlittledata. InProceedingsofthe2022
InternationalSymposiumonSymbolicandAlgebraicComputation,ISSAC’22,page83–90.
ACM,July2022.
[34] WalterG.KelleyandAllanC.Peterson.Differenceequations:Anintroductionwithapplications.
Harcourt/AcademicPress,SanDiego,CA,secondedition,2000.
[35] John R. Koza. Genetic programming as a means for programming computers by natural
selection. StatisticsandComputing,4:87–112,1994.
[36] ErnstEduardKummer. EineneueMethode,dienumerischenSummenlangsamconvergirender
Reihenzuberechnen. WalterdeGruyter,Berlin/NewYork,1837.
[37] L. J. Lange. An elegant continued fraction for π. American Mathematical Monthly, 106:
456–458,1999.
12