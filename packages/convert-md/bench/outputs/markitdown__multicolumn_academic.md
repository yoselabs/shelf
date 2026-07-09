|     |     | Deep      |     | Residual |              | Learning | for Image   | Recognition |     |         |     |     |     |
| --- | --- | --------- | --- | -------- | ------------ | -------- | ----------- | ----------- | --- | ------- | --- | --- | --- |
|     |     | KaimingHe |     |          | XiangyuZhang |          | ShaoqingRen |             |     | JianSun |     |     |     |
MicrosoftResearch
|     |     |     |     | kahe,v-xiangz,v-shren,jiansun |     |     | @microsoft.com |     |     |     |     |     |     |
| --- | --- | --- | --- | ----------------------------- | --- | --- | -------------- | --- | --- | --- | --- | --- | --- |
|     |     |     |     | {                             |     |     | }              |     |     |     |     |     |     |
5102 ceD 01  ]VC.sc[  1v58330.2151:viXra
|     |     | Abstract |     |     |     |     | 20  |     |     |   20 |     |     |     |
| --- | --- | -------- | --- | --- | --- | --- | --- | --- | --- | ---- | --- | --- | --- |
)%( rorre gniniart
|        |        |          |          |           |     |           |     |     |     | )%( rorre tset |     |     | 56-layer |
| ------ | ------ | -------- | -------- | --------- | --- | --------- | --- | --- | --- | -------------- | --- | --- | -------- |
| Deeper | neural | networks | are more | difficult | to  | train. We |     |     |     |                |     |     |          |
20-layer
|                                                    |      |                   |     |        |      |            | 10  |     |          | 10  |     |     |     |
| -------------------------------------------------- | ---- | ----------------- | --- | ------ | ---- | ---------- | --- | --- | -------- | --- | --- | --- | --- |
| presentaresiduallearningframeworktoeasethetraining |      |                   |     |        |      |            |     |     | 56-layer |     |     |     |     |
| of networks                                        | that | are substantially |     | deeper | than | those used |     |     |          |     |     |     |     |
20-layer
| previously. | We explicitly | reformulate |     | the | layers | as learn- |         |     |       |      |     |     |     |
| ----------- | ------------- | ----------- | --- | --- | ------ | --------- | ------- | --- | ----- | ---- | --- | --- | --- |
|             |               |             |     |     |        |           | 0 0   1 | 2 3 | 4 5 6 | 00   | 1 2 | 3 4 | 5 6 |
ingresidualfunctionswithreferencetothelayerinputs,in- iter.  (1e4) iter. (1e4)
steadoflearningunreferencedfunctions. Weprovidecom- Figure1.Trainingerror(left)andtesterror(right)onCIFAR-10
prehensive empirical evidence showing that these residual with20-layerand56-layer“plain”networks. Thedeepernetwork
|     |     |     |     |     |     |     | hashighertrainingerror,andthustesterror. |     |     |     | Similarphenomena |     |     |
| --- | --- | --- | --- | --- | --- | --- | ---------------------------------------- | --- | --- | --- | ---------------- | --- | --- |
networksareeasiertooptimize,andcangainaccuracyfrom
considerablyincreaseddepth. OntheImageNetdatasetwe onImageNetispresentedinFig.4.
evaluateresidualnetswithadepthofupto152layers—8
×
deeperthanVGGnets[41]butstillhavinglowercomplex- greatlybenefitedfromverydeepmodels.
ity.Anensembleoftheseresidualnetsachieves3.57%error Drivenbythesignificanceofdepth,aquestionarises: Is
ontheImageNettestset.Thisresultwonthe1stplaceonthe learning better networks as easy as stacking more layers?
ILSVRC2015classificationtask. Wealsopresentanalysis An obstacle to answering this question was the notorious
|     |     |     |     |     |     |     | problem | of vanishing/exploding |     | gradients |     | [1, 9], | which |
| --- | --- | --- | --- | --- | --- | --- | ------- | ---------------------- | --- | --------- | --- | ------- | ----- |
onCIFAR-10with100and1000layers.
The depth of representations is of central importance hamper convergence from the beginning. This problem,
for many visual recognition tasks. Solely due to our ex- however,hasbeenlargelyaddressedbynormalizedinitial-
tremelydeeprepresentations,weobtaina28%relativeim- ization[23,9,37,13]andintermediatenormalizationlayers
provement on the COCO object detection dataset. Deep [16],whichenablenetworkswithtensoflayerstostartcon-
|     |     |     |     |     |     |     | verging | for stochastic | gradient | descent | (SGD) | with | back- |
| --- | --- | --- | --- | --- | --- | --- | ------- | -------------- | -------- | ------- | ----- | ---- | ----- |
residualnetsarefoundationsofoursubmissionstoILSVRC
| & COCO | 2015 competitions1, |     | where | we  | also won | the 1st | propagation[22]. |     |     |     |     |     |     |
| ------ | ------------------- | --- | ----- | --- | -------- | ------- | ---------------- | --- | --- | --- | --- | --- | --- |
placesonthetasksofImageNetdetection,ImageNetlocal-
|     |     |     |     |     |     |     | When | deeper networks |     | are able | to start | converging, | a   |
| --- | --- | --- | --- | --- | --- | --- | ---- | --------------- | --- | -------- | -------- | ----------- | --- |
ization,COCOdetection,andCOCOsegmentation. degradation problem has been exposed: with the network
|     |     |     |     |     |     |     | depth increasing, |     | accuracy | gets saturated | (which |     | might be |
| --- | --- | --- | --- | --- | --- | --- | ----------------- | --- | -------- | -------------- | ------ | --- | -------- |
1.Introduction unsurprising) and then degrades rapidly. Unexpectedly,
|      |               |        |          |     |          |          | such degradation |     | is not caused | by  | overfitting, | and | adding |
| ---- | ------------- | ------ | -------- | --- | -------- | -------- | ---------------- | --- | ------------- | --- | ------------ | --- | ------ |
| Deep | convolutional | neural | networks |     | [22, 21] | have led |                  |     |               |     |              |     |        |
morelayerstoasuitablydeepmodelleadstohighertrain-
to a series of breakthroughs for image classification [21, ingerror,asreportedin[11,42]andthoroughlyverifiedby
50, 40]. Deep networks naturally integrate low/mid/high- ourexperiments. Fig.1showsatypicalexample.
| level features | [50] | and classifiers |     | in an | end-to-end | multi- |     |     |     |     |     |     |     |
| -------------- | ---- | --------------- | --- | ----- | ---------- | ------ | --- | --- | --- | --- | --- | --- | --- |
Thedegradation(oftrainingaccuracy)indicatesthatnot
| layer fashion, | and | the “levels” | of              | features | can be | enriched |                                       |              |     |            |                |     |           |
| -------------- | --- | ------------ | --------------- | -------- | ------ | -------- | ------------------------------------- | ------------ | --- | ---------- | -------------- | --- | --------- |
|                |     |              |                 |          |        |          | allsystemsaresimilarlyeasytooptimize. |              |     |            | Letusconsidera |     |           |
| by the number  | of  | stacked      | layers (depth). |          | Recent | evidence |                                       |              |     |            |                |     |           |
|                |     |              |                 |          |        |          | shallower                             | architecture | and | its deeper | counterpart    |     | that adds |
[41,44]revealsthatnetworkdepthisofcrucialimportance, morelayersontoit. Thereexistsasolutionbyconstruction
| and the | leading results | [41, | 44, 13, | 16] on | the challenging |     |                   |     |                                   |     |     |     |     |
| ------- | --------------- | ---- | ------- | ------ | --------------- | --- | ----------------- | --- | --------------------------------- | --- | --- | --- | --- |
|         |                 |      |         |        |                 |     | tothedeepermodel: |     | theaddedlayersareidentitymapping, |     |     |     |     |
ImageNetdataset[36]allexploit“verydeep”[41]models,
|     |     |     |     |     |     |     | and the | other layers | are copied | from | the learned | shallower |     |
| --- | --- | --- | --- | --- | --- | --- | ------- | ------------ | ---------- | ---- | ----------- | --------- | --- |
withadepthofsixteen[41]tothirty[16]. Manyothernon- model. Theexistenceofthisconstructedsolutionindicates
| trivial visual | recognition | tasks | [8, | 12, 7, | 32, 27] | have also |     |     |     |     |     |     |     |
| -------------- | ----------- | ----- | --- | ------ | ------- | --------- | --- | --- | --- | --- | --- | --- | --- |
thatadeepermodelshouldproducenohighertrainingerror
|                                              |     |     |     |     |     |     | than its | shallower | counterpart. | But | experiments | show | that |
| -------------------------------------------- | --- | --- | --- | --- | --- | --- | -------- | --------- | ------------ | --- | ----------- | ---- | ---- |
| 1http://image-net.org/challenges/LSVRC/2015/ |     |     |     |     |     | and |          |           |              |     |             |      |      |
http://mscoco.org/dataset/#detections-challenge2015. ourcurrentsolversonhandareunabletofindsolutionsthat
1

|     |     |     |     |     |     |     |     | ImageNet | test | set, and | won | the 1st place | in  | the ILSVRC |
| --- | --- | --- | --- | --- | --- | --- | --- | -------- | ---- | -------- | --- | ------------- | --- | ---------- |
x
|     |     |     |     |     |     |     |     | 2015 classification |     | competition. |     | The | extremely | deep rep- |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------------- | --- | ------------ | --- | --- | --------- | --------- |
weight layer
resentationsalsohaveexcellentgeneralizationperformance
|     | (x) |     | relu |     |     |     |     |          |             |        |     |         |            |         |
| --- | --- | --- | ---- | --- | --- | --- | --- | -------- | ----------- | ------ | --- | ------- | ---------- | ------- |
|     |     |     |      |     | x   |     |     | on other | recognition | tasks, | and | lead us | to further | win the |
F
weight layer identity 1st places on: ImageNet detection, ImageNet localization,
|     |     |     |     |     |     |     |     | COCO detection, |     | and | COCO | segmentation |     | in ILSVRC & |
| --- | --- | --- | --- | --- | --- | --- | --- | --------------- | --- | --- | ---- | ------------ | --- | ----------- |
(x)(cid:1)+(cid:1)x
|     | F   |     | relu |     |     |     |     | COCO2015competitions. |     |     | Thisstrongevidenceshowsthat |     |     |     |
| --- | --- | --- | ---- | --- | --- | --- | --- | --------------------- | --- | --- | --------------------------- | --- | --- | --- |
Figure2.Residuallearning:abuildingblock. theresiduallearningprincipleisgeneric,andweexpectthat
itisapplicableinothervisionandnon-visionproblems.
arecomparablygoodorbetterthantheconstructedsolution
| (orunabletodosoinfeasibletime). |        |               |         |                 |            |         |     | 2.RelatedWork |                  |     |     |          |              |      |
| ------------------------------- | ------ | ------------- | ------- | --------------- | ---------- | ------- | --- | ------------- | ---------------- | --- | --- | -------- | ------------ | ---- |
| In this                         | paper, | we            | address | the degradation |            | problem | by  |               |                  |     |     |          |              |      |
|                                 |        |               |         |                 |            |         |     | Residual      | Representations. |     |     | In image | recognition, | VLAD |
| introducing                     | a      | deep residual |         | learning        | framework. |         | In- |               |                  |     |     |          |              |      |
stead of hoping each few stacked layers directly fit a [18]isarepresentationthatencodesbytheresidualvectors
|           |            |          |           |               |          |           |         | with respect | to   | a dictionary, |     | and Fisher | Vector  | [30] can be |
| --------- | ---------- | -------- | --------- | ------------- | -------- | --------- | ------- | ------------ | ---- | ------------- | --- | ---------- | ------- | ----------- |
| desired   | underlying | mapping, |           | we explicitly |          | let these | lay-    |              |      |               |     |            |         |             |
|           |            |          |           |               |          |           |         | formulated   | as a | probabilistic |     | version    | [18] of | VLAD. Both  |
| ers fit a | residual   | mapping. | Formally, |               | denoting | the       | desired |              |      |               |     |            |         |             |
underlyingmappingas (x), weletthestackednonlinear ofthemarepowerfulshallowrepresentationsforimagere-
H trieval and classification [4, 48]. For vector quantization,
| layersfitanothermappin |     |     | gof | (x):= | (x) | x. Theorig- |     |     |     |     |     |     |     |     |
| ---------------------- | --- | --- | --- | ----- | --- | ----------- | --- | --- | --- | --- | --- | --- | --- | --- |
|                        |     |     | F   |       | H   | −           |     |     |     |     |     |     |     |     |
inalmappingisrecastinto ( x)+x.W ehyp othesizethatit encoding residual vectors [17] is shown to be more effec-
|                         |     |     | F                           |     |     |     |     | tivethanencodingoriginalvectors. |     |     |     |     |     |     |
| ----------------------- | --- | --- | --------------------------- | --- | --- | --- | --- | -------------------------------- | --- | --- | --- | --- | --- | --- |
| iseasiertooptimizethere |     |     | sidualmappingthantooptimize |     |     |     |     |                                  |     |     |     |     |     |     |
the original, unreferenced mapping. To the extreme, if an In low-level vision and computer graphics, for solv-
identity mapping were optimal, it would be easier to push ing Partial Differential Equations (PDEs), the widely used
|     |     |     |     |     |     |     |     | Multigrid | method | [3] | reformulates | the | system | as subprob- |
| --- | --- | --- | --- | --- | --- | --- | --- | --------- | ------ | --- | ------------ | --- | ------ | ----------- |
theresidualtozerothantofitanidentitymappingbyastack
ofnonlinearlayers. lems at multiple scales, where each subproblem is respon-
siblefortheresidualsolutionbetweenacoarserandafiner
| Theformulationof |     |     | (x)+xcanberealizedbyfeedfor- |     |     |     |     |     |     |     |     |     |     |     |
| ---------------- | --- | --- | ---------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
F
wardneuralnetworkswith“shortcutconnections”(Fig.2). scale. AnalternativetoMultigridishierarchicalbasispre-
|              |             |           |             |          |             |          |        | conditioning[45,46],                 |     |     | whichreliesonvariablesthatrepre- |     |                |     |
| ------------ | ----------- | --------- | ----------- | -------- | ----------- | -------- | ------ | ------------------------------------ | --- | --- | -------------------------------- | --- | -------------- | --- |
| Shortcut     | connections |           | [2, 34, 49] | are      | those       | skipping | one or |                                      |     |     |                                  |     |                |     |
|              |             |           |             |          |             |          |        | sentresidualvectorsbetweentwoscales. |     |     |                                  |     | Ithasbeenshown |     |
| more layers. | In          | our case, | the         | shortcut | connections |          | simply |                                      |     |     |                                  |     |                |     |
perform identity mapping, and their outputs are added to [3,45,46]thatthesesolversconvergemuchfasterthanstan-
|             |     |             |        |       |     |          |        | dard solvers | that | are unaware |     | of the residual |     | nature of the |
| ----------- | --- | ----------- | ------ | ----- | --- | -------- | ------ | ------------ | ---- | ----------- | --- | --------------- | --- | ------------- |
| the outputs | of  | the stacked | layers | (Fig. | 2). | Identity | short- |              |      |             |     |                 |     |               |
solutions.Thesemethodssuggestthatagoodreformulation
| cut connections |     | add neither | extra | parameter |     | nor computa- |     |     |     |     |     |     |     |     |
| --------------- | --- | ----------- | ----- | --------- | --- | ------------ | --- | --- | --- | --- | --- | --- | --- | --- |
orpreconditioningcansimplifytheoptimization.
| tional complexity. |     | The | entire | network | can | still be | trained |     |     |     |     |     |     |     |
| ------------------ | --- | --- | ------ | ------- | --- | -------- | ------- | --- | --- | --- | --- | --- | --- | --- |
end-to-endbySGDwithbackpropagation,andcanbeeas-
|                 |     |       |        |           |        |       |       | Shortcut | Connections. |     | Practices | and | theories | that lead to |
| --------------- | --- | ----- | ------ | --------- | ------ | ----- | ----- | -------- | ------------ | --- | --------- | --- | -------- | ------------ |
| ily implemented |     | using | common | libraries | (e.g., | Caffe | [19]) |          |              |     |           |     |          |              |
shortcutconnections[2,34,49]havebeenstudiedforalong
withoutmodifyingthesolvers. time. Anearlypracticeoftrainingmulti-layerperceptrons
| We present |     | comprehensive |     | experiments |     | on ImageNet |     |     |     |     |     |     |     |     |
| ---------- | --- | ------------- | --- | ----------- | --- | ----------- | --- | --- | --- | --- | --- | --- | --- | --- |
(MLPs)istoaddalinearlayerconnectedfromthenetwork
[36] to show the degradation problem and evaluate our input to the output [34, 49]. In [44, 24], a few interme-
| method. | Weshowthat: |     | 1)Ourextremelydeepresidualnets |     |     |     |     |              |     |          |           |     |           |             |
| ------- | ----------- | --- | ------------------------------ | --- | --- | --- | --- | ------------ | --- | -------- | --------- | --- | --------- | ----------- |
|         |             |     |                                |     |     |     |     | diate layers | are | directly | connected | to  | auxiliary | classifiers |
are easy to optimize, but the counterpart “plain” nets (that for addressing vanishing/exploding gradients. The papers
simply stack layers) exhibit higher training error when the of[39,38,31,47]proposemethodsforcenteringlayerre-
depthincreases;2)Ourdeepresidualnetscaneasilyenjoy
sponses,gradients,andpropagatederrors,implementedby
accuracygainsfromgreatlyincreaseddepth,producingre- shortcutconnections. In[44],an“inception”layeriscom-
sultssubstantiallybetterthanpreviousnetworks.
posedofashortcutbranchandafewdeeperbranches.
SimilarphenomenaarealsoshownontheCIFAR-10set Concurrentwithourwork,“highwaynetworks”[42,43]
| [20], suggesting |     | that | the optimization |     | difficulties |     | and the |         |          |             |     |             |           |       |
| ---------------- | --- | ---- | ---------------- | --- | ------------ | --- | ------- | ------- | -------- | ----------- | --- | ----------- | --------- | ----- |
|                  |     |      |                  |     |              |     |         | present | shortcut | connections |     | with gating | functions | [15]. |
effectsofourmethodarenotjustakintoaparticulardataset. These gates are data-dependent and have parameters, in
Wepresentsuccessfullytrainedmodelsonthisdatasetwith contrast to our identity shortcuts that are parameter-free.
over100layers,andexploremodelswithover1000layers.
|     |     |     |     |     |     |     |     | When a | gated shortcut |     | is “closed” | (approaching |     | zero), the |
| --- | --- | --- | --- | --- | --- | --- | --- | ------ | -------------- | --- | ----------- | ------------ | --- | ---------- |
On the ImageNet classification dataset [36], we obtain layers in highway networks represent non-residual func-
excellentresultsbyextremelydeepresidualnets. Our152- tions. On the contrary, our formulation always learns
layerresidualnetisthedeepestnetworkeverpresentedon residual functions; our identity shortcuts are never closed,
ImageNet, while still having lower complexity than VGG and all information is always passed through, with addi-
nets [41]. Our ensemble has 3.57% top-5 error on the tional residual functions to be learned. In addition, high-
2

way networks have not demonstrated accuracy gains with ReLU [29] and the biases are omitted for simplifying no-
extremelyincreaseddepth(e.g.,over100layers). tations. The operation + x is performed by a shortcut
F
|     |     |     |     |     |     |     |     | connection | and element-wise |     | addition. |     | We adopt | the sec- |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------- | ---------------- | --- | --------- | --- | -------- | -------- |
3.DeepResidualLearning ondnonlinearityaftertheaddition(i.e.,σ(y),seeFig.2).
TheshortcutconnectionsinEqn.(1)introduceneitherex-
3.1.ResidualLearning
|     |     |     |     |     |     |     |     | traparameternorcomputationcomplexity. |     |     |     |     | Thisisnotonly |     |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------------------------------- | --- | --- | --- | --- | ------------- | --- |
Let us consider as an underlying mapping to be attractiveinpracticebutalsoimportantinourcomparisons
(x)
H
fit by a few stacked layers (not necessarily the entire net), between plain and residual networks. We can fairly com-
withxdenotingtheinputstothefirstoftheselayers. Ifone pare plain/residual networks that simultaneously have the
|              |      |          |           |     |        |                |     | same number | of parameters, |     | depth, | width, | and computa- |     |
| ------------ | ---- | -------- | --------- | --- | ------ | -------------- | --- | ----------- | -------------- | --- | ------ | ------ | ------------ | --- |
| hypothesizes | that | multiple | nonlinear |     | layers | can asymptoti- |     |             |                |     |        |        |              |     |
callyapproximatecomplicatedfunctions2,thenitisequiv- tionalcost(exceptforthenegligibleelement-wiseaddition).
alent to hypothesize that they can asymptotically approxi- The dimensions of x and must be equal in Eqn.(1).
F
mate the residual functions, i.e., (x) x (assuming that Ifthisisnotthecase(e.g.,whenchangingtheinput/output
|     |     |     |     | H   | −   |     |     |     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
the input and output are of the same dimensions). So channels), we can perform a linear projection W by the
s
shortcutconnectionstomatchthedimensions:
| ratherthanexpectstackedlayerstoapproximate |     |     |     |     |     |     | (x),we |     |     |     |     |     |     |     |
| ------------------------------------------ | --- | --- | --- | --- | --- | --- | ------ | --- | --- | --- | --- | --- | --- | --- |
H
| explicitly | let these | layers | approximate |     | a residual | function |     |     |     |     |     |     |     |     |
| ---------- | --------- | ------ | ----------- | --- | ---------- | -------- | --- | --- | --- | --- | --- | --- | --- | --- |
(x) := (x) x. The original function thus becomes y= (x, W )+W x. (2)
|     |     |     |     |     |     |     |     |     |     | F   | { i | }   | s   |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F   | H   | −   |     |     |     |     |     |     |     |     |     |     |     |     |
(x)+x.Althoughbothformsshouldbeabletoasymptot-
| F                                                     |     |     |     |     |     |     |     | WecanalsouseasquarematrixW |     |     |     | inEqn.(1). | Butwewill |     |
| ----------------------------------------------------- | --- | --- | --- | --- | --- | --- | --- | -------------------------- | --- | --- | --- | ---------- | --------- | --- |
| icallyapproximatethedesiredfunctions(ashypothesized), |     |     |     |     |     |     |     |                            |     |     |     | s          |           |     |
showbyexperimentsthattheidentitymappingissufficient
theeaseoflearningmightbedifferent.
foraddressingthedegradationproblemandiseconomical,
| This | reformulation |     | is motivated |     | by the | counterintuitive |     |     |     |     |     |     |     |     |
| ---- | ------------- | --- | ------------ | --- | ------ | ---------------- | --- | --- | --- | --- | --- | --- | --- | --- |
andthusW
phenomenaaboutthedegradationproblem(Fig.1,left). As s isonlyusedwhenmatchingdimensions.
|              |     |                   |     |     |              |        |     | The form  | of the     | residual | function |          | is flexible. | Exper- |
| ------------ | --- | ----------------- | --- | --- | ------------ | ------ | --- | --------- | ---------- | -------- | -------- | -------- | ------------ | ------ |
| we discussed | in  | the introduction, |     |     | if the added | layers | can |           |            |          |          |          | F            |        |
|              |     |                   |     |     |              |        |     | iments in | this paper | involve  | a        | function | that has     | two or |
beconstructedasidentitymappings,adeepermodelshould
F
|               |       |     |         |      |               |          |     | threelayers(Fig.5),whilemorelayersarepossible. |     |     |     |     |     | Butif |
| ------------- | ----- | --- | ------- | ---- | ------------- | -------- | --- | ---------------------------------------------- | --- | --- | --- | --- | --- | ----- |
| have training | error | no  | greater | than | its shallower | counter- |     |                                                |     |     |     |     |     |       |
hasonlyasinglelayer,Eqn.(1)issimilartoalinearlayer:
| part. The | degradation |     | problem | suggests |     | that the | solvers |     |     |     |     |     |     |     |
| --------- | ----------- | --- | ------- | -------- | --- | -------- | ------- | --- | --- | --- | --- | --- | --- | --- |
F y=W
mighthavedifficultiesinapproximatingidentitymappings 1 x+x,forwhichwehavenotobservedadvantages.
Wealsonotethatalthoughtheabovenotationsareabout
| bymultiplenonlinearlayers. |     |     |     | Withtheresiduallearningre- |     |     |     |     |     |     |     |     |     |     |
| -------------------------- | --- | --- | --- | -------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
fully-connectedlayersforsimplicity,theyareapplicableto
| formulation, | if  | identity | mappings | are | optimal, | the | solvers |     |     |     |     |     |     |     |
| ------------ | --- | -------- | -------- | --- | -------- | --- | ------- | --- | --- | --- | --- | --- | --- | --- |
maysimplydrivetheweightsofthemultiplenonlinearlay- convolutional layers. The function (x, W i ) can repre-
|     |     |     |     |     |     |     |     |                                  |     |     |     | F                    | { } |     |
| --- | --- | --- | --- | --- | --- | --- | --- | -------------------------------- | --- | --- | --- | -------------------- | --- | --- |
|     |     |     |     |     |     |     |     | sentmultipleconvolutionallayers. |     |     |     | Theelement-wiseaddi- |     |     |
erstowardzerotoapproachidentitymappings.
Inrealcases,itisunlikelythatidentitymappingsareop- tionisperformedontwofeaturemaps,channelbychannel.
| timal, but | our reformulation |     |     | may help | to precondition |     | the |     |     |     |     |     |     |     |
| ---------- | ----------------- | --- | --- | -------- | --------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
3.3.NetworkArchitectures
| problem. | If the | optimal | function |     | is closer | to an | identity |     |     |     |     |     |     |     |
| -------- | ------ | ------- | -------- | --- | --------- | ----- | -------- | --- | --- | --- | --- | --- | --- | --- |
mappingthantoazeromapping,itshouldbeeasierforthe Wehavetestedvariousplain/residualnets,andhaveob-
solvertofindtheperturbationswithreferencetoanidentity servedconsistentphenomena. Toprovideinstancesfordis-
mapping,thantolearnthefunctionasanewone. Weshow cussion,wedescribetwomodelsforImageNetasfollows.
byexperiments(Fig.7)thatthelearnedresidualfunctionsin
|     |     |     |     |     |     |     |     | Plain Network. | Our | plain | baselines |     | (Fig. 3, middle) | are |
| --- | --- | --- | --- | --- | --- | --- | --- | -------------- | --- | ----- | --------- | --- | ---------------- | --- |
generalhavesmallresponses,suggestingthatidentitymap-
mainlyinspiredbythephilosophyofVGGnets[41](Fig.3,
pingsprovidereasonablepreconditioning.
|     |     |     |     |     |     |     |     | left). Theconvolutionallayersmostlyhave3 |     |     |     |     | 3filtersand |     |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------------------------------------- | --- | --- | --- | --- | ----------- | --- |
×
3.2.IdentityMappingbyShortcuts follow two simple design rules: (i) for the same output
|                               |          |          |     |          |                      |         |         | feature        | map size,   | the layers | have  | the         | same number    | of fil- |
| ----------------------------- | -------- | -------- | --- | -------- | -------------------- | ------- | ------- | -------------- | ----------- | ---------- | ----- | ----------- | -------------- | ------- |
| We adopt                      | residual | learning |     | to every | few                  | stacked | layers. |                |             |            |       |             |                |         |
|                               |          |          |     |          |                      |         |         | ters; and      | (ii) if the | feature    | map   | size        | is halved, the | num-    |
| AbuildingblockisshowninFig.2. |          |          |     |          | Formally,inthispaper |         |         |                |             |            |       |             |                |         |
|                               |          |          |     |          |                      |         |         | ber of filters | is doubled  |            | so as | to preserve | the time       | com-    |
weconsiderabuildingblockdefinedas: plexity per layer. We perform downsampling directly by
|        |           |     |       |            |         |     |          | convolutional   | layers   | that    | have     | a stride | of 2. The        | network |
| ------ | --------- | --- | ----- | ---------- | ------- | --- | -------- | --------------- | -------- | ------- | -------- | -------- | ---------------- | ------- |
|        |           | y=  | (x,   | W )+x.     |         |     | (1)      |                 |          |         |          |          |                  |         |
|        |           |     |       | i          |         |     |          | ends with       | a global | average | pooling  | layer    | and a 1000-way   |         |
|        |           |     | F     | { }        |         |     |          |                 |          |         |          |          |                  |         |
|        |           |     |       |            |         |     |          | fully-connected | layer    | with    | softmax. |          | The total number | of      |
| Here x | and y are | the | input | and output | vectors | of  | the lay- |                 |          |         |          |          |                  |         |
weightedlayersis34inFig.3(middle).
| ers considered. |         | The   | function | (x,   | W )             | represents | the    |            |          |         |     |       |                   |     |
| --------------- | ------- | ----- | -------- | ----- | --------------- | ---------- | ------ | ---------- | -------- | ------- | --- | ----- | ----------------- | --- |
|                 |         |       |          |       | i               |            |        | It isworth | noticing | thatour |     | model | has fewer filters | and |
| residual        | mapping | to be | learned. | F For | { the example } | in         | Fig. 2 |            |          |         |     |       |                   |     |
lowercomplexitythanVGGnets[41](Fig.3,left).Our34-
| that has | two layers, |     | = W | σ(W | x) in which | σ   | denotes |                                                      |     |     |     |     |     |     |
| -------- | ----------- | --- | --- | --- | ----------- | --- | ------- | ---------------------------------------------------- | --- | --- | --- | --- | --- | --- |
|          |             | F   |     | 2   | 1           |     |         | layerbaselinehas3.6billionFLOPs(multiply-adds),which |     |     |     |     |     |     |
2Thishypothesis,however,isstillanopenquestion.See[28]. isonly18%ofVGG-19(19.6billionFLOPs).
3

VGG-19 34-layer plain 34-layer residual ResidualNetwork. Basedontheaboveplainnetwork,we
|     |       |       |       | insert shortcut | connections | (Fig. | 3, right) | which | turn the |
| --- | ----- | ----- | ----- | --------------- | ----------- | ----- | --------- | ----- | -------- |
|     | image | image | image |                 |             |       |           |       |          |
o u t p u t   network into its counterpart residual version. The identity
s iz e :  2 2 4 3x3 conv, 64
shortcuts(Eqn.(1))canbedirectlyusedwhentheinputand
3x3 conv, 64
|     |     |     |     | output are | of the same | dimensions | (solid | line shortcuts | in  |
| --- | --- | --- | --- | ---------- | ----------- | ---------- | ------ | -------------- | --- |
pool, /2
| output  |     |     |     | Fig.3).Whenthedimensionsincrease(dottedlineshortcuts |     |     |     |     |     |
| ------- | --- | --- | --- | ---------------------------------------------------- | --- | --- | --- | --- | --- |
size: 112 3x3 conv, 128
|         |               |                  |                  | in Fig. 3),              | we consider       | two options:                | (A)        | The shortcut | still  |
| ------- | ------------- | ---------------- | ---------------- | ------------------------ | ----------------- | --------------------------- | ---------- | ------------ | ------ |
|         | 3x3 conv, 128 | 7x7 conv, 64, /2 | 7x7 conv, 64, /2 |                          |                   |                             |            |              |        |
|         |               |                  |                  | performs                 | identity mapping, | with                        | extra zero | entries      | padded |
|         | pool, /2      | pool, /2         | pool, /2         |                          |                   |                             |            |              |        |
| output  |               |                  |                  | forincreasingdimensions. |                   | Thisoptionintroducesnoextra |            |              |        |
size: 56
3x3 conv, 256 3x3 conv, 64 3x3 conv, 64 parameter;(B)TheprojectionshortcutinEqn.(2)isusedto
|     | 3x3 conv, 256 | 3x3 conv, 64 | 3x3 conv, 64 |                  |       |      |                  |     |      |
| --- | ------------- | ------------ | ------------ | ---------------- | ----- | ---- | ---------------- | --- | ---- |
|     |               |              |              | match dimensions | (done | by 1 | 1 convolutions). | For | both |
×
3x3 conv, 256 3x3 conv, 64 3x3 conv, 64 options, when the shortcuts go across feature maps of two
|     | 3x3 conv, 256 | 3x3 conv, 64 | 3x3 conv, 64 |     |     |     |     |     |     |
| --- | ------------- | ------------ | ------------ | --- | --- | --- | --- | --- | --- |
sizes,theyareperformedwithastrideof2.
|     |     | 3x3 conv, 64 | 3x3 conv, 64 |     |     |     |     |     |     |
| --- | --- | ------------ | ------------ | --- | --- | --- | --- | --- | --- |
3.4.Implementation
|     |     | 3x3 conv, 64 | 3x3 conv, 64 |     |     |     |     |     |     |
| --- | --- | ------------ | ------------ | --- | --- | --- | --- | --- | --- |
pool, /2 3x3 conv, 128, /2 3x3 conv, 128, /2 Our implementation for ImageNet follows the practice
output
size: 28 in [21, 41]. The image is resized with its shorter side ran-
|     | 3x3 conv, 512 | 3x3 conv, 128 | 3x3 conv, 128 |     |     |     |     |     |     |
| --- | ------------- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
3x3 conv, 512 3x3 conv, 128 3x3 conv, 128 domly sampled in [256,480] for scale augmentation [41].
A224 224cropisrandomlysampledfromanimageorits
|     | 3x3 conv, 512 | 3x3 conv, 128 | 3x3 conv, 128 |     |     |     |     |     |     |
| --- | ------------- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
horizontalflip,withtheper-pixelmeansubtracted[21].The ×
|     | 3x3 conv, 512 | 3x3 conv, 128 | 3x3 conv, 128 |     |     |     |     |     |     |
| --- | ------------- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
standardcoloraugmentationin[21]isused.Weadoptbatch
|              |          | 3x3 conv, 128     | 3x3 conv, 128     |                                                   |           |       |                        |             |     |
| ------------ | -------- | ----------------- | ----------------- | ------------------------------------------------- | --------- | ----- | ---------------------- | ----------- | --- |
|              |          |                   |                   | normalization                                     | (BN) [16] | right | after each             | convolution | and |
|              |          | 3x3 conv, 128     | 3x3 conv, 128     |                                                   |           |       |                        |             |     |
|              |          |                   |                   | beforeactivation,following[16].                   |           |       | Weinitializetheweights |             |     |
|              |          | 3x3 conv, 128     | 3x3 conv, 128     |                                                   |           |       |                        |             |     |
|              |          |                   |                   | asin[13]andtrainallplain/residualnetsfromscratch. |           |       |                        |             | We  |
| o u t p u t  | pool, /2 | 3x3 conv, 256, /2 | 3x3 conv, 256, /2 |                                                   |           |       |                        |             |     |
s iz e :  1 4 use SGD with a mini-batch size of 256. The learning rate
|     | 3x3 conv, 512 | 3x3 conv, 256 | 3x3 conv, 256 |     |     |     |     |     |     |
| --- | ------------- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
startsfrom0.1andisdividedby10whentheerrorplateaus,
|     | 3x3 conv, 512 | 3x3 conv, 256 | 3x3 conv, 256 |                                           |     |     |     |                |     |
| --- | ------------- | ------------- | ------------- | ----------------------------------------- | --- | --- | --- | -------------- | --- |
|     |               |               |               | andthemodelsaretrainedforupto60           |     |     |     | 104iterations. | We  |
|     | 3x3 conv, 512 | 3x3 conv, 256 | 3x3 conv, 256 |                                           |     |     | ×   |                |     |
|     |               |               |               | useaweightdecayof0.0001andamomentumof0.9. |     |     |     |                | We  |
|     | 3x3 conv, 512 | 3x3 conv, 256 | 3x3 conv, 256 |                                           |     |     |     |                |     |
donotusedropout[14],followingthepracticein[16].
3x3 conv, 256 3x3 conv, 256 Intesting,forcomparisonstudiesweadoptthestandard
3x3 conv, 256 3x3 conv, 256 10-crop testing [21]. For best results, we adopt the fully-
3x3 conv, 256 3x3 conv, 256 convolutional form as in [41, 13], and average the scores
3x3 conv, 256 3x3 conv, 256 at multiple scales (images are resized such that the shorter
|     |     | 3x3 conv, 256 | 3x3 conv, 256 | sideisin | 224,256,384,480,640 |     | ).  |     |     |
| --- | --- | ------------- | ------------- | -------- | ------------------- | --- | --- | --- | --- |
|     |     |               |               |          | {                   |     | }   |     |     |
|     |     | 3x3 conv, 256 | 3x3 conv, 256 |          |                     |     |     |     |     |
4.Experiments
|     |     | 3x3 conv, 256 | 3x3 conv, 256 |     |     |     |     |     |     |
| --- | --- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
o u t p u t
si z e :  7 pool, /2 3x3 conv, 512, /2 3x3 conv, 512, /2 4.1.ImageNetClassification
|     |     | 3x3 conv, 512 | 3x3 conv, 512 |     |     |     |     |     |     |
| --- | --- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
WeevaluateourmethodontheImageNet2012classifi-
|     |     | 3x3 conv, 512 | 3x3 conv, 512 |     |     |     |     |     |     |
| --- | --- | ------------- | ------------- | --- | --- | --- | --- | --- | --- |
cationdataset[36]thatconsistsof1000classes.Themodels
|     |     | 3x3 conv, 512 | 3x3 conv, 512 |             |                    |         |          |             |         |
| --- | --- | ------------- | ------------- | ----------- | ------------------ | ------- | -------- | ----------- | ------- |
|     |     |               |               | are trained | on the 1.28        | million | training | images, and | evalu-  |
|     |     | 3x3 conv, 512 | 3x3 conv, 512 |             |                    |         |          |             |         |
|     |     |               |               | ated on     | the 50k validation | images. | We       | also obtain | a final |
|     |     | 3x3 conv, 512 | 3x3 conv, 512 |             |                    |         |          |             |         |
o u t p u t  result on the 100k test images, reported by the test server.
|             | fc 4096 | avg pool | avg pool |                                        |     |     |     |     |     |
| ----------- | ------- | -------- | -------- | -------------------------------------- | --- | --- | --- | --- | --- |
| si z e :  1 |         |          |          | Weevaluatebothtop-1andtop-5errorrates. |     |     |     |     |     |
|             | fc 4096 | fc 1000  | fc 1000  |                                        |     |     |     |     |     |
Plain Networks.
|                                                 | fc 1000 |     |           |                                   | We                                    | first evaluate | 18-layer        | and | 34-layer |
| ----------------------------------------------- | ------- | --- | --------- | --------------------------------- | ------------------------------------- | -------------- | --------------- | --- | -------- |
|                                                 |         |     |           | plainnets.                        | The34-layerplainnetisinFig.3(middle). |                |                 |     | The      |
|                                                 |         |     |           | 18-layerplainnetisofasimilarform. |                                       |                | SeeTable1forde- |     |          |
| Figure3.ExamplenetworkarchitecturesforImageNet. |         |     | Left: the |                                   |                                       |                |                 |     |          |
VGG-19 model [41] (19.6 billion FLOPs) as a reference. Mid- tailedarchitectures.
dle:aplainnetworkwith34parameterlayers(3.6billionFLOPs). TheresultsinTable2showthatthedeeper34-layerplain
Right: a residual network with 34 parameter layers (3.6 billion net has higher validation error than the shallower 18-layer
FLOPs).Thedottedshortcutsincreasedimensions.Table1shows
|     |     |     |     | plain net. | To reveal the | reasons, | in Fig. | 4 (left) we | com- |
| --- | --- | --- | --- | ---------- | ------------- | -------- | ------- | ----------- | ---- |
moredetailsandothervariants.
paretheirtraining/validationerrorsduringthetrainingpro-
|     |     |     |     | cedure. | We have observed | the | degradation | problem | - the |
| --- | --- | --- | --- | ------- | ---------------- | --- | ----------- | ------- | ----- |
4

layername outputsize 18-layer 34-layer 50-layer 101-layer 152-layer
conv1 112 112 7 7,64,stride2
× ×
3 3maxpool,stride2
conv2x 56 × 56 (cid:20) 3 3 × 3 3 , , 6 6 4 4 (cid:21) × 2 (cid:20) 3 3 × 3 3 , , 6 6 4 4 (cid:21) × 3   × 1 3 × × 1 3 , , 6 6 4 4   × 3   1 3 × × 1 3 , , 6 6 4 4   × 3   1 3 × × 1 3 , , 6 6 4 4   × 3
× × 1 1,256 1 1,256 1 1,256
conv3x 28 × 28 (cid:20) 3 3 × 3 3 , , 1 1 2 2 8 8 (cid:21) × 2 (cid:20) 3 3 × 3 3 , , 1 1 2 2 8 8 (cid:21) × 4   1 3 × × × 1 3 , , 1 1 2 2 8 8   × 4   1 3 × × × 1 3 , , 1 1 2 2 8 8   × 4   1 3 × × × 1 3 , , 1 1 2 2 8 8   × 8
× × 1 1,512 1 1,512 1 1,512
conv4x 14 × 14 (cid:20) 3 3 × 3 3 , , 2 2 5 5 6 6 (cid:21) × 2 (cid:20) 3 3 × 3 3 , , 2 2 5 5 6 6 (cid:21) × 6   1 3 × × × 1 3 , , 2 2 5 5 6 6   × 6   1 3 × × × 1 3 , , 2 2 5 5 6 6   × 23   1 3 × × × 1 3 , , 2 2 5 5 6 6   × 36
× × 1 1,1024 1 1,1024 1 1,1024
conv5x 7 × 7 (cid:20) 3 3 × 3 3 , , 5 5 1 1 2 2 (cid:21) × 2 (cid:20) 3 3 × 3 3 , , 5 5 1 1 2 2 (cid:21) × 3   1 3 × × × 1 3 , , 5 5 1 1 2 2   × 3   1 3 × × × 1 3 , , 5 5 1 1 2 2   × 3   1 3 × × × 1 3 , , 5 5 1 1 2 2   × 3
× × 1 1,2048 1 1,2048 1 1,2048
× × ×
1 1 averagepool,1000-dfc,softmax
×
FLOPs 1.8 109 3.6 109 3.8 109 7.6 109 11.3 109
× × × × ×
Table1.ArchitecturesforImageNet. Buildingblocksareshowninbrackets(seealsoFig.5),withthenumbersofblocksstacked. Down-
samplingisperformedbyconv3 1,conv4 1,andconv5 1withastrideof2.
60
50
40
30
20
0 10 20 30 40 50
iter. (1e4)
)%(
rorre
60
50
40
30
plain-18
plain-34
20
0 10 20 30 40 50
iter. (1e4)
)%(
rorre
34-layer
18-layer
18-layer
ResNet-18
ResNet-34 34-layer
Figure4.TrainingonImageNet.Thincurvesdenotetrainingerror,andboldcurvesdenotevalidationerrorofthecentercrops.Left:plain
networksof18and34layers.Right:ResNetsof18and34layers.Inthisplot,theresidualnetworkshavenoextraparametercomparedto
theirplaincounterparts.
plain ResNet reducing of the training error3. The reason for such opti-
18layers 27.94 27.88 mizationdifficultieswillbestudiedinthefuture.
34layers 28.54 25.03
Residual Networks. Next we evaluate 18-layer and 34-
Table2.Top-1error(%,10-croptesting)onImageNetvalidation. layer residual nets (ResNets). The baseline architectures
HeretheResNetshavenoextraparametercomparedtotheirplain arethesameastheaboveplainnets,expectthatashortcut
counterparts.Fig.4showsthetrainingprocedures.
connectionisaddedtoeachpairof3 3filtersasinFig.3
×
(right). In the first comparison (Table 2 and Fig. 4 right),
weuseidentitymappingforallshortcutsandzero-padding
34-layer plain net has higher training error throughout the forincreasingdimensions(optionA).Sotheyhavenoextra
whole training procedure, even though the solution space parametercomparedtotheplaincounterparts.
of the 18-layer plain network is a subspace of that of the We have three major observations from Table 2 and
34-layerone. Fig. 4. First, the situation is reversed with residual learn-
We argue that this optimization difficulty is unlikely to ing–the34-layerResNetisbetterthanthe18-layerResNet
becausedbyvanishinggradients. Theseplainnetworksare (by2.8%). Moreimportantly,the34-layerResNetexhibits
trained with BN [16], which ensures forward propagated considerablylowertrainingerrorandisgeneralizabletothe
signalstohavenon-zerovariances. Wealsoverifythatthe validationdata. Thisindicatesthatthedegradationproblem
backwardpropagatedgradientsexhibithealthynormswith is well addressed in this setting and we manage to obtain
BN. So neither forward nor backward signals vanish. In accuracygainsfromincreaseddepth.
fact, the 34-layer plain net is still able to achieve compet- Second, compared to its plain counterpart, the 34-layer
itive accuracy (Table 3), suggesting that the solver works
3Wehaveexperimentedwithmoretrainingiterations(3×)andstillob-
tosomeextent. Weconjecturethatthedeepplainnetsmay
servedthedegradationproblem, suggestingthatthisproblemcannotbe
haveexponentiallylowconvergencerates,whichimpactthe feasiblyaddressedbysimplyusingmoreiterations.
5

|     |            |                     |      |     |     | 64-d |     |     | 256-d   |     |     |
| --- | ---------- | ------------------- | ---- | --- | --- | ---- | --- | --- | ------- | --- | --- |
|     | model      | top-1err. top-5err. |      |     |     |      |     |     |         |     |     |
|     | VGG-16[41] | 28.07               | 9.33 |     |     |      |     |     | 1x1, 64 |     |     |
3x3, 64
|     |               |     |      |     | relu |     |     |     | relu    |     |     |
| --- | ------------- | --- | ---- | --- | ---- | --- | --- | --- | ------- | --- | --- |
|     | GoogLeNet[44] | -   | 9.15 |     |      |     |     |     | 3x3, 64 |     |     |
relu
|     | PReLU-net[13] | 24.27 | 7.38 |     | 3x3, 64 |     |     |     |     |     |     |
| --- | ------------- | ----- | ---- | --- | ------- | --- | --- | --- | --- | --- | --- |
1x1, 256
|     | plain-34 | 28.54 | 10.02 |     |      |     |     |     |      |     |     |
| --- | -------- | ----- | ----- | --- | ---- | --- | --- | --- | ---- | --- | --- |
|     |          | 25.03 | 7.76  |     | relu |     |     |     | relu |     |     |
ResNet-34A
|     | ResNet-34B | 24.52 | 7.46 |        |             |          |          |     |               |     |         |
| --- | ---------- | ----- | ---- | ------ | ----------- | -------- | -------- | --- | ------------- | --- | ------- |
|     |            |       |      | Figure | 5. A deeper | residual | function | F   | for ImageNet. |     | Left: a |
|     | ResNet-34C | 24.19 | 7.40 |        |             |          |          |     |               |     |         |
buildingblock(on56×56featuremaps)asinFig.3forResNet-
|     | ResNet-50 | 22.85 | 6.71 |     |     |     |     |     |     |     |     |
| --- | --------- | ----- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
34.Right:a“bottleneck”buildingblockforResNet-50/101/152.
|     | ResNet-101 | 21.75 | 6.05 |                 |     |          |           |      |      |           |      |
| --- | ---------- | ----- | ---- | --------------- | --- | -------- | --------- | ---- | ---- | --------- | ---- |
|     | ResNet-152 | 21.43 | 5.71 |                 |     |          |           |      |      |           |      |
|     |            |       |      | parameter-free, |     | identity | shortcuts | help | with | training. | Next |
Table3.Errorrates(%,10-croptesting)onImageNetvalidation. weinvestigateprojectionshortcuts(Eqn.(2)). InTable3we
| VGG-16isbasedonourtest. |     | ResNet-50/101/152areofoptionB |     |                      |     |     |                                 |     |     |     |     |
| ----------------------- | --- | ----------------------------- | --- | -------------------- | --- | --- | ------------------------------- | --- | --- | --- | --- |
|                         |     |                               |     | comparethreeoptions: |     |     | (A)zero-paddingshortcutsareused |     |     |     |     |
thatonlyusesprojectionsforincreasingdimensions.
forincreasingdimensions,andallshortcutsareparameter-
method top-1err. top-5err. free (the same as Table 2 and Fig. 4 right); (B) projec-
tionshortcutsareusedforincreasingdimensions,andother
| VGG[41](ILSVRC’14) |     | -   | 8.43† |     |     |     |     |     |     |     |     |
| ------------------ | --- | --- | ----- | --- | --- | --- | --- | --- | --- | --- | --- |
shortcutsareidentity;and(C)allshortcutsareprojections.
| GoogLeNet[44](ILSVRC’14) |     | -   | 7.89 |     |     |     |     |     |     |     |     |
| ------------------------ | --- | --- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
Table3showsthatallthreeoptionsareconsiderablybet-
| VGG[41](v5) |     | 24.4 | 7.1 |     |     |     |     |     |     |     |     |
| ----------- | --- | ---- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
terthantheplaincounterpart.BisslightlybetterthanA.We
| PReLU-net[13] |     | 21.59 | 5.71 |     |     |     |     |     |     |     |     |
| ------------- | --- | ----- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
arguethatthisisbecausethezero-paddeddimensionsinA
| BN-inception[16] |     | 21.99 | 5.81 |     |     |     |     |     |     |     |     |
| ---------------- | --- | ----- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
indeedhavenoresiduallearning.Cismarginallybetterthan
| ResNet-34B |     | 21.84 | 5.71 |         |              |            |        |            |            |            |      |
| ---------- | --- | ----- | ---- | ------- | ------------ | ---------- | ------ | ---------- | ---------- | ---------- | ---- |
|            |     |       |      | B, and  | we attribute | this       | to the | extra      | parameters | introduced |      |
| ResNet-34C |     | 21.53 | 5.60 |         |              |            |        |            |            |            |      |
|            |     |       |      | by many | (thirteen)   | projection |        | shortcuts. | But        | the small  | dif- |
| ResNet-50  |     | 20.74 | 5.25 |         |              |            |        |            |            |            |      |
ferencesamongA/B/Cindicatethatprojectionshortcutsare
| ResNet-101 |     | 19.87 | 4.60 |     |     |     |     |     |     |     |     |
| ---------- | --- | ----- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
notessentialforaddressingthedegradationproblem.Sowe
| ResNet-152 |     | 19.38 | 4.49 |     |     |     |     |     |     |     |     |
| ---------- | --- | ----- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
donotuseoptionCintherestofthispaper,toreducemem-
Table4.Errorrates(%)ofsingle-modelresultsontheImageNet ory/timecomplexityandmodelsizes. Identityshortcutsare
validationset(except†reportedonthetestset).
|     |     |     |     | particularly | important |     | for not | increasing | the | complexity | of  |
| --- | --- | --- | --- | ------------ | --------- | --- | ------- | ---------- | --- | ---------- | --- |
thebottleneckarchitecturesthatareintroducedbelow.
| method |     | top-5err.(test) |     |     |     |     |     |     |     |     |     |
| ------ | --- | --------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
VGG[41](ILSVRC’14) 7.32 Deeper Bottleneck Architectures. Next we describe our
GoogLeNet[44](ILSVRC’14) 6.66 deepernetsforImageNet.Becauseofconcernsonthetrain-
VGG[41](v5) 6.8 ing time that we can afford, we modify the building block
PReLU-net[13] 4.94 as a bottleneck design4. For each residual function , we
F
BN-inception[16] 4.82 useastackof3layersinsteadof2(Fig.5). Thethreelayers
ResNet(ILSVRC’15) 3.57 are1 1,3 3,and1 1convolutions,wherethe1 1layers
|     |     |     |     | ×   | ×   | ×   |     |     |     | ×   |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
areresponsibleforreducingandthenincreasing(restoring)
| Table5.Errorrates(%)ofensembles.             |     | Thetop-5errorisonthe |     |                        |             |     |                              |         |             |     |       |
| -------------------------------------------- | --- | -------------------- | --- | ---------------------- | ----------- | --- | ---------------------------- | ------- | ----------- | --- | ----- |
|                                              |     |                      |     | dimensions,leavingthe3 |             |     | 3layerabottleneckwithsmaller |         |             |     |       |
| testsetofImageNetandreportedbythetestserver. |     |                      |     |                        |             |     | ×                            |         |             |     |       |
|                                              |     |                      |     | input/output           | dimensions. |     | Fig.                         | 5 shows | an example, |     | where |
bothdesignshavesimilartimecomplexity.
Theparameter-freeidentityshortcutsareparticularlyim-
ResNetreducesthetop-1errorby3.5%(Table2),resulting
portantforthebottleneckarchitectures.Iftheidentityshort-
fromthesuccessfullyreducedtrainingerror(Fig.4rightvs.
left). Thiscomparisonverifiestheeffectivenessofresidual cut in Fig. 5 (right) is replaced with projection, one can
showthatthetimecomplexityandmodelsizearedoubled,
learningonextremelydeepsystems.
Last, we also note that the 18-layer plain/residual nets as the shortcut is connected to the two high-dimensional
|     |     |     |     | ends. | So identity | shortcuts | lead | to  | more efficient | models |     |
| --- | --- | --- | --- | ----- | ----------- | --------- | ---- | --- | -------------- | ------ | --- |
arecomparablyaccurate(Table2),butthe18-layerResNet
forthebottleneckdesigns.
| convergesfaster(Fig.4rightvs.left). |     | Whenthenetis“not |     |          |         |     |            |      |         |       |        |
| ----------------------------------- | --- | ---------------- | --- | -------- | ------- | --- | ---------- | ---- | ------- | ----- | ------ |
|                                     |     |                  |     | 50-layer | ResNet: |     | We replace | each | 2-layer | block | in the |
overlydeep”(18layershere),thecurrentSGDsolverisstill
| abletofindgoodsolutionstotheplainnet. |     |     | Inthiscase,the |     |     |     |     |     |     |     |     |
| ------------------------------------- | --- | --- | -------------- | --- | --- | --- | --- | --- | --- | --- | --- |
4Deepernon-bottleneckResNets(e.g.,Fig.5left)alsogainaccuracy
| ResNet | eases the optimization | by providing | faster conver- |     |     |     |     |     |     |     |     |
| ------ | ---------------------- | ------------ | -------------- | --- | --- | --- | --- | --- | --- | --- | --- |
fromincreaseddepth(asshownonCIFAR-10),butarenotaseconomical
genceattheearlystage. asthebottleneckResNets.Sotheusageofbottleneckdesignsismainlydue
|     |     |     |     | topracticalconsiderations. |     |     | Wefurthernotethatthedegradationproblem |     |     |     |     |
| --- | --- | --- | --- | -------------------------- | --- | --- | -------------------------------------- | --- | --- | --- | --- |
Identity vs. Projection Shortcuts. We have shown that ofplainnetsisalsowitnessedforthebottleneckdesigns.
6

34-layernetwiththis3-layerbottleneckblock,resultingin method error(%)
a50-layerResNet(Table1).WeuseoptionBforincreasing Maxout[10] 9.38
| dimensions. |     | Thismodelhas3.8billionFLOPs. |     |     |     |     |     |     |     | NIN[25] |     | 8.81 |     |     |
| ----------- | --- | ---------------------------- | --- | --- | --- | --- | --- | --- | --- | ------- | --- | ---- | --- | --- |
101-layer and 152-layer ResNets: We construct 101- DSN[24] 8.22
| layer | and | 152-layer ResNets |     | by using | more 3-layer | blocks |     |     |     |         |         |     |     |     |
| ----- | --- | ----------------- | --- | -------- | ------------ | ------ | --- | --- | --- | ------- | ------- | --- | --- | --- |
|       |     |                   |     |          |              |        |     |     |     | #layers | #params |     |     |     |
(Table 1). Remarkably, although the depth is significantly FitNet[35] 19 2.5M 8.39
increased, the 152-layer ResNet (11.3 billion FLOPs) still Highway[42,43] 19 2.3M 7.54(7.72±0.16)
has lower complexity than VGG-16/19 nets (15.3/19.6 bil- Highway[42,43] 32 1.25M 8.80
| lionFLOPs). |     |     |     |     |     |     |     | ResNet |     | 20  | 0.27M | 8.75 |     |     |
| ----------- | --- | --- | --- | --- | --- | --- | --- | ------ | --- | --- | ----- | ---- | --- | --- |
The 50/101/152-layer ResNets are more accurate than ResNet 32 0.46M 7.51
the34-layeronesbyconsiderablemargins(Table3and4). ResNet 44 0.66M 7.17
| We  | do not | observe the | degradation | problem |     | and thus en- |     |        |     |     |       |      |     |     |
| --- | ------ | ----------- | ----------- | ------- | --- | ------------ | --- | ------ | --- | --- | ----- | ---- | --- | --- |
|     |        |             |             |         |     |              |     | ResNet |     | 56  | 0.85M | 6.97 |     |     |
joysignificantaccuracygainsfromconsiderablyincreased ResNet 110 1.7M 6.43(6.61±0.16)
depth.Thebenefitsofdeptharewitnessedforallevaluation ResNet 1202 19.4M 7.93
metrics(Table3and4).
|             |     |                       |     |          |     |            | Table6.ClassificationerrorontheCIFAR-10testset. |     |     |     |     |     |     | Allmeth- |
| ----------- | --- | --------------------- | --- | -------- | --- | ---------- | ----------------------------------------------- | --- | --- | --- | --- | --- | --- | -------- |
| Comparisons |     | with State-of-the-art |     | Methods. |     | In Table 4 |                                                 |     |     |     |     |     |     |          |
odsarewithdataaugmentation.ForResNet-110,werunit5times
we compare with the previous best single-model results. andshow“best(mean±std)”asin[43].
Ourbaseline34-layerResNetshaveachievedverycompet-
| itive | accuracy. | Our 152-layer |     | ResNet | has a | single-model |     |     |     |     |     |     |     |     |
| ----- | --------- | ------------- | --- | ------ | ----- | ------------ | --- | --- | --- | --- | --- | --- | --- | --- |
soourresidualmodelshaveexactlythesamedepth,width,
| top-5 | validation | error | of 4.49%. | This | single-model | result |     |     |     |     |     |     |     |     |
| ----- | ---------- | ----- | --------- | ---- | ------------ | ------ | --- | --- | --- | --- | --- | --- | --- | --- |
andnumberofparametersastheplaincounterparts.
| outperforms |     | all previous | ensemble | results | (Table | 5). We |     |     |     |     |     |     |     |     |
| ----------- | --- | ------------ | -------- | ------- | ------ | ------ | --- | --- | --- | --- | --- | --- | --- | --- |
Weuseaweightdecayof0.0001andmomentumof0.9,
combinesixmodelsofdifferentdepthtoformanensemble
andadopttheweightinitializationin[13]andBN[16]but
| (only | with | two 152-layer | ones | at the | time of | submitting). |     |     |     |     |     |     |     |     |
| ----- | ---- | ------------- | ---- | ------ | ------- | ------------ | --- | --- | --- | --- | --- | --- | --- | --- |
This leads to 3.57% top-5 error on the test set (Table 5). with no dropout. These models are trained with a mini-
|     |     |     |     |     |     |     | batch | size | of 128 | on two | GPUs. We | start | with a | learning |
| --- | --- | --- | --- | --- | --- | --- | ----- | ---- | ------ | ------ | -------- | ----- | ------ | -------- |
Thisentrywonthe1stplaceinILSVRC2015.
|     |     |     |     |     |     |     | rate | of 0.1, | divide | it by | 10 at 32k and | 48k | iterations, | and |
| --- | --- | --- | --- | --- | --- | --- | ---- | ------- | ------ | ----- | ------------- | --- | ----------- | --- |
4.2.CIFAR-10andAnalysis terminatetrainingat64kiterations,whichisdeterminedon
|                                                  |           |                |         |                      |             |               | a45k/5ktrain/valsplit.       |            |                | Wefollowthesimpledataaugmen-      |                             |      |      |          |
| ------------------------------------------------ | --------- | -------------- | ------- | -------------------- | ----------- | ------------- | ---------------------------- | ---------- | -------------- | --------------------------------- | --------------------------- | ---- | ---- | -------- |
| We                                               | conducted | more           | studies | on the               | CIFAR-10    | dataset       |                              |            |                |                                   |                             |      |      |          |
|                                                  |           |                |         |                      |             |               | tationin[24]fortraining:     |            |                |                                   | 4pixelsarepaddedoneachside, |      |      |          |
| [20],                                            | which     | consists       | of 50k  | training images      |             | and 10k test- |                              |            |                |                                   |                             |      |      |          |
|                                                  |           |                |         |                      |             |               | and                          | a 32       | 32             | crop is randomly                  | sampled                     | from | the  | padded   |
| ing                                              | images    | in 10 classes. | We      | present              | experiments | trained       |                              |            | ×              |                                   |                             |      |      |          |
|                                                  |           |                |         |                      |             |               | image                        | or         | its horizontal | flip.                             | For testing,                | we   | only | evaluate |
| onthetrainingsetandevaluatedonthetestset.        |           |                |         |                      |             | Ourfocus      |                              |            |                |                                   |                             |      |      |          |
|                                                  |           |                |         |                      |             |               | thesingleviewoftheoriginal32 |            |                |                                   | 32image.                    |      |      |          |
| isonthebehaviorsofextremelydeepnetworks,butnoton |           |                |         |                      |             |               |                              |            |                |                                   | ×                           |      |      |          |
|                                                  |           |                |         |                      |             |               |                              | Wecomparen |                | = 3,5,7,9                         | ,leadingto20,32,44,and      |      |      |          |
| pushingthestate-of-the-artresults,               |           |                |         | soweintentionallyuse |             |               |                              |            |                | {                                 | }                           |      |      |          |
|                                                  |           |                |         |                      |             |               | 56-layernetworks.            |            |                | Fig.6(left)showsthebehaviorsofthe |                             |      |      |          |
simplearchitecturesasfollows.
|     |     |     |     |     |     |     | plainnets. |     | Thedeepplainnetssufferfromincreaseddepth, |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | ---------- | --- | ----------------------------------------- | --- | --- | --- | --- | --- |
Theplain/residualarchitecturesfollowtheforminFig.3
|                             |     |                       |     |                  |               |         | and                                                | exhibit | higher | training | error when | going | deeper. | This |
| --------------------------- | --- | --------------------- | --- | ---------------- | ------------- | ------- | -------------------------------------------------- | ------- | ------ | -------- | ---------- | ----- | ------- | ---- |
| (middle/right).             |     | Thenetworkinputsare32 |     |                  | 32images,with |         |                                                    |         |        |          |            |       |         |      |
|                             |     |                       |     |                  | ×             |         | phenomenonissimilartothatonImageNet(Fig.4,left)and |         |        |          |            |       |         |      |
| theper-pixelmeansubtracted. |     |                       |     | Thefirstlayeris3 |               | 3convo- |                                                    |         |        |          |            |       |         |      |
onMNIST(see[42]),suggestingthatsuchanoptimization
×
lutions. Thenweuseastackof6nlayerswith3 3convo- difficultyisafundamentalproblem.
×
| lutionsonthefeaturemapsofsizes |           |          |                                   | 32,16,8     |       | respectively, |                                                    |        |          |          |               |            |          |         |
| ------------------------------ | --------- | -------- | --------------------------------- | ----------- | ----- | ------------- | -------------------------------------------------- | ------ | -------- | -------- | ------------- | ---------- | -------- | ------- |
|                                |           |          |                                   |             |       |               |                                                    | Fig. 6 | (middle) | shows    | the behaviors | of         | ResNets. | Also    |
| with                           | 2n layers | for each | feature                           | map { size. | The } | numbers of    |                                                    |        |          |          |               |            |          |         |
|                                |           |          |                                   |             |       |               | similar                                            | to     | the      | ImageNet | cases (Fig.   | 4, right), | our      | ResNets |
| filtersare                     |           | 16,32,64 | respectively.Thesubsamplingisper- |             |       |               |                                                    |        |          |          |               |            |          |         |
|                                | {         | }        |                                   |             |       |               | managetoovercometheoptimizationdifficultyanddemon- |        |          |          |               |            |          |         |
formedbyconvolutionswithastrideof2.Thenetworkends
strateaccuracygainswhenthedepthincreases.
with a global average pooling, a 10-way fully-connected We further explore n that leads to a 110-layer
|     |     |     |     |     |     |     |     |     |     |     | = 18 |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---- | --- | --- | --- |
layer,andsoftmax.Therearetotally6n+2stackedweighted
|     |     |     |     |     |     |     | ResNet. |     | In this | case, we | find that the | initial | learning | rate |
| --- | --- | --- | --- | --- | --- | --- | ------- | --- | ------- | -------- | ------------- | ------- | -------- | ---- |
layers. Thefollowingtablesummarizesthearchitecture:
|     |     |     |     |     |     |     | of  | 0.1 is | slightly | too large | to start converging5. |     | So  | we use |
| --- | --- | --- | --- | --- | --- | --- | --- | ------ | -------- | --------- | --------------------- | --- | --- | ------ |
0.01towarmupthetraininguntilthetrainingerrorisbelow
|     | outputmapsize |     | 32×32 | 16×16 |     | 8×8 |     |     |     |     |     |     |     |     |
| --- | ------------- | --- | ----- | ----- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
80%(about400iterations),andthengobackto0.1andcon-
|        |          | #layers       | 1+2n     |           | 2n          | 2n        |                |     |                                          |                                      |      |       |      |          |
| ------ | -------- | ------------- | -------- | --------- | ----------- | --------- | -------------- | --- | ---------------------------------------- | ------------------------------------ | ---- | ----- | ---- | -------- |
|        |          |               |          |           |             |           | tinuetraining. |     |                                          | Therestofthelearningscheduleisasdone |      |       |      |          |
|        |          | #filters      |          | 16        | 32          | 64        |                |     |                                          |                                      |      |       |      |          |
|        |          |               |          |           |             |           | previously.    |     | This110-layernetworkconvergeswell(Fig.6, |                                      |      |       |      |          |
|        |          |               |          |           |             |           | middle).       |     | It has                                   | fewer parameters                     | than | other | deep | and thin |
| When   | shortcut | connections   |          | are used, | they are    | connected |                |     |                                          |                                      |      |       |      |          |
| to the | pairs    | of 3 3 layers | (totally | 3n        | shortcuts). | On this   |                |     |                                          |                                      |      |       |      |          |
5Withaninitiallearningrateof0.1,itstartsconverging(<90%error)
×
datasetweuseidentityshortcutsinallcases(i.e.,optionA), afterseveralepochs,butstillreachessimilaraccuracy.
7

20
|     |     |     |     |     |     |   20 |     |     |     |     | ResNet-20   | 20  | residual-110  |     |
| --- | --- | --- | --- | --- | --- | ---- | --- | --- | --- | --- | ----------- | --- | ------------- | --- |
|     |     |     |     |     |     |      |     |     |     |     | ResNet-32   |     | residual-1202 |     |
ResNet-44
|     |     |     |     |     | 56-layer |     |     |     |     |     | ResNet-56 |     |     |     |
| --- | --- | --- | --- | --- | -------- | --- | --- | --- | --- | --- | --------- | --- | --- | --- |
ResNet-110
|     | )%( rorre |     |     |     |     | )%( rorre |     |     |     |     | )%( rorre |     |     |     |
| --- | --------- | --- | --- | --- | --- | --------- | --- | --- | --- | --- | --------- | --- | --- | --- |
|     | 10        |     |     |     |     | 10        |     |     |     |     | 20-layer  | 10  |     |     |
20-layer
110-layer
|     | 5   | plain-20 |     |     |     | 5   |     |     |     |     |     | 5   |     |     |
| --- | --- | -------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
plain-32
plain-44
|     |      | plain-56 |                 |     |     |      |     |     |     |     |     | 1   |     |     |
| --- | ---- | -------- | --------------- | --- | --- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
|     | 00   |          |                 |     |     | 00   |     |     |     |     |     | 0   |     |     |
|     |      | 1        | 2 iter. (1e4) 3 | 4   | 5 6 |      | 1   | 2   | 3   | 4 5 | 6   | 4   | 5 6 |     |
Figure6.TrainingonCIFAR-10. Dashedlinesdenotetrainingerror,andboldlinesdenotetestingerror. iter. (1e4) Left: iter. (1e4) plainnetworks. Theerror
ofplain-110ishigherthan60%andnotdisplayed.Middle:ResNets.Right:ResNetswith110and1202layers.

|     |     |     |     |     |     | plain-20  |     |     | trainingdata |     | 07+12     |      | 07++12    |     |
| --- | --- | --- | --- | --- | --- | --------- | --- | --- | ------------ | --- | --------- | ---- | --------- | --- |
| 3   |     |     |     |     |     | plain-56  |     |     |              |     |           |      |           |     |
|     |     |     |     |     |     | ResNet-20 |     |     | testdata     |     | VOC07test |      | VOC12test |     |
| dts |     |     |     |     |     | ResNet-56 |     |     |              |     |           |      |           |     |
| 2   |     |     |     |     |     |           |     |     | VGG-16       |     |           | 73.2 | 70.4      |     |
ResNet-110
| 1   |     |     |     |     |     |     |     |     | ResNet-101 |     |     | 76.4 | 73.8 |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---------- | --- | --- | ---- | ---- | --- |

| 0   | 20  | 40  |     | 60  | 80  | 100 |     |     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
layer index (original) Table 7. Object detection mAP (%) on the PASCAL VOC

3 plain-20 2007/2012 test sets using baseline Faster R-CNN. See also Ta-
plain-56
|       |     |     |     |     |     | ResNet-20 |     | ble10and11forbetterresults. |     |     |     |     |     |     |
| ----- | --- | --- | --- | --- | --- | --------- | --- | --------------------------- | --- | --- | --- | --- | --- | --- |
| dts 2 |     |     |     |     |     | ResNet-56 |     |                             |     |     |     |     |     |     |
ResNet-110
|     |     |     |     |     |     |     |     |     | metric |     | mAP@.5 |     | mAP@[.5,.95] |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ------ | --- | ------ | --- | ------------ | --- |
1
|     |     |                                      |     |     |     |     |     |     | VGG-16     |     | 41.5 |     | 21.2 |     |
| --- | --- | ------------------------------------ | --- | --- | --- | --- | --- | --- | ---------- | --- | ---- | --- | ---- | --- |
| 0   | 20  | layer index (sorted by magnitude) 40 |     | 60  | 80  | 100 |     |     |            |     |      |     |      |     |
|     |     |                                      |     |     |     |     |     |     | ResNet-101 |     | 48.4 |     | 27.2 |     |
Figure7.Standarddeviations(std)oflayerresponsesonCIFAR-
10.Theresponsesaretheoutputsofeach3×3layer,afterBNand Table 8. Object detection mAP (%) on the COCO validation set
before nonlinearity. Top: the layers are shown in their original usingbaselineFasterR-CNN.SeealsoTable9forbetterresults.
order.Bottom:theresponsesarerankedindescendingorder.
|     |     |     |     |     |     |     |     | havesimilartrainingerror. |     |     | Wearguethatthisisbecauseof |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------------------- | --- | --- | -------------------------- | --- | --- | --- |
networks such as FitNet [35] and Highway [42] (Table 6), overfitting. The 1202-layer network may be unnecessarily
|     |     |     |     |     |     |     |     | large | (19.4M) | for this | small | dataset. | Strong regularization |     |
| --- | --- | --- | --- | --- | --- | --- | --- | ----- | ------- | -------- | ----- | -------- | --------------------- | --- |
yetisamongthestate-of-the-artresults(6.43%,Table6).
suchasmaxout[10]ordropout[14]isappliedtoobtainthe
| Analysis   | of Layer | Responses.   |            | Fig. 7 shows | the           | standard |     |                                          |     |     |     |     |     |              |
| ---------- | -------- | ------------ | ---------- | ------------ | ------------- | -------- | --- | ---------------------------------------- | --- | --- | --- | --- | --- | ------------ |
|            |          |              |            |              |               |          |     | bestresults([10,25,24,35])onthisdataset. |     |     |     |     |     | Inthispaper, |
| deviations | (std)    | of the layer | responses. |              | The responses | are      |     |                                          |     |     |     |     |     |              |
weusenomaxout/dropoutandjustsimplyimposeregular-
| the outputs | of each | 3 3 | layer, | after BN | and before | other |     |         |          |     |                    |     |            |         |
| ----------- | ------- | --- | ------ | -------- | ---------- | ----- | --- | ------- | -------- | --- | ------------------ | --- | ---------- | ------- |
|             |         |     |        |          |            |       |     | ization | via deep | and | thin architectures |     | by design, | without |
×
nonlinearity (ReLU/addition). For ResNets, this analy- distracting from the focus on the difficulties of optimiza-
| sis reveals | the response |     | strength | of the residual |     | functions. |     |       |               |     |               |     |                |         |
| ----------- | ------------ | --- | -------- | --------------- | --- | ---------- | --- | ----- | ------------- | --- | ------------- | --- | -------------- | ------- |
|             |              |     |          |                 |     |            |     | tion. | But combining |     | with stronger |     | regularization | may im- |
Fig.7showsthatResNetshavegenerallysmallerresponses
proveresults,whichwewillstudyinthefuture.
| thantheirplaincounterparts. |     |     | Theseresultssupportourba- |     |     |     |     |     |     |     |     |     |     |     |
| --------------------------- | --- | --- | ------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
sic motivation (Sec.3.1) that the residual functions might 4.3.ObjectDetectiononPASCALandMSCOCO
begenerallyclosertozerothanthenon-residualfunctions.
|         |        |          |        |            |         |        |     | Our                    | method | has | good generalization |     | performance       | on  |
| ------- | ------ | -------- | ------ | ---------- | ------- | ------ | --- | ---------------------- | ------ | --- | ------------------- | --- | ----------------- | --- |
| We also | notice | that the | deeper | ResNet has | smaller | magni- |     |                        |        |     |                     |     |                   |     |
|         |        |          |        |            |         |        |     | otherrecognitiontasks. |        |     | Table7and           |     | 8showtheobjectde- |     |
tudesofresponses,asevidencedbythecomparisonsamong
|            |     |         |         |         |       |          |     | tection | baseline | results | on PASCAL |     | VOC 2007 | and 2012 |
| ---------- | --- | ------- | ------- | ------- | ----- | -------- | --- | ------- | -------- | ------- | --------- | --- | -------- | -------- |
| ResNet-20, | 56, | and 110 | in Fig. | 7. When | there | are more |     |         |          |         |           |     |          |          |
[5]andCOCO[26].WeadoptFasterR-CNN[32]asthede-
| layers, an | individual | layer | of ResNets | tends | to  | modify the |     |     |     |     |     |     |     |     |
| ---------- | ---------- | ----- | ---------- | ----- | --- | ---------- | --- | --- | --- | --- | --- | --- | --- | --- |
tectionmethod.Hereweareinterestedintheimprovements
signalless.
|     |     |     |     |     |     |     |     | ofreplacingVGG-16[41]withResNet-101. |     |     |     |     | Thedetection |     |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------------------------------ | --- | --- | --- | --- | ------------ | --- |
Exploring Over 1000 layers. We explore an aggressively implementation(seeappendix)ofusingbothmodelsisthe
deep model of over 1000 layers. We set n that same,sothegainscanonlybeattributedtobetternetworks.
= 200
leadstoa1202-layernetwork,whichistrainedasdescribed Mostremarkably,onthechallengingCOCOdatasetweob-
above. Our method shows no optimization difficulty, and taina6.0%increaseinCOCO’sstandardmetric(mAP@[.5,
103-layer
this network is able to achieve training error .95]), which is a 28% relative improvement. This gain is
<0.1% (Fig. 6, right). Its test error is still fairly good solelyduetothelearnedrepresentations.
(7.93%,Table6). Based on deep residual nets, we won the 1st places in
But there are still open problems on such aggressively severaltracksinILSVRC&COCO2015competitions:Im-
deepmodels. Thetestingresultofthis1202-layernetwork ageNetdetection,ImageNetlocalization,COCOdetection,
isworsethanthatofour110-layernetwork, althoughboth andCOCOsegmentation. Thedetailsareintheappendix.
8