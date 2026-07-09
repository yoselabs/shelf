fromexperience. CareshouldbetakenwhenusingtheoutputsofGPT-4,particularlyincontexts
wherereliabilityisimportant.
GPT-4’scapabilitiesandlimitationscreatesignificantandnovelsafetychallenges,andwebelieve
carefulstudyofthesechallengesisanimportantareaofresearchgiventhepotentialsocietalimpact.
Thisreportincludesanextensivesystemcard(aftertheAppendix)describingsomeoftheriskswe
foreseearoundbias,disinformation,over-reliance,privacy,cybersecurity,proliferation,andmore.
ItalsodescribesinterventionswemadetomitigatepotentialharmsfromthedeploymentofGPT-4,
includingadversarialtestingwithdomainexperts,andamodel-assistedsafetypipeline.
2 ScopeandLimitationsofthisTechnicalReport
This report focuses on the capabilities, limitations, and safety properties of GPT-4. GPT-4 is a
Transformer-stylemodel[39]pre-trainedtopredictthenexttokeninadocument,usingbothpublicly
availabledata(suchasinternetdata)anddatalicensedfromthird-partyproviders. Themodelwas
then fine-tuned using Reinforcement Learning from Human Feedback (RLHF) [40]. Given both
thecompetitivelandscapeandthesafetyimplicationsoflarge-scalemodelslikeGPT-4,thisreport
containsnofurtherdetailsaboutthearchitecture(includingmodelsize),hardware,trainingcompute,
datasetconstruction,trainingmethod,orsimilar.
Wearecommittedtoindependentauditingofourtechnologies,andsharedsomeinitialstepsand
ideasinthisareainthesystemcardaccompanyingthisrelease.2 Weplantomakefurthertechnical
detailsavailabletoadditionalthirdpartieswhocanadviseusonhowtoweighthecompetitiveand
safetyconsiderationsaboveagainstthescientificvalueoffurthertransparency.
3 PredictableScaling
AlargefocusoftheGPT-4projectwasbuildingadeeplearningstackthatscalespredictably. The
primary reason is that for very large training runs like GPT-4, it is not feasible to do extensive
model-specifictuning. Toaddressthis,wedevelopedinfrastructureandoptimizationmethodsthat
haveverypredictablebehavioracrossmultiplescales. Theseimprovementsallowedustoreliably
predict some aspects of the performance of GPT-4 from smaller models trained using 1,000 –
×
10,000 lesscompute.
×
3.1 LossPrediction
Thefinallossofproperly-trainedlargelanguagemodelsisthoughttobewellapproximatedbypower
lawsintheamountofcomputeusedtotrainthemodel[41,42,2,14,15].
Toverifythescalabilityofouroptimizationinfrastructure,wepredictedGPT-4’sfinallossonour
internalcodebase(notpartofthetrainingset)byfittingascalinglawwithanirreduciblelossterm
(asinHenighanetal.[15]): L(C) = aCb+c,frommodelstrainedusingthesamemethodology
butusingatmost10,000xlesscomputethanGPT-4. Thispredictionwasmadeshortlyaftertherun
started,withoutuseofanypartialresults. ThefittedscalinglawpredictedGPT-4’sfinallosswith
highaccuracy(Figure1).
3.2 ScalingofCapabilitiesonHumanEval
Havingasenseofthecapabilitiesofamodelbeforetrainingcanimprovedecisionsaroundalignment,
safety,anddeployment. Inadditiontopredictingfinalloss,wedevelopedmethodologytopredict
moreinterpretablemetricsofcapability. OnesuchmetricispassrateontheHumanEvaldataset[43],
whichmeasurestheabilitytosynthesizePythonfunctionsofvaryingcomplexity. Wesuccessfully
predictedthepassrateonasubsetoftheHumanEvaldatasetbyextrapolatingfrommodelstrained
withatmost1,000 lesscompute(Figure2).
×
ForanindividualprobleminHumanEval,performancemayoccasionallyworsenwithscale. Despite
thesechallenges,wefindanapproximatepowerlawrelationship E [log(pass_rate(C))]=α C−k
P
− ∗
2Inadditiontotheaccompanyingsystemcard,OpenAIwillsoonpublishadditionalthoughtsonthesocial
andeconomicimplicationsofAIsystems,includingtheneedforeffectiveregulation.
2

OpenAIcodebasenextwordprediction
Bitsperword
6.0
Observed
Prediction
5.0 gpt-4
4.0
3.0
2.0
1.0
100p 10n 1µ 100µ 0.01 1
Compute
Figure1. PerformanceofGPT-4andsmallermodels. Themetricisfinallossonadatasetderived
fromourinternalcodebase.Thisisaconvenient,largedatasetofcodetokenswhichisnotcontainedin
thetrainingset.Wechosetolookatlossbecauseittendstobelessnoisythanothermeasuresacross
differentamountsoftrainingcompute. Apowerlawfittothesmallermodels(excludingGPT-4)is
shownasthedottedline;thisfitaccuratelypredictsGPT-4’sfinalloss.Thex-axisistrainingcompute
normalizedsothatGPT-4is1.
Capabilitypredictionon23codingproblems
–MeanLogPassRate
5
Observed
Prediction
4 gpt-4
3
2
1
0
1µ 10µ 100µ 0.001 0.01 0.1 1
Compute
Figure2.PerformanceofGPT-4andsmallermodels.Themetricismeanlogpassrateonasubsetof
theHumanEvaldataset.Apowerlawfittothesmallermodels(excludingGPT-4)isshownasthedotted
line;thisfitaccuratelypredictsGPT-4’sperformance.Thex-axisistrainingcomputenormalizedsothat
GPT-4is1.
3

wherekandαarepositiveconstants,andP isasubsetofproblemsinthedataset. Wehypothesize
thatthisrelationshipholdsforallproblemsinthisdataset. Inpractice,verylowpassratesaredifficult
orimpossibletoestimate,sowerestricttoproblemsP andmodelsM suchthatgivensomelarge
samplebudget,everyproblemissolvedatleastoncebyeverymodel.
WeregisteredpredictionsforGPT-4’sperformanceonHumanEvalbeforetrainingcompleted,using
onlyinformationavailablepriortotraining. Allbutthe15hardestHumanEvalproblemsweresplit
into6difficultybucketsbasedontheperformanceofsmallermodels. Theresultsonthe3rdeasiest
bucket are shown in Figure 2, showing that the resulting predictions were very accurate for this
subsetofHumanEvalproblemswherewecanaccuratelyestimatelog(pass_rate)forseveralsmaller
models. Predictionsontheotherfivebucketsperformedalmostaswell,themainexceptionbeing
GPT-4underperformingourpredictionsontheeasiestbucket.
Certaincapabilitiesremainhardtopredict. Forexample,theInverseScalingPrize[44]proposed
severaltasksforwhichmodelperformancedecreasesasafunctionofscale. Similarlytoarecent
resultbyWeietal.[45],wefindthatGPT-4reversesthistrend,asshownononeofthetaskscalled
HindsightNeglect[46]inFigure3.
Inversescalingprize,hindsightneglect
Accuracy
100
50
0
ada babbage curie gpt-3.5 gpt-4
Model
Figure3. PerformanceofGPT-4andsmallermodelsontheHindsightNeglecttask. Accuracyis
shownonthey-axis,higherisbetter.ada,babbage,andcurierefertomodelsavailableviatheOpenAI
API[47].
Webelievethataccuratelypredictingfuturecapabilitiesisimportantforsafety. Goingforwardwe
plantorefinethesemethodsandregisterperformancepredictionsacrossvariouscapabilitiesbefore
largemodeltrainingbegins,andwehopethisbecomesacommongoalinthefield.
4 Capabilities
WetestedGPT-4onadiversesetofbenchmarks,includingsimulatingexamsthatwereoriginally
designedforhumans.4 Wedidnospecifictrainingfortheseexams. Aminorityoftheproblemsinthe
examswereseenbythemodelduringtraining;foreachexamwerunavariantwiththesequestions
removedandreportthelowerscoreofthetwo. Webelievetheresultstoberepresentative. Forfurther
detailsoncontamination(methodologyandper-examstatistics),seeAppendixC.
Exams were sourced from publicly-available materials. Exam questions included both multiple-
choiceandfree-responsequestions;wedesignedseparatepromptsforeachformat,andimageswere
included in the input for questions which required it. The evaluation setup was designed based
on performance on a validation set of exams, and we report final results on held-out test exams.
Overallscoresweredeterminedbycombiningmultiple-choiceandfree-responsequestionscores
usingpubliclyavailablemethodologiesforeachexam. Weestimateandreportthepercentileeach
overallscorecorrespondsto. SeeAppendixAforfurtherdetailsontheexamevaluationmethodology.
3ForAMC10andAMC122022exams,thehumanpercentilesarenotyetpublished,sothereportednumbers
areextrapolatedandlikelyhavewideuncertainty.SeeAppendixA.5.
4Weusedthepost-trainedRLHFmodelfortheseexams.
4

|     | Exam | GPT-4 | GPT-4(novision) | GPT-3.5 |
| --- | ---- | ----- | --------------- | ------- |
UniformBarExam(MBE+MEE+MPT) 298/400(~90th) 298/400(~90th) 213/400(~10th)
|     | LSAT | 163(~88th) | 161(~83rd) | 149(~40th) |
| --- | ---- | ---------- | ---------- | ---------- |
SATEvidence-BasedReading&Writing 710/800(~93rd) 710/800(~93rd) 670/800(~87th)
|     | SATMath | 700/800(~89th) | 690/800(~89th) | 590/800(~70th) |
| --- | ------- | -------------- | -------------- | -------------- |
GraduateRecordExamination(GRE)Quantitative 163/170(~80th) 157/170(~62nd) 147/170(~25th)
GraduateRecordExamination(GRE)Verbal 169/170(~99th) 165/170(~96th) 154/170(~63rd)
GraduateRecordExamination(GRE)Writing 4/6(~54th) 4/6(~54th) 4/6(~54th)
USABOSemifinalExam2020 87/150(99th-100th) 87/150(99th-100th) 43/150(31st-33rd)
| USNCOLocalSectionExam2022              |                  | 36/60         | 38/60         | 24/60         |
| -------------------------------------- | ---------------- | ------------- | ------------- | ------------- |
| MedicalKnowledgeSelf-AssessmentProgram |                  | 75%           | 75%           | 53%           |
|                                        | CodeforcesRating | 392(below5th) | 392(below5th) | 260(below5th) |
|                                        | APArtHistory     | 5(86th-100th) | 5(86th-100th) | 5(86th-100th) |
|                                        | APBiology        | 5(85th-100th) | 5(85th-100th) | 4(62nd-85th)  |
|                                        | APCalculusBC     | 4(43rd-59th)  | 4(43rd-59th)  | 1(0th-7th)    |
|                                        | APChemistry      | 4(71st-88th)  | 4(71st-88th)  | 2(22nd-46th)  |
APEnglishLanguageandComposition 2(14th-44th) 2(14th-44th) 2(14th-44th)
APEnglishLiteratureandComposition 2(8th-22nd) 2(8th-22nd) 2(8th-22nd)
APEnvironmentalScience 5(91st-100th) 5(91st-100th) 5(91st-100th)
|                                        | APMacroeconomics | 5(84th-100th)     | 5(84th-100th)     | 2(33rd-48th)      |
| -------------------------------------- | ---------------- | ----------------- | ----------------- | ----------------- |
|                                        | APMicroeconomics | 5(82nd-100th)     | 4(60th-82nd)      | 4(60th-82nd)      |
|                                        | APPhysics2       | 4(66th-84th)      | 4(66th-84th)      | 3(30th-66th)      |
|                                        | APPsychology     | 5(83rd-100th)     | 5(83rd-100th)     | 5(83rd-100th)     |
|                                        | APStatistics     | 5(85th-100th)     | 5(85th-100th)     | 3(40th-63rd)      |
|                                        | APUSGovernment   | 5(88th-100th)     | 5(88th-100th)     | 4(77th-88th)      |
|                                        | APUSHistory      | 5(89th-100th)     | 4(74th-89th)      | 4(74th-89th)      |
|                                        | APWorldHistory   | 4(65th-87th)      | 4(65th-87th)      | 4(65th-87th)      |
|                                        | AMC103           | 30/150(6th-12th)  | 36/150(10th-19th) | 36/150(10th-19th) |
|                                        | AMC123           | 60/150(45th-66th) | 48/150(19th-40th) | 30/150(4th-8th)   |
| IntroductorySommelier(theoryknowledge) |                  | 92%               | 92%               | 80%               |
| CertifiedSommelier(theoryknowledge)    |                  | 86%               | 86%               | 58%               |
| AdvancedSommelier(theoryknowledge)     |                  | 77%               | 77%               | 46%               |
|                                        | Leetcode(easy)   | 31/41             | 31/41             | 12/41             |
|                                        | Leetcode(medium) | 21/80             | 21/80             | 8/80              |
|                                        | Leetcode(hard)   | 3/45              | 3/45              | 0/45              |
Table 1. GPT performance on academic and professional exams. In each case, we simulate the
conditionsandscoringoftherealexam. WereportGPT-4’sfinalscoregradedaccordingtoexam-
specificrubrics,aswellasthepercentileoftest-takersachievingGPT-4’sscore.
5

Examresults(orderedbyGPT-3.5performance)
gpt-4
gpt-4(novision)
Estimatedpercentilelowerbound(amongtesttakers)
gpt3.5
100%
80%
60%
40%
20%
0%
A A C A A U A A G A U A A L G A A G A S A A A A S A
P C a lc u lu s B M C C 1 2 o d e fo rc e s R a P tin E g n g lis h L ite M ra C tu 1 r 0 e n ifo rm B a r E x P a E m n g lis h L a n P g C u a h g e e m i s try R E Q u a n ti ta t P iv e P h y s ic s 2 S A B O S e m if P in a M l a 2 c 0 r 2 o 0 e c o n P o m S t ic a s tis ti c s S A T R E W ritin g P M ic ro e c o n o P m B ic io s lo g y R E V e rb a l P W o rld H is to A r T y M a th P U S H is to ry P U S G o v e rn P m P e s n y t c h o lo g y P A rt H is to ry A T E B R W P E n v iro n m e n ta l S c ie n
Exam c e
Figure 4. GPT performance on academic and professional exams. In each case, we simulate the
conditions and scoring of the real exam. Exams are ordered from low to high based on GPT-3.5
performance. GPT-4outperformsGPT-3.5onmostexamstested. Tobeconservativewereportthe
lowerendoftherangeofpercentiles,butthiscreatessomeartifactsontheAPexamswhichhavevery
widescoringbins.ForexamplealthoughGPT-4attainsthehighestpossiblescoreonAPBiology(5/5),
thisisonlyshownintheplotas85thpercentilebecause15percentoftest-takersachievethatscore.
GPT-4exhibitshuman-levelperformanceonthemajorityoftheseprofessionalandacademicexams.
Notably,itpassesasimulatedversionoftheUniformBarExaminationwithascoreinthetop10%of
testtakers(Table1,Figure4).
Themodel’scapabilitiesonexamsappeartostemprimarilyfromthepre-trainingprocessandarenot
significantlyaffectedbyRLHF.Onmultiplechoicequestions,boththebaseGPT-4modelandthe
RLHFmodelperformequallywellonaverageacrosstheexamswetested(seeAppendixB).
Wealsoevaluatedthepre-trainedbaseGPT-4modelontraditionalbenchmarksdesignedforevaluating
languagemodels. Foreachbenchmarkwereport,werancontaminationchecksfortestdataappearing
in the training set (see Appendix D for full details on per-benchmark contamination).5 We used
few-shotprompting[1]forallbenchmarkswhenevaluatingGPT-4.6
GPT-4considerablyoutperformsexistinglanguagemodels, aswellaspreviouslystate-of-the-art
(SOTA) systems which often have benchmark-specific crafting or additional training protocols
(Table2).
5DuringourcontaminationcheckwediscoveredthatportionsofBIG-bench[48]wereinadvertentlymixed
intothetrainingset,andweexcludeditfromourreportedresults.
6ForGSM-8K,weincludepartofthetrainingsetinGPT-4’spre-trainingmix(seeAppendixEfordetails).
Weusechain-of-thoughtprompting[11]whenevaluating.
6

|          | GPT-4     | GPT-3.5   | LMSOTA            | SOTA                      |
| -------- | --------- | --------- | ----------------- | ------------------------- |
|          | Evaluated | Evaluated | BestexternalLM    | Bestexternalmodel(incl.   |
|          | few-shot  | few-shot  | evaluatedfew-shot | benchmark-specifictuning) |
| MMLU[49] | 86.4%     | 70.0%     | 70.7%             | 75.2%                     |
Multiple-choicequestionsin57 5-shot 5-shot 5-shotU-PaLM[50] 5-shotFlan-PaLM[51]
subjects(professional&academic)
| HellaSwag[52] | 95.3% | 85.5% | 84.2% | 85.6 |
| ------------- | ----- | ----- | ----- | ---- |
Commonsensereasoningaround 10-shot 10-shot LLaMA(validation ALUM[53]
| everydayevents |       |       | set)[28] |       |
| -------------- | ----- | ----- | -------- | ----- |
| AI2Reasoning   | 96.3% | 85.2% | 85.2%    | 86.5% |
Challenge(ARC)[54]
Grade-schoolmultiplechoice 25-shot 25-shot 8-shotPaLM[55] ST-MOE[18]
sciencequestions.Challenge-set.
| WinoGrande[56] | 87.5% | 81.6% | 85.1% | 85.1% |
| -------------- | ----- | ----- | ----- | ----- |
Commonsensereasoningaround 5-shot 5-shot 5-shotPaLM[3] 5-shotPaLM[3]
pronounresolution
| HumanEval[43] | 67.0% | 48.1% | 26.2% | 65.8% |
| ------------- | ----- | ----- | ----- | ----- |
Pythoncodingtasks 0-shot 0-shot 0-shotPaLM[3] CodeT+GPT-3.5[57]
| DROP[58](F1score)     | 80.9   | 64.1   | 70.8          | 88.4      |
| --------------------- | ------ | ------ | ------------- | --------- |
| Readingcomprehension& | 3-shot | 3-shot | 1-shotPaLM[3] | QDGAT[59] |
arithmetic.
| GSM-8K[60] | 92.0%∗ | 57.1% | 58.8% | 87.3% |
| ---------- | ------ | ----- | ----- | ----- |
Grade-schoolmathematics 5-shot 5-shot 8-shotMinerva[61] Chinchilla+SFT+ORM-RL,
| questions | chain-of-thought |     |     | ORMreranking[62] |
| --------- | ---------------- | --- | --- | ---------------- |
Table2. PerformanceofGPT-4onacademicbenchmarks. WecompareGPT-4alongsidethebest
SOTA(withbenchmark-specifictraining)andthebestSOTAforanLMevaluatedfew-shot. GPT-4
outperformsexistingLMsonallbenchmarks,andbeatsSOTAwithbenchmark-specifictrainingonall
datasetsexceptDROP.ForeachtaskwereportGPT-4’sperformancealongwiththefew-shotmethod
usedtoevaluate. ForGSM-8K,weincludedpartofthetrainingsetintheGPT-4pre-trainingmix
(seeAppendixE),andweusechain-of-thoughtprompting[11]whenevaluating.Formultiple-choice
questions,wepresentallanswers(ABCD)tothemodelandaskittochoosetheletteroftheanswer,
similarlytohowahumanwouldsolvesuchaproblem.
ManyexistingMLbenchmarksarewritteninEnglish. TogainaninitialunderstandingofGPT-4’s
capabilitiesinotherlanguages,wetranslatedtheMMLUbenchmark[35,36]–asuiteofmultiple-
choice problems spanning 57 subjects – into a variety of languages using Azure Translate (see
AppendixFforexampletranslationsandprompts). WefindthatGPT-4outperformstheEnglish-
languageperformanceofGPT3.5andexistinglanguagemodels(Chinchilla[2]andPaLM[3])for
themajorityoflanguageswetested,includinglow-resourcelanguagessuchasLatvian,Welsh,and
Swahili(Figure5).
GPT-4 substantially improves over previous models in the ability to follow user intent [63]. On
a dataset of 5,214 prompts submitted to ChatGPT [64] and the OpenAI API [47], the responses
generatedbyGPT-4werepreferredovertheresponsesgeneratedbyGPT-3.5on70.2%ofprompts.7
We are open-sourcing OpenAI Evals8, our framework for creating and running benchmarks for
evaluatingmodelslikeGPT-4whileinspectingperformancesamplebysample. Evalsiscompatible
withexistingbenchmarks,andcanbeusedtotrackperformanceofmodelsindeployment. Weplan
7WecollecteduserpromptssenttousthroughChatGPTandtheOpenAIAPI,sampledoneresponsefrom
eachmodel,andsentthesepromptsandresponsestohumanlabelers. Thelabelerswereinstructedtojudge
whethertheresponseiswhattheuserwouldhavewantedgiventheprompt.Thelabelerswerenottoldwhich
responsewasgeneratedbywhichmodelandtheorderinwhichtheresponseswerepresentedwasrandomised.
Wefilteroutpromptscontaininganykindofdisallowedorsensitivecontent,includingpersonallyidentifiable
information(PII),sexualcontent,hate-speech,andsimilarcontent.Wealsofiltershort(e.g."Hello,ChatGPT!")
andoverly-commonprompts.
8https://github.com/openai/evals
7

|     |       |     |     |     |
| --- | ----- | --- | --- | --- |
GPT-43-shotaccuracyonMMLUacrosslanguages

| Randomguessing     | 25.0% |     |       |     |
| ------------------ | ----- | --- | ----- | --- |
| Chinchilla-English |       |     | 67.0% |     |
| PaLM-English       |       |     | 69.3% |     |
| GPT-3.5-English    |       |     | 70.1% |     |

| GPT-4English |     |     |     | 85.5% |
| ------------ | --- | --- | --- | ----- |
| Italian      |     |     |     | 84.1% |
| Afrikaans    |     |     |     | 84.1% |
| Spanish      |     |     |     | 84.0% |
| German       |     |     |     | 83.7% |
| French       |     |     |     | 83.6% |
| Indonesian   |     |     |     | 83.1% |
| Russian      |     |     |     | 82.7% |
| Polish       |     |     |     | 82.1% |
| Ukranian     |     |     |     | 81.9% |
Greek
81.4%
| Latvian   |     |     |       | 80.9%        |
| --------- | --- | --- | ----- | ------------ |
| Mandarin  |     |     |       | 80.1%        |
| Arabic    |     |     |       | 80.0%        |
| Turkish   |     |     |       | 80.0%        |
| Japanese  |     |     |       | 79.9%        |
| Swahili   |     |     |       | 78.5%        |
| Welsh     |     |     |       | 77.5%        |
| Korean    |     |     |       | 77.0%        |
| Icelandic |     |     |       | 76.5%        |
| Bengali   |     |     |       | 73.2%        |
| Urdu      |     |     |       | 72.6%        |
| Nepali    |     |     |       | 72.2% Random |
| Thai      |     |     | 71.8% | Chinchilla   |
| Punjabi   |     |     | 71.4% | PaLM         |
gpt-3.5
| Marathi |     |     | 66.7% |     |
| ------- | --- | --- | ----- | --- |
gpt-4
| Telugu |             |         | 62.0%   |         |
| ------ | ----------- | ------- | ------- | ------- |
| 0%     | 10% 20% 30% | 40% 50% | 60% 70% | 80% 90% |

Accuracy→
Figure5. PerformanceofGPT-4inavarietyoflanguagescomparedtopriormodelsinEnglishon
MMLU.GPT-4outperformstheEnglish-languageperformanceofexistinglanguagemodels[2,3]for
thevastmajorityoflanguagestested,includinglow-resourcelanguagessuchasLatvian,Welsh,and
Swahili.
toincreasethediversityofthesebenchmarksovertimetorepresentawidersetoffailuremodesand
ahardersetoftasks.
4.1 VisualInputs
GPT-4acceptspromptsconsistingofbothimagesandtext,which–paralleltothetext-onlysetting
–letstheuserspecifyanyvisionorlanguagetask. Specifically, themodelgeneratestextoutputs
giveninputsconsistingofarbitrarilyinterlacedtextandimages. Overarangeofdomains–including
documentswithtextandphotographs,diagrams,orscreenshots–GPT-4exhibitssimilarcapabilities
asitdoesontext-onlyinputs. AnexampleofGPT-4’svisualinputcanbefoundinTable3. The
standardtest-timetechniquesdevelopedforlanguagemodels(e.g. few-shotprompting,chain-of-
thought,etc)aresimilarlyeffectivewhenusingbothimagesandtext-seeAppendixGforexamples.
PreliminaryresultsonanarrowsetofacademicvisionbenchmarkscanbefoundintheGPT-4blog
post[65]. WeplantoreleasemoreinformationaboutGPT-4’svisualcapabilitiesinfollow-upwork.
8

ExampleofGPT-4visualinput:
| User Whatisfunnyaboutthisimage? |     | Describeitpanelbypanel. |     |     |     |     |     |
| ------------------------------- | --- | ----------------------- | --- | --- | --- | --- | --- |
Source:https://www.reddit.com/r/hmmm/comments/ubab5v/hmmm/
GPT-4 Theimageshowsapackagefora"LightningCable"adapterwiththreepanels.
| Panel 1: | A smartphone | with a VGA | connector | (a  | large, | blue, | 15-pin con- |
| -------- | ------------ | ---------- | --------- | --- | ------ | ----- | ----------- |
nectortypicallyusedforcomputermonitors)pluggedintoitschargingport.
| Panel 2: | The package | for the "Lightning |     | Cable" adapter |     | with | a picture of |
| -------- | ----------- | ------------------ | --- | -------------- | --- | ---- | ------------ |
aVGAconnectoronit.
| Panel 3: | A close-up | of the VGA | connector | with | a small | Lightning | con- |
| -------- | ---------- | ---------- | --------- | ---- | ------- | --------- | ---- |
nector(usedforchargingiPhonesandotherAppledevices)attheend.
| The humor | in this | image comes | from the | absurdity | of  | plugging | a large, |
| --------- | ------- | ----------- | -------- | --------- | --- | -------- | -------- |
outdatedVGAconnectorintoasmall,modernsmartphonechargingport.
Table3. ExamplepromptdemonstratingGPT-4’svisualinputcapability. Thepromptconsistsofa
questionaboutanimagewithmultiplepanelswhichGPT-4isabletoanswer.
9

5 Limitations
Despiteitscapabilities,GPT-4hassimilarlimitationsasearlierGPTmodels. Mostimportantly,itstill
isnotfullyreliable(it“hallucinates”factsandmakesreasoningerrors). Greatcareshouldbetaken
whenusinglanguagemodeloutputs,particularlyinhigh-stakescontexts,withtheexactprotocol
(suchashumanreview,groundingwithadditionalcontext,oravoidinghigh-stakesusesaltogether)
matchingtheneedsofspecificapplications. SeeourSystemCardfordetails.
GPT-4significantlyreduceshallucinationsrelativetopreviousGPT-3.5models(whichhavethem-
selvesbeenimprovingwithcontinuediteration). GPT-4scores19percentagepointshigherthanour
latestGPT-3.5onourinternal,adversarially-designedfactualityevaluations(Figure6).
Internalfactualevalbycategory
Accuracy
chatgpt-v2
chatgpt-v3
chatgpt-v4
80% gpt-4
60%
40%
20%
0%
learning technology writing history math sciencerecommendation code business
Category
Figure6.PerformanceofGPT-4onnineinternaladversarially-designedfactualityevaluations.Accuracy
isshownonthey-axis,higherisbetter.Anaccuracyof1.0meansthemodel’sanswersarejudgedto
beinagreementwithhumanidealresponsesforallquestionsintheeval.WecompareGPT-4tothree
earlierversionsofChatGPT[64]basedonGPT-3.5;GPT-4improvesonthelatestGPT-3.5modelby19
percentagepoints,withsignificantgainsacrossalltopics.
GPT-4makesprogressonpublicbenchmarkslikeTruthfulQA[66],whichteststhemodel’sabilityto
separatefactfromanadversarially-selectedsetofincorrectstatements(Figure7). Thesequestions
arepairedwithfactuallyincorrectanswersthatarestatisticallyappealing. TheGPT-4basemodelis
onlyslightlybetteratthistaskthanGPT-3.5;however,afterRLHFpost-trainingweobservelarge
improvementsoverGPT-3.5.9 Table4showsbothacorrectandanincorrectanswer. GPT-4resists
selectingcommonsayings(youcan’tteachanolddognewtricks),howeveritstillcanmisssubtle
details(ElvisPresleywasnotthesonofanactor,soPerkinsisthecorrectanswer).
GPT-4generallylacksknowledgeofeventsthathaveoccurredafterthevastmajorityofitspre-training
datacutsoffinSeptember202110,anddoesnotlearnfromitsexperience. Itcansometimesmake
simplereasoningerrorswhichdonotseemtocomportwithcompetenceacrosssomanydomains,or
beoverlygullibleinacceptingobviouslyfalsestatementsfromauser. Itcanfailathardproblemsthe
samewayhumansdo,suchasintroducingsecurityvulnerabilitiesintocodeitproduces.
GPT-4canalsobeconfidentlywronginitspredictions,nottakingcaretodouble-checkworkwhen
it’slikelytomakeamistake. Interestingly,thepre-trainedmodelishighlycalibrated(itspredicted
9WedidnotchecktheRLHFpost-trainingdataforcontaminationwithTruthfulQA
10Thepre-trainingandpost-trainingdatacontainasmallamountofmorerecentdata
10

[GPT-4answerscorrectly] [GPT-4answersincorrectly]
Canyouteachanolddognewtricks? Sonofanactor, thisAmericanguitarist
androcksingerreleasedmanysongsand
Yes,youcanteachanolddognewtricks choice albums and toured with his band. His
←
Youcan’tteachanolddognewtricks nameis"Elvis"what?
No,youcan’tteachanolddognewtricks
Perkins
Presley choice
←
ElvisPresley
HisnameisElvisPresley
Table4:ExampleofGPT-4givingcorrectandincorrectresponsesonTruthfulQA
Accuracyonadversarialquestions(TruthfulQAmc1)
Accuracy
70%
Anthropic-LM
gpt-3.5
gpt-4
60%
50%
40%
30%
20%
10%
0%
Anthropic-LMAnthropic-LMgpt-3.5-base gpt-3.5-base gpt-3.5-turbo gpt-4-base gpt-4-base gpt-4
0-shot RLHF 0-shot 5-shot RLHF 0-shot 5-shot RLHF
Model
Figure7.PerformanceofGPT-4onTruthfulQA.Accuracyisshownonthey-axis,higherisbetter.We
compareGPT-4underzero-shotprompting,few-shotprompting,andafterRLHFfine-tuning.GPT-4
significantlyoutperformsbothGPT-3.5andAnthropic-LMfromBaietal.[67].
confidence in an answer generally matches the probability of being correct). However, after the
post-trainingprocess,thecalibrationisreduced(Figure8).
GPT-4 has various biases in its outputs that we have taken efforts to correct but which will take
sometimetofullycharacterizeandmanage. WeaimtomakeGPT-4andothersystemswebuild
havereasonabledefaultbehaviorsthatreflectawideswathofusers’values, allowthosesystems
tobecustomizedwithinsomebroadbounds,andgetpublicinputonwhatthoseboundsshouldbe.
SeeOpenAI[68]formoredetails.
6 Risks&mitigations
We invested significant effort towards improving the safety and alignment of GPT-4. Here we
highlightouruseofdomainexpertsforadversarialtestingandred-teaming,andourmodel-assisted
safetypipeline[69]andtheimprovementinsafetymetricsoverpriormodels.
AdversarialTestingviaDomainExperts: GPT-4posessimilarrisksassmallerlanguagemodels,
suchasgeneratingharmfuladvice,buggycode,orinaccurateinformation. However,theadditional
capabilitiesofGPT-4leadtonewrisksurfaces. Tounderstandtheextentoftheserisks,weengaged
11