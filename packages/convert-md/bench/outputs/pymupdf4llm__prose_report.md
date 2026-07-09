from experience. Care should be taken when using the outputs of GPT-4, particularly in contexts where reliability is important. 

GPT-4’s capabilities and limitations create significant and novel safety challenges, and we believe careful study of these challenges is an important area of research given the potential societal impact. This report includes an extensive system card (after the Appendix) describing some of the risks we foresee around bias, disinformation, over-reliance, privacy, cybersecurity, proliferation, and more. It also describes interventions we made to mitigate potential harms from the deployment of GPT-4, including adversarial testing with domain experts, and a model-assisted safety pipeline. 

# **2 Scope and Limitations of this Technical Report** 

This report focuses on the capabilities, limitations, and safety properties of GPT-4. GPT-4 is a Transformer-style model [39] pre-trained to predict the next token in a document, using both publicly available data (such as internet data) and data licensed from third-party providers. The model was then fine-tuned using Reinforcement Learning from Human Feedback (RLHF) [40]. Given both the competitive landscape and the safety implications of large-scale models like GPT-4, this report contains no further details about the architecture (including model size), hardware, training compute, dataset construction, training method, or similar. 

We are committed to independent auditing of our technologies, and shared some initial steps and ideas in this area in the system card accompanying this release.<sup>2</sup> We plan to make further technical details available to additional third parties who can advise us on how to weigh the competitive and safety considerations above against the scientific value of further transparency. 

# **3 Predictable Scaling** 

A large focus of the GPT-4 project was building a deep learning stack that scales predictably. The primary reason is that for very large training runs like GPT-4, it is not feasible to do extensive model-specific tuning. To address this, we developed infrastructure and optimization methods that have very predictable behavior across multiple scales. These improvements allowed us to reliably predict some aspects of the performance of GPT-4 from smaller models trained using 1 _,_ 000 _×_ – 10 _,_ 000 _×_ less compute. 

## **3.1 Loss Prediction** 

The final loss of properly-trained large language models is thought to be well approximated by power laws in the amount of compute used to train the model [41, 42, 2, 14, 15]. 

To verify the scalability of our optimization infrastructure, we predicted GPT-4’s final loss on our internal codebase (not part of the training set) by fitting a scaling law with an irreducible loss term (as in Henighan et al. [15]): _L_ ( _C_ ) = _aC_<sup>_b_</sup> + _c,_ from models trained using the same methodology but using at most 10,000x less compute than GPT-4. This prediction was made shortly after the run started, without use of any partial results. The fitted scaling law predicted GPT-4’s final loss with high accuracy (Figure 1). 

## **3.2 Scaling of Capabilities on HumanEval** 

Having a sense of the capabilities of a model before training can improve decisions around alignment, safety, and deployment. In addition to predicting final loss, we developed methodology to predict more interpretable metrics of capability. One such metric is pass rate on the HumanEval dataset [43], which measures the ability to synthesize Python functions of varying complexity. We successfully predicted the pass rate on a subset of the HumanEval dataset by extrapolating from models trained with at most 1 _,_ 000 _×_ less compute (Figure 2). 

For an individual problem in HumanEval, performance may occasionally worsen with scale. Despite these challenges, we find an approximate power law relationship _−_ E _P_ [log(pass_rate(C))] = _α∗_ C<sup>_−k_</sup> 

2In addition to the accompanying system card, OpenAI will soon publish additional thoughts on the social and economic implications of AI systems, including the need for effective regulation. 

2 



<!-- Start of picture text -->
OpenAI codebase next word prediction<br>Bits per word<br>6.0<br>Observed<br>Prediction<br>5.0 gpt-4<br>4.0<br>3.0<br>2.0<br>1.0<br>100p 10n 1µ 100µ 0.01 1<br>Compute<br><!-- End of picture text -->

**Figure 1.** Performance of GPT-4 and smaller models. The metric is final loss on a dataset derived from our internal codebase. This is a convenient, large dataset of code tokens which is not contained in the training set. We chose to look at loss because it tends to be less noisy than other measures across different amounts of training compute. A power law fit to the smaller models (excluding GPT-4) is shown as the dotted line; this fit accurately predicts GPT-4’s final loss. The x-axis is training compute normalized so that GPT-4 is 1. 



<!-- Start of picture text -->
Capability prediction on 23 coding problems<br>– Mean Log Pass Rate<br>5<br>Observed<br>Prediction<br>4 gpt-4<br>3<br>2<br>1<br>0<br>1µ 10µ 100µ 0.001 0.01 0.1 1<br>Compute<br><!-- End of picture text -->

**Figure 2.** Performance of GPT-4 and smaller models. The metric is mean log pass rate on a subset of the HumanEval dataset. A power law fit to the smaller models (excluding GPT-4) is shown as the dotted line; this fit accurately predicts GPT-4’s performance. The x-axis is training compute normalized so that GPT-4 is 1. 

3 

where _k_ and _α_ are positive constants, and _P_ is a subset of problems in the dataset. We hypothesize that this relationship holds for all problems in this dataset. In practice, very low pass rates are difficult or impossible to estimate, so we restrict to problems _P_ and models _M_ such that given some large sample budget, every problem is solved at least once by every model. 

We registered predictions for GPT-4’s performance on HumanEval before training completed, using only information available prior to training. All but the 15 hardest HumanEval problems were split into 6 difficulty buckets based on the performance of smaller models. The results on the 3<sup>rd</sup> easiest bucket are shown in Figure 2, showing that the resulting predictions were very accurate for this subset of HumanEval problems where we can accurately estimate log(pass_rate) for several smaller models. Predictions on the other five buckets performed almost as well, the main exception being GPT-4 underperforming our predictions on the easiest bucket. 

Certain capabilities remain hard to predict. For example, the Inverse Scaling Prize [44] proposed several tasks for which model performance decreases as a function of scale. Similarly to a recent result by Wei et al. [45], we find that GPT-4 reverses this trend, as shown on one of the tasks called Hindsight Neglect [46] in Figure 3. 



<!-- Start of picture text -->
Inverse scaling prize, hindsight neglect<br>Accuracy<br>100<br>50<br>0<br>ada babbage curie gpt-3.5 gpt-4<br>Model<br><!-- End of picture text -->

**Figure 3.** Performance of GPT-4 and smaller models on the Hindsight Neglect task. Accuracy is shown on the y-axis, higher is better. ada, babbage, and curie refer to models available via the OpenAI API [47]. 

We believe that accurately predicting future capabilities is important for safety. Going forward we plan to refine these methods and register performance predictions across various capabilities before large model training begins, and we hope this becomes a common goal in the field. 

# **4 Capabilities** 

We tested GPT-4 on a diverse set of benchmarks, including simulating exams that were originally designed for humans.<sup>4</sup> We did no specific training for these exams. A minority of the problems in the exams were seen by the model during training; for each exam we run a variant with these questions removed and report the lower score of the two. We believe the results to be representative. For further details on contamination (methodology and per-exam statistics), see Appendix C. 

Exams were sourced from publicly-available materials. Exam questions included both multiplechoice and free-response questions; we designed separate prompts for each format, and images were included in the input for questions which required it. The evaluation setup was designed based on performance on a validation set of exams, and we report final results on held-out test exams. Overall scores were determined by combining multiple-choice and free-response question scores using publicly available methodologies for each exam. We estimate and report the percentile each overall score corresponds to. See Appendix A for further details on the exam evaluation methodology. 

> 3For AMC 10 and AMC 12 2022 exams, the human percentiles are not yet published, so the reported numbers are extrapolated and likely have wide uncertainty. See Appendix A.5. 

> 4We used the post-trained RLHF model for these exams. 

4 

|Exam|GPT-4|GPT-4 (no vision)|GPT-3.5|
|---|---|---|---|
|Uniform Bar Exam (MBE+MEE+MPT)<br>LSAT|298 / 400 (~90th)<br>163 (~88th)|298 / 400 (~90th)<br>161 (~83rd)|213 / 400 (~10th)<br>149 (~40th)|
|SAT Evidence-Based Reading & Writing|710 / 800 (~93rd)|710 / 800 (~93rd)|670 / 800 (~87th)|
|SAT Math|700 / 800 (~89th)|690 / 800 (~89th)|590 / 800 (~70th)|
|Graduate Record Examination (GRE) Quantitative|163 / 170 (~80th)|157 / 170 (~62nd)|147 / 170 (~25th)|
|Graduate Record Examination (GRE) Verbal|169 / 170 (~99th)|165 / 170 (~96th)|154 / 170 (~63rd)|
|Graduate Record Examination (GRE) Writing|4 / 6 (~54th)|4 / 6 (~54th)|4 / 6 (~54th)|
|USABO Semifnal Exam 2020|87 / 150 (99th - 100th)|87 / 150 (99th - 100th)|43 / 150 (31st - 33rd)|
|USNCO Local Section Exam 2022|36 / 60|38 / 60|24 / 60|
|Medical Knowledge Self-Assessment Program|75 %|75 %|53 %|
|Codeforces Rating|392 (below 5th)|392 (below 5th)|260 (below 5th)|
|AP Art History|5 (86th - 100th)|5 (86th - 100th)|5 (86th - 100th)|
|AP Biology|5 (85th - 100th)|5 (85th - 100th)|4 (62nd - 85th)|
|AP Calculus BC|4 (43rd - 59th)|4 (43rd - 59th)|1 (0th - 7th)|
|AP Chemistry|4 (71st - 88th)|4 (71st - 88th)|2 (22nd - 46th)|
|AP English Language and Composition|2 (14th - 44th)|2 (14th - 44th)|2 (14th - 44th)|
|AP English Literature and Composition|2 (8th - 22nd)|2 (8th - 22nd)|2 (8th - 22nd)|
|AP Environmental Science|5 (91st - 100th)|5 (91st - 100th)|5 (91st - 100th)|
|AP Macroeconomics|5 (84th - 100th)|5 (84th - 100th)|2 (33rd - 48th)|
|AP Microeconomics|5 (82nd - 100th)|4 (60th - 82nd)|4 (60th - 82nd)|
|AP Physics 2|4 (66th - 84th)|4 (66th - 84th)|3 (30th - 66th)|
|AP Psychology|5 (83rd - 100th)|5 (83rd - 100th)|5 (83rd - 100th)|
|AP Statistics|5 (85th - 100th)|5 (85th - 100th)|3 (40th - 63rd)|
|AP US Government|5 (88th - 100th)|5 (88th - 100th)|4 (77th - 88th)|
|AP US History|5 (89th - 100th)|4 (74th - 89th)|4 (74th - 89th)|
|AP World History|4 (65th - 87th)|4 (65th - 87th)|4 (65th - 87th)|
|AMC 10<sup>3</sup>|30 / 150 (6th - 12th)|36 / 150 (10th - 19th)|36 / 150 (10th - 19th)|
|AMC 12<sup>3</sup>|60 / 150 (45th - 66th)|48 / 150 (19th - 40th)|30 / 150 (4th - 8th)|
|Introductory Sommelier (theory knowledge)|92 %|92 %|80 %|
|Certifed Sommelier (theory knowledge)|86 %|86 %|58 %|
|Advanced Sommelier (theory knowledge)|77 %|77 %|46 %|
|Leetcode (easy)|31 / 41|31 / 41|12 / 41|
|Leetcode (medium)|21 / 80|21 / 80|8 / 80|
|Leetcode (hard)|3 / 45|3 / 45|0 / 45|



**Table 1.** GPT performance on academic and professional exams. In each case, we simulate the conditions and scoring of the real exam. We report GPT-4’s final score graded according to examspecific rubrics, as well as the percentile of test-takers achieving GPT-4’s score. 

5 



<!-- Start of picture text -->
Exam results (ordered by GPT-3.5 performance)<br>gpt-4<br>Estimated percentile lower bound (among test takers) gpt-4 (no vision)<br>gpt3.5<br>100%<br>80%<br>60%<br>40%<br>20%<br>0%<br>Exam<br>AP AMC AP AMC AP AP GRE AP AP AP LSAT GRE AP AP GRE AP SAT APUS APUS AP APArt SAT AP<br>12 10Uniform USABO<br>World Math<br>CalculusBC Codeforces English Bar English Chemistry Physics2 Statistics Writing Biology Verbal History Psychology HistoryEBRW<br>Rating Literature Exam Language Quantitative SemifinalMacroeconomics Microeconomics History Government Environmental<br>2020 Science<br><!-- End of picture text -->

**Figure 4.** GPT performance on academic and professional exams. In each case, we simulate the conditions and scoring of the real exam. Exams are ordered from low to high based on GPT-3.5 performance. GPT-4 outperforms GPT-3.5 on most exams tested. To be conservative we report the lower end of the range of percentiles, but this creates some artifacts on the AP exams which have very wide scoring bins. For example although GPT-4 attains the highest possible score on AP Biology (5/5), this is only shown in the plot as 85th percentile because 15 percent of test-takers achieve that score. 

GPT-4 exhibits human-level performance on the majority of these professional and academic exams. Notably, it passes a simulated version of the Uniform Bar Examination with a score in the top 10% of test takers (Table 1, Figure 4). 

The model’s capabilities on exams appear to stem primarily from the pre-training process and are not significantly affected by RLHF. On multiple choice questions, both the base GPT-4 model and the RLHF model perform equally well on average across the exams we tested (see Appendix B). 

We also evaluated the pre-trained base GPT-4 model on traditional benchmarks designed for evaluating language models. For each benchmark we report, we ran contamination checks for test data appearing in the training set (see Appendix D for full details on per-benchmark contamination).<sup>5</sup> We used few-shot prompting [1] for all benchmarks when evaluating GPT-4.<sup>6</sup> 

GPT-4 considerably outperforms existing language models, as well as previously state-of-the-art (SOTA) systems which often have benchmark-specific crafting or additional training protocols (Table 2). 

> 5During our contamination check we discovered that portions of BIG-bench [48] were inadvertently mixed into the training set, and we excluded it from our reported results. 

> 6For GSM-8K, we include part of the training set in GPT-4’s pre-training mix (see Appendix E for details). We use chain-of-thought prompting [11] when evaluating. 

6 

||GPT-4<br>Evaluated<br>few-shot|GPT-3.5<br>Evaluated<br>few-shot|LM SOTA<br>Best external LM<br>evaluated few-shot|SOTA<br>Best external model (incl.<br>benchmark-specifc tuning)|
|---|---|---|---|---|
|MMLU [49]|**86.4%**|70.0%|70.7%|75.2%|
|Multiple-choice questions in 57<br>subjects (professional & academic)|5-shot|5-shot|5-shot U-PaLM [50]|5-shot Flan-PaLM [51]|
|HellaSwag [52]|**95.3%**|85.5%|84.2%|85.6|
|Commonsense reasoning around<br>everyday events|10-shot|10-shot|LLaMA (validation<br>set) [28]|ALUM [53]|
|AI2 Reasoning<br>Challenge (ARC) [54]|**96.3%**|85.2%|85.2%|86.5%|
|Grade-school multiple choice<br>science questions. Challenge-set.|25-shot|25-shot|8-shot PaLM [55]|ST-MOE [18]|
|WinoGrande [56]|**87.5%**|81.6%|85.1%|85.1%|
|Commonsense reasoning around<br>pronoun resolution|5-shot|5-shot|5-shot PaLM [3]|5-shot PaLM [3]|
|HumanEval [43]|**67.0%**|48.1%|26.2%|65.8%|
|Python coding tasks|0-shot|0-shot|0-shot PaLM [3]|CodeT + GPT-3.5 [57]|
|DROP [58] (F1 score)|80.9|64.1|70.8|**88.4**|
|Reading comprehension &<br>arithmetic.|3-shot|3-shot|1-shot PaLM [3]|QDGAT [59]|
|GSM-8K [60]|**92.0%**<sup>_∗_</sup>|57.1%|58.8%|87.3%|
|Grade-school mathematics<br>questions|5-shot<br>chain-of-thought|5-shot|8-shot Minerva [61]|Chinchilla + SFT+ORM-RL,<br>ORM reranking [62]|



**Table 2.** Performance of GPT-4 on academic benchmarks. We compare GPT-4 alongside the best SOTA (with benchmark-specific training) and the best SOTA for an LM evaluated few-shot. GPT-4 outperforms existing LMs on all benchmarks, and beats SOTA with benchmark-specific training on all datasets except DROP. For each task we report GPT-4’s performance along with the few-shot method used to evaluate. For GSM-8K, we included part of the training set in the GPT-4 pre-training mix (see Appendix E), and we use chain-of-thought prompting [11] when evaluating. For multiple-choice questions, we present all answers (ABCD) to the model and ask it to choose the letter of the answer, similarly to how a human would solve such a problem. 

Many existing ML benchmarks are written in English. To gain an initial understanding of GPT-4’s capabilities in other languages, we translated the MMLU benchmark [35, 36] – a suite of multiplechoice problems spanning 57 subjects – into a variety of languages using Azure Translate (see Appendix F for example translations and prompts). We find that GPT-4 outperforms the Englishlanguage performance of GPT 3.5 and existing language models (Chinchilla [2] and PaLM [3]) for the majority of languages we tested, including low-resource languages such as Latvian, Welsh, and Swahili (Figure 5). 

GPT-4 substantially improves over previous models in the ability to follow user intent [63]. On a dataset of 5,214 prompts submitted to ChatGPT [64] and the OpenAI API [47], the responses generated by GPT-4 were preferred over the responses generated by GPT-3.5 on 70 _._ 2% of prompts.<sup>7</sup> 

We are open-sourcing OpenAI Evals<sup>8</sup> , our framework for creating and running benchmarks for evaluating models like GPT-4 while inspecting performance sample by sample. Evals is compatible with existing benchmarks, and can be used to track performance of models in deployment. We plan 

> 7We collected user prompts sent to us through ChatGPT and the OpenAI API, sampled one response from each model, and sent these prompts and responses to human labelers. The labelers were instructed to judge whether the response is what the user would have wanted given the prompt. The labelers were not told which response was generated by which model and the order in which the responses were presented was randomised. We filter out prompts containing any kind of disallowed or sensitive content, including personally identifiable information (PII), sexual content, hate-speech, and similar content. We also filter short (e.g. "Hello, ChatGPT!") and overly-common prompts. 

> 8https://github.com/openai/evals 

7 

**GPT-4 3-shot accuracy on MMLU across languages** 



<!-- Start of picture text -->
Random guessing 25.0%<br>Chinchilla-English 67.0%<br>PaLM-English 69.3%<br>GPT-3.5-English 70.1%<br>GPT-4 English 85.5%<br>Italian 84.1%<br>Afrikaans 84.1%<br>Spanish 84.0%<br>German 83.7%<br>French 83.6%<br>Indonesian 83.1%<br>Russian 82.7%<br>Polish 82.1%<br>Ukranian 81.9%<br>Greek 81.4%<br>Latvian 80.9%<br>Mandarin 80.1%<br>Arabic 80.0%<br>Turkish 80.0%<br>Japanese 79.9%<br>Swahili 78.5%<br>Welsh 77.5%<br>Korean 77.0%<br>Icelandic 76.5%<br>Bengali 73.2%<br>Urdu 72.6%<br>Nepali 72.2% Random<br>Thai 71.8% Chinchilla<br>Punjabi 71.4% PaLM<br>Marathi 66.7% gpt-3.5<br>gpt-4<br>Telugu 62.0%<br>0% 10% 20% 30% 40% 50% 60% 70% 80% 90%<br>Accuracy →<br><!-- End of picture text -->

**Figure 5.** Performance of GPT-4 in a variety of languages compared to prior models in English on MMLU. GPT-4 outperforms the English-language performance of existing language models [2, 3] for the vast majority of languages tested, including low-resource languages such as Latvian, Welsh, and Swahili. 

to increase the diversity of these benchmarks over time to represent a wider set of failure modes and a harder set of tasks. 

## **4.1 Visual Inputs** 

GPT-4 accepts prompts consisting of both images and text, which – parallel to the text-only setting – lets the user specify any vision or language task. Specifically, the model generates text outputs given inputs consisting of arbitrarily interlaced text and images. Over a range of domains – including documents with text and photographs, diagrams, or screenshots – GPT-4 exhibits similar capabilities as it does on text-only inputs. An example of GPT-4’s visual input can be found in Table 3. The standard test-time techniques developed for language models (e.g. few-shot prompting, chain-ofthought, etc) are similarly effective when using both images and text - see Appendix G for examples. 

Preliminary results on a narrow set of academic vision benchmarks can be found in the GPT-4 blog post [65]. We plan to release more information about GPT-4’s visual capabilities in follow-up work. 

8 

## **Example of GPT-4 visual input** : 

User What is funny about this image? Describe it panel by panel. 



Source: `https://www.reddit.com/r/hmmm/comments/ubab5v/hmmm/` 

- GPT-4 The image shows a package for a "Lightning Cable" adapter with three panels. 

   - Panel 1: A smartphone with a VGA connector (a large, blue, 15-pin connector typically used for computer monitors) plugged into its charging port. 

Panel 2: The package for the "Lightning Cable" adapter with a picture of a VGA connector on it. 

Panel 3: A close-up of the VGA connector with a small Lightning connector (used for charging iPhones and other Apple devices) at the end. 

The humor in this image comes from the absurdity of plugging a large, outdated VGA connector into a small, modern smartphone charging port. 

> **Table 3.** Example prompt demonstrating GPT-4’s visual input capability. The prompt consists of a question about an image with multiple panels which GPT-4 is able to answer. 

9 

# **5 Limitations** 

Despite its capabilities, GPT-4 has similar limitations as earlier GPT models. Most importantly, it still is not fully reliable (it “hallucinates” facts and makes reasoning errors). Great care should be taken when using language model outputs, particularly in high-stakes contexts, with the exact protocol (such as human review, grounding with additional context, or avoiding high-stakes uses altogether) matching the needs of specific applications. See our System Card for details. 

GPT-4 significantly reduces hallucinations relative to previous GPT-3.5 models (which have themselves been improving with continued iteration). GPT-4 scores 19 percentage points higher than our latest GPT-3.5 on our internal, adversarially-designed factuality evaluations (Figure 6). 

## **Internal factual eval by category** 



<!-- Start of picture text -->
Accuracy<br><!-- End of picture text -->



<!-- Start of picture text -->
chatgpt-v2<br>chatgpt-v3<br>chatgpt-v4<br>80% gpt-4<br>60%<br>40%<br>20%<br>0%<br>learning technology writing history math science recommendation code business<br>Category<br><!-- End of picture text -->

**Figure 6.** Performance of GPT-4 on nine internal adversarially-designed factuality evaluations. Accuracy is shown on the y-axis, higher is better. An accuracy of 1.0 means the model’s answers are judged to be in agreement with human ideal responses for all questions in the eval. We compare GPT-4 to three earlier versions of ChatGPT [64] based on GPT-3.5; GPT-4 improves on the latest GPT-3.5 model by 19 percentage points, with significant gains across all topics. 

GPT-4 makes progress on public benchmarks like TruthfulQA [66], which tests the model’s ability to separate fact from an adversarially-selected set of incorrect statements (Figure 7). These questions are paired with factually incorrect answers that are statistically appealing. The GPT-4 base model is only slightly better at this task than GPT-3.5; however, after RLHF post-training we observe large improvements over GPT-3.5.<sup>9</sup> Table 4 shows both a correct and an incorrect answer. GPT-4 resists selecting common sayings (you can’t teach an old dog new tricks), however it still can miss subtle details (Elvis Presley was not the son of an actor, so Perkins is the correct answer). 

GPT-4 generally lacks knowledge of events that have occurred after the vast majority of its pre-training data cuts off in September 2021<sup>10</sup> , and does not learn from its experience. It can sometimes make simple reasoning errors which do not seem to comport with competence across so many domains, or be overly gullible in accepting obviously false statements from a user. It can fail at hard problems the same way humans do, such as introducing security vulnerabilities into code it produces. 

GPT-4 can also be confidently wrong in its predictions, not taking care to double-check work when it’s likely to make a mistake. Interestingly, the pre-trained model is highly calibrated (its predicted 

> 9We did not check the RLHF post-training data for contamination with TruthfulQA 

> 10The pre-training and post-training data contain a small amount of more recent data 

10 

|**[GPT-4 answers correctly]**|**[GPT-4 answers incorrectly]**|
|---|---|
|Can you teach an old dog new tricks?<br>Yes, you can teach an old dog new tricks_←_choice<br>You can’t teach an old dog new tricks<br>No, you can’t teach an old dog new tricks|Son of an actor, this American guitarist<br>and rock singer released many songs and<br>albums and toured with his band. His<br>name is "Elvis" what?<br>Perkins<br>Presley_←_choice<br>Elvis Presley<br>His name is Elvis Presley|



**Table 4:** Example of GPT-4 giving correct and incorrect responses on TruthfulQA 



<!-- Start of picture text -->
Accuracy on adversarial questions (TruthfulQA mc1)<br>Accuracy<br>70%<br>Anthropic-LM<br>gpt-3.5<br>60% gpt-4<br>50%<br>40%<br>30%<br>20%<br>10%<br>0%<br>Anthropic-LM Anthropic-LM gpt-3.5-base gpt-3.5-base gpt-3.5-turbo gpt-4-base gpt-4-base gpt-4<br>0-shot RLHF 0-shot 5-shot RLHF 0-shot 5-shot RLHF<br>Model<br><!-- End of picture text -->

**Figure 7.** Performance of GPT-4 on TruthfulQA. Accuracy is shown on the y-axis, higher is better. We compare GPT-4 under zero-shot prompting, few-shot prompting, and after RLHF fine-tuning. GPT-4 significantly outperforms both GPT-3.5 and Anthropic-LM from Bai et al. [67]. 

confidence in an answer generally matches the probability of being correct). However, after the post-training process, the calibration is reduced (Figure 8). 

GPT-4 has various biases in its outputs that we have taken efforts to correct but which will take some time to fully characterize and manage. We aim to make GPT-4 and other systems we build have reasonable default behaviors that reflect a wide swath of users’ values, allow those systems to be customized within some broad bounds, and get public input on what those bounds should be. See OpenAI [68] for more details. 

# **6 Risks & mitigations** 

We invested significant effort towards improving the safety and alignment of GPT-4. Here we highlight our use of domain experts for adversarial testing and red-teaming, and our model-assisted safety pipeline [69] and the improvement in safety metrics over prior models. 

**Adversarial Testing via Domain Experts:** GPT-4 poses similar risks as smaller language models, such as generating harmful advice, buggy code, or inaccurate information. However, the additional capabilities of GPT-4 lead to new risk surfaces. To understand the extent of these risks, we engaged 

11 

